import sqlite3
import sys

import pandas as pd

from engine import predictive_decision, threshold_decision
from predictor import predict_rps

name = sys.argv[1] if len(sys.argv) > 1 else "spike"

conn = sqlite3.connect(f"data/{name}.db")
df = pd.read_sql("SELECT * FROM metrics ORDER BY ts", conn)
conn.close()
last = df.index[df["rps"] > 0].max()
df = df.loc[:last].reset_index(drop=True)      # drop idle tail

instances = 1
last_action_at = -999
actions = 0
instance_total = 0

for i in range(8, len(df)):
    now = i * 5
    history = df["rps"].iloc[: i + 1].tolist()
    since = now - last_action_at
    try:
        predicted = predict_rps(history, df["cpu"].iloc[i])
        new, action, reason = predictive_decision(predicted, instances, since)
    except Exception:                           # fallback if prediction fails
        predicted = float("nan")
        new, action, reason = threshold_decision(history[-1], instances, since)
        reason = "FALLBACK: " + reason
    if action != "hold":
        last_action_at = now
        actions += 1
    instances = new
    instance_total += instances
    print(f"t={now:4d}s  rps={df['rps'].iloc[i]:5.1f}  "
          f"predicted={predicted:5.1f}  instances={instances}  "
          f"{action:10s} {reason}")

steps = len(df) - 8
print(f"\nPattern: {name}")
print(f"Scaling actions: {actions}")
print(f"Average instances: {instance_total / steps:.2f}")