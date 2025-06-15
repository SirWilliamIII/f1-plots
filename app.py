import os

os.environ["MPLBACKEND"] = "Agg"
os.environ["MPLCONFIGDIR"] = "/tmp"

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt

plt.ioff()  # Turn off interactive mode

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os
import uuid
import atexit
from io import BytesIO
from flask import Flask, render_template, request, send_file
import fastf1
from fastf1 import plotting

import logging

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from utils import classify_moment

# Import our new session manager and configuration
from session_manager import SessionManager, get_races_cached, initialize_fastf1_cache

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

load_dotenv()

app = Flask(__name__)

# Initialize FastF1 cache and session manager
initialize_fastf1_cache('fastf1_cache')

# Initialize the global session manager with optimized settings
session_manager = SessionManager(
    max_workers=2,  # 2 background threads for preloading
    enable_preloading=False,  # Enable preloading of popular sessions
)

# Global variables (keep for backward compatibility)
last_plot_buf = None


def get_cached_session(year, race, session_type):
    """
    Get or create a cached session using the new session manager.

    This maintains backward compatibility with your existing code
    while leveraging the improved session management.
    """
    return session_manager.get_session(year, race, session_type)


@app.route("/get_races", methods=["POST"])
def get_races():
    """Get list of races for a given year with improved caching"""
    year = int(request.form["year"])
    try:
        races = get_races_cached(year)
        logging.info(f"Returning {len(races)} races for year={year}")
        return {"races": races}
    except Exception as e:
        logging.error(f"[ERROR] Failed to fetch races: {e}")
        return {"error": "Failed to fetch races"}, 500


@app.route("/get_drivers", methods=["POST"])
def get_drivers():
    """Returns a JSON list of drivers for the selected year, race, and session"""
    try:
        year = int(request.form["year"])
        race = request.form["race"]
        session_name = request.form["session"]
        session_map = {"Qualifying": "Q", "Race": "R"}
        session_type = session_map.get(session_name, session_name)

        # Use cached session with better error handling
        session = get_cached_session(year, race, session_type)

        # Check if session loaded properly
        if not hasattr(session, "drivers") or len(session.drivers) == 0:
            return {
                "error": f"No driver data available for {year} {race} {session_name}"
            }, 400

        driver_options = [
            {
                "abbreviation": session.get_driver(num)["Abbreviation"],
                "broadcast_name": session.get_driver(num)["BroadcastName"],
            }
            for num in session.drivers
        ]
        return {"drivers": driver_options}

    except Exception as e:
        error_msg = str(e)
        if (
            "SessionNotAvailableError" in error_msg
            or "No data for this session" in error_msg
        ):
            return {
                "error": f"Session data not available for {year} {race} {session_name}. Try a different year/race combination."
            }, 400
        logging.error(f"[ERROR] Failed to fetch drivers: {e}")
        return {"error": "Failed to load session data. Please try again."}, 500


