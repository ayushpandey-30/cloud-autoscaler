import csv
import glob
import os
import subprocess

from flask import Flask, jsonify, send_from_directory

app = Flask(__name__)
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")


def latest_log():
    files = glob.glob(os.path.join(DATA, "live_*.csv"))
    return max(files, key=os.path.getmtime) if files else None


def number(text):
    try:
        v = float(text)
        return None if v != v else v          # nan -> None
    except ValueError:
        return None


def running_containers():
    try:
        out = subprocess.run(
            ["docker", "ps", "--filter", "name=^web", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=5).stdout
        return len([n for n in out.splitlines() if n])
    except Exception:
        return None


@app.route("/")
def index():
    return send_from_directory(HERE, "index.html")


@app.route("/api/data")
def api_data():
    path = latest_log()
    rows = []
    if path:
        with open(path) as f:
            for r in csv.DictReader(f):
                rows.append({
                    "t": number(r["t"]),
                    "rps": number(r["rps"]),
                    "predicted": number(r["predicted"]),
                    "instances": number(r["instances"]),
                    "action": r["action"],
                })
    return jsonify({
        "source": os.path.basename(path) if path else None,
        "rows": rows[-120:],                  # last 10 minutes
        "containers": running_containers(),
    })


if __name__ == "__main__":
    app.run(port=5050)