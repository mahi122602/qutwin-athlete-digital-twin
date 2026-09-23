# QUTwin upload prediction correction

This patch adds an **experimental research estimate** path. It does not establish clinical accuracy, support arbitrary unrelated files, or turn imputed measurements into observed facts.

## What caused the empty output

The previous upload workflow required all eight physiological inputs, plus an activity date, before calling its model. Wearable session exports commonly omit sleep, hydration, recovery and injury history. Saving a file therefore succeeded while prediction was blocked. AI recommendation generation was independently blocked by missing API configuration.

## Changes

- Reuse the content-aware importer and mapping/unit review for supported CSV, Excel, JSON, FIT, GPX, TCX, XML and ZIP export structures. Unknown schemas need mapping; malformed or unsupported content is reported explicitly.
- Derive duration, pace, speed and a documented QUTwin workload estimate where measurements permit. Prior workload comparisons use earlier dated observations only. No invented activity dates or filled calendar days.
- Use a separately fitted Ridge multiple-regression fatigue model and Random Forest category model. Numeric scaling, training-only median imputation and missingness indicators are part of the fitted pipelines. Recorded measurements remain untouched.
- Encode event type during research-model fitting. The supplied dataset supports **100 m and 800 m only**. Other selected events receive generic estimates with an explicit unsupported-event flag. Multiple selection does not multiply the workload or prove multiple events were performed.
- Save one assessment for the latest dated activity in each file; if all dates are unknown, assess its final imported record. Retain all imported records. This avoids repeatedly running models on every sensor sample.
- Show feature provenance, model-only imputations, research labels, limitations and internal validation results.
- Recalculate an existing observations-only upload while preserving its database ID and saved date. Files with existing predictions or AI/coach review cannot be overwritten by that action.
- Generate an actual AI draft using the configured API; there is no rule-based text pretending to be AI. Drafts and coach approval/modification/rejection stay linked to the upload. AI failure does not erase the saved upload.
- History uses one row per saved file, immediate database reads, latest snapshot and recommendation, and four charts in two rows. Experimental values are labelled.

## Mapping to Concepts(2).docx

| Concept | Treatment in this patch |
|---|---|
| Ingestion, validation, preprocessing | Content detection, mapping, units, bounds and clear failure reports |
| Feature engineering | Observed/derived feature provenance; personal workload baseline where dated history exists |
| Multiple regression / least squares | Ridge regression: penalised least squares, not a claim of unregularised OLS |
| Random Forest / CART / ensemble | Research risk-category classifier, with weak validation disclosed |
| Scaling and missing values | Fitted preprocessing pipeline; training medians and indicators |
| Cross-validation / leakage prevention | Five folds grouped by athlete, preprocessing fitted within each training fold |
| MAE, RMSE, R², F1 | Stored in research_prediction/validation.json |
| Target engineering | Existing dataset labels retained; their origin is not independently verified |
| Readiness, Twin Score, Health Index | Engineered composite indices, not independently validated prediction targets |
| Temporal trends | Prior observed workload comparison; upload-history charts, no invented daily observations |
| Bayesian/state-space/forecasting/what-if | Existing modules retained. This new partial-data path does not claim calibrated Bayesian or temporal predictions |
| Recommendations | Real API-generated draft followed by authorised coach review; latest request supersedes the document's legacy rule-based recommendation description |
| Persistence | Atomic per-file ledger, duplicate protection and retained feedback |

## Validation limits that matter

The supplied dataset has 999 rows across 333 athletes. Its training-load definition is undocumented; the derived wearable workload may not be equivalent. Training heart-rate measurement context and injury-history coding are also unclear, so those ambiguous fields are excluded from this research model. Exercise heart rate can still contribute to the explicitly described workload estimate.

Five-fold athlete-held-out evaluation gave approximately:

| Pattern | Fatigue MAE | Fatigue R² | Risk balanced accuracy |
|---|---:|---:|---:|
| Complete research inputs | 4.88 | 0.734 | 44.7% |
| Training load plus event only | 7.06 | 0.413 | 42.1% |

**The injury classifier is weak. Its category must not be presented as an accurate probability, diagnosis or training clearance.** These are internal dataset results, not independent wearable validation. Partial-input benchmarks do not validate every possible missing-data pattern. Error summaries are not calibrated individual confidence intervals. An input outside the training range yields feature analysis without a fabricated score.

The historical Bayesian, forecasting and dashboard modules are not deleted. Experimental upload snapshots are deliberately not inserted into the legacy digital-athlete-state table. Consequently those older dashboard/forecasting pages do not automatically consume these new experimental estimates. Prediction, upload History and the linked recommendation workflow do.

## Installation

1. Back up the current project. Copy the **contents of replacement_files** into the project directory containing app.py, merging folders and replacing matching files. Do not delete the rest of the project.
2. Stop the running Streamlit server with Ctrl+C. In that project directory run:

```powershell
python -m pip install -r requirements.txt
python -m utils.check_workflow
python -m streamlit run app.py
```

The workflow checker checks/setup migration 005 using your existing database configuration. If the database role cannot apply migrations, the included SQL must be applied by the database owner. No new database credentials are provided or required by this patch.

3. For the already-saved file in your screenshot: open Prediction, select the file, then click **Recalculate this saved upload**. New uploads are processed automatically.
4. For actual AI text, enter an API key and accessible model ID in **Configure AI for this session**, then click **Generate / retry AI recommendation**. Or set OPENAI_API_KEY and QUTWIN_AI_MODEL in your existing application secrets. Never commit real keys. Session settings are temporary; API charges belong to the configured account.
5. Existing coach assignment is required to route a generated draft to a coach. Coach decisions appear against that same upload in Prediction and History and create athlete notifications.

This patch has not been run against your live Supabase database or a paid AI endpoint. Automated database tests use an isolated adapter; API tests use controlled responses.

## Reproduce the research experiment

```powershell
python -m research_prediction.train
```

This uses the existing data/athlete_training_dataset.csv and writes only the separate research model and its validation report. The bundled artifact must be used with scikit-learn 1.6.1 as pinned in requirements.txt.
