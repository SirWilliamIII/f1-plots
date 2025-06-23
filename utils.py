def classify_moment(
    t1: float,
    t2: float,
    b1: float,
    b2: float,
    v1: float,
    v2: float,
    r1: float = 0,
    r2: float = 0,
    prev_t1: float = None,
    prev_t2: float = None,
    prev_b1: float = None,
    prev_b2: float = None,
    prev_v1: float = None,
    prev_v2: float = None,
    prev_r1: float = None,
    prev_r2: float = None,
    session_type: str = "Q"  # ✅ NEW: Add session context
) -> str:
    """
    Classify racing moments where one driver gains an advantage over another.

    Parameters:
    - session_type: "Q" for Qualifying, "R" for Race, affects which moments are relevant
    """

    # Add safety check at the start
    if r1 == 0 and r2 == 0:
        pass

    throttle_diff = t1 - t2
    brake_diff = b1 - b2
    speed_diff = v1 - v2
    rpm_diff = r1 - r2

    # Calculate deltas if previous values exist
    if all(x is not None for x in [prev_t1, prev_t2, prev_b1, prev_b2, prev_v1, prev_v2, prev_r1, prev_r2]):
        t1_delta = t1 - prev_t1
        t2_delta = t2 - prev_t2
        b1_delta = b1 - prev_b1
        b2_delta = b2 - prev_b2
        v1_delta = v1 - prev_v1
        v2_delta = v2 - prev_v2
        r1_delta = r1 - prev_r1
        r2_delta = r2 - prev_r2
    else:
        t1_delta = t2_delta = b1_delta = b2_delta = v1_delta = v2_delta = r1_delta = r2_delta = 0

    # ===== QUALIFYING-SPECIFIC MOMENTS =====

    # 1. Gear selection advantage (lower gear = higher RPM = better acceleration)
    if abs(speed_diff) < 5 and abs(rpm_diff) > 1000 and t1 > 50 and t2 > 50:
        return "Better gear selection"

    # 2. Short-shifting detection (RPM drop without speed loss)
    if prev_r1 is not None and prev_r2 is not None:
        if (r1 < prev_r1 - 2000 and v1 >= prev_v1 - 2) and not (r2 < prev_r2 - 2000):
            return "Short-shifting technique"
        if (r2 < prev_r2 - 2000 and v2 >= prev_v2 - 2) and not (r1 < prev_r1 - 2000):
            return "Short-shifting technique"

    # 3. Power band optimization
    optimal_rpm_min = 10500
    optimal_rpm_max = 11500
    d1_in_powerband = optimal_rpm_min <= r1 <= optimal_rpm_max
    d2_in_powerband = optimal_rpm_min <= r2 <= optimal_rpm_max

    if (d1_in_powerband and not d2_in_powerband) or (d2_in_powerband and not d1_in_powerband):
        if t1 > 80 and t2 > 80:
            return "Better power band usage"

    # 4. Earlier throttle application (rising edge detection)
    if prev_t1 is not None and prev_t2 is not None:
        if (t1 > 20 and prev_t1 < 10) and (t2 < 10):
            return "Earlier throttle application"
        if (t2 > 20 and prev_t2 < 10) and (t1 < 10):
            return "Earlier throttle application"

    # 5. Trail braking technique
    if b1 > 0.1 and b2 > 0.1:  # Both braking
        if abs(speed_diff) > 3 and abs(brake_diff) > 0.1:
            if (b1 < b2 and v1 > v2) or (b2 < b1 and v2 > v1):
                return "Superior trail braking"

    # 6. Later braking point
    if prev_b1 is not None and prev_b2 is not None:
        if (b1 < 0.1 and prev_b1 > 0.2) and (b2 > 0.2):
            return "Later braking point"
        if (b2 < 0.1 and prev_b2 > 0.2) and (b1 > 0.2):
            return "Later braking point"

    # 7. Higher apex/mid-corner speed
    if (b1 < 0.05 and b2 < 0.05) and (t1 < 15 and t2 < 15):
        if abs(speed_diff) > 5:
            return "Higher apex speed"
        elif abs(speed_diff) > 2:
            return "Higher mid-corner speed"

    # 8. Better corner exit technique
    if (t1 > 50 and t2 < 30 and v1 > v2 + 5) or (t2 > 50 and t1 < 30 and v2 > v1 + 5):
        return "Superior corner exit"
    elif (t1 > 30 and t2 < 15 and v1 > v2 + 3) or (t2 > 30 and t1 < 15 and v2 > v1 + 3):
        return "Better exit technique"

    # 9. Smoother driving technique
    if prev_t1 is not None and abs(t1_delta) < abs(t2_delta) - 10:
        if v1 >= v2 - 1:
            return "Smoother throttle control"

    # 10. Car control / correction
    if (t1 < 5 or t2 < 5) and (b1 < 0.05 and b2 < 0.05):
        if max(v1, v2) > 80:
            return "Car control correction"
        elif v1_delta < -5 or v2_delta < -5:
            return "Stability correction"

    # 11. Driving mistake detection
    if prev_v1 is not None and prev_v2 is not None:
        if (v1 < prev_v1 - 10) or (v2 < prev_v2 - 10):
            if b1 > 0.5 or b2 > 0.5:
                return "Lock-up or major mistake"
            else:
                return "Possible mistake or wide line"

    # 12. Brake efficiency
    if b1 > 0.1 and b2 > 0.1 and abs(brake_diff) > 0.15:
        if (b1 < b2 and v1 > v2 - 2) or (b2 < b1 and v2 > v1 - 2):
            return "More efficient braking"

    # 13. Straight-line performance (car advantage)
    if t1 > 95 and t2 > 95:  # Both full throttle
        if abs(speed_diff) > 5:
            return "Car performance advantage"

    # ===== RACE-SPECIFIC MOMENTS (only if session_type == "R") =====
    if session_type == "R":
        # 14. Slipstreaming/drafting advantage
        if prev_v1 is not None and prev_v2 is not None:
            if (v1_delta > 5 and v2_delta < 2) or (v2_delta > 5 and v1_delta < 2):
                if abs(t1 - t2) < 10:
                    return "Slipstream advantage"

        # 15. Overtake detection
        if prev_v1 is not None and prev_v2 is not None:
            if (prev_v1 < prev_v2 - 2 and v1 > v2 + 2) or (prev_v2 < prev_v1 - 2 and v2 > v1 + 2):
                return "Overtake completed"

    # ===== GENERAL PERFORMANCE DIFFERENCES =====

    # 16. Significant performance gaps
    if abs(speed_diff) > 10:
        return "Major performance difference"
    elif abs(speed_diff) > 5:
        return "Significant speed difference"
    elif abs(speed_diff) > 3:
        return "Notable speed difference"
    elif abs(speed_diff) > 1.5:
        return "Minor performance gap"

    # 17. Large input differences
    if abs(throttle_diff) > 50:
        return "Major throttle difference"
    elif abs(brake_diff) > 0.3:
        return "Significant brake difference"

    # Default
    return "Minor technique difference"

