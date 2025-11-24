from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.append(str(SRC))

from mli_rice import data as data_module
from mli_rice.features import FeatureConfig
from mli_rice.modeling import TrainingConfig, multi_step_forecast

app = FastAPI(title="Rice Forecast API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def get_region_history() -> pd.DataFrame:
    df = data_module.load_rice_data()
    return data_module.region_monthly_average(df)


@lru_cache(maxsize=1)
def get_pipeline():
    config = TrainingConfig()
    artifact = config.artifact_path
    if not artifact.exists():
        raise RuntimeError(f"Missing trained model at {artifact}.")
    return joblib.load(artifact)


@lru_cache(maxsize=1)
def get_feature_config() -> FeatureConfig:
    return FeatureConfig()


def _months_between(start: pd.Timestamp, end: pd.Timestamp) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month)


@app.get("/")
def forecast(
    months: int = Query(1, ge=1, le=24, description="Number of sequential months to generate."),
    target_year: int | None = Query(None, ge=2000, le=2100, description="Year component of the target month."),
    target_month: int | None = Query(None, ge=1, le=12, description="Month component (1-12) of the target month."),
):
    region_df = get_region_history().copy()
    pipeline = get_pipeline()
    config = TrainingConfig()
    feature_cfg = get_feature_config()
    last_observed = region_df["date"].max()

    target_date: pd.Timestamp | None = None
    months_to_generate = months

    if (target_year is None) ^ (target_month is None):
        raise HTTPException(status_code=400, detail="Provide both target_year and target_month, or omit both.")

    if target_year is not None and target_month is not None:
        target_date = pd.Timestamp(year=target_year, month=target_month, day=1)
        delta = _months_between(last_observed, target_date)
        if delta < 1:
            raise HTTPException(
                status_code=400,
                detail=f"Target must be after the latest observation ({last_observed.strftime('%Y-%m')}).",
            )
        months_to_generate = max(months_to_generate, delta)

    forecasts, _ = multi_step_forecast(
        region_df,
        pipeline,
        months=months_to_generate,
        config=config,
        feature_config=feature_cfg,
    )

    if target_date is not None:
        forecasts = forecasts[forecasts["forecast_date"] == target_date]

    results = [
        {
            "region": row[config.region_col],
            "current_date": row["current_date"].strftime("%Y-%m-%d"),
            "forecast_date": row["forecast_date"].strftime("%Y-%m-%d"),
            "current_price": row[config.price_col],
            "forecast_price": row["forecast_price"],
            "price_change": row["price_change"],
            "pct_change": row["pct_change"],
            "step": int(row["step"]),
        }
        for _, row in forecasts.iterrows()
    ]

    return {
        "latest_observation": last_observed.strftime("%Y-%m-%d"),
        "months_requested": months,
        "months_generated": months_to_generate,
        "target_date": target_date.strftime("%Y-%m-%d") if target_date else None,
        "result_count": len(results),
        "results": results,
    }
