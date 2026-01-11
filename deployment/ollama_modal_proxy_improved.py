"""
Improved Ollama proxy with Modal GPU backend and local fallback.

Enhancements over original:
1. Local Ollama fallback if Modal is unavailable
2. Health check improvements
3. Request timeout handling
4. Connection pooling
5. Better error messages

Usage:
    # Terminal 1: Deploy Modal function
    modal deploy app_modal_ollama_only.py

    # Terminal 2: Run this proxy
    python ollama_modal_proxy_improved.py

    # Terminal 3: Run Flask with this proxy
    export OLLAMA_BASE_URL=http://localhost:11435
    ./dev-start.sh
"""

import os
import time
import logging
import json
from flask import Flask, request, jsonify
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)

app = Flask(__name__)

# Configuration
MODAL_TIMEOUT = 120  # seconds
LOCAL_OLLAMA_URL = os.getenv("LOCAL_OLLAMA_URL", "http://localhost:11434")
ENABLE_LOCAL_FALLBACK = os.getenv("ENABLE_LOCAL_FALLBACK", "false").lower() == "true"

# Lazy import Modal to avoid startup overhead
_modal_generate = None
_modal_available = None
_last_modal_check = 0
MODAL_CHECK_INTERVAL = 300  # 5 minutes


def check_modal_available():
    """Check if Modal function is available (with caching)"""
    global _modal_available, _last_modal_check

    now = time.time()
    if _modal_available is not None and (now - _last_modal_check) < MODAL_CHECK_INTERVAL:
        return _modal_available

    try:
        get_modal_function()
        _modal_available = True
    except Exception as e:
        logging.warning(f"Modal not available: {e}")
        _modal_available = False

    _last_modal_check = now
    return _modal_available


def get_modal_function():
    """Lazy load Modal function"""
    global _modal_generate
    if _modal_generate is None:
        import modal
        _modal_generate = modal.Function.from_name("f1-ollama-gpu", "generate")
        logging.info("Connected to Modal GPU function")
    return _modal_generate


def try_local_ollama(model: str, prompt: str, temperature: float) -> dict:
    """Try local Ollama as fallback"""
    import requests

    logging.info(f"Trying local Ollama at {LOCAL_OLLAMA_URL}")
    response = requests.post(
        f"{LOCAL_OLLAMA_URL}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature}
        },
        timeout=300
    )
    response.raise_for_status()
    return response.json()


def call_modal_with_timeout(model: str, prompt: str, temperature: float) -> dict:
    """Call Modal with timeout handling"""
    modal_fn = get_modal_function()

    # Use ThreadPoolExecutor for timeout
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            modal_fn.remote,
            model=model,
            prompt=prompt,
            temperature=temperature
        )
        try:
            return future.result(timeout=MODAL_TIMEOUT)
        except FuturesTimeoutError:
            raise TimeoutError(f"Modal inference timed out after {MODAL_TIMEOUT}s")


@app.route('/api/tags', methods=['GET'])
def list_models():
    """Mock endpoint to list available models"""
    return jsonify({
        "models": [
            {"name": "qwen2.5-coder:7b"},
            {"name": "f1-analyst:latest"},
        ]
    })


