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
                  <option value="Hurghada">الغردقة / Hurghada</option>
                  <option value="Aswan">أسوان / Aswan</option>
                  <option value="Sohag">سوهاج / Sohag</option>
                  <option value="Safaga">سفاجا / Safaga</option>
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
    <AlertBanner city={city} lang={language} />
    <AnalysisPanel lang={language} />
  </main>
) : (
  <ChatbotPanel lang={language} />
)}      </div>
    </div>
  );
}