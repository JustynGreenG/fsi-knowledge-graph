from google.cloud import spanner
import os

project_id = os.environ.get("GCP_PROJECT_ID", "pv-fsi-knowledge-graph")
instance_id = os.environ.get("SPANNER_INSTANCE_ID", "fsi-demo-instance")
database_id = os.environ.get("SPANNER_DATABASE_ID", "fsi-customer-db")

print(f"Checking Spanner: {project_id}/{instance_id}/{database_id}")

try:
    client = spanner.Client(project=project_id)
    instance = client.instance(instance_id)
    database = instance.database(database_id)

    print("--- Row Counts ---")
    for table in ["Customers", "Accounts", "Merchants", "Transactions", "Products"]:
        try:
            with database.snapshot() as snapshot:
                rows = list(snapshot.execute_sql(f"SELECT COUNT(*) FROM {table}"))
                print(f"{table}: {rows[0][0]}")
        except Exception as e:
            print(f"{table}: Error - {e}")

except Exception as e:
    print(f"FATAL CONNECTION ERROR: {e}")
