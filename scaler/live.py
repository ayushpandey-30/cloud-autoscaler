import argparse
import csv
import subprocess
import time

import psutil
import requests

from engine import predictive_decision, threshold_decision
from predictor import predict_rps

STATUS_URL = "http://localhost:8080/nginx_status"
INTERVAL = 5                  # seconds between readings
NETWORK = "scalenet"
IMAGE = "autoscaler-app"


def docker(*args):
    result = subprocess.run(["docker", *args], capture_output=True, text=True)
    return result.stdout.strip()


def running_web():
    out = docker("ps", "--filter", "name=^web", "--format", "{{.Names}}")
    return [n for n in out.splitlines() if n]


def start_one():
    name = f"web{int(time.time())}"
    docker("run", "-d", "--name", name, "--network", NETWORK,
           "--network-alias", "web", "--cpus", "0.5", IMAGE)
    print(f"      -> started container {name}")


def stop_one():
    names = running_web()
    if names:
        docker("rm", "-f", names[0])          # names[0] is the newest
        print(f"      -> removed container {names[0]}")


def total_requests():
    # nginx stub_status: 3rd line is "accepts handled requests"
    text = requests.get(STATUS_URL, timeout=2).text
    return int(text.splitlines()[2].split()[2])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--active", action="store_true",
                        help="really start/stop containers (default: advice only)")
    parser.add_argument("--strategy", choices=["predictive", "threshold"],
                        default="predictive")
    args = parser.parse_args()

    mode = "ACTIVE" if args.active else "RECOMMEND ONLY"
    print(f"Scaler running: mode={mode}, strategy={args.strategy}")
    print("Press Ctrl+C to stop.\n")

    if args.active and not running_web():
        start_one()
    virtual = max(1, len(running_web()))      # instance count in recommend mode

    log_name = f"data/live_{args.strategy}_{'active' if args.active else 'advice'}.csv"
    log = open(log_name, "w", newline="")
    writer = csv.writer(log)
    writer.writerow(["t", "rps", "predicted", "instances", "action"])

    history = []
    last_total = None
    last_action_at = -999.0
    start = time.time()

    while True:
        try:
            total = total_requests()
        except Exception:
            print("Cannot reach the load balancer at", STATUS_URL)
            time.sleep(INTERVAL)
            continue
        cpu = psutil.cpu_percent(interval=1)

        if last_total is None:
            last_total = total
            time.sleep(INTERVAL - 1)
            continue

        # subtract 1: our own status request is counted by nginx
        rps = max(0.0, (total - last_total - 1) / INTERVAL)
        last_total = total
        history.append(rps)

        now = time.time()
        since = now - last_action_at
        current = max(1, len(running_web())) if args.active else virtual

        if len(history) < 8:
            print(f"warming up ({len(history)}/8 readings)  rps={rps:.1f}")
            time.sleep(INTERVAL - 1)
            continue

        predicted = float("nan")
        if args.strategy == "threshold":
            new, action, reason = threshold_decision(rps, current, since)
        else:
            try:
                predicted = predict_rps(history, cpu)
                new, action, reason = predictive_decision(predicted, current, since)
            except Exception:                 # fallback if prediction fails
                new, action, reason = threshold_decision(rps, current, since)
                reason = "FALLBACK: " + reason

        if action != "hold":
            last_action_at = now
            if args.active:
                for _ in range(max(0, new - current)):
                    start_one()
                for _ in range(max(0, current - new)):
                    stop_one()
            virtual = new

        print(f"t={now - start:5.0f}s  rps={rps:5.1f}  predicted={predicted:5.1f}  "
              f"instances={new}  {action:10s} {reason}")
        writer.writerow([round(now - start), round(rps, 1),
                         round(predicted, 1), new, action])
        log.flush()
        time.sleep(INTERVAL - 1)


main()