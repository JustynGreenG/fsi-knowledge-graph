FROM python:3.11-slim

# Install system dependencies
# graphviz is often required for graph visualization libraries
RUN apt-get update && apt-get install -y \
    graphviz \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# Install dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Expose port
EXPOSE 8080

# Set entrypoint
ENTRYPOINT ["./entrypoint.sh"]
