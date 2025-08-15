#!/bin/bash

# Production restart script for F1 Race Plots
# Safely restarts the app on port 5151 (connected to Cloudflare tunnel)

echo "🔄 Restarting F1 Race Plots in PRODUCTION mode..."
echo "📍 Port: 5151 (Cloudflare tunnel)"
echo "🌐 URL: https://f1.linux-box.cc"
echo ""

# Kill existing processes on port 5151
echo "⏹️  Stopping existing production app..."
lsof -ti:5151 | xargs kill -9 2>/dev/null || true

# Wait a moment for processes to fully stop
sleep 3

# Set production environment variables
export PORT=5151
export FLASK_ENV=production

# Start the application in background
echo "🚀 Starting production app..."
nohup uv run python app.py > prod.log 2>&1 &

# Show the process ID
sleep 2
echo "✅ Production app started! PID: $(lsof -ti:5151)"
echo "📄 Logs: tail -f prod.log"
