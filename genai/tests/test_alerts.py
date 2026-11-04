from langchain_core.messages import AIMessage

from genai.alerts import generate_alert, validate_alert_text
from genai.data_to_text import build_alert_payload, render_template_alert
from genai.settings import DISCLAIMER
from genai.tests.conftest import ScriptedLLM


def test_payload_facts(with_predictions):
    p = build_alert_payload("Hurghada")
    assert p["status"] == "ok" and p["risk_level"] == "Watch" and p["should_alert"]
    assert p["peak"]["source"] == "model_prediction" and p["peak"]["risk_score"] == 72
    assert p["peak"]["risk_level"] == "Danger"
    assert p["main_factors"][0]["factor"] in {"rain_now_mm", "rain_24h_mm", "rain_72h_mm"}


def test_payload_safe_region_not_alerting(sql):
    p = build_alert_payload("Aswan")
    assert p["status"] == "ok" and p["should_alert"] is False


def test_payload_no_data_unknown_region(sql):
    assert build_alert_payload("Cairo")["status"] == "error"


GOOD = ("Hurghada is at Watch level with a risk score of 35 at 2026-10-21 23:00 UTC. "
        "A model prediction shows the peak, level Danger, score 72, at 2026-10-22 00:00 UTC. "
        "Rainfall over the last 24 hours was 12.5 mm. Stay away from wadi channels and follow official sources.")


def test_validator_accepts_good_text(with_predictions):
    p = build_alert_payload("Hurghada")
    assert validate_alert_text(GOOD.replace("2026-10-22 00:00", "2026-10-22 00:00"), p) == []


def test_validator_rejects_invented_number_region_and_level(with_predictions):
    p = build_alert_payload("Hurghada")
    assert any("number 90" in x for x in validate_alert_text(GOOD + " Expect 90 mm.", p))
    assert any("other region" in x for x in validate_alert_text(GOOD + " Aswan is also affected.", p))
    assert any("unexpected level" in x for x in validate_alert_text(GOOD + " This is Severe Danger.", p))
    assert validate_alert_text("ok", p)


def test_llm_alert_used_when_valid(with_predictions):
    res = generate_alert("Hurghada", "en", llm=ScriptedLLM([AIMessage(content=GOOD)]))
    assert res["status"] == "ok" and res["source"] == "llm" and res["text"].endswith(DISCLAIMER["en"])
    assert res["should_alert"] and res["validation_problems"] == []


def test_invalid_llm_text_retries_then_falls_back_to_template(with_predictions):
    bad = AIMessage(content="Hurghada flood level Watch, expect 250 mm of rain and 40 casualties soon.")
    llm = ScriptedLLM([bad, bad])
    res = generate_alert("Hurghada", "en", llm=llm)
    assert res["source"] == "template" and llm.calls == 2 and "250" not in res["text"] and "casualties" not in res["text"]
    assert res["validation_problems"] and DISCLAIMER["en"] in res["text"]


def test_retry_can_recover(with_predictions):
    llm = ScriptedLLM([AIMessage(content="Hurghada Watch, 999 mm expected."), AIMessage(content=GOOD)])
    assert generate_alert("Hurghada", "en", llm=llm)["source"] == "llm"


def test_llm_exception_falls_back(with_predictions):
    class Boom:
        def invoke(self, m): raise RuntimeError("down")
    res = generate_alert("Hurghada", "ar", llm=Boom())
    assert res["source"] == "template" and "الغردقة" in res["text"] and DISCLAIMER["ar"] in res["text"]


def test_safe_region_uses_template_without_llm_call(sql):
    llm = ScriptedLLM([])
    res = generate_alert("Aswan", "ar", llm=llm)
    assert res["should_alert"] is False and llm.calls == 0 and "أسوان" in res["text"]


def test_alert_for_missing_data(sql):
    res = generate_alert("Cairo", "en", llm=ScriptedLLM([]))
    assert res["status"] == "error" and DISCLAIMER["en"] in res["text"]


def test_template_arabic_and_english_only_use_payload_numbers(with_predictions):
    from genai.chatbot_chain import extract_numbers
    from genai.data_to_text import allowed_numbers
    p = build_alert_payload("Hurghada")
    for lang in ("ar", "en"):
        text = render_template_alert(p, lang)
        allowed = allowed_numbers(p) + [100.0]          # "out of 100" scale
        assert all(any(abs(n - a) < 0.051 for a in allowed) for n in extract_numbers(text))
