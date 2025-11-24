"""
Local Ollama proxy that forwards requests to Modal GPU.

This runs locally and acts as a drop-in replacement for Ollama,
forwarding inference requests to Modal's T4 GPU for 10x speedup.

Usage:
    # Terminal 1: Deploy Modal function
    modal deploy app_modal_ollama_only.py

    # Terminal 2: Run this proxy
    python ollama_modal_proxy.py

    # Terminal 3: Run Flask with this proxy
    export OLLAMA_BASE_URL=http://localhost:11435
    ./dev-start.sh
"""

from flask import Flask, request, jsonify, Response
import logging
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)

app = Flask(__name__)

# Lazy import Modal to avoid startup overhead
_modal_generate = None

def get_modal_function():
    """Lazy load Modal function"""
    global _modal_generate
    if _modal_generate is None:
        import modal
        # Use from_name to reference the deployed function
        _modal_generate = modal.Function.from_name("f1-ollama-gpu", "generate")
        logging.info("✓ Connected to Modal GPU function")
    return _modal_generate


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
    Proxy Ollama generation requests to Modal GPU.

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
            "done": true
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

        logging.info(f"🚀 Forwarding to Modal GPU: model={model}, temp={temperature}")

        # Call Modal GPU function
        modal_fn = get_modal_function()
        result = modal_fn.remote(
            model=model,
            prompt=prompt,
            temperature=temperature
        )

        logging.info(f"✓ GPU inference completed")
        return jsonify(result)

    except Exception as e:
        logging.error(f"✗ Modal GPU error: {e}")
        return jsonify({
            "error": str(e),
            "details": "Failed to connect to Modal GPU function. Is it deployed?"
        }), 503


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    try:
        get_modal_function()
        return jsonify({"status": "healthy", "backend": "modal-gpu"})
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 503


@app.route('/warmup', methods=['POST'])
def warmup():
    """
    Warmup endpoint - triggers a lightweight inference to wake up Modal container.
    Call this when user visits the site to eliminate cold starts.
    """
    try:
        logging.info("🔥 Warming up Modal GPU container...")
        modal_fn = get_modal_function()

        # Send a tiny warmup prompt (fast inference, just to wake container)
        result = modal_fn.remote(
            model="qwen2.5-coder:7b",
            prompt="Ready",
            temperature=0.1
        )

        logging.info("✓ Modal container warmed up")
        return jsonify({"status": "warmed", "backend": "modal-gpu"})
    except Exception as e:
        logging.error(f"✗ Warmup failed: {e}")
        return jsonify({"status": "warmup-failed", "error": str(e)}), 503


if __name__ == '__main__':
    print("🚀 Starting Ollama → Modal GPU Proxy")
    print("📍 Listening on: http://localhost:11435")
    print("🔗 Forwarding to: Modal T4 GPU function")
    print("")
    print("💡 Set in your Flask app:")
    print("   export OLLAMA_BASE_URL=http://localhost:11435")
    print("")

    app.run(host='0.0.0.0', port=11435, debug=False)
