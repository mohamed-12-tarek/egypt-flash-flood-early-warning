
USE FloodProjectDB;
GO
IF SCHEMA_ID(N'bronze') IS NULL
    EXEC(N'CREATE SCHEMA bronze');
GO
IF OBJECT_ID(N'bronze.historical_weather', N'U') IS NULL
CREATE TABLE bronze.historical_weather (
    id                      BIGINT IDENTITY(1,1) PRIMARY KEY,
    city                    NVARCHAR(50)    NOT NULL,
    event_time              NVARCHAR(50)    NOT NULL,  
    precipitation           FLOAT           NULL,
    relative_humidity_2m    FLOAT           NULL,
    temperature_2m          FLOAT           NULL,
    surface_pressure        FLOAT           NULL,
    windspeed_10m           FLOAT           NULL,
    cloudcover              FLOAT           NULL,
    soil_moisture_0_to_7cm  FLOAT           NULL,
    ingested_at             DATETIME2       NOT NULL DEFAULT GETUTCDATE(),
    source                  NVARCHAR(20)    NOT NULL DEFAULT 'historical'
);
GO

IF OBJECT_ID(N'bronze.live_weather', N'U') IS NULL
CREATE TABLE bronze.live_weather (
    id                      BIGINT IDENTITY(1,1) PRIMARY KEY,
    city                    NVARCHAR(50)    NOT NULL,
    event_time              NVARCHAR(50)    NOT NULL,
    precipitation           FLOAT           NULL,
    relative_humidity_2m    FLOAT           NULL,
    temperature_2m          FLOAT           NULL,
    surface_pressure        FLOAT           NULL,
    windspeed_10m           FLOAT           NULL,
    cloudcover              FLOAT           NULL,
    soil_moisture_0_to_7cm  FLOAT           NULL,
    ingested_at             DATETIME2       NOT NULL DEFAULT GETUTCDATE(),
    source                  NVARCHAR(20)    NOT NULL DEFAULT 'live'
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes
               WHERE name = N'IX_bronze_live_ingested'
                 AND object_id = OBJECT_ID(N'bronze.live_weather'))
    CREATE INDEX IX_bronze_live_ingested ON bronze.live_weather (ingested_at DESC);
GO
