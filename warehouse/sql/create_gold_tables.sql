USE FloodProjectDB;
GO
IF SCHEMA_ID(N'gold') IS NULL
    EXEC(N'CREATE SCHEMA gold');
GO
IF OBJECT_ID(N'gold.dim_location', N'U') IS NULL
CREATE TABLE gold.dim_location (
    city            NVARCHAR(50)    PRIMARY KEY,
    latitude        FLOAT           NOT NULL,
    longitude       FLOAT           NOT NULL,
    elevation       FLOAT           NOT NULL,
    slope_degree    FLOAT           NOT NULL,
    updated_at      DATETIME2       NOT NULL DEFAULT GETUTCDATE()
);
GO

IF OBJECT_ID(N'gold.fact_hourly_risk', N'U') IS NULL
CREATE TABLE gold.fact_hourly_risk (
    id                  BIGINT IDENTITY(1,1) PRIMARY KEY,
    city                NVARCHAR(50)    NOT NULL,
    event_time          DATETIME2       NOT NULL,
    avg_rainfall        FLOAT           NOT NULL,
    rain_sum_24h        FLOAT           NOT NULL,
    rain_sum_72h        FLOAT           NOT NULL,
    risk_score          INT             NOT NULL,
    risk_level          NVARCHAR(20)    NOT NULL,
    loaded_at           DATETIME2       NOT NULL DEFAULT GETUTCDATE(),

    CONSTRAINT UQ_gold_city_time UNIQUE (city, event_time)
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes
               WHERE name = N'IX_gold_risk_time'
                 AND object_id = OBJECT_ID(N'gold.fact_hourly_risk'))
    CREATE INDEX IX_gold_risk_time ON gold.fact_hourly_risk (event_time DESC);
GO

IF OBJECT_ID(N'gold.predictions', N'U') IS NULL
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
GO
