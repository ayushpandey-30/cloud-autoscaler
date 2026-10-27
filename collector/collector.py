import os
import sqlite3
import time

import psutil
import requests

DB_PATH = "data/metrics.db"
APP_URL = "http://localhost:5000/metrics"
INTERVAL = 5   # seconds between readings

os.makedirs("data", exist_ok=True)   # make the data folder if it's missing
conn = sqlite3.connect(DB_PATH)
conn.execute(
    "CREATE TABLE IF NOT EXISTS metrics "
    "(ts REAL, cpu REAL, mem REAL, rps REAL)"
)

last_total = None

print("Collector started. Press Ctrl+C to stop.")
while True:
    cpu = psutil.cpu_percent(interval=1)      # CPU %, measured over 1 second
    mem = psutil.virtual_memory().percent     # memory %

    try:
        total = requests.get(APP_URL, timeout=2).json()["requests"]
    except requests.RequestException:
        total = last_total if last_total is not None else 0

    # requests per second = new requests since last reading / time passed
    rps = 0 if last_total is None else (total - last_total) / INTERVAL
    last_total = total

    conn.execute(
        "INSERT INTO metrics VALUES (?, ?, ?, ?)",
        (time.time(), cpu, mem, rps),
    )
    conn.commit()
    print(f"cpu={cpu}%  mem={mem}%  rps={rps:.1f}")

    time.sleep(INTERVAL - 1)