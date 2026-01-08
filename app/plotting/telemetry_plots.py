"""
Telemetry Plot Generation

Handles creation of telemetry comparison plots with annotations.
"""

import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import numpy as np
import pandas as pd
import logging
import math
import time
from io import BytesIO
from fastf1 import plotting
from flask import session as flask_session
from utils import classify_moment, extract_telemetry_context
from app.services.context_service import store_telemetry_context


# ✅ FIXED: Removed global plot buffer to prevent cross-user data leaks
# Plot buffers are now stored per-session in Flask sessions


def safe_int(val, default=0):
    """Safely convert value to int"""
    try:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return default
        return int(val)
    except Exception:
        return default


def plot_telemetry(ax, drv1_tel, drv2_tel, channel, drv1_color, drv2_color, drv1_abbr, drv2_abbr, label_font, line_effects):
    """Plot telemetry data for a specific channel"""
    # Use Time instead of Distance for x-axis
    drv1_time = drv1_tel['Time'].dt.total_seconds()
    drv2_time = drv2_tel['Time'].dt.total_seconds()

    # Debug: log time range for first plot
    if channel == 'Throttle':
        logging.info(f"Time range - {drv1_abbr}: {drv1_time.min():.1f}s to {drv1_time.max():.1f}s")
        logging.info(f"Time range - {drv2_abbr}: {drv2_time.min():.1f}s to {drv2_time.max():.1f}s")

    ax.plot(drv1_time, drv1_tel[channel], color=drv1_color, linewidth=2, label=drv1_abbr)
    ax.plot(drv2_time, drv2_tel[channel], color=drv2_color, linewidth=2, label=drv2_abbr)
    ax.set_ylabel(channel, **label_font)
    ax.grid(True, alpha=0.3)
    ax.set_facecolor('#1a1a1a')

    # Apply styling
    for spine in ax.spines.values():
        spine.set_color('white')
    ax.tick_params(colors='white')


def plot_gear_telemetry(ax, drv1_tel, drv2_tel, drv1_color, drv2_color, drv1_abbr, drv2_abbr, label_font, line_effects):
    """Plot gear telemetry with special stepped visualization"""
    # Use Time instead of Distance for x-axis
    drv1_time = drv1_tel['Time'].dt.total_seconds()
    drv2_time = drv2_tel['Time'].dt.total_seconds()
    ax.plot(drv1_time, drv1_tel['nGear'], color=drv1_color, linewidth=2, drawstyle='steps-post', label=drv1_abbr)
    ax.plot(drv2_time, drv2_tel['nGear'], color=drv2_color, linewidth=2, drawstyle='steps-post', label=drv2_abbr)
    ax.set_ylabel("Gear", **label_font)
    ax.grid(True, alpha=0.3)
    ax.set_facecolor('#1a1a1a')

    # Apply styling
    for spine in ax.spines.values():
        spine.set_color('white')
    ax.tick_params(colors='white')


