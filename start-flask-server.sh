#!/bin/bash
# Wrapper script for Flask server auto-start via LaunchAgent

# Log startup attempt
echo "=== Flask Server Starting at $(date) ===" >> /Users/will/Library/Logs/flask-server.log 2>&1

# Change to app directory
cd /Users/will/Programming/Websites/f1-race-plots || {
    echo "ERROR: Failed to change to app directory" >> /Users/will/Library/Logs/flask-server.log 2>&1
    exit 1
}

# Set environment variables
export PATH="/Users/will/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export HOME="/Users/will"
export OLLAMA_BASE_URL="http://localhost:11434"
export PYTHONUNBUFFERED="1"
export PORT="5151"
export FLASK_ENV="production"

# Wait for Ollama to be available (max 30 seconds)
echo "Waiting for Ollama service..." >> /Users/will/Library/Logs/flask-server.log 2>&1
for i in {1..30}; do
    if curl -s http://localhost:11434/api/version > /dev/null 2>&1; then
        echo "Ollama is ready!" >> /Users/will/Library/Logs/flask-server.log 2>&1
        break
    fi
    if [ $i -eq 30 ]; then
        echo "WARNING: Ollama not responding after 30 seconds, continuing anyway..." >> /Users/will/Library/Logs/flask-server.log 2>&1
    fi
    sleep 1
done

# Ensure log directory exists
mkdir -p /Users/will/Library/Logs

# Start the Flask app with uv
echo "Starting Flask app..." >> /Users/will/Library/Logs/flask-server.log 2>&1
exec /opt/homebrew/bin/uv run python app.py >> /Users/will/Library/Logs/flask-server.log 2>&1
