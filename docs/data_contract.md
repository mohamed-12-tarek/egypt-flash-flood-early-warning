# 📜 Data Contract
### Flood Warning Project — المرجع الوحيد لأسماء الجداول والأعمدة والرسائل

> **قاعدة صارمة:** أي تعديل على أي اسم جدول أو عمود أو رسالة في هذا الملف **لازم يتناقش في الميتنج الأسبوعي** قبل التنفيذ. أي كود في المشروع لازم يطابق هذا الملف بالحرف الواحد.

---

## 1) المناطق المعتمدة (Canonical City Names)

استخدم هذه الأسماء **بالحرف الواحد** في كل مكان (Kafka messages, SQL tables, Python code):

```
St_Catherine, Dahab, Nuweiba, Taba, Sharm_El_Sheikh, Ras_Gharib,
Hurghada, Safaga, Quseir, Marsa_Alam, Ain_Sokhna, Suez, Aswan, Luxor, Sohag
```

---

## 2) رسالة Kafka (Topic: `flood-risk-raw`)

كل رسالة بتتبعت من `producer_live.py` لازم تكون بالشكل ده بالظبط:

```json
{
  "city": "St_Catherine",
  "time": "2026-09-23T14:00",
  "precipitation": 0.0,
  "relative_humidity_2m": 55.0,
  "temperature_2m": 21.4,
  "surface_pressure": 1012.3,
  "windspeed_10m": 12.1,
  "cloudcover": 30.0,
  "soil_moisture_0_to_7cm": 0.12,
  "ingested_at": "2026-09-23T14:00:05Z",
  "source": "live"
}
```

| الحقل | النوع | إلزامي؟ |
|---|---|---|
| `city` | string (من القائمة أعلاه فقط) | ✅ |
| `time` | ISO string | ✅ |
| `precipitation` | float (≥ 0) | ✅ |
| `relative_humidity_2m` | float (0–100) | ✅ |
| `temperature_2m` | float | ⚪ (ممكن null) |
| `surface_pressure` | float | ⚪ |
| `windspeed_10m` | float | ⚪ |
| `cloudcover` | float | ⚪ |
| `soil_moisture_0_to_7cm` | float | ⚪ |
| `ingested_at` | ISO timestamp | ✅ |
| `source` | `"live"` أو `"historical"` | ✅ |

---

## 3) Bronze Layer (ملفات، مش SQL)

```
bronze/historical/weather_raw.parquet
bronze/live/{year}/{month}/{day}/{hour}/weather_raw.json
```
**الأعمدة:** نفس حقول رسالة Kafka بالظبط (القسم 2).

---

## 4) Silver Layer — SQL Server

### `silver.fact_weather_features`

```sql
CREATE TABLE silver.fact_weather_features (
    id                      BIGINT IDENTITY(1,1) PRIMARY KEY,
    city                    NVARCHAR(50)    NOT NULL,
    event_time              DATETIME2       NOT NULL,
    source                  NVARCHAR(20)    NOT NULL,

    precipitation           FLOAT           NOT NULL,
    relative_humidity_2m    FLOAT           NOT NULL,
    temperature_2m          FLOAT           NULL,
    surface_pressure        FLOAT           NULL,
    windspeed_10m           FLOAT           NULL,
    cloudcover              FLOAT           NULL,
    soil_moisture_0_to_7cm  FLOAT           NULL,

    elevation               FLOAT           NOT NULL,
    slope_degree            FLOAT           NOT NULL,

    rain_lag_1h             FLOAT           NULL,
    rain_lag_3h             FLOAT           NULL,
    rain_lag_24h            FLOAT           NULL,
    rain_sum_6h             FLOAT           NULL,
    rain_sum_24h            FLOAT           NULL,
    rain_sum_72h            FLOAT           NULL,
    hour_of_day             INT             NOT NULL,
    month                   INT             NOT NULL,

    processed_at            DATETIME2       NOT NULL DEFAULT GETUTCDATE(),

    CONSTRAINT UQ_silver_city_time UNIQUE (city, event_time)
);

CREATE INDEX IX_silver_city_time ON silver.fact_weather_features (city, event_time DESC);
```

