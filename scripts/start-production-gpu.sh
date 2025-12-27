#!/bin/bash

# Production startup script with Hybrid GPU Architecture
# Runs Flask on port 5151 with Modal GPU proxy for AI inference

echo "🚀 Starting F1 Race Plots in PRODUCTION mode (Hybrid GPU)"
echo "📍 Flask Port: 5151"
echo "🔗 Cloudflare: https://f1.linux-box.cc"
echo "⚡ GPU: Modal T4 via proxy (port 11435)"
echo ""

# Kill any existing processes on the ports
echo "🧹 Cleaning up existing processes..."
lsof -ti:5151 | xargs kill -9 2>/dev/null || true
lsof -ti:11435 | xargs kill -9 2>/dev/null || true

# Start Ollama Modal Proxy in background
echo "🔥 Starting Ollama Modal GPU Proxy..."
uv run python deployment/ollama_modal_proxy.py > logs/proxy.log 2>&1 &
PROXY_PID=$!
echo "   Proxy PID: $PROXY_PID"

# Wait for proxy to be ready
sleep 3

# Set production environment variables
export PORT=5151
export FLASK_ENV=production
export OLLAMA_BASE_URL=http://localhost:11435

# Start Flask app
echo "🏎️  Starting Flask application..."
uv run python run.py

# Cleanup on exit
trap "kill $PROXY_PID 2>/dev/null" EXIT
