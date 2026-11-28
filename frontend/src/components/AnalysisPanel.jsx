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

/* ---------- analytics charts: the five /analysis/charts/* endpoints ---------- */

const CHART_PATHS = {
  overview: "/analysis/charts/cities-overview",
  weekly: "/analysis/charts/weekly-trend",
  hourly: "/analysis/charts/hourly-pattern",
  predictions: "/analysis/charts/predictions-comparison",
  soil: "/analysis/charts/soil-moisture-impact",
};

const RISK_ORDER = ["safe", "watch", "danger", "severe"];

const chartLabels = {
  ar: {
    sectionTitle: "الرسوم التحليلية",
    cityRisk: "مقارنة الخطورة بين المدن",
    cityRiskNote: "درجة الخطورة الحالية لكل مدينة (من 100).",
    distribution: "توزيع مستويات الخطورة",
    distributionNote: "عدد المدن في كل مستوى خطورة.",
    cities: "مدن",
    total: "الإجمالي",
    rainCompare: "الأمطار: 24 ساعة مقابل 72 ساعة",
    terrain: "التضاريس مقابل الخطورة",
    terrainNote: "كل نقطة مدينة؛ اللون يدل على مستوى الخطورة.",
    elevation: "الارتفاع",
    slope: "الانحدار (درجة)",
    weekly: "اتجاه الخطورة الأسبوعي",
    weeklyNote: "للمدينة المحددة.",
    hourly: "النمط على مدار اليوم",
    hourlyNote: "متوسط حسب ساعة اليوم.",
    predictions: "التوقعات مقابل الفعلي",
    predictionsNote: "للمدينة المحددة عند توفر عمود المدينة.",
    soil: "تأثير رطوبة التربة",
    soilNote: "حجم النقطة = أمطار 24 ساعة؛ اللون = مستوى الخطورة.",
    soilMoisture: "رطوبة التربة",
    hourOfDay: "ساعة اليوم",
    avgRisk: "متوسط الخطورة",
    maxRisk: "أعلى خطورة",
    totalRain: "إجمالي الأمطار",
    avgHourlyRain: "متوسط الأمطار بالساعة",
    avgHourlyRisk: "متوسط الخطورة بالساعة",
    samples: "عدد العينات",
    predicted: "المتوقع",
    actual: "الفعلي",
    risk: "الخطورة",
    rain: "الأمطار",
    noCityRows: "لا توجد بيانات لهذه المدينة في هذا الرسم.",
    unknownFields: "تعذّر التعرف على حقلي المتوقع والفعلي في الرد. الحقول المتاحة:",
    metric: "المقياس",
  },
  en: {
    sectionTitle: "Analytical charts",
    cityRisk: "City risk comparison",
    cityRiskNote: "Current risk score for each city (out of 100).",
    distribution: "Risk-level distribution",
    distributionNote: "Number of cities in each risk level.",
    cities: "cities",
    total: "Total",
    rainCompare: "Rainfall: 24h vs 72h",
    terrain: "Terrain vs risk",
    terrainNote: "Each point is a city; colour shows the risk level.",
    elevation: "Elevation",
    slope: "Slope (degrees)",
    weekly: "Weekly risk trend",
    weeklyNote: "For the selected city.",
    hourly: "Time-of-day pattern",
    hourlyNote: "Average by hour of day.",
    predictions: "Predicted vs actual",
    predictionsNote: "For the selected city when a city column is provided.",
    soil: "Soil moisture impact",
    soilNote: "Dot size = 24h rainfall; colour = risk level.",
    soilMoisture: "Soil moisture",
    hourOfDay: "Hour of day",
    avgRisk: "Average risk",
    maxRisk: "Max risk",
    totalRain: "Total rainfall",
    avgHourlyRain: "Avg hourly rainfall",
    avgHourlyRisk: "Avg hourly risk",
    samples: "Samples",
    predicted: "Predicted",
    actual: "Actual",
    risk: "Risk",
    rain: "Rainfall",
    noCityRows: "No data for this city in this chart.",
    unknownFields: "Could not find predicted/actual fields in the response. Available fields:",
    metric: "Metric",
  },
};