def extract_telemetry_context(session, driver1, driver2):
    """Extract telemetry context for the AI model, focusing on key performance metrics.

    Args:
        session: FastF1 session object
        driver1: First driver abbreviation
        driver2: Second driver abbreviation

    Returns:
        dict: Context containing race info, driver data, and performance metrics
    """
    # Extract lap data
    drv1_laps = session.laps.pick_driver(driver1)
    drv2_laps = session.laps.pick_driver(driver2)

    # Get fastest laps
    drv1_fastest = drv1_laps.pick_fastest()
    drv2_fastest = drv2_laps.pick_fastest()

    # Get telemetry data
    drv1_tel = drv1_fastest.get_telemetry()
    drv2_tel = drv2_fastest.get_telemetry()

    # Get driver info
    drv1_info = session.get_driver(driver1)
    drv2_info = session.get_driver(driver2)

    # Build context dictionary with all relevant data
    try:
        circuit_info = session.get_circuit_info()
        track_length = float(circuit_info.CircuitLength) if hasattr(circuit_info, 'CircuitLength') else 0.0
    except:
        track_length = 0.0

    context = {
        "race_info": {
            "year": session.event.year,
            "race_name": session.event['EventName'],
            "session_type": "Race" if session.name == "R" else "Qualifying",
            "track_length": track_length
        },
        "driver1": {
            "name": driver1,
            "full_name": drv1_info['BroadcastName'],
            "lap_time": float(drv1_fastest['LapTime'].total_seconds()),
            "max_speed": float(drv1_tel['Speed'].max()),
            "avg_throttle": float(drv1_tel['Throttle'].mean())
        },
        "driver2": {
            "name": driver2,
            "full_name": drv2_info['BroadcastName'],
            "lap_time": float(drv2_fastest['LapTime'].total_seconds()),
            "max_speed": float(drv2_tel['Speed'].max()),
            "avg_throttle": float(drv2_tel['Throttle'].mean())
        }
    }

    # Add comparison data
    faster_time = min(context["driver1"]["lap_time"], context["driver2"]["lap_time"])
    context["comparison"] = {
        "faster_driver": driver1 if context["driver1"]["lap_time"] == faster_time else driver2,
        "lap_time_delta": abs(context["driver1"]["lap_time"] - context["driver2"]["lap_time"]),
        "speed_difference": abs(context["driver1"]["max_speed"] - context["driver2"]["max_speed"])
    }

    # Add sector analysis
    sectors = []
    for i in range(1, 4):
        s1_time = float(drv1_fastest[f'Sector{i}Time'].total_seconds())
        s2_time = float(drv2_fastest[f'Sector{i}Time'].total_seconds())
        sectors.append({
            "sector": i,
            "driver1_time": s1_time,
            "driver2_time": s2_time,
            "delta": abs(s1_time - s2_time),
            "faster_driver": driver1 if s1_time < s2_time else driver2
        })
    context["sectors"] = sectors

    return context
