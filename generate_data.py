import argparse
import os
import random
import uuid
from datetime import datetime, timedelta
from faker import Faker
from google.cloud import spanner

fake = Faker()

def log(msg):
    print(f"[GenerateData] {msg}")

def generate_customers(num=50):
    customers = []
    segments = ["Young Professional", "Retiree", "Student", "High Net Worth", "Family"]
    risks = ["LOW", "MEDIUM", "HIGH"]
    
    for _ in range(num):
        c_id = str(uuid.uuid4())
        customers.append({
            "customer_id": c_id,
            "name": fake.name(),
            "age": random.randint(18, 90),
            "segment": random.choice(segments),
            "risk_profile": random.choice(risks),
            "created_at": fake.date_time_this_decade()
        })
    return customers

def generate_accounts(customers):
    accounts = []
    types = ["SAVINGS", "CHECKING", "The credit account", "INVESTMENT", "LOAN"] # "The credit account" to match earlier thought, but standardizing to CREDIT
    
    for c in customers:
        # Each customer has 1-3 accounts
        num_accounts = random.randint(1, 3)
        for _ in range(num_accounts):
            accounts.append({
                "account_id": str(uuid.uuid4()),
                "customer_id": c["customer_id"],
                "type": random.choice(["SAVINGS", "CREDIT", "INVESTMENT"]), 
                "balance": round(random.uniform(100.0, 50000.0), 2),
                "created_at": c["created_at"] # Account created same time or after customer
            })
    return accounts

def generate_merchants(num=20):
    merchants = []
    categories = ["GROCERY", "DINING", "TRAVEL", "UTILITY", "ENTERTAINMENT"]
    
    for _ in range(num):
        merchants.append({
            "merchant_id": str(uuid.uuid4()),
            "name": fake.company(),
            "category": random.choice(categories),
            "location": fake.city()
        })
    return merchants

def generate_transactions(accounts, merchants, num_per_account=20):
    transactions = []
    
    for acc in accounts:
        # Generate varied transactions for each account
        for _ in range(random.randint(5, num_per_account)):
            m = random.choice(merchants)
            transactions.append({
                "transaction_id": str(uuid.uuid4()),
                "account_id": acc["account_id"],
                "merchant_id": m["merchant_id"],
                "amount": round(random.uniform(5.0, 500.0), 2),
                "timestamp": fake.date_time_between(start_date="-1y", end_date="now")
            })
    return transactions

def generate_products():
    products = [
        {"product_id": "prod-1", "name": "Gold Credit Card", "type": "CARD", "terms": "5% Cashback on Travel"},
        {"product_id": "prod-2", "name": "First Home Saver", "type": "SAVINGS", "terms": "4.5% Interest"},
        {"product_id": "prod-3", "name": "Travel Insurance", "type": "INSURANCE", "terms": "Global Coverage"},
        {"product_id": "prod-4", "name": "Personal Loan", "type": "LOAN", "terms": "Low rates for consolidation"},
    ]
    return products

def batch_insert(database, table, data):
    if not data:
        return
    
    keys = data[0].keys()
    columns = list(keys)
    values = [[d[k] for k in columns] for d in data]
    
    batch_size = 500
    for i in range(0, len(values), batch_size):
        batch = values[i:i+batch_size]
        with database.batch() as batch_txn:
            batch_txn.insert(
                table=table,
                columns=columns,
                values=batch
            )
    log(f"Inserted {len(data)} rows into {table}")

def main(project_id, instance_id, database_id):
    log("Generating Synthetic Data...")
    
    customers = generate_customers(100)
    accounts = generate_accounts(customers)
    merchants = generate_merchants(50)
    transactions = generate_transactions(accounts, merchants)
    products = generate_products()
    
    log(f"Generated: {len(customers)} Customers, {len(accounts)} Accounts, {len(merchants)} Merchants, {len(transactions)} Transactions")
    
    # Connect to Spanner
    spanner_client = spanner.Client(project=project_id)
    instance = spanner_client.instance(instance_id)
    database = instance.database(database_id)
    
    # Insert Data
    batch_insert(database, "Customers", customers)
    batch_insert(database, "Accounts", accounts)
    batch_insert(database, "Merchants", merchants)
    batch_insert(database, "Transactions", transactions)
    batch_insert(database, "Products", products)
    
    log("✅ Data Load Complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Customer Twins Data.")
    parser.add_argument("--project_id", default=os.environ.get("GCP_PROJECT_ID", "pv-knowledge-graph-demo")) 
    parser.add_argument("--instance_id", default=os.environ.get("SPANNER_INSTANCE_ID", "fsi-demo-instance"))
    parser.add_argument("--database_id", default=os.environ.get("SPANNER_DATABASE_ID", "fsi-customer-db"))
    
    args = parser.parse_args()
    
    main(args.project_id, args.instance_id, args.database_id)
