import argparse
import os
from google.cloud import spanner

def log(msg):
    print(f"[SetupSchema] {msg}")

def apply_ddl(project_id, instance_id, database_id):
    log(f"Connecting to {project_id}/{instance_id}/{database_id}...")
    spanner_client = spanner.Client(project=project_id)
    instance = spanner_client.instance(instance_id)
    database = instance.database(database_id)

    # --- 1. TABLES DDL ---
    # We use STRING(MAX) for IDs to allow UUIDs.
    # We use TIMESTAMP for time.
    # We Use FLOAT64 for money (Demo only; use NUMERIC in production).
    
    tables_ddl = [
        """CREATE TABLE Customers (
            customer_id STRING(MAX) NOT NULL,
            name STRING(MAX),
            age INT64,
            segment STRING(MAX),
            risk_profile STRING(MAX),
            created_at TIMESTAMP
        ) PRIMARY KEY (customer_id)""",

        """CREATE TABLE Accounts (
            account_id STRING(MAX) NOT NULL,
            customer_id STRING(MAX) NOT NULL,
            type STRING(MAX), -- 'SAVINGS', 'CREDIT', 'INVESTMENT'
            balance FLOAT64,
            created_at TIMESTAMP,
            CONSTRAINT FK_CustomerAccount FOREIGN KEY (customer_id) REFERENCES Customers (customer_id)
        ) PRIMARY KEY (account_id)""",

        """CREATE TABLE Merchants (
            merchant_id STRING(MAX) NOT NULL,
            name STRING(MAX),
            category STRING(MAX), -- 'GROCERY', 'TRAVEL', 'DINING'
            location STRING(MAX)
        ) PRIMARY KEY (merchant_id)""",

        """CREATE TABLE Transactions (
            transaction_id STRING(MAX) NOT NULL,
            account_id STRING(MAX) NOT NULL,
            merchant_id STRING(MAX) NOT NULL,
            amount FLOAT64,
            timestamp TIMESTAMP,
            CONSTRAINT FK_AccountTx FOREIGN KEY (account_id) REFERENCES Accounts (account_id),
            CONSTRAINT FK_MerchantTx FOREIGN KEY (merchant_id) REFERENCES Merchants (merchant_id)
        ) PRIMARY KEY (transaction_id)""",
        
        """CREATE TABLE Products (
            product_id STRING(MAX) NOT NULL,
            name STRING(MAX),
            type STRING(MAX), -- 'LOAN', 'CARD', 'INSURANCE'
            terms STRING(MAX)
        ) PRIMARY KEY (product_id)""",

        """CREATE TABLE CustomerProductInteractions (
            interaction_id STRING(MAX) NOT NULL,
            customer_id STRING(MAX) NOT NULL,
            product_id STRING(MAX) NOT NULL,
            interaction_type STRING(MAX), -- 'VIEWED', 'PURCHASED', 'REJECTED'
            timestamp TIMESTAMP,
            CONSTRAINT FK_CustProd FOREIGN KEY (customer_id) REFERENCES Customers (customer_id),
            CONSTRAINT FK_ProdInt FOREIGN KEY (product_id) REFERENCES Products (product_id)
        ) PRIMARY KEY (interaction_id)"""
    ]

    # --- 2. GRAPH DDL ---
    graph_ddl = """CREATE PROPERTY GRAPH CustomerGraph
          NODE TABLES (
            Customers,
            Accounts,
            Merchants,
            Products
          )
          EDGE TABLES (
            Accounts AS OWNS
              SOURCE KEY (customer_id) REFERENCES Customers (customer_id)
              DESTINATION KEY (account_id) REFERENCES Accounts (account_id)
              LABEL OWNS,
            
            Transactions AS EXECUTED_AT
              SOURCE KEY (account_id) REFERENCES Accounts (account_id)
              DESTINATION KEY (merchant_id) REFERENCES Merchants (merchant_id)
              LABEL EXECUTED_AT,
              
            CustomerProductInteractions AS INTERACTED_WITH
              SOURCE KEY (customer_id) REFERENCES Customers (customer_id)
              DESTINATION KEY (product_id) REFERENCES Products (product_id)
              LABEL INTERACTED_WITH
          )"""

    # Apply Tables
    try:
        log("Creating Tables...")
        operation = database.update_ddl(tables_ddl)
        operation.result(timeout=300)
        log("✅ Tables Created.")
    except Exception as e:
        if "Duplicate name" in str(e):
            log("ℹ️ Tables likely already exist. Skipping.")
        else:
            log(f"❌ Failed to create tables: {e}")

    # Apply Graph
    try:
        log("Creating 'CustomerGraph' property graph...")
        operation = database.update_ddl([graph_ddl])
        operation.result(timeout=300)
        log("✅ Created 'CustomerGraph'.")
    except Exception as e:
        if "Duplicate name" in str(e):
            log("ℹ️ Graph 'CustomerGraph' already exists. Skipping.")
        else:
            log(f"❌ Failed to create graph: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply Spanner Graph DDL for Customer Twins.")
    parser.add_argument("--project_id", default=os.environ.get("GCP_PROJECT_ID", "pv-knowledge-graph-demo")) 
    parser.add_argument("--instance_id", default=os.environ.get("SPANNER_INSTANCE_ID", "fsi-demo-instance"))
    parser.add_argument("--database_id", default=os.environ.get("SPANNER_DATABASE_ID", "fsi-customer-db"))
    
    args = parser.parse_args()
    
    apply_ddl(args.project_id, args.instance_id, args.database_id)
