#!/bin/bash

# Configuration - Matching your deploy script defaults
PROJECT_ID=${GCP_PROJECT_ID:-"justyn-demo-bank-ai"}
INSTANCE_ID=${SPANNER_INSTANCE_ID:-"fsi-demo-instance"}
REGION=${GCP_REGION:-"us-central1"}
SERVICE_NAME="customer-twins-demo"

echo "🗑️ Starting Cleanup for Customer Twins Demo..."
echo "------------------------------------------------"
echo "Project:  $PROJECT_ID"
echo "Instance: $INSTANCE_ID"
echo "Region:   $REGION"
echo "------------------------------------------------"

# 1. Delete Cloud Run Service
echo "☁️ Deleting Cloud Run service: $SERVICE_NAME..."
gcloud run services delete $SERVICE_NAME \
    --region $REGION \
    --project $PROJECT_ID \
    --quiet || echo "Cloud Run service not found, skipping."

# 2. Delete Container Images from Artifact Registry
# Note: gcloud run deploy --source creates a repository named 'cloud-run-source-deploy'
REPO_NAME="cloud-run-source-deploy"
echo "📦 Cleaning up Artifact Registry images..."
gcloud artifacts repositories delete $REPO_NAME \
    --location $REGION \
    --project $PROJECT_ID \
    --quiet || echo "Artifact repository not found, skipping."

# 3. Handle Spanner Backups
# Backups must be deleted before the instance or database can be cleanly removed in some workflows, 
# and they incur costs even if the DB is idle.
echo "💾 Checking for Spanner backups..."
BACKUPS=$(gcloud spanner backups list --instance=$INSTANCE_ID --project=$PROJECT_ID --format="value(name)")

if [ -n "$BACKUPS" ]; then
    for BACKUP in $BACKUPS; do
        echo "Deleting backup: $BACKUP"
        gcloud spanner backups delete $BACKUP --instance=$INSTANCE_ID --project=$PROJECT_ID --quiet
    done
else
    echo "No backups found."
fi

# 4. Delete Spanner Instance
# This will also delete all databases within the instance
echo "🗄️ Deleting Spanner instance: $INSTANCE_ID..."
gcloud spanner instances delete $INSTANCE_ID \
    --project $PROJECT_ID \
    --quiet || echo "Spanner instance not found, skipping."

# 5. Local Cleanup (Optional)
echo "🧹 Cleaning up local Python artifacts..."
find . -type d -name "__pycache__" -exec rm -rf {} +
rm -rf .pytest_cache

echo "------------------------------------------------"
echo "✅ Cleanup Complete! APIs remain enabled."