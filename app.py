import os
import streamlit as st
import pandas as pd
import networkx as nx
from pyvis.network import Network
import streamlit.components.v1 as components
import random
import time
import uuid
from google.cloud import spanner
from google.cloud import aiplatform

# --- CONFIGURATION ---
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "pv-knowledge-graph-demo")
SPANNER_INSTANCE_ID = os.environ.get("SPANNER_INSTANCE_ID", "fsi-demo-instance")
SPANNER_DATABASE_ID = os.environ.get("SPANNER_DATABASE_ID", "fsi-customer-db")
REGION = os.environ.get("GCP_REGION", "us-central1")

# Initialize Vertex AI
aiplatform.init(project=GCP_PROJECT_ID, location=REGION)

st.set_page_config(page_title="Customer Twin Simulator", layout="wide", page_icon="🏦")

# Inject FontAwesome
st.markdown('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">', unsafe_allow_html=True)

@st.cache_resource
def get_database():
    spanner_client = spanner.Client(project=GCP_PROJECT_ID)
    instance = spanner_client.instance(SPANNER_INSTANCE_ID)
    return instance.database(SPANNER_DATABASE_ID)

try:
    database = get_database()
except Exception as e:
    st.error(f"Failed to connect to Spanner. Error: {e}")
    st.stop()

# --- HELPER FUNCTIONS ---

def get_segments():
    try:
        with database.snapshot() as snapshot:
            rows = list(snapshot.execute_sql("SELECT DISTINCT segment FROM Customers"))
            return [r[0] for r in rows if r[0]]
    except Exception as e:
        return ["Young Professional", "Retiree"] # Fallback

def get_customer_graph(customer_id):
    """Fetches a subgraph for a specific customer."""
    query = """
    SELECT n.id, n.type, n.label, e.src, e.tgt, e.label as edge_label
    FROM GRAPH_TABLE(CustomerGraph
        MATCH (c:Customers)-[r]->(t)
        WHERE c.customer_id = @customer_id
        RETURN 
            c.customer_id as id, 'Customer' as type, c.name as label,
            t.account_id as tgt_id, 'Account' as tgt_type,
            r.label as edge_label
    )
    UNION ALL
    SELECT t.account_id, 'Account', t.type, 
           m.merchant_id as tgt_id, 'Merchant', m.name 
    FROM GRAPH_TABLE(CustomerGraph
        MATCH (c:Customers)-[:OWNS]->(a:Accounts)-[:EXECUTED_AT]->(m:Merchants)
        WHERE c.customer_id = @customer_id
        RETURN a.account_id, 'Account', a.type, m.merchant_id, 'Merchant', m.name
    )
    """
    # Simplified GQL for Demo (Spanner Graph syntax varies, using standard SQL for nodes/edges if GQL complex)
    # Reverting to SQL for safety and speed in this demo version
    
    nodes = []
    edges = []
    
    # SQL Implementation for robustness
    with database.snapshot() as snapshot:
        # Get Customer
        c_rows = list(snapshot.execute_sql("SELECT customer_id, name, segment FROM Customers WHERE customer_id = @id", params={"id": customer_id}, param_types={"id": spanner.param_types.STRING}))
        if not c_rows: return [], []
        
        c = c_rows[0]
        nodes.append({"id": c[0], "label": c[1], "type": "Customer", "title": f"Segment: {c[2]}"})
        
        # Get Accounts
        a_rows = list(snapshot.execute_sql("SELECT account_id, type, balance FROM Accounts WHERE customer_id = @id", params={"id": customer_id}, param_types={"id": spanner.param_types.STRING}))
        for a in a_rows:
            nodes.append({"id": a[0], "label": a[1], "type": "Account", "title": f"Balance: ${a[2]}"})
            edges.append({"from": customer_id, "to": a[0], "label": "OWNS"})
            
            # Get Interactions/Transactions for this account (Limit 5)
            t_rows = list(snapshot.execute_sql(
                "SELECT t.merchant_id, m.name, m.category, t.amount "
                "FROM Transactions t JOIN Merchants m ON t.merchant_id = m.merchant_id "
                "WHERE t.account_id = @aid ORDER BY t.timestamp DESC LIMIT 5",
                params={"aid": a[0]}, param_types={"aid": spanner.param_types.STRING}
            ))
            for t in t_rows:
                # Check if merchant node exists
                if not any(n['id'] == t[0] for n in nodes):
                    nodes.append({"id": t[0], "label": t[1], "type": "Merchant", "title": f"Category: {t[2]}"})
                edges.append({"from": a[0], "to": t[0], "label": f"PAID ${t[3]}"})

    return nodes, edges

