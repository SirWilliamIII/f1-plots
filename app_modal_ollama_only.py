"""
Modal deployment for Ollama GPU inference ONLY.

This keeps Flask and FastF1 running locally, only offloads Ollama to GPU.
Avoids FastF1 download timeout issues.

Usage:
    modal deploy app_modal_ollama_only.py
"""

import modal

app = modal.App("f1-ollama-gpu")

# Simpler image - only needs Ollama + custom modelfile
from pathlib import Path
local_dir = Path(__file__).parent

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("curl")
    .run_commands("curl -fsSL https://ollama.com/install.sh | sh")
    # Add the modelfile to the image
    .add_local_file(
        str(local_dir / "f1-analyst.modelfile"),
        "/root/f1-analyst.modelfile"
    )
)


@app.function(
    image=image,
    gpu="T4",
    timeout=900,  # 15 minutes (includes time to build custom model)
    container_idle_timeout=600,  # Keep warm for 10 minutes
)
def generate(
    model: str,
    prompt: str,
    temperature: float = 0.1,
) -> dict:
    """
    Run Ollama inference on T4 GPU.

    Args:
        model: Model name (e.g., "qwen2.5-coder:7b")
        prompt: The prompt
        temperature: Sampling temperature

    Returns:
        dict: {"response": "...", "model": "...", "done": True}
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

    time.sleep(3)

    try:
        # Pull/build model if needed
        print(f"Checking for model: {model}")
        check = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
        )

        if model not in check.stdout:
            # Check if it's the f1-analyst custom model
            if model == "f1-analyst:latest":
                print(f"Building custom model: {model}")
                # First pull the base model
                subprocess.run(
                    ["ollama", "pull", "llama3:8b"],
                    check=True,
                    timeout=600,  # 10 minute timeout for base model
                )
                # Then build the custom model from modelfile
                subprocess.run(
                    ["ollama", "create", "f1-analyst:latest", "-f", "/root/f1-analyst.modelfile"],
                    check=True,
                    timeout=120,
                )
                print(f"Custom model {model} built successfully")
            else:
                print(f"Pulling model: {model}")
                subprocess.run(
                    ["ollama", "pull", model],
                    check=True,
                    timeout=300,  # 5 minute timeout for pull
                )
            print(f"Model {model} ready")

        # Run inference
        print(f"Running inference...")
        result = subprocess.run(
            [
                "curl",
                "-X", "POST",
                "http://localhost:11434/api/generate",
                "-H", "Content-Type: application/json",
                "-d", json.dumps({
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": temperature}
                })
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            raise Exception(f"Inference failed: {result.stderr}")

        return json.loads(result.stdout)

    finally:
        ollama_process.terminate()
        ollama_process.wait(timeout=5)


@app.local_entrypoint()
def main():
    """Test the function"""
    print("Testing Ollama GPU inference...")
    result = generate.remote(
        model="qwen2.5-coder:7b",
        prompt="What is trail braking in F1? Answer in 2 sentences.",
        temperature=0.1,
    )
    print(f"\nResponse: {result['response']}")
    print("\n✅ Deploy with: modal deploy app_modal_ollama_only.py")
