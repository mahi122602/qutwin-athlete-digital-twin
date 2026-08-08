QUTWIN FORECASTING INSTALLATION

1. Copy the forecasting/, database/, and views/ files into your project.
2. Replace app.py with app_with_forecasting.py and rename it app.py.
3. Run database/migrations/002_gender_and_forecasting.sql in PostgreSQL.
4. Install: pip install -r requirements_forecasting.txt
5. Apply PROFILE_GENDER_PATCH.py to athlete_profile().
6. Optionally apply SIGNUP_GENDER_PATCH.py so gender is captured at registration.
7. Start: streamlit run app.py

The page reports measured rolling-origin MAPE-based performance. It does not
claim 80% unless the backtest actually reaches 80% or more.
