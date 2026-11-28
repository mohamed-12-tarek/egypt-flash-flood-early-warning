GET_CURRENT_STATUS_QUERY = """
SELECT 
    f.city,
    f.event_time,
    f.avg_rainfall,
    f.rain_sum_24h,
    f.rain_sum_72h,
    f.risk_score,
    f.risk_level,
    d.latitude,
    d.longitude,
    d.elevation,
    d.slope_degree
FROM gold.fact_hourly_risk f
INNER JOIN gold.dim_location d ON f.city = d.city
WHERE f.event_time = (
    SELECT MAX(event_time) 
    FROM gold.fact_hourly_risk 
    WHERE city = f.city
);
"""

GET_CITY_HISTORY_QUERY = """
WITH latest_city_time AS (
    SELECT MAX(event_time) AS max_time
    FROM gold.fact_hourly_risk
    WHERE city = ?
)
SELECT 
    f.city,
    f.event_time,
    f.avg_rainfall,
    f.rain_sum_24h,
    f.rain_sum_72h,
    f.risk_score,
    f.risk_level
FROM gold.fact_hourly_risk f
CROSS JOIN latest_city_time l
WHERE f.city = ?
  AND l.max_time IS NOT NULL
  AND f.event_time >= DATEADD(hour, -24, l.max_time)
ORDER BY f.event_time ASC;
"""

GET_CITIES_COMPARISON_QUERY = """
WITH latest AS (
    SELECT
        f.city,
        f.event_time,
        f.avg_rainfall,
        f.rain_sum_24h,
        f.rain_sum_72h,
        f.risk_score,
        f.risk_level,
        LAG(f.risk_score) OVER (PARTITION BY f.city ORDER BY f.event_time) AS prev_risk_score,
        ROW_NUMBER() OVER (PARTITION BY f.city ORDER BY f.event_time DESC) AS rn
    FROM gold.fact_hourly_risk f
)
SELECT
    l.city,
    l.event_time,
    l.avg_rainfall,
    l.rain_sum_24h,
    l.rain_sum_72h,
    l.risk_score,
    l.risk_level,
    COALESCE(l.risk_score - l.prev_risk_score, 0) AS risk_delta_1h,
    d.latitude,
    d.longitude,
    d.elevation,
    d.slope_degree
FROM latest l
INNER JOIN gold.dim_location d ON l.city = d.city
WHERE l.rn = 1
ORDER BY l.risk_score DESC, l.rain_sum_24h DESC;
"""

GET_WEEKLY_TREND_QUERY = """
SELECT
    city,
    CAST(event_time AS DATE) AS risk_date,
    DATEPART(HOUR, event_time) AS risk_hour,
    ROUND(AVG(CAST(risk_score AS FLOAT)), 2) AS avg_risk_score,
    MAX(risk_score) AS max_risk_score,
    ROUND(SUM(avg_rainfall), 2) AS total_rainfall
FROM gold.fact_hourly_risk
WHERE event_time >= DATEADD(day, -7, (SELECT MAX(event_time) FROM gold.fact_hourly_risk))
GROUP BY city, CAST(event_time AS DATE), DATEPART(HOUR, event_time)
ORDER BY risk_date ASC, risk_hour ASC;
"""

GET_HOURLY_PATTERN_QUERY = """
SELECT
    DATEPART(HOUR, event_time) AS hour_of_day,
    ROUND(AVG(avg_rainfall), 3) AS avg_hourly_rain,
    ROUND(AVG(CAST(risk_score AS FLOAT)), 2) AS avg_hourly_risk,
    COUNT(*) AS sample_count
FROM gold.fact_hourly_risk
GROUP BY DATEPART(HOUR, event_time)
ORDER BY hour_of_day ASC;
"""

GET_PREDICTIONS_VS_ACTUAL_QUERY = """
DECLARE @max_pred DATETIME2 = (SELECT MAX(predicted_for) FROM gold.predictions);

SELECT
    p.city,
    p.predicted_for AS timestamp,
    p.predicted_rainfall,
    p.predicted_risk_score,
    p.predicted_risk_level,
    f.avg_rainfall AS actual_rainfall,
    f.risk_score AS actual_risk_score,
    f.risk_level AS actual_risk_level
FROM gold.predictions p
LEFT JOIN gold.fact_hourly_risk f
    ON p.city = f.city AND p.predicted_for = f.event_time
WHERE @max_pred IS NOT NULL
  AND p.predicted_for >= DATEADD(day, -7, @max_pred)
ORDER BY p.city ASC, p.predicted_for ASC;
"""

GET_SOIL_VS_RISK_QUERY = """
SELECT TOP 500
    s.city,
    s.event_time,
    ROUND(s.soil_moisture_0_to_7cm, 3) AS soil_moisture,
    s.rain_sum_24h,
    g.risk_score,
    g.risk_level
FROM silver.fact_weather_features s
INNER JOIN gold.fact_hourly_risk g
    ON s.city = g.city AND s.event_time = g.event_time
WHERE s.rain_sum_24h > 0
ORDER BY s.event_time DESC;
"""