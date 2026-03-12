# 🏦 FSI Customer Twin Simulator

The **FSI Customer Twin Simulator** is a cutting-edge demonstration of hyper-personalization in the Financial Services Industry. Leveraging **Google Cloud Spanner Graph** and **Vertex AI**, it creates "digital twins" of customers to simulate their reactions to new financial products, enabling banks to test market entry and product features with unprecedented accuracy.

## 🌟 Key Features

- **🔍 360° Customer Explorer**: Visualize complex relationships between customers, their accounts, and their spending habits at merchants using an interactive graph interface.
- **🤖 Twin Simulation**: Run large-scale simulations on customer segments to predict the adoption rate and sentiment of new products (e.g., a "Platinum Travel Card").
- **⚡ Spanner Graph Backend**: Utilizes the powerful Graph capabilities of Google Cloud Spanner to perform multi-hop relationship queries in milliseconds.
- **🧠 Vertex AI Integration**: Uses generative AI to simulate human-like reasoning for each customer twin based on their historical data.

---

## 🏗️ Tech Stack

- **Frontend**: [Streamlit](https://streamlit.io/) (Python-based interactive UI)
- **Database**: [Google Cloud Spanner](https://cloud.google.com/spanner) (with Graph DDL)
- **AI/ML**: [Google Vertex AI](https://cloud.google.com/vertex-ai)
- **Deployment**: [Google Cloud Run](https://cloud.google.com/run)
- **Visualization**: [PyVis](https://pyvis.readthedocs.io/en/latest/)

---

## 🚀 Deployment Steps

Follow these steps to deploy the demo to your Google Cloud Project.

### 1. Prerequisites
- A Google Cloud Project with billing enabled.
- [Google Cloud SDK (gcloud CLI)](https://cloud.google.com/sdk/docs/install) installed and authenticated.
- Python 3.9 or higher.

### 2. Configure Environment
Set your environment variables to target your GCP project and preferred Spanner IDs:

```bash
export GCP_PROJECT_ID="your-project-id"
export SPANNER_INSTANCE_ID="fsi-demo-instance"
export SPANNER_DATABASE_ID="fsi-customer-db"
export GCP_REGION="us-central1"
```

### 3. Run the Deployment Script
The Repo includes a bash script that automates API enablement, schema creation, data generation, and Cloud Run deployment:

```bash
chmod +x deploy_v1.sh
./deploy_v1.sh
```

Alternatively, you can run the steps manually:

#### A. Enable APIs
```bash
gcloud services enable spanner.googleapis.com aiplatform.googleapis.com run.googleapis.com
```

#### B. Setup Spanner Schema
```bash
python3 setup_schema.py
```

#### C. Generate Synthetic Data
```bash
python3 generate_data.py
```

#### D. Deploy to Cloud Run
```bash
gcloud run deploy customer-twins-demo --source . --region $GCP_REGION --allow-unauthenticated
```

---

## 💻 Local Development

To run the application locally for testing:

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run Streamlit**:
   ```bash
   streamlit run app.py
   ```

*Note: Ensure you have valid GCP credentials configured locally (e.g., `gcloud auth application-default login`).*

---

## 📂 Repository Structure

| File | Description |
| :--- | :--- |
| `app.py` | The main Streamlit application logic and UI. |
| `setup_schema.py` | DDL script to create Spanner tables and the `CustomerGraph`. |
| `generate_data.py` | Python script to populate Spanner with synthetic FSI data. |
| `deploy_v1.sh` | Orchestrator script for full GCP deployment. |
| `requirements.txt` | Python dependencies list. |
| `pv-fsi-knowledge-graph/` | Supporting assets and sub-modules. |

---

## 🛡️ Disclaimer
This is a demonstration repository intended for educational and POC purposes. The data generated is entirely synthetic and does not represent real customers or transactions.
