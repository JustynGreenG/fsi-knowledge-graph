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

# Pre-Requisite
# --- Google SSO Services - gcert ---
## Interactively request a new SSO certificate
gcert
# ---------------------------------
# --- Virtual Environment Setup ---
VENV_PATH="./.venv"

if [ ! -d "$VENV_PATH" ]; then
    echo "🛠️ Creating python virtual environment..."
    python3 -m venv "$VENV_PATH"
fi

if [[ "$VIRTUAL_ENV" != *"$VENV_PATH"* ]]; then
    echo "💡 Activating virtual environment..."
    source "$VENV_PATH/bin/activate"
else
    echo "✅ Virtual environment already active."
fi
# ---------------------------------

echo "🚀 Starting Deployment for Customer Twins Demo..."
echo "------------------------------------------------"
echo "Project: $PROJECT_ID"
echo "Instance: $INSTANCE_ID"
echo "Database: $DATABASE_ID"
echo "------------------------------------------------"

# 1. Enable APIs (idempotent)
echo "🔌 Ensuring Google Cloud APIs are enabled..."
gcloud services enable spanner.googleapis.com \
    aiplatform.googleapis.com \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    --project $PROJECT_ID
### 
# 1a. Create the policy JSON in the format gcloud expects for v1/v2 hybrid
echo "🚀 Ensuring GCP Project Organization Policy is Opened and enabled..."
cat <<EOF > policy.json
{
  "constraint": "constraints/iam.allowedPolicyMemberDomains",
  "listPolicy": {
    "allValues": "ALLOW"
  }
}
EOF
# 1b. Apply the policy
gcloud resource-manager org-policies set-policy policy.json \
    --project=$PROJECT_ID
# 1c. Clean up
rm policy.json
###

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

# 2. Python Dependencies
echo "📦 Installing Python dependencies..."
pip3 install -r requirements.txt

# 3. Spanner Setup
echo "🗄️ Setting up Spanner Schema..."
# Create Instance if not exists
gcloud spanner instances create $INSTANCE_ID \
    --config=regional-$REGION \
    --description="FSI Demo Instance" \
    --nodes=1 \
    --edition=ENTERPRISE \
    --project=$PROJECT_ID || echo "Instance likely exists, skipping creation."

# Create Database if not exists
gcloud spanner databases create $DATABASE_ID \
    --instance=$INSTANCE_ID \
    --project=$PROJECT_ID || echo "Database likely exists, skipping creation."

# 3a. Run Schema Script
python3 setup_schema.py --project_id=$PROJECT_ID --instance_id=$INSTANCE_ID --database_id=$DATABASE_ID

# 3b. Data Generation
echo "🌱 Generating Synthetic Data..."
python3 generate_data.py --project_id=$PROJECT_ID --instance_id=$INSTANCE_ID --database_id=$DATABASE_ID

# 4. Create Artifact Registry Repository (if not exists)
echo "📦 Ensuring Artifact Registry Repository exists..."
gcloud artifacts repositories create $REPO_NAME \
    --repository-format=docker \
    --location=$REGION \
    --description="Docker repository for FSI Demos" \
    --quiet || echo "Repository likely already exists, proceeding..."

# 5. Build Container
echo "🔨 Building Container using Cloud Build..."
# Using --tag forces a build and push to Artifact Registry
gcloud builds submit --tag $IMAGE_NAME .

# 6. Deploy to Cloud Run
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

echo "✅ Deployment Complete! Check the Cloud Run URL above."
