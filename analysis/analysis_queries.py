

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