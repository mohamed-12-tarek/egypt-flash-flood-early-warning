import os
import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)
from warehouse.db_connection import get_engine
from analysis.analysis_queries import GET_CURRENT_STATUS_QUERY, GET_CITY_HISTORY_QUERY
from analysis.kpi_calculations import calculate_summary_kpis

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