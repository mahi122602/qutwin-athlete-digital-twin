# Evidence and remaining research

This update forecasts saved research indices; it does not establish physiological or clinical validity.
There is no evidence supporting a 99% accuracy claim. Continuous fatigue/readiness scores are assessed
in index points using MAE/RMSE, not a generic percentage accuracy.

The implementation follows chronological, multi-horizon evaluation principles described in:
https://otexts.com/fpp3/tscv.html

For a defensible injury model, collect verified injury outcomes with dates, athlete exposure,
a specified prediction horizon, pre-outcome features, and sufficient injury events. Evaluate on
athletes and future time periods excluded from model development. Class imbalance means overall
accuracy alone cannot establish utility. Report sensitivity, precision, calibration and uncertainty
against a baseline before using any probabilities in the athlete interface.

Next empirical milestone: benchmark this implementation with real longitudinal athlete data.
Record score provenance, missingness, duplicate sessions, model versions, daily aggregation policy
and individual sport context. Comparing forecasts of model-generated scores only measures how well
the scores are extrapolated, not whether the original scores describe health accurately.

Interval coverage here is empirical and can fail under changing training regimes or sensor/model
changes. There is no causal response model for changing a training plan and no validated menstrual
cycle adjustment. Keep coach review and clearly distinguish recorded observations from forecasts.
