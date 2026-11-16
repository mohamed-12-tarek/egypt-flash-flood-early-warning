import { useEffect, useState } from "react";

const API_BASE = "http://127.0.0.1:8001";

// The alert endpoint is always requested with lang=en. The UI language only
// changes how the structured fields are labelled below; it must never decide
// whether the data is fetched (the Arabic text generation on the backend is
// not needed to show score / level / rainfall / time).
const REQUEST_LANG = "en";

const LOCALES = { ar: "ar-u-nu-latn", en: "en" };

const messages = {
  ar: {
    alerts: "التنبيهات",
    risk: "مستوى الخطورة",
    forecast: "التوقع القريب",
    loading: "جاري تحميل التنبيه...",
    stale: "البيانات قديمة",
    noPeak: "لا يوجد توقع قريب متاح.",
    safe: "آمن",
    watch: "مراقبة",
    danger: "خطر",
    severe: "خطر شديد",
    error: "تعذّر تحميل التنبيه. حاول مرة أخرى.",
    noData: "لا توجد بيانات حالية متاحة لهذه المنطقة.",
    advisory: "هذه معلومات استرشادية وليست تحذيرًا رسميًا.",
    currentRisk: "مستوى الخطورة الحالي",
    outOf: "من 100",
    rainfall: "الأمطار",
    mm: "ملم",
    updated: "آخر تحديث",
    retry: "إعادة المحاولة",
    serverError: "رد الخادم برمز",
    networkError: "تعذّر الوصول إلى الخدمة على المنفذ 8001.",
  },
  en: {
    alerts: "Alerts",
    risk: "Risk level",
    forecast: "Near-term forecast",
    loading: "Loading alert...",
    stale: "Data may be stale",
    noPeak: "No near-term forecast is available.",
    safe: "Safe",
    watch: "Watch",
    danger: "Danger",
    severe: "Severe Danger",
    error: "Could not load the alert. Please try again.",
    noData: "No current data available for this region.",
    advisory: "This is advisory information, not an official warning.",
    currentRisk: "Current risk level",
    outOf: "out of 100",
    rainfall: "Rainfall",
    mm: "mm",
    updated: "Last updated",
    retry: "Try again",
    serverError: "Server responded with status",
    networkError: "Could not reach the service on port 8001.",
  },
};

const riskNames = {
  safe: "safe",
  watch: "watch",
  danger: "danger",
  "severe danger": "severe",
  severe: "severe",
  "آمن": "safe",
  "مراقبة": "watch",
  "خطر": "danger",
  "خطر شديد": "severe",
};

// Candidate field names; only fields that actually exist in the response are used.
const SCORE_KEYS = ["risk_score", "score"];
const RAIN_KEYS = [
  "rainfall_mm",
  "rainfall",
  "rain_mm",
  "rain",
  "precipitation_mm",
  "precipitation",
  "precip_mm",
];
const TIME_KEYS = [
  "timestamp",
  "time",
  "datetime",
  "observed_at",
  "updated_at",
  "generated_at",
  "as_of",
];
const NESTED_KEYS = ["current", "latest", "metrics", "weather", "data"];

function toNumber(value) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function pick(source, keys) {
  if (!source || typeof source !== "object" || Array.isArray(source)) {
    return undefined;
  }
  for (const key of keys) {
    if (source[key] !== undefined && source[key] !== null) return source[key];
  }
  for (const nestedKey of NESTED_KEYS) {
    const nested = source[nestedKey];
    if (nested && typeof nested === "object" && !Array.isArray(nested)) {
      for (const key of keys) {
        if (nested[key] !== undefined && nested[key] !== null) return nested[key];
      }
    }
  }
  return undefined;
}

