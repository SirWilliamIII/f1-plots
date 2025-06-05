import os
import uuid
from io import BytesIO
from flask import Flask, render_template, request, send_file
import fastf1
from fastf1 import plotting
import matplotlib
import logging

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from fastf1.plotting import get_driver_color
from dotenv import load_dotenv
from utils import classify_moment

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

load_dotenv()

app = Flask(__name__)

os.makedirs("fastf1_cache", exist_ok=True)
fastf1.Cache.enable_cache("fastf1_cache")
plotting.setup_mpl(color_scheme="fastf1", misc_mpl_mods=False)

last_plot_buf = None


@app.route("/get_races", methods=["POST"])
def get_races():
    year = int(request.form["year"])
    try:
        df = fastf1.get_event_schedule(year, include_testing=False)
        races = [
            {"country": row["Country"], "event_name": row["EventName"]}
            for _, row in df.iterrows()
        ]
        logging.info(f"Returning {len(races)} races for year={year}")
        return {"races": races}
    except Exception as e:
        logging.error(f"[ERROR] Failed to fetch races: {e}")
        return {"error": "Failed to fetch races"}, 500


@app.route("/", methods=["GET", "POST"])
def index():
    global last_plot_buf
    years = list(range(2020, 2026))
    sessions = ["Qualifying", "Race"]
    session_map = {"Qualifying": "Q", "Race": "R"}
    races = [
        race
        for race in fastf1.get_event_schedule(2023)["EventName"].tolist()
        if "testing" not in race.lower()
    ]
    drivers = None
    selected_year = None
    selected_race = None
    selected_session = None

    if request.method == "POST":

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
            session = fastf1.get_session(selected_year, selected_race, session_type)
            try:
                session.load()

            except Exception as e:
                print(f"[ERROR] Failed to load session: {e}")
                return render_template(
                    "error.html", message="Failed to load F1 session."
                )
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
            session = fastf1.get_session(selected_year, selected_race, session_type)
            try:
                session.load()
            except Exception as e:
                print(f"[ERROR] Failed to load session: {e}")
                return render_template(
                    "error.html", message="Failed to load F1 session."
                )
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
        return send_file(last_plot_buf, mimetype="image/png")
    return "No plot available", 404


@app.route("/get_drivers", methods=["POST"])
def get_drivers():
    """
    Returns a JSON list of drivers for the selected year, race, and session.
    """
    try:
        year = int(request.form["year"])
        race = request.form["race"]
        session_name = request.form["session"]
        session_map = {"Qualifying": "Q", "Race": "R"}
        session_type = session_map.get(session_name, session_name)
        session = fastf1.get_session(year, race, session_type)
        session.load()
        driver_options = [
            {
                "abbreviation": session.get_driver(num)["Abbreviation"],
                "broadcast_name": session.get_driver(num)["BroadcastName"],
            }
            for num in session.drivers
        ]
        return {"drivers": driver_options}
    except Exception as e:
        logging.error(f"[ERROR] Failed to fetch drivers: {e}")
        return {"drivers": []}, 500


