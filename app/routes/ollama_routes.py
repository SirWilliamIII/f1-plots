"""
Ollama Proxy Routes

Handles proxying requests to Ollama for AI inference.
"""

import os
import logging
import requests
from flask import request, jsonify, Response, stream_with_context, session as flask_session
from app.services.context_service import retrieve_telemetry_context
from app.services.ai_service import create_contextual_prompt
from app.error_tracking.error_tracker import get_error_tracker, ErrorSeverity


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")


def register_ollama_routes(app):
    """Register Ollama proxy routes"""

    @app.route("/ollama_proxy/tags", methods=["GET"])
    def ollama_tags():
        """Proxy endpoint to check Ollama connection"""
        try:
            logging.info(f"DEBUG: Trying to connect to {OLLAMA_BASE_URL}/api/tags")
            resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
            return Response(
                resp.content,
                status=resp.status_code,
                content_type=resp.headers.get("content-type"),
            )
        except requests.exceptions.RequestException as e:
            error_tracker = get_error_tracker()
            error_tracker.capture_exception(
                e,
                context={
                    'operation': 'ollama_tags',
                    'ollama_url': OLLAMA_BASE_URL,
                    'endpoint': '/ollama_proxy/tags'
                },
                level=ErrorSeverity.ERROR
            )
            logging.error(f"DEBUG: Ollama connection failed: {e}")
            return jsonify({"error": "Ollama not available", "url": OLLAMA_BASE_URL, "details": str(e)}), 503

    @app.route("/ollama_proxy/generate", methods=["POST"])
    def ollama_generate():
        """Proxy endpoint with session-scoped telemetry context injection"""
        try:
            logging.info("🔍 /ollama_proxy/generate called")
            logging.info(f"🔍 Request content type: {request.content_type}")
            logging.info(f"🔍 Request data: {request.get_data(as_text=True)[:200]}")

            request_data = request.json.copy()
            user_prompt = request_data.get("prompt", "")
            request_data["model"] = "qwen2.5-coder:7b"  # Use base model instead of custom f1-analyst

            # Performance optimizations for speed
            request_data["options"] = {
                "num_predict": -1,  # Allow model to complete response naturally
                "temperature": 0.1,
                "num_ctx": 1024,
                "repeat_penalty": 1.1,
                "top_p": 0.7,
                "num_thread": 4,
                "stop": ["</s>", "\n\n\n\n"]  # Stop tokens to prevent excessive output
            }

            # Get session-specific context
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

            logging.info(f"🚀 Forwarding to Ollama at {OLLAMA_BASE_URL}/api/generate")

            # Forward to Ollama
            resp = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json=request_data,
                stream=request_data.get("stream", False),
                timeout=300,
            )

            logging.info(f"✅ Ollama response status: {resp.status_code}")

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
            error_tracker = get_error_tracker()
            session_id = flask_session.get('telemetry_session_id', 'unknown')
            error_tracker.capture_exception(
                e,
                context={
                    'operation': 'ollama_generate',
                    'ollama_url': OLLAMA_BASE_URL,
                    'endpoint': '/ollama_proxy/generate',
                    'session_id': session_id,
                    'has_context': bool(flask_session.get('telemetry_session_id'))
                },
                level=ErrorSeverity.ERROR
            )
            logging.error(f"❌ Ollama proxy error: {e}")
            logging.error(f"❌ Error type: {type(e).__name__}")
            logging.error(f"❌ Traceback: ", exc_info=True)
            return jsonify({"error": "Failed to connect to Ollama", "details": str(e)}), 503
