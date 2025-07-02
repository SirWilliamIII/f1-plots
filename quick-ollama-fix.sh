#!/bin/bash

# Quick Ollama Fix - Run this directly on your VM
# This script fixes the most common Ollama connection issues

echo "🔧 Quick Ollama Fix for 48GB VM"
echo "==============================="

# Stop all services
echo "🛑 Stopping services..."
cd /opt/f1-app
docker-compose down --remove-orphans || true

# Clean up
echo "🧹 Cleaning Docker..."
docker system prune -f

# Start Ollama with proper memory limits
echo "🚀 Starting Ollama with optimized settings..."
docker run -d \
  --name ollama-fixed \
  --restart unless-stopped \
  -p 11434:11434 \
  -v ollama_data:/root/.ollama \
  -v $(pwd)/f1expert.modelfile:/tmp/f1expert.modelfile \
  --memory=35g \
  --cpus=6 \
  -e OLLAMA_HOST=0.0.0.0:11434 \
  -e OLLAMA_ORIGINS=* \
  -e OLLAMA_KEEP_ALIVE=24h \
  -e OLLAMA_NUM_PARALLEL=1 \
  -e OLLAMA_MAX_LOADED_MODELS=1 \
  ollama/ollama:latest

# Wait for Ollama to start
echo "⏳ Waiting for Ollama to start..."
sleep 30

# Test Ollama
if curl -sf http://localhost:11434/api/tags >/dev/null; then
    echo "✅ Ollama is running!"
else
    echo "❌ Ollama failed to start"
    docker logs ollama-fixed
    exit 1
fi

# Create F1 model if needed
echo "🤖 Setting up F1 Expert model..."
if ! docker exec ollama-fixed ollama list | grep -q "f1expert"; then
    docker exec ollama-fixed ollama create f1expert -f /tmp/f1expert.modelfile
    echo "✅ F1 Expert model created"
else
    echo "✅ F1 Expert model already exists"
fi

# Start Flask with proper Ollama URL
echo "🌐 Starting Flask app..."
docker run -d \
  --name flask-fixed \
  --restart unless-stopped \
  -p 8080:8080 \
  --link ollama-fixed:ollama \
  -v $(pwd)/fastf1_cache:/app/fastf1_cache \
  -v $(pwd)/static/plots:/app/static/plots \
  -v $(pwd)/logs:/app/logs \
  --memory=8g \
  --cpus=2 \
  -e OLLAMA_BASE_URL=http://ollama:11434 \
  -e PYTHONUNBUFFERED=1 \
  -e MATPLOTLIB_BACKEND=Agg \
  -e PORT=8080 \
  -e FLASK_ENV=production \
  f1-flask-app:latest

# Wait for Flask
echo "⏳ Waiting for Flask to start..."
sleep 20

# Test connection
echo "🧪 Testing connection..."
if curl -sf http://localhost:8080/ >/dev/null; then
    echo "✅ Flask is running!"
else
    echo "❌ Flask failed to start"
    docker logs flask-fixed
fi

if curl -sf http://localhost:11434/api/tags >/dev/null; then
    echo "✅ Ollama API is accessible!"
else
    echo "❌ Ollama API is not accessible"
fi

# Test Flask -> Ollama connection
if docker exec flask-fixed curl -sf http://ollama:11434/api/tags >/dev/null; then
    echo "✅ Flask can reach Ollama!"
else
    echo "❌ Flask cannot reach Ollama"
fi

echo ""
echo "🎉 Quick fix complete!"
echo "📊 Services status:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""
echo "🌐 Your app should now be working at: http://$(curl -s ifconfig.me):8080"
echo ""
echo "💡 To make permanent, run the full deployment script."