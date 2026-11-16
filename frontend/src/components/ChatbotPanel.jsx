import { useEffect, useRef, useState } from "react";

const API_BASE = "http://127.0.0.1:8001";

const labels = {
  ar: {
    title: "مساعد السيول",
    available: "متاح الآن",
    placeholder: "اكتب سؤالك...",
    send: "إرسال",
    typing: "المساعد يكتب",
    stale: "البيانات قد تكون قديمة.",
    retry: "حاول تاني",
    timeout: "الطلب اتأخر. حاول مرة أخرى.",
    error: "تعذّر إرسال السؤال. حاول مرة أخرى.",
    notConfigured: "خدمة المساعد غير مجهزة حاليًا.",
    advisory: "هذه إجابة استرشادية وليست تحذيرًا رسميًا.",
    you: "أنت",
    assistant: "المساعد",
  },
  en: {
    title: "Flood Assistant",
    available: "Available now",
    placeholder: "Type your question...",
    send: "Send",
    typing: "Assistant is typing",
    stale: "Data may be stale.",
    retry: "Try again",
    timeout: "The request took too long. Please try again.",
    error: "Could not send the question. Please try again.",
    notConfigured: "The assistant service is not configured.",
    advisory: "This is advisory information, not an official warning.",
    you: "You",
    assistant: "Assistant",
  },
};

// Direction follows the message's own text (first strong letter), not the UI
// language, so an English question asked while the UI is Arabic still reads LTR.
function textDirection(value, fallback) {
  const firstLetter = (value ?? "").match(/[A-Za-z؀-ۿ]/);
  if (!firstLetter) return fallback;
  return /[؀-ۿ]/.test(firstLetter[0]) ? "rtl" : "ltr";
}

/* ---------- minimal, safe Markdown renderer for assistant replies ----------
   Builds React elements only (no innerHTML), so reply text can never inject
   markup. Supports: **bold**, *italic*, `code`, [text](http/https link),
   # headings, - / * / • bullet lists, 1. numbered lists, > quotes, ---,
   and ``` code fences. Anything else (tables, images) shows as plain text. */

const INLINE_PATTERN =
  /\*\*(.+?)\*\*|`([^`\n]+)`|\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)|\*([^\s*](?:[^*\n]*[^\s*])?)\*/g;
const HR_PATTERN = /^\s*([-*_])(\s*\1){2,}\s*$/;
const BULLET_PATTERN = /^\s*[-*•]\s+(.*)$/;
const ORDERED_PATTERN = /^\s*\d+[.)]\s+(.*)$/;
const QUOTE_PATTERN = /^\s*>\s?(.*)$/;
const HEADING_PATTERN = /^\s*(#{1,6})\s+(.*)$/;
const FENCE_PATTERN = /^\s*```/;

function renderInline(source, keyPrefix) {
  const nodes = [];
  const pattern = new RegExp(INLINE_PATTERN.source, "g");
  let last = 0;
  let count = 0;
  let match = pattern.exec(source);

  while (match !== null) {
    if (match.index > last) nodes.push(source.slice(last, match.index));
    const key = `${keyPrefix}-${count++}`;

    if (match[1] !== undefined) {
      nodes.push(<strong key={key}>{renderInline(match[1], key)}</strong>);
    } else if (match[2] !== undefined) {
      nodes.push(<code key={key}>{match[2]}</code>);
    } else if (match[3] !== undefined) {
      nodes.push(
        <a key={key} href={match[4]} target="_blank" rel="noopener noreferrer">
          {match[3]}
        </a>
      );
    } else {
      nodes.push(<em key={key}>{renderInline(match[5], key)}</em>);
    }

    last = pattern.lastIndex;
    match = pattern.exec(source);
  }

  if (last < source.length) nodes.push(source.slice(last));
  return nodes;
}

function isSpecialLine(line) {
  return (
    FENCE_PATTERN.test(line) ||
    HEADING_PATTERN.test(line) ||
    HR_PATTERN.test(line) ||
    BULLET_PATTERN.test(line) ||
    ORDERED_PATTERN.test(line) ||
    QUOTE_PATTERN.test(line)
  );
}

