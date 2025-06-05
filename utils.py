def classify_moment(
    t1: float, t2: float, b1: float, b2: float, v1: float, v2: float,
    prev_t1: float = None, prev_t2: float = None, prev_b1: float = None, prev_b2: float = None
) -> str:
    throttle_diff = t1 - t2
    brake_diff = b1 - b2
    speed_diff = v1 - v2

    # 1. Earlier throttle ON (check for rising edge, not just absolute value)
    if prev_t1 is not None and prev_t2 is not None:
        if (t1 > 20 and prev_t1 < 10) and (t2 < 10):
            return "Earlier throttle"
        if (t2 > 20 and prev_t2 < 10) and (t1 < 10):
            return "Earlier throttle"
    # 2. Later braking (check for brake release point)
    if prev_b1 is not None and prev_b2 is not None:
        if (b1 < 0.1 and prev_b1 > 0.2) and (b2 > 0.2):
            return "Later braking"
        if (b2 < 0.1 and prev_b2 > 0.2) and (b1 > 0.2):
            return "Later braking"
    # 3. Higher mid-corner speed (sustained, even if small)
    if (b1 < 0.05 and b2 < 0.05) and (t1 < 10 and t2 < 10) and abs(speed_diff) > 2:
        return "Higher mid‑corner speed"
    # 4. Better exit (throttle advantage leads to speed gain)
    if (t1 > 30 and t2 < 15 and v1 > v2 + 3):
        return "Better exit"
    if (t2 > 30 and t1 < 15 and v2 > v1 + 3):
        return "Better exit"
    # 5. Correction for over/under-steer (low throttle+brake, speed drop)
    if (t1 < 5 or t2 < 5) and (b1 < 0.05 and b2 < 0.05) and (max(v1, v2) > 80):
        return "Correction for over/under‑steer"
    # 6. Large, sustained speed delta (big advantage)
    if abs(speed_diff) > 5:
        return "Big speed advantage"
    # 7. Sudden, large throttle or brake difference
    if abs(throttle_diff) > 40:
        return "Big throttle difference"
    if abs(brake_diff) > 0.7:
        return "Big brake difference"
    # 8. Sharp speed drop (possible mistake)
    if prev_t1 is not None and prev_t2 is not None and prev_b1 is not None and prev_b2 is not None:
        if (v1 < prev_t1 - 10) or (v2 < prev_t2 - 10):
            return "Possible mistake or off-track"
    # 9. Overtake-like event (speed crossover and sustained lead)
    if (v1 > v2 + 2 and speed_diff > 0 and prev_t1 is not None and prev_t2 is not None and prev_t1 < prev_t2):
        return "Overtake or pass"
    if (v2 > v1 + 2 and speed_diff < 0 and prev_t1 is not None and prev_t2 is not None and prev_t2 < prev_t1):
        return "Overtake or pass"
    # 10. Micro-momentum shift (catch all, small but relevant)
    if abs(speed_diff) > 1.5:
        return "Micro momentum shift"
    return "Momentum shift"