#!/bin/bash
set -e

# Configuration
PROJECT_ID=${GCP_PROJECT_ID:-$(gcloud config get-value project)}
# Default to existing if not set
INSTANCE_ID=${SPANNER_INSTANCE_ID:-"fsi-demo-instance"}
DATABASE_ID=${SPANNER_DATABASE_ID:-"fsi-customer-db"}
REGION=${GCP_REGION:-"us-central1"}
SERVICE_NAME="customer-twins-demo"
SERVICE_NAME="customer-twins-demo"
REPO_NAME="containers"
IMAGE_NAME="$REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/$SERVICE_NAME"

echo "🚀 Starting Robust Deployment for Customer Twins Demo..."
echo "------------------------------------------------"
echo "Project: $PROJECT_ID"
echo "Service: $SERVICE_NAME"
echo "Image:   $IMAGE_NAME"
echo "------------------------------------------------"

# 1. Enable APIs (idempotent)
echo "🔌 Ensuring Google Cloud APIs are enabled..."
gcloud services enable spanner.googleapis.com \
    aiplatform.googleapis.com \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    --project $PROJECT_ID

# 1.5 Fix IAM Permissions (Logging & Storage)
echo "🛡️ Fixing IAM permissions..."
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
# Grant permission to write logs (fixes build failure)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member=serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com \
    --role=roles/logging.logWriter
# Grant permission to read/write artifacts
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member=serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com \
    --role=roles/artifactregistry.writer
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member=serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com \
    --role=roles/storage.objectViewer
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member=serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com \
    --role=roles/spanner.databaseUser
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member=serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com \
    --role=roles/aiplatform.user
    
echo "⏳ Waiting 15s for IAM propagation..."
sleep 15

# 2. Create Artifact Registry Repository (if not exists)
echo "📦 Ensuring Artifact Registry Repository exists..."
gcloud artifacts repositories create $REPO_NAME \
    --repository-format=docker \
    --location=$REGION \
    --description="Docker repository for FSI Demos" \
    --quiet || echo "Repository likely already exists, proceeding..."

# 3. Build Container
echo "🔨 Building Container using Cloud Build..."
# Using --tag forces a build and push to Artifact Registry
gcloud builds submit --tag $IMAGE_NAME .

# 4. Deploy to Cloud Run

# 3. Deploy to Cloud Run
echo "🦄 Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_NAME \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --set-env-vars GCP_PROJECT_ID=$PROJECT_ID \
    --set-env-vars SPANNER_INSTANCE_ID=$INSTANCE_ID \
    --set-env-vars SPANNER_DATABASE_ID=$DATABASE_ID \
    --set-env-vars GOOGLE_CLOUD_DISABLE_GRPC_GCP_OBSERVABILITY=true \
    --memory 2Gi

echo "✅ Deployment Complete!"
echo "Service URL: $(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')"
