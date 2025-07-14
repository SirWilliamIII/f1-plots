#!/bin/bash

# Deploy F1 App to Oracle with Remote Ollama Configuration
# This script removes the local Ollama service and connects to remote Ollama

set -e

echo "🚀 Deploying F1 App with Remote Ollama Configuration..."

# Check if we're in the right directory
if [ ! -f "app.py" ]; then
    echo "❌ Error: app.py not found. Please run this script from the project root directory."
    exit 1
fi

# Stop and remove existing containers
echo "🛑 Stopping existing containers..."
docker-compose down --remove-orphans || true

# Remove the local Ollama volume since we won't need it anymore
echo "🗑️  Removing local Ollama volume..."
docker volume rm f1-race-plots_ollama_data 2>/dev/null || true

# Build the Flask app image
echo "🔨 Building Flask app image..."
docker build -t f1-flask-app:latest .

# Start the app with remote Ollama configuration
echo "🚀 Starting Flask app with remote Ollama..."
docker-compose -f docker-compose.remote-ollama.yml up -d

# Wait for the app to be ready
echo "⏳ Waiting for app to be ready..."
sleep 10

# Check if the app is running
if docker-compose -f docker-compose.remote-ollama.yml ps | grep -q "Up"; then
    echo "✅ Flask app is running!"

    # Test the Ollama connection
    echo "🔍 Testing Ollama connection..."
    if curl -s http://localhost:80/ollama_proxy/tags > /dev/null; then
        echo "✅ Remote Ollama connection successful!"
    else
        echo "⚠️  Warning: Could not connect to remote Ollama. Please check:"
        echo "   - SSH tunnel is active with port forwarding: ssh -L 11434:localhost:11434 -i ~/.ssh/lambda-gpu.pem ubuntu@129.213.30.129"
        echo "   - Ollama is running on the remote server"
        echo "   - You can access the Ollama API directly at http://localhost:11434/api/tags"
    fi

    echo ""
    echo "🎉 Deployment complete!"
    echo "📱 App is available at: http://localhost:80"
    echo "🔗 Ollama endpoint: http://localhost:11434 (via SSH tunnel)"
    echo ""
    echo "⚠️  IMPORTANT: Before using the app, ensure the SSH tunnel is active:"
    echo "   ssh -L 11434:localhost:11434 -i ~/.ssh/lambda-gpu.pem ubuntu@129.213.30.129"
    echo ""
    echo "📋 To view logs: docker-compose -f docker-compose.remote-ollama.yml logs -f"
    echo "🛑 To stop: docker-compose -f docker-compose.remote-ollama.yml down"

else
    echo "❌ Failed to start the app. Check logs:"
    docker-compose -f docker-compose.remote-ollama.yml logs
    exit 1
fi
