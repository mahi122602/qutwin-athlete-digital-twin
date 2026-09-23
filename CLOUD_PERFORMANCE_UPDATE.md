# Cloud page-transition update

This complete project includes the earlier page split and memoryview login correction.

## Changes
- Database connections now use a thread-safe pool, with one retained idle connection and a maximum of six simultaneous connections per database configuration, per Python process. Existing close() calls return the lease. Open or failed transactions are rolled back by the pool; commits remain explicit. Abandoned leases have finalizer cleanup.
- Idle connections are checked after 60 seconds and replaced if disconnected. Application queries and writes are never automatically replayed.
- Thirteen athlete/coach navigation buttons use callbacks so state changes before the page rerun. This avoids loading the previous page before requesting a second rerun. Existing labels, styling and destinations are preserved.
- Database URL, environment-variable precedence and local config fallback remain as supplied. No new secrets or database migration are required.

## Apply to your GitHub-connected folder
Keep your existing local configuration. Copy this project's contents into athlete_digital_twin_github (the folder containing app.py). Keep the existing Git history and Python environment. Do not upload private data or credentials.

Create a branch before copying if desired:

```powershell
git switch -c cloud-navigation-performance
```

Run locally and test athlete and coach navigation, profile saving and uploads:

```powershell
python -m unittest discover -s tests -v
python -m streamlit run app.py
```

Then review, commit and push:

```powershell
git add .
git diff --cached --stat
git commit -m "Reuse database connections and reduce navigation reruns"
git push -u origin cloud-navigation-performance
```

Create and review the pull request, then merge into main to update the deployed app.

## Verification and limits
15 tests passed, including an actual Streamlit navigation test and mocked connection lifecycle tests. Python syntax checks passed. Digital Twin, forecasting, training and model files were compared byte-for-byte unchanged against the preceding corrected project. The pool was not tested against your live Supabase connection, and no hosted response-time improvement has been measured yet.

After deployment, compare several page switches after the first load. Initial startup and the large existing login video can still take time. Full-history queries remain unchanged.

Optional troubleshooting: QUTWIN_DB_POOL=0 disables connection reuse and restores the previous connection behavior. QUTWIN_PROFILE=1 enables per-operation timing output without logging query parameters or credentials. These can be supplied as environment variables (or top-level Streamlit secrets for deployment). Restart after changing them.

If problems appear only with pooling, disable it and retain the navigation fix while investigating. Do not change Supabase credentials or switch connection endpoint types just to apply this update.
