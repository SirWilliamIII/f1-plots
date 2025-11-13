#!/bin/bash
# Production Flask startup with Modal GPU acceleration

export OLLAMA_BASE_URL=http://localhost:11435
export PORT=5151
export FLASK_ENV=production

echo "Starting Flask on port $PORT with GPU proxy at $OLLAMA_BASE_URL"
exec uv run python app.py