function renderMarkdown(source) {
  const lines = String(source ?? "").replace(/\r\n?/g, "\n").split("\n");
  const blocks = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    if (line.trim() === "") {
      i += 1;
      continue;
    }

    const key = `b${blocks.length}`;

    if (FENCE_PATTERN.test(line)) {
      const code = [];
      i += 1;
      while (i < lines.length && !FENCE_PATTERN.test(lines[i])) {
        code.push(lines[i]);
        i += 1;
      }
      i += 1; // closing fence
      blocks.push(
        <pre key={key} dir="ltr">
          <code>{code.join("\n")}</code>
        </pre>
      );
      continue;
    }

    const heading = line.match(HEADING_PATTERN);
    if (heading) {
      blocks.push(
        <div
          key={key}
          role="heading"
          aria-level={Math.min(heading[1].length + 2, 6)}
          className="md-heading"
        >
          {renderInline(heading[2].trim(), key)}
        </div>
      );
      i += 1;
      continue;
    }

    if (HR_PATTERN.test(line)) {
      blocks.push(<hr key={key} />);
      i += 1;
      continue;
    }

    const isOrdered = ORDERED_PATTERN.test(line);
    if (isOrdered || BULLET_PATTERN.test(line)) {
      const pattern = isOrdered ? ORDERED_PATTERN : BULLET_PATTERN;
      const items = [];
      while (i < lines.length && pattern.test(lines[i])) {
        items.push(lines[i].match(pattern)[1]);
        i += 1;
      }
      const List = isOrdered ? "ol" : "ul";
      blocks.push(
        <List key={key}>
          {items.map((item, index) => (
            <li key={index}>{renderInline(item, `${key}-${index}`)}</li>
          ))}
        </List>
      );
      continue;
    }

    if (QUOTE_PATTERN.test(line)) {
      const quoted = [];
      while (i < lines.length && QUOTE_PATTERN.test(lines[i])) {
        quoted.push(lines[i].match(QUOTE_PATTERN)[1]);
        i += 1;
      }
      blocks.push(<blockquote key={key}>{renderInline(quoted.join(" "), key)}</blockquote>);
      continue;
    }

    // Paragraph: consecutive plain lines, kept as line breaks.
    const paragraph = [];
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      (paragraph.length === 0 || !isSpecialLine(lines[i]))
    ) {
      paragraph.push(lines[i]);
      i += 1;
    }
    blocks.push(
      <p key={key}>
        {paragraph.flatMap((text, index) =>
          index === 0
            ? renderInline(text, `${key}-0`)
            : [<br key={`${key}-br${index}`} />, ...renderInline(text, `${key}-${index}`)]
        )}
      </p>
    );
  }

  return blocks;
}

export default function ChatbotPanel({ lang }) {
  const text = labels[lang] ?? labels.ar;
  const uiDir = lang === "ar" ? "rtl" : "ltr";

  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [stale, setStale] = useState(false);
  const [fallback, setFallback] = useState(false);
  const [retryRequest, setRetryRequest] = useState(null);

  const scrollRef = useRef(null);

  // Always show the newest message / loading / error state.
  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;
    container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
  }, [messages, loading, error, fallback]);

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

      // An error response may not be JSON; don't let that hide the status code.
      let result = null;
      try {
        result = await response.json();
      } catch {
        result = null;
      }

      if (!response.ok || !result) {
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

  const showRetry = (Boolean(error) || fallback) && !loading && retryRequest;

  return (
    <section className="card chat-card" dir={uiDir}>
      <header className="chat-header">
        <div>
          <h2>{text.title}</h2>
          <span className="chat-availability">{text.available}</span>
        </div>
        {stale && <span className="stale-note">{text.stale}</span>}
      </header>

      {/* The message list is always LTR so the user is on the right and the
          assistant on the left in both languages; each bubble sets its own
          text direction. */}
      <div className="chat-messages" ref={scrollRef} aria-live="polite">
        {messages.length === 0 && !loading && (
          <p className="chat-empty" dir={uiDir}>
            {text.advisory}
          </p>
        )}

        {messages.map((item, index) => (
          <div
            className={`message-row ${item.role}`}
            key={`${item.role}-${index}`}
          >
            <div className="message-stack">
              <span className="message-author" dir={uiDir}>
                {item.role === "user" ? text.you : text.assistant}
              </span>
              {item.role === "assistant" ? (
                <div
                  className="message-bubble markdown"
                  dir={textDirection(item.content, item.language === "ar" ? "rtl" : "ltr")}
                >
                  {renderMarkdown(item.content)}
                </div>
              ) : (
                <p
                  className="message-bubble"
                  dir={textDirection(item.content, item.language === "ar" ? "rtl" : "ltr")}
                >
                  {item.content}
                </p>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="message-row assistant">
            <div className="message-stack">
              <p className="message-bubble typing-bubble" role="status" aria-label={text.typing}>
                <span className="typing-dot" />
                <span className="typing-dot" />
                <span className="typing-dot" />
              </p>
            </div>
          </div>
        )}

        {error && (
          <div className="message-row assistant">
            <div className="message-stack">
              <p className="message-bubble error-bubble" role="alert" dir={uiDir}>
                {error}
              </p>
            </div>
          </div>
        )}

        {showRetry && (
          <div className="message-row assistant">
            <button className="retry-button" type="button" onClick={handleRetry}>
              {text.retry}
            </button>
          </div>
        )}
      </div>

      <form className="chat-form" onSubmit={handleSubmit}>
        <input
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder={text.placeholder}
          maxLength={1000}
          disabled={loading}
          dir="auto"
        />
        <button type="submit" disabled={loading || !question.trim()}>
          {text.send}
        </button>
      </form>
    </section>
  );
}