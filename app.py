from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.append(str(SRC))

from mli_rice import data as data_module
from mli_rice.features import FeatureConfig
from mli_rice.modeling import TrainingConfig, multi_step_forecast
from mli_rice.rules import advisories_to_frame, generate_advisories

st.set_page_config(page_title="Rice Price Forecasting", layout="wide")

DATA_PATH = ROOT / "rice.csv"
ARTIFACT_PATH = ROOT / "artifacts" / "best_model.joblib"
METRICS_PATH = ROOT / "artifacts" / "metrics.json"


@st.cache_data(show_spinner=False)
def load_dataset(path: Path) -> pd.DataFrame:
    return data_module.load_rice_data(path)


@st.cache_data(show_spinner=False)
def regional_monthly(df: pd.DataFrame) -> pd.DataFrame:
    return data_module.region_monthly_average(df)


@st.cache_data(show_spinner=False)
def national_monthly(df: pd.DataFrame) -> pd.DataFrame:
    return data_module.national_monthly_average(df)


@st.cache_resource(show_spinner=False)
def load_pipeline(path: Path):
    if path.exists():
        return joblib.load(path)
    return None


@st.cache_data(show_spinner=False)
def load_metrics(path: Path) -> dict | None:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def layout_overview(df: pd.DataFrame, region_df: pd.DataFrame, national_df: pd.DataFrame) -> None:
    st.header("Exploratory Overview")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Rows", f"{len(df):,}")
    col2.metric("Regions", df["admin1"].nunique())
    col3.metric("Span", f"{df['year'].min()} - {df['year'].max()}")
    col4.metric("Latest Price", f"{national_df['national_price'].iloc[-1]:.2f} PHP/kg")

    available_regions = sorted(region_df["admin1"].unique())
    region_choice = st.selectbox("Select a region", available_regions)
    subset = region_df[region_df["admin1"] == region_choice]
    fig_region = px.line(subset, x="date", y="avg_price", title=f"{region_choice} retail prices")
    fig_region.update_layout(yaxis_title="PHP/kg")

    fig_national = px.line(national_df, x="date", y="national_price", title="National average retail price")
    fig_national.update_layout(yaxis_title="PHP/kg")

    st.plotly_chart(fig_region, use_container_width=True)
    st.plotly_chart(fig_national, use_container_width=True)


def layout_evaluation(metrics: dict | None) -> None:
    st.header("Model Evaluation")
    if not metrics:
        st.info("Train the model via `python -m mli_rice.cli train` to log evaluation metrics.")
        return
    selected = metrics.get("selected_model")
    records = []
    for name, stats in metrics["models"].items():
        record = {"model": name, **stats}
        record["selected"] = "best" if name == selected else ""
        records.append(record)
    df = pd.DataFrame(records)
    df.rename(columns={"cv_rmse": "CV RMSE", "cv_r2": "CV R2", "holdout_rmse": "Holdout RMSE", "holdout_r2": "Holdout R2"}, inplace=True)
    st.dataframe(df)


def layout_forecasts(region_df: pd.DataFrame, pipeline) -> None:
    st.header("Forecasts & Advisories")
    if pipeline is None:
        st.warning("No trained pipeline found. Run the training CLI to generate `artifacts/best_model.joblib`.")
        return
    config = TrainingConfig()
    months_to_forecast = st.slider("Months to forecast", min_value=1, max_value=6, value=1)
    feature_cfg = FeatureConfig()
    predictions, histories = multi_step_forecast(
        region_df,
        pipeline,
        months=months_to_forecast,
        config=config,
        feature_config=feature_cfg,
    )
    st.subheader("Forecast results")
    formatted = predictions.copy()
    formatted["forecast_date"] = formatted["forecast_date"].dt.date
    formatted["current_date"] = formatted["current_date"].dt.date
    formatted["pct_change"] = (formatted["pct_change"] * 100).round(2)
    st.dataframe(formatted, use_container_width=True)

    step_options = sorted(predictions["step"].unique())
    def _format_step(step: int) -> str:
        step_df = predictions[predictions["step"] == step]
        if not step_df.empty:
            month_label = step_df["forecast_date"].iloc[0].strftime("%b %Y")
            return f"{month_label} (step {step})"
        return f"Step {step}"

    selected_step = st.selectbox(
        "Advisories for which forecast month?",
        step_options,
        format_func=_format_step,
    )
    selected_predictions = predictions[predictions["step"] == selected_step]
    history_for_step = histories[selected_step - 1]
    advisories = generate_advisories(history_for_step, selected_predictions)
    if advisories:
        st.subheader("Rule-based advisories")
        adv_df = advisories_to_frame(advisories)
        st.dataframe(adv_df, use_container_width=True)
    else:
        st.info("No advisories triggered under the current rules.")


@st.cache_data(show_spinner=False)
def sdg_notes() -> pd.DataFrame:
    data = [
        {"SDG": "SDG 2 Zero Hunger", "Contribution": "Targets price volatility early, allowing LGUs to stabilize consumer access."},
        {"SDG": "SDG 8 Decent Work & Growth", "Contribution": "Highlights fair market opportunities and protects farmer income through proactive guidance."},
    ]
    return pd.DataFrame(data)


def layout_sdg_section() -> None:
    st.header("SDG Alignment")
    st.write(
        "The workflow prioritizes food security (SDG 2) and resilient livelihoods (SDG 8) by pairing forecasts "
        "with prescriptive advisories."
    )
    st.dataframe(sdg_notes(), use_container_width=True)


def main() -> None:
    st.title("Rice Price Forecasting & Advisory")
    st.caption("Forecasting pipeline + knowledge-based advisories inspired by the MLI guide.")
    df = load_dataset(DATA_PATH)
    region_df = regional_monthly(df)
    national_df = national_monthly(df)
    metrics = load_metrics(METRICS_PATH)
    pipeline = load_pipeline(ARTIFACT_PATH)

    layout_overview(df, region_df, national_df)
    layout_evaluation(metrics)
    layout_forecasts(region_df, pipeline)
    layout_sdg_section()


if __name__ == "__main__":
    main()
