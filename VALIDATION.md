# Validation and implementation notes

## Measured model performance

Model selection: three-fold grouped development CV. Reported metrics: untouched 20% athlete holdout. Bundled models fitted on development athletes only.

| Input set | Fatigue model | Injury-label model | Fatigue MAE | Injury balanced accuracy |
|---|---|---|---:|---:|
| complete | catboost | catboost | 4.67 | 39.2% |
| load_recovery | linear | linear | 5.19 | 39.9% |
| recovery | catboost | catboost | 5.31 | 39.8% |
| load_only | catboost | linear | 6.13 | 37.0% |

These are dataset holdout results, not accuracy on real-world wearable exports. MAE is in fatigue-score units, not an accuracy percentage. Injury labels remain weak. Model choice used grouped development folds; held-out athletes were not used to choose or fit the delivered models.

## Automated and sample checks

- 112 tests passed under Python 3.12/Linux; 13 existing SQLite date-adapter deprecation warnings.
- Offline package/model check passed.
- Covered CSV delimiters and encodings, Excel content with incorrect suffixes, HTML tables, JSON, ZIP member errors, XML/TCX/GPX, Apple workout matching, missing fields, locale/unit mapping and date confirmation.
- Covered input-tier routing, untouched observations, unsupported-event handling, same-file reanalysis protection, duplicate uploads, coach authorisation, atomic notification rollback, old/new notification roles and fresh History rendering.
- Reviewed all 155 active Python files for syntax and traced the import/training/prediction/save/recommendation/history paths. Nested old cloud-update copies are not the running app and were left unchanged.

## Supplied running files

| File | Imported activity records | HR | Minutes | Derived proxy load | Result |
|---|---:|---:|---:|---:|---|
| MalappuramRun20260625061537.csv | 1 | 163.0 | 27.83 | 45.37 | load-only research estimate |
| KochitalukRun20260513064914.csv | 1 | 158.0 | 40.03 | 63.25 | load-only research estimate |

Both file headers lacked an activity date. The importer offers a date/time found in the filename for confirmation; it does not silently declare it the activity time. Temperature and distance without explicit units remain subject to unit review. The displayed model estimates are not a validation of those exports.

## What changed

- Content-aware importer retained and extended. Canonical fields, camel-case aliases, additional measurement types, source records, units and optional header-only AI mapping suggestions.
- Apple workout HR uses samples within the workout interval. Resting HR stays separate. GPX distance is calculated within each track segment, not across disconnected segments. TCX uses lap totals and available HR.
- Four independently evaluated input tiers replace the single all-input imputation path. No missing physiological values are filled in saved records. Unused/out-of-range measurements are disclosed.
- Multiple events stay attached to the upload and AI context. Supported 100 m/800 m events have learned model inputs. Unsupported events have no invented per-event numeric scores.
- Latest workout is assessed ahead of unrelated later measurement samples. All imported records stay in the per-file ledger.
- Same-file explicit model-version refresh retains ID/date and previous assessment; AI/coach-reviewed assessments cannot be overwritten.
- Current workflow snapshots are read alongside legacy Digital Twin history. Experimental outputs are not inserted as measured values into legacy sensor tables.
- Personal state estimate uses a fitted local-level state-space model and Gaussian update only after 14 earlier comparable observed days. Its uncertainty is conditional on modelling assumptions and is not clinical validation.
- Forecast consumers exclude incompatible model versions/input tiers/events and undated records. Simple preview slopes now use actual elapsed days. Other forecasting algorithms remain in place.
- AI generation uses a real API, with no fixed-rule fallback. Drafts and coach decisions remain linked to upload IDs. Notification role casing is compatible with existing records.
- Main navigation and page layouts retained; recovery indices shown on the proper percentage scale and missing recovery/load no longer displayed as zero in the home summary.

## Remaining evidence and service limits

- Research dataset labels; no verified prospective injury outcomes or injury horizon.
- Training-load definition is undocumented. Wearable load and HR-duration proxy are not established as equivalent to training load.
- Only 100 m and 800 m occur in training. Other events receive context-aware AI advice, not invented event-specific scores.
- Only three training dates; no claim of validated long-term forecasting or fitted personal physiology.
- Readiness, Twin Score and Health Index are engineered summaries, not separately validated outcomes.
- Holdout error summaries are not individual confidence intervals or clinical validation.
- No real Supabase migration, paid AI request, deployed Streamlit run, or Windows/Python 3.13 execution was performed here. The setup checks and local acceptance steps cover those deployment-specific prerequisites.
- FIT session parser was retained; a new physical FIT sample was not supplied for this run.
- No importer can understand every proprietary, encrypted, corrupted, image-only or arbitrary document format. Unrecognised structures need explicit mapping or a supported structured export.
- Recovery-only and load-only estimates are limited research views, not comprehensive athlete assessments. Wearable load compatibility remains unverified.
- Personal state smoothing is implemented, but the supplied three-day research dataset cannot validate long-term Bayesian forecasting. Temporal diagnostics in validation.json are separate from the athlete holdout and are explicitly limited.
- New labels/data are still required for calibrated injury probabilities and numerical coverage of additional sports/events. These cannot be manufactured by changing code.

## Reproduce the model comparison

After installing requirements.txt, run `python -m research_prediction.train` from the project root. This overwrites adaptive_models.joblib and validation.json in the working copy; it does not change Supabase. Normal app usage loads the included artifact and does not retrain.

## Files to replace/add

- `database/connection_request_repository.py` — replace
- `database/migrations/005_upload_review_workflow.sql` — unchanged setup migration
- `database/twin_repository.py` — replace
- `database/workflow_repository.py` — replace
- `digital_twin/forecasting_engine.py` — replace
- `ingestion/adaptive_table.py` — replace
- `ingestion/ai_mapping.py` — add
- `ingestion/workflow_loader.py` — replace
- `ingestion/xml_activity.py` — add
- `prediction/upload_processing.py` — replace
- `recommendation/llm_service.py` — replace
- `requirements-dev.txt` — add
- `requirements.txt` — replace
- `research_prediction/adaptive_models.joblib` — add
- `research_prediction/features.py` — replace
- `research_prediction/history.py` — add
- `research_prediction/longitudinal.py` — add
- `research_prediction/predict.py` — replace
- `research_prediction/train.py` — replace
- `research_prediction/validation.json` — replace
- `tests/test_adaptive_v2.py` — add
- `tests/test_daily_summary_upload.py` — replace
- `tests/test_research_prediction.py` — replace
- `tests/test_upload_review_workflow.py` — replace
- `ui/prediction_guidance.py` — replace
- `utils/check_workflow.py` — replace
- `views/athlete/digital_twin.py` — replace
- `views/athlete/history.py` — replace
- `views/athlete/import_review.py` — replace
- `views/athlete/predictions.py` — replace
- `views/athlete/simulation.py` — replace
- `views/athlete/upload.py` — replace
- `views/athlete_home.py` — replace
- `views/forecasting_page.py` — replace
