import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import requests

URL = sys.argv[3] if len(sys.argv) > 3 else "http://localhost:5000/"


# Each pattern takes f (how far through the run we are, from 0.0 to 1.0)
# and returns how many requests per second to send.
def steady(f):
    return 8

def ramp(f):                      # gradual rise from 2 to 30 requests/sec
    return 2 + 28 * f

def spike(f):                     # quiet, then a sudden burst in the middle
    return 30 if 0.4 <= f < 0.6 else 3

def wave(f):                      # daily-style up and down, 4 cycles
    return 15 + 12 * math.sin(2 * math.pi * f * 4)


PATTERNS = {"steady": steady, "ramp": ramp, "spike": spike, "wave": wave}


def hit():
    try:
        requests.get(URL, timeout=10)
    except requests.RequestException:
        pass


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "steady"
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else 600   # seconds
    if name not in PATTERNS:
        print("Choose one of:", ", ".join(PATTERNS))
        return

    pattern = PATTERNS[name]
    pool = ThreadPoolExecutor(max_workers=60)
    print(f"Running '{name}' pattern for {duration} seconds...")

    start = time.time()
    for second in range(duration):
        rate = int(pattern(second / duration))
        for _ in range(rate):
            pool.submit(hit)                      # send one request
        if second % 10 == 0:
            print(f"t={second}s  sending {rate} requests/sec")
        # wait until the next whole second
        time.sleep(max(0, start + second + 1 - time.time()))

    pool.shutdown(wait=True)
    print("Done.")


main()