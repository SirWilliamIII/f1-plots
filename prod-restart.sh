#!/bin/bash

# Production restart script for F1 Race Plots
# Safely restarts the app on port 5052 (connected to Cloudflare tunnel)

echo "🔄 Restarting F1 Race Plots in PRODUCTION mode..."
echo "📍 Port: 5052 (Cloudflare tunnel)"
echo "🌐 URL: https://f1.linux-box.cc"
echo ""

# Kill existing processes on port 5052
echo "⏹️  Stopping existing production app..."
lsof -ti:5052 | xargs kill -9 2>/dev/null || true

# Wait a moment for processes to fully stop
sleep 3

# Set production environment variables
export PORT=5052
export FLASK_ENV=production

# Start the application in background
echo "🚀 Starting production app..."
nohup uv run python app.py > prod.log 2>&1 &

# Show the process ID
sleep 2
echo "✅ Production app started! PID: $(lsof -ti:5052)"
echo "📄 Logs: tail -f prod.log"