/* ----- normalizers (only fields that exist in the response are used) ----- */

const ELEVATION_KEYS = ["elevation", "elevation_m", "altitude"];
const SLOPE_KEYS = ["slope_degree", "slope", "slope_degrees"];

function normalizeOverview(payload) {
  const source = isPlainObject(payload) ? payload : {};
  const rawCities = Array.isArray(source.cities)
    ? source.cities
    : isPlainObject(source.cities)
      ? toList(source.cities)
      : [];

  const cities = rawCities.filter(isPlainObject).map((item) => {
    const level = pick(item, LEVEL_KEYS);
    return {
      city: pick(item, CITY_KEYS),
      score: toNumber(pick(item, SCORE_KEYS)),
      level: typeof level === "string" ? level : null,
      rain24: toNumber(pick(item, RAIN24_KEYS)),
      rain72: toNumber(pick(item, RAIN72_KEYS)),
      elevation: toNumber(pick(item, ELEVATION_KEYS)),
      slope: toNumber(pick(item, SLOPE_KEYS)),
    };
  });

  // risk_distribution: [{risk_level, count}] or {"آمن": 3, ...}.
  const counts = { safe: 0, watch: 0, danger: 0, severe: 0 };
  let recognised = false;
  const add = (level, amount) => {
    const key = riskKeyOf(typeof level === "string" ? level : String(level ?? ""));
    const value = toNumber(amount);
    if (key && value !== null) {
      counts[key] += value;
      recognised = true;
    }
  };
  const dist = source.risk_distribution;
  if (Array.isArray(dist)) {
    dist.filter(isPlainObject).forEach((item) =>
      add(
        pick(item, LEVEL_KEYS) ?? item.name ?? item.label,
        item.count ?? item.total ?? item.value ?? item.cities ?? item.num_cities ?? item.n
      )
    );
  } else if (isPlainObject(dist)) {
    Object.entries(dist).forEach(([level, value]) =>
      add(level, isPlainObject(value) ? value.count ?? value.total ?? value.value : value)
    );
  }

  return { cities, distribution: recognised ? counts : null };
}

function dayHourMs(date, hour) {
  if (date === null || date === undefined || date === "") return null;
  let ms = null;
  const base = typeof date === "string" ? date.trim().slice(0, 10) : "";
  if (/^\d{4}-\d{2}-\d{2}$/.test(base)) {
    ms = Date.parse(`${base}T00:00:00Z`);
  } else {
    const parsed = parseTime(date);
    ms = parsed ? parsed.getTime() : null;
  }
  if (ms === null || Number.isNaN(ms)) return null;
  return ms + (hour ?? 0) * 3_600_000;
}

function matchesRegion(value, region) {
  if (!region) return true;
  return regionKeys(region).includes(nameKey(value));
}

function normalizeWeekly(payload, region) {
  let rows = toList(payload).filter(isPlainObject);
  const hasCity = rows.some((row) => pick(row, CITY_KEYS) !== undefined);
  if (hasCity) rows = rows.filter((row) => matchesRegion(pick(row, CITY_KEYS), region));

  return rows
    .map((row) => ({
      ms: dayHourMs(row.risk_date, toNumber(row.risk_hour)),
      hasHour: toNumber(row.risk_hour) !== null,
      avg: toNumber(row.avg_risk_score),
      max: toNumber(row.max_risk_score),
      rain: toNumber(row.total_rainfall),
    }))
    .filter((point) => point.ms !== null)
    .sort((a, b) => a.ms - b.ms);
}

function normalizeHourly(payload) {
  return toList(payload)
    .filter(isPlainObject)
    .map((row) => ({
      hour: toNumber(row.hour_of_day),
      risk: toNumber(row.avg_hourly_risk),
      rain: toNumber(row.avg_hourly_rain),
      samples: toNumber(row.sample_count),
    }))
    .filter((row) => row.hour !== null)
    .sort((a, b) => a.hour - b.hour);
}

function normalizeSoil(payload) {
  return toList(payload)
    .filter(isPlainObject)
    .map((row) => ({
      x: toNumber(row.soil_moisture),
      y: toNumber(row.risk_score),
      rain24: toNumber(row.rain_sum_24h),
      level: typeof row.risk_level === "string" ? row.risk_level : null,
    }))
    .filter((row) => row.x !== null && row.y !== null);
}