def compare_fastest_laps(session, drv1_abbr: str, drv2_abbr: str):
    """
    Generate telemetry comparison plot with all optimizations

    Returns:
        tuple: (plot_buffer, drv1_abbr, drv1_lap_time, drv2_abbr, drv2_lap_time,
                drv1_sectors, drv2_sectors, faster_driver, delta, drv1_team_color,
                drv1_position, drv1_lap_gap, drv2_team_color, drv2_position,
                drv2_lap_gap, leader_abbr, plot_annotations)
    """
    start_time = time.time()

    # Get driver data
    drv1_laps = session.laps.pick_driver(drv1_abbr)
    drv2_laps = session.laps.pick_driver(drv2_abbr)

    drv1_color = plotting.get_driver_color(drv1_abbr, session)
    drv2_color = plotting.get_driver_color(drv2_abbr, session)

    if drv1_color == drv2_color:
        drv1_color, drv2_color = "#FF6B6B", "#4ECDC4"

    drv1_fastest = drv1_laps.pick_fastest()
    drv2_fastest = drv2_laps.pick_fastest()

    # Load telemetry data
    drv1_tel = drv1_fastest.get_telemetry()
    drv2_tel = drv2_fastest.get_telemetry()

    # Track-aware interpolation
    try:
        common_dist = np.linspace(drv1_tel['Distance'].min(), drv1_tel['Distance'].max(), 1000)
        track_name = session.event['EventName']
        logging.info(f"🎯 {track_name}: Using {len(common_dist)} adaptive interpolation points")
    except Exception as e:
        logging.warning(f"Track optimization failed, using fallback: {e}")
        common_dist = np.linspace(
            max(drv1_tel["Distance"].min(), drv2_tel["Distance"].min()),
            min(drv1_tel["Distance"].max(), drv2_tel["Distance"].max()),
            1500
        )

    # Calculate sector times
    drv1_sector_times = [drv1_fastest[f"Sector{i}Time"] for i in range(1, 4)]
    drv2_sector_times = [drv2_fastest[f"Sector{i}Time"] for i in range(1, 4)]

    session_best_sector_times = [
        session.laps[f"Sector{i}Time"].min().total_seconds() if not pd.isnull(session.laps[f"Sector{i}Time"].min()) else None
        for i in range(1, 4)
    ]

    # Interpolate timing data
    drv1_time = np.interp(
        common_dist, drv1_tel["Distance"], drv1_tel["Time"].dt.total_seconds()
    )
    drv2_time = np.interp(
        common_dist, drv2_tel["Distance"], drv2_tel["Time"].dt.total_seconds()
    )

    # Calculate delta and find key moments
    delta = drv2_time - drv1_time
    delta_diff = np.diff(delta)

    total_lap_delta = abs(delta[-1] - delta[0])
    percentile_threshold = np.percentile(np.abs(delta_diff), 95)
    delta_based_threshold = total_lap_delta * 0.05
    min_threshold = 0.005
    min_significant_change = max(min_threshold, min(percentile_threshold, delta_based_threshold))

    key_idxs = np.where(np.abs(delta_diff) > min_significant_change)[0]

    # Filter out moments that are too close together
    if len(key_idxs) > 1:
        moments_with_significance = []
        for idx in key_idxs:
            time_point = drv1_time[idx]
            significance = abs(delta_diff[idx])
            moments_with_significance.append((idx, time_point, significance))

        moments_with_significance.sort(key=lambda x: x[1])

        filtered_moments = []
        for idx, time_point, significance in moments_with_significance:
            too_close = False
            competing_moment = None

            for selected_idx, selected_time, selected_significance in filtered_moments:
                if abs(time_point - selected_time) < 3.0:
                    too_close = True
                    competing_moment = (selected_idx, selected_time, selected_significance)
                    break

            if too_close and competing_moment:
                if significance > competing_moment[2]:
                    filtered_moments.remove(competing_moment)
                    filtered_moments.append((idx, time_point, significance))
            elif not too_close:
                filtered_moments.append((idx, time_point, significance))

        filtered_moments.sort(key=lambda x: x[1])
        key_idxs = np.array([moment[0] for moment in filtered_moments])

    # Create matplotlib figure
    telemetry_metrics = ["Throttle", "Brakes", "RPM", "Speed", "nGear"]

    fig, axes = plt.subplots(len(telemetry_metrics), 1, figsize=(28, 20))
    fig.subplots_adjust(hspace=0.18)

    label_font = {"fontsize": 16, "color": "white", "fontweight": "bold"}
    line_effects = [pe.Stroke(linewidth=4, foreground="#222"), pe.Normal()]

    # Add Turn Markers and Labels
    try:
        circuit_info = session.get_circuit_info()
        if hasattr(circuit_info, 'corners'):
            corners = circuit_info.corners
            for _, turn in corners.iterrows():
                turn_num = str(turn['Number'])
                turn_dist = turn['Distance']
                if (drv1_tel['Distance'].min() <= turn_dist <= drv1_tel['Distance'].max()):
                    turn_time = np.interp(turn_dist, drv1_tel['Distance'], drv1_tel['Time'].dt.total_seconds())
                    for ax in axes:
                        ax.axvline(x=turn_time, color='white', alpha=0.18, linewidth=1, zorder=0)
                    axes[0].text(
                        turn_time, axes[0].get_ylim()[1] * 1.01, turn_num,
                        ha='center', va='bottom', fontsize=11, fontweight='bold',
                        color='white',
                        bbox=dict(facecolor='#444', edgecolor='none', boxstyle='round,pad=0.2', alpha=0.7),
                        zorder=10
                    )
    except Exception as e:
        logging.warning(f"Could not add turn markers: {e}")

    # Add Sector Split Markers
    try:
        s2_start = drv1_fastest['Sector1Time'].total_seconds()
        s3_start = s2_start + drv1_fastest['Sector2Time'].total_seconds()
        for ax in axes:
            ax.axvline(x=s2_start, color='#fff', linewidth=2.2, alpha=0.32, linestyle='--', zorder=2)
            ax.axvline(x=s3_start, color='#fff', linewidth=2.2, alpha=0.32, linestyle='--', zorder=2)

        ylim = axes[0].get_ylim()
        label_y = ylim[1] + (ylim[1] - ylim[0]) * 0.04
        axes[0].text(s2_start, label_y, 'S2', ha='center', va='bottom',
                    fontsize=11, fontweight='bold', color='white',
                    bbox=dict(facecolor='#222', edgecolor='none', boxstyle='round,pad=0.18', alpha=0.85),
                    zorder=10)
        axes[0].text(s3_start, label_y, 'S3', ha='center', va='bottom',
                    fontsize=11, fontweight='bold', color='white',
                    bbox=dict(facecolor='#222', edgecolor='none', boxstyle='round,pad=0.18', alpha=0.85),
                    zorder=10)
    except Exception as e:
        logging.warning(f"Could not add sector split markers: {e}")

    # Plot telemetry channels
    plot_telemetry(axes[0], drv1_tel, drv2_tel, "Throttle", drv1_color, drv2_color, drv1_abbr, drv2_abbr, label_font, line_effects)
    axes[0].legend(facecolor="#222", edgecolor="white", fontsize=14, labelcolor="white", framealpha=0.85, loc='upper right')

    plot_telemetry(axes[1], drv1_tel, drv2_tel, "Brake", drv1_color, drv2_color, drv1_abbr, drv2_abbr, label_font, line_effects)
    axes[1].set_ylabel("Brakes", **label_font)

    plot_telemetry(axes[2], drv1_tel, drv2_tel, "RPM", drv1_color, drv2_color, drv1_abbr, drv2_abbr, label_font, line_effects)
    plot_telemetry(axes[3], drv1_tel, drv2_tel, "Speed", drv1_color, drv2_color, drv1_abbr, drv2_abbr, label_font, line_effects)
    axes[3].set_ylabel("Speed (km/h)", **label_font)

    # Special handling for gear plot
    plot_gear_telemetry(axes[4], drv1_tel, drv2_tel, drv1_color, drv2_color, drv1_abbr, drv2_abbr, label_font, line_effects)
    axes[4].set_ylabel("Gear", **label_font)
    axes[4].set_xlabel("Lap Time", **label_font)

    # Styling for all subplots
    for ax in axes:
        ax.set_facecolor("#222")
        ax.grid(True, alpha=0.2, color="white")
        ax.tick_params(colors="white", labelsize=12)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("white")
        ax.spines["bottom"].set_color("white")

    # Add Key Moment Annotations
    annotation_colors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#f9ca24', '#f0932b']
    moment_details = []

    for i, idx in enumerate(key_idxs):
        try:
            time_point = drv1_time[idx]

            # Interpolate telemetry values
            drv1_throttle = np.interp(common_dist[idx], drv1_tel["Distance"], drv1_tel["Throttle"])
            drv2_throttle = np.interp(common_dist[idx], drv2_tel["Distance"], drv2_tel["Throttle"])
            drv1_brake = np.interp(common_dist[idx], drv1_tel["Distance"], drv1_tel["Brake"])
            drv2_brake = np.interp(common_dist[idx], drv2_tel["Distance"], drv2_tel["Brake"])
            drv1_speed = np.interp(common_dist[idx], drv1_tel["Distance"], drv1_tel["Speed"])
            drv2_speed = np.interp(common_dist[idx], drv2_tel["Distance"], drv2_tel["Speed"])
            drv1_rpm = np.interp(common_dist[idx], drv1_tel["Distance"], drv1_tel["RPM"])
            drv2_rpm = np.interp(common_dist[idx], drv2_tel["Distance"], drv2_tel["RPM"])
            drv1_gear = int(np.round(np.interp(common_dist[idx], drv1_tel["Distance"], drv1_tel["nGear"])))
            drv2_gear = int(np.round(np.interp(common_dist[idx], drv2_tel["Distance"], drv2_tel["nGear"])))

            # Classify the moment
            moment_description = classify_moment(
                t1=drv1_throttle, t2=drv2_throttle,
                b1=drv1_brake, b2=drv2_brake,
                v1=drv1_speed, v2=drv2_speed,
                r1=drv1_rpm, r2=drv2_rpm,
                session_type=session.name
            )

            # Skip minor moments
            if any(word in moment_description.lower() for word in ['minor', 'slight difference', 'small']):
                continue

            # Store moment details
            moment_id = len(moment_details) + 1
            moment_data = {
                'id': moment_id,
                'time': time_point,
                'description': moment_description,
                'telemetry': {
                    drv1_abbr: {
                        'throttle': drv1_throttle, 'brake': drv1_brake,
                        'speed': drv1_speed, 'rpm': drv1_rpm, 'gear': drv1_gear
                    },
                    drv2_abbr: {
                        'throttle': drv2_throttle, 'brake': drv2_brake,
                        'speed': drv2_speed, 'rpm': drv2_rpm, 'gear': drv2_gear
                    }
                },
                'distance': common_dist[idx]
            }
            moment_details.append(moment_data)

            # Add annotations
            annotation_color = annotation_colors[i % len(annotation_colors)]
            for ax_idx, ax in enumerate(axes):
                ax.axvline(x=time_point, color=annotation_color, alpha=0.3, linewidth=1, linestyle='--', zorder=10)

            # Determine target plot for annotation
            description_lower = moment_description.lower()
            target_plot_idx = 0  # Default to Throttle

            if any(word in description_lower for word in ['brake', 'braking', 'stopping', 'trail']):
                target_plot_idx = 1
            elif any(word in description_lower for word in ['gear', 'shift', 'selection']):
                target_plot_idx = 4
            elif any(word in description_lower for word in ['rpm', 'engine', 'rev']):
                target_plot_idx = 2
            elif any(word in description_lower for word in ['speed', 'velocity', 'fast', 'slow']):
                target_plot_idx = 3

            # Add annotation
            ax = axes[target_plot_idx]
            y_min, y_max = ax.get_ylim()
            y_range = y_max - y_min
            y_position = y_max + (y_range * 0.02)

            short_label = f"Moment {moment_id}"
            ax.annotate(
                short_label,
                xy=(time_point, y_max),
                xytext=(time_point, y_position),
                ha='center', va='bottom',
                color=annotation_color,
                fontsize=10, fontweight='bold',
                bbox=dict(boxstyle="round,pad=0.3", facecolor='black', alpha=0.9,
                         edgecolor=annotation_color, linewidth=1.5),
                path_effects=line_effects,
                zorder=11, clip_on=False
            )

        except Exception as e:
            logging.error(f"Failed to annotate moment {i}: {e}")
            continue

    # Save plot to buffer (after all plotting is complete)
    plot_buffer = BytesIO()
    plt.savefig(
        plot_buffer,
        format="png",
        dpi=150,
        bbox_inches="tight",
        facecolor="#111",
        edgecolor="none",
    )
    plot_buffer.seek(0)

    plt.close(fig)

    # Clean up telemetry data to free memory
    del drv1_tel, drv2_tel

    # Record performance statistics
    processing_time = time.time() - start_time
    track_name = session.event['EventName']

    # Prepare sector data
    drv1_sectors = []
    drv2_sectors = []
    for i, (s1, s2) in enumerate(zip(drv1_sector_times, drv2_sector_times)):
        sector_num = i + 1
        s1_time = s1.total_seconds() if not pd.isnull(s1) else None
        s2_time = s2.total_seconds() if not pd.isnull(s2) else None
        session_best = session_best_sector_times[i]

        # Sector color logic
        if s1_time is not None and session_best is not None and abs(s1_time - session_best) < 0.001:
            bg_color_1 = "#a020f0"
        elif s1_time is not None and abs(s1_time - drv1_fastest[f"Sector{sector_num}Time"].total_seconds()) < 0.001:
            bg_color_1 = "#22c55e"
        else:
            bg_color_1 = "#fbbf24"

        if s2_time is not None and session_best is not None and abs(s2_time - session_best) < 0.001:
            bg_color_2 = "#a020f0"
        elif s2_time is not None and abs(s2_time - drv2_fastest[f"Sector{sector_num}Time"].total_seconds()) < 0.001:
            bg_color_2 = "#22c55e"
        else:
            bg_color_2 = "#fbbf24"

        color_1 = drv1_color if bg_color_1 in ["#a020f0", "#22c55e"] else "#222"
        color_2 = drv2_color if bg_color_2 in ["#a020f0", "#22c55e"] else "#222"

        drv1_sectors.append({
            "time": f"{s1_time:.3f}s" if s1_time is not None else "N/A",
            "color": color_1, "bg_color": bg_color_1
        })
        drv2_sectors.append({
            "time": f"{s2_time:.3f}s" if s2_time is not None else "N/A",
            "color": color_2, "bg_color": bg_color_2
        })

    # Calculate lap time comparison
    drv1_lap_time = drv1_fastest["LapTime"].total_seconds()
    drv2_lap_time = drv2_fastest["LapTime"].total_seconds()
    faster_driver = drv1_abbr if drv1_lap_time < drv2_lap_time else drv2_abbr
    delta = abs(drv1_lap_time - drv2_lap_time)

    # Get positions and team colors
    results = session.results
    drv1_result = results[results['Abbreviation'] == drv1_abbr]
    drv2_result = results[results['Abbreviation'] == drv2_abbr]
    drv1_position = int(drv1_result['Position'].iloc[0]) if not drv1_result.empty else 0
    drv2_position = int(drv2_result['Position'].iloc[0]) if not drv2_result.empty else 0

    drv1_team_color = drv1_color
    drv2_team_color = drv2_color

    session_best_lap_time = min(drv1_lap_time, drv2_lap_time)
    drv1_lap_gap = f"+{drv1_lap_time - session_best_lap_time:.3f}" if drv1_lap_time > session_best_lap_time else "+0.000"
    drv2_lap_gap = f"+{drv2_lap_time - session_best_lap_time:.3f}" if drv2_lap_time > session_best_lap_time else "+0.000"

    leader_abbr = drv1_abbr if drv1_lap_time < drv2_lap_time else drv2_abbr

    # Add sector gaps and F1 color classes
    for i, sector in enumerate(drv1_sectors):
        sector["label"] = f"S{i+1}"

        # Determine F1 color based on sector performance
        session_best = session_best_sector_times[i]
        s_time = float(sector["time"].replace("s", "")) if sector["time"] != "N/A" else None
        driver_personal_best = drv1_sector_times[i]

        if s_time is not None and session_best is not None:
            session_best_sec = session_best.total_seconds() if hasattr(session_best, 'total_seconds') else float(session_best)
            personal_best_sec = driver_personal_best.total_seconds() if hasattr(driver_personal_best, 'total_seconds') else float(driver_personal_best)

            gap = s_time - session_best_sec
            sector["gap"] = f"+{gap:.3f}" if gap > 0.001 else "+0.000"

            # F1 color logic
            if abs(s_time - session_best_sec) < 0.001:
                sector["f1_color"] = "purple"
            elif abs(s_time - personal_best_sec) < 0.001:
                sector["f1_color"] = "green"
            else:
                sector["f1_color"] = "yellow"
        else:
            sector["gap"] = "N/A"
            sector["f1_color"] = "yellow"

    for i, sector in enumerate(drv2_sectors):
        sector["label"] = f"S{i+1}"

        # Determine F1 color based on sector performance
        session_best = session_best_sector_times[i]
        s_time = float(sector["time"].replace("s", "")) if sector["time"] != "N/A" else None
        driver_personal_best = drv2_sector_times[i]

        if s_time is not None and session_best is not None:
            session_best_sec = session_best.total_seconds() if hasattr(session_best, 'total_seconds') else float(session_best)
            personal_best_sec = driver_personal_best.total_seconds() if hasattr(driver_personal_best, 'total_seconds') else float(driver_personal_best)

            gap = s_time - session_best_sec
            sector["gap"] = f"+{gap:.3f}" if gap > 0.001 else "+0.000"

            # F1 color logic
            if abs(s_time - session_best_sec) < 0.001:
                sector["f1_color"] = "purple"
            elif abs(s_time - personal_best_sec) < 0.001:
                sector["f1_color"] = "green"
            else:
                sector["f1_color"] = "yellow"
        else:
            sector["gap"] = "N/A"
            sector["f1_color"] = "yellow"

    # Create enhanced telemetry context with performance stats
    enhanced_context = extract_telemetry_context(session, drv1_abbr, drv2_abbr)
    enhanced_context["moment_details"] = moment_details
    enhanced_context["plot_annotations"] = [
        {
            "id": m["id"],
            "time": f"{m['time']:.1f}s",
            "description": m["description"],
            "telemetry": {
                drv1_abbr: {
                    "throttle": f"{m['telemetry'][drv1_abbr]['throttle']:.0f}%",
                    "brake": f"{m['telemetry'][drv1_abbr]['brake']:.0f}%",
                    "speed": f"{m['telemetry'][drv1_abbr]['speed']:.0f} km/h",
                    "rpm": f"{m['telemetry'][drv1_abbr]['rpm']:.0f}",
                    "gear": f"Gear {m['telemetry'][drv1_abbr]['gear']}"
                },
                drv2_abbr: {
                    "throttle": f"{m['telemetry'][drv2_abbr]['throttle']:.0f}%",
                    "brake": f"{m['telemetry'][drv2_abbr]['brake']:.0f}%",
                    "speed": f"{m['telemetry'][drv2_abbr]['speed']:.0f} km/h",
                    "rpm": f"{m['telemetry'][drv2_abbr]['rpm']:.0f}",
                    "gear": f"Gear {m['telemetry'][drv2_abbr]['gear']}"
                }
            }
        }
        for m in moment_details
    ]

    # Add performance statistics to context
    enhanced_context["processing_stats"] = {
        "interpolation_points": len(common_dist),
        "processing_time": processing_time,
        "track_category": "unknown",
        "key_moments_detected": len(key_idxs),
        "optimization_used": "track_aware" if len(common_dist) != 1500 else "fallback"
    }

    enhanced_context["visual_elements"] = {
        "total_annotations": len(moment_details),
        "annotation_times": [f"{m['time']:.1f}s" for m in moment_details],
        "key_moments": [m["description"] for m in moment_details]
    }

    # Store context with session
    session_id = flask_session.get('telemetry_session_id')
    if session_id:
        store_telemetry_context(session_id, enhanced_context)
        logging.info(f"📊 Stored enhanced context for session {session_id[:8]}... "
                    f"({processing_time:.2f}s processing, {len(common_dist)} points)")

    logging.info(f"✅ Plot generation complete: {processing_time:.2f}s, "
                f"{len(moment_details)} moments, {len(common_dist)} points")

    # Return all values
    return (
        plot_buffer,
        drv1_abbr,
        f"{drv1_lap_time:.3f}s",
        drv2_abbr,
        f"{drv2_lap_time:.3f}s",
        drv1_sectors,
        drv2_sectors,
        faster_driver,
        delta,
        drv1_team_color,
        drv1_position,
        drv1_lap_gap,
        drv2_team_color,
        drv2_position,
        drv2_lap_gap,
        leader_abbr,
        enhanced_context["plot_annotations"],
    )


def set_last_plot_buffer(plot_buffer):
    """
    Store plot buffer in user's Flask session (thread-safe, per-user)

    ✅ FIXED: Previously used global variable causing cross-user data leaks
    """
    import base64

    # Convert buffer to base64 for session storage
    plot_buffer.seek(0)
    plot_b64 = base64.b64encode(plot_buffer.read()).decode('utf-8')
    flask_session['plot_data'] = plot_b64

    buffer_size = len(plot_b64)
    logging.info(f"📊 Stored plot in session (size: {buffer_size:,} bytes)")


def get_last_plot_buffer():
    """
    Retrieve plot buffer from user's Flask session

    ✅ FIXED: Now retrieves from user's own session, not global variable
    """
    import base64

    plot_b64 = flask_session.get('plot_data')
    if not plot_b64:
        logging.warning("❌ No plot data in session")
        return None

    try:
        plot_bytes = base64.b64decode(plot_b64)
        plot_buffer = BytesIO(plot_bytes)
        logging.info(f"✅ Retrieved plot from session (size: {len(plot_bytes):,} bytes)")
        return plot_buffer
    except Exception as e:
        logging.error(f"Failed to decode plot from session: {e}")
        return None
