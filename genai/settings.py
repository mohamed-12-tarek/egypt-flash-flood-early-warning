"""Shared constants and environment-driven settings for the GenAI layer."""

import os
import re
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

CITIES = [
    "St_Catherine", "Dahab", "Nuweiba", "Taba", "Sharm_El_Sheikh", "Ras_Gharib",
    "Hurghada", "Safaga", "Quseir", "Marsa_Alam", "Ain_Sokhna", "Suez",
    "Aswan", "Luxor", "Sohag",
]

CITY_AR = {
    "St_Catherine": "سانت كاترين", "Dahab": "دهب", "Nuweiba": "نويبع",
    "Taba": "طابا", "Sharm_El_Sheikh": "شرم الشيخ", "Ras_Gharib": "رأس غارب",
    "Hurghada": "الغردقة", "Safaga": "سفاجا", "Quseir": "القصير",
    "Marsa_Alam": "مرسى علم", "Ain_Sokhna": "العين السخنة", "Suez": "السويس",
    "Aswan": "أسوان", "Luxor": "الأقصر", "Sohag": "سوهاج",
}

CITY_ALIASES = {
    "St_Catherine": ["saint catherine", "st catherine", "katreen", "سانت كاترين", "سانت كاترين", "كاترين"],
    "Dahab": ["dahab", "دهب"],
    "Nuweiba": ["nuweiba", "nuwaiba", "نويبع"],
    "Taba": ["taba", "طابا"],
    "Sharm_El_Sheikh": ["sharm el sheikh", "sharm", "شرم الشيخ", "شرم"],
    "Ras_Gharib": ["ras gharib", "ras ghareb", "رأس غارب", "راس غارب"],
    "Hurghada": ["hurghada", "الغردقة", "الغردقه"],
    "Safaga": ["safaga", "safaja", "سفاجا"],
    "Quseir": ["quseir", "al quseir", "القصير"],
    "Marsa_Alam": ["marsa alam", "مرسى علم", "مرسي علم"],
    "Ain_Sokhna": ["ain sokhna", "sokhna", "العين السخنة", "السخنة", "العين السخنه"],
    "Suez": ["suez", "السويس"],
    "Aswan": ["aswan", "أسوان", "اسوان"],
    "Luxor": ["luxor", "الأقصر", "الاقصر"],
    "Sohag": ["sohag", "سوهاج"],
}

LEVELS = ["Safe", "Watch", "Danger", "Severe Danger"]
LEVEL_RANK = {name: i for i, name in enumerate(LEVELS)}
LEVEL_AR = {"Safe": "آمن", "Watch": "مراقبة", "Danger": "خطر", "Severe Danger": "خطر شديد"}

MAX_QUESTION_CHARS = int(os.getenv("GENAI_MAX_QUESTION_CHARS", "1000"))
MAX_AGENT_STEPS = int(os.getenv("GENAI_MAX_AGENT_STEPS", "6"))
STALE_AFTER_HOURS = float(os.getenv("GENAI_STALE_AFTER_HOURS", "3"))
RAG_MAX_DISTANCE = float(os.getenv("RAG_MAX_DISTANCE", "0.75"))  # cosine distance; tune on real docs
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "4"))

RATE_LIMIT_RETRIES = int(os.getenv("GENAI_RATE_LIMIT_RETRIES", "4"))
RATE_LIMIT_MAX_WAIT = float(os.getenv("GENAI_RATE_LIMIT_MAX_WAIT", "30"))   # seconds, per wait

CHROMA_DIR = os.getenv("CHROMA_DIR", os.path.join(os.path.dirname(__file__), ".chroma"))
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "flood_knowledge")
KNOWLEDGE_DIR = os.getenv("KNOWLEDGE_DIR", os.path.join(os.path.dirname(__file__), "knowledge"))
EVAL_RESULTS_DIR = os.getenv("EVAL_RESULTS_DIR", os.path.join(os.path.dirname(__file__), "eval_results"))

DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"


def groq_model_name() -> str:
    return os.getenv("GROQ_MODEL_NAME") or DEFAULT_GROQ_MODEL


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


_ARABIC = re.compile(r"[؀-ۿ]")


def detect_language(text: str) -> str:
    """'ar' if the text contains Arabic letters, otherwise 'en'."""
    return "ar" if _ARABIC.search(text or "") else "en"


DISCLAIMER = {
    "ar": "⚠️ هذا ليس تحذيرًا رسميًا. المعلومات استرشادية وتعتمد على نموذج تحليلي وبيانات طقس؛ "
          "للتحذيرات الرسمية ارجع للجهات المختصة (هيئة الأرصاد الجوية والحماية المدنية).",
    "en": "⚠️ This is not an official warning. The information is advisory, based on an analytical "
          "model and weather data; for official warnings refer to the competent authorities "
          "(the national meteorological authority and civil protection).",
}
