#!/bin/bash

# Podman Compose wrapper that ensures requirements.txt is up-to-date using uv

set -e

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ Error: uv is not installed. Please install uv first."
    echo "   Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Check if podman-compose is installed
if ! command -v podman-compose &> /dev/null; then
    echo "📦 Installing podman-compose with uv..."
    uv tool install podman-compose
fi

# Generate requirements.txt from pyproject.toml
echo "📦 Updating requirements.txt from pyproject.toml..."
uv pip compile pyproject.toml -o requirements.txt

# Build the image first if it's an 'up' command
if [[ "$1" == "up" ]] || [[ "$2" == "up" ]]; then
    echo "🔨 Building Flask app image..."
    podman build -t localhost/f1-flask-app:latest .
fi

# Use the podman-specific compose file
echo "🚀 Running podman-compose with podman-specific config..."
podman-compose -f docker-compose.podman.yml "$@"