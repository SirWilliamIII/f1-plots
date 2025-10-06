#!/bin/bash

# Development startup script for F1 Race Plots
# Runs on port 5050 with development settings

echo "🚀 Starting F1 Race Plots in DEVELOPMENT mode..."
echo "📍 Port: 5050"
echo "🌐 URL: http://localhost:5050"
echo ""

# Set development environment variables
export PORT=5050
export FLASK_ENV=development

# Start the application
uv run python app.py