const PRED_ROLE = /(^|_)(predicted|prediction|pred|forecast|forecasted|expected)(?=_|$)/i;
const ACTUAL_ROLE = /(^|_)(actual|observed|real|measured)(?=_|$)/i;
const PRED_TIME_KEYS = [...TIME_KEYS, "prediction_time", "target_time", "forecast_time", "hour_of_day"];

// Pairs "predicted_<x>" with "actual_<x>" by their shared stem (e.g. risk_score,
// rain_sum_24h). Whatever pairs exist in the response become the chart metrics.
function normalizePredictions(payload, region) {
  let rows = toList(payload).filter(isPlainObject);
  const keys = [...new Set(rows.flatMap((row) => Object.keys(row)))];
  const numericKeys = keys.filter((key) => rows.some((row) => toNumber(row[key]) !== null));

  const stems = new Map();
  for (const key of numericKeys) {
    const role = ACTUAL_ROLE.test(key) ? "actual" : PRED_ROLE.test(key) ? "predicted" : null;
    if (!role) continue;
    const stem = key
      .replace(ACTUAL_ROLE, "")
      .replace(PRED_ROLE, "")
      .replace(/^_+|_+$/g, "")
      .toLowerCase();
    const entry = stems.get(stem) ?? {};
    entry[role] = key;
    stems.set(stem, entry);
  }
  const metrics = [...stems.entries()]
    .filter(([, entry]) => entry.predicted && entry.actual)
    .map(([stem, entry]) => ({ stem, predicted: entry.predicted, actual: entry.actual }));

  const hasCity = rows.some((row) => pick(row, CITY_KEYS) !== undefined);
  const hasTime = rows.some((row) => pick(row, PRED_TIME_KEYS) !== undefined);
  // City filter only when rows are a per-city time series; a pure per-city
  // comparison keeps every city.
  if (hasCity && hasTime) {
    rows = rows.filter((row) => matchesRegion(pick(row, CITY_KEYS), region));
  }

  const mode = hasTime ? "time" : hasCity ? "city" : "index";
  const points = rows.map((row, index) => ({
    index,
    time: mode === "time" ? pick(row, PRED_TIME_KEYS) : null,
    city: pick(row, CITY_KEYS),
    values: Object.fromEntries(numericKeys.map((key) => [key, toNumber(row[key])])),
  }));
  if (mode === "time") {
    points.sort((a, b) => (parseTime(a.time)?.getTime() ?? 0) - (parseTime(b.time)?.getTime() ?? 0));
  }

  return { metrics, points, mode, keys };
}

/* ----- small chart building blocks ----- */

function ChartCard({ title, note, state, text, isEmpty, emptyText, controls, children }) {
  return (
    <div className="card chart-card">
      <div className="chart-heading">
        <h2>{title}</h2>
        {controls}
      </div>
      {note && <p className="analysis-note chart-note">{note}</p>}
      <StateMessage state={state} text={text} isEmpty={isEmpty} emptyText={emptyText}>
        {children}
      </StateMessage>
    </div>
  );
}

