# QUTwin Gender-Based Forecasting Upgrade

## What this package adds

- A top navigation option named **Forecasting**.
- A general seven-day athlete forecast for every athlete.
- An optional menstrual-aware path for profiles saved as Female.
- Editable menstrual history using period start and end dates.
- Calculated period duration and cycle span.
- Seven-day tabular forecasts containing date, span, forecast result, fatigue,
  readiness, injury risk, Digital Twin score, Health Index, AI advice, coach
  advice, model method and confidence.
- Multiple Linear Regression, Holt-Winters when weekly seasonality is detected,
  ARIMA/Box-Jenkins candidates, and inverse-RMSE forecast combination.
- Rolling-origin evaluation with MAE, MSE, RMSE and MAPE.

## Files to copy

Copy these package files into the matching project folders:

```text
forecasting/__init__.py
forecasting/engine.py
database/forecasting_repository.py
database/migrations/002_gender_and_forecasting.sql
views/forecasting_page.py
```

Replace your current `app.py` with `app_with_forecasting.py`, then rename it to
`app.py`.

## Install dependencies

```bash
pip install -r requirements_forecasting.txt
```

## Database setup

The forecasting page calls `ensure_forecasting_schema()` automatically. For a
controlled deployment, run the SQL migration manually in PostgreSQL before
starting the application:

```bash
psql -d YOUR_DATABASE -f database/migrations/002_gender_and_forecasting.sql
```

The repository first tries to reuse one of these project helpers:

```text
database.connection.get_connection
database.connection.get_db_connection
database.db_connection.get_connection
database.db_connection.get_db_connection
database.database.get_connection
```

When none exists, set `DATABASE_URL`, or set `DB_HOST`, `DB_NAME`, `DB_USER`,
`DB_PASSWORD` and optionally `DB_PORT`.

## Add gender to Athlete Profile

Use `PROFILE_GENDER_PATCH.py` as the small insertion patch for your existing
`athlete_profile()` function. Existing accounts without gender can also save it
from the Forecasting page on first use.

## About the requested 80% accuracy

The code does not manufacture an 80% claim. It calculates a rolling-origin
MAPE-based score and displays **target met** only when the measured score is at
least 80%. With insufficient history or a score below 80%, the UI states that
clearly. This protects the research from an unsupported accuracy claim.

For dependable personalised evaluation, collect continuous daily Digital Twin
history. Holt-Winters requires enough records to test weekly seasonality, and
ARIMA becomes more defensible as longitudinal history grows.
