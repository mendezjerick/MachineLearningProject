# Rice Price Forecasting & Advisory (MLI Guide)

This project follows the **MLI_Guide** proposal for "Rice Price Forecasting and Rule-Based Advisory System". It uses the provided `rice.csv` dataset to:

- Clean and aggregate PSA/WFP/WB rice price series to monthly national and regional averages.
- Train baseline forecasting models (Linear Regression, Random Forest, HistGradientBoosting) with time-aware features.
- Persist the best-performing model (
  next-month horizon via `artifacts/best_model.joblib`) plus documented metrics.
- Interpret model outputs through a lightweight forward-chaining rule base that produces stakeholder advisories tied to SDG 2 and SDG 8.
- Surface insights, forecasts, and advisories through a Streamlit dashboard.

## Project layout

```
.
├── rice.csv                     # raw dataset supplied by the user
├── app.py                       # Streamlit dashboard
├── requirements.txt             # Python dependencies
├── src/mli_rice                 # reusable Python package
│   ├── data.py                  # loading & aggregation helpers
│   ├── features.py              # feature engineering utilities
│   ├── modeling.py              # training + forecasting logic
│   ├── rules.py                 # rule-based advisory engine
│   └── cli.py                   # Typer CLI for training & reporting
├── artifacts/                   # serialized models + metrics (gitignored)
├── reports/                     # generated forecasts/advisories
└── MLI_Guide.pdf                # reference proposal
```

## Quick start

1. **Install dependencies** (Python 3.11 recommended):
   ```powershell
   pip install -r requirements.txt
   ```

2. **Set the module path** for CLI usage (PowerShell example):
   ```powershell
   $env:PYTHONPATH = "$PWD/src"
   ```

3. **Explore the dataset**:
   ```powershell
   python -m mli_rice.cli describe
   ```

4. **Train models & log metrics** (1-month horizon with 12-month holdout window):
   ```powershell
   python -m mli_rice.cli train --holdout-months 12 --horizon 1
   ```
   Outputs:
   - `artifacts/best_model.joblib` – fitted sklearn pipeline
   - `artifacts/metrics.json` – CV & holdout RMSE/R² for each candidate

5. **Generate forecasts + advisories** (set `--forecast-months` to look multiple months ahead even if the dataset stops earlier):
   ```powershell
   python -m mli_rice.cli forecast `
     --forecast-months 2 `
     --output-path reports/next_month_forecast.csv `
     --advisories-path reports/rule_based_advisories.csv
   ```

6. **Launch the dashboard** (after training):
   ```powershell
   streamlit run app.py
   ```

## Modeling approach

- **Aggregation**: `mli_rice.data` creates national and region-level monthly averages with a `date` index.
- **Feature engineering** (`mli_rice.features`):
  - Lagged prices (1, 2, 3, 6 months)
  - Rolling mean/std (3- & 6-month windows)
  - Temporal encodings (`month`, sinusoidal seasonality, running `time_index`)
- **Algorithms**: Linear Regression, Random Forest Regressor, and HistGradientBoosting (scikit-learn).
- **Evaluation**: 5-fold time-series CV + 12-month holdout RMSE/R². Metrics are persisted to JSON for auditability.
- **Artifacts**: Best model refit on full data after selection to maximize predictive strength for operational use.

## Rule-based reasoning

`mli_rice.rules` implements forward-chaining heuristics aligned with the guide's examples:

- >5% forecasted MoM price rise or 3-month upward trend ⇒ "Supply Risk" (import/storage) advisory.
- >3% projected decline ⇒ "Market Opportunity" to stabilize farmer income.
- Regional forecast >1σ above national mean ⇒ "Consumer Protection" (monitoring/subsidies).
- Forecast well below mean with falling trend ⇒ "Trade Optimization" (ship to deficit areas).
- Persistent uptick ⇒ "Local Government Action" prompt for LGUs/DA.

The CLI stores the resulting advisories in `reports/rule_based_advisories.csv`, while the dashboard renders them alongside forecasts for transparency.

## Dashboard highlights (`app.py`)

- **Exploratory overview**: interactive region-level price trends + national benchmark.
- **Model evaluation**: tabular view of CV/holdout metrics with the current best estimator flagged.
- **Forecasts & advisories**: predicted next-month price per region, percent deltas, and triggered advisory messages.
- **SDG alignment**: concise mapping of outputs to SDG 2 (Zero Hunger) and SDG 8 (Decent Work & Growth).

## Web API & Vercel-ready portal

The repository now ships with a lightweight FastAPI endpoint (`api/forecast.py`) plus a static UI (`index.html`, `web/app.js`, `web/styles.css`). Together they deliver a GitHub-ready site that Vercel can host:

- `GET /api/forecast` parameters:
  - `months`: number of sequential months to produce (default 1, max 24).
  - `target_year` + `target_month` (optional): request the specific month you want to reach; the API will run enough steps to get there and return only that month.
- Response: JSON metadata + all matching regional rows with prices, percentage deltas, and the originating `step`.
- The static portal collects the month/year + months-ahead input from users, calls the API via `fetch`, and presents filters for viewing each month.

### Local run

```powershell
# launch API
uvicorn api.forecast:app --reload --port 8000

# in a second terminal, open the static client (any static server works)
python -m http.server 8080
# visit http://localhost:8080 and interact with the UI (it will call http://localhost:8000/api/forecast)
```

### Deploy to Vercel

1. Ensure `artifacts/best_model.joblib` (and optionally `metrics.json`) are committed so the API can load a model in the serverless build.
2. Push the repo to GitHub and create a Vercel project from it. The included `vercel.json` pins Python 3.11 for `api/*.py`.
3. No build command is required—the static site is served as-is and the Python function handles `/api/forecast`.
4. After deployment, Visiting `/` shows the portal; `/api/forecast?months=3` returns JSON for programmatic use.

## Extensibility

- Adjust lag windows or horizons via CLI options (`--horizon`) or by editing `FeatureConfig` defaults.
- Extend `generate_advisories` to ingest external signals (rainfall, import volumes) as data becomes available.
- Replace/augment the baseline models with deep-learning (LSTM) models by adding new estimators inside `mli_rice.modeling`.
- Connect the dashboard to a live database/API once production data pipelines exist.

## References

- `MLI_Guide.pdf` – proposal text with objectives, rules, and SDG framing.
- PSA/WFP/World Bank rice price statistics consolidated in `rice.csv`.
