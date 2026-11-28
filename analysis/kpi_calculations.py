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

    critical_count = (
        int(df["risk_level"].isin(["Severe Danger", "خطر شديد"]).sum())
        if "risk_level" in df.columns
        else 0
    )
    warning_count = (
        int(df["risk_level"].isin(["Danger", "خطر"]).sum())
        if "risk_level" in df.columns
        else 0
    )

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


def calculate_extended_kpis(df: pd.DataFrame, predictions_df: pd.DataFrame | None = None) -> dict:
    if df.empty:
        return {
            "total_monitored_cities": 0,
            "severe_danger_count": 0,
            "danger_count": 0,
            "watch_count": 0,
            "safe_count": 0,
            "avg_risk_score": 0.0,
            "highest_risk_city": None,
            "highest_risk_score": 0,
            "max_rain_24h": 0.0,
            "max_rain_72h": 0.0,
            "active_rain_cities": 0,
            "escalating_cities_count": 0,
            "predicted_high_risk_count": 0,
        }

    severe_count = int(df["risk_level"].isin(["Severe Danger", "خطر شديد"]).sum())
    danger_count = int(df["risk_level"].isin(["Danger", "خطر"]).sum())
    watch_count = int(df["risk_level"].isin(["Watch", "مراقبة"]).sum())
    safe_count = int(df["risk_level"].isin(["Safe", "آمن"]).sum())

    top_row = df.sort_values(["risk_score", "rain_sum_24h"], ascending=False).iloc[0]
    escalating = int((df["risk_delta_1h"] > 0).sum()) if "risk_delta_1h" in df.columns else 0

    pred_high = 0
    if predictions_df is not None and not predictions_df.empty:
        pred_high = int(
            predictions_df["predicted_risk_level"]
            .isin(["Severe Danger", "Danger", "خطر شديد", "خطر"])
            .sum()
        )

    return {
        "total_monitored_cities": int(df["city"].nunique()),
        "severe_danger_count": severe_count,
        "danger_count": danger_count,
        "watch_count": watch_count,
        "safe_count": safe_count,
        "avg_risk_score": round(float(df["risk_score"].mean()), 1),
        "highest_risk_city": str(top_row["city"]),
        "highest_risk_score": int(top_row["risk_score"]),
        "max_rain_24h": round(float(df["rain_sum_24h"].max()), 2),
        "max_rain_72h": round(float(df["rain_sum_72h"].max()), 2),
        "active_rain_cities": int((df["avg_rainfall"] > 0).sum()),
        "escalating_cities_count": escalating,
        "predicted_high_risk_count": pred_high,
    }