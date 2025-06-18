import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os
import uuid
import atexit
from io import BytesIO
from flask import Flask, render_template, request, send_file, jsonify
import fastf1
from fastf1 import plotting
import logging
import numpy as np
import pandas as pd
from functools import wraps
import signal
from dotenv import load_dotenv
from utils import classify_moment
from flask_compress import Compress
from matplotlib.ticker import FuncFormatter
from datetime import datetime
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from session_manager import SessionManager, get_races_cached, initialize_fastf1_cache

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

load_dotenv()

app = Flask(__name__)


os.environ["MPLBACKEND"] = "Agg"
os.environ["MPLCONFIGDIR"] = "/tmp"


# plt.ioff()  # Turn off interactive mode
plt.switch_backend("Agg")  # Use Agg backend instead of interactive mode


Compress(app)
# Initialize FastF1 cache and session manager
initialize_fastf1_cache("fastf1_cache")

# Initialize the global session manager with optimized settings
session_manager = SessionManager(
    max_workers=2,  # 2 background threads for preloading
    enable_preloading=False,  # Enable preloading of popular sessions
)

# Global variables (keep for backward compatibility)
last_plot_buf = None

# Prometheus metrics
REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds", "HTTP request latency", ["method", "endpoint"]
)
PLOT_GENERATION_TIME = Histogram(
    "plot_generation_seconds", "Time taken to generate plots"
)


def timeout(seconds=30):
    def decorator(func):
        def handler(signum, frame):
            raise TimeoutError("Request timed out")

        @wraps(func)
        def wrapper(*args, **kwargs):
            signal.signal(signal.SIGALRM, handler)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)
            return result

        return wrapper

    return decorator


@app.route("/get_races", methods=["POST"])
def get_races():
    """Get list of races for a given year with improved caching and filtering for current year"""
    REQUEST_COUNT.labels(method="POST", endpoint="/get_races", status="200").inc()
    with REQUEST_LATENCY.labels(method="POST", endpoint="/get_races").time():
        year = int(request.form["year"])
        try:
            races = get_races_cached(year)
            race_names = []
            for race in races:
                if isinstance(race, str):
                    race_names.append(race)
                elif hasattr(race, "EventName"):
                    race_names.append(race.EventName)
                elif hasattr(race, "name"):
                    race_names.append(race.name)
                else:
                    race_names.append(str(race))

            # --- Filter out future races if current year is selected ---
            from datetime import datetime
            import fastf1 as f1

            current_year = datetime.now().year
            if year == current_year:
                # Get remaining events for the current year
                remaining_events = set(f1.get_events_remaining()["EventName"])
                # Only include races NOT in remaining_events
                race_names = [r for r in race_names if r not in remaining_events]

            logging.info(f"Returning {len(race_names)} races for year={year}")
            return jsonify({"races": race_names})
        except Exception as e:
            REQUEST_COUNT.labels(
                method="POST", endpoint="/get_races", status="500"
            ).inc()
            logging.error(f"[ERROR] Failed to fetch races: {e}")
            return jsonify({"error": "Failed to fetch races"}), 500


