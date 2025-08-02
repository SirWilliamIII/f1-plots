#!/bin/bash

# Development startup script for F1 Race Plots
# Runs on port 5050 with development settings

echo "🚀 Starting F1 Race Plots in DEVELOPMENT mode..."
echo "📍 Port: 5051"
echo "🌐 URL: http://localhost:5051"
echo ""

# Set development environment variables
export PORT=5051
export FLASK_ENV=development

# Start the application
uv run python app.py