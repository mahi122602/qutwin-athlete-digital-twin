# QUTwin Athlete Digital Twin

Start this existing project from its root in your normal Python environment:

```powershell
streamlit run app.py
```

`app.py` is the main entry point for Athlete and Coach accounts. The Coach
route opens Coach Studio with Dawn/Dusk themes, connected athletes, teams,
recommendation reviews, insights and profile pages. Existing forecasting and
prediction model files remain in the project.

Read [PROJECT_SETUP.md](PROJECT_SETUP.md) for installation into Mahima's actual
project folder, the database/table mapping, schema checks and GitHub steps.
Keep your existing private `config.py` and `.streamlit/secrets.toml` locally.
Set equivalent database/API settings in the hosting platform's secrets when
deploying. The update does not include or replace private settings.

Check the configured Coach database with:

```powershell
python -m utils.check_coach_database
```

Create missing workflow/team tables only when needed with:

```powershell
python -m utils.check_coach_database --setup
```

Install missing dependencies with `python -m pip install -r requirements.txt`.
