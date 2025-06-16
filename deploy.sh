#!/bin/bash
set -e  # Exit on any error

# === CONFIG ===
PROJECT_ID=$(gcloud config get-value project)
if [ -z "$PROJECT_ID" ]; then
    echo "❌ No GCP project configured. Run: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

IMAGE_NAME="f1-plots"
REGION="us-central1"
SERVICE_NAME="f1-plots"
PORT=8080

# === BUILD IMAGE FOR CLOUD RUN COMPATIBILITY ===
echo -e "\n🔧 Building image (linux/amd64 for Cloud Run)..."
podman build --platform linux/amd64 -t gcr.io/$PROJECT_ID/$IMAGE_NAME .

# === AUTHENTICATE PODMAN TO GCP ===
echo -e "\n🔐 Ensuring Podman is authenticated with GCP..."
gcloud auth configure-docker gcr.io --quiet

# === PUSH IMAGE TO CONTAINER REGISTRY ===
echo -e "\n📦 Pushing image to Google Container Registry..."
podman push gcr.io/$PROJECT_ID/$IMAGE_NAME

# === DEPLOY TO CLOUD RUN ===
echo -e "\n🚀 Deploying to Google Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$IMAGE_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --port $PORT \
  --memory 2Gi \
  --cpu 2 \
  --timeout 900 \
  --concurrency 80 \
  --max-instances 10 \
  --set-env-vars PORT=8080

# === CHECK DEPLOYMENT STATUS ===
echo -e "\n🔍 Checking service status..."
gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.conditions[0].message)'

# === GET SERVICE URL ===
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)')

# === SHOW RECENT LOGS ===
echo -e "\n📋 Recent logs:"
gcloud logs read --service=$SERVICE_NAME --region=$REGION --limit=10

# === DONE ===
echo -e "\n✅ Deployment complete!"
echo -e "🌐 Service URL: $SERVICE_URL"