@app.route("/get_drivers", methods=["POST"])
def get_drivers():
    """Returns a JSON list of drivers for the selected year, race, and session"""
    REQUEST_COUNT.labels(method="POST", endpoint="/get_drivers", status="200").inc()
    with REQUEST_LATENCY.labels(method="POST", endpoint="/get_drivers").time():
        try:
            year = int(request.form["year"])
            race = request.form["race"]
            session_name = request.form["session"]

            # Add debug logging
            logging.info(f"🔍 Loading drivers for: {year} - {race} - {session_name}")

            session_map = {"Qualifying": "Q", "Race": "R"}
            session_type = session_map.get(session_name, session_name)

            # Use session manager directly - FIXED
            session = session_manager.get_session(year, race, session_type)

            # Add more debug logging
            logging.info(
                f"🔍 Session loaded, drivers available: {len(session.drivers) if hasattr(session, 'drivers') else 'None'}"
            )

            # Check if session loaded properly
            if not hasattr(session, "drivers") or len(session.drivers) == 0:
                logging.warning(f"⚠️ No drivers found for {year} {race} {session_name}")
                return (
                    jsonify(
                        {
                            "error": f"No driver data available for {year} {race} {session_name}",
                            "details": "This session may not have telemetry data available.",
                        }
                    ),
                    400,
                )

            driver_options = [
                {
                    "abbreviation": session.get_driver(num)["Abbreviation"],
                    "broadcast_name": session.get_driver(num)["BroadcastName"],
                }
                for num in session.drivers
            ]

            logging.info(f"✅ Returning {len(driver_options)} drivers")
            return jsonify({"drivers": driver_options})

        except TimeoutError:
            REQUEST_COUNT.labels(
                method="POST", endpoint="/get_drivers", status="504"
            ).inc()
            return (
                jsonify(
                    {
                        "error": "Request timed out",
                        "details": "Loading driver data is taking longer than expected. Please try again.",
                    }
                ),
                504,
            )
        except Exception as e:
            REQUEST_COUNT.labels(
                method="POST", endpoint="/get_drivers", status="500"
            ).inc()
            error_msg = str(e)
            if (
                "SessionNotAvailableError" in error_msg
                or "No data for this session" in error_msg
            ):
                return (
                    jsonify(
                        {
                            "error": f"Session data not available for {year} {race} {session_name}",
                            "details": "Try a different year/race combination. Not all sessions have telemetry data.",
                        }
                    ),
                    400,
                )
            logging.error(f"[ERROR] Failed to fetch drivers: {e}")
            return (
                jsonify({"error": "Failed to load session data", "details": str(e)}),
                500,
            )


# 4. Add cache warming for popular sessions
@app.before_request
def warm_cache():
    """Pre-load popular sessions into cache"""
    popular_sessions = [
        (2024, "British Grand Prix", "R"),
        (2024, "Monaco Grand Prix", "Q"),
        (2023, "Abu Dhabi Grand Prix", "R"),
    ]

    for year, race, session_type in popular_sessions:
        try:
            session_manager.get_session(year, race, session_type)
            logging.info(f"✅ Pre-loaded {year} {race} {session_type}")
        except Exception as e:
            logging.warning(f"Could not pre-load {year} {race}: {e}")


# 5. Add response compression
@app.route("/", methods=["GET", "POST"])
def index():
    REQUEST_COUNT.labels(method="GET", endpoint="/", status="200").inc()
    with REQUEST_LATENCY.labels(method="GET", endpoint="/").time():
        global last_plot_buf
        years = list(range(2020, 2026))
        sessions = ["Qualifying", "Race"]  # Available options
        session_map = {"Qualifying": "Q", "Race": "R"}

        # Get races for default year (2023) for initial page load - FIXED
        try:
            races = get_races_cached(2023)  # Use the same cached function
        except:
            races = []

        drivers = None
        selected_year = None
        selected_race = None
        selected_session = None  # This gets set from form

        if request.method == "POST":
            # Always assign variables from form at the top
            selected_year = int(request.form.get("year"))
            selected_race = request.form.get("race")
            selected_session = request.form.get(
                "session", "Qualifying"
            )  # ← Change to "Qualifying"
            driver1 = request.form.get("driver1")
            driver2 = request.form.get("driver2")
            session_type = session_map.get(selected_session, selected_session)

            # Validate form data
            if not (
                selected_year
                and selected_race
                and driver1
                and driver2
                and driver1 != driver2
            ):
                return render_template(
                    "error.html", message="Missing or invalid form data."
                )

            try:
                # Use session manager directly here too - FIXED
                session = session_manager.get_session(
                    selected_year, selected_race, session_type
                )
                (
                    plot_path,
                    drv1_abbr,
                    drv1_lap_time_str,
                    drv2_abbr,
                    drv2_lap_time_str,
                ) = compare_fastest_laps(session, driver1, driver2)
                last_plot_buf = plot_path

                # 🔥 NEW: Create race title for header
                race_title = f"{session.event.year} {session.event['EventName']}"
                driver_comparison = f"{drv1_abbr}  {drv2_abbr}"
                session_name = "Qualifying" if session_type == "Q" else "Race"

                return render_template(
                    "result.html",
                    plot_path="/static/plot.png",
                    drv1_abbr=drv1_abbr,
                    drv1_lap_time=drv1_lap_time_str,
                    drv2_abbr=drv2_abbr,
                    drv2_lap_time=drv2_lap_time_str,
                    race_title=race_title,  # ✅ NEW
                    driver_comparison=driver_comparison,  # ✅ NEW
                    session_name=session_name,  # ✅ NEW
                )
            except Exception as e:
                logging.error(f"[ERROR] Failed to generate plot: {e}")
                return render_template(
                    "error.html",
                    message="Failed to generate telemetry comparison. Please try again.",
                )

        # Default GET request
        return render_template(
            "index.html",
            years=years,
            races=races,
            sessions=sessions,
            drivers=drivers,
            selected_year=selected_year,
            selected_race=selected_race,
            selected_session=selected_session,
        )


