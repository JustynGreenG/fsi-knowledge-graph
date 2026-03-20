#!/bin/bash
set -e
### --- Configuration --- ###
CONFIG_FILE="variables.json"
# Verify jq is installed and the config file exists
if ! command -v jq &> /dev/null; then
    echo "Error: jq is required but could not be found. Please install it."
    exit 1
fi
if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "Error: Configuration file $CONFIG_FILE not found."
    exit 1
fi
# Read base variables from the JSON file
PROJECT_ID=$(jq -r '.PROJECT_ID' "$CONFIG_FILE")
INSTANCE_ID=$(jq -r '.INSTANCE_ID' "$CONFIG_FILE")
DATABASE_ID=$(jq -r '.DATABASE_ID' "$CONFIG_FILE")
REGION=$(jq -r '.REGION' "$CONFIG_FILE")
SERVICE_NAME=$(jq -r '.SERVICE_NAME' "$CONFIG_FILE")
REPO_NAME=$(jq -r '.REPO_NAME' "$CONFIG_FILE")
# Handle dynamic fallbacks
# If PROJECT_ID is empty or null in the JSON, fetch it from gcloud
if [[ -z "$PROJECT_ID" || "$PROJECT_ID" == "null" ]]; then
    PROJECT_ID=$(gcloud config get-value project)
fi
# Construct composite variables
IMAGE_NAME="$REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/$SERVICE_NAME"
### --- End of Configuration --- ###

echo "⚠️  WARNING: Starting Cleanup for Customer Twins Demo..."
echo "------------------------------------------------"
echo "Project: $PROJECT_ID"
echo "Instance: $INSTANCE_ID"
echo "Cloud Run Service: $SERVICE_NAME"
echo "Artifact Repo: $REPO_NAME"
echo "------------------------------------------------"

read -p "Are you sure you want to permanently delete these resources? (y/N): " confirm
if [[ "$confirm" != [yY] && "$confirm" != [yY][eE][sS] ]]; then
    echo "🛑 Aborting cleanup."
    exit 1
fi

# 1. Delete Cloud Run Service
echo "🗑️  Deleting Cloud Run service ($SERVICE_NAME)..."
gcloud run services delete $SERVICE_NAME \
    --region=$REGION \
    --project=$PROJECT_ID \
    --quiet || echo "⚠️ Service not found or already deleted."

# 2. Delete Spanner Instance
# Note: Deleting the instance automatically deletes all databases inside it.
echo "🗄️  Deleting Spanner Instance ($INSTANCE_ID)..."
gcloud spanner instances delete $INSTANCE_ID \
    --project=$PROJECT_ID \
    --quiet || echo "⚠️ Spanner instance not found or already deleted."

# 3. Delete Artifact Registry Repository
echo "📦 Deleting Artifact Registry Repository ($REPO_NAME) and all images..."
gcloud artifacts repositories delete $REPO_NAME \
    --location=$REGION \
    --project=$PROJECT_ID \
    --quiet || echo "⚠️ Repository not found or already deleted."

# 4. Revert IAM Permissions
echo "🛡️  Removing IAM permissions for default compute service account..."
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
SA_EMAIL="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# Remove logging permission
gcloud projects remove-iam-policy-binding $PROJECT_ID \
    --member=serviceAccount:$SA_EMAIL \
    --role=roles/logging.logWriter \
    --quiet || true

# Remove artifact registry permission
gcloud projects remove-iam-policy-binding $PROJECT_ID \
    --member=serviceAccount:$SA_EMAIL \
    --role=roles/artifactregistry.writer \
    --quiet || true

# Remove storage permission
gcloud projects remove-iam-policy-binding $PROJECT_ID \
    --member=serviceAccount:$SA_EMAIL \
    --role=roles/storage.objectViewer \
    --quiet || true

# Remove spanner permission
gcloud projects remove-iam-policy-binding $PROJECT_ID \
    --member=serviceAccount:$SA_EMAIL \
    --role=roles/spanner.databaseUser \
    --quiet || true

# Remove aiplatform permission
gcloud projects remove-iam-policy-binding $PROJECT_ID \
    --member=serviceAccount:$SA_EMAIL \
    --role=roles/aiplatform.user \
    --quiet || true

echo "✅ Cleanup Complete!"