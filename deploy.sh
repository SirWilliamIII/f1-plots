#!/bin/bash

# === CONFIG ===
PROJECT_ID=$(gcloud config get-value project)
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
  --port $PORT

# === DONE ===
echo -e "\n✅ Deployment complete!"