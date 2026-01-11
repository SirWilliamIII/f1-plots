"""
Modal deployment wrapper for F1 Telemetry Application - FIXED VERSION

Simplified deployment that addresses:
- Cold start timeout issues
- HTTP/2 stream errors
- Proper Flask initialization
- Correct decorator ordering

Usage:
    modal deploy deployment/app_modal_fixed.py
"""

import modal
from pathlib import Path

# Create Modal app
app = modal.App("f1-telemetry")

# Get project root directory
deployment_dir = Path(__file__).parent
project_root = deployment_dir.parent

# Define persistent volumes
data_volume = modal.Volume.from_name("f1-data", create_if_missing=True)
ollama_volume = modal.Volume.from_name("ollama-models", create_if_missing=True)

# Simplified image build - use requirements.txt
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install_from_requirements(str(project_root / "requirements.txt"))
    .apt_install("curl")
    # Install Ollama
    .run_commands("curl -fsSL https://ollama.com/install.sh | sh")
    # Mount the application code
    .add_local_dir(str(project_root), remote_path="/root")
)


@app.function(
    image=image,
    gpu="T4",
    timeout=900,  # 15 minutes for model building
    volumes={"/root/.ollama": ollama_volume},
    min_containers=0,  # Don't keep warm to save costs
)
def run_ollama_generate(model: str, prompt: str, options: dict = None) -> dict:
    """Run Ollama generate API on GPU."""
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
        # Check if model exists
        check = subprocess.run(["ollama", "list"], capture_output=True, text=True)

        if model not in check.stdout:
            print(f"Model {model} not found, pulling...")
            if model == "f1-analyst:latest":
                # Build custom f1-analyst model
                subprocess.run(["ollama", "pull", "llama3:8b"], check=True, timeout=600)
                subprocess.run(
                    ["ollama", "create", "f1-analyst:latest", "-f", "/root/f1-analyst.modelfile"],
                    check=True,
                    timeout=120,
                )
            else:
                subprocess.run(["ollama", "pull", model], check=True, timeout=300)

        # Prepare request
        request_data = {"model": model, "prompt": prompt, "stream": False}
        if options:
            request_data["options"] = options

        # Run inference
        result = subprocess.run(
            [
                "curl", "-X", "POST",
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

        return json.loads(result.stdout)

    finally:
        ollama_volume.commit()
        ollama_process.terminate()
        ollama_process.wait(timeout=5)


@app.function(
    image=image,
    volumes={"/cache": data_volume},
    memory=16384,  # 16GB RAM (increased from 8GB)
    timeout=1800,  # 30 minute timeout (increased from 10min)
    min_containers=0,  # Don't keep warm - scale to zero
    cpu=4,  # Use 4 CPUs for faster processing
)
@modal.wsgi_app()
def web():
    """
    Optimized Flask WSGI app deployment.

    Key optimizations:
    - Set MODAL_DEPLOYMENT=true BEFORE any imports
    - Skip session preloading entirely
    - Fast initialization
    - Proper error handling
    """
    import sys
    import os

    # CRITICAL: Set MODAL_DEPLOYMENT *FIRST* before any app imports
    # This prevents the warm_cache @before_request hook from running
    os.environ["MODAL_DEPLOYMENT"] = "true"

    # Set other environment variables
    os.environ["FLASK_ENV"] = "production"
    os.environ["FASTF1_CACHE"] = "/cache/fastf1_cache"
    os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"
    os.environ["DISABLE_PRELOADING"] = "true"
    os.environ["MPLBACKEND"] = "Agg"
    os.environ["MPLCONFIGDIR"] = "/tmp"

    # Create cache directory
    os.makedirs("/cache/fastf1_cache", exist_ok=True)

    # Add project to path
    if "/root" not in sys.path:
        sys.path.insert(0, "/root")

    # Create Flask app (should be fast now - no preloading)
    try:
        import time
        start_time = time.time()

        from app import create_app
        app_instance = create_app()

        elapsed = time.time() - start_time
        print(f"✓ Flask app created successfully in {elapsed:.2f}s (Modal mode)")
        print(f"✓ FastF1 cache directory: {os.environ.get('FASTF1_CACHE')}")
        print(f"✓ Memory: 16GB, CPU: 4 cores, Timeout: 30min")

        return app_instance
    except Exception as e:
        print(f"✗ Failed to create Flask app: {e}")
        import traceback
        traceback.print_exc()
        raise


@app.local_entrypoint()
def main():
    """Test the deployment locally."""
    print("Testing Ollama GPU function...")
    result = run_ollama_generate.remote(
        model="qwen2.5-coder:7b",
        prompt="What is Formula 1? Answer in one sentence.",
        options={"temperature": 0.1},
    )
    print(f"✓ Ollama response: {result.get('response', 'No response')[:100]}...")
    print("\n✅ Functions working! Deploy with:")
    print("modal deploy deployment/app_modal_fixed.py")
