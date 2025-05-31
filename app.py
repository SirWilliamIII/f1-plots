import os
from flask import Flask, render_template, request
import fastf1
from fastf1 import plotting
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from fastf1.plotting import get_driver_color
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

os.makedirs("fastf1_cache", exist_ok=True)
fastf1.Cache.enable_cache("fastf1_cache")
plotting.setup_mpl(color_scheme="fastf1", misc_mpl_mods=False)


@app.route("/", methods=["GET", "POST"])
def index():
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
        # Step 1: year/gp/session_type selected, but not drivers yet
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
            session.load()
            # Build driver options: list of dicts with abbreviation and broadcast name
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
        # Step 2: drivers selected, generate plot
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
            session.load()
            plot_path, drv1_abbr, drv1_lap_time_str, drv2_abbr, drv2_lap_time_str = (
                compare_fastest_laps(session, driver1, driver2)
            )
            return render_template(
                "result.html",
                plot_path=plot_path,
                drv1_abbr=drv1_abbr,
                drv1_lap_time=drv1_lap_time_str,
                drv2_abbr=drv2_abbr,
                drv2_lap_time=drv2_lap_time_str,
            )
    # GET or initial load: no drivers yet
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


def classify_moment(
    t1: float, t2: float, b1: float, b2: float, v1: float, v2: float
) -> str:
    throttle_diff = t1 - t2
    brake_diff = b1 - b2
    speed_diff = v1 - v2
    if abs(brake_diff) > 0.5 and (b1 > 0.5 or b2 > 0.5):
        return "Later braking"
    if abs(throttle_diff) > 40 and (t1 > 40 or t2 > 40):
        return "Earlier throttle"
    if abs(speed_diff) > 8 and (b1 < 0.05 and b2 < 0.05) and (t1 < 10 and t2 < 10):
        return "Higher mid‑corner speed"
    if (t1 < 5 or t2 < 5) and (b1 < 0.05 and b2 < 0.05):
        return "Correction for over/under‑steer"
    return "Momentum shift"


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
        drv1_tel["Distance"], drv1_tel["Throttle"], color=drv1_color, label=drv1_abbr
    )
    axes[0].plot(
        drv2_tel["Distance"], drv2_tel["Throttle"], color=drv2_color, label=drv2_abbr
    )
    axes[0].set_ylabel("Throttle", **label_font)
    axes[0].legend(facecolor="#222", edgecolor="white", fontsize=14, labelcolor="white")
    axes[1].plot(drv1_tel["Distance"], drv1_tel["Brake"], color=drv1_color)
    axes[1].plot(drv2_tel["Distance"], drv2_tel["Brake"], color=drv2_color)
    axes[1].set_ylabel("Brakes", **label_font)
    axes[2].plot(drv1_tel["Distance"], drv1_tel["RPM"], color=drv1_color)
    axes[2].plot(drv2_tel["Distance"], drv2_tel["RPM"], color=drv2_color)
    axes[2].set_ylabel("RPM", **label_font)
    axes[3].plot(drv1_tel["Distance"], drv1_tel["Speed"], color=drv1_color)
    axes[3].plot(drv2_tel["Distance"], drv2_tel["Speed"], color=drv2_color)
    axes[3].set_ylabel("Speed (km/h)", **label_font)
    axes[3].set_xlabel("Distance (m)", **label_font)
    if key_idxs.size:
        top_swings = key_idxs[np.argsort(-np.abs(delta_diff[key_idxs]))][:3]
        for idx in top_swings:
            dist = common_dist[idx]
            t1 = np.interp(dist, drv1_tel["Distance"], drv1_tel["Throttle"])
            t2 = np.interp(dist, drv2_tel["Distance"], drv2_tel["Throttle"])
            b1 = np.interp(dist, drv1_tel["Distance"], drv1_tel["Brake"])
            b2 = np.interp(dist, drv2_tel["Distance"], drv2_tel["Brake"])
            v1 = np.interp(dist, drv1_tel["Distance"], drv1_tel["Speed"])
            v2 = np.interp(dist, drv2_tel["Distance"], drv2_tel["Speed"])
            label = classify_moment(t1, t2, b1, b2, v1, v2)
            for ax in axes:
                ax.axvline(dist, color="yellow", linestyle="--", alpha=0.7)
            axes[3].annotate(
                label,
                xy=(dist, (v1 + v2) / 2),
                xytext=(50, 0),
                textcoords="offset points",
                arrowprops=dict(arrowstyle="->", color="yellow"),
                color="yellow",
                fontsize=12,
                backgroundcolor="#222",
            )
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
    os.makedirs("static/plots", exist_ok=True)
    img_path = f"static/plots/{drv1_abbr}_{drv2_abbr}.png"
    plt.savefig(img_path, facecolor=fig.get_facecolor(), bbox_inches="tight", dpi=180)
    plt.close()
    return (
        img_path,
        drv1_abbr,
        _format(drv1_fastest["LapTime"]),
        drv2_abbr,
        _format(drv2_fastest["LapTime"]),
    )


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0")

