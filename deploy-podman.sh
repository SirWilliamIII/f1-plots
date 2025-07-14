#!/bin/bash

# Deploy F1 App with Podman
# This script uses Podman for containerization and uv for Python package management

set -e

echo "🚀 Deploying F1 App with Podman..."

# Check if we're in the right directory
if [ ! -f "app.py" ]; then
    echo "❌ Error: app.py not found. Please run this script from the project root directory."
    exit 1
fi

# Check if podman is installed
if ! command -v podman &> /dev/null; then
    echo "❌ Error: Podman is not installed. Please install Podman first."
    exit 1
fi

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ Error: uv is not installed. Please install uv first."
    echo "   Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Generate requirements.txt from pyproject.toml using uv
echo "📦 Generating requirements.txt from pyproject.toml..."
uv pip compile pyproject.toml -o requirements.txt

# Check if Ollama is already running
OLLAMA_RUNNING=false
if podman ps | grep -q "ollama.*Up"; then
    echo "✅ Ollama is already running"
    OLLAMA_RUNNING=true
elif lsof -i :11434 >/dev/null 2>&1 || netstat -an | grep -q ":11434.*LISTEN" 2>/dev/null; then
    echo "⚠️  Port 11434 is already in use (possibly by local Ollama)"
    echo "   Using existing Ollama instance"
    OLLAMA_RUNNING=true
fi

# Stop and remove existing containers
echo "🛑 Stopping existing containers..."
podman stop flask-app 2>/dev/null || true
podman rm flask-app 2>/dev/null || true

if [ "$OLLAMA_RUNNING" = false ]; then
    podman stop ollama 2>/dev/null || true
    podman rm ollama 2>/dev/null || true
fi

# Create network if it doesn't exist
echo "🌐 Creating network..."
podman network exists f1-network 2>/dev/null || podman network create f1-network

# Create volume for Ollama if it doesn't exist
echo "💾 Creating Ollama volume..."
podman volume exists ollama_data 2>/dev/null || podman volume create ollama_data

# Build the Flask app image
echo "🔨 Building Flask app image with Podman..."
podman build -t localhost/f1-flask-app:latest .

# Start Ollama container only if not already running
if [ "$OLLAMA_RUNNING" = false ]; then
    echo "🚀 Starting Ollama container..."
    podman run -d \
        --name ollama \
        --network f1-network \
        -p 11434:11434 \
        -v ollama_data:/root/.ollama:Z \
        -e OLLAMA_KEEP_ALIVE=24h \
        -e OLLAMA_HOST=0.0.0.0 \
        -e OLLAMA_ORIGINS=* \
        -e OLLAMA_NUM_PARALLEL=2 \
        --memory 40g \
        --cpus 4 \
        --restart unless-stopped \
        ollama/ollama:latest
else
    echo "ℹ️  Skipping Ollama container creation (already running)"
fi

# Wait for Ollama to be ready
echo "⏳ Waiting for Ollama to start..."
max_attempts=30
attempt=0
while ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ $attempt -ge $max_attempts ]; then
        echo "❌ Ollama failed to start after ${max_attempts} attempts"
        exit 1
    fi
    echo "   Waiting... (attempt $attempt/$max_attempts)"
    sleep 2
done
echo "✅ Ollama is ready!"

# Check if f1expert model exists, if not create it
echo "🤖 Checking f1expert model..."
if [ "$OLLAMA_RUNNING" = true ] && command -v ollama &> /dev/null; then
    # Use local ollama command if available
    if ! ollama list | grep -q "f1expert:latest"; then
        echo "📥 Creating f1expert model..."
        # First ensure base model exists
        ollama pull llama3.2:3b
        # Create custom model
        ollama create f1expert -f f1expert.modelfile
        echo "✅ f1expert model created!"
    else
        echo "✅ f1expert model already exists!"
    fi
elif podman ps | grep -q "ollama.*Up"; then
    # Use podman exec if running in container
    if ! podman exec ollama ollama list | grep -q "f1expert:latest"; then
        echo "📥 Creating f1expert model..."
        # First ensure base model exists
        podman exec ollama ollama pull llama3.2:3b
        # Copy modelfile and create custom model
        podman cp f1expert.modelfile ollama:/tmp/f1expert.modelfile
        podman exec ollama ollama create f1expert -f /tmp/f1expert.modelfile
        echo "✅ f1expert model created!"
    else
        echo "✅ f1expert model already exists!"
    fi
else
    echo "⚠️  Could not check/create f1expert model - Ollama not accessible"
fi

# Start Flask app container
echo "🚀 Starting Flask app container..."
# Determine Ollama URL based on where it's running
if [ "$OLLAMA_RUNNING" = true ] && ! podman ps | grep -q "ollama.*Up"; then
    # Local Ollama - use host network or host.containers.internal
    OLLAMA_URL="http://host.containers.internal:11434"
    echo "ℹ️  Using local Ollama at $OLLAMA_URL"
    podman run -d \
        --name flask-app \
        --add-host=host.containers.internal:host-gateway \
        -p 8080:8080 \
        -e OLLAMA_BASE_URL=$OLLAMA_URL \
        -e PYTHONUNBUFFERED=1 \
        -e MATPLOTLIB_BACKEND=Agg \
        -e PORT=8080 \
        -v ./fastf1_cache:/app/fastf1_cache:Z \
        -v ./static/plots:/app/static/plots:Z \
        -v ./logs:/app/logs:Z \
        --memory 8g \
        --cpus 2 \
        --restart unless-stopped \
        localhost/f1-flask-app:latest
else
    # Container Ollama - use container name
    OLLAMA_URL="http://ollama:11434"
    echo "ℹ️  Using containerized Ollama at $OLLAMA_URL"
    podman run -d \
        --name flask-app \
        --network f1-network \
        -p 8080:8080 \
        -e OLLAMA_BASE_URL=$OLLAMA_URL \
        -e PYTHONUNBUFFERED=1 \
        -e MATPLOTLIB_BACKEND=Agg \
        -e PORT=8080 \
        -v ./fastf1_cache:/app/fastf1_cache:Z \
        -v ./static/plots:/app/static/plots:Z \
        -v ./logs:/app/logs:Z \
        --memory 8g \
        --cpus 2 \
        --restart unless-stopped \
        localhost/f1-flask-app:latest
fi

# Wait for Flask app to be ready
echo "⏳ Waiting for Flask app to start..."
sleep 10

# Check if the app is running
if podman ps | grep -q "flask-app.*Up"; then
    echo "✅ Flask app is running!"
    
    # Test the Ollama connection through Flask proxy
    echo "🔍 Testing Ollama integration..."
    if curl -s http://localhost:8080/ollama_proxy/tags > /dev/null 2>&1; then
        echo "✅ Ollama integration successful!"
    else
        echo "⚠️  Warning: Could not verify Ollama integration"
        echo "   Check logs with: podman logs flask-app"
    fi
    
    echo ""
    echo "🎉 Deployment complete!"
    echo "📱 App is available at: http://localhost:8080"
    echo ""
    echo "📋 Useful commands:"
    echo "   View logs: podman logs -f flask-app"
    echo "   View Ollama logs: podman logs -f ollama"
    echo "   List models: podman exec ollama ollama list"
    echo "   Stop services: podman stop flask-app ollama"
    echo "   Remove containers: podman rm flask-app ollama"
    echo "   Remove network: podman network rm f1-network"
    
else
    echo "❌ Failed to start Flask app. Check logs:"
    podman logs flask-app
    exit 1
fi