@app.route("/", methods=["GET", "POST"])
def index():
    global last_plot_buf
    years = list(range(2020, 2026))
    sessions = ["Qualifying", "Race"]
    session_map = {"Qualifying": "Q", "Race": "R"}

    # Get races for default year (2023) for initial page load
    try:
        races = [
            race
            for race in fastf1.get_event_schedule(2023)["EventName"].tolist()
            if "testing" not in race.lower()
        ]
    except:
        races = []

    drivers = None
    selected_year = None
    selected_race = None
    selected_session = None

    if request.method == "POST":
        # Handle driver selection (step 1 of form)
        if (
            "year" in request.form
            and "race" in request.form
            and "session" in request.form
            and ("driver1" not in request.form or "driver2" not in request.form)
        ):
            selected_year = int(request.form["year"])
            selected_race = request.form["race"]
            selected_session = request.form["session"]
            session_type = session_map[selected_session]

            try:
                session = get_cached_session(selected_year, selected_race, session_type)

                driver_options = [
                    {
                        "abbreviation": session.get_driver(num)["Abbreviation"],
                        "broadcast_name": session.get_driver(num)["BroadcastName"],
                    }
                    for num in session.drivers
                ]

                return render_template(
                    "index.html",
                    years=years,
                    races=races,
                    sessions=sessions,
                    driver_options=driver_options,
                    selected_year=selected_year,
                    selected_race=selected_race,
                    selected_session=selected_session,
                )
            except Exception as e:
                logging.error(f"[ERROR] Failed to load session: {e}")
                return render_template(
                    "error.html",
                    message=f"Failed to load F1 session data for {selected_year} {selected_race} {selected_session}. Please try a different combination.",
                )

        # Handle plot generation (step 2 of form)
        elif (
            "year" in request.form
            and "race" in request.form
            and "session" in request.form
            and "driver1" in request.form
            and "driver2" in request.form
        ):
            selected_year = int(request.form["year"])
            selected_race = request.form["race"]
            selected_session = request.form["session"]
            session_type = session_map[selected_session]
            driver1 = request.form["driver1"]
            driver2 = request.form["driver2"]

            try:
                session = get_cached_session(selected_year, selected_race, session_type)

                plot_buf, drv1_abbr, drv1_lap_time_str, drv2_abbr, drv2_lap_time_str = (
                    compare_fastest_laps(session, driver1, driver2)
                )
                last_plot_buf = plot_buf

                return render_template(
                    "result.html",
                    plot_path="/plot.png",
                    drv1_abbr=drv1_abbr,
                    drv1_lap_time=drv1_lap_time_str,
                    drv2_abbr=drv2_abbr,
                    drv2_lap_time=drv2_lap_time_str,
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

    # Add key moment annotations
    if key_idxs.size:
        top_swings = key_idxs[np.argsort(-np.abs(delta_diff[key_idxs]))][:3]
        for idx in top_swings:
            dist = common_dist[idx]

            # Find corresponding time for both drivers
            t1_time = np.interp(
                dist, drv1_tel["Distance"], drv1_tel["Time"].dt.total_seconds()
            )
            t2_time = np.interp(
                dist, drv2_tel["Distance"], drv2_tel["Time"].dt.total_seconds()
            )
            avg_time = (t1_time + t2_time) / 2

            # Get telemetry values at this point
            t1 = np.interp(dist, drv1_tel["Distance"], drv1_tel["Throttle"])
            t2 = np.interp(dist, drv2_tel["Distance"], drv2_tel["Throttle"])
            b1 = np.interp(dist, drv1_tel["Distance"], drv1_tel["Brake"])
            b2 = np.interp(dist, drv2_tel["Distance"], drv2_tel["Brake"])
            v1 = np.interp(dist, drv1_tel["Distance"], drv1_tel["Speed"])
            v2 = np.interp(dist, drv2_tel["Distance"], drv2_tel["Speed"])

            # Classify the moment
            label = classify_moment(t1, t2, b1, b2, v1, v2)

            # Add vertical line and annotation
            for ax in axes:
                ax.axvline(
                    avg_time, color="yellow", linestyle="--", alpha=0.15, linewidth=1
                )

            axes[3].annotate(
                label,
                xy=(avg_time, (v1 + v2) / 2),
                xytext=(50, 0),
                textcoords="offset points",
                arrowprops=dict(arrowstyle="->", color="yellow"),
                color="yellow",
                fontsize=12,
                backgroundcolor="#222",
            )

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

            # Add sector time annotations
            axes[1].annotate(
                s1str,
                xy=(end - offset, 1.10),
                xycoords=("data", "axes fraction"),
                ha="right",
                va="bottom",
                color=color1,
                fontsize=22,
                fontweight="bold",
                bbox=dict(
                    facecolor=box_color1,
                    edgecolor="white",
                    boxstyle="round,pad=0.8",
                    alpha=0.98,
                    linewidth=3,
                ),
                zorder=10,
            )
            axes[2].annotate(
                s2str,
                xy=(end + offset, 1.10),
                xycoords=("data", "axes fraction"),
                ha="left",
                va="bottom",
                color=color2,
                fontsize=22,
                fontweight="bold",
                bbox=dict(
                    facecolor=box_color2,
                    edgecolor="white",
                    boxstyle="round,pad=0.8",
                    alpha=0.98,
                    linewidth=3,
                ),
                zorder=10,
            )

    # Format x-axis as stopwatch
    from matplotlib.ticker import FuncFormatter

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
    sup_title = f"{drv1_abbr} vs {drv2_abbr} – {session.event['EventName']} {session.event.year} {session.name}"
    plt.suptitle(sup_title, **title_font)
    plt.tight_layout()
    plt.subplots_adjust(top=0.93)

    # Save to buffer
    buf = BytesIO()
    plt.savefig(
        buf, format="png", facecolor=fig.get_facecolor(), bbox_inches="tight", dpi=180
    )
    plt.close()
    buf.seek(0)

    return (
        buf,
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

# For debugging - can be removed in production
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=False)