def compare_fastest_laps(session, drv1_abbr: str, drv2_abbr: str):
    drv1_laps = session.laps.pick_driver(drv1_abbr)
    drv2_laps = session.laps.pick_driver(drv2_abbr)
    drv1_color = get_driver_color(drv1_abbr, session)
    drv2_color = get_driver_color(drv2_abbr, session)
    if drv1_color == drv2_color:
        drv1_color, drv2_color = "#FF6B6B", "#4ECDC4"
    drv1_fastest = drv1_laps.pick_fastest()
    drv2_fastest = drv2_laps.pick_fastest()
    drv1_tel = drv1_fastest.get_telemetry().add_distance()
    drv2_tel = drv2_fastest.get_telemetry().add_distance()

    # --- Sector times and cumulative ends ---
    drv1_sector_times = [drv1_fastest[f"Sector{i}Time"] for i in range(1, 4)]
    drv2_sector_times = [drv2_fastest[f"Sector{i}Time"] for i in range(1, 4)]
    # Use driver 1's sector ends for annotation (could average, but usually very close)
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

    # --- End sector annotation prep ---

    common_dist = np.linspace(
        max(drv1_tel["Distance"].min(), drv2_tel["Distance"].min()),
        min(drv1_tel["Distance"].max(), drv2_tel["Distance"].max()),
        1500,
    )

    drv1_time = np.interp(
        common_dist, drv1_tel["Distance"], drv1_tel["Time"].dt.total_seconds()
    )
    drv2_time = np.interp(
        common_dist, drv2_tel["Distance"], drv2_tel["Time"].dt.total_seconds()
    )
    delta = drv2_time - drv1_time
    delta_diff = np.diff(delta)
    swing_threshold = np.percentile(np.abs(delta_diff), 99)
    key_idxs = np.where(np.abs(delta_diff) > swing_threshold)[0]
    fig, axes = plt.subplots(4, 1, figsize=(18, 12), sharex=True)
    fig.patch.set_facecolor("#111")
    label_font = {"fontsize": 16, "color": "white"}
    tick_font = {"fontsize": 12, "color": "white"}
    title_font = {"fontsize": 24, "color": "white"}
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
    axes[1].plot(
        drv1_tel["Time"].dt.total_seconds(), drv1_tel["Brake"], color=drv1_color
    )
    axes[1].plot(
        drv2_tel["Time"].dt.total_seconds(), drv2_tel["Brake"], color=drv2_color
    )
    axes[1].set_ylabel("Brakes", **label_font)
    axes[2].plot(drv1_tel["Time"].dt.total_seconds(), drv1_tel["RPM"], color=drv1_color)
    axes[2].plot(drv2_tel["Time"].dt.total_seconds(), drv2_tel["RPM"], color=drv2_color)
    axes[2].set_ylabel("RPM", **label_font)
    axes[3].plot(
        drv1_tel["Time"].dt.total_seconds(), drv1_tel["Speed"], color=drv1_color
    )
    axes[3].plot(
        drv2_tel["Time"].dt.total_seconds(), drv2_tel["Speed"], color=drv2_color
    )
    axes[3].set_ylabel("Speed (km/h)", **label_font)
    axes[3].set_xlabel("Lap Time (s)", **label_font)
    if key_idxs.size:
        top_swings = key_idxs[np.argsort(-np.abs(delta_diff[key_idxs]))][:3]
        for idx in top_swings:
            dist = common_dist[idx]
            # Find the corresponding time for the distance for both drivers
            t1_time = np.interp(
                dist, drv1_tel["Distance"], drv1_tel["Time"].dt.total_seconds()
            )
            t2_time = np.interp(
                dist, drv2_tel["Distance"], drv2_tel["Time"].dt.total_seconds()
            )
            # Use the average time for the vertical line and annotation
            avg_time = (t1_time + t2_time) / 2
            t1 = np.interp(dist, drv1_tel["Distance"], drv1_tel["Throttle"])
            t2 = np.interp(dist, drv2_tel["Distance"], drv2_tel["Throttle"])
            b1 = np.interp(dist, drv1_tel["Distance"], drv1_tel["Brake"])
            b2 = np.interp(dist, drv2_tel["Distance"], drv2_tel["Brake"])
            v1 = np.interp(dist, drv1_tel["Distance"], drv1_tel["Speed"])
            v2 = np.interp(dist, drv2_tel["Distance"], drv2_tel["Speed"])
            label = classify_moment(t1, t2, b1, b2, v1, v2)
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

    # --- Find session best (purple) and personal best (green) for each sector ---
    all_laps = session.laps.pick_quicklaps()
    session_best_sectors = [all_laps[f"Sector{i}Time"].min() for i in range(1, 4)]
    drv1_best_sectors = [drv1_laps[f"Sector{i}Time"].min() for i in range(1, 4)]
    drv2_best_sectors = [drv2_laps[f"Sector{i}Time"].min() for i in range(1, 4)]

    # Draw sector lines and annotate sector times
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
            for ax in axes:
                ax.axvline(end, color="#888", linestyle=":", alpha=0.7, linewidth=2)
            # Determine box color for driver 1
            if not pd.isnull(s1time):
                if s1time == session_best_sectors[i]:
                    box_color1 = "#b800b8"  # purple
                elif s1time == drv1_best_sectors[i]:
                    box_color1 = "#00d400"  # green
                else:
                    box_color1 = drv1_color
            else:
                box_color1 = drv1_color
            # Determine box color for driver 2
            if not pd.isnull(s2time):
                if s2time == session_best_sectors[i]:
                    box_color2 = "#b800b8"  # purple
                elif s2time == drv2_best_sectors[i]:
                    box_color2 = "#00d400"  # green
                else:
                    box_color2 = drv2_color
            else:
                box_color2 = drv2_color

            # Helper to determine best text color (black or white) for a given background
            def get_contrast_text_color(bg_color):
                bg_color = bg_color.lstrip("#")
                r, g, b = tuple(int(bg_color[i : i + 2], 16) for i in (0, 2, 4))
                brightness = (r * 299 + g * 587 + b * 114) / 1000
                return "black" if brightness > 170 else "white"

            color1 = get_contrast_text_color(box_color1)
            color2 = get_contrast_text_color(box_color2)
            # Place first driver's sector boxes between throttle and brakes (above axes[1])
            # Place second driver's sector boxes between brakes and RPM (above axes[2])
            offset = 0.7  # seconds, adjust as needed for clarity
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

    # Custom x-axis formatting: stopwatch style mm:ss.sss
    from matplotlib.ticker import FuncFormatter

    def stopwatch_fmt(x, pos):
        mins = int(x // 60)
        secs = x % 60
        return f"{mins:01d}:{secs:06.3f}"

    axes[3].xaxis.set_major_formatter(FuncFormatter(stopwatch_fmt))

    # Optionally, set major ticks at big moments (turns/braking zones)
    # We'll use the avg_time of moments with relevant labels
    big_moment_labels = {
        "Later braking",
        "Big brake difference",
        "Big speed advantage",
        "Overtake or pass",
    }
    big_moment_times = []
    if key_idxs.size:
        top_swings = key_idxs[np.argsort(-np.abs(delta_diff[key_idxs]))][:3]
        for idx in top_swings:
            dist = common_dist[idx]
            t1_time = np.interp(
                dist, drv1_tel["Distance"], drv1_tel["Time"].dt.total_seconds()
            )
            t2_time = np.interp(
                dist, drv2_tel["Distance"], drv2_tel["Time"].dt.total_seconds()
            )
            avg_time = (t1_time + t2_time) / 2
            t1 = np.interp(dist, drv1_tel["Distance"], drv1_tel["Throttle"])
            t2 = np.interp(dist, drv2_tel["Distance"], drv2_tel["Throttle"])
            b1 = np.interp(dist, drv1_tel["Distance"], drv1_tel["Brake"])
            b2 = np.interp(dist, drv2_tel["Distance"], drv2_tel["Brake"])
            v1 = np.interp(dist, drv1_tel["Distance"], drv1_tel["Speed"])
            v2 = np.interp(dist, drv2_tel["Distance"], drv2_tel["Speed"])
            label = classify_moment(t1, t2, b1, b2, v1, v2)
            if label in big_moment_labels:
                big_moment_times.append(avg_time)
    if big_moment_times:
        axes[3].set_xticks(sorted(big_moment_times))
    for ax in axes:
        ax.set_facecolor("#222")
        ax.grid(True, color="gray", linestyle="--", linewidth=0.3)
        ax.tick_params(axis="x", colors="white", labelsize=14)
        ax.tick_params(axis="y", colors="white", labelsize=12)
        for label in ax.get_xticklabels() + ax.get_yticklabels():
            label.set_color("white")

    def _format(lap_time):
        if lap_time is None or pd.isnull(lap_time):
            return "N/A"
        total_sec = lap_time.total_seconds()
        return f"{int(total_sec // 60)}:{total_sec % 60:06.3f}"

    sup_title = f"{drv1_abbr} vs {drv2_abbr} – {session.event['EventName']} {session.event.year} {session.name}"
    plt.suptitle(sup_title, **title_font)
    plt.tight_layout()
    plt.subplots_adjust(top=0.93)
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


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0")
