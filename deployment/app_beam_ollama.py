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

# Build image with Ollama installed and model pre-downloaded
# NOTE: Model is baked into the image, so no volume needed
image = (
    Image(python_version="python3.11")
    .add_commands([
        "apt-get update",
        "apt-get install -y curl",
        "curl -fsSL https://ollama.com/install.sh | sh",
        # Start Ollama in background, pull model, then stop
        "ollama serve & sleep 10 && ollama pull qwen2.5-coder:7b && pkill ollama || true",
    ])
    .add_python_packages(["requests"])
)


@endpoint(
    name="f1-ollama",
    cpu=2,
    memory="16Gi",
    gpu="A10G",
    image=image,
    # No volumes - model is baked into image
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

    # Wait for Ollama to start and verify it's ready
    print("Waiting for Ollama to be ready...")
    time.sleep(5)

    # Verify Ollama is responding
    max_retries = 10
    for i in range(max_retries):
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.status_code == 200:
                print("Ollama is ready!")
                break
        except:
            if i < max_retries - 1:
                print(f"Ollama not ready yet, waiting... ({i+1}/{max_retries})")
                time.sleep(2)
            else:
                raise Exception("Ollama failed to start")

    try:
        # List available models for debugging
        print(f"Listing available models...")
        check = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
        )
        print(f"Available models:\n{check.stdout}")

        # Model should be pre-downloaded in image, but pull if missing
        if model not in check.stdout:
            print(f"Model {model} not found in image, pulling now...")
            pull_result = subprocess.run(
                ["ollama", "pull", model],
                capture_output=False,
                timeout=600,
            )
            if pull_result.returncode != 0:
                raise Exception(f"Failed to pull model {model}: exit code {pull_result.returncode}")
            print(f"Model {model} pulled successfully")
        else:
            print(f"Using pre-downloaded model: {model}")

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
