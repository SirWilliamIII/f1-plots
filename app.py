import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os
import requests
import json
import uuid
import atexit
from io import BytesIO
from flask import (
    Flask,
    render_template,
    request,
    send_file,
    jsonify,
    Response,
    stream_with_context,
)
from werkzeug.exceptions import HTTPException
import fastf1
from fastf1 import plotting
import logging
import numpy as np
import pandas as pd
from functools import wraps
import signal
from dotenv import load_dotenv
from utils import classify_moment, extract_telemetry_context
from flask_compress import Compress
from matplotlib.ticker import FuncFormatter
from datetime import datetime
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from session_manager import SessionManager, get_races_cached, initialize_fastf1_cache
from matplotlib import rcParams
import matplotlib.patheffects as pe
import math

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


env = os.getenv('FLASK_ENV', 'development')
if env == 'production':
  load_dotenv('.env.prod')
else:
  load_dotenv('.env')


app = Flask(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")

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
current_telemetry_context = None

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


@app.route("/ollama_proxy/tags", methods=["GET"])
def ollama_tags():
    """Proxy endpoint to check Ollama connection"""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return Response(
            resp.content,
            status=resp.status_code,
            content_type=resp.headers.get("content-type"),
        )
    except requests.exceptions.RequestException:
        return jsonify({"error": "Ollama not available"}), 503


@app.route("/ollama_proxy/generate", methods=["POST"])
def ollama_generate():
    """Enhanced proxy endpoint with telemetry context injection"""
    global current_telemetry_context

    try:
        request_data = request.json.copy()
        user_prompt = request_data.get("prompt", "")
        request_data["model"] = "f1expert-fast"
        
        # Performance optimizations
        request_data["options"] = {
            "num_predict": 200,  # Limit response length for faster inference
            "temperature": 0.3,  # Lower temperature for faster, more focused responses
            "num_ctx": 2048,     # Smaller context window for faster processing
            "repeat_penalty": 1.1
        }
        
        # 🔥 Inject telemetry context into the prompt
        if current_telemetry_context:
            logging.info(f"Injecting telemetry context with keys: {list(current_telemetry_context.keys())}")
            
            # Debug driver names
            if "driver1" in current_telemetry_context and "driver2" in current_telemetry_context:
                drv1 = current_telemetry_context["driver1"]
                drv2 = current_telemetry_context["driver2"]
                logging.info(f"Driver names: {drv1['name']} ({drv1['full_name']}) vs {drv2['name']} ({drv2['full_name']})")
            
            if "plot_annotations" in current_telemetry_context:
                logging.info(f"Found {len(current_telemetry_context['plot_annotations'])} plot annotations")
                for i, ann in enumerate(current_telemetry_context['plot_annotations']):
                    logging.info(f"Annotation {i+1}: {ann['time']} - {ann['description']}")
            context_prompt = create_contextual_prompt(
                user_prompt, current_telemetry_context
            )
            request_data["prompt"] = context_prompt
        else:
            logging.warning("No telemetry context available for AI model")

            # Enhanced system message for concise, formatted output
            request_data[
                "system"
            ] = """You are an expert F1 data analyst. Your goal is to provide concise, easy-to-read telemetry analysis based on the provided telemetry data and context. 2 drivers are being compared in a specific lap.

CRITICAL RULES:
- **Use Markdown for formatting:**
  - Use headings (`### Key Takeaways`) for structure.
  - Use bullet points (`-`) for comparisons and lists.
  - Use bold (`**text**`) for driver names, key stats, and metrics.
- **Be concise and direct.** Avoid long paragraphs. Get straight to the analysis.
- **Data-driven:** ONLY discuss the provided telemetry data. Do not mention other races, years, or drivers.
- **Reference specific values** from the data context to support your points.

Base ALL responses on the specific comparison data provided."""

        # Forward to Ollama
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=request_data,
            stream=request_data.get("stream", False),
            timeout=300,
        )

        if request_data.get("stream", False):
            return Response(
                stream_with_context(resp.iter_content(chunk_size=1024)),
                content_type=resp.headers.get("content-type"),
                status=resp.status_code,
            )
        else:
            return Response(
                resp.content,
                status=resp.status_code,
                content_type=resp.headers.get("content-type"),
            )

    except Exception as e:
        logging.error(f"Ollama proxy error: {e}")
        return jsonify({"error": "Failed to connect to Ollama"}), 503