function MetricSwitch({ options, value, onChange, label }) {
  if (options.length < 2) return null;
  return (
    <div className="metric-switch" role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.key}
          type="button"
          className={option.key === value ? "active" : ""}
          onClick={() => onChange(option.key)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function ChartLegend({ items }) {
  return (
    <ul className="chart-legend">
      {items.map((item) => (
        <li key={item.label}>
          <span className={`legend-swatch ${item.cls}`} />
          {item.label}
        </li>
      ))}
    </ul>
  );
}

function toneOf(level) {
  return `tone-${riskKeyOf(level) ?? "unknown"}`;
}

// Horizontal bars as HTML/CSS: they follow the page direction (RTL/LTR) and wrap
// well on small screens. Each row can hold one or several bars.
function HBarChart({ rows, lang, ariaLabel, suffix = "" }) {
  const max = Math.max(0, ...rows.flatMap((row) => row.bars.map((bar) => bar.value ?? 0)));
  return (
    <div className="hbar" role="img" aria-label={ariaLabel}>
      {rows.map((row) => (
        <div className="hbar-row" key={row.id}>
          <span className="hbar-label">{row.label}</span>
          <div className="hbar-tracks">
            {row.bars.map((bar, index) => (
              <div className="hbar-track" key={index} title={bar.title}>
                <span className="hbar-bar">
                  <span
                    className={`hbar-fill ${bar.cls}`}
                    style={{ width: `${max > 0 && bar.value ? (bar.value / max) * 100 : 0}%` }}
                  />
                </span>
                <span className="hbar-value">
                  {bar.value === null ? "—" : `${formatNumber(bar.value, lang)}${suffix}`}
                </span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function StackedBar({ counts, text, chartText, lang }) {
  const total = RISK_ORDER.reduce((sum, key) => sum + counts[key], 0);
  return (
    <div className="stacked">
      <div className="stacked-bar" role="img" aria-label={chartText.distribution}>
        {RISK_ORDER.map((key) =>
          counts[key] > 0 ? (
            <span
              key={key}
              className={`stacked-segment tone-${key}`}
              style={{ width: `${(counts[key] / total) * 100}%` }}
              title={`${text[key]}: ${formatNumber(counts[key], lang)}`}
            />
          ) : null
        )}
      </div>
      <ul className="distribution-list">
        {RISK_ORDER.map((key) => (
          <li key={key}>
            <span className={`legend-swatch tone-${key}`} />
            <span>{text[key]}</span>
            <strong>{formatNumber(counts[key], lang)}</strong>
          </li>
        ))}
      </ul>
      <p className="analysis-note">
        {chartText.total}: {formatNumber(total, lang)} {chartText.cities}
      </p>
    </div>
  );
}

function axisTicks(min, max, count = 4) {
  const span = max - min || 1;
  return Array.from({ length: count + 1 }, (_, i) => min + (span * i) / count);
}

function SeriesChart({ categories, series, lang, ariaLabel, fixedMax }) {
  const W = 720;
  const H = 300;
  const pad = { left: 52, right: 16, top: 16, bottom: 42 };

  const values = series.flatMap((item) => item.values).filter((value) => value !== null);
  const dataMax = Math.max(0, ...values);
  const yMin = Math.min(0, ...values);
  const yMax = fixedMax
    ? Math.max(fixedMax, dataMax)
    : dataMax > yMin
      ? dataMax + (dataMax - yMin) * 0.12
      : yMin + 1;
  const span = yMax - yMin || 1;

  const count = categories.length;
  const xAt = (i) =>
    count <= 1
      ? (pad.left + W - pad.right) / 2
      : pad.left + (i / (count - 1)) * (W - pad.left - pad.right);
  const yAt = (v) => pad.top + (1 - (v - yMin) / span) * (H - pad.top - pad.bottom);

  const step = Math.max(1, Math.ceil(count / 6));

  return (
    <div className="chart-wrap" dir="ltr">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={ariaLabel} className="line-chart">
        {axisTicks(yMin, yMax).map((tick) => (
          <g key={tick}>
            <line className="chart-grid" x1={pad.left} x2={W - pad.right} y1={yAt(tick)} y2={yAt(tick)} />
            <text className="chart-label" x={pad.left - 8} y={yAt(tick) + 4} textAnchor="end">
              {formatNumber(tick, lang)}
            </text>
          </g>
        ))}

        {categories.map((category, i) =>
          i % step === 0 || i === count - 1 ? (
            <text key={i} className="chart-label" x={xAt(i)} y={H - 14} textAnchor="middle">
              {category.label}
            </text>
          ) : null
        )}

        {series.map((item) => {
          let path = "";
          let pen = false;
          item.values.forEach((value, i) => {
            if (value === null) {
              pen = false;
              return;
            }
            path += `${pen ? "L" : "M"}${xAt(i).toFixed(1)} ${yAt(value).toFixed(1)} `;
            pen = true;
          });
          return (
            <g key={item.key}>
              <path
                className={`series-line ${item.cls}`}
                strokeDasharray={item.dashed ? "6 4" : undefined}
                d={path.trim()}
              />
              {item.values.map((value, i) =>
                value === null ? null : (
                  <circle key={i} className={`series-dot ${item.cls}`} cx={xAt(i)} cy={yAt(value)} r="3">
                    <title>{`${item.label} · ${categories[i].title ?? categories[i].label}: ${formatNumber(value, lang)}`}</title>
                  </circle>
                )
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function ScatterChart({ points, xLabel, yLabel, lang, ariaLabel }) {
  const W = 720;
  const H = 320;
  const pad = { left: 52, right: 18, top: 16, bottom: 52 };

  const xs = points.map((p) => p.x);
  let xMin = Math.min(...xs);
  let xMax = Math.max(...xs);
  if (xMin === xMax) {
    xMin -= 1;
    xMax += 1;
  }
  const yMax = Math.max(100, ...points.map((p) => p.y));
  const rMax = Math.max(0, ...points.map((p) => p.size ?? 0));

  const xAt = (v) => pad.left + ((v - xMin) / (xMax - xMin)) * (W - pad.left - pad.right);
  const yAt = (v) => pad.top + (1 - v / yMax) * (H - pad.top - pad.bottom);
  const radius = (p) => (p.size === null || p.size === undefined || rMax === 0 ? 5 : 4 + (p.size / rMax) * 6);

  return (
    <div className="chart-wrap" dir="ltr">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={ariaLabel} className="line-chart">
        {axisTicks(0, yMax).map((tick) => (
          <g key={`y${tick}`}>
            <line className="chart-grid" x1={pad.left} x2={W - pad.right} y1={yAt(tick)} y2={yAt(tick)} />
            <text className="chart-label" x={pad.left - 8} y={yAt(tick) + 4} textAnchor="end">
              {formatNumber(tick, lang)}
            </text>
          </g>
        ))}
        {axisTicks(xMin, xMax, 5).map((tick) => (
          <text key={`x${tick}`} className="chart-label" x={xAt(tick)} y={H - 28} textAnchor="middle">
            {formatNumber(tick, lang)}
          </text>
        ))}
        <text className="chart-axis-title" x={(pad.left + W - pad.right) / 2} y={H - 6} textAnchor="middle">
          {xLabel}
        </text>
        <text className="chart-axis-title" x={12} y={pad.top + 4} textAnchor="start">
          {yLabel}
        </text>

        {points.map((p, i) => (
          <circle key={i} className={`scatter-dot ${toneOf(p.level)}`} cx={xAt(p.x)} cy={yAt(p.y)} r={radius(p)}>
            <title>{p.title}</title>
          </circle>
        ))}
      </svg>
    </div>
  );
}

function ToneLegend({ text }) {
  return <ChartLegend items={RISK_ORDER.map((key) => ({ cls: `tone-${key}`, label: text[key] }))} />;
}

function stemLabel(stem, text, chartText) {
  if (/rain|precip/.test(stem)) {
    if (/24/.test(stem)) return text.rain24;
    if (/72/.test(stem)) return text.rain72;
    return chartText.rain;
  }
  if (/risk|score/.test(stem)) return chartText.risk;
  return humanize(stem || "value");
}

/* ----- the charts section ----- */

function ChartsSection({ lang, city, regions, reloadKey, text }) {
  const chartText = chartLabels[lang] ?? chartLabels.ar;

  const overview = useResource(CHART_PATHS.overview, reloadKey);
  const weekly = useResource(CHART_PATHS.weekly, reloadKey);
  const hourly = useResource(CHART_PATHS.hourly, reloadKey);
  const predictions = useResource(CHART_PATHS.predictions, reloadKey);
  const soil = useResource(CHART_PATHS.soil, reloadKey);

  const [terrainAxis, setTerrainAxis] = useState("elevation");
  const [weeklyMetric, setWeeklyMetric] = useState("risk");
  const [hourlyMetric, setHourlyMetric] = useState("risk");
  const [predMetric, setPredMetric] = useState(null);

  const region = regions.find((item) => item.id === city) ?? null;
  const cityText = (name) => {
    const match = regions.find((item) => regionKeys(item).includes(nameKey(name)));
    return match ? match[lang] : String(name ?? "");
  };

  const overviewData = useMemo(
    () => (overview.status === "success" ? normalizeOverview(overview.data) : null),
    [overview]
  );
  const weeklyPoints = useMemo(
    () => (weekly.status === "success" ? normalizeWeekly(weekly.data, region) : []),
    [weekly, region]
  );
  const hourlyRows = useMemo(
    () => (hourly.status === "success" ? normalizeHourly(hourly.data) : []),
    [hourly]
  );
  const predData = useMemo(
    () => (predictions.status === "success" ? normalizePredictions(predictions.data, region) : null),
    [predictions, region]
  );
  const soilPoints = useMemo(
    () => (soil.status === "success" ? normalizeSoil(soil.data) : []),
    [soil]
  );

  const cities = overviewData?.cities ?? [];

  /* city risk comparison */
  const riskRows = cities
    .filter((row) => row.score !== null)
    .sort((a, b) => b.score - a.score)
    .map((row, index) => ({
      id: `${row.city}-${index}`,
      label: cityText(row.city),
      bars: [
        {
          value: row.score,
          cls: toneOf(row.level),
          title: `${cityText(row.city)}: ${formatNumber(row.score, lang)} / 100`,
        },
      ],
    }));

  /* 24h vs 72h rainfall */
  const rainRows = cities
    .filter((row) => row.rain24 !== null || row.rain72 !== null)
    .sort((a, b) => (b.rain72 ?? b.rain24 ?? 0) - (a.rain72 ?? a.rain24 ?? 0))
    .map((row, index) => ({
      id: `${row.city}-${index}`,
      label: cityText(row.city),
      bars: [
        { value: row.rain24, cls: "series-fill-1", title: `${text.rain24} · ${cityText(row.city)}` },
        { value: row.rain72, cls: "series-fill-2", title: `${text.rain72} · ${cityText(row.city)}` },
      ],
    }));

  /* terrain vs risk */
  const terrainPoints = cities
    .filter((row) => row[terrainAxis] !== null && row.score !== null)
    .map((row) => ({
      x: row[terrainAxis],
      y: row.score,
      level: row.level,
      title: `${cityText(row.city)} · ${chartText[terrainAxis]}: ${formatNumber(row[terrainAxis], lang)} · ${
        text.score
      }: ${formatNumber(row.score, lang)}`,
    }));
  const terrainOptions = [
    { key: "elevation", label: chartText.elevation },
    { key: "slope", label: chartText.slope },
  ].filter((option) => cities.some((row) => row[option.key] !== null));
  const activeTerrain = terrainOptions.some((option) => option.key === terrainAxis)
    ? terrainAxis
    : terrainOptions[0]?.key;

  /* weekly trend */
  const weeklyHasHour = weeklyPoints.some((point) => point.hasHour);
  const weeklyFormat = new Intl.DateTimeFormat(LOCALES[lang] ?? lang, {
    month: "short",
    day: "numeric",
    ...(weeklyHasHour ? { hour: "2-digit", hour12: false } : {}),
    timeZone: "UTC",
  });
  const weeklyCategories = weeklyPoints.map((point) => ({ label: weeklyFormat.format(point.ms) }));
  const weeklyOptions = [
    { key: "risk", label: chartText.risk, show: weeklyPoints.some((p) => p.avg !== null || p.max !== null) },
    { key: "rain", label: chartText.totalRain, show: weeklyPoints.some((p) => p.rain !== null) },
  ].filter((option) => option.show);
  const activeWeekly = weeklyOptions.some((option) => option.key === weeklyMetric)
    ? weeklyMetric
    : weeklyOptions[0]?.key;
  const weeklySeries =
    activeWeekly === "rain"
      ? [{ key: "rain", label: chartText.totalRain, cls: "series-1", values: weeklyPoints.map((p) => p.rain) }]
      : [
          { key: "avg", label: chartText.avgRisk, cls: "series-1", values: weeklyPoints.map((p) => p.avg) },
          { key: "max", label: chartText.maxRisk, cls: "series-2", dashed: true, values: weeklyPoints.map((p) => p.max) },
        ];

  /* hourly pattern */
  const hourlyCategories = hourlyRows.map((row) => ({
    label: `${String(row.hour).padStart(2, "0")}:00`,
    title: `${String(row.hour).padStart(2, "0")}:00 (${chartText.samples}: ${
      row.samples === null ? "—" : formatNumber(row.samples, lang)
    })`,
  }));
  const hourlyOptions = [
    { key: "risk", label: chartText.avgHourlyRisk, show: hourlyRows.some((r) => r.risk !== null) },
    { key: "rain", label: chartText.avgHourlyRain, show: hourlyRows.some((r) => r.rain !== null) },
  ].filter((option) => option.show);
  const activeHourly = hourlyOptions.some((option) => option.key === hourlyMetric)
    ? hourlyMetric
    : hourlyOptions[0]?.key;

  /* predictions vs actual */
  const predMetrics = predData?.metrics ?? [];
  const activePred = predMetrics.find((metric) => metric.stem === predMetric) ?? predMetrics[0];
  const predOptions = predMetrics.map((metric) => ({
    key: metric.stem,
    label: stemLabel(metric.stem, text, chartText),
  }));
  const predLabelOf = (point) =>
    predData.mode === "time"
      ? formatTime(point.time, lang, DATE_TIME)
      : predData.mode === "city"
        ? cityText(point.city)
        : String(point.index + 1);

  /* soil moisture impact */
  const soilScatter = soilPoints.map((row) => ({
    x: row.x,
    y: row.y,
    size: row.rain24,
    level: row.level,
    title: `${chartText.soilMoisture}: ${formatNumber(row.x, lang)} · ${text.score}: ${formatNumber(
      row.y,
      lang
    )}${row.rain24 === null ? "" : ` · ${text.rain24}: ${formatNumber(row.rain24, lang)} ${text.mm}`}`,
  }));

  const overviewEmpty = (items) => overviewData !== null && items.length === 0;

  return (
    <>
      <div className="analysis-header charts-heading">
        <p className="eyebrow">{chartText.sectionTitle}</p>
      </div>

      <div className="chart-grid-2">
        <ChartCard
          title={chartText.cityRisk}
          note={chartText.cityRiskNote}
          state={overview}
          text={text}
          isEmpty={overviewEmpty(riskRows)}
        >
          <HBarChart rows={riskRows} lang={lang} ariaLabel={chartText.cityRisk} />
          <ToneLegend text={text} />
        </ChartCard>

        <ChartCard
          title={chartText.distribution}
          note={chartText.distributionNote}
          state={overview}
          text={text}
          isEmpty={overviewData !== null && overviewData.distribution === null}
        >
          {overviewData?.distribution && (
            <StackedBar counts={overviewData.distribution} text={text} chartText={chartText} lang={lang} />
          )}
        </ChartCard>
      </div>

      <div className="chart-grid-2">
        <ChartCard
          title={chartText.rainCompare}
          state={overview}
          text={text}
          isEmpty={overviewEmpty(rainRows)}
        >
          <HBarChart rows={rainRows} lang={lang} ariaLabel={chartText.rainCompare} suffix={` ${text.mm}`} />
          <ChartLegend
            items={[
              { cls: "series-fill-1", label: text.rain24 },
              { cls: "series-fill-2", label: text.rain72 },
            ]}
          />
        </ChartCard>

        <ChartCard
          title={chartText.terrain}
          note={chartText.terrainNote}
          state={overview}
          text={text}
          isEmpty={overviewEmpty(terrainPoints)}
          controls={
            <MetricSwitch
              options={terrainOptions}
              value={activeTerrain}
              onChange={setTerrainAxis}
              label={chartText.metric}
            />
          }
        >
          <ScatterChart
            points={terrainPoints}
            xLabel={chartText[activeTerrain] ?? ""}
            yLabel={text.score}
            lang={lang}
            ariaLabel={chartText.terrain}
          />
          <ToneLegend text={text} />
        </ChartCard>
      </div>

      <ChartCard
        title={`${chartText.weekly} · ${region ? region[lang] : city}`}
        note={chartText.weeklyNote}
        state={weekly}
        text={text}
        isEmpty={weeklyPoints.length === 0 || weeklyOptions.length === 0}
        emptyText={chartText.noCityRows}
        controls={
          <MetricSwitch options={weeklyOptions} value={activeWeekly} onChange={setWeeklyMetric} label={chartText.metric} />
        }
      >
        <SeriesChart
          categories={weeklyCategories}
          series={weeklySeries}
          lang={lang}
          ariaLabel={chartText.weekly}
          fixedMax={activeWeekly === "risk" ? 100 : undefined}
        />
        <ChartLegend items={weeklySeries.map((item) => ({ cls: `${item.cls}-key`, label: item.label }))} />
      </ChartCard>

      <ChartCard
        title={chartText.hourly}
        note={chartText.hourlyNote}
        state={hourly}
        text={text}
        isEmpty={hourlyRows.length === 0 || hourlyOptions.length === 0}
        controls={
          <MetricSwitch options={hourlyOptions} value={activeHourly} onChange={setHourlyMetric} label={chartText.metric} />
        }
      >
        <SeriesChart
          categories={hourlyCategories}
          series={[
            {
              key: activeHourly,
              label: activeHourly === "rain" ? chartText.avgHourlyRain : chartText.avgHourlyRisk,
              cls: "series-1",
              values: hourlyRows.map((row) => (activeHourly === "rain" ? row.rain : row.risk)),
            },
          ]}
          lang={lang}
          ariaLabel={chartText.hourly}
          fixedMax={activeHourly === "risk" ? 100 : undefined}
        />
      </ChartCard>

      <ChartCard
        title={chartText.predictions}
        note={chartText.predictionsNote}
        state={predictions}
        text={text}
        isEmpty={predData !== null && predData.points.length === 0}
        emptyText={chartText.noCityRows}
        controls={
          <MetricSwitch options={predOptions} value={activePred?.stem} onChange={setPredMetric} label={chartText.metric} />
        }
      >
        {predData && !activePred ? (
          <div className="analysis-note">
            <p>{chartText.unknownFields}</p>
            <p dir="ltr">
              <code>{predData.keys.join(", ")}</code>
            </p>
          </div>
        ) : activePred && predData.mode === "time" ? (
          <SeriesChart
            categories={predData.points.map((point) => ({ label: predLabelOf(point) }))}
            series={[
              {
                key: "predicted",
                label: chartText.predicted,
                cls: "series-1",
                dashed: true,
                values: predData.points.map((point) => point.values[activePred.predicted]),
              },
              {
                key: "actual",
                label: chartText.actual,
                cls: "series-2",
                values: predData.points.map((point) => point.values[activePred.actual]),
              },
            ]}
            lang={lang}
            ariaLabel={chartText.predictions}
          />
        ) : activePred ? (
          <HBarChart
            rows={predData.points.map((point) => ({
              id: String(point.index),
              label: predLabelOf(point),
              bars: [
                { value: point.values[activePred.predicted], cls: "series-fill-1", title: chartText.predicted },
                { value: point.values[activePred.actual], cls: "series-fill-2", title: chartText.actual },
              ],
            }))}
            lang={lang}
            ariaLabel={chartText.predictions}
          />
        ) : null}
        {activePred && (
          <ChartLegend
            items={[
              { cls: predData.mode === "time" ? "series-1-key" : "series-fill-1", label: chartText.predicted },
              { cls: predData.mode === "time" ? "series-2-key" : "series-fill-2", label: chartText.actual },
            ]}
          />
        )}
      </ChartCard>

      <ChartCard
        title={chartText.soil}
        note={chartText.soilNote}
        state={soil}
        text={text}
        isEmpty={soilPoints.length === 0}
      >
        <ScatterChart
          points={soilScatter}
          xLabel={chartText.soilMoisture}
          yLabel={text.score}
          lang={lang}
          ariaLabel={chartText.soil}
        />
        <ToneLegend text={text} />
      </ChartCard>
    </>
  );
}


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
          {text.statusTitle} · {regionLabel(city)}
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

      <ChartsSection
        lang={lang}
        city={city}
        regions={regions}
        reloadKey={reloadKey}
        text={text}
      />
    </section>
  );
}