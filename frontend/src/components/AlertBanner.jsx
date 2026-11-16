import { useEffect, useState } from "react";

const API_BASE = "http://127.0.0.1:8001";

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
    advisory: "هذه معلومات استرشادية وليست تحذيرًا رسميًا.",
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
    advisory: "This is advisory information, not an official warning.",
  },
};

const riskNames = {
  Safe: "safe",
  Watch: "watch",
  Danger: "danger",
  "Severe Danger": "severe",
  "آمن": "safe",
  "مراقبة": "watch",
  "خطر": "danger",
  "خطر شديد": "severe",
};

const cityNames = {
  Hurghada: { ar: "الغردقة", en: "Hurghada" },
  Aswan: { ar: "أسوان", en: "Aswan" },
  Sohag: { ar: "سوهاج", en: "Sohag" },
  Safaga: { ar: "سفاجا", en: "Safaga" },
};

function formatPeakTime(value, language) {
  if (!value) return "";

  // أوقات الـ API بصيغة UTC؛ نضيف Z إذا لم تكن موجودة.
  const utcValue = value.endsWith("Z") ? value : `${value}Z`;
  const date = new Date(utcValue);

  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat(language, {
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export default function AlertBanner({ city, lang }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  const text = messages[lang] ?? messages.ar;
  const displayCity =
    cityNames[city]?.[lang] ?? cityNames[city]?.en ?? city;

  useEffect(() => {
    const controller = new AbortController();

    async function loadAlert() {
      setLoading(true);
      setFailed(false);
      setData(null);

      try {
        const url =
          `${API_BASE}/chatbot/alert/${encodeURIComponent(city)}` +
          `?lang=en`;

        const response = await fetch(url, { signal: controller.signal });
        const result = await response.json();

        if (!response.ok) {
          throw new Error("Alert request failed");
        }

        setData(result);
      } catch (error) {
        if (error.name !== "AbortError") {
          setFailed(true);
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    loadAlert();

    return () => controller.abort();
  }, [city]);

  if (loading) {
    return <section className="card">{text.loading}</section>;
  }

  if (failed) {
    return (
      <section className="card" role="alert">
        {text.error}
      </section>
    );
  }

  // لو البيانات غير متاحة، نعرض النص فقط بدون شارة أو بانر خطر.
  if (data?.status !== "ok") {
    return (
      <section className="card">
        <p>
        {lang === "ar"
            ? "لا تتوفر بيانات كافية لهذه المدينة حاليًا."
            : data?.text ?? text.error}
        </p>     
      </section>
    );
  }

  const riskKey = riskNames[data.risk_level];
  const riskLabel = riskKey ? text[riskKey] : data.risk_level;
  const alertClass = data.should_alert ? "alert-card has-alert" : "alert-card";

  return (
    <div className="dashboard-grid">
      <section
        className={`card ${alertClass}`}
        role={data.should_alert ? "alert" : "status"}
        dir={lang === "ar" ? "rtl" : "ltr"}
      >
        <div>
          <p className="eyebrow">{text.alerts}</p>
          <h2>{displayCity}</h2>
          <p>
          {lang === "ar"
              ? `مستوى الخطورة الحالي: ${riskLabel} (${data.risk_score ?? "—"} من 100).`
              : data.text}
          </p>          {data.stale && <p className="stale-note">{text.stale}</p>}
          <p className="disclaimer-note">{text.advisory}</p>
        </div>
      </section>

      <section className="card risk-card" dir={lang === "ar" ? "rtl" : "ltr"}>
        <p className="eyebrow">{text.risk}</p>
        <span className={`risk-pill risk-${riskKey ?? "unknown"}`}>
          {riskLabel}
        </span>
        <div className="risk-score">
          {data.risk_score ?? "—"} <small>/ 100</small>
        </div>
      </section>

      <section className="card forecast-card" dir={lang === "ar" ? "rtl" : "ltr"}>
        <p className="eyebrow">{text.forecast}</p>
        {data.peak ? (
          <>
            <h2>{formatPeakTime(data.peak.time, lang)}</h2>
            <p>
              {riskNames[data.peak.risk_level]
                ? text[riskNames[data.peak.risk_level]]
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