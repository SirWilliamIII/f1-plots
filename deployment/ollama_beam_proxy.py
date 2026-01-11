"""
Local Ollama proxy that forwards requests to Beam.cloud GPU.

This runs on the Oracle server and acts as a drop-in replacement for Ollama,
forwarding inference requests to Beam's T4 GPU.

Setup:
    1. Deploy Beam function:
       beam deploy deployment/app_beam_ollama.py:generate

    2. Get your Beam API token from https://platform.beam.cloud
       Set it as environment variable:
       export BEAM_API_TOKEN=your_token_here

    3. Run this proxy:
       python deployment/ollama_beam_proxy.py

    4. Run Flask with this proxy:
       export OLLAMA_BASE_URL=http://localhost:11435
       python run.py

Environment Variables:
    BEAM_API_TOKEN: Your Beam.cloud API token (required)
    BEAM_ENDPOINT_URL: Override endpoint URL (optional)
"""

from flask import Flask, request, jsonify
import requests
import logging
import os
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)

app = Flask(__name__)

# Beam configuration
BEAM_API_TOKEN = os.environ.get("BEAM_API_TOKEN")
BEAM_ENDPOINT_URL = os.environ.get(
    "BEAM_ENDPOINT_URL",
    "https://f1-ollama-b942c80-v1.app.beam.cloud"
)
BEAM_HEALTH_URL = os.environ.get(
    "BEAM_HEALTH_URL",
    "https://app.beam.cloud/endpoint/f1-ollama-health"
)


def check_config():
    """Verify configuration on startup"""
    if not BEAM_API_TOKEN:
        logging.error("BEAM_API_TOKEN environment variable is not set!")
        logging.error("Get your token from https://platform.beam.cloud")
        raise ValueError("BEAM_API_TOKEN is required")


def call_beam_endpoint(url: str, payload: dict, timeout: int = 180) -> dict:
    """Call a Beam endpoint with authentication"""
    headers = {
        "Authorization": f"Bearer {BEAM_API_TOKEN}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=timeout
    )

    if response.status_code != 200:
        raise Exception(f"Beam API error: {response.status_code} - {response.text}")

    return response.json()


@app.route('/api/tags', methods=['GET'])
def list_models():
    """Mock endpoint to list available models"""
    return jsonify({
        "models": [
            {"name": "qwen2.5-coder:7b"},
            {"name": "f1-analyst:latest"},
            {"name": "llama3:8b"},
        ]
    })


@app.route('/api/generate', methods=['POST'])
def generate():
    """
    Proxy Ollama generation requests to Beam GPU.

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
                "error": "Streaming not supported via Beam proxy"
            }), 400

        logging.info(f"Forwarding to Beam GPU: model={model}, temp={temperature}")
        start_time = time.time()

        # Call Beam GPU endpoint
        result = call_beam_endpoint(
            BEAM_ENDPOINT_URL,
            {
                "model": model,
                "prompt": prompt,
                "temperature": temperature
            },
            timeout=180  # 3 minute timeout for inference
        )

        elapsed = time.time() - start_time
        logging.info(f"GPU inference completed in {elapsed:.1f}s")

        return jsonify(result)

    except requests.Timeout:
        logging.error("Beam GPU request timed out")
        return jsonify({
            "error": "Request timed out",
            "details": "Beam GPU inference took too long"
        }), 504

    except Exception as e:
        logging.error(f"Beam GPU error: {e}")
        return jsonify({
            "error": str(e),
            "details": "Failed to connect to Beam GPU. Check BEAM_API_TOKEN and deployment."
        }), 503


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    try:
        # Quick local check - just verify we have config
        if not BEAM_API_TOKEN:
            return jsonify({
                "status": "unhealthy",
                "error": "BEAM_API_TOKEN not configured"
            }), 503

        return jsonify({
            "status": "healthy",
            "backend": "beam-gpu",
            "endpoint": BEAM_ENDPOINT_URL
        })

    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 503


@app.route('/warmup', methods=['POST'])
def warmup():
    """
    Warmup endpoint - triggers a lightweight inference to wake up Beam container.
    Call this when user visits the site to eliminate cold starts.
    """
    try:
        start = time.time()
        logging.info("Warming up Beam GPU container...")

        # Send a tiny warmup prompt
        result = call_beam_endpoint(
            BEAM_ENDPOINT_URL,
            {
                "model": "qwen2.5-coder:7b",
                "prompt": "Ready",
                "temperature": 0.1
            },
            timeout=120  # 2 minute timeout for warmup (includes cold start)
        )

        elapsed = time.time() - start
        logging.info(f"Beam container warmed in {elapsed:.1f}s")

        return jsonify({
            "status": "warmed",
            "backend": "beam-gpu",
            "time": f"{elapsed:.1f}s"
        })

    except Exception as e:
        logging.error(f"Warmup failed: {e}")
        return jsonify({"status": "warmup-failed", "error": str(e)}), 503


@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Proxy Ollama chat requests to Beam GPU.
    Converts chat format to generate format.
    """
    try:
        data = request.json
        model = data.get("model", "qwen2.5-coder:7b")
        messages = data.get("messages", [])
        options = data.get("options", {})
        temperature = options.get("temperature", 0.1)
        stream = data.get("stream", False)

        if stream:
            return jsonify({
                "error": "Streaming not supported via Beam proxy"
            }), 400

        # Convert messages to a single prompt
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")

        prompt = "\n\n".join(prompt_parts)
        if prompt_parts:
            prompt += "\n\nAssistant:"

        logging.info(f"Chat request to Beam GPU: model={model}")
        start_time = time.time()

        result = call_beam_endpoint(
            BEAM_ENDPOINT_URL,
            {
                "model": model,
                "prompt": prompt,
                "temperature": temperature
            },
            timeout=180
        )

        elapsed = time.time() - start_time
        logging.info(f"Chat completed in {elapsed:.1f}s")

        # Convert to chat response format
        return jsonify({
            "model": model,
            "message": {
                "role": "assistant",
                "content": result.get("response", "")
            },
            "done": True
        })

    except Exception as e:
        logging.error(f"Chat error: {e}")
        return jsonify({
            "error": str(e),
            "details": "Failed to process chat request"
        }), 503


if __name__ == '__main__':
    print("=" * 60)
    print("  Ollama -> Beam.cloud GPU Proxy")
    print("=" * 60)
    print()

    try:
        check_config()
        print(f"  Endpoint: {BEAM_ENDPOINT_URL}")
        print(f"  Token: {'*' * 20}...{BEAM_API_TOKEN[-4:] if BEAM_API_TOKEN else 'NOT SET'}")
        print()
        print("  Listening on: http://localhost:11435")
        print()
        print("  Set in your Flask app:")
        print("    export OLLAMA_BASE_URL=http://localhost:11435")
        print()
        print("=" * 60)

        app.run(host='0.0.0.0', port=11435, debug=False)

    except ValueError as e:
        print(f"\n  ERROR: {e}")
        print("\n  To fix:")
        print("    1. Get your API token from https://platform.beam.cloud")
        print("    2. Run: export BEAM_API_TOKEN=your_token_here")
        print("    3. Restart this proxy")
        exit(1)
