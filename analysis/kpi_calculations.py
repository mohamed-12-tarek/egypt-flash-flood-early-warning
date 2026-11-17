import pandas as pd

def calculate_summary_kpis(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "total_monitored_cities": 0,
            "critical_risk_count": 0,
            "warning_risk_count": 0,
            "max_rain_24h": 0.0,
        }

    total_cities = df["city"].nunique() if "city" in df.columns else 0
    
  
    critical_count = int((df["risk_level"] == "خطر شديد").sum()) if "risk_level" in df.columns else 0
    warning_count = int((df["risk_level"] == "خطر").sum()) if "risk_level" in df.columns else 0
    
    max_rain = float(df["rain_sum_24h"].max()) if "rain_sum_24h" in df.columns else 0.0

    return {
        "total_monitored_cities": total_cities,
        "critical_risk_count": critical_count,
        "warning_risk_count": warning_count,
        "max_rain_24h": round(max_rain, 2),
    }

def evaluate_risk_level(score: int) -> str:
    if score >= 80:
        return "خطر شديد"
    elif score >= 60:
        return "خطر"
    elif score >= 30:
        return "مراقبة"
    else:
        return "آمن"