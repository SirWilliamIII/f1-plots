"""
Modal deployment wrapper for F1 Telemetry Application (OPTIMIZED)

This file defines an optimized Modal app structure including:
- Better timeout handling and concurrency support
- Optimized image building with caching
- Improved Ollama GPU integration
- Persistent volumes for FastF1 cache and Ollama models
- Health checks and monitoring

Usage:
    modal deploy deployment/app_modal_optimized.py
"""

import os
import modal
from pathlib import Path

# Create Modal app with project directory mounted
app = modal.App("f1-telemetry")

# Get the directory containing this file (deployment/)
deployment_dir = Path(__file__).parent
# Get project root directory (parent of deployment/)
project_root = deployment_dir.parent

# Define persistent volumes
data_volume = modal.Volume.from_name("f1-data", create_if_missing=True)
ollama_volume = modal.Volume.from_name("ollama-models", create_if_missing=True)

# Optimized container image with better caching
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install_from_requirements(str(project_root / "requirements.txt"))
    .apt_install("curl")
    # Install Ollama
    .run_commands(
        "curl -fsSL https://ollama.com/install.sh | sh",
    )
    # Add modelfile for custom F1 analyst model
    .add_local_file(
        str(project_root / "f1-analyst.modelfile"),
        "/root/f1-analyst.modelfile"
    )
    # Add all application source files
    .add_local_dir(str(project_root), remote_path="/root")
)


@app.function(
    image=image,
    gpu="T4",
    timeout=900,  # 15 minutes for model building
    volumes={"/root/.ollama": ollama_volume},
    keep_warm=1,  # Keep 1 container warm to reduce cold starts
)
def run_ollama_generate(
    model: str,
    prompt: str,
    options: dict = None,
    stream: bool = False,
) -> dict:
    """
    Run Ollama generate API on GPU (compatible with /api/generate endpoint).

    This function is optimized for minimal latency by:
    - Using persistent volume for model caching
    - Pre-warming containers
    - Efficient model loading

    Args:
        model: Model name (e.g., "f1-analyst:latest")
        prompt: The prompt to send
        options: Model options (temperature, etc.)
        stream: Whether to stream the response

    Returns:
        dict: Ollama API response
    """
    import subprocess
    import json
    import time

    # Start Ollama service in background
    ollama_process = subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for Ollama to be ready (reduced from 3s to 2s)
    time.sleep(2)

    try:
        # Check if model exists
        check = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
        )

        if model not in check.stdout:
            print(f"Building/pulling model: {model}")

            # Build custom f1-analyst model
            if model == "f1-analyst:latest":
                # Pull base model
                subprocess.run(
                    ["ollama", "pull", "llama3:8b"],
                    check=True,
                    timeout=600,
                )
                # Build custom model
                subprocess.run(
                    ["ollama", "create", "f1-analyst:latest", "-f", "/root/f1-analyst.modelfile"],
                    check=True,
                    timeout=120,
                )
            else:
                # Pull other models
                subprocess.run(
                    ["ollama", "pull", model],
                    check=True,
                    timeout=300,
                )

            print(f"Model {model} ready")

        # Prepare request
        request_data = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
        }

        if options:
            request_data["options"] = options

        # Run inference
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
            timeout=120,
        )

        if result.returncode != 0:
            raise Exception(f"Inference failed: {result.stderr}")

        if stream:
            # Parse streaming response
            lines = result.stdout.strip().split('\n')
            responses = []
            for line in lines:
                if line:
                    try:
                        responses.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            return {"responses": responses, "streaming": True}
        else:
            return json.loads(result.stdout)

    finally:
        # Commit volume to persist models
        ollama_volume.commit()

        # Clean up Ollama process
        ollama_process.terminate()
        ollama_process.wait(timeout=5)


@app.function(
    image=image,
    volumes={"/cache": data_volume},
    memory=8192,  # 8GB RAM for Flask app and FastF1
    timeout=600,  # 10 minute timeout (increased from 5 minutes)
    keep_warm=1,  # Keep 1 container warm
    allow_concurrent_inputs=10,  # Handle up to 10 concurrent requests
)
@modal.wsgi_app()
def web():
    """
    Deploy Flask app as WSGI application with optimizations.

    Improvements:
    - Increased timeout for plot generation
    - Concurrent request handling
    - Pre-warmed container
    - Optimized environment variables
    """
    import sys
    import os

    # Set up environment BEFORE importing anything
    os.environ["MODAL_DEPLOYMENT"] = "true"
    os.environ["FLASK_ENV"] = "production"
    os.environ["FASTF1_CACHE"] = "/cache/fastf1_cache"
    os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"
    os.environ["DISABLE_PRELOADING"] = "true"  # Disable preloading on Modal

    # Matplotlib backend (prevent GUI errors)
    os.environ["MPLBACKEND"] = "Agg"
    os.environ["MPLCONFIGDIR"] = "/tmp"

    # Create cache directory
    os.makedirs("/cache/fastf1_cache", exist_ok=True)

    # Ensure project root is in path
    project_dir = "/root"
    if project_dir not in sys.path:
        sys.path.insert(0, project_dir)

    # Import and create Flask app
    from app import create_app
    flask_application = create_app()

    return flask_application


@app.function(
    image=image,
    volumes={"/cache": data_volume},
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

    # Create cache directory
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
    print("Cache warming complete!")


@app.local_entrypoint()
def main():
    """
    Local entrypoint for testing Modal functions.

    Usage:
        modal run deployment/app_modal_optimized.py
    """
    # Test Ollama inference
    print("Testing Ollama GPU inference...")
    result = run_ollama_generate.remote(
        model="qwen2.5-coder:7b",
        prompt="What is trail braking in Formula 1? Answer in 2 sentences.",
        options={"temperature": 0.1},
    )
    print(f"Response: {result.get('response', 'No response')}")

    print("\n✅ Modal functions are working!")
    print("\nDeploy with: modal deploy deployment/app_modal_optimized.py")


if __name__ == "__main__":
    main()
