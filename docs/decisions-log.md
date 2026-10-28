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

  ## Live scaler (Phase 5)
- Containers run behind an nginx load balancer on a Docker network; the
  scaler reads the request rate from nginx and starts/stops containers
  with the docker CLI.
- Default mode is recommend-only; --active switches on real scaling.
- Observed: on a 3 -> 30 rps spike the scaler jumped straight from 1 to 5
  instances, and on small prediction swings it added/removed an instance
  when the real load had barely moved.
- Capacity per instance (10 rps) is an assumed number. It should be
  calibrated by measuring how much load one 0.5-CPU container really handles.