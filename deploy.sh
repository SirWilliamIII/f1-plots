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
  --memory 2Gi \
  --cpu 2 \
  --timeout 900 \
  --concurrency 80 \
  --max-instances 10

# === CHECK DEPLOYMENT STATUS ===
echo -e "\n🔍 Checking service status..."
gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.conditions[0].message)'

# === GET SERVICE URL ===
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)')

# === SHOW RECENT LOGS ===
echo -e "\n📋 Recent logs:"
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME" --limit=10 --format="table(timestamp,severity,textPayload)"

# === DONE ===
echo -e "\n✅ Deployment complete!"
echo -e "🌐 Service URL: $SERVICE_URL"