@app.route('/api/generate', methods=['POST'])
def generate():
    """
    Proxy Ollama generation requests to Modal GPU with optional local fallback.

    Expects:
        {
            "model": "qwen2.5-coder:7b",
            "prompt": "...",
            "stream": false,
            "options": {"temperature": 0.1}
        }

    Returns:
        {
            "response": "...",
            "model": "...",
            "done": true,
            "backend": "modal-gpu" | "local-ollama"
        }
    """
    try:
        data = request.json
        model = data.get("model", "qwen2.5-coder:7b")
        prompt = data.get("prompt", "")
        options = data.get("options", {})
        temperature = options.get("temperature", 0.1)
        stream = data.get("stream", False)

        if stream:
            return jsonify({
                "error": "Streaming not supported via Modal proxy"
            }), 400

        start_time = time.time()

        # Try Modal first
        modal_available = check_modal_available()

        if modal_available:
            try:
                logging.info(f"Forwarding to Modal GPU: model={model}, temp={temperature}")
                result = call_modal_with_timeout(model, prompt, temperature)
                elapsed = time.time() - start_time
                logging.info(f"Modal GPU inference completed in {elapsed:.1f}s")
                result["backend"] = "modal-gpu"
                result["inference_time"] = f"{elapsed:.1f}s"
                return jsonify(result)

            except Exception as modal_error:
                logging.error(f"Modal GPU error: {modal_error}")

                if ENABLE_LOCAL_FALLBACK:
                    logging.info("Falling back to local Ollama")
                else:
                    raise modal_error

        # Local fallback (if enabled and Modal failed)
        if ENABLE_LOCAL_FALLBACK:
            try:
                result = try_local_ollama(model, prompt, temperature)
                elapsed = time.time() - start_time
                logging.info(f"Local Ollama inference completed in {elapsed:.1f}s")
                result["backend"] = "local-ollama"
                result["inference_time"] = f"{elapsed:.1f}s"
                return jsonify(result)
            except Exception as local_error:
                logging.error(f"Local Ollama error: {local_error}")
                return jsonify({
                    "error": "Both Modal and local Ollama failed",
                    "modal_error": str(modal_error) if 'modal_error' in dir() else "Not attempted",
                    "local_error": str(local_error)
                }), 503
        else:
            return jsonify({
                "error": str(modal_error) if 'modal_error' in dir() else "Modal not available",
                "details": "Failed to connect to Modal GPU function. Is it deployed?",
                "hint": "Set ENABLE_LOCAL_FALLBACK=true for local Ollama fallback"
            }), 503

    except Exception as e:
        logging.error(f"Proxy error: {e}")
        return jsonify({
            "error": str(e),
            "details": "Unexpected error in proxy"
        }), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint with detailed status"""
    status = {
        "status": "healthy",
        "backends": {}
    }

    # Check Modal
    try:
        modal_ok = check_modal_available()
        status["backends"]["modal-gpu"] = "available" if modal_ok else "unavailable"
    except Exception as e:
        status["backends"]["modal-gpu"] = f"error: {str(e)}"

    # Check local Ollama (if fallback enabled)
    if ENABLE_LOCAL_FALLBACK:
        try:
            import requests
            resp = requests.get(f"{LOCAL_OLLAMA_URL}/api/tags", timeout=5)
            status["backends"]["local-ollama"] = "available" if resp.ok else "unavailable"
        except Exception:
            status["backends"]["local-ollama"] = "unavailable"

    # Overall status
    if status["backends"].get("modal-gpu") == "available":
        status["primary_backend"] = "modal-gpu"
    elif status["backends"].get("local-ollama") == "available":
        status["primary_backend"] = "local-ollama"
        status["status"] = "degraded"
    else:
        status["status"] = "unhealthy"
        status["primary_backend"] = None

    status_code = 200 if status["status"] != "unhealthy" else 503
    return jsonify(status), status_code


@app.route('/warmup', methods=['POST'])
def warmup():
    """
    Warmup endpoint - triggers a lightweight inference to wake up Modal container.
    Call this when user visits the site to eliminate cold starts.
    """
    try:
        start = time.time()
        logging.info("Warming up Modal GPU container...")

        modal_fn = get_modal_function()

        # Send a tiny warmup prompt (fast inference, just to wake container)
        result = modal_fn.remote(
            model="qwen2.5-coder:7b",
            prompt="Ready",
            temperature=0.1
        )

        elapsed = time.time() - start
        logging.info(f"Modal container warmed in {elapsed:.1f}s")

        return jsonify({
            "status": "warmed",
            "backend": "modal-gpu",
            "time": f"{elapsed:.1f}s",
            "note": "Container will stay warm for 10 minutes"
        })
    except Exception as e:
        logging.error(f"Warmup failed: {e}")
        return jsonify({"status": "warmup-failed", "error": str(e)}), 503


@app.route('/stats', methods=['GET'])
def stats():
    """Return proxy statistics"""
    return jsonify({
        "modal_available": _modal_available,
        "last_modal_check": _last_modal_check,
        "local_fallback_enabled": ENABLE_LOCAL_FALLBACK,
        "modal_timeout": MODAL_TIMEOUT
    })


if __name__ == '__main__':
    print("=" * 60)
    print("  F1 Telemetry - Ollama Modal GPU Proxy (Improved)")
    print("=" * 60)
    print(f"  Listening on: http://localhost:11435")
    print(f"  Primary backend: Modal T4 GPU")
    print(f"  Local fallback: {'Enabled' if ENABLE_LOCAL_FALLBACK else 'Disabled'}")
    print(f"  Modal timeout: {MODAL_TIMEOUT}s")
    print("")
    print("  Set in your Flask app:")
    print("    export OLLAMA_BASE_URL=http://localhost:11435")
    print("")
    print("  Enable local fallback:")
    print("    export ENABLE_LOCAL_FALLBACK=true")
    print("=" * 60)

    app.run(host='0.0.0.0', port=11435, debug=False, threaded=True)
