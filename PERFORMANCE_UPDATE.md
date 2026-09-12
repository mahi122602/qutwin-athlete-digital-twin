# QUTwin performance update

## Run the updated copy
1. Keep your current working project as a backup. Extract this ZIP into a separate folder.
2. Open the extracted athlete_digital_twin folder (the folder containing app.py) in VS Code.
3. Select the same Python interpreter that runs your current app. Keep your current database configuration and PostgreSQL service available. If your local configuration has changed since the uploaded ZIP, copy that current configuration into this extracted project.
4. Run `python -m streamlit run app.py` from that folder.

No new dependency or database migration is required by this refactor. Existing project dependencies are still required. The archive contains the supplied project assets and models; a Python environment is not bundled.

## Changes
- Athlete, coach and authentication page functions now have individual modules under views/athlete, views/coach and views/auth. app.py remains the entry point.
- Existing imports through athlete_pages.py, coach_pages.py and auth_pages.py remain supported by lightweight wrappers. Pages import when called.
- Identical database reads are reused within a single app execution, with copied results. A new interaction starts a fresh cache. Writes invalidate it, including failed writes.
- Loaded prediction model files are reused and reloaded when their file timestamp or size changes.
- Forecasting schema setup runs once per process after a successful initialization.
- Login asset encoding is cached. Its existing large video still needs to be delivered to the browser.

Page layouts, SQL statements, model binaries and relocated page function bodies are preserved. No MCP features were added.

## Validation and practical limits
Eight regression tests passed, all relocated modules imported, and the unauthenticated Streamlit login page rendered without exceptions in AppTest. The 22 relocated page bodies were compared with the source using Python AST; existing SQL strings were compared unchanged.

Run the tests with `python -m unittest discover -s tests -v`.

Live PostgreSQL, authenticated page flows and browser layout were not tested here. Full history queries and connection creation remain possible bottlenecks. Faster module imports do not prove a particular end-to-end speedup.

## Check with your database
- Log in as an athlete; open Dashboard, Profile, Upload Data, Prediction, History, Visualisation, What-if, Forecasting and Requests.
- Save a profile change and verify the updated value appears immediately.
- Upload a small known-valid file and confirm the expected records and duplicate handling.
- Log in as a coach and check assigned athletes, history, recommendations and notifications.
- Compare prediction and forecast results with the original app using the same data.

For operation timings in the PowerShell terminal, run:

```powershell
$env:QUTWIN_PROFILE = "1"
python -m streamlit run app.py
```

Timing logs include operation names, elapsed time and cache hits, without parameters or athlete data. Remove the variable when finished with `Remove-Item Env:QUTWIN_PROFILE`.

If a problem appears, stop the updated app and launch your original project. Preserve the complete traceback for diagnosis.

## Login cache correction
Database results containing non-copyable values, including PostgreSQL memoryview binary data, bypass optional read caching. Values are returned unchanged. Regression tests cover this case and ensure database exceptions still propagate. Live database login must still be checked in your environment.
