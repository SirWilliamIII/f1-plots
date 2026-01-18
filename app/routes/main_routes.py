"""
Main Application Routes

Handles the main index route and telemetry comparison.
"""

import logging
from flask import render_template, request
from session_manager import get_races_cached
from app.services.context_service import get_or_create_session_id, store_telemetry_context
from app.plotting.telemetry_plots import compare_fastest_laps, set_last_plot_buffer
from app.services.result_cache import get_cached_result, cache_result
from app.middleware.cleanup import get_session_manager
from app.metrics import REQUEST_COUNT, REQUEST_LATENCY
from app.error_tracking.error_tracker import get_error_tracker, ErrorSeverity


def register_main_routes(app):
    """Register main application routes"""

    @app.route("/", methods=["GET", "POST"])
    def index():
        """Main index route with session management and telemetry comparison"""

        # ✅ FIXED: Don't increment metrics here (wait for after_request)
        # Previously incremented status="200" before knowing actual status
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
                # Create or get session ID for this user
                session_id = get_or_create_session_id(request)
                logging.info(f"🔐 Processing request for session {session_id[:8]}...")

                selected_year = int(request.form.get("year")) if request.form.get("year") else None
                selected_race = request.form.get("race")
                selected_session = request.form.get("session", "Qualifying")
                driver1 = request.form.get("driver1")
                driver2 = request.form.get("driver2")
                session_type = session_map.get(selected_session, selected_session)

                # ✅ FIXED: Validate form data with proper error handling
                if not (selected_year and selected_race and driver1 and driver2):
                    error_msg = 'Please fill in all fields (year, race, session, and both drivers)'
                    logging.warning(f"⚠️  Validation failed: missing fields")
                    return render_template(
                        'index.html',
                        years=years,  # ✅ Include years so template doesn't crash
                        sessions=sessions,  # ✅ Include sessions
                        races=races,
                        error=error_msg,
                        # ✅ Preserve user selections
                        selected_year=selected_year,
                        selected_race=selected_race,
                        selected_session=selected_session
                    ), 400  # ✅ Proper HTTP status code

                if driver1 == driver2:
                    error_msg = f'Please select different drivers (both are currently {driver1})'
                    logging.warning(f"⚠️  Validation failed: duplicate drivers ({driver1})")
                    return render_template(
                        'index.html',
                        years=years,  # ✅ Include all required context
                        sessions=sessions,
                        races=races,
                        error=error_msg,
                        # ✅ Preserve user selections
                        selected_year=selected_year,
                        selected_race=selected_race,
                        selected_session=selected_session
                    ), 400

                try:
                    logging.info(f"🏎️  Loading {selected_year} {selected_race} {selected_session} for session {session_id[:8]}")

                    # Check cache first for instant results
                    cached = get_cached_result(selected_year, selected_race, session_type, driver1, driver2)

                    if cached:
                        comparison_result = cached
                        logging.info(f"⚡ Using cached result for {driver1} vs {driver2}")
                    else:
                        # Load session using smart session manager
                        session_manager = get_session_manager()
                        session_obj = session_manager.get_session(selected_year, selected_race, session_type)

                        # Use enhanced comparison function
                        comparison_result = compare_fastest_laps(session_obj, driver1, driver2)

                        # Cache the result for future requests
                        cache_result(selected_year, selected_race, session_type, driver1, driver2, comparison_result)

                    # Unpack results (including plot annotations)
                    (plot_path, drv1_abbr, drv1_lap_time_str, drv2_abbr, drv2_lap_time_str,
                     drv1_sectors, drv2_sectors, faster_driver, delta, drv1_team_color,
                     drv1_position, drv1_lap_gap, drv2_team_color, drv2_position,
                     drv2_lap_gap, leader_abbr, plot_annotations) = comparison_result

                    # Store plot buffer for serving
                    set_last_plot_buffer(plot_path)

                    # Define session_name before using it
                    session_name = "Qualifying" if session_type == "Q" else "Race"

                    # Store telemetry context with plot annotations for AI analysis
                    session_id = get_or_create_session_id(request)

                    # Build sector comparison data for AI
                    sectors_data = []
                    for i in range(3):
                        if i < len(drv1_sectors) and i < len(drv2_sectors):
                            drv1_sector = drv1_sectors[i]
                            drv2_sector = drv2_sectors[i]
                            # Parse sector times (handle "N/A" cases)
                            try:
                                drv1_time = float(drv1_sector['time'].replace('s', ''))
                                drv2_time = float(drv2_sector['time'].replace('s', ''))
                                delta_time = drv1_time - drv2_time
                                sectors_data.append({
                                    "sector": i + 1,
                                    "driver1_time": drv1_time,
                                    "driver2_time": drv2_time,
                                    "delta": abs(delta_time),
                                    "faster_driver": drv1_abbr if delta_time < 0 else drv2_abbr
                                })
                            except (ValueError, KeyError):
                                # Skip sectors with N/A times
                                pass

                    telemetry_context = {
                        "plot_annotations": plot_annotations,
                        "race_info": {
                            "year": selected_year,
                            "race_name": selected_race,
                            "session_type": session_name
                        },
                        "driver1": {
                            "name": drv1_abbr,
                            "full_name": drv1_abbr,  # Could enhance this later
                            "lap_time": float(drv1_lap_time_str.replace('s', ''))
                        },
                        "driver2": {
                            "name": drv2_abbr,
                            "full_name": drv2_abbr,  # Could enhance this later
                            "lap_time": float(drv2_lap_time_str.replace('s', ''))
                        },
                        "comparison": {
                            "faster_driver": faster_driver,
                            "delta": delta,
                            "lap_time_delta": delta
                        },
                        "sectors": sectors_data
                    }
                    store_telemetry_context(session_id, telemetry_context)

                    # Create display data
                    race_title = f"{session_obj.event.year} {session_obj.event['EventName']}"
                    driver_comparison = f"{drv1_abbr} vs {drv2_abbr}"

                    # Use plot annotations directly from comparison result
                    moment_annotations = plot_annotations
                    ai_telemetry_data = None
                    ai_annotations = None

                    logging.info(f"🔍 Debug: plot_annotations type: {type(plot_annotations)}, length: {len(plot_annotations) if hasattr(plot_annotations, '__len__') else 'no length'}")

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

                    # Capture exception with full context
                    error_tracker = get_error_tracker()
                    error_tracker.capture_exception(
                        e,
                        context={
                            'operation': 'telemetry_comparison',
                            'session_id': session_id,
                            'year': selected_year,
                            'race': selected_race,
                            'session': selected_session,
                            'driver1': driver1,
                            'driver2': driver2,
                            'endpoint': '/'
                        },
                        level=ErrorSeverity.ERROR
                    )

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
