USE FloodProjectDB;
GO
IF SCHEMA_ID(N'silver') IS NULL
    EXEC(N'CREATE SCHEMA silver');
GO
IF OBJECT_ID(N'silver.fact_weather_features', N'U') IS NULL
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

    rain_sum_1h             FLOAT           NULL,
    rain_sum_3h             FLOAT           NULL,
    rain_sum_6h             FLOAT           NULL,
    rain_sum_24h            FLOAT           NULL,
    rain_sum_72h            FLOAT           NULL,
    rain_lag_1h             FLOAT           NULL,
    rain_lag_24h            FLOAT           NULL,

    hour_of_day             INT             NOT NULL,
    month                   INT             NOT NULL,

    processed_at            DATETIME2       NOT NULL DEFAULT GETUTCDATE(),

    CONSTRAINT UQ_silver_city_time UNIQUE (city, event_time)
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes
               WHERE name = N'IX_silver_city_time'
                 AND object_id = OBJECT_ID(N'silver.fact_weather_features'))
    CREATE INDEX IX_silver_city_time ON silver.fact_weather_features (city, event_time DESC);
GO
