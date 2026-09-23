# QUTwin adaptive upload and prediction update

Built against your latest `athlete_digital_twin_github (2).zip`, supplied 22 September 2026.

This is one replacement package, not a collection of alternative patches. Copy every file in `replacement_files` into your existing application folder, preserving its subfolders. It contains complete files, including trained model artifacts; you do not need to assemble snippets or train models to run it.

## What this update can and cannot deliver

It implements flexible content-based imports, automatic calculation of supported features, separately evaluated models for four input sets, measured-data analysis when no model applies, real AI drafts with coach review, fresh per-file History, and clearer input guidance. It preserves the existing main page layouts and route names.

It cannot make accurate injury predictions from arbitrary athlete data. The supplied research dataset has 999 rows, 333 athletes, only 100 m/800 m events and three dates. Its load definition and injury-label provenance are undocumented. The new injury classifiers score approximately 37–40% balanced accuracy on held-out athletes. They are exploratory labels, not validated probabilities. The code does not hide this limitation or invent measurements to make every card numeric.

## 1. Stop the app and replace the files

1. In the VS Code terminal running Streamlit, press Ctrl+C.
2. Keep a backup of your current project folder.
3. Extract this ZIP into a separate temporary folder.
4. Open `replacement_files`. Copy ALL its contents into:

   `C:\Users\mahib\OneDrive\Desktop\projects\athlete_digital_twin_github`

5. Choose **Replace the files in the destination** and merge folders. The destination is the folder containing your existing `app.py`.
6. Check that this file now exists directly under your project:

   `research_prediction\adaptive_models.joblib`

Do not put `replacement_files` itself inside the project. Do not replace your entire project with this partial package. Your app.py, images, original datasets, login routes, database credentials and Git history remain in your existing folder.

## 2. Install the runtime dependencies

Open PowerShell in VS Code and run these commands individually:

```powershell
cd "C:\Users\mahib\OneDrive\Desktop\projects\athlete_digital_twin_github"
python -m pip install -r requirements.txt
python -m utils.check_workflow --offline
```

The last command must print `Offline checks passed`. Use the same `python` for installing and launching. The new model bundle uses scikit-learn 1.6.1 and CatBoost 1.2.8, pinned in requirements.txt. A Python 3.13 Windows run was not available in the build environment; the package was exercised under Python 3.12/Linux.

You do not need to run `research_prediction.train` during installation. The trained bundle is included. The training command is retained for reproducibility and future documented dataset changes, not run on page clicks.

## 3. Keep Supabase connected and check the schema

Keep your current Supabase connection settings. This update does not replace your config.py or database connection module.

Run:

```powershell
python -m utils.check_workflow
```

This checks the existing connection and automatically applies the existing additive migration 005 if required. It may create missing workflow tables/columns; it does not delete athlete records. It does not perform a paid AI request.

If it specifically reports that the database role cannot apply migration 005:

1. Open the SQL Editor in the SAME Supabase project used by this app.
2. Open `database\migrations\005_upload_review_workflow.sql` from your project.
3. Copy its complete contents into the SQL Editor and run it once.
4. Run `python -m utils.check_workflow` again.

Do not create a new Supabase project or change the database simply because a workflow table is missing. The migration assumes your original QUTwin base tables already exist.

## 4. Configure real AI generation

Add these two **top-level** entries to your existing local `.streamlit\secrets.toml`. Place them before any TOML `[section]` headings. Preserve all existing database settings:

```toml
OPENAI_API_KEY = "YOUR_ACTUAL_OPENAI_API_KEY"
QUTWIN_AI_MODEL = "gpt-4.1-mini"
```

Use an API account with access and available quota. Do not paste your key into chat or commit the secrets file. This package cannot supply your credentials or verify account access.

GPT-4.1 mini supports the Chat Completions endpoint used by the application. Official reference: https://developers.openai.com/api/docs/models/gpt-4.1-mini

The same two settings must be added to your Streamlit Cloud app's Secrets before the deployed app can generate recommendations. Local secrets are not uploaded by copying code to GitHub.

The Prediction page's session configuration remains available, but persistent app secrets are the installation path for this package. If no key/model is configured, measurements and history still save; the page explains the setup issue and does not substitute fixed text for AI generation.

## 5. Launch and verify the actual workflow

```powershell
python -m streamlit run app.py
```

Then:

1. Log in as an athlete and select the actual event or events being trained for.
2. Upload an activity export. Recognised columns are processed automatically. Unknown/ambiguous units stay unconfirmed rather than guessed.
3. Review any flagged fields. For a single-activity file without a date column, enter the known date/time under **Review columns, units and file format**. Include the timezone offset. A filename-derived date is a suggestion only; it may be an export date.
4. Assign the file's records to their event. A single selected event is automatically selected where unambiguous. Multiple selections do not multiply the workload.
5. Click **Upload and proceed**. Prediction uses an evaluated input tier when possible. Otherwise, its Activity analysis shows the usable measurements and explains what prevents scoring. AI can still summarise those measured facts for coach review.
6. Open History: there should be one row for the saved file, ordered by database upload time. Its latest snapshot, AI text, four charts and interpretation use the current saved result. No synthetic daily records are inserted.
7. Log in as the assigned coach. Open Recommendation Reviews. Approve, modify or reject the draft.
8. Return as the athlete. The linked decision appears under Recommendation from coach, History and notifications. Role matching now recognises both older lowercase notifications and newer title-case notifications.

If the same file was already saved under the previous model version, select it on Prediction and click **Recalculate this saved upload**. This preserves its ID/date and saves the old assessment inside the new snapshot. Existing AI drafts and coach-reviewed assessments are deliberately not overwritten by recalculation.

## 6. Deploy the tested code

After local checks pass, commit the copied replacement files and push to the branch used by your existing Streamlit deployment. Include `research_prediction/adaptive_models.joblib` and `requirements.txt`. Do not commit secrets, virtual environments or cache folders. The package does not push or merge GitHub changes for you.

Add the AI settings in Streamlit Cloud Secrets, then restart the deployed app after the dependency installation finishes. Keep the same repository, branch, app.py path and Supabase connection as your working deployment. The Prediction caption should read `Upload analysis · adaptive-v2`.

## Optional developer verification

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q tests
```

The delivered implementation passed 112 automated tests in the build environment. Database workflow tests use an isolated SQLite adapter and schema mocks, not your live Supabase server. AI responses are mocked. The two supplied running CSVs were also parsed and assessed successfully as load-only research estimates. See VALIDATION.md for results and limits.
