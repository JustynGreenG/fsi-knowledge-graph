#!/bin/bash
set -e

# Default to app.py if not specified
SCRIPT_NAME=${DASHBOARD_SCRIPT:-"app.py"}

echo "🚀 Starting Streamlit App: $SCRIPT_NAME"
exec streamlit run $SCRIPT_NAME --server.port $PORT --server.address 0.0.0.0
