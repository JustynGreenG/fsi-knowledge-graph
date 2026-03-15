#!/bin/bash

# Configuration
PROJECT_ID=${GCP_PROJECT_ID:-"justyn-demo-bank-ai"}
INSTANCE_ID=${SPANNER_INSTANCE_ID:-"fsi-demo-instance"}
DATABASE_ID=${SPANNER_DATABASE_ID:-"fsi-customer-db"}
REGION=${GCP_REGION:-"us-central1"}

# Pre-Requisite
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

# 1. Enable APIs
echo "🔌 Enabling Google Cloud APIs..."
gcloud services enable spanner.googleapis.com \
    aiplatform.googleapis.com \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    --project $PROJECT_ID

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

# Run Schema Script
python3 setup_schema.py --project_id=$PROJECT_ID --instance_id=$INSTANCE_ID --database_id=$DATABASE_ID

# 4. Data Generation
echo "🌱 Generating Synthetic Data..."
python3 generate_data.py --project_id=$PROJECT_ID --instance_id=$INSTANCE_ID --database_id=$DATABASE_ID

# 5. Deploy Streamlit App to Cloud Run
echo "🦄 Deploying Streamlit to Cloud Run..."
gcloud run deploy customer-twins-demo \
    --source . \
    --region $REGION \
    --project $PROJECT_ID \
    --allow-unauthenticated \
    --set-env-vars GCP_PROJECT_ID=$PROJECT_ID,SPANNER_INSTANCE_ID=$INSTANCE_ID,SPANNER_DATABASE_ID=$DATABASE_ID

echo "✅ Deployment Complete! Check the Cloud Run URL above."
