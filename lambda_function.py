# app.py (modified for App Runner)
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
import boto3

# Initialize S3 client
s3 = boto3.client('s3')
BUCKET_NAME = 'f1-plots-app-data'

app = Flask(__name__)

os.makedirs("/tmp/fastf1_cache", exist_ok=True)
fastf1.Cache.enable_cache("/tmp/fastf1_cache")
plotting.setup_mpl(color_scheme="fastf1", misc_mpl_mods=False)

def classify_moment(t1, t2, b1, b2, v1, v2):
    # Your existing classify_moment function
    throttle_diff = t1 - t2
    brake_diff = b1 - b2
    speed_diff = v1 - v2

    if abs(brake_diff) > 0.5 and (b1 > 0.5 or b2 > 0.5):
        return "Later braking"
    if abs(throttle_diff) > 40 and (t1 > 40 or t2 > 40):
        return "Earlier throttle"
    if abs(speed_diff) > 8 and (b1 < 0.05 and b2 < 0.05) and (t1 < 10 and t2 < 10):
        return "Higher mid-corner speed"
    if (t1 < 5 or t2 < 5) and (b1 < 0.05 and b2 < 0.05):
        return "Correction for over/under-steer"
    return "Momentum shift"

def compare_fastest_laps(session, drv1_abbr, drv2_abbr):
    # Your existing compare_fastest_laps function
    # Modified to save to S3
    # ... (rest of your function)

    # Upload to S3
    plot_key = f"plots/{drv1_abbr}_{drv2_abbr}.png"
    s3.upload_fileobj(buf, BUCKET_NAME, plot_key, ExtraArgs={'ContentType': 'image/png'})

    return (
        f"https://{BUCKET_NAME}.s3.amazonaws.com/{plot_key}",
        drv1_abbr,
        _format(drv1_fastest["LapTime"]),
        drv2_abbr,
        _format(drv2_fastest["LapTime"]),
    )

@app.route("/", methods=["GET", "POST"])
def index():
    years = list(range(2020, 2026))
    sessions = ["Qualifying", "Race"]
    drivers = [
        "ALB", "ALO", "ANT", "BEA", "BOR", "BOT", "COL", "GAS", "GIO", "HAD",
        "HAM", "HUL", "LAT", "LAW", "LEC", "MAG", "MAZ", "MSC", "NOR", "OCO",
        "PER", "PIA", "RAI", "RIC", "RUS", "SAI", "SAR", "STR", "TSU", "VER",
        "VET", "ZHO",
    ]

    session_map = {"Qualifying": "Q", "Race": "R"}

    if request.method == "POST":
        year = int(request.form["year"])
        gp = request.form["race"]
        session_type = session_map[request.form["session"]]
        driver1 = request.form["driver1"]
        driver2 = request.form["driver2"]

        session = fastf1.get_session(year, gp, session_type)
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

    # default event list for form
    races = fastf1.get_event_schedule(2023)["EventName"].tolist()
    return render_template(
        "index.html", years=years, races=races, sessions=sessions, drivers=drivers
    )

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
