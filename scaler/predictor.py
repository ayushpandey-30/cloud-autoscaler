import joblib
import pandas as pd

_bundle = joblib.load("model/model.joblib")
_model = _bundle["model"]
_features = _bundle["features"]


def predict_rps(rps_history, cpu):
    """rps_history: readings oldest to newest (at least 8). Returns the
    predicted requests/sec 30 seconds from now."""
    h = rps_history[-8:][::-1]            # h[0] = now, h[1] = 5s ago, ...
    row = {f"rps_lag{k}": h[k] for k in range(8)}
    row["trend_5s"] = h[0] - h[1]
    row["trend_15s"] = h[0] - h[3]
    row["trend_35s"] = h[0] - h[7]
    row["cpu"] = cpu
    delta = _model.predict(pd.DataFrame([row])[_features])[0]
    return max(0.0, h[0] + delta)         # the model predicts the CHANGE