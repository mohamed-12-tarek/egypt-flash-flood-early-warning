import { useState } from "react";
import AlertBanner from "./components/AlertBanner.jsx";
import ChatbotPanel from "./components/ChatbotPanel.jsx";
import AnalysisPanel from "./components/AnalysisPanel.jsx";
import "./App.css";

const labels = {
  ar: {
    brand: "درع السيول",
    subtitle: "الإنذار المبكر",
    dashboard: "الرئيسية والتنبيهات",
    assistant: "مساعد السيول",
    systemReady: "النظام يعمل",
    titleDashboard: "الإنذار المبكر للسيول",
    titleAssistant: "مساعد السيول",
    chooseCity: "المدينة",
    riskTitle: "مستوى الخطورة",
    alertTitle: "التنبيهات",
    forecastTitle: "التوقع القريب",
    riskWaiting: "سيظهر مستوى الخطورة هنا بعد الاتصال بالخدمة.",
    alertWaiting: "سيظهر التنبيه هنا بعد اختيار المدينة.",
    forecastWaiting: "ستظهر معلومات التوقع إذا وفرها الـ API.",
    chatWaiting: "اكتب سؤالك عن مخاطر السيول.",
    inputPlaceholder: "اكتب سؤالك...",
    send: "إرسال",
    darkMode: "الوضع الداكن",
    lightMode: "الوضع الفاتح",
    english: "English",
    arabic: "العربية",
    advisory: "هذه معلومات استرشادية وليست تحذيرًا رسميًا.",
  },
  en: {
    brand: "Flood Shield",
    subtitle: "Early Warning",
    dashboard: "Home & Alerts",
    assistant: "Flood Assistant",
    systemReady: "System online",
    titleDashboard: "Flash Flood Early Warning",
    titleAssistant: "Flood Assistant",
    chooseCity: "City",
    riskTitle: "Risk level",
    alertTitle: "Alerts",
    forecastTitle: "Near-term forecast",
    riskWaiting: "The risk level will appear here when connected to the service.",
    alertWaiting: "The alert will appear here after choosing a city.",
    forecastWaiting: "Forecast details will appear if provided by the API.",
    chatWaiting: "Ask a question about flood risk.",
    inputPlaceholder: "Type your question...",
    send: "Send",
    darkMode: "Dark mode",
    lightMode: "Light mode",
    english: "English",
    arabic: "العربية",
    advisory: "This is advisory information, not an official warning.",
  },
};

// Canonical list of the 15 monitored regions. `id` is the exact value sent to
// the API. The dropdown and the status grid are built from THIS list, never from
// API responses, so a region stays selectable even when it has no current data.
// `aliases` only help match API records whose name is spelled differently.
const REGIONS = [
  { id: "St_Catherine", ar: "سانت كاترين", en: "St. Catherine", aliases: ["Saint Catherine", "Saint_Catherine"] },
  { id: "Dahab", ar: "دهب", en: "Dahab" },
  { id: "Nuweiba", ar: "نويبع", en: "Nuweiba" },
  { id: "Taba", ar: "طابا", en: "Taba" },
  { id: "Sharm_El_Sheikh", ar: "شرم الشيخ", en: "Sharm El-Sheikh", aliases: ["Sharm El Sheikh", "Sharm Elsheikh"] },
  { id: "Ras_Gharib", ar: "رأس غارب", en: "Ras Gharib" },
  { id: "Hurghada", ar: "الغردقة", en: "Hurghada" },
  { id: "Safaga", ar: "سفاجا", en: "Safaga" },
  { id: "Quseir", ar: "القصير", en: "Quseir", aliases: ["El Quseir", "Al Quseir"] },
  { id: "Marsa_Alam", ar: "مرسى علم", en: "Marsa Alam" },
  { id: "Ain_Sokhna", ar: "العين السخنة", en: "Ain Sokhna", aliases: ["Ain El Sokhna"] },
  { id: "Suez", ar: "السويس", en: "Suez" },
  { id: "Aswan", ar: "أسوان", en: "Aswan" },
  { id: "Luxor", ar: "الأقصر", en: "Luxor" },
  { id: "Sohag", ar: "سوهاج", en: "Sohag" },
];

export default function App() {
  const [language, setLanguage] = useState("ar");
  const [theme, setTheme] = useState("light");
  const [screen, setScreen] = useState("dashboard");
  const [city, setCity] = useState("Hurghada");

  const text = labels[language];
  const isArabic = language === "ar";

  return (
    <div
      className={`app theme-${theme}`}
      lang={language}
      dir={isArabic ? "rtl" : "ltr"}
    >
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-icon">☁</span>
          <div>
            <strong>{text.brand}</strong>
            <small>{text.subtitle}</small>
          </div>
        </div>

        <nav className="navigation">
          <button
            className={screen === "dashboard" ? "nav-item active" : "nav-item"}
            onClick={() => setScreen("dashboard")}
          >
            {text.dashboard}
          </button>
          <button
            className={screen === "assistant" ? "nav-item active" : "nav-item"}
            onClick={() => setScreen("assistant")}
          >
            {text.assistant}
          </button>
        </nav>

        <div className="system-status">
          <span className="status-dot" />
          {text.systemReady}
        </div>

        <p className="disclaimer">{text.advisory}</p>
      </aside>

      <div className="page">
        <header className="topbar">
          <div>
            <p className="eyebrow">{text.brand}</p>
            <h1>
              {screen === "dashboard"
                ? text.titleDashboard
                : text.titleAssistant}
            </h1>
          </div>

          <div className="toolbar">
            {screen === "dashboard" && (
              <label className="city-picker">
                <span>{text.chooseCity}</span>
                <select value={city} onChange={(event) => setCity(event.target.value)}>
                  {REGIONS.map((region) => (
                    <option key={region.id} value={region.id}>
                      {region[language]}
                    </option>
                  ))}
                </select>
              </label>
            )}

            <button
              className="toolbar-button"
              onClick={() =>
                setTheme((current) => (current === "light" ? "dark" : "light"))
              }
            >
              {theme === "light" ? text.darkMode : text.lightMode}
            </button>

            <button
              className="toolbar-button"
              onClick={() => setLanguage(isArabic ? "en" : "ar")}
            >
              {isArabic ? text.english : text.arabic}
            </button>
          </div>
        </header>

        {screen === "dashboard" ? (
          <main className="dashboard-view">
            <AlertBanner city={city} lang={language} regions={REGIONS} />
            <AnalysisPanel city={city} lang={language} regions={REGIONS} />
          </main>
        ) : (
          <ChatbotPanel lang={language} />
        )}
      </div>
    </div>
  );
}