def create_contextual_prompt(user_prompt, context):
    """Create enhanced prompt with specific telemetry context"""

    race_info = context["race_info"]
    drv1 = context["driver1"]
    drv2 = context["driver2"]
    comparison = context["comparison"]
    sectors = context["sectors"]

    context_text = f"""
CURRENT TELEMETRY DATA BEING ANALYZED:

Race: {race_info['year']} {race_info['race_name']} - {race_info['session_type']}
Track Length: {race_info['track_length']}

IMPORTANT - DRIVER IDENTIFICATION:
Driver 1: {drv1['full_name']} (Abbreviation: {drv1['name']})
- Lap Time: {drv1['lap_time']:.3f} seconds
- Top Speed: {drv1['max_speed']:.1f} km/h
- Average Throttle: {drv1['avg_throttle']:.1f}%

Driver 2: {drv2['full_name']} (Abbreviation: {drv2['name']})
- Lap Time: {drv2['lap_time']:.3f} seconds
- Top Speed: {drv2['max_speed']:.1f} km/h
- Average Throttle: {drv2['avg_throttle']:.1f}%

CRITICAL: Always use the correct driver names above. {drv1['name']} = {drv1['full_name']}, {drv2['name']} = {drv2['full_name']}.

Overall Comparison:
- Faster Driver: {comparison['faster_driver']}
- Lap Time Delta: {comparison['lap_time_delta']:.3f} seconds
- Top Speed Difference: {comparison['speed_difference']:.1f} km/h

Sector Analysis:"""

    for sector in sectors:
        context_text += f"""
Sector {sector['sector']}: {sector['faster_driver']} faster by {sector['delta']:.3f}s
- {drv1['name']}: {sector['driver1_time']:.3f}s
- {drv2['name']}: {sector['driver2_time']:.3f}s"""

    # Add plot annotations if available
    if "plot_annotations" in context and context["plot_annotations"]:
        context_text += f"""

PLOT ANNOTATIONS VISIBLE ON CURRENT TELEMETRY PLOT:
The following {len(context['plot_annotations'])} key moments are marked with colored vertical lines and text annotations:"""
        
        for i, annotation in enumerate(context["plot_annotations"]):
            context_text += f"""
{i+1}. At {annotation['time']}: "{annotation['description']}"
   - Placed on the plot that best represents this moment
   - Telemetry data: {annotation.get('telemetry', {})}"""
    
    if "visual_elements" in context:
        visual = context["visual_elements"]
        context_text += f"""

VISUAL PLOT ELEMENTS:
- Total annotations shown: {visual.get('total_annotations', 0)}
- Key moment times: {', '.join(visual.get('annotation_times', []))}
- Racing insights: {', '.join(visual.get('key_moments', []))}"""

    context_text += f"""

VISIBLE PLOTS: The user can see 4 telemetry traces plotted against lap time:
1. Throttle position (0-100%) - with annotations for throttle-related moments
2. Brake pressure (0-100%) - with annotations for braking-related moments  
3. Engine RPM - with annotations for gear/engine-related moments
4. Speed (km/h) - with annotations for speed-related moments

Each significant racing moment is marked with a colored vertical line across all plots and descriptive text above the most relevant plot.

User Question: {user_prompt}

Answer based ONLY on this specific data and the exact annotations visible in the current plots. Reference the specific times and descriptions listed above."""

    return context_text


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

import os