def render_graph(nodes, edges):
    net = Network(height="500px", width="100%", bgcolor="#222222", font_color="white")
    
    for n in nodes:
        color = "#97c2fc" # Default Blue
        icon = None
        if n['type'] == 'Customer': 
            color = "#ff0000" # Red
            icon = "f007" # user
        elif n['type'] == 'Account': 
            color = "#00ff00" # Green
            icon = "f555" # wallet
        elif n['type'] == 'Merchant': 
            color = "#ffff00" # Yellow
            icon = "f54e" # store
            
        net.add_node(n['id'], label=n['label'], title=n['title'], color=color) # , shape='icon', icon={'face': "'Font Awesome 5 Free'", 'code': icon}
        
    for e in edges:
        net.add_edge(e['from'], e['to'], title=e['label'])
        
    path = f'/tmp/graph_{uuid.uuid4()}.html'
    net.save_graph(path)
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

# --- MAIN UI ---
st.title("🏦 Customer Twin Simulator")
st.markdown("### Hyper-Personalization with Spanner Graph & Vertex AI")

tab_explore, tab_simulate = st.tabs(["🔍 360° Explorer", "🤖 Twin Simulation"])

with tab_explore:
    c1, c2 = st.columns([1, 3])
    with c1:
        st.subheader("Select Customer")
        segment = st.selectbox("Segment", get_segments())
        
        # Get Customers in Segment
        cust_rows = []
        try:
            with database.snapshot() as snapshot:
                cust_rows = list(snapshot.execute_sql("SELECT customer_id, name FROM Customers WHERE segment = @seg LIMIT 20", params={"seg": segment}, param_types={"seg": spanner.param_types.STRING}))
        except: pass
        
        cust_dict = {r[1]: r[0] for r in cust_rows}
        selected_name = st.selectbox("Customer Name", list(cust_dict.keys()))
        
    with c2:
        if selected_name:
            cust_id = cust_dict[selected_name]
            st.markdown(f"#### Graph View: {selected_name}")
            nodes, edges = get_customer_graph(cust_id)
            html = render_graph(nodes, edges)
            components.html(html, height=520, scrolling=True)

with tab_simulate:
    st.subheader("🚀 Product Launch Simulation")
    
    c_prod, c_res = st.columns([1, 1])
    
    with c_prod:
        st.info("Define a new product to test against this segment.")
        prod_name = st.text_input("Product Name", "Platinum Travel Card")
        prod_terms = st.text_area("Product Terms", "Zero FX fees. 5x points on Travel. $400 Annual Fee.")
        
        start_sim = st.button("Run Simulation on Segment", type="primary")
        
    with c_res:
        if start_sim:
            st.success(f"Simulating reaction of {len(cust_dict)} Twins in '{segment}'...")
            progress_bar = st.progress(0)
            
            results = []
            
            # MOCK SIMULATION FOR DEMO SPEED (Replace with actual Vertex AI call in loop)
            for i, (name, cid) in enumerate(cust_dict.items()):
                time.sleep(0.1) 
                
                # Simple logic for mock: "Travel" in segment or transactions -> High
                score = random.randint(10, 90)
                sentiment = "POSITIVE" if score > 50 else "NEGATIVE"
                dataset_row = {"Customer": name, "Adoption %": score, "Sentiment": sentiment, "Reasoning": f"Based on my spending in {random.choice(['Travel', 'Grocery', 'Dining'])}, this looks {'interesting' if score > 50 else 'irrelevant'}."}
                results.append(dataset_row)
                progress_bar.progress((i + 1) / len(cust_dict))
                
            st.dataframe(pd.DataFrame(results))
            
            avg_score = sum([r['Adoption %'] for r in results]) / len(results)
            st.metric("Predicted Market Penetration", f"{avg_score:.1f}%")
