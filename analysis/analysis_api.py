import os
import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)
from warehouse.db_connection import get_engine
from analysis.analysis_queries import (
    GET_CURRENT_STATUS_QUERY,
    GET_CITY_HISTORY_QUERY,
    GET_CITIES_COMPARISON_QUERY,
    GET_WEEKLY_TREND_QUERY,
    GET_HOURLY_PATTERN_QUERY,
    GET_PREDICTIONS_VS_ACTUAL_QUERY,
    GET_SOIL_VS_RISK_QUERY,
)
from analysis.kpi_calculations import (
    calculate_summary_kpis,
    calculate_extended_kpis,
)

app = FastAPI(
    title="Egypt Flash Flood Analysis API",
    description="APIs for current status, historical data, and KPIs.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/analysis/current-status")
def get_current_status():
    try:
        engine = get_engine()
        df = pd.read_sql(GET_CURRENT_STATUS_QUERY, engine)
        df = df.where(pd.notnull(df), None)
        return {"status": "success", "data": df.to_dict(orient="records")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analysis/history/{city}")
def get_city_history(city: str):
    try:
        engine = get_engine()
        df = pd.read_sql(GET_CITY_HISTORY_QUERY, engine, params=(city, city))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if df.empty:
        raise HTTPException(
            status_code=404, detail=f"No history found for city: {city}"
        )

    df = df.where(pd.notnull(df), None)
    return {
        "status": "success",
        "city": city,
        "data": df.to_dict(orient="records"),
    }


@app.get("/analysis/kpis")
def get_kpis():
    try:
        engine = get_engine()
        df = pd.read_sql(GET_CURRENT_STATUS_QUERY, engine)
        kpis = calculate_summary_kpis(df)
        return {"status": "success", "kpis": kpis}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analysis/kpis/extended")
def get_extended_kpis():
    """يرجع المؤشرات الموسعة الـ 13 للبطاقات العلوية في لوحة التحليل"""
    try:
        engine = get_engine()
        df = pd.read_sql(GET_CITIES_COMPARISON_QUERY, engine)
        preds_df = pd.read_sql(GET_PREDICTIONS_VS_ACTUAL_QUERY, engine)
        kpis = calculate_extended_kpis(df, preds_df)
        return {"status": "success", "kpis": kpis}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analysis/charts/cities-overview")
def get_cities_overview():
    """يغذي رسومات: (1) مقارنة الخطورة، (2) توزيع الحالات، (3) أمطار 24h vs 72h، (4) التضاريس vs الخطورة"""
    try:
        engine = get_engine()
        df = pd.read_sql(GET_CITIES_COMPARISON_QUERY, engine)
        df = df.where(pd.notnull(df), None)
        records = df.to_dict(orient="records")

        distribution = df["risk_level"].value_counts().to_dict() if not df.empty else {}
        return {
            "status": "success",
            "risk_distribution": distribution,
            "cities": records,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analysis/charts/weekly-trend")
def get_weekly_trend():
    """يغذي رسم: (6) الاتجاه الأسبوعي لآخر 7 أيام"""
    try:
        engine = get_engine()
        df = pd.read_sql(GET_WEEKLY_TREND_QUERY, engine)
        df = df.where(pd.notnull(df), None)
        return {"status": "success", "data": df.to_dict(orient="records")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analysis/charts/hourly-pattern")
def get_hourly_pattern():
    """يغذي رسم: (8) الساعات الأعلى مطراً وخطورة خلال اليوم"""
    try:
        engine = get_engine()
        df = pd.read_sql(GET_HOURLY_PATTERN_QUERY, engine)
        df = df.where(pd.notnull(df), None)
        return {"status": "success", "data": df.to_dict(orient="records")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analysis/charts/predictions-comparison")
def get_predictions_comparison():
    """يغذي رسم: (5) مقارنة التنبؤات بالواقع"""
    try:
        engine = get_engine()
        df = pd.read_sql(GET_PREDICTIONS_VS_ACTUAL_QUERY, engine)
        df = df.where(pd.notnull(df), None)
        return {"status": "success", "data": df.to_dict(orient="records")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analysis/charts/soil-moisture-impact")
def get_soil_moisture_impact():
    """يغذي رسم: (7) تأثير رطوبة التربة على درجة الخطورة"""
    try:
        engine = get_engine()
        df = pd.read_sql(GET_SOIL_VS_RISK_QUERY, engine)
        df = df.where(pd.notnull(df), None)
        return {"status": "success", "data": df.to_dict(orient="records")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))