**مالك الجدول:** منه وخيري (Schema) — يوسف (كتابة/قراءة عبر Spark).

---

## 5) Gold Layer — SQL Server

### `gold.dim_location` (ثابت)

```sql
CREATE TABLE gold.dim_location (
    city            NVARCHAR(50)    PRIMARY KEY,
    latitude        FLOAT           NOT NULL,
    longitude       FLOAT           NOT NULL,
    elevation       FLOAT           NOT NULL,
    slope_degree    FLOAT           NOT NULL,
    updated_at      DATETIME2       NOT NULL DEFAULT GETUTCDATE()
);
```
**مالك:** محمد طارق (يملأه مرة واحدة عبر `fetch_static_data.py`).

### `gold.fact_hourly_risk` (كل ساعة)

```sql
CREATE TABLE gold.fact_hourly_risk (
    id                  BIGINT IDENTITY(1,1) PRIMARY KEY,
    city                NVARCHAR(50)    NOT NULL,
    event_time          DATETIME2       NOT NULL,
    avg_rainfall        FLOAT           NOT NULL,
    rain_sum_24h        FLOAT           NOT NULL,
    rain_sum_72h        FLOAT           NOT NULL,
    risk_score          INT             NOT NULL,   -- 0–100
    risk_level          NVARCHAR(20)    NOT NULL,   -- آمن / مراقبة / خطر / خطر شديد
    loaded_at           DATETIME2       NOT NULL DEFAULT GETUTCDATE(),

    CONSTRAINT UQ_gold_city_time UNIQUE (city, event_time)
);

CREATE INDEX IX_gold_risk_time ON gold.fact_hourly_risk (event_time DESC);
```
**مالك:** يوسف (يكتب فيه عبر `silver_to_gold_load.py`) — عمرو وعبد الرحمن ومحمد طارق (بيقرأوا منه بس).

### `gold.predictions`

```sql
CREATE TABLE gold.predictions (
    id                      BIGINT IDENTITY(1,1) PRIMARY KEY,
    city                    NVARCHAR(50)    NOT NULL,
    predicted_for           DATETIME2       NOT NULL,
    predicted_rainfall      FLOAT           NOT NULL,
    predicted_risk_score    INT             NOT NULL,
    predicted_risk_level    NVARCHAR(20)    NOT NULL,
    model_version           NVARCHAR(20)    NOT NULL,
    generated_at            DATETIME2       NOT NULL DEFAULT GETUTCDATE(),

    CONSTRAINT UQ_pred_city_time UNIQUE (city, predicted_for, model_version)
);
```
**مالك:** عبد الرحمن (يكتب فيه عبر `inference_job.py`) — عمرو ومحمد طارق ويوسف (بيقرأوا منه بس).

---

## 6) قيم `risk_level` المعتمدة (نفس النص بالحرف الواحد في كل الكود)

| النطاق | القيمة |
|---|---|
| 0–29 | `"آمن"` |
| 30–59 | `"مراقبة"` |
| 60–79 | `"خطر"` |
| 80–100 | `"خطر شديد"` |

---

## 7) أسماء الـ APIs الداخلية (بين Backend والـ Frontend)

| Endpoint | مالكه | بيرجع إيه |
|---|---|---|
| `GET /analysis/current-status` | عمرو | آخر `risk_score`/`risk_level` لكل مدينة |
| `GET /analysis/history/{city}` | عمرو | آخر 24 ساعة لمدينة معينة |
| `GET /analysis/kpis` | عمرو | بطاقات الملخص (عدد المناطق في خطر، أعلى قيمة...) |
| `POST /chatbot/ask` | محمد طارق | body: `{"question": "..."}` → يرجع `{"answer": "..."}` |

---

*هذا الملف هو مصدر الحقيقة الوحيد (Single Source of Truth) لكل مسميات المشروع.*