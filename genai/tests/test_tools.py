import pytest

from genai import tools
from genai.tests.conftest import LATEST


@pytest.mark.parametrize("text,expected", [
    ("Aswan", "Aswan"), ("aswan", "Aswan"), ("أسوان", "Aswan"), ("اسوان", "Aswan"),
    ("St Catherine", "St_Catherine"), ("سانت كاترين", "St_Catherine"),
    ("what's the risk in Sharm El Sheikh today?", "Sharm_El_Sheikh"),
    ("الغردقه", "Hurghada"), ("مرسي علم", "Marsa_Alam"),
])
def test_resolve_city(text, expected):
    assert tools.resolve_city(text) == expected


def test_resolve_city_unknown():
    assert tools.resolve_city("Cairo") is None
    assert tools.resolve_city("") is None


def test_current_risk_ok(sql):
    r = tools.current_risk("Hurghada")
    assert r["status"] == "ok" and r["city"] == "Hurghada"
    row = r["rows"][0]
    assert row["risk_level"] == "Watch" and row["risk_score"] == 35 and row["rain_sum_24h_mm"] == 12.5
    assert r["data_as_of"] == LATEST.strftime("%Y-%m-%dT%H:%M:%S") and r["timezone"] == "UTC"
    assert r["stale"] is False


def test_stale_flag(sql, monkeypatch):
    from datetime import timedelta
    monkeypatch.setattr(tools, "utcnow", lambda: LATEST + timedelta(hours=10))
    assert tools.current_risk("Aswan")["stale"] is True


def test_unknown_city_is_error_with_valid_list(sql):
    r = tools.current_risk("Cairo")
    assert r["status"] == "error" and "Aswan" in r["valid_regions"] and r["rows"] == []


def test_top_risky_sorted(sql):
    r = tools.top_risky_regions(2)
    assert [x["city"] for x in r["rows"]] == ["Hurghada", "St_Catherine"]
    assert r["rows"][0]["risk_score"] >= r["rows"][1]["risk_score"]
    assert r["regions_covered"] == 3


def test_history_window(sql):
    r = tools.risk_history("Aswan", 5)
    assert len(r["rows"]) == 6          # inclusive window: latest hour and 5 hours before
    assert r["rows"][0]["event_time"] < r["rows"][-1]["event_time"]


def test_outlook_no_data_when_no_predictions(sql):
    r = tools.weather_outlook("Hurghada")
    assert r["status"] == "no_data" and r["rows"] == []


def test_outlook_ok(with_predictions):
    r = tools.weather_outlook("Hurghada")
    assert r["status"] == "ok" and len(r["rows"]) == 3 and r["model_version"] == "v1"
    assert max(x["predicted_risk_score"] for x in r["rows"]) == 72


def test_past_events_grouped(sql):
    r = tools.past_events("St_Catherine", "Danger", 30)
    assert r["status"] == "ok" and len(r["rows"]) == 1
    e = r["rows"][0]
    assert e["hours_at_or_above_level"] == 4 and e["peak_risk_score"] == 73 and e["peak_risk_level"] == "Danger"


def test_past_events_none(sql):
    assert tools.past_events("Aswan", "Danger", 30)["status"] == "no_data"
    assert tools.past_events(None, "Safe", 30)["status"] == "error"


def test_tools_are_read_only():
    from genai import db
    with pytest.raises(ValueError):
        db.run_query("DELETE FROM gold.fact_hourly_risk")


def test_results_state_their_own_counts(sql):
    assert tools.top_risky_regions(2)["count"] == 2
    assert tools.risk_history("Aswan", 5)["count"] == 6
    assert tools.past_events("St_Catherine", "Danger", 30)["count"] == 1
    assert tools.past_events("St_Catherine", "Danger", 30)["events_total"] == 1
    assert tools.list_regions()["count"] == 15
    assert tools.current_risk("Cairo")["valid_regions_count"] == 15


def test_tool_json_is_compact_to_save_tokens(sql):
    out = tools.get_current_risk.invoke({"city": "Hurghada"})
    assert '"status":"ok"' in out and '"status": "ok"' not in out