@app.route("/plot.png")
def serve_plot():
    global last_plot_buf
    if last_plot_buf:
        last_plot_buf.seek(0)  # <-- Ensure buffer is rewound before sending
        logging.info("✅ Serving plot image")
        return send_file(last_plot_buf, mimetype="image/png")
    logging.warning("❌ No plot buffer available to serve")
    return "No plot available", 404


# New debug endpoints for monitoring session manager performance
@app.route("/cache_stats")
def cache_stats():
    """Debug endpoint to view session cache statistics"""
    if session_manager:
        stats = session_manager.get_cache_stats()
        return {"cache_stats": stats, "message": "Session manager is running"}
    return {"error": "Session manager not initialized"}, 500


@app.route("/clear_cache", methods=["POST"])
def clear_cache():
    """Administrative endpoint to clear session cache"""
    if session_manager:
        session_manager.clear_cache(keep_popular=True)
        return {"message": "Cache cleared successfully"}
    return {"error": "Session manager not available"}, 500


# Initialize performance optimizations


def initialize_data():
    if not hasattr(app, "_initialized"):
        app._initialized = True
        logging.info("✅ Application initialized successfully")

        # Initialize performance optimizations
        # Warm up matplotlib to reduce first-plot latency
        fig, ax = plt.subplots(1, 1, figsize=(1, 1))
        plt.close(fig)

        logging.info("🚀 Backend optimizations initialized")


# Call it directly
initialize_data()


