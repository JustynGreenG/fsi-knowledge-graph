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
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "pv-fsi-knowledge-graph")
SPANNER_INSTANCE_ID = os.environ.get("SPANNER_INSTANCE_ID", "fsi-demo-instance")
SPANNER_DATABASE_ID = os.environ.get("SPANNER_DATABASE_ID", "fsi-customer-db")
SPANNER_DATABASE_ID = os.environ.get("SPANNER_DATABASE_ID", "fsi-customer-db")
REGION = os.environ.get("GCP_REGION", "us-central1")
MODEL_NAME = "gemini-2.5-flash" # As requested by user/reference

# Initialise Vertex AI
aiplatform.init(project=GCP_PROJECT_ID, location=REGION)

@st.cache_resource
def get_chat_model():
    from vertexai.generative_models import GenerativeModel
    return GenerativeModel(MODEL_NAME)

st.set_page_config(page_title="Customer Twin Simulator", layout="wide", page_icon="🏦")

# Inject FontAwesome
st.markdown('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">', unsafe_allow_html=True)

# --- CBA BRANDING CSS ---
st.markdown("""
<style>
    /* Main Background & Text */
    .stApp {
        background-color: #FFFFFF;
        color: #333333;
    }
    
    /* Headings */
    h1, h2, h3 {
        color: #111111 !important;
        font-family: 'Open Sans', sans-serif;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #F8F9FA;
        border-right: 1px solid #E0E0E0;
    }
    
    /* Buttons */
    .stButton > button {
        background-color: #FFCC00 !important;
        color: #000000 !important;
        border-radius: 4px;
        border: none;
        font-weight: bold;
    }
    .stButton > button:hover {
        background-color: #E6B800 !important;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        background-color: #F8F9FA;
        border-radius: 4px 4px 0 0;
        color: #333333;
        border: 1px solid #E0E0E0;
        border-bottom: none;
    }
    .stTabs [aria-selected="true"] {
        background-color: #FFCC00 !important;
        color: #000000 !important;
    }
    
    /* Metric Cards */
    [data-testid="stMetricValue"] {
        color: #111111 !important;
    }
    [data-testid="stMetricLabel"] {
        color: #555555 !important;
    }
</style>
""", unsafe_allow_html=True)

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
        st.error(f"Segment Query Error: {e}")
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
    with database.snapshot(multi_use=True) as snapshot:
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
            color = "#FFCC00" # CBA Yellow
            icon = "f007" # user
        elif n['type'] == 'Account': 
            color = "#FFFFFF" # White/Light for contrast
            icon = "f555" # wallet
        elif n['type'] == 'Merchant': 
            color = "#00CB53" # Green for merchant/money
            icon = "f54e" # store
            
        net.add_node(n['id'], label=n['label'], title=n['title'], color=color) # , shape='icon', icon={'face': "'Font Awesome 5 Free'", 'code': icon}
        
    for e in edges:
        net.add_edge(e['from'], e['to'], title=e['label'])
        
    path = f'/tmp/graph_{uuid.uuid4()}.html'
    net.save_graph(path)
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

# --- MAIN UI ---
st.title("🏦 CommBank Customer Twin Simulator")
st.markdown("### Hyper-Personalisation with Spanner Graph & Vertex AI")



# --- SIDEBAR (Global Context) ---
with st.sidebar:
    st.image("commbank-logo.svg", width=64) # Official SVG Logo
    st.header("👤 Customer Context")
    segment = st.selectbox("Select Segment", get_segments())
    
    # Get Customers in Segment
    cust_rows = []
    try:
        with database.snapshot() as snapshot:
            cust_rows = list(snapshot.execute_sql("SELECT customer_id, name FROM Customers WHERE segment = @seg LIMIT 20", params={"seg": segment}, param_types={"seg": spanner.param_types.STRING}))
    except Exception as e:
        st.error(f"Customer Query Error: {e}")
    
    cust_dict = {r[1]: r[0] for r in cust_rows}
    selected_name = st.selectbox("Select Customer", list(cust_dict.keys()))
    
    if selected_name:
        cust_id = cust_dict[selected_name]
        st.success(f"Active Twin: {selected_name}")
        st.info(f"ID: {cust_id[:8]}...")

# --- MAIN TAB UI ---
tab_explore, tab_chat, tab_simulate = st.tabs(["🔍 360° Explorer", "💬 Chat with Twin", "🤖 Twin Simulation"])

# 1. 360 EXPLORER
with tab_explore:
    if selected_name:
        st.subheader(f"Graph View: {selected_name}")
        st.markdown("""
        <div style="margin-bottom: 10px;">
            <span style="color: #E6B800; font-weight: bold;">● Customer</span> &nbsp;&nbsp;
            <span style="color: #666666; font-weight: bold;">● Account</span> &nbsp;&nbsp;
            <span style="color: #00C853; font-weight: bold;">● Merchant</span>
        </div>
        """, unsafe_allow_html=True)
        nodes, edges = get_customer_graph(cust_id)
        html = render_graph(nodes, edges)
        components.html(html, height=520, scrolling=True)
    else:
        st.info("Please select a customer from the sidebar.")

# 2. CHAT WITH TWIN
with tab_chat:
    st.subheader("💬 Chat with Knowledge Plane")
    
    if selected_name:
        # Prepare Context
        nodes, edges = get_customer_graph(cust_id)
        
        # Simple Context Serialiser
        context_text = f"Customer: {selected_name}\n\nContext Graph:\n"
        for n in nodes:
            context_text += f"- Node ({n['type']}): {n['label']} ({n.get('title','')})\n"
        for e in edges:
            context_text += f"- Edge: {e['from']} -[{e['label']}]-> {e['to']}\n"
            
        # Chat History
        if "messages" not in st.session_state:
            st.session_state.messages = []

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input(f"Ask about {selected_name}..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                model = get_chat_model()
                full_prompt = f"""You are an expert CommBank AI Assistant analysing a Customer Twin Knowledge Graph.

                Data Context:
                {context_text}

                User Question: {prompt}

                Reasoning Guidelines:
                1. ANALYZE: First, scan the graph data for spending patterns, merchant categories, and financial health indicators.
                2. CONNECT: Relate these data points to the user's question (e.g., "Frequent coffee" -> "Lifestyle").
                3. EVIDENCE: Always cite specific merchant names or transaction amounts to back up your insights.
                
                Response Guidelines:
                - Tone: Professional, empathetic, and distinctly CommBank (warm & helpful).
                - For "Draft Email" requests: Create a polished, ready-to-send email with a subject line, using specific details from the context to personalise it.
                - For General Questions: Provide a direct answer followed by a brief "Why?" (evidence).
                - Keep responses concise unless asked for detailed drafts.
                """
                
                try:
                    response = model.generate_content(full_prompt)
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"GenAI Error: {e}")
    else:
        st.warning("Select a customer in the sidebar to start chatting.")

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
