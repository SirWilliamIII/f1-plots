"""
🔥 COMPLETE INTEGRATION GUIDE for F1 App Performance Upgrades

This file contains the exact changes needed to upgrade your existing app.py
Copy these sections into your current app.py file.
"""

# ========================================
# 1. NEW IMPORTS (Add to top of app.py)
# ========================================

from context_manager import (
    managed_figure, 
    global_context_manager, 
    create_user_session,
    get_session_context,
    set_session_context,
    MemoryOptimizedTelemetryProcessor
)
from track_optimizer import TrackAwareInterpolator, create_optimized_distance_array
from session_manager_enhanced import SmartSessionManager
import time

# ========================================
# 2. REPLACE SESSION MANAGER INITIALIZATION
# ========================================

# REPLACE THIS:
# session_manager = SessionManager(max_workers=2, enable_preloading=False)

# WITH THIS:
session_manager = SmartSessionManager(
    max_workers=2,
    enable_preloading=True,  # 🔥 Smart preloading enabled
    max_cache_size=15        # 🔥 Optimized cache size
)

# Create global track interpolator
track_interpolator = TrackAwareInterpolator()

# ========================================
# 3. REPLACE GLOBAL CONTEXT HANDLING
# ========================================

# REMOVE THIS:
# current_telemetry_context = None

# ADD THESE HELPER FUNCTIONS:
def get_or_create_session_id(request):
    """Get session ID from request or create new one"""
    # Check if session ID exists in Flask session
    if 'telemetry_session_id' not in session:
        session['telemetry_session_id'] = create_user_session()
    return session['telemetry_session_id']

def store_telemetry_context(session_id: str, context: dict):
    """Store telemetry context for a session"""
    set_session_context(session_id, context)
    logging.info(f"📊 Stored context for session {session_id[:8]}...")

def retrieve_telemetry_context(session_id: str) -> dict:
    """Retrieve telemetry context for a session"""
    return get_session_context(session_id) or {}

# ========================================
# 4. ENHANCED OLLAMA PROXY (Replace existing function)
# ========================================

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
        session_id = session.get('telemetry_session_id')
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

# ========================================
# 5. OPTIMIZED COMPARE_FASTEST_LAPS (Replace your existing function)
# ========================================

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
    
    # 🔥 NEW: Memory-optimized telemetry loading
    processor = MemoryOptimizedTelemetryProcessor()
    drv1_tel = processor.get_optimized_telemetry(drv1_fastest)
    drv2_tel = processor.get_optimized_telemetry(drv2_fastest)
    
    # 🔥 NEW: Track-aware interpolation
    try:
        common_dist = create_optimized_distance_array(
            session, drv1_tel, drv2_tel, track_interpolator
        )
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
    
    with managed_figure((28, 20), len(telemetry_metrics), 1) as (fig, axes):
        fig.subplots_adjust(hspace=0.18)
        
        label_font = {"fontsize": 16, "color": "white", "fontweight": "bold"}
        line_effects = [pe.Stroke(linewidth=4, foreground="#222"), pe.Normal()]
        
        # Add Turn Markers and Labels (your existing code)
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
        
        # Add Sector Split Markers (your existing code)
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
        
        # Plot telemetry channels (your existing plot functions)
        plot_telemetry(axes[0], drv1_tel, drv2_tel, "Throttle", drv1_color, drv2_color, drv1_abbr, drv2_abbr, label_font, line_effects)
        axes[0].legend(facecolor="#222", edgecolor="white", fontsize=14, labelcolor="white", framealpha=0.85, loc='upper right')
        
        plot_telemetry(axes[1], drv1_tel, drv2_tel, "Brake", drv1_color, drv2_color, drv1_abbr, drv2_abbr, label_font, line_effects)
        axes[1].set_ylabel("Brakes", **label_font)
        
        plot_telemetry(axes[2], drv1_tel, drv2_tel, "RPM", drv1_color, drv2_color, drv1_abbr, drv2_abbr, label_font, line_effects)
        plot_telemetry(axes[3], drv1_tel, drv2_tel, "Speed", drv1_color, drv2_color, drv1_abbr, drv2_abbr, label_font, line_effects)
        axes[3].set_ylabel("Speed (km/h)", **label_font)
        
        # Special handling for gear plot (your existing function)
        plot_gear_telemetry(axes[4], drv1_tel, drv2_tel, drv1_color, drv2_color, drv1_abbr, drv2_abbr, label_font, line_effects)
        axes[4].set_ylabel("Gear", **label_font)
        axes[4].set_xlabel("Lap Time", **label_font)
        
        # Styling for all subplots (your existing styling)
        for ax in axes:
            ax.set_facecolor("#222")
            ax.grid(True, alpha=0.2, color="white")
            ax.tick_params(colors="white", labelsize=12)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.spines["left"].set_color("white")
            ax.spines["bottom"].set_color("white")
        
        # Add Key Moment Annotations (your existing annotation logic)
        annotation_colors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#f9ca24', '#f0932b']
        moment_details = []
        
        for i, idx in enumerate(key_idxs):
            try:
                time_point = drv1_time[idx]
                
                # Interpolate telemetry values (your existing logic)
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
        
        # The managed_figure context automatically cleans up matplotlib resources
    
    # 🔥 NEW: Clean up telemetry data to free memory
    processor.cleanup_telemetry_data(drv1_tel, drv2_tel)
    
    # Record performance statistics
    processing_time = time.time() - start_time
    track_name = session.event['EventName']
    track_interpolator.record_interpolation_performance(
        track_name, len(common_dist), processing_time
    )
    
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
    
    # Add sector gaps and F1 color classes (your existing logic)
    for i, sector in enumerate(drv1_sectors):
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
        "track_category": track_interpolator.track_profiles.get(track_name, {}).get('category', 'unknown'),
        "key_moments_detected": len(key_idxs),
        "optimization_used": "track_aware" if len(common_dist) != 1500 else "fallback"
    }
    
    enhanced_context["visual_elements"] = {
        "total_annotations": len(moment_details),
        "annotation_times": [f"{m['time']:.1f}s" for m in moment_details],
        "key_moments": [m["description"] for m in moment_details]
    }
    
    # 🔥 NEW: Store context with session instead of global variable
    session_id = session.get('telemetry_session_id')
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

# ========================================
# 6. ENHANCED INDEX ROUTE (Replace your existing route)
# ========================================

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
                context = retrieve_telemetry_context(session_id)
                if context and "plot_annotations" in context:
                    moment_annotations = context["plot_annotations"]
                
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

# ========================================
# 7. NEW PERFORMANCE MONITORING ENDPOINTS
# ========================================

@app.route("/optimize_cache", methods=["POST"])
def optimize_cache():
    """🔥 NEW: Trigger cache optimization"""
    try:
        # Force cleanup of expired contexts
        global_context_manager.force_cleanup()
        
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

# ========================================
# 8. STARTUP LOGGING
# ========================================

logging.info("🔥 F1 App Performance Upgrades Loaded:")
logging.info("  ✅ Smart Session Manager with analytics")  
logging.info("  ✅ Track-aware interpolation system")
logging.info("  ✅ Memory-optimized matplotlib handling")
logging.info("  ✅ Request-scoped context management")
logging.info("  ✅ Concurrent user support enabled")
