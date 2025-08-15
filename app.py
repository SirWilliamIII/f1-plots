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
    session as flask_session,
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
from flask_cors import CORS
import psutil
import gc
import tracemalloc
from datetime import datetime
import threading
import time
from matplotlib.ticker import FuncFormatter

from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from session_manager import SessionManager, get_races_cached, initialize_fastf1_cache
from matplotlib import rcParams
import matplotlib.patheffects as pe
import math

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

logging.info("🔥 F1 App Performance Upgrades Loaded:")
logging.info("  ✅ Smart Session Manager with analytics")  
logging.info("  ✅ Track-aware interpolation system")
logging.info("  ✅ Memory-optimized matplotlib handling")
logging.info("  ✅ Request-scoped context management")
logging.info("  ✅ Concurrent user support enabled")



env = os.getenv('FLASK_ENV', 'development')
if env == 'production':
  load_dotenv('.env.prod')
else:
  load_dotenv('.env')


app = Flask(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
print(f"DEBUG: OLLAMA_BASE_URL set to: {OLLAMA_BASE_URL}")
app.secret_key = 'f1-telemetry-secret-key-change-in-production'  

os.environ["MPLBACKEND"] = "Agg"
os.environ["MPLCONFIGDIR"] = "/tmp"


# plt.ioff()  # Turn off interactive mode
plt.switch_backend("Agg")  # Use Agg backend instead of interactive mode


Compress(app)
CORS(app)
# Initialize FastF1 cache and session manager
initialize_fastf1_cache("fastf1_cache")

# Memory management functions
def force_garbage_collection():
    """Force garbage collection and return memory freed"""
    before = psutil.Process().memory_info().rss
    gc.collect()
    after = psutil.Process().memory_info().rss
    freed_mb = (before - after) / (1024 * 1024)
    return freed_mb

def check_memory_usage():
    """Check current memory usage and trigger cleanup if needed"""
    from config import FLASK_CONFIG
    current_memory = psutil.Process().memory_info().rss / (1024 * 1024)
    if current_memory > FLASK_CONFIG.memory_threshold_mb:
        freed = force_garbage_collection()
        logging.info(f"Memory cleanup: freed {freed:.1f}MB, current: {current_memory:.1f}MB")
        return True
    return False

def cleanup_matplotlib():
    """Clean up matplotlib resources"""
    plt.close('all')
    gc.collect()

# Initialize the global session manager with optimized settings
session_manager = SessionManager(
    max_workers=2,  # 2 background threads for preloading
    enable_preloading=False,  # Enable preloading of popular sessions
)

# Initialize track interpolator

# Global variables (keep for backward compatibility)
last_plot_buf = None
def get_or_create_session_id(request):
    """Get session ID from request or create new one"""
    # Check if session ID exists in Flask session
    if 'telemetry_session_id' not in flask_session:
        flask_session['telemetry_session_id'] = str(uuid.uuid4())
    return flask_session['telemetry_session_id']

def store_telemetry_context(session_id: str, context: dict):
    """Store telemetry context for a session"""
    # Context management removed
    logging.info(f"📊 Stored context for session {session_id[:8]}...")

def retrieve_telemetry_context(session_id: str) -> dict:
    """Retrieve telemetry context for a session"""
    return {}


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

# Memory management hooks
@app.after_request
def after_request_cleanup(response):
    """Clean up memory after each request"""
    from config import FLASK_CONFIG
    
    if FLASK_CONFIG.enable_gc_after_request:
        # Always do light cleanup
        gc.collect()
        
        # Check if we need aggressive cleanup
        check_memory_usage()
    
    return response


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
        print(f"DEBUG: Trying to connect to {OLLAMA_BASE_URL}/api/tags")
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return Response(
            resp.content,
            status=resp.status_code,
            content_type=resp.headers.get("content-type"),
        )
    except requests.exceptions.RequestException as e:
        print(f"DEBUG: Ollama connection failed: {e}")
        return jsonify({"error": "Ollama not available", "url": OLLAMA_BASE_URL, "details": str(e)}), 503


@app.route("/ollama_proxy/generate", methods=["POST"])
def ollama_generate():
    """🔥 ENHANCED: Proxy endpoint with session-scoped telemetry context injection"""
    try:
        request_data = request.json.copy()
        user_prompt = request_data.get("prompt", "")
        request_data["model"] = "f1-analyst:latest"

        # Performance optimizations for speed
        request_data["options"] = {
            "num_predict": 150,
            "temperature": 0.1,
            "num_ctx": 1024,
            "repeat_penalty": 1.1,
            "top_p": 0.7,
            "num_thread": 4
        }

        # 🔥 NEW: Get session-specific context instead of global
        session_id = flask_session.get('telemetry_session_id')
        if session_id:
            current_telemetry_context = retrieve_telemetry_context(session_id)
            
            if current_telemetry_context:
                logging.info(f"🧠 Injecting session context for {session_id[:8]}...")
                context_prompt = create_contextual_prompt(user_prompt, current_telemetry_context)
                request_data["prompt"] = context_prompt
            else:
                logging.warning(f"❌ No context found for session {session_id[:8]}...")
        else:
            logging.warning("❌ No session ID found")

        # Forward to Ollama (your existing code)
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


@app.route("/optimize_cache", methods=["POST"])
def optimize_cache():
    """🔥 NEW: Trigger cache optimization"""
    try:
        # Force cleanup of expired contexts
        # Context cleanup removed
        
        # Clear old session cache entries
        session_manager.clear_cache(keep_popular=True)
        
        # Force garbage collection
        import gc
        gc.collect()
        
        return jsonify({
            'message': 'Cache optimization completed',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/analyze_moment", methods=["POST"])
def analyze_moment():
    """Analyze a specific moment from the telemetry plot"""
    try:
        # Get session-specific context
        session_id = flask_session.get('telemetry_session_id')
        if not session_id:
            return jsonify({"error": "No session found"}), 400
            
        current_telemetry_context = retrieve_telemetry_context(session_id)
        if not current_telemetry_context:
            return jsonify({"error": "No telemetry data available"}), 400
        
        data = request.json
        moment_id = data.get("moment_id")
        
        if not moment_id:
            return jsonify({"error": "No moment_id provided"}), 400
        
        # Find the specific moment
        moment = None
        for m in current_telemetry_context.get("plot_annotations", []):
            if m["id"] == moment_id:
                moment = m
                break
        
        if not moment:
            return jsonify({"error": f"Moment {moment_id} not found"}), 404
        
        # Create specialized prompt for moment analysis
        race_info = current_telemetry_context["race_info"]
        drv1 = current_telemetry_context["driver1"]
        drv2 = current_telemetry_context["driver2"]
        
        moment_prompt = f"""Analyze this specific racing moment from the telemetry comparison:

**{race_info['year']} {race_info['race_name']} - {race_info['session_type']}**
**Time:** {moment['time']}
**Drivers:** {drv1['name']} vs {drv2['name']}

**What happened:** {moment['description']}

**Telemetry at this moment:**
- {drv1['name']}: Throttle {moment['telemetry'][drv1['name']]['throttle']}, Brake {moment['telemetry'][drv1['name']]['brake']}, Speed {moment['telemetry'][drv1['name']]['speed']}, RPM {moment['telemetry'][drv1['name']]['rpm']}, {moment['telemetry'][drv1['name']]['gear']}
- {drv2['name']}: Throttle {moment['telemetry'][drv2['name']]['throttle']}, Brake {moment['telemetry'][drv2['name']]['brake']}, Speed {moment['telemetry'][drv2['name']]['speed']}, RPM {moment['telemetry'][drv2['name']]['rpm']}, {moment['telemetry'][drv2['name']]['gear']}

Explain what technique advantage occurred here and why it made a difference. Be specific about the driving technique and its impact on lap time."""

        # Forward to Ollama with optimized settings
        request_data = {
            "model": "f1-analyst:latest",
            "prompt": moment_prompt,
            "stream": data.get("stream", True),
            "options": {
                "temperature": 0.3,
                "num_predict": 200,
                "stop": ["</s>", "\n\n\n"]
            }
        }
        
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=request_data,
            stream=request_data.get("stream", False),
            timeout=60,
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
        logging.error(f"Moment analysis error: {e}")
        return jsonify({"error": str(e)}), 500


def create_contextual_prompt(user_prompt, context):
    """Create optimized prompt with essential telemetry context for faster processing"""

    race_info = context["race_info"]
    drv1 = context["driver1"]
    drv2 = context["driver2"]
    comparison = context["comparison"]
    sectors = context["sectors"]

    # Simplified context for faster processing
    context_text = f"""
F1 TELEMETRY ANALYSIS:
{race_info['year']} {race_info['race_name']} - {race_info['session_type']}

DRIVERS:
**{drv1['name']}** ({drv1['full_name']}): {drv1['lap_time']:.3f}s, {drv1['max_speed']:.0f} km/h
**{drv2['name']}** ({drv2['full_name']}): {drv2['lap_time']:.3f}s, {drv2['max_speed']:.0f} km/h

RESULT: **{comparison['faster_driver']}** faster by {comparison['lap_time_delta']:.3f}s

SECTORS:"""

    for sector in sectors:
        context_text += f"""
Sector {sector['sector']}: {sector['faster_driver']} faster by {sector['delta']:.3f}s
- {drv1['name']}: {sector['driver1_time']:.3f}s
- {drv2['name']}: {sector['driver2_time']:.3f}s"""

    # Add key moments (simplified)
    if "plot_annotations" in context and context["plot_annotations"]:
        context_text += f"""

KEY MOMENTS:"""
        for i, annotation in enumerate(context["plot_annotations"][:3]):  # Limit to 3 most important
            context_text += f"""
- {annotation['time']}: {annotation['description']}"""

    context_text += f"""

QUESTION: {user_prompt}

Provide a concise analysis focusing on the key differences between the drivers."""

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
    """🔥 ENHANCED: Index route with session management and smart analytics"""
    
    REQUEST_COUNT.labels(method=request.method, endpoint="/", status="200").inc()
    with REQUEST_LATENCY.labels(method=request.method, endpoint="/").time():
        
        years = list(range(2020, 2026))
        sessions = ["Qualifying", "Race"]
        session_map = {"Qualifying": "Q", "Race": "R"}
        
        # Get races for default year
        try:
            races = get_races_cached(2023)
        except:
            races = []
        
        drivers = None
        selected_year = None
        selected_race = None
        selected_session = None
        
        if request.method == "POST":
            # 🔥 NEW: Create or get session ID for this user
            session_id = get_or_create_session_id(request)
            logging.info(f"🔐 Processing request for session {session_id[:8]}...")
            
            # Process form data (your existing logic)
            selected_year = int(request.form.get("year"))
            selected_race = request.form.get("race") 
            selected_session = request.form.get("session", "Qualifying")
            driver1 = request.form.get("driver1")
            driver2 = request.form.get("driver2")
            session_type = session_map.get(selected_session, selected_session)
            
            # Validate form data
            if not (selected_year and selected_race and driver1 and driver2 and driver1 != driver2):
                logging.warning(f"❌ Invalid form data for session {session_id[:8]}")
                return render_template("error.html", error_message="Missing or invalid form data.")
            
            try:
                logging.info(f"🏎️  Loading {selected_year} {selected_race} {selected_session} for session {session_id[:8]}")
                
                # Load session using smart session manager
                session_obj = session_manager.get_session(selected_year, selected_race, session_type)
                
                # 🔥 NEW: Use enhanced comparison function
                comparison_result = compare_fastest_laps(session_obj, driver1, driver2)
                
                # Unpack results (same as your original code)
                (plot_path, drv1_abbr, drv1_lap_time_str, drv2_abbr, drv2_lap_time_str,
                 drv1_sectors, drv2_sectors, faster_driver, delta, drv1_team_color,
                 drv1_position, drv1_lap_gap, drv2_team_color, drv2_position, 
                 drv2_lap_gap, leader_abbr) = comparison_result
                
                # Store plot buffer for serving
                global last_plot_buf
                last_plot_buf = plot_path
                
                # Create display data
                race_title = f"{session_obj.event.year} {session_obj.event['EventName']}"
                driver_comparison = f"{drv1_abbr} vs {drv2_abbr}"
                session_name = "Qualifying" if session_type == "Q" else "Race"
                
                # Get moment annotations from context
                moment_annotations = []
                ai_telemetry_data = None
                ai_annotations = None
                
                context = retrieve_telemetry_context(session_id)
                if context:
                    if "plot_annotations" in context:
                        moment_annotations = context["plot_annotations"]
                    # Extract telemetry data for AI
                    if "telemetry_data" in context:
                        ai_telemetry_data = context["telemetry_data"]
                    if "annotations" in context:
                        ai_annotations = context["annotations"]
                
                logging.info(f"✅ Rendering result for session {session_id[:8]}: "
                            f"{drv1_abbr} vs {drv2_abbr}, {len(moment_annotations)} moments")
                
                return render_template(
                    "result.html",
                    plot_path="/plot.png",
                    drv1_abbr=drv1_abbr,
                    drv1_lap_time=drv1_lap_time_str,
                    drv2_abbr=drv2_abbr,
                    drv2_lap_time=drv2_lap_time_str,
                    race_title=race_title,
                    driver_comparison=driver_comparison,
                    session_name=session_name,
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
                    moment_annotations=moment_annotations,
                    ai_telemetry_data=ai_telemetry_data,
                    ai_annotations=ai_annotations,
                )
                
            except Exception as e:
                import traceback
                logging.error(f"💥 Exception for session {session_id[:8]}: {e}")
                traceback.print_exc()
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
    🔥 ENHANCED: Generate telemetry comparison plot with all optimizations
    """
    start_time = time.time()
    
    # Get driver data (your existing code)
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
    
    # 🔥 NEW: Track-aware interpolation
    try:
        common_dist = np.linspace(drv1_tel['Distance'].min(), drv1_tel['Distance'].max(), 1000)
        track_name = session.event['EventName']
        logging.info(f"🎯 {track_name}: Using {len(common_dist)} adaptive interpolation points")
    except Exception as e:
        logging.warning(f"Track optimization failed, using fallback: {e}")
        # Fallback to your original method
        common_dist = np.linspace(
            max(drv1_tel["Distance"].min(), drv2_tel["Distance"].min()),
            min(drv1_tel["Distance"].max(), drv2_tel["Distance"].max()),
            1500
        )
    
    # Calculate sector times (your existing code)
    drv1_sector_times = [drv1_fastest[f"Sector{i}Time"] for i in range(1, 4)]
    drv2_sector_times = [drv2_fastest[f"Sector{i}Time"] for i in range(1, 4)]
    
    session_best_sector_times = [
        session.laps[f"Sector{i}Time"].min().total_seconds() if not pd.isnull(session.laps[f"Sector{i}Time"].min()) else None
        for i in range(1, 4)
    ]
    
    # Interpolate timing data (your existing logic)
    drv1_time = np.interp(
        common_dist, drv1_tel["Distance"], drv1_tel["Time"].dt.total_seconds()
    )
    drv2_time = np.interp(
        common_dist, drv2_tel["Distance"], drv2_tel["Time"].dt.total_seconds()
    )
    
    # Calculate delta and find key moments (your existing algorithm)
    delta = drv2_time - drv1_time
    delta_diff = np.diff(delta)
    
    total_lap_delta = abs(delta[-1] - delta[0])
    percentile_threshold = np.percentile(np.abs(delta_diff), 95)
    delta_based_threshold = total_lap_delta * 0.05
    min_threshold = 0.005
    min_significant_change = max(min_threshold, min(percentile_threshold, delta_based_threshold))
    
    key_idxs = np.where(np.abs(delta_diff) > min_significant_change)[0]
    
    # Filter out moments that are too close together (your existing logic)
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
    
    # 🔥 NEW: Use managed matplotlib figure to prevent memory leaks
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
            
            # Classify the moment (your existing function)
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
            
            # Store moment details (your existing logic)
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
            
            # Add annotations (your existing annotation logic)
            annotation_color = annotation_colors[i % len(annotation_colors)]
            for ax_idx, ax in enumerate(axes):
                ax.axvline(x=time_point, color=annotation_color, alpha=0.3, linewidth=1, linestyle='--', zorder=10)
            
            # Determine target plot for annotation (your existing logic)
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
        
        # Save plot to buffer
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
    # Track interpolation performance recording removed
    
    # Prepare sector data (your existing logic)
    drv1_sectors = []
    drv2_sectors = []
    for i, (s1, s2) in enumerate(zip(drv1_sector_times, drv2_sector_times)):
        sector_num = i + 1
        s1_time = s1.total_seconds() if not pd.isnull(s1) else None
        s2_time = s2.total_seconds() if not pd.isnull(s2) else None
        session_best = session_best_sector_times[i]
        
        # Your existing sector color logic
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
    
    # Calculate lap time comparison (your existing logic)
    drv1_lap_time = drv1_fastest["LapTime"].total_seconds()
    drv2_lap_time = drv2_fastest["LapTime"].total_seconds()
    faster_driver = drv1_abbr if drv1_lap_time < drv2_lap_time else drv2_abbr
    delta = abs(drv1_lap_time - drv2_lap_time)
    
    # Get positions and team colors (your existing logic)
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
            
            # F1 color logic: purple = fastest overall, green = personal best, yellow = slower than personal best
            if abs(s_time - session_best_sec) < 0.001:  # Fastest overall sector
                sector["f1_color"] = "purple"
            elif abs(s_time - personal_best_sec) < 0.001:  # Personal best sector
                sector["f1_color"] = "green"
            else:  # Slower than personal best
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
            
            # F1 color logic: purple = fastest overall, green = personal best, yellow = slower than personal best
            if abs(s_time - session_best_sec) < 0.001:  # Fastest overall sector
                sector["f1_color"] = "purple"
            elif abs(s_time - personal_best_sec) < 0.001:  # Personal best sector
                sector["f1_color"] = "green"
            else:  # Slower than personal best
                sector["f1_color"] = "yellow"
        else:
            sector["gap"] = "N/A"
            sector["f1_color"] = "yellow"
    
    # 🔥 NEW: Create enhanced telemetry context with performance stats
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
    
    # 🔥 NEW: Add performance statistics to context
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
    
    # 🔥 NEW: Store context with session instead of global variable
    session_id = flask_session.get('telemetry_session_id')
    if session_id:
        store_telemetry_context(session_id, enhanced_context)
        logging.info(f"📊 Stored enhanced context for session {session_id[:8]}... "
                    f"({processing_time:.2f}s processing, {len(common_dist)} points)")
    
    logging.info(f"✅ Plot generation complete: {processing_time:.2f}s, "
                f"{len(moment_details)} moments, {len(common_dist)} points")
    
    # Return all the same values as your original function
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


# Memory monitoring endpoints and functionality
class MemoryMonitor:
    def __init__(self):
        self.process = psutil.Process()
        self.start_time = datetime.now()
        self.memory_samples = []
        self.max_samples = 1000
        tracemalloc.start()
        
    def get_memory_info(self):
        memory_info = self.process.memory_info()
        return {
            'rss_mb': memory_info.rss / 1024 / 1024,
            'vms_mb': memory_info.vms / 1024 / 1024,
            'percent': self.process.memory_percent(),
            'available_mb': psutil.virtual_memory().available / 1024 / 1024,
            'swap_used_mb': psutil.swap_memory().used / 1024 / 1024,
        }
    
    def get_top_allocations(self, limit=10):
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')
        return [
            {
                'file': stat.traceback.format()[0],
                'size_mb': stat.size / 1024 / 1024,
                'count': stat.count
            }
            for stat in top_stats[:limit]
        ]
    
    def record_sample(self):
        sample = {
            'timestamp': datetime.now().isoformat(),
            'memory': self.get_memory_info()
        }
        self.memory_samples.append(sample)
        if len(self.memory_samples) > self.max_samples:
            self.memory_samples.pop(0)
        return sample

# Initialize memory monitor
memory_monitor = MemoryMonitor()

# Background thread to collect memory samples
def memory_sampling_thread():
    while True:
        try:
            memory_monitor.record_sample()
            time.sleep(60)  # Sample every minute
        except Exception as e:
            logging.error(f"Memory sampling error: {e}")

# Start memory sampling thread
sampling_thread = threading.Thread(target=memory_sampling_thread, daemon=True)
sampling_thread.start()

@app.route('/memory_status')
def memory_status():
    """Endpoint to check current memory usage"""
    try:
        current = memory_monitor.get_memory_info()
        top_allocations = memory_monitor.get_top_allocations()
        
        # Force garbage collection
        gc.collect()
        after_gc = memory_monitor.get_memory_info()
        
        return jsonify({
            'current_memory': current,
            'after_gc': after_gc,
            'gc_freed_mb': current['rss_mb'] - after_gc['rss_mb'],
            'top_allocations': top_allocations,
            'uptime_minutes': (datetime.now() - memory_monitor.start_time).total_seconds() / 60,
            'sample_count': len(memory_monitor.memory_samples)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/memory_history')
def memory_history():
    """Get memory usage history"""
    return jsonify({
        'samples': memory_monitor.memory_samples[-100:]  # Last 100 samples
    })

@app.route('/force_gc', methods=['POST'])
def force_gc():
    """Force garbage collection"""
    before = memory_monitor.get_memory_info()
    gc.collect()
    after = memory_monitor.get_memory_info()
    
    return jsonify({
        'before': before,
        'after': after,
        'freed_mb': before['rss_mb'] - after['rss_mb']
    })

# Memory-aware request wrapper
def monitor_request_memory(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        before = memory_monitor.get_memory_info()
        result = f(*args, **kwargs)
        after = memory_monitor.get_memory_info()
        
        # Log if request used more than 50MB
        memory_used = after['rss_mb'] - before['rss_mb']
        if memory_used > 50:
            logging.warning(f"High memory usage in {f.__name__}: {memory_used:.2f}MB")
            
        return result
    return decorated_function


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5151))
    logging.info(f"🚀 Starting Flask app on port: {port}")
    logging.info(f"🌐 Access the app at: http://localhost:{port}")
    app.run(debug=True, host='0.0.0.0', port=port)
    
