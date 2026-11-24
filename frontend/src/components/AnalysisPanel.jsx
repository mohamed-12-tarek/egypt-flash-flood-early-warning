import { useEffect, useMemo, useRef, useState } from "react";

// Empty by default: requests go to /analysis/... on the Vite origin and the dev
// proxy (vite.config.js) forwards them to http://127.0.0.1:8000, which avoids
// CORS. Set VITE_ANALYSIS_API_BASE=http://127.0.0.1:8000 only if the backend
// itself allows the frontend origin.
const API_BASE = import.meta.env.VITE_ANALYSIS_API_BASE ?? "";

const CACHE_TTL_MS = 60_000;
const LOCALES = { ar: "ar-u-nu-latn", en: "en" };

const labels = {
  ar: {
    eyebrow: "قسم التحليلات",
    refresh: "تحديث البيانات",
    statusTitle: "تفاصيل المدينة المحددة",
    kpiTitle: "مؤشرات الأداء",
    historyTitle: "آخر 24 ساعة",
    loading: "جاري التحميل...",
    empty: "لا توجد بيانات متاحة.",
    retryHint: "تحقق من تشغيل الـ backend على المنفذ 8000 ثم اضغط تحديث.",
    serverError: "رد الخادم برمز",
    networkError: "تعذّر الاتصال بخدمة التحليل.",
    risk: "مستوى الخطورة",
    score: "درجة الخطورة",
    rainfall: "متوسط الأمطار",
    rain24: "أمطار 24 ساعة",
    rain72: "أمطار 72 ساعة",
    updated: "آخر تحديث",
    mm: "ملم",
    yes: "نعم",
    no: "لا",
    safe: "آمن",
    watch: "مراقبة",
    danger: "خطر",
    severe: "خطر شديد",
    metricLabel: "المقياس",
    chartAria: "رسم بياني لآخر 24 ساعة",
    selectedCity: "المدينة المحددة",
    noMetric: "لا توجد قيم رقمية في بيانات السجل.",
    noData: "لا توجد بيانات حالية متاحة.",
    noHistory: "لا توجد قراءات خلال آخر 24 ساعة لهذه المنطقة.",
  },
  en: {
    eyebrow: "Analytics",
    refresh: "Refresh data",
    statusTitle: "Selected city details",
    kpiTitle: "Key indicators",
    historyTitle: "Last 24 hours",
    loading: "Loading...",
    empty: "No data available.",
    retryHint: "Check that the backend is running on port 8000, then press refresh.",
    serverError: "Server responded with status",
    networkError: "Could not reach the analysis service.",
    risk: "Risk level",
    score: "Risk score",
    rainfall: "Avg rainfall",
    rain24: "24h rainfall",
    rain72: "72h rainfall",
    updated: "Last updated",
    mm: "mm",
    yes: "Yes",
    no: "No",
    safe: "Safe",
    watch: "Watch",
    danger: "Danger",
    severe: "Severe Danger",
    metricLabel: "Metric",
    chartAria: "24-hour history chart",
    selectedCity: "Selected city",
    noMetric: "The history data has no numeric values.",
    noData: "No current data available.",
    noHistory: "No readings in the last 24 hours for this region.",
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

// Known KPI keys get an Arabic label; anything else falls back to the label or
// key returned by the API (humanized), so no KPI is dropped.
const kpiLabels = {
  // Keys returned by GET /analysis/kpis (kpi_calculations.py)
  total_monitored_cities: { ar: "المدن التي لها بيانات", en: "Cities with data" },
  critical_risk_count: { ar: "مدن في خطر شديد", en: "Severe-danger cities" },
  warning_risk_count: { ar: "مدن في حالة خطر", en: "Danger cities" },
  max_rain_24h: { ar: "أعلى أمطار خلال 24 ساعة", en: "Max 24h rainfall" },
  total_cities: { ar: "إجمالي المدن", en: "Total cities" },
  cities_at_risk: { ar: "مدن في خطر", en: "Cities at risk" },
  avg_risk_score: { ar: "متوسط درجة الخطورة", en: "Average risk score" },
  max_risk_score: { ar: "أعلى درجة خطورة", en: "Highest risk score" },
  min_risk_score: { ar: "أدنى درجة خطورة", en: "Lowest risk score" },
  avg_rainfall: { ar: "متوسط الأمطار", en: "Average rainfall" },
  max_rainfall: { ar: "أعلى هطول أمطار", en: "Peak rainfall" },
  total_rainfall: { ar: "إجمالي الأمطار", en: "Total rainfall" },
};

// Candidate field names. Only fields that really exist in a response are shown.
const CITY_KEYS = ["city", "city_name", "name", "location"];
const SCORE_KEYS = ["risk_score", "score"];
const LEVEL_KEYS = ["risk_level", "level", "risk_category", "category"];
const RAIN24_KEYS = ["rain_sum_24h"];
const RAIN72_KEYS = ["rain_sum_72h"];
const RAIN_KEYS = [
  "avg_rainfall",
  "rainfall_mm",
  "rainfall",
  "rain_mm",
  "rain",
  "precipitation_mm",
  "precipitation",
  "precip_mm",
];
const TIME_KEYS = [
  "event_time",
  "timestamp",
  "time",
  "datetime",
  "date",
  "observed_at",
  "updated_at",
  "generated_at",
  "hour",
  "ts",
];
const LIST_KEYS = [
  "cities",
  "statuses",
  "items",
  "results",
  "history",
  "records",
  "points",
  "readings",
  "rows",
  "data",
];
const NESTED_KEYS = ["current", "latest", "metrics", "weather", "data"];

/* ---------- request layer: cache + in-flight dedupe ---------- */

const cache = new Map();
const inflight = new Map();

function getJson(path, force = false) {
  if (!force) {
    const hit = cache.get(path);
    if (hit && Date.now() - hit.time < CACHE_TTL_MS) {
      return Promise.resolve(hit.data);
    }
    if (inflight.has(path)) return inflight.get(path);
  }

  const promise = fetch(`${API_BASE}${path}`, {
    headers: { Accept: "application/json" },
  })
    .then(async (response) => {
      let body = null;
      let parsed = true;
      try {
        body = await response.json();
      } catch {
        parsed = false;
      }
      if (!response.ok) {
        const error = new Error(`HTTP ${response.status}`);
        error.status = response.status;
        error.detail = typeof body?.detail === "string" ? body.detail : "";
        throw error;
      }
      if (!parsed) {
        const error = new Error("Invalid JSON");
        error.status = response.status;
        throw error;
      }
      cache.set(path, { time: Date.now(), data: body });
      return body;
    })
    .finally(() => {
      inflight.delete(path);
    });

  inflight.set(path, promise);
  return promise;
}

function useResource(path, reloadKey) {
  const [state, setState] = useState({
    status: path ? "loading" : "idle",
    data: null,
    error: null,
  });
  const seenReload = useRef(reloadKey);

  useEffect(() => {
    if (!path) {
      setState({ status: "idle", data: null, error: null });
      return undefined;
    }

    // Bypass the cache only when the refresh button was pressed.
    const force = seenReload.current !== reloadKey;
    seenReload.current = reloadKey;

    let cancelled = false;
    setState({ status: "loading", data: null, error: null });

    getJson(path, force)
      .then((data) => {
        if (!cancelled) setState({ status: "success", data, error: null });
      })
      .catch((error) => {
        if (!cancelled) setState({ status: "error", data: null, error });
      });

    return () => {
      cancelled = true;
    };
  }, [path, reloadKey]);

  return state;
}

/* ---------- response normalizers ---------- */

const isPlainObject = (value) =>
  value !== null && typeof value === "object" && !Array.isArray(value);

function toNumber(value) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function pick(source, keys) {
  if (!isPlainObject(source)) return undefined;
  for (const key of keys) {
    if (source[key] !== undefined && source[key] !== null) return source[key];
  }
  for (const nestedKey of NESTED_KEYS) {
    const nested = source[nestedKey];
    if (isPlainObject(nested)) {
      for (const key of keys) {
        if (nested[key] !== undefined && nested[key] !== null) return nested[key];
      }
    }
  }
  return undefined;
}

// Accepts an array, an object wrapping an array, or an object keyed by city.
function toList(payload) {
  if (Array.isArray(payload)) return payload;
  if (!isPlainObject(payload)) return [];

  for (const key of LIST_KEYS) {
    if (Array.isArray(payload[key])) return payload[key];
  }
  for (const key of LIST_KEYS) {
    if (isPlainObject(payload[key])) {
      const inner = toList(payload[key]);
      if (inner.length) return inner;
    }
  }

  const entries = Object.entries(payload);
  if (entries.length && entries.every(([, value]) => isPlainObject(value))) {
    return entries.map(([key, value]) => ({ city: key, ...value }));
  }
  return [];
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

function formatTime(value, lang, options) {
  const date = parseTime(value);
  if (!date) return typeof value === "string" ? value : "";
  return new Intl.DateTimeFormat(LOCALES[lang] ?? lang, options).format(date);
}

// Year included so an old reading (e.g. "Jan 1, 2025") is obviously not live.
const DATE_TIME = {
  year: "numeric",
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
};
const HOUR_ONLY = { hour: "2-digit", minute: "2-digit", hour12: false };

function formatNumber(value, lang) {
  return new Intl.NumberFormat(LOCALES[lang] ?? lang, {
    maximumFractionDigits: 2,
  }).format(value);
}

function riskKeyOf(level) {
  if (typeof level !== "string") return null;
  return riskNames[level.trim().toLowerCase()] ?? null;
}

function humanize(key) {
  const spaced = String(key).replace(/[_-]+/g, " ").trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

// "St_Catherine", "St. Catherine" and "st catherine" all normalize to the same key.
function nameKey(value) {
  return String(value ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9؀-ۿ]/g, "");
}

function regionKeys(region) {
  return [region.id, region.en, region.ar, ...(region.aliases ?? [])].map(nameKey);
}

// Match one API record to the canonical region list by id / name. Records that
// match no canonical region are ignored: the list is fixed by the project.
function findRecord(region, rows) {
  const keys = regionKeys(region);
  return rows.find((row) => row.city && keys.includes(nameKey(row.city))) ?? null;
}

function normalizeStatus(item) {
  const level = pick(item, LEVEL_KEYS);
  return {
    city: pick(item, CITY_KEYS),
    score: toNumber(pick(item, SCORE_KEYS)),
    level: typeof level === "string" ? level : null,
    rain: toNumber(pick(item, RAIN_KEYS)),
    rain24: toNumber(pick(item, RAIN24_KEYS)),
    rain72: toNumber(pick(item, RAIN72_KEYS)),
    time: pick(item, TIME_KEYS),
  };
}

function normalizeKpis(payload) {
  const wrapperKeys = ["kpis", "cards", "metrics", "summary", "statistics", "data"];
  let source = payload;

  if (isPlainObject(payload)) {
    for (const key of wrapperKeys) {
      if (Array.isArray(payload[key]) || isPlainObject(payload[key])) {
        source = payload[key];
        break;
      }
    }
  }

  if (Array.isArray(source)) {
    return source
      .filter(isPlainObject)
      .map((item, index) => {
        const key = item.key ?? item.id ?? item.name ?? item.label ?? item.title;
        return {
          id: String(key ?? index),
          key: typeof key === "string" ? key : null,
          label: item.label ?? item.title ?? item.name ?? key,
          value: item.value ?? item.count ?? item.total ?? item.average ?? null,
          unit: typeof item.unit === "string" ? item.unit : "",
        };
      })
      .filter((item) => item.value !== null && typeof item.value !== "object");
  }

  if (!isPlainObject(source)) return [];

  const rows = [];
  for (const [key, value] of Object.entries(source)) {
    if (value === null || value === undefined) continue;
    if (typeof value !== "object") {
      rows.push({ id: key, key, label: key, value, unit: "" });
    } else if (isPlainObject(value)) {
      for (const [innerKey, innerValue] of Object.entries(value)) {
        if (innerValue !== null && typeof innerValue !== "object") {
          rows.push({
            id: `${key}.${innerKey}`,
            key: `${key}_${innerKey}`,
            label: `${humanize(key)} · ${humanize(innerKey)}`,
            value: innerValue,
            unit: "",
          });
        }
      }
    }
  }
  return rows;
}

function normalizeHistory(payload) {
  const points = toList(payload)
    .filter(isPlainObject)
    .map((item, index) => ({
      index,
      time: pick(item, TIME_KEYS),
      score: toNumber(pick(item, SCORE_KEYS)),
      rain: toNumber(pick(item, RAIN_KEYS)),
      rain24: toNumber(pick(item, RAIN24_KEYS)),
    }));

  const allDated = points.length > 0 && points.every((p) => parseTime(p.time));
  if (allDated) {
    points.sort((a, b) => parseTime(a.time) - parseTime(b.time));
  }
  return points;
}

/* ---------- small presentational pieces ---------- */

// analysis_api.py raises HTTPException(404) inside `try ... except Exception`,
// so the 404 is caught and re-sent as a 500 whose detail starts with
// "404: No history found...". Treat both shapes as "no record for this region".
function isNoRecord(error) {
  return (
    error?.status === 404 ||
    (error?.status === 500 && /no history found/i.test(error?.detail ?? ""))
  );
}

function StateMessage({ state, text, children, isEmpty, emptyText, notFoundIsEmpty }) {
  if (state.status === "loading" || state.status === "idle") {
    return (
      <p className="analysis-note" role="status">
        {text.loading}
      </p>
    );
  }
  // For per-region endpoints, a 404 means "no record for this region".
  if (state.status === "error" && notFoundIsEmpty && isNoRecord(state.error)) {
    return <p className="analysis-note">{emptyText ?? text.empty}</p>;
  }
  if (state.status === "error") {
    return (
      <div className="analysis-error" role="alert">
        <p>
          {state.error?.status
            ? `${text.serverError} ${state.error.status}.`
            : text.networkError}
        </p>
        <p className="analysis-note">{text.retryHint}</p>
      </div>
    );
  }
  if (isEmpty) return <p className="analysis-note">{emptyText ?? text.empty}</p>;
  return children;
}

function LineChart({ points, metric, lang, text }) {
  const W = 720;
  const H = 280;
  const pad = { left: 48, right: 16, top: 16, bottom: 36 };

  const usable = points.filter((p) => p[metric] !== null);
  const dataMax = Math.max(0, ...usable.map((p) => p[metric]));
  const yMax =
    metric === "score" ? Math.max(100, dataMax) : dataMax > 0 ? dataMax * 1.15 : 1;

  const count = points.length;
  const xAt = (i) =>
    count <= 1
      ? (pad.left + W - pad.right) / 2
      : pad.left + (i / (count - 1)) * (W - pad.left - pad.right);
  const yAt = (v) => pad.top + (1 - v / yMax) * (H - pad.top - pad.bottom);

  let path = "";
  let pen = false;
  points.forEach((p, i) => {
    if (p[metric] === null) {
      pen = false;
      return;
    }
    path += `${pen ? "L" : "M"}${xAt(i).toFixed(1)} ${yAt(p[metric]).toFixed(1)} `;
    pen = true;
  });

  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * yMax);
  const step = Math.max(1, Math.ceil(count / 6));
  const xTicks = points.filter((_, i) => i % step === 0 || i === count - 1);

  return (
    <div className="chart-wrap" dir="ltr">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={text.chartAria}
        className="line-chart"
      >
        {yTicks.map((tick) => (
          <g key={tick}>
            <line
              className="chart-grid"
              x1={pad.left}
              x2={W - pad.right}
              y1={yAt(tick)}
              y2={yAt(tick)}
            />
            <text className="chart-label" x={pad.left - 8} y={yAt(tick) + 4} textAnchor="end">
              {formatNumber(tick, lang)}
            </text>
          </g>
        ))}

        {xTicks.map((p) => (
          <text
            key={p.index}
            className="chart-label"
            x={xAt(p.index)}
            y={H - 12}
            textAnchor="middle"
          >
            {p.time ? formatTime(p.time, lang, HOUR_ONLY) : p.index + 1}
          </text>
        ))}

        <path className="chart-line" d={path.trim()} />

        {points.map((p, i) =>
          p[metric] === null ? null : (
            <circle key={i} className="chart-dot" cx={xAt(i)} cy={yAt(p[metric])} r="3.5">
              <title>
                {`${p.time ? formatTime(p.time, lang, DATE_TIME) : i + 1}: ${formatNumber(
                  p[metric],
                  lang
                )}`}
              </title>
            </circle>
          )
        )}
      </svg>
    </div>
  );
}

/* ---------- main component ---------- */

export default function AnalysisPanel({ lang, city, regions = [] }) {
  const text = labels[lang] ?? labels.ar;
  const dir = lang === "ar" ? "rtl" : "ltr";

  const [reloadKey, setReloadKey] = useState(0);
  const [metric, setMetric] = useState("score");

  // Status and KPIs are city-independent: fetched once (then cached), never on
  // city change. History is keyed by the encoded city, so it only refetches
  // when the selected city actually changes.
  const status = useResource("/analysis/current-status", reloadKey);
  const kpis = useResource("/analysis/kpis", reloadKey);
  const history = useResource(
    city ? `/analysis/history/${encodeURIComponent(city)}` : null,
    reloadKey
  );

  // The API row for the selected region (matched by canonical id / name from the
  // existing current-status response), or null when it has no current record.
  const selectedRecord = useMemo(() => {
    if (status.status !== "success") return null;
    const region = regions.find((item) => item.id === city);
    if (!region) return null;
    const rows = toList(status.data).filter(isPlainObject).map(normalizeStatus);
    return findRecord(region, rows);
  }, [status, regions, city]);
  const kpiRows = useMemo(
    () => (kpis.status === "success" ? normalizeKpis(kpis.data) : []),
    [kpis]
  );
  const points = useMemo(
    () => (history.status === "success" ? normalizeHistory(history.data) : []),
    [history]
  );

  const availableMetrics = ["score", "rain", "rain24"].filter((key) =>
    points.some((p) => p[key] !== null)
  );
  const activeMetric = availableMetrics.includes(metric)
    ? metric
    : availableMetrics[0];
  const metricName = {
    score: text.score,
    rain: `${text.rainfall} (${text.mm})`,
    rain24: `${text.rain24} (${text.mm})`,
  };

  const regionLabel = (id) =>
    regions.find((region) => region.id === id)?.[lang] ?? id ?? "";

  // The five metrics of the selected-city card. A missing value is shown as "—".
  const cityMetrics = (() => {
    const record = selectedRecord;
    const number = (value, suffix) =>
      value === null || value === undefined
        ? null
        : `${formatNumber(value, lang)}${suffix}`;
    const rows = [
      { key: "score", label: text.score, value: number(record?.score, " / 100") },
      { key: "rain", label: text.rainfall, value: number(record?.rain, ` ${text.mm}`) },
      { key: "rain24", label: text.rain24, value: number(record?.rain24, ` ${text.mm}`) },
      { key: "rain72", label: text.rain72, value: number(record?.rain72, ` ${text.mm}`) },
      {
        key: "updated",
        label: text.updated,
        value: record?.time ? formatTime(record.time, lang, DATE_TIME) || null : null,
      },
    ];
    return rows.map((row) => ({
      ...row,
      empty: row.value === null,
      value: row.value ?? "—",
    }));
  })();

  const kpiLabel = (row) => {
    const known = row.key ? kpiLabels[row.key.toLowerCase()] : null;
    if (known) return known[lang];
    return typeof row.label === "string" ? humanize(row.label) : String(row.label);
  };

  const kpiUnit = (row) => (/rain/i.test(row.key ?? "") ? text.mm : "");

  const kpiValue = (row) => {
    if (typeof row.value === "boolean") return row.value ? text.yes : text.no;
    const numeric = typeof row.value === "number" ? row.value : null;
    return numeric !== null ? formatNumber(numeric, lang) : String(row.value);
  };

  return (
    <section className="analysis-panel" dir={dir}>
      <div className="analysis-header">
        <p className="eyebrow">{text.eyebrow}</p>
        <button
          className="toolbar-button"
          type="button"
          onClick={() => setReloadKey((current) => current + 1)}
        >
          {text.refresh}
        </button>
      </div>

      <div className="card">
        <h2>{text.kpiTitle}</h2>
        <StateMessage state={kpis} text={text} isEmpty={kpiRows.length === 0}>
          <div className="kpi-grid">
            {kpiRows.map((row) => (
              <article className="kpi-card" key={row.id}>
                <span className="kpi-label">{kpiLabel(row)}</span>
                <strong className="kpi-value">
                  {kpiValue(row)}
                  {(row.unit || kpiUnit(row)) && (
                    <small> {row.unit || kpiUnit(row)}</small>
                  )}
                </strong>
              </article>
            ))}
          </div>
        </StateMessage>
      </div>

      <div className="card selected-city-card">
        <h2>
          {regionLabel(city)}
        </h2>
        <StateMessage state={status} text={text}>
          <dl className="city-metrics">
            {cityMetrics.map((metricRow) => (
              <div className="city-metric" key={metricRow.key}>
                <dt>{metricRow.label}</dt>
                <dd className={metricRow.empty ? "is-empty" : ""}>{metricRow.value}</dd>
              </div>
            ))}
          </dl>
          {!selectedRecord && <p className="analysis-note">{text.noData}</p>}
        </StateMessage>
      </div>

      <div className="card">
        <div className="chart-heading">
          <h2>
            {text.historyTitle} · {regionLabel(city)}
          </h2>
          {availableMetrics.length > 1 && (
            <div className="metric-switch" role="group" aria-label={text.metricLabel}>
              {availableMetrics.map((key) => (
                <button
                  key={key}
                  type="button"
                  className={key === activeMetric ? "active" : ""}
                  onClick={() => setMetric(key)}
                >
                  {metricName[key]}
                </button>
              ))}
            </div>
          )}
        </div>
        <StateMessage
          state={history}
          text={text}
          isEmpty={points.length === 0}
          emptyText={text.noHistory}
          notFoundIsEmpty
        >
          {activeMetric ? (
            <LineChart points={points} metric={activeMetric} lang={lang} text={text} />
          ) : (
            <p className="analysis-note">{text.noMetric}</p>
          )}
        </StateMessage>
      </div>
    </section>
  );
}