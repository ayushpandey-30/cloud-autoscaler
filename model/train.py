import sqlite3

import joblib
import matplotlib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error

matplotlib.use("Agg")                 # draw graphs to files, no window needed
import matplotlib.pyplot as plt

PATTERNS = ["steady", "ramp", "spike", "wave"]
HORIZON = 6      # predict 6 readings ahead = 30 seconds
LAGS = 8         # use the last 8 readings (40 seconds) as inputs


def load(name):
    conn = sqlite3.connect(f"data/{name}.db")
    df = pd.read_sql("SELECT * FROM metrics ORDER BY ts", conn)
    conn.close()
    # cut off the idle tail recorded after the load generator stopped
    last = df.index[df["rps"] > 0].max()
    return df.loc[:last].reset_index(drop=True)


def make_features(df):
    out = pd.DataFrame()
    for k in range(LAGS):                         # lag0 = now, lag1 = 5 s ago...
        out[f"rps_lag{k}"] = df["rps"].shift(k)
    out["trend_5s"] = out["rps_lag0"] - out["rps_lag1"]      # recent change
    out["trend_15s"] = out["rps_lag0"] - out["rps_lag3"]
    out["trend_35s"] = out["rps_lag0"] - out["rps_lag7"]
    out["cpu"] = df["cpu"]
    out["target"] = df["rps"].shift(-HORIZON)     # actual rate 30 s ahead
    out["delta"] = out["target"] - out["rps_lag0"]   # change we train on
    return out.dropna().reset_index(drop=True)


data = {}
for name in PATTERNS:
    data[name] = make_features(load(name))
    print(f"{name}: {len(data[name])} usable rows")

FEATURES = [c for c in data["steady"].columns if c not in ("target", "delta")]
LAG_COLS = [f"rps_lag{k}" for k in range(4)]


def new_models():
    return {
        "Linear (change)": Ridge(alpha=1.0),
        "Random forest (change)": RandomForestRegressor(
            n_estimators=100, max_depth=5, min_samples_leaf=3,
            random_state=42),
    }


# Leave-one-pattern-out test: train on three patterns, test on the fourth.
rows = []
forest_predictions = {}
for test_name in PATTERNS:
    train = pd.concat([data[n] for n in PATTERNS if n != test_name])
    test = data[test_name]
    y = test["target"]

    row = {"test pattern": test_name}
    row["Baseline: last value"] = mean_absolute_error(y, test["rps_lag0"])
    row["Baseline: avg of last 4"] = mean_absolute_error(
        y, test[LAG_COLS].mean(axis=1))
    for model_name, model in new_models().items():
        model.fit(train[FEATURES], train["delta"])        # learn the CHANGE
        pred = (test["rps_lag0"] + model.predict(test[FEATURES])).clip(lower=0)
        row[model_name] = mean_absolute_error(y, pred)
        if model_name.startswith("Random forest"):
            forest_predictions[test_name] = pred.values
    rows.append(row)

results = pd.DataFrame(rows).round(2)
print("\nMean absolute error in requests/sec (lower is better):")
print(results.to_string(index=False))

# Graph: predicted vs actual for each pattern
fig, axes = plt.subplots(2, 2, figsize=(11, 7))
for ax, name in zip(axes.flat, PATTERNS):
    ax.plot(data[name]["target"].values, label="actual")
    ax.plot(forest_predictions[name], label="predicted (30s ahead)")
    ax.set_title(name)
    ax.set_xlabel("reading number (5 s each)")
    ax.set_ylabel("requests/sec")
    ax.legend()
plt.tight_layout()
plt.savefig("docs/predictions.png", dpi=120)
print("\nSaved graph: docs/predictions.png")

# Final model: train on ALL patterns and save it for the scaler to use
all_data = pd.concat(data.values())
final = new_models()["Random forest (change)"]
final.fit(all_data[FEATURES], all_data["delta"])
joblib.dump({"model": final, "features": FEATURES, "predicts": "delta"},
            "model/model.joblib")
print("Saved model: model/model.joblib")