function parseTime(value) {
  if (value === null || value === undefined || value === "") return null;
  let date;
  if (typeof value === "number") {
    date = new Date(value < 1e12 ? value * 1000 : value);
  } else if (typeof value === "string") {
    let raw = value.trim();
    // API times are UTC; add Z when the string carries no offset.
    if (/^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(raw)) {
      raw = `${raw.replace(" ", "T")}Z`;
    }
    date = new Date(raw);
  } else {
    return null;
  }
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatTime(value, language, withDate = false) {
  const date = parseTime(value);
  if (!date) return typeof value === "string" ? value : "";
  const options = withDate
    ? { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }
    : { hour: "2-digit", minute: "2-digit" };
  return new Intl.DateTimeFormat(LOCALES[language] ?? language, options).format(date);
}

function formatNumber(value, language) {
  return new Intl.NumberFormat(LOCALES[language] ?? language, {
    maximumFractionDigits: 2,
  }).format(value);
}

function riskKeyOf(level) {
  if (typeof level !== "string") return null;
  return riskNames[level.trim().toLowerCase()] ?? null;
}

async function requestAlert(city, signal) {
  const response = await fetch(
    `${API_BASE}/chatbot/alert/${encodeURIComponent(city)}?lang=${REQUEST_LANG}`,
    { signal }
  );

  let body = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (!response.ok) {
    const error = new Error("Alert request failed");
    error.status = response.status;
    throw error;
  }

  return body;
}

export default function AlertBanner({ city, lang, regions = [] }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [failure, setFailure] = useState(null);
  const [attempt, setAttempt] = useState(0);

  const text = messages[lang] ?? messages.ar;
  const dir = lang === "ar" ? "rtl" : "ltr";
  const displayCity =
    regions.find((region) => region.id === city)?.[lang] ?? city;

  // Depends on city only: switching language never refetches or drops data.
  useEffect(() => {
    const controller = new AbortController();

    async function loadAlert() {
      setLoading(true);
      setFailure(null);
      setData(null);

      try {
        setData(await requestAlert(city, controller.signal));
      } catch (error) {
        if (error.name === "AbortError") {
          // Request was cancelled by a newer city selection; nothing to show.
        } else if (error.status === 404) {
          // The region is monitored but the API has no current record for it:
          // show the localized "no current data" state, not a failure.
          setData({});
        } else {
          setFailure({ status: error.status ?? null });
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    loadAlert();

    return () => controller.abort();
  }, [city, attempt]);

  if (loading) {
    return (
      <section className="card" dir={dir}>
        {text.loading}
      </section>
    );
  }

  if (failure) {
    return (
      <section className="card" role="alert" dir={dir}>
        <p className="error-text">{text.error}</p>
        <p className="error-detail">
          {failure.status
            ? `${text.serverError} ${failure.status}`
            : text.networkError}
        </p>
        <button
          className="toolbar-button"
          type="button"
          onClick={() => setAttempt((current) => current + 1)}
        >
          {text.retry}
        </button>
      </section>
    );
  }

  const score = toNumber(pick(data, SCORE_KEYS));
  const level = typeof data?.risk_level === "string" ? data.risk_level : null;
  const hasStructuredData = score !== null || level !== null;

  // Decide on the data that is actually present, not only on the `status`
  // string, so valid fields are never hidden behind a generic message.
  if (!hasStructuredData) {
    return (
      <section className="card" dir={dir}>
        <p>
          {lang === "en" && typeof data?.text === "string" && data.text
            ? data.text
            : text.noData}
        </p>
      </section>
    );
  }

  const riskKey = riskKeyOf(level);
  const riskLabel = riskKey ? text[riskKey] : level ?? "—";
  const rainfall = toNumber(pick(data, RAIN_KEYS));
  const updatedAt = pick(data, TIME_KEYS);
  const updatedLabel = updatedAt ? formatTime(updatedAt, lang, true) : "";
  const scoreLabel = score !== null ? formatNumber(score, lang) : "—";
  const alertClass = data.should_alert ? "alert-card has-alert" : "alert-card";

  const summary =
    lang === "en" && typeof data.text === "string" && data.text
      ? data.text
      : `${text.currentRisk}: ${riskLabel}${
          score !== null ? ` (${scoreLabel} ${text.outOf})` : ""
        }.`;

  return (
    <div className="dashboard-grid">
      <section
        className={`card ${alertClass}`}
        role={data.should_alert ? "alert" : "status"}
        dir={dir}
      >
        <div>
          <p className="eyebrow">{text.alerts}</p>
          <h2>{displayCity}</h2>
          <p>{summary}</p>
          {(rainfall !== null || updatedLabel) && (
            <ul className="alert-facts">
              {rainfall !== null && (
                <li>
                  <span>{text.rainfall}</span>
                  <strong>
                    {formatNumber(rainfall, lang)} {text.mm}
                  </strong>
                </li>
              )}
              {updatedLabel && (
                <li>
                  <span>{text.updated}</span>
                  <strong>{updatedLabel}</strong>
                </li>
              )}
            </ul>
          )}
          {data.stale && <p className="stale-note">{text.stale}</p>}
          <p className="disclaimer-note">{text.advisory}</p>
        </div>
      </section>

      <section className="card risk-card" dir={dir}>
        <p className="eyebrow">{text.risk}</p>
        <span className={`risk-pill risk-${riskKey ?? "unknown"}`}>
          {riskLabel}
        </span>
        <div className="risk-score">
          {scoreLabel} <small>/ 100</small>
        </div>
      </section>

      <section className="card forecast-card" dir={dir}>
        <p className="eyebrow">{text.forecast}</p>
        {data.peak ? (
          <>
            <h2>{formatTime(data.peak.time, lang)}</h2>
            <p>
              {riskKeyOf(data.peak.risk_level)
                ? text[riskKeyOf(data.peak.risk_level)]
                : data.peak.risk_level}
              {" · "}
              {data.peak.risk_score} / 100
            </p>
          </>
        ) : (
          <p>{text.noPeak}</p>
        )}
      </section>
    </div>
  );
}