def compare_fastest_laps(session, drv1_abbr: str, drv2_abbr: str):
    """Generate telemetry comparison plot for two drivers"""

    # Get driver data
    drv1_laps = session.laps.pick_driver(drv1_abbr)
    drv2_laps = session.laps.pick_driver(drv2_abbr)

    # Get driver colors using correct FastF1 API
    drv1_color = plotting.get_driver_color(drv1_abbr, session)
    drv2_color = plotting.get_driver_color(drv2_abbr, session)

    # Handle same colors
    if drv1_color == drv2_color:
        drv1_color, drv2_color = "#FF6B6B", "#4ECDC4"

    # Get fastest laps
    drv1_fastest = drv1_laps.pick_fastest()
    drv2_fastest = drv2_laps.pick_fastest()

    # Get telemetry data
    drv1_tel = drv1_fastest.get_telemetry().add_distance()
    drv2_tel = drv2_fastest.get_telemetry().add_distance()

    # Calculate sector times
    drv1_sector_times = [drv1_fastest[f"Sector{i}Time"] for i in range(1, 4)]
    drv2_sector_times = [drv2_fastest[f"Sector{i}Time"] for i in range(1, 4)]

    # Calculate cumulative sector ends
    drv1_sector_ends = []
    cum = 0.0
    for s in drv1_sector_times:
        if pd.isnull(s):
            drv1_sector_ends.append(None)
        else:
            cum += s.total_seconds()
            drv1_sector_ends.append(cum)

    # Prepare sector time strings
    drv1_sector_strs = [
        f"S{i+1}: {s.total_seconds():.3f}s" if not pd.isnull(s) else ""
        for i, s in enumerate(drv1_sector_times)
    ]
    drv2_sector_strs = [
        f"S{i+1}: {s.total_seconds():.3f}s" if not pd.isnull(s) else ""
        for i, s in enumerate(drv2_sector_times)
    ]

    # Create common distance array for comparison
    common_dist = np.linspace(
        max(drv1_tel["Distance"].min(), drv2_tel["Distance"].min()),
        min(drv1_tel["Distance"].max(), drv2_tel["Distance"].max()),
        1500,
    )

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
    swing_threshold = np.percentile(np.abs(delta_diff), 99)
    key_idxs = np.where(np.abs(delta_diff) > swing_threshold)[0]

    # Create the plot
    fig, axes = plt.subplots(4, 1, figsize=(18, 12), sharex=True)
    fig.patch.set_facecolor("#111")

    # Font settings
    label_font = {"fontsize": 16, "color": "white"}
    title_font = {"fontsize": 24, "color": "white"}

    # Plot throttle
    axes[0].plot(
        drv1_tel["Time"].dt.total_seconds(),
        drv1_tel["Throttle"],
        color=drv1_color,
        label=drv1_abbr,
    )
    axes[0].plot(
        drv2_tel["Time"].dt.total_seconds(),
        drv2_tel["Throttle"],
        color=drv2_color,
        label=drv2_abbr,
    )
    axes[0].set_ylabel("Throttle", **label_font)
    axes[0].legend(facecolor="#222", edgecolor="white", fontsize=14, labelcolor="white")

    # Plot brakes
    axes[1].plot(
        drv1_tel["Time"].dt.total_seconds(), drv1_tel["Brake"], color=drv1_color
    )
    axes[1].plot(
        drv2_tel["Time"].dt.total_seconds(), drv2_tel["Brake"], color=drv2_color
    )
    axes[1].set_ylabel("Brakes", **label_font)

    # Plot RPM
    axes[2].plot(drv1_tel["Time"].dt.total_seconds(), drv1_tel["RPM"], color=drv1_color)
    axes[2].plot(drv2_tel["Time"].dt.total_seconds(), drv2_tel["RPM"], color=drv2_color)
    axes[2].set_ylabel("RPM", **label_font)

    # Plot speed
    axes[3].plot(
        drv1_tel["Time"].dt.total_seconds(), drv1_tel["Speed"], color=drv1_color
    )
    axes[3].plot(
        drv2_tel["Time"].dt.total_seconds(), drv2_tel["Speed"], color=drv2_color
    )
    axes[3].set_ylabel("Speed (km/h)", **label_font)
    axes[3].set_xlabel("Lap Time (s)", **label_font)

    # 🔥 FIXED: Comprehensive moment detection WITHOUT duplicates
    if key_idxs.size:

        def get_best_subplot_for_moment(label):
            """Determine which subplot and data to use based on moment type"""
            label_lower = label.lower()

            # Throttle-related moments
            if any(
                keyword in label_lower
                for keyword in [
                    "throttle",
                    "exit",
                    "acceleration",
                    "power band",
                    "gear selection",
                    "corner exit",
                ]
            ):
                return 0, "Throttle"

            # Brake-related moments
            elif any(
                keyword in label_lower
                for keyword in [
                    "brake",
                    "braking",
                    "trail",
                    "lock-up",
                    "correction",
                    "mistake",
                    "wide",
                ]
            ):
                return 1, "Brake"

            # RPM-related moments
            elif any(
                keyword in label_lower
                for keyword in [
                    "rpm",
                    "gear",
                    "shifting",
                    "power",
                    "band",
                    "performance advantage",
                ]
            ):
                return 2, "RPM"

            # Speed-related moments (default)
            else:
                return 3, "Speed"

        # Analyze more moments
        num_moments = max(12, len(key_idxs) // 5)
        top_swings = key_idxs[np.argsort(-np.abs(delta_diff[key_idxs]))][:num_moments]

        # 🔥 NEW: Single pass analysis with smart subplot assignment
        subplot_moments = {0: [], 1: [], 2: [], 3: []}  # throttle, brake, rpm, speed
        used_times = set()  # Track which times we've already used

        for idx in top_swings:
            dist = common_dist[idx]
            t1_time = np.interp(
                dist, drv1_tel["Distance"], drv1_tel["Time"].dt.total_seconds()
            )
            t2_time = np.interp(
                dist, drv2_tel["Distance"], drv2_tel["Time"].dt.total_seconds()
            )
            avg_time = (t1_time + t2_time) / 2

            # 🔥 SKIP if we've already used a moment within 2 seconds
            if any(abs(avg_time - used_time) < 2.0 for used_time in used_times):
                continue

            used_times.add(avg_time)

            # Get telemetry values
            t1 = np.interp(dist, drv1_tel["Distance"], drv1_tel["Throttle"])
            t2 = np.interp(dist, drv2_tel["Distance"], drv2_tel["Throttle"])
            b1 = np.interp(dist, drv1_tel["Distance"], drv1_tel["Brake"])
            b2 = np.interp(dist, drv2_tel["Distance"], drv2_tel["Brake"])
            v1 = np.interp(dist, drv1_tel["Distance"], drv1_tel["Speed"])
            v2 = np.interp(dist, drv2_tel["Distance"], drv2_tel["Speed"])
            r1 = (
                np.interp(dist, drv1_tel["Distance"], drv1_tel["RPM"])
                if "RPM" in drv1_tel.columns
                else 10000
            )
            r2 = (
                np.interp(dist, drv2_tel["Distance"], drv2_tel["RPM"])
                if "RPM" in drv2_tel.columns
                else 10000
            )

            # Get previous values
            prev_dist = max(dist - 50, common_dist[0])
            prev_t1 = np.interp(prev_dist, drv1_tel["Distance"], drv1_tel["Throttle"])
            prev_t2 = np.interp(prev_dist, drv2_tel["Distance"], drv2_tel["Throttle"])
            prev_b1 = np.interp(prev_dist, drv1_tel["Distance"], drv1_tel["Brake"])
            prev_b2 = np.interp(prev_dist, drv2_tel["Distance"], drv2_tel["Brake"])
            prev_v1 = np.interp(prev_dist, drv1_tel["Distance"], drv1_tel["Speed"])
            prev_v2 = np.interp(prev_dist, drv2_tel["Distance"], drv2_tel["Speed"])
            prev_r1 = (
                np.interp(prev_dist, drv1_tel["Distance"], drv1_tel["RPM"])
                if "RPM" in drv1_tel.columns
                else 10000
            )
            prev_r2 = (
                np.interp(prev_dist, drv2_tel["Distance"], drv2_tel["RPM"])
                if "RPM" in drv2_tel.columns
                else 10000
            )

            # 🔥 SMART: Create multiple labels for the same moment, assign to best subplot
            primary_label = classify_moment(
                t1,
                t2,
                b1,
                b2,
                v1,
                v2,
                r1,
                r2,
                prev_t1,
                prev_t2,
                prev_b1,
                prev_b2,
                prev_v1,
                prev_v2,
                prev_r1,
                prev_r2,
                session_type=session.name,
            )

            # Create moment data
            moment_data = {
                "time": avg_time,
                "values": (t1, t2, b1, b2, v1, v2, r1, r2),
                "significance": abs(delta_diff[idx]),
            }

            # 🔥 SMART ASSIGNMENT: Assign to the subplot that needs it most
            primary_subplot, primary_data_type = get_best_subplot_for_moment(
                primary_label
            )

            # Check if we can create additional relevant labels for other subplots
            additional_labels = []

            # Brake analysis
            if (
                max(b1, b2) > 0.1 and len(subplot_moments[1]) < 3
            ):  # Brake subplot needs more
                brake_diff = abs(b1 - b2)
                if brake_diff > 0.05:
                    additional_labels.append(
                        (1, f"Brake difference ({brake_diff:.2f})", "Brake")
                    )

            # RPM analysis
            if (
                abs(r1 - r2) > 500 and len(subplot_moments[2]) < 3
            ):  # RPM subplot needs more
                rpm_diff = abs(r1 - r2)
                additional_labels.append(
                    (2, f"RPM difference ({int(rpm_diff)} RPM)", "RPM")
                )

            # Throttle analysis
            if (
                abs(t1 - t2) > 20 and len(subplot_moments[0]) < 3
            ):  # Throttle subplot needs more
                throttle_diff = abs(t1 - t2)
                additional_labels.append(
                    (0, f"Throttle difference ({throttle_diff:.1f}%)", "Throttle")
                )

            # 🔥 ASSIGN to primary subplot first
            moment_copy = moment_data.copy()
            moment_copy["label"] = primary_label
            moment_copy["data_type"] = primary_data_type
            subplot_moments[primary_subplot].append(moment_copy)

            # 🔥 ASSIGN additional labels to other subplots (only if they need more content)
            for subplot_idx, label, data_type in additional_labels:
                if subplot_idx != primary_subplot:  # Don't duplicate on same subplot
                    moment_copy = moment_data.copy()
                    moment_copy["label"] = label
                    moment_copy["data_type"] = data_type
                    subplot_moments[subplot_idx].append(moment_copy)

        # 🔥 FINAL: Annotate each subplot (max 3 per subplot, no duplicates)
        for subplot_idx, moments in subplot_moments.items():
            if not moments:
                continue

            # Sort by significance and take top 3
            moments.sort(key=lambda x: x["significance"], reverse=True)
            top_moments = moments[:3]

            subplot_names = ["Throttle", "Brake", "RPM", "Speed"]
            logging.info(
                f"🏁 {subplot_names[subplot_idx]} plot: {len(top_moments)} unique moments"
            )

            for i, moment in enumerate(top_moments):
                avg_time = moment["time"]
                label = moment["label"]
                data_type = moment["data_type"]
                t1, t2, b1, b2, v1, v2, r1, r2 = moment["values"]

                # Calculate Y position
                if data_type == "Throttle":
                    y_pos = (t1 + t2) / 2
                elif data_type == "Brake":
                    y_pos = (b1 + b2) / 2
                elif data_type == "RPM":
                    y_pos = (r1 + r2) / 2
                else:  # Speed
                    y_pos = (v1 + v2) / 2

                # Add subtle vertical line to ALL subplots
                for ax in axes:
                    ax.axvline(
                        avg_time,
                        color="yellow",
                        linestyle="--",
                        alpha=0.08,
                        linewidth=0.8,
                    )

                # Add annotation ONLY to the specific subplot - LARGER
                axes[subplot_idx].annotate(
                    label,
                    xy=(avg_time, y_pos),
                    xytext=(35, 8 + (i * 32)),
                    textcoords="offset points",
                    arrowprops=dict(arrowstyle="->", color="yellow", alpha=0.9, lw=1.0),
                    color="yellow",
                    fontsize=10,  # Increased from 8 to 10
                    fontweight="bold",
                    bbox=dict(
                        facecolor="#333",
                        edgecolor="yellow",
                        boxstyle="round,pad=0.3",  # Slightly more padding
                        alpha=0.95,
                        linewidth=0.8,
                    ),
                    zorder=15,
                    ha="left",
                )

        # Debug summary
        total_annotations = sum(
            len(moments[:3]) for moments in subplot_moments.values()
        )
        logging.info(f"🎯 Total unique annotations: {total_annotations}")

    # Add sector analysis
    all_laps = session.laps.pick_quicklaps()
    session_best_sectors = [all_laps[f"Sector{i}Time"].min() for i in range(1, 4)]
    drv1_best_sectors = [drv1_laps[f"Sector{i}Time"].min() for i in range(1, 4)]
    drv2_best_sectors = [drv2_laps[f"Sector{i}Time"].min() for i in range(1, 4)]

    # Draw sector lines and annotations
    for i, (end, s1str, s2str, s1time, s2time) in enumerate(
        zip(
            drv1_sector_ends,
            drv1_sector_strs,
            drv2_sector_strs,
            drv1_sector_times,
            drv2_sector_times,
        )
    ):
        if end is not None:
            # Add sector boundary lines
            for ax in axes:
                ax.axvline(end, color="#888", linestyle=":", alpha=0.7, linewidth=2)

            # Determine colors for sector time boxes
            def get_sector_color(
                sector_time, session_best, personal_best, driver_color
            ):
                if not pd.isnull(sector_time):
                    if sector_time == session_best:
                        return "#b800b8"  # purple for session best
                    elif sector_time == personal_best:
                        return "#00d400"  # green for personal best
                return driver_color

            box_color1 = get_sector_color(
                s1time, session_best_sectors[i], drv1_best_sectors[i], drv1_color
            )
            box_color2 = get_sector_color(
                s2time, session_best_sectors[i], drv2_best_sectors[i], drv2_color
            )

            # Helper for text color contrast
            def get_contrast_text_color(bg_color):
                bg_color = bg_color.lstrip("#")
                r, g, b = tuple(int(bg_color[i : i + 2], 16) for i in (0, 2, 4))
                brightness = (r * 299 + g * 587 + b * 114) / 1000
                return "black" if brightness > 170 else "white"

            color1 = get_contrast_text_color(box_color1)
            color2 = get_contrast_text_color(box_color2)

            offset = 0.7  # seconds

            # ULTRA-SLEEK sector time annotations with slightly larger boxes
            axes[1].annotate(
                s1str,
                xy=(end - offset, 1.06),
                xycoords=("data", "axes fraction"),
                ha="right",
                va="bottom",
                color=color1,
                fontsize=11,  # Increased from 9 to 11
                fontweight="600",
                bbox=dict(
                    facecolor=box_color1,
                    edgecolor=box_color1,
                    boxstyle="round,pad=0.4",  # Slightly more padding
                    alpha=0.9,
                    linewidth=0,
                ),
                zorder=10,
            )
            axes[2].annotate(
                s2str,
                xy=(end + offset, 1.06),
                xycoords=("data", "axes fraction"),
                ha="left",
                va="bottom",
                color=color2,
                fontsize=11,  # Increased from 9 to 11
                fontweight="600",
                bbox=dict(
                    facecolor=box_color2,
                    edgecolor=box_color2,
                    boxstyle="round,pad=0.4",  # Slightly more padding
                    alpha=0.9,
                    linewidth=0,
                ),
                zorder=10,
            )

    # Format x-axis as stopwatch

    def stopwatch_fmt(x, pos):
        mins = int(x // 60)
        secs = x % 60
        return f"{mins:01d}:{secs:06.3f}"

    axes[3].xaxis.set_major_formatter(FuncFormatter(stopwatch_fmt))

    # Style all axes
    for ax in axes:
        ax.set_facecolor("#222")
        ax.grid(True, color="gray", linestyle="--", linewidth=0.3)
        ax.tick_params(axis="x", colors="white", labelsize=14)
        ax.tick_params(axis="y", colors="white", labelsize=12)
        for label in ax.get_xticklabels() + ax.get_yticklabels():
            label.set_color("white")

    # Format lap times
    def _format(lap_time):
        if lap_time is None or pd.isnull(lap_time):
            return "N/A"
        total_sec = lap_time.total_seconds()
        return f"{int(total_sec // 60)}:{total_sec % 60:06.3f}"

    # Add title
    sup_title = f"{drv1_abbr} {drv2_abbr} – {session.event['EventName']} {session.event.year} {session.name}"
    # plt.suptitle(sup_title, **title_font)  # ❌ Remove this line
    plt.tight_layout()
    # plt.subplots_adjust(top=0.93)  # ❌ Remove this line too

    # Save to file instead of buffer
    plot_path = "static/plot.png"
    plt.savefig(
        plot_path,
        format="png",
        facecolor=fig.get_facecolor(),
        bbox_inches="tight",
        dpi=180,
    )
    plt.close()

    return (
        plot_path,
        drv1_abbr,
        _format(drv1_fastest["LapTime"]),
        drv2_abbr,
        _format(drv2_fastest["LapTime"]),
    )


# Graceful shutdown handling
def shutdown_handler():
    """Ensure clean shutdown of session manager"""
    if session_manager:
        logging.info("🛑 Shutting down session manager...")
        session_manager.shutdown()


atexit.register(shutdown_handler)


@app.route("/health")
def health_check():
    """Health check endpoint for monitoring instance status"""
    return jsonify(
        {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "instance_id": id(app),  # Unique identifier for this instance
        }
    )


@app.route("/metrics")
def metrics():
    """Prometheus metrics endpoint"""
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}



if  __name__ == "__main__":
    app.run(host="0.0.0.0",debug=True)