"""Structured alert data (from SQL) and the deterministic text template.

Nothing here calls an LLM. ``build_alert_payload`` gathers the facts an alert may
state (region, level, peak time, main factors); ``render_template_alert`` turns the
same payload into text and is the fallback when the LLM text fails validation.
"""

import math

from genai import db, tools
from genai.settings import CITY_AR, DISCLAIMER, LEVEL_AR, LEVEL_RANK


FACTOR_REFS = {
    "rain_now_mm": 15.0,     
    "rain_24h_mm": 60.0,
    "rain_72h_mm": 80.0,
}
FACTOR_LABELS = {
    "en": {"rain_now_mm": "rainfall in the current hour", "rain_24h_mm": "rainfall over the last 24 hours",
           "rain_72h_mm": "rainfall over the last 72 hours (wet ground)", "slope_degree": "steep terrain"},
    "ar": {"rain_now_mm": "المطر في الساعة الحالية", "rain_24h_mm": "المطر خلال آخر 24 ساعة",
           "rain_72h_mm": "المطر خلال آخر 72 ساعة (تشبع التربة)", "slope_degree": "تضاريس شديدة الانحدار"},
}
ALERT_LEVELS = {"Watch", "Danger", "Severe Danger"}


def _strength(value: float, ref: float) -> float:
    return 1.0 - math.exp(-max(value, 0.0) / ref)


def _terrain(city: str) -> float | None:
    rows = db.run_query("SELECT slope_degree FROM gold.dim_location WHERE city = :c", {"c": city})
    return round(float(rows[0]["slope_degree"]), 1) if rows else None


def build_alert_payload(city: str) -> dict:
    """Facts for one region. ``status`` is ok | no_data | error."""
    current = tools.current_risk(city)
    if current["status"] != "ok":
        return {"status": current["status"], "reason": current.get("reason"), "city": current.get("city")}
    row = current["rows"][0]
    canonical = current["city"]

    factors = [
        ("rain_now_mm", row["avg_rainfall_mm"]),
        ("rain_24h_mm", row["rain_sum_24h_mm"]),
        ("rain_72h_mm", row["rain_sum_72h_mm"]),
    ]
    ranked = [(name, val, _strength(val, FACTOR_REFS[name])) for name, val in factors if val > 0]
    slope = _terrain(canonical)
    if slope is not None and slope >= 10:
        ranked.append(("slope_degree", slope, _strength(slope, 30.0) * 0.5))
    ranked.sort(key=lambda t: -t[2])
    main_factors = [{"factor": n, "value": v} for n, v, _ in ranked[:3]]

    # peak time: model outlook if available, otherwise the current hour
    outlook = tools.weather_outlook(canonical)
    peak = {"time": row["event_time"], "risk_score": row["risk_score"],
            "risk_level": row["risk_level"], "source": "observed"}
    if outlook["status"] == "ok":
        best = max(outlook["rows"], key=lambda r: (r["predicted_risk_score"], -len(r["predicted_for"])))
        if best["predicted_risk_score"] > peak["risk_score"]:
            peak = {"time": best["predicted_for"], "risk_score": best["predicted_risk_score"],
                    "risk_level": best["predicted_risk_level"], "source": "model_prediction"}

    return {
        "status": "ok",
        "city": canonical,
        "city_ar": CITY_AR[canonical],
        "risk_level": row["risk_level"],
        "risk_score": row["risk_score"],
        "observed_at": row["event_time"],
        "peak": peak,
        "main_factors": main_factors,
        "data_as_of": current["data_as_of"],
        "stale": current["stale"],
        "should_alert": row["risk_level"] in ALERT_LEVELS or peak["risk_level"] in ALERT_LEVELS,
    }


STATIC_NUMBERS = [24.0, 72.0, 100.0]


def allowed_numbers(payload: dict) -> list[float]:
    """Every number an alert text may contain (used by the validator)."""
    from genai.chatbot_chain import extract_numbers

    flat = [str(payload.get(k, "")) for k in ("observed_at", "data_as_of", "risk_score")]
    flat += [str(payload["peak"].get(k, "")) for k in ("time", "risk_score")]
    flat += [str(f["value"]) for f in payload["main_factors"]]
    return STATIC_NUMBERS + [n for t in flat for n in extract_numbers(t)]


def _t(iso: str) -> str:
    return iso.replace("T", " ")[:16] + " UTC"


def render_template_alert(payload: dict, lang: str) -> str:
    """Deterministic alert text (fallback). Contains only payload facts."""
    lvl = payload["risk_level"]
    peak = payload["peak"]
    labels = FACTOR_LABELS[lang]
    factors = [f"{labels[f['factor']]}: {f['value']}" + ("°" if f["factor"] == "slope_degree" else " mm")
               for f in payload["main_factors"]]
    if lang == "ar":
        head = f"تنبيه استرشادي - {payload['city_ar']}"
        if not payload["should_alert"]:
            return f"{head}\nمستوى الخطورة الحالي: {LEVEL_AR[lvl]} ({lvl}) - درجة الخطورة {payload['risk_score']} من 100. لا يوجد ارتفاع في المخاطر حاليًا حسب البيانات."
        lines = [head, f"مستوى الخطورة الحالي: {LEVEL_AR[lvl]} ({lvl}) - درجة {payload['risk_score']} من 100 (قراءة {_t(payload['observed_at'])})."]
        if peak["source"] == "model_prediction":
            lines.append(f"ذروة الخطورة المتوقعة (توقع النموذج): {LEVEL_AR[peak['risk_level']]} ({peak['risk_level']}) - درجة {peak['risk_score']} عند {_t(peak['time'])}.")
        if factors:
            lines.append("أهم العوامل: " + "، ".join(factors) + ".")
        lines.append("ابتعد عن مجاري الأودية والمناطق المنخفضة وتابع التعليمات الرسمية.")
        return "\n".join(lines)
    head = f"Advisory alert - {payload['city']}"
    if not payload["should_alert"]:
        return f"{head}\nCurrent risk level: {lvl} - score {payload['risk_score']} out of 100. No elevated risk according to the data."
    lines = [head, f"Current risk level: {lvl} - score {payload['risk_score']} out of 100 (reading at {_t(payload['observed_at'])})."]
    if peak["source"] == "model_prediction":
        lines.append(f"Expected peak (model prediction): {peak['risk_level']} - score {peak['risk_score']} at {_t(peak['time'])}.")
    if factors:
        lines.append("Main factors: " + "; ".join(factors) + ".")
    lines.append("Stay away from wadi channels and low-lying areas and follow official instructions.")
    return "\n".join(lines)


def with_disclaimer(text: str, lang: str) -> str:
    return text.rstrip() + "\n\n" + DISCLAIMER[lang]
