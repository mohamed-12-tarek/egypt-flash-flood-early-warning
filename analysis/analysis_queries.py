

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
SELECT 
    city,
    event_time,
    avg_rainfall,
    rain_sum_24h,
    rain_sum_72h,
    risk_score,
    risk_level
FROM gold.fact_hourly_risk
WHERE city = ?
  AND event_time >= DATEADD(hour, -24, GETUTCDATE())
ORDER BY event_time ASC;
"""