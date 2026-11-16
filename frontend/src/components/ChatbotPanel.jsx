import { useState } from "react";

const API_BASE = "http://127.0.0.1:8001";

const labels = {
  ar: {
    title: "مساعد السيول",
    available: "متاح الآن",
    placeholder: "اكتب سؤالك...",
    send: "إرسال",
    typing: "جاري الكتابة...",
    stale: "البيانات قد تكون قديمة.",
    retry: "حاول تاني",
    timeout: "الطلب اتأخر. حاول مرة أخرى.",
    error: "تعذّر إرسال السؤال. حاول مرة أخرى.",
    notConfigured: "خدمة المساعد غير مجهزة حاليًا.",
    advisory: "هذه إجابة استرشادية وليست تحذيرًا رسميًا.",
  },
  en: {
    title: "Flood Assistant",
    available: "Available now",
    placeholder: "Type your question...",
    send: "Send",
    typing: "Typing...",
    stale: "Data may be stale.",
    retry: "Try again",
    timeout: "The request took too long. Please try again.",
    error: "Could not send the question. Please try again.",
    notConfigured: "The assistant service is not configured.",
    advisory: "This is advisory information, not an official warning.",
  },
};

export default function ChatbotPanel({ lang }) {
  const text = labels[lang] ?? labels.ar;

  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [stale, setStale] = useState(false);
  const [fallback, setFallback] = useState(false);
  const [retryRequest, setRetryRequest] = useState(null);

  async function requestAnswer(message, history) {
    setLoading(true);
    setError("");
    setFallback(false);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 60000);

    try {
      const response = await fetch(`${API_BASE}/chatbot/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: message, history }),
        signal: controller.signal,
      });

      const result = await response.json();

      if (!response.ok) {
        setError(response.status === 503 ? text.notConfigured : text.error);
        return;
      }

      const answer = result.answer ?? result.body ?? "";

      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: answer,
          historyContent: result.body ?? answer,
          language: result.language ?? lang,
        },
      ]);

      setStale(Boolean(result.stale));
      setFallback(result.status === "fallback");
    } catch (requestError) {
      setError(
        requestError.name === "AbortError" ? text.timeout : text.error
      );
    } finally {
      clearTimeout(timeoutId);
      setLoading(false);
    }
  }

  function handleSubmit(event) {
    event.preventDefault();

    const message = question.trim();
    if (!message || loading) return;

    const history = messages.slice(-12).map((item) => ({
      role: item.role,
      content: item.historyContent ?? item.content,
    }));

    setMessages((current) => [
      ...current,
      {
        role: "user",
        content: message,
        historyContent: message,
        language: lang,
      },
    ]);

    setRetryRequest({ message, history });
    setQuestion("");
    requestAnswer(message, history);
  }

  function handleRetry() {
    if (retryRequest && !loading) {
      requestAnswer(retryRequest.message, retryRequest.history);
    }
  }

  return (
    <section className="card chat-card" dir={lang === "ar" ? "rtl" : "ltr"}>
      <header className="chat-header">
        <div>
          <h2>{text.title}</h2>
          <span className="chat-availability">{text.available}</span>
        </div>
        {stale && <span className="stale-note">{text.stale}</span>}
      </header>

      <div className="chat-messages" aria-live="polite">
        {messages.map((item, index) => (
          <div
            className={`message-row ${item.role}`}
            key={`${item.role}-${index}`}
          >
            <p
              className="message-bubble"
              dir={item.language === "ar" ? "rtl" : "ltr"}
            >
              {item.content}
            </p>
          </div>
        ))}

        {loading && <p className="chat-status">{text.typing}</p>}
        {error && <p className="chat-error">{error}</p>}

        {fallback && !loading && (
          <button className="retry-button" onClick={handleRetry}>
            {text.retry}
          </button>
        )}

        {messages.length === 0 && !loading && (
          <p className="chat-empty">{text.advisory}</p>
        )}
      </div>

      <form className="chat-form" onSubmit={handleSubmit}>
        <input
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder={text.placeholder}
          maxLength={1000}
          disabled={loading}
        />
        <button type="submit" disabled={loading || !question.trim()}>
          {text.send}
        </button>
      </form>
    </section>
  );
}