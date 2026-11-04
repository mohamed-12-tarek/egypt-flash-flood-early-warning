"""SQL tools for the flood-risk agent.

Every tool:
  * runs fixed, parameterised, read-only queries (the LLM never writes SQL),
  * returns JSON with ``status`` = ok | no_data | error,
  * includes ``data_as_of`` (UTC timestamp of the newest data used) and a
    ``stale`` flag, so answers can always show how fresh the numbers are.

The plain functions (``current_risk`` ...) return dicts and are reused by the
alert writer; ``TOOLS`` wraps them as LangChain tools for the agent.
"""

import json
import re
import unicodedata
from datetime import datetime
from typing import Any

from langchain_core.tools import tool

from genai import db
from genai.settings import (
    CITIES, CITY_ALIASES, CITY_AR, LEVEL_RANK, LEVELS, STALE_AFTER_HOURS, utcnow,
)

RISK_COLUMNS = "city, event_time, avg_rainfall, rain_sum_24h, rain_sum_72h, risk_score, risk_level"


def _norm(text_: str) -> str:
    text_ = unicodedata.normalize("NFKC", str(text_)).lower().strip()
    text_ = text_.replace("_", " ").replace("-", " ")
    text_ = re.sub(r"[ً-ٟـ]", "", text_)           # Arabic diacritics / tatweel
    text_ = text_.translate(str.maketrans("أإآٱىة", "اااايه"))     # unify alef / ya / ta marbuta
    return re.sub(r"\s+", " ", text_)


_ALIAS_INDEX: dict[str, str] = {}
for _city in CITIES:
    for _name in [_city, CITY_AR[_city], *CITY_ALIASES.get(_city, [])]:
        _ALIAS_INDEX[_norm(_name)] = _city


def resolve_city(name: str) -> str | None:
    """Map free text (Arabic/English, any case) to a canonical city name."""
    key = _norm(name)
    if key in _ALIAS_INDEX:
        return _ALIAS_INDEX[key]
    for alias, city in sorted(_ALIAS_INDEX.items(), key=lambda kv: -len(kv[0])):
        if len(alias) >= 4 and alias in key:
            return city
    return None


def _ok(rows: Any, as_of, **extra) -> dict:
    as_of_dt = db.to_datetime(as_of)
    stale = bool(as_of_dt and (utcnow() - as_of_dt).total_seconds() > STALE_AFTER_HOURS * 3600)
    return {
        "status": "ok",
        "data_as_of": db.to_iso(as_of_dt),
        "timezone": "UTC",
        "stale": stale,
        "count": len(rows) if isinstance(rows, list) else None,   # lets the agent state "N regions/events" with a grounded number
        **extra,
        "rows": rows,
    }


def _no_data(reason: str, **extra) -> dict:
    return {"status": "no_data", "reason": reason, **extra, "rows": []}


def _bad_city(name: str) -> dict:
    return {
        "status": "error",
        "reason": f"Unknown region '{name}'.",
        "valid_regions": CITIES,
        "valid_regions_count": len(CITIES),
        "rows": [],
    }


def _risk_row(row: dict) -> dict:
    return {
        "city": row["city"],
        "event_time": db.to_iso(row["event_time"]),
        "risk_score": int(row["risk_score"]),
        "risk_level": row["risk_level"],
        "avg_rainfall_mm": round(float(row["avg_rainfall"]), 2),
        "rain_sum_24h_mm": round(float(row["rain_sum_24h"]), 2),
        "rain_sum_72h_mm": round(float(row["rain_sum_72h"]), 2),
    }


def _latest_event_time(city: str | None = None):
    if city:
        rows = db.run_query(
            "SELECT MAX(event_time) AS t FROM gold.fact_hourly_risk WHERE city = :city", {"city": city}
        )
    else:
        rows = db.run_query("SELECT MAX(event_time) AS t FROM gold.fact_hourly_risk")
    return rows[0]["t"] if rows else None


def list_regions() -> dict:
    return {
        "status": "ok",
        "count": len(CITIES),
        "rows": [{"city": c, "name_ar": CITY_AR[c]} for c in CITIES],
        "risk_levels": LEVELS,
    }


def current_risk(city: str) -> dict:
    canonical = resolve_city(city)
    if not canonical:
        return _bad_city(city)
    latest = _latest_event_time(canonical)
    if latest is None:
        return _no_data(f"No risk data stored for {canonical}.", city=canonical)
    rows = db.run_query(
        f"SELECT {RISK_COLUMNS} FROM gold.fact_hourly_risk "
        "WHERE city = :city AND event_time = :t",
        {"city": canonical, "t": db.to_param(db.to_datetime(latest))},
    )
    if not rows:
        return _no_data(f"No risk data stored for {canonical}.", city=canonical)
    return _ok([_risk_row(rows[0])], as_of=latest, city=canonical)


def top_risky_regions(n: int = 5) -> dict:
    n = max(1, min(int(n), len(CITIES)))
    latest = _latest_event_time()
    if latest is None:
        return _no_data("The risk table is empty.")
    # only look at the most recent hours; one latest row per city
    since = db.hours_before(latest, 6)
    rows = db.run_query(
        f"""
        SELECT {RISK_COLUMNS} FROM (
            SELECT {RISK_COLUMNS},
                   ROW_NUMBER() OVER (PARTITION BY city ORDER BY event_time DESC) AS rn
            FROM gold.fact_hourly_risk
            WHERE event_time >= :since
        ) t WHERE rn = 1
        """,
        {"since": since},
    )
    if not rows:
        return _no_data("No recent risk data.")
    rows.sort(key=lambda r: (-int(r["risk_score"]), r["city"]))
    out = [_risk_row(r) for r in rows[:n]]
    as_of = max(db.to_datetime(r["event_time"]) for r in rows)
    return _ok(out, as_of=as_of, ranked_by="risk_score (descending)", regions_covered=len(rows))


def risk_history(city: str, hours: int = 24) -> dict:
    canonical = resolve_city(city)
    if not canonical:
        return _bad_city(city)
    hours = max(1, min(int(hours), 168))
    latest = _latest_event_time(canonical)
    if latest is None:
        return _no_data(f"No risk data stored for {canonical}.", city=canonical)
    rows = db.run_query(
        f"SELECT {RISK_COLUMNS} FROM gold.fact_hourly_risk "
        "WHERE city = :city AND event_time >= :since ORDER BY event_time",
        {"city": canonical, "since": db.hours_before(latest, hours)},
    )
    if not rows:
        return _no_data("No rows in the requested window.", city=canonical)
    return _ok([_risk_row(r) for r in rows], as_of=latest, city=canonical, window_hours=hours)


def weather_outlook(city: str) -> dict:
    """Model predictions (gold.predictions) for the hours after the latest observation."""
    canonical = resolve_city(city)
    if not canonical:
        return _bad_city(city)
    latest = _latest_event_time(canonical)
    if latest is None:
        return _no_data(f"No risk data stored for {canonical}.", city=canonical)
    rows = db.run_query(
        """
        SELECT predicted_for, predicted_rainfall, predicted_risk_score, predicted_risk_level,
               model_version, generated_at
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY predicted_for ORDER BY generated_at DESC) AS rn
            FROM gold.predictions
            WHERE city = :city AND predicted_for >= :since
        ) t WHERE rn = 1 ORDER BY predicted_for
        """,
        {"city": canonical, "since": db.to_param(db.to_datetime(latest))},
    )
    if not rows:
        return _no_data(
            "No forecast/prediction rows are available for this region yet.", city=canonical
        )
    out = [
        {
            "predicted_for": db.to_iso(r["predicted_for"]),
            "predicted_rainfall_mm": round(float(r["predicted_rainfall"]), 2),
            "predicted_risk_score": int(r["predicted_risk_score"]),
            "predicted_risk_level": r["predicted_risk_level"],
        }
        for r in rows
    ]
    generated = max(db.to_datetime(r["generated_at"]) for r in rows)
    return _ok(out, as_of=generated, city=canonical, model_version=rows[-1]["model_version"],
               note="These are model predictions, not observations.")


def past_events(city: str | None = None, min_level: str = "Danger", days: int = 365) -> dict:
    """Group consecutive high-risk hours into events (gap <= 3h joins hours)."""
    canonical = None
    if city:
        canonical = resolve_city(city)
        if not canonical:
            return _bad_city(city)
    if min_level not in LEVEL_RANK or min_level == "Safe":
        return {"status": "error", "reason": "min_level must be one of Watch, Danger, Severe Danger", "rows": []}
    days = max(1, min(int(days), 1825))
    latest = _latest_event_time(canonical)
    if latest is None:
        return _no_data("No risk data stored.", city=canonical)
    levels = [lv for lv in LEVELS if LEVEL_RANK[lv] >= LEVEL_RANK[min_level]]
    placeholders = ", ".join(f":lv{i}" for i in range(len(levels)))
    params = {f"lv{i}": lv for i, lv in enumerate(levels)}
    params["since"] = db.hours_before(latest, days * 24)
    city_filter = ""
    if canonical:
        city_filter = "AND city = :city"
        params["city"] = canonical
    rows = db.run_query(
        f"SELECT {RISK_COLUMNS} FROM gold.fact_hourly_risk "
        f"WHERE risk_level IN ({placeholders}) AND event_time >= :since {city_filter} "
        "ORDER BY city, event_time",
        params,
    )
    events: list[dict] = []
    for r in rows:
        t = db.to_datetime(r["event_time"])
        cur = events[-1] if events else None
        if cur and cur["city"] == r["city"] and (t - cur["_end"]).total_seconds() <= 3 * 3600:
            cur["_end"] = t
            cur["hours_at_or_above_level"] += 1
            if int(r["risk_score"]) > cur["peak_risk_score"]:
                cur.update(peak_risk_score=int(r["risk_score"]), peak_risk_level=r["risk_level"],
                           peak_time=db.to_iso(t))
            cur["max_rain_sum_24h_mm"] = max(cur["max_rain_sum_24h_mm"], round(float(r["rain_sum_24h"]), 2))
        else:
            events.append({
                "city": r["city"], "_start": t, "_end": t, "hours_at_or_above_level": 1,
                "peak_risk_score": int(r["risk_score"]), "peak_risk_level": r["risk_level"],
                "peak_time": db.to_iso(t), "max_rain_sum_24h_mm": round(float(r["rain_sum_24h"]), 2),
            })
    for e in events:
        e["start"], e["end"] = db.to_iso(e.pop("_start")), db.to_iso(e.pop("_end"))
    events.sort(key=lambda e: (-e["peak_risk_score"], e["start"]))
    events_total = len(events)
    events = events[:15]
    if not events:
        return _no_data(f"No events at level {min_level} or above in the last {days} days.",
                        city=canonical, window_days=days)
    return _ok(events, as_of=latest, city=canonical, min_level=min_level, window_days=days,
               ordered_by="peak_risk_score (descending)", events_total=events_total,
               note="Events are computed from the model's hourly risk levels, not from official flood records.")


def _dump(result: dict) -> str:
    return json.dumps(result, ensure_ascii=False, default=str, separators=(",", ":"))   # compact = fewer LLM tokens


@tool
def get_current_risk(city: str) -> str:
    """Latest hourly risk (score 0-100, level, rainfall sums) for ONE region. City may be Arabic or English."""
    return _dump(current_risk(city))


@tool
def get_top_risky_regions(n: int = 5) -> str:
    """The N regions with the highest latest risk score, ranked. Use for 'which areas are most at risk'."""
    return _dump(top_risky_regions(n))


@tool
def get_risk_history(city: str, hours: int = 24) -> str:
    """Hourly risk for one region over the last `hours` hours (max 168), measured from its newest data."""
    return _dump(risk_history(city, hours))


@tool
def get_weather_outlook(city: str) -> str:
    """Model predictions (rainfall and risk) for the coming hours for one region. May be empty."""
    return _dump(weather_outlook(city))


@tool
def get_past_events(city: str = "", min_level: str = "Danger", days: int = 365) -> str:
    """Past high-risk events (consecutive hours at `min_level` or above: Watch, Danger, Severe Danger).
    Leave `city` empty for all regions. `days` up to 1825."""
    return _dump(past_events(city or None, min_level, days))


@tool
def list_supported_regions() -> str:
    """The 15 monitored regions (English and Arabic names) and the possible risk levels."""
    return _dump(list_regions())


SQL_TOOLS = [
    get_current_risk, get_top_risky_regions, get_risk_history,
    get_weather_outlook, get_past_events, list_supported_regions,
]
SQL_TOOL_NAMES = {t.name for t in SQL_TOOLS}
