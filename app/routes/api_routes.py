"""
API Routes

Handles F1 data API endpoints (races, drivers, moment analysis).
"""

import os
import logging
import requests
from datetime import datetime
from flask import request, jsonify, Response, stream_with_context, session as flask_session
from session_manager import get_races_cached
import fastf1 as f1
from app.services.context_service import retrieve_telemetry_context
from app.middleware.cleanup import get_session_manager
from app.metrics import REQUEST_COUNT, REQUEST_LATENCY

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")


def register_api_routes(app):
    """Register API routes"""

    @app.route("/get_races", methods=["POST"])
    def get_races():
        """Get list of races for a given year"""
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

                # Filter out future races if current year is selected
                current_year = datetime.now().year
                if year == current_year:
                    remaining_events = set(f1.get_events_remaining()["EventName"])
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

                logging.info(f"🔍 Loading drivers for: {year} - {race} - {session_name}")

                session_map = {"Qualifying": "Q", "Race": "R"}
                session_type = session_map.get(session_name, session_name)

                # Use lightweight method that doesn't load full telemetry
                session_manager = get_session_manager()
                session = session_manager.get_drivers_only(year, race, session_type)

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
                    "num_predict": -1,  # Allow model to complete response naturally
                    "stop": ["</s>", "\n\n\n\n", "---"]  # Stop tokens
                }
            }

            resp = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json=request_data,
                stream=request_data.get("stream", False),
                timeout=120,
            )

            if not resp.ok:
                logging.error(f"Ollama API error: {resp.status_code} - {resp.text}")
                return jsonify({"error": f"AI service error: {resp.status_code}"}), 502

            if request_data.get("stream", False):
                return Response(
                    stream_with_context(resp.iter_content(chunk_size=1024)),
                    content_type=resp.headers.get("content-type"),
                    status=resp.status_code,
                )
            else:
                # Parse Ollama response and return just the response text
                try:
                    ollama_response = resp.json()
                    response_text = ollama_response.get("response", "")

                    if not response_text:
                        logging.error(f"Empty response from Ollama: {ollama_response}")
                        return jsonify({"error": "AI returned empty response"}), 500

                    return jsonify({
                        "response": response_text,
                        "model": ollama_response.get("model", ""),
                        "done": ollama_response.get("done", True)
                    })
                except Exception as e:
                    logging.error(f"Failed to parse Ollama response: {e}")
                    return jsonify({"error": "Failed to parse AI response"}), 500

        except Exception as e:
            logging.error(f"Moment analysis error: {e}")
            return jsonify({"error": str(e)}), 500
