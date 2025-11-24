"""
Modal deployment wrapper for F1 Telemetry Application

This file defines the Modal app structure including:
- Persistent volumes for FastF1 cache and Ollama models
- GPU-accelerated Ollama inference function
- Flask ASGI app deployment

Usage:
    modal deploy app_modal.py
"""

import os
import modal
from pathlib import Path

# Create Modal app with project directory mounted
app = modal.App("f1-telemetry")

# Get the directory containing this file
local_dir = Path(__file__).parent

# Define persistent volumes
# This volume stores both FastF1 cache and Ollama models
data_volume = modal.Volume.from_name("f1-data", create_if_missing=True)

# Define the container image with all dependencies
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install_from_requirements("requirements.txt")
    .apt_install("curl")
    # Install Ollama
    .run_commands(
        "curl -fsSL https://ollama.com/install.sh | sh",
    )
    # Add all application source files to the image
    .add_local_dir(local_dir, remote_path="/root")
)


@app.function(
    image=image,
    gpu="T4",  # NVIDIA T4 GPU for Ollama inference
    timeout=120,  # 2 minute timeout for inference
    scaledown_window=600,  # Keep warm for 10 minutes after last request (enough for user browsing)
)
def run_ollama_inference(
    prompt: str,
    model: str = "f1-analyst:latest",
    temperature: float = 0.1,
    stream: bool = False,
) -> dict:
    """
    Run Ollama inference on GPU.

    Args:
        prompt: The prompt to send to the model
        model: Model name (default: f1-analyst:latest)
        temperature: Sampling temperature (default: 0.1)
        stream: Whether to stream the response (default: False)

    Returns:
        dict: Response from Ollama
    """
    import subprocess
    import json
    import time

    # Start Ollama service
    ollama_process = subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for Ollama to be ready
    time.sleep(2)

    try:
        # Check if model exists, if not pull it
        model_check = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
        )

        if model not in model_check.stdout:
            print(f"Model {model} not found, pulling...")
            subprocess.run(
                ["ollama", "pull", model],
                check=True,
            )

        # Run inference
        if stream:
            # Streaming response
            result = subprocess.run(
                ["ollama", "run", model, "--format", "json"],
                input=prompt,
                capture_output=True,
                text=True,
            )
            return {"response": result.stdout, "streaming": True}
        else:
            # Non-streaming response
            result = subprocess.run(
                [
                    "ollama",
                    "run",
                    model,
                    prompt,
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            return {
                "response": result.stdout.strip(),
                "model": model,
                "streaming": False,
            }

    finally:
        # Clean up Ollama process
        ollama_process.terminate()
        ollama_process.wait(timeout=5)


@app.function(
    image=image,
    gpu="T4",
    timeout=120,
    scaledown_window=600,  # Keep warm for 10 minutes after last request (enough for user browsing)
)
def run_ollama_generate(
    model: str,
    prompt: str,
    options: dict = None,
    stream: bool = False,
) -> dict:
    """
    Run Ollama generate API (compatible with /api/generate endpoint).

    Args:
        model: Model name
        prompt: The prompt to send
        options: Model options (temperature, etc.)
        stream: Whether to stream the response

    Returns:
        dict: Ollama API response
    """
    import subprocess
    import json
    import time

    # Start Ollama service
    ollama_process = subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    time.sleep(2)

    try:
        # Use curl to call Ollama API
        request_data = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
        }

        if options:
            request_data["options"] = options

        result = subprocess.run(
            [
                "curl",
                "-X", "POST",
                "http://localhost:11434/api/generate",
                "-H", "Content-Type: application/json",
                "-d", json.dumps(request_data),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if stream:
            # Parse streaming response
            lines = result.stdout.strip().split('\n')
            responses = []
            for line in lines:
                if line:
                    responses.append(json.loads(line))
            return {"responses": responses, "streaming": True}
        else:
            return json.loads(result.stdout)

    finally:
        ollama_process.terminate()
        ollama_process.wait(timeout=5)


@app.function(
    image=image,
    volumes={"/cache": data_volume},
    memory=8192,  # 8GB RAM for Flask app
    timeout=300,  # 5 minute timeout for plot generation
    scaledown_window=600,  # Keep warm for 10 minutes
)
@modal.wsgi_app()
def web():
    """
    Deploy Flask app as WSGI application.
    """
    import sys
    import os
    import subprocess

    # Debug: See what files are available
    print("=== DEBUG: Files in /root ===")
    result = subprocess.run(["ls", "-la", "/root"], capture_output=True, text=True)
    print(result.stdout)
    print("=== DEBUG: Python path ===")
    print(sys.path)
    print("=== DEBUG: Current directory ===")
    print(os.getcwd())
    result = subprocess.run(["ls", "-la", "."], capture_output=True, text=True)
    print(result.stdout)

    # Set up environment before importing app
    os.environ["MODAL_DEPLOYMENT"] = "true"
    os.environ["FLASK_ENV"] = "production"
    os.environ["FASTF1_CACHE"] = "/cache/fastf1_cache"
    os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"

    # Create cache directory
    os.makedirs("/cache/fastf1_cache", exist_ok=True)

    # Modal automatically mounts the directory, just need to ensure path
    project_dir = "/root"
    if project_dir not in sys.path:
        sys.path.insert(0, project_dir)

    # Import and return Flask app
    from app import app as flask_application
    return flask_application


@app.function(
    image=image,
    volumes={"/cache": data_volume},  # Fixed: mount at /cache to match Flask app
    schedule=modal.Cron("0 0 * * *"),  # Run daily at midnight
)
def warm_cache():
    """
    Daily cache warming job to preload popular F1 sessions.

    This runs in the background to ensure frequently accessed sessions
    are available in the cache, reducing cold start times.
    """
    import fastf1
    from datetime import datetime
    import os

    # Create cache directory (matches Flask app setup)
    os.makedirs("/cache/fastf1_cache", exist_ok=True)

    # Set cache directory
    fastf1.Cache.enable_cache("/cache/fastf1_cache")

    # Get current year
    year = datetime.now().year

    # Popular races to preload
    popular_races = [
        "Monaco",
        "British",
        "Italian",
        "Abu Dhabi",
    ]

    for race_name in popular_races:
        try:
            print(f"Preloading {race_name} {year}...")
            session = fastf1.get_session(year, race_name, "R")
            session.load()
            print(f"✓ Loaded {race_name}")
        except Exception as e:
            print(f"✗ Failed to load {race_name}: {e}")

    # Commit changes to volume
    data_volume.commit()


@app.local_entrypoint()
def main():
    """
    Local entrypoint for testing Modal functions.

    Usage:
        modal run app_modal.py
    """
    # Test Ollama inference
    print("Testing Ollama inference...")
    result = run_ollama_inference.remote(
        prompt="What is trail braking in Formula 1?",
        model="f1-analyst:latest",
    )
    print(f"Response: {result}")

    print("\nModal functions are working! Deploy with: modal deploy app_modal.py")


if __name__ == "__main__":
    main()