# Near the top of your file, add:
STATIC_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
if not os.path.exists(STATIC_FOLDER):
    os.makedirs(STATIC_FOLDER)

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
    global current_telemetry_context

    if request.method == "GET":
        current_telemetry_context = None

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
            print("[DEBUG] POST request received on / route")
            # Always assign variables from form at the top
            selected_year = int(request.form.get("year"))
            selected_race = request.form.get("race")
            selected_session = request.form.get(
                "session", "Qualifying"
            )  # ← Change to "Qualifying"
            driver1 = request.form.get("driver1")
            driver2 = request.form.get("driver2")
            session_type = session_map.get(selected_session, selected_session)

            print(f"[DEBUG] Form data: year={selected_year}, race={selected_race}, session={selected_session}, driver1={driver1}, driver2={driver2}")

            # Validate form data
            if not (
                selected_year
                and selected_race
                and driver1
                and driver2
                and driver1 != driver2
            ):
                print("[DEBUG] Invalid form data, rendering error.html")
                return render_template(
                    "error.html", error_message="Missing or invalid form data."
                )

            try:
                print("[DEBUG] Attempting to get session...")
                session = session_manager.get_session(
                    selected_year, selected_race, session_type
                )
                print("[DEBUG] Session loaded successfully")
                # Use session manager directly here too - FIXED
                (
                    plot_path,
                    drv1_abbr,
                    drv1_lap_time_str,
                    drv2_abbr,
                    drv2_lap_time_str,
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
                ) = compare_fastest_laps(session, driver1, driver2)
                print("[DEBUG] compare_fastest_laps executed successfully")
                last_plot_buf = plot_path

                # 🔥 NEW: Create race title for header - context will be set after plot generation
                print("[DEBUG] Starting plot generation")

                race_title = f"{session.event.year} {session.event['EventName']}"
                driver_comparison = f"{drv1_abbr}  {drv2_abbr}"
                session_name = "Qualifying" if session_type == "Q" else "Race"

                # Only use the values returned from compare_fastest_laps
                return render_template(
                    "result.html",
                    plot_path="/plot.png",
                    drv1_abbr=drv1_abbr,
                    drv1_lap_time=drv1_lap_time_str,
                    drv2_abbr=drv2_abbr,
                    drv2_lap_time=drv2_lap_time_str,
                    race_title=race_title,  # ✅ NEW
                    driver_comparison=driver_comparison,  # ✅ NEW
                    session_name=session_name,  # ✅ NEW
                    drv1_sectors=drv1_sectors,
                    drv2_sectors=drv2_sectors,
                    faster_driver=faster_driver,
                    delta=delta,
                    drv1_team_color=drv1_team_color,
                    drv1_position=drv1_position,
                    drv1_lap_gap=drv1_lap_gap,
                    drv2_team_color=drv2_team_color,
                    drv2_position=drv2_position,
                    drv2_lap_gap=drv2_lap_gap,
                    leader_abbr=leader_abbr,
                )
            except Exception as e:
                import traceback
                print("[ERROR] Exception occurred during telemetry comparison:", e)
                traceback.print_exc()
                logging.error(f"[ERROR] Failed to generate plot: {e}")
                return render_template(
                    "error.html",
                    error_message="Failed to generate telemetry comparison. Please try again.",
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


from flask import url_for
import time

# In your serve_plot function or wherever you save the plot:
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


def safe_int(val, default=0):
    try:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return default
        return int(val)
    except Exception:
        return default


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

    # Fix: Define session_best_sector_times for sector gap calculations
    session_best_sector_times = [
        session.laps[f"Sector{i}Time"].min() for i in range(1, 4)
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

    # Calculate delta and find key moments with dynamic threshold
    delta = drv2_time - drv1_time
    delta_diff = np.diff(delta)
    
    # Use a more meaningful threshold based on lap time difference
    total_lap_delta = abs(delta[-1] - delta[0])  # Total lap time difference
    
    # Calculate multiple potential thresholds
    percentile_threshold = np.percentile(np.abs(delta_diff), 95)  # 95th percentile (less strict than 99th)
    delta_based_threshold = total_lap_delta * 0.05  # 5% of total delta (was 10%)
    min_threshold = 0.005  # Minimum 5ms change
    
    # Use the most permissive threshold to ensure we catch significant moments
    min_significant_change = max(min_threshold, min(percentile_threshold, delta_based_threshold))
    
    # Find moments where time difference changes significantly
    key_idxs = np.where(np.abs(delta_diff) > min_significant_change)[0]
    
    # Filter out moments that are too close together (within 3 seconds) - keep most significant
    if len(key_idxs) > 1:
        # Create list of (index, time, significance) tuples
        moments_with_significance = []
        for idx in key_idxs:
            time_point = drv1_time[idx]
            significance = abs(delta_diff[idx])
            moments_with_significance.append((idx, time_point, significance))
        
        # Sort by time to process chronologically
        moments_with_significance.sort(key=lambda x: x[1])
        
        filtered_moments = []
        for idx, time_point, significance in moments_with_significance:
            # Check if this moment is too close to any already selected moment
            too_close = False
            competing_moment = None
            
            for selected_idx, selected_time, selected_significance in filtered_moments:
                if abs(time_point - selected_time) < 3.0:  # Within 3 seconds
                    too_close = True
                    competing_moment = (selected_idx, selected_time, selected_significance)
                    break
            
            if too_close and competing_moment:
                # Replace if this moment is more significant
                if significance > competing_moment[2]:
                    filtered_moments.remove(competing_moment)
                    filtered_moments.append((idx, time_point, significance))
                    logging.info(f"Replaced moment at {competing_moment[1]:.1f}s (sig={competing_moment[2]:.4f}) with {time_point:.1f}s (sig={significance:.4f})")
                # Otherwise skip this less significant moment
            elif not too_close:
                filtered_moments.append((idx, time_point, significance))
        
        # Extract just the indices, sorted by time
        filtered_moments.sort(key=lambda x: x[1])
        key_idxs = np.array([moment[0] for moment in filtered_moments])
    
    # Debug logging
    logging.info(f"Threshold analysis: percentile_95={percentile_threshold:.4f}s, delta_based={delta_based_threshold:.4f}s, min={min_threshold:.4f}s")
    logging.info(f"Selected threshold: {min_significant_change:.4f}s")
    logging.info(f"Found {len(key_idxs)} significant moments with threshold {min_significant_change:.4f}s")
    logging.info(f"Total lap delta: {total_lap_delta:.3f}s")
    if len(key_idxs) > 0:
        logging.info(f"Key moment times: {[f'{drv1_time[idx]:.1f}s' for idx in key_idxs]}")
        logging.info(f"Delta changes: {[f'{delta_diff[idx]:.3f}s' for idx in key_idxs]}")
    else:
        logging.warning(f"No key moments found! Max delta_diff: {np.max(np.abs(delta_diff)):.4f}s")

    # Telemetry channels to plot
    telemetry_metrics = ["Throttle", "Brakes", "RPM", "Speed"]

    # --- Plotting ---
    rcParams['font.family'] = 'DejaVu Sans'
    fig, axes = plt.subplots(
        nrows=len(telemetry_metrics),
        ncols=1,
        figsize=(22, 16),  # Much wider and taller
        sharex=True,
        gridspec_kw={'hspace': 0.25, 'top': 0.98, 'bottom': 0.07, 'left': 0.07, 'right': 0.98}
    )
    fig.subplots_adjust(hspace=0.18)
    fig.patch.set_facecolor("#111")

    label_font = {"fontsize": 16, "color": "white", "fontweight": "bold"}
    line_effects = [pe.Stroke(linewidth=4, foreground="#222"), pe.Normal()]

    # --- Add Turn Markers and Labels ---
    try:
        circuit_info = session.get_circuit_info()
        if hasattr(circuit_info, 'corners'):
            corners = circuit_info.corners
            for _, turn in corners.iterrows():
                turn_num = str(turn['Number'])
                turn_dist = turn['Distance']
                if (
                    drv1_tel['Distance'].min() <= turn_dist <= drv1_tel['Distance'].max()
                ):
                    turn_time = np.interp(turn_dist, drv1_tel['Distance'], drv1_tel['Time'].dt.total_seconds())
                    for ax in axes:
                        ax.axvline(x=turn_time, color='white', alpha=0.18, linewidth=1, zorder=0)
                    axes[0].text(
                        turn_time,
                        axes[0].get_ylim()[1] * 1.01,
                        turn_num,
                        ha='center', va='bottom',
                        fontsize=11, fontweight='bold',
                        color='white',
                        bbox=dict(facecolor='#444', edgecolor='none', boxstyle='round,pad=0.2', alpha=0.7),
                        zorder=10
                    )
    except Exception as e:
        logging.warning(f"Could not add turn markers: {e}")

    # --- Add Sector Split Markers (restyled, labeled) ---
    try:
        # Sector 2 starts at end of sector 1, sector 3 at end of sector 2
        s2_start = drv1_fastest['Sector1Time'].total_seconds()
        s3_start = s2_start + drv1_fastest['Sector2Time'].total_seconds()
        for ax in axes:
            ax.axvline(x=s2_start, color='#fff', linewidth=2.2, alpha=0.32, linestyle='--', zorder=2)
            ax.axvline(x=s3_start, color='#fff', linewidth=2.2, alpha=0.32, linestyle='--', zorder=2)
        # Add S2 and S3 labels above the lines on axes[0]
        ylim = axes[0].get_ylim()
        label_y = ylim[1] + (ylim[1] - ylim[0]) * 0.04
        axes[0].text(
            s2_start, label_y, 'S2',
            ha='center', va='bottom',
            fontsize=11, fontweight='bold',
            color='white',
            bbox=dict(facecolor='#222', edgecolor='none', boxstyle='round,pad=0.18', alpha=0.85),
            zorder=10
        )
        axes[0].text(
            s3_start, label_y, 'S3',
            ha='center', va='bottom',
            fontsize=11, fontweight='bold',
            color='white',
            bbox=dict(facecolor='#222', edgecolor='none', boxstyle='round,pad=0.18', alpha=0.85),
            zorder=10
        )
    except Exception as e:
        logging.warning(f"Could not add sector split markers: {e}")

    def plot_telemetry(ax, drv1_tel, drv2_tel, metric, drv1_color, drv2_color, drv1_abbr, drv2_abbr, label_font, line_effects):
        ax.plot(
            drv1_tel["Time"].dt.total_seconds(),
            drv1_tel[metric],
            color=drv1_color,
            label=drv1_abbr,
            linewidth=2.2,
            path_effects=line_effects
        )
        ax.plot(
            drv2_tel["Time"].dt.total_seconds(),
            drv2_tel[metric],
            color=drv2_color,
            label=drv2_abbr,
            linewidth=2.2,
            path_effects=line_effects
        )
        ax.set_ylabel(metric, **label_font)

    plot_telemetry(axes[0], drv1_tel, drv2_tel, "Throttle", drv1_color, drv2_color, drv1_abbr, drv2_abbr, label_font, line_effects)
    axes[0].legend(facecolor="#222", edgecolor="white", fontsize=14, labelcolor="white", framealpha=0.85, loc='upper right')
    plot_telemetry(axes[1], drv1_tel, drv2_tel, "Brake", drv1_color, drv2_color, drv1_abbr, drv2_abbr, label_font, line_effects)
    axes[1].set_ylabel("Brakes", **label_font)
    plot_telemetry(axes[2], drv1_tel, drv2_tel, "RPM", drv1_color, drv2_color, drv1_abbr, drv2_abbr, label_font, line_effects)
    plot_telemetry(axes[3], drv1_tel, drv2_tel, "Speed", drv1_color, drv2_color, drv1_abbr, drv2_abbr, label_font, line_effects)
    axes[3].set_ylabel("Speed (km/h)", **label_font)
    axes[3].set_xlabel("Lap Time", **label_font)

    # Styling for all subplots
    for ax in axes:
        ax.set_facecolor("#222")
        ax.grid(True, alpha=0.2, color="white")
        ax.tick_params(colors="white", labelsize=12)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("white")
        ax.spines["bottom"].set_color("white")

    # --- Add Key Moment Annotations ---
    logging.info(f"Starting annotation process with {len(key_idxs)} significant moments")
    
    # Add annotations for key moments
    annotation_colors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#f9ca24', '#f0932b']
    
    for i, idx in enumerate(key_idxs):
        try:
            logging.info(f"Processing annotation {i+1}/{len(key_idxs)} at index {idx}")
            
            # Get telemetry values at this moment
            time_point = drv1_time[idx]
            logging.info(f"Time point for annotation {i}: {time_point}")
            
            # Interpolate telemetry values for both drivers at this moment
            drv1_throttle = np.interp(common_dist[idx], drv1_tel["Distance"], drv1_tel["Throttle"])
            drv2_throttle = np.interp(common_dist[idx], drv2_tel["Distance"], drv2_tel["Throttle"])
            drv1_brake = np.interp(common_dist[idx], drv1_tel["Distance"], drv1_tel["Brake"])
            drv2_brake = np.interp(common_dist[idx], drv2_tel["Distance"], drv2_tel["Brake"])
            drv1_speed = np.interp(common_dist[idx], drv1_tel["Distance"], drv1_tel["Speed"])
            drv2_speed = np.interp(common_dist[idx], drv2_tel["Distance"], drv2_tel["Speed"])
            drv1_rpm = np.interp(common_dist[idx], drv1_tel["Distance"], drv1_tel["RPM"])
            drv2_rpm = np.interp(common_dist[idx], drv2_tel["Distance"], drv2_tel["RPM"])
            
            logging.info(f"Telemetry at moment {i}: T1={drv1_throttle:.1f}, T2={drv2_throttle:.1f}, V1={drv1_speed:.1f}, V2={drv2_speed:.1f}")
            
            # Classify the moment
            moment_description = classify_moment(
                t1=drv1_throttle,
                t2=drv2_throttle,
                b1=drv1_brake,
                b2=drv2_brake,
                v1=drv1_speed,
                v2=drv2_speed,
                r1=drv1_rpm,
                r2=drv2_rpm,
                session_type=session.name
            )
            
            logging.info(f"Moment description: {moment_description}")
            
            # Skip minor/insignificant moments
            if any(word in moment_description.lower() for word in ['minor', 'slight difference', 'small']):
                logging.info(f"Skipping minor moment: {moment_description}")
                continue
            
            # Add vertical line across all plots
            annotation_color = annotation_colors[i % len(annotation_colors)]
            for ax_idx, ax in enumerate(axes):
                ax.axvline(x=time_point, color=annotation_color, alpha=0.3, linewidth=1, linestyle='--', zorder=10)
            
            # Determine which plot the annotation should go on based on content
            plot_names = ["Throttle", "Brake", "RPM", "Speed"]
            target_plot_idx = 0  # Default to Throttle plot
            
            # Analyze the moment description to determine best plot placement
            description_lower = moment_description.lower()
            
            # Priority order for keyword matching (most specific first)
            if any(word in description_lower for word in ['brake', 'braking', 'stopping', 'trail']):
                target_plot_idx = 1  # Brake plot
            elif any(word in description_lower for word in ['rpm', 'gear', 'shift', 'engine', 'rev']):
                target_plot_idx = 2  # RPM plot  
            elif any(word in description_lower for word in ['speed', 'velocity', 'fast', 'slow', 'mph', 'km/h', 'corner exit', 'straight']):
                target_plot_idx = 3  # Speed plot
            elif any(word in description_lower for word in ['throttle', 'acceleration', 'power', 'pedal', 'gas']):
                target_plot_idx = 0  # Throttle plot
            else:
                # If no specific keywords, analyze the telemetry data to determine most relevant plot
                throttle_diff = abs(drv1_throttle - drv2_throttle)
                brake_diff = abs(drv1_brake - drv2_brake)
                speed_diff = abs(drv1_speed - drv2_speed)
                rpm_diff = abs(drv1_rpm - drv2_rpm) if drv1_rpm > 0 and drv2_rpm > 0 else 0
                
                # Find which telemetry channel has the biggest difference
                diffs = [throttle_diff, brake_diff, rpm_diff/100, speed_diff/10]  # Normalize for comparison
                target_plot_idx = diffs.index(max(diffs))
                
                logging.info(f"No keywords matched, using telemetry analysis: T={throttle_diff:.1f}, B={brake_diff:.1f}, R={rpm_diff:.0f}, S={speed_diff:.1f} -> {plot_names[target_plot_idx]}")
            
            # Add annotation text to the determined plot
            ax = axes[target_plot_idx]
            y_min, y_max = ax.get_ylim()
            y_range = y_max - y_min
            y_position = y_max + (y_range * 0.02)  # Slightly above the top of the plot
            
            ax.annotate(
                moment_description,
                xy=(time_point, y_max),
                xytext=(time_point, y_position),
                ha='center',
                va='bottom',
                color=annotation_color,
                fontsize=9,
                fontweight='bold',
                bbox=dict(
                    boxstyle="round,pad=0.3",
                    facecolor='black',
                    alpha=0.9,
                    edgecolor=annotation_color,
                    linewidth=1.5
                ),
                path_effects=line_effects,
                zorder=11,
                clip_on=False  # Allow text to extend outside plot area
            )
            
            logging.info(f"Placed annotation '{moment_description}' on {plot_names[target_plot_idx]} plot")
            
            logging.info(f"Added annotation to all plots: '{moment_description}' at {time_point:.1f}s with color {annotation_color}")
            
        except Exception as e:
            logging.error(f"Failed to annotate moment {i}: {e}")
            import traceback
            logging.error(traceback.format_exc())
            continue
    
    logging.info(f"Finished processing {len(key_idxs)} annotations")

    # Prepare sector data with correct coloring
    drv1_sectors = []
    drv2_sectors = []
    for i, (s1, s2) in enumerate(zip(drv1_sector_times, drv2_sector_times)):
        sector_num = i + 1
        s1_time = s1.total_seconds() if not pd.isnull(s1) else None
        s2_time = s2.total_seconds() if not pd.isnull(s2) else None
        session_best = session_best_sector_times[i]
        # Driver 1 pill color
        if s1_time is not None and s1_time == session_best:
            bg_color_1 = "#a020f0"  # Purple
        elif s1_time is not None and s1_time == drv1_fastest[f"Sector{sector_num}Time"].total_seconds():
            bg_color_1 = "#22c55e"  # Green
        else:
            bg_color_1 = "#fbbf24"  # Yellow
        # Driver 2 pill color
        if s2_time is not None and s2_time == session_best:
            bg_color_2 = "#a020f0"  # Purple
        elif s2_time is not None and s2_time == drv2_fastest[f"Sector{sector_num}Time"].total_seconds():
            bg_color_2 = "#22c55e"  # Green
        else:
            bg_color_2 = "#fbbf24"  # Yellow
        # Text color: use team color for purple/green, dark for yellow
        color_1 = drv1_color if bg_color_1 in ["#a020f0", "#22c55e"] else "#222"
        color_2 = drv2_color if bg_color_2 in ["#a020f0", "#22c55e"] else "#222"
        drv1_sectors.append({
            "time": f"{s1_time:.3f}s" if s1_time is not None else "N/A",
            "color": color_1,
            "bg_color": bg_color_1,
            "is_personal_best": s1_time == drv1_fastest[f"Sector{sector_num}Time"].total_seconds() if s1_time is not None else False,
            "is_overall_best": s1_time == session_best if s1_time is not None else False
        })
        drv2_sectors.append({
            "time": f"{s2_time:.3f}s" if s2_time is not None else "N/A",
            "color": color_2,
            "bg_color": bg_color_2,
            "is_personal_best": s2_time == drv2_fastest[f"Sector{sector_num}Time"].total_seconds() if s2_time is not None else False,
            "is_overall_best": s2_time == session_best if s2_time is not None else False
        })

    # 🔥 LAP TIME COMPARISON: Add lap time info
    drv1_lap_time = drv1_fastest["LapTime"].total_seconds()
    drv2_lap_time = drv2_fastest["LapTime"].total_seconds()
    faster_driver = drv1_abbr if drv1_lap_time < drv2_lap_time else drv2_abbr
    delta = abs(drv1_lap_time - drv2_lap_time)
    time_info = f"{faster_driver} faster by {delta:.3f}s"

    # 🔥 SAVE PLOT to buffer
    plot_buffer = BytesIO()
    plt.savefig(
        plot_buffer,
        format="png",
        dpi=150,
        bbox_inches="tight",
        facecolor="#111",
        edgecolor="none",
    )
    plt.close(fig)
    plot_buffer.seek(0)

    # 🔥 RETURN values
    drv1_lap_time_str = f"{drv1_lap_time:.3f}s"
    drv2_lap_time_str = f"{drv2_lap_time:.3f}s"

    sector_gaps = [
        drv1_sector_times[i] - session_best_sector_times[i]
        for i in range(3)
    ]

    # Get actual qualifying positions from session results
    results = session.results
    drv1_result = results[results['Abbreviation'] == drv1_abbr]
    drv2_result = results[results['Abbreviation'] == drv2_abbr]
    drv1_position = int(drv1_result['Position'].iloc[0]) if not drv1_result.empty else 0
    drv2_position = int(drv2_result['Position'].iloc[0]) if not drv2_result.empty else 0

    # After calculating sector times and lap times, add F1 TV panel fields for both drivers
    # Get driver info for position and team color
    drv1_info = session.get_driver(drv1_abbr)
    drv2_info = session.get_driver(drv2_abbr)
    drv1_team_color = drv1_color
    drv2_team_color = drv2_color
    drv1_code = drv1_abbr
    drv2_code = drv2_abbr
    # Lap gap to leader (session best lap)
    session_best_lap_time = min(drv1_lap_time, drv2_lap_time)
    drv1_lap_gap = f"+{drv1_lap_time - session_best_lap_time:.3f}" if drv1_lap_time > session_best_lap_time else "+0.000"
    drv2_lap_gap = f"+{drv2_lap_time - session_best_lap_time:.3f}" if drv2_lap_time > session_best_lap_time else "+0.000"
    # Add sector label and F1 color class for template
    for i, sector in enumerate(drv1_sectors):
        sector["label"] = f"S{i+1}"
        if sector["bg_color"] == "#a020f0":
            sector["f1_color"] = "purple"
        elif sector["bg_color"] == "#22c55e":
            sector["f1_color"] = "green"
        else:
            sector["f1_color"] = "yellow"
        # Add gap to session best for each sector
        session_best = session_best_sector_times[i]
        s_time = float(sector["time"].replace("s", "")) if sector["time"] != "N/A" else None
        if s_time is not None and session_best is not None:
            session_best_sec = session_best.total_seconds() if hasattr(session_best, 'total_seconds') else float(session_best)
            gap = s_time - session_best_sec
            sector["gap"] = f"+{gap:.3f}" if gap > 0.001 else "+0.000"
        else:
            sector["gap"] = "N/A"
    for i, sector in enumerate(drv2_sectors):
        sector["label"] = f"S{i+1}"
        if sector["bg_color"] == "#a020f0":
            sector["f1_color"] = "purple"
        elif sector["bg_color"] == "#22c55e":
            sector["f1_color"] = "green"
        else:
            sector["f1_color"] = "yellow"
        session_best = session_best_sector_times[i]
        s_time = float(sector["time"].replace("s", "")) if sector["time"] != "N/A" else None
        if s_time is not None and session_best is not None:
            session_best_sec = session_best.total_seconds() if hasattr(session_best, 'total_seconds') else float(session_best)
            gap = s_time - session_best_sec
            sector["gap"] = f"+{gap:.3f}" if gap > 0.001 else "+0.000"
        else:
            sector["gap"] = "N/A"
    # Determine leader (fastest lap)
    if drv1_lap_time < drv2_lap_time:
        leader_abbr = drv1_abbr
    else:
        leader_abbr = drv2_abbr

    # Create enhanced telemetry context with annotation information
    global current_telemetry_context
    current_telemetry_context = extract_telemetry_context(
        session, drv1_abbr, drv2_abbr
    )
    
    # Add annotation information to context
    annotation_info = []
    for i, idx in enumerate(key_idxs):
        try:
            time_point = drv1_time[idx]
            drv1_throttle = np.interp(common_dist[idx], drv1_tel["Distance"], drv1_tel["Throttle"])
            drv2_throttle = np.interp(common_dist[idx], drv2_tel["Distance"], drv2_tel["Throttle"])
            drv1_brake = np.interp(common_dist[idx], drv1_tel["Distance"], drv1_tel["Brake"])
            drv2_brake = np.interp(common_dist[idx], drv2_tel["Distance"], drv2_tel["Brake"])
            drv1_speed = np.interp(common_dist[idx], drv1_tel["Distance"], drv1_tel["Speed"])
            drv2_speed = np.interp(common_dist[idx], drv2_tel["Distance"], drv2_tel["Speed"])
            
            moment_description = classify_moment(
                t1=drv1_throttle, t2=drv2_throttle, b1=drv1_brake, b2=drv2_brake,
                v1=drv1_speed, v2=drv2_speed, r1=0, r2=0,  # Skip RPM for context
                session_type=session.name
            )
            
            annotation_info.append({
                "time": f"{time_point:.1f}s",
                "description": moment_description,
                "telemetry": {
                    f"{drv1_abbr}": {"throttle": f"{drv1_throttle:.0f}%", "brake": f"{drv1_brake:.0f}%", "speed": f"{drv1_speed:.0f} km/h"},
                    f"{drv2_abbr}": {"throttle": f"{drv2_throttle:.0f}%", "brake": f"{drv2_brake:.0f}%", "speed": f"{drv2_speed:.0f} km/h"}
                }
            })
        except:
            continue

    # Add visual plot information to context
    current_telemetry_context["plot_annotations"] = annotation_info
    current_telemetry_context["visual_elements"] = {
        "total_annotations": len(annotation_info),
        "annotation_times": [ann["time"] for ann in annotation_info],
        "key_moments": [ann["description"] for ann in annotation_info]
    }
    
    logging.info(f"Enhanced telemetry context with {len(annotation_info)} annotations")

    # Return all fields for template, including leader_abbr
    return (
        plot_buffer,
        drv1_code,
        f"{drv1_lap_time:.3f}s",
        drv2_code,
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
    )


driver_info = {
    "position": 6,
    "name": "MAGNUSSEN",
    "team_color": "#00D2BE",
    "tyre": "soft",  # or "medium", "hard"
    "lap_time": "1:13.103",
    "lap_gap": "+0.874",
    "sectors": [
        {"label": "S1", "time": "22.123", "gap": "+0.050", "color": "purple"},
        {"label": "S2", "time": "28.456", "gap": "+0.200", "color": "yellow"},
        {"label": "S3", "time": "22.524", "gap": "+0.000", "color": "green"},
    ]
}

@app.errorhandler(Exception)
def handle_exception(e):
    # pass through HTTP errors
    if isinstance(e, HTTPException):
        return e

    # now you're handling non-HTTP exceptions only
    return render_template("error.html", error_message=str(e)), 500
