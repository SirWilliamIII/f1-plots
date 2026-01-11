"""
Beam.cloud deployment for Ollama GPU inference.

This replaces Modal for GPU inference while Flask/FastF1 runs on Oracle server.

Setup:
    pip install beam-client
    beam config create  # Enter API keys

Deploy:
    beam deploy deployment/app_beam_ollama.py:generate

Test:
    curl -X POST 'https://app.beam.cloud/endpoint/f1-ollama' \
      -H 'Authorization: Bearer YOUR_TOKEN' \
      -H 'Content-Type: application/json' \
      -d '{"model": "qwen2.5-coder:7b", "prompt": "What is trail braking?", "temperature": 0.1}'
"""

from beam import endpoint, Image, Volume, env
from pathlib import Path

# Get project root for modelfile
local_dir = Path(__file__).parent
root_dir = local_dir.parent

# Create persistent volume for Ollama models (prevents re-downloading each time)
ollama_volume = Volume(name="ollama-models", mount_path="/root/.ollama")

# Build image with Ollama installed
image = (
    Image(python_version="python3.11")
    .add_commands([
        "apt-get update",
        "apt-get install -y curl",
        "curl -fsSL https://ollama.com/install.sh | sh",
    ])
    .add_python_packages(["requests"])
)


@endpoint(
    name="f1-ollama",
    cpu=2,
    memory="16Gi",
    gpu="T4",
    image=image,
    volumes=[ollama_volume],
    keep_warm_seconds=600,  # Keep warm for 10 minutes after last request
    timeout=900,  # 15 minutes max (includes model download time)
)
def generate(**inputs) -> dict:
    """
    Run Ollama inference on T4 GPU.

    Args:
        model: Model name (e.g., "qwen2.5-coder:7b")
        prompt: The prompt
        temperature: Sampling temperature (default 0.1)

    Returns:
        dict: {"response": "...", "model": "...", "done": True}
    """
    import subprocess
    import json
    import time
    import requests

    model = inputs.get("model", "qwen2.5-coder:7b")
    prompt = inputs.get("prompt", "")
    temperature = inputs.get("temperature", 0.1)

    # Start Ollama service
    print("Starting Ollama service...")
    ollama_process = subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for Ollama to start
    time.sleep(3)

    try:
        # Check if model exists, pull if needed
        print(f"Checking for model: {model}")
        check = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
        )

        if model not in check.stdout:
            print(f"Pulling model: {model}")
            subprocess.run(
                ["ollama", "pull", model],
                check=True,
                timeout=600,  # 10 minute timeout for pull
            )
            print(f"Model {model} ready")

        # Run inference via HTTP API
        print(f"Running inference with model={model}, temp={temperature}")
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature}
            },
            timeout=120
        )

        if response.status_code != 200:
            raise Exception(f"Inference failed: {response.text}")

        result = response.json()
        print("Inference completed successfully")
        return result

    finally:
        # Cleanup
        ollama_process.terminate()
        try:
            ollama_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            ollama_process.kill()


# Health check endpoint
@endpoint(
    name="f1-ollama-health",
    cpu=0.5,
    memory="512Mi",
    image=Image(python_version="python3.11"),
    timeout=30,
)
def health_check(**inputs) -> dict:
    """Simple health check endpoint"""
    return {"status": "healthy", "backend": "beam-gpu"}
