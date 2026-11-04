"""LLM-written alerts. Facts come from SQL; the model only writes the wording.

Flow:  payload (SQL) -> LLM text -> validator -> (ok) LLM text | (fail) deterministic template.
The validator rejects any text that mentions a number, region or risk level that is not in
the payload. The disclaimer is appended by code.
"""

import json
import logging
import re

from genai.chatbot_chain import _text, build_llm, extract_numbers
from genai.data_to_text import (
    allowed_numbers, build_alert_payload, render_template_alert, with_disclaimer,
)
from genai.settings import CITY_AR, LEVEL_AR, LEVELS

from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger("alerts")

ALERT_SYSTEM = """You write short public flood advisories for one Egyptian region.
Write ONLY from the JSON facts you are given. Rules:
- Mention the region, the risk level, the peak time (UTC) and the main factors from the JSON.
- Use ONLY numbers and times that appear in the JSON. Never invent, round differently, convert time zones, or add other numbers.
- Do not mention regions, casualties, roads or events that are not in the JSON.
- If peak.source is "model_prediction" say it is a model prediction.
- Give one short safety sentence (stay away from wadi channels and low-lying areas; follow official sources). No promises of safety.
- 3-5 sentences, plain text, no markdown, no emojis. Do not write any disclaimer (it is added separately).
- Write in {language}."""


def validate_alert_text(text: str, payload: dict) -> list[str]:
    """Return a list of problems (empty = valid)."""
    problems = []
    if not text or len(text) < 20:
        return ["empty or too short"]
    allowed = allowed_numbers(payload)
    for n in extract_numbers(text, strip_list_markers=True):
        tol = 0.5 if float(n).is_integer() else 0.051
        if not any(abs(n - a) <= tol for a in allowed):
            problems.append(f"number {n:g} not in data")
    low = text.lower()
    if payload["city"].replace("_", " ").lower() not in low and payload["city_ar"] not in text:
        problems.append("region not mentioned")
    # no other region may appear
    for other, ar in CITY_AR.items():
        if other != payload["city"] and (other.replace("_", " ").lower() in low or ar in text):
            problems.append(f"mentions other region {other}")
    # the alert must carry the current level (English or Arabic name)
    lvl = payload["risk_level"]
    if lvl.lower() not in low and LEVEL_AR[lvl] not in text:
        problems.append("current risk level missing")
    # must not state an English level name that is neither the current nor the peak level.
    # Case-sensitive on the exact names, so ordinary words ("stay safe") are not flagged.
    # (Arabic level words like "خطر" appear in ordinary sentences, so they are not policed.)
    allowed_levels = {payload["risk_level"], payload["peak"]["risk_level"]}
    for match in re.finditer(r"\b(Severe Danger|Danger|Watch|Safe)\b", text):
        if match.group(1) not in allowed_levels:
            problems.append(f"unexpected level {match.group(1)}")
    return problems


def generate_alert(city: str, lang: str = "ar", llm=None) -> dict:
    lang = "ar" if lang == "ar" else "en"
    payload = build_alert_payload(city)
    if payload["status"] != "ok":
        msg = {"ar": "لا تتوفر بيانات كافية لإصدار تنبيه لهذه المنطقة.",
               "en": "There is not enough data to issue an alert for this region."}[lang]
        return {"status": payload["status"], "text": with_disclaimer(msg, lang), "language": lang,
                "source": "none", "reason": payload.get("reason"), "data_as_of": None}

    text, source, problems = None, "template", []
    if payload["should_alert"]:
        try:
            model = llm or build_llm()
            facts = json.dumps({k: payload[k] for k in
                                ("city", "city_ar", "risk_level", "risk_score", "observed_at", "peak", "main_factors")},
                               ensure_ascii=False)
            prompt = [SystemMessage(content=ALERT_SYSTEM.format(language="Arabic" if lang == "ar" else "English")),
                      HumanMessage(content=facts)]
            for _ in range(2):
                candidate = _text(model.invoke(prompt).content).strip()
                problems = validate_alert_text(candidate, payload)
                if not problems:
                    text, source = candidate, "llm"
                    break
                prompt.append(HumanMessage(content="Rejected: " + "; ".join(problems) +
                                           ". Rewrite using only the JSON facts."))
        except Exception:
            logger.exception("LLM alert generation failed; using template")
    if text is None:
        text = render_template_alert(payload, lang)

    stale_note = {"ar": "\nتنبيه: البيانات قد تكون قديمة.", "en": "\nNote: the data may be outdated."}[lang] if payload["stale"] else ""
    return {
        "status": "ok",
        "text": with_disclaimer(text + stale_note, lang),
        "language": lang,
        "source": source,               
        "should_alert": payload["should_alert"],
        "city": payload["city"],
        "risk_level": payload["risk_level"],
        "risk_score": payload["risk_score"],
        "peak": payload["peak"],
        "main_factors": payload["main_factors"],
        "data_as_of": payload["data_as_of"],
        "stale": payload["stale"],
        "validation_problems": problems if source == "template" and payload["should_alert"] else [],
    }
