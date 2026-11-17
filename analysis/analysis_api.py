
import pandas as pd
from fastapi import FastAPI, HTTPException
import sys
import os


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from warehouse.db_connection import get_engine
from analysis.analysis_queries import GET_CURRENT_STATUS_QUERY, GET_CITY_HISTORY_QUERY
from analysis.kpi_calculations import calculate_summary_kpis

app = FastAPI(
    title="Egypt Flash Flood Analysis API",
    description="APIs for current status, historical data, and KPIs.",
    version="1.0.0"
)

@app.get("/analysis/current-status")
def get_current_status():
    try:
        engine = get_engine()
        df = pd.read_sql(GET_CURRENT_STATUS_QUERY, engine)
        return {"status": "success", "data": df.to_dict(orient="records")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analysis/history/{city}")
def get_city_history(city: str):
    try:
        engine = get_engine()
        df = pd.read_sql(GET_CITY_HISTORY_QUERY, engine, params=(city,))
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No history found for city: {city}")
        return {"status": "success", "city": city, "data": df.to_dict(orient="records")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analysis/kpis")
def get_kpis():
    try:
        engine = get_engine()
        df = pd.read_sql(GET_CURRENT_STATUS_QUERY, engine)
        kpis = calculate_summary_kpis(df)
        return {"status": "success", "kpis": kpis}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))