# Decisions log

## Prediction model (Phase 3)
- Predicts requests/sec 30 seconds ahead (6 readings x 5 s), using the last
  8 readings, trend features and CPU.
- Tested leave-one-pattern-out: train on 3 traffic patterns, test on the 4th.
- Result: the "last value" baseline had the lowest error on steady, ramp and
  spike. The ML models were marginally better only on wave (17.52 vs 17.86).
- Reasons: small dataset (60-78 rows per pattern), unseen test patterns, and
  spikes cannot be predicted from past values.
- Decision: keep the model, but protect the scaler with min/max limits,
  a cooldown and a fallback to a threshold rule. Judge the model by scaling
  outcomes (Phase 7), not only by prediction error.