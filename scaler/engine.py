import math

CAPACITY = 20         # requests/sec one instance handles (simulated number)
TARGET_UTIL = 0.6     # aim to keep each instance 60% busy
MIN_INSTANCES = 1
MAX_INSTANCES = 5
COOLDOWN = 30         # seconds to wait after any scaling action


def clamp(n):
    return max(MIN_INSTANCES, min(MAX_INSTANCES, n))


def predictive_decision(predicted_rps, current, seconds_since_action):
    """Decide using the model's prediction of future load."""
    needed = clamp(math.ceil(predicted_rps / (CAPACITY * TARGET_UTIL)))
    if needed == current:
        return current, "hold", "capacity matches predicted load"
    if seconds_since_action < COOLDOWN:
        return current, "hold", "cooldown active"
    action = "scale_up" if needed > current else "scale_down"
    return needed, action, f"predicted {predicted_rps:.1f} rps needs {needed}"


def threshold_decision(current_rps, current, seconds_since_action):
    """Simple reactive rule: our baseline, and the fallback if prediction fails."""
    utilisation = current_rps / (CAPACITY * current)
    if seconds_since_action < COOLDOWN:
        return current, "hold", "cooldown active"
    if utilisation > 0.8 and current < MAX_INSTANCES:
        return current + 1, "scale_up", f"utilisation {utilisation:.0%} > 80%"
    if utilisation < 0.3 and current > MIN_INSTANCES:
        return current - 1, "scale_down", f"utilisation {utilisation:.0%} < 30%"
    return current, "hold", "within thresholds"