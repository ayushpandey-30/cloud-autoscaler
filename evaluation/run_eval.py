import csv
import math
import statistics
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import matplotlib
import requests

matplotlib.use("Agg")
import matplotlib.pyplot as plt

URL = "http://localhost:8080/"
SLOW = 1.0                      # a request slower than 1 second = "overloaded"
STRATEGIES = ["none", "threshold", "predictive"]

pattern_name = sys.argv[1] if len(sys.argv) > 1 else "spike"
DURATION = int(sys.argv[2]) if len(sys.argv) > 2 else 240

PATTERNS = {
    "steady": lambda f: 8,
    "ramp": lambda f: 2 + 28 * f,
    "spike": lambda f: 30 if 0.4 <= f < 0.6 else 3,
    "wave": lambda f: 15 + 12 * math.sin(2 * math.pi * f * 4),
}
if pattern_name not in PATTERNS:
    sys.exit("Choose one of: " + ", ".join(PATTERNS))


def docker(*args):
    return subprocess.run(["docker", *args], capture_output=True,
                          text=True).stdout.strip()


def web_count():
    out = docker("ps", "--filter", "name=^web", "--format", "{{.Names}}")
    return len([n for n in out.splitlines() if n])


def reset():
    """Back to the starting state: load balancer + exactly one app container."""
    for cid in docker("ps", "-aq", "--filter", "name=^web").split():
        docker("rm", "-f", cid)
    docker("start", "lb")
    docker("run", "-d", "--name", "web1", "--network", "scalenet",
           "--network-alias", "web", "--cpus", "0.5", "autoscaler-app")
    time.sleep(8)


def run_one(strategy):
    print(f"\n=== {strategy} on '{pattern_name}' ({DURATION}s) ===")
    reset()
    scaler = None
    if strategy != "none":
        scaler = subprocess.Popen(
            [sys.executable, "scaler/live.py", "--active", "--strategy", strategy],
            stdout=subprocess.DEVNULL)
        print("   waiting 50 s for the scaler to warm up...")
        time.sleep(50)

    results, samples = [], []
    stop = threading.Event()

    def hit(submitted):
        try:
            ok = requests.get(URL, timeout=10).status_code == 200
        except requests.RequestException:
            ok = False
        results.append((submitted - start, time.time() - submitted, ok))

    def sample():
        while not stop.is_set():
            samples.append((time.time() - start, web_count()))
            stop.wait(2)

    pool = ThreadPoolExecutor(max_workers=200)
    start = time.time()
    threading.Thread(target=sample, daemon=True).start()
    for second in range(DURATION):
        for _ in range(int(PATTERNS[pattern_name](second / DURATION))):
            pool.submit(hit, time.time())
        time.sleep(max(0, start + second + 1 - time.time()))
    pool.shutdown(wait=True)
    stop.set()
    if scaler:
        scaler.terminate()
        scaler.wait()

    good = sorted(lat for _, lat, ok in results if ok)
    slow = sum(1 for _, lat, ok in results if (not ok) or lat > SLOW)
    summary = {
        "strategy": strategy,
        "requests": len(results),
        "median_s": round(statistics.median(good), 3) if good else None,
        "p95_s": round(good[int(0.95 * (len(good) - 1))], 3) if good else None,
        "slow_or_failed_%": round(100 * slow / max(1, len(results)), 1),
        "avg_containers": round(statistics.mean(c for _, c in samples), 2),
        "max_containers": max(c for _, c in samples),
    }
    print("   ", summary)
    return summary, results, samples


def bucketed(res):
    buckets = {}
    for t, lat, _ in res:
        buckets.setdefault(int(t // 10) * 10, []).append(lat)
    xs = sorted(buckets)
    return xs, [statistics.mean(buckets[x]) for x in xs]


summaries, all_results, all_samples = [], {}, {}
for s in STRATEGIES:
    summary, res, smp = run_one(s)
    summaries.append(summary)
    all_results[s], all_samples[s] = res, smp
reset()                          # leave one clean container running

print("\nRESULTS for pattern:", pattern_name)
for row in summaries:
    print(row)

with open(f"docs/evaluation_{pattern_name}.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(summaries[0].keys()))
    writer.writeheader()
    writer.writerows(summaries)

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
for s in STRATEGIES:
    xs, ys = bucketed(all_results[s])
    ax1.plot(xs, ys, label=s)
    smp = all_samples[s]
    ax2.step([t for t, _ in smp], [c for _, c in smp], where="post", label=s)
ax1.axhline(SLOW, color="gray", linestyle=":")
ax1.set_ylabel("mean response time (s)")
ax1.set_title(f"Response time and containers: '{pattern_name}' traffic")
ax1.legend()
ax2.set_ylabel("containers running")
ax2.set_xlabel("seconds since traffic started")
ax2.legend()
plt.tight_layout()
plt.savefig(f"docs/evaluation_{pattern_name}.png", dpi=120)
print(f"\nSaved docs/evaluation_{pattern_name}.csv and .png")