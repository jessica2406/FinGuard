import streamlit as st
import os
from langchain_ollama import ChatOllama
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_neo4j import Neo4jGraph

# --- SETUP ---
st.set_page_config(page_title="FinGuard AI Auditor", layout="wide")
st.title("🏦 FinGuard: Neuro-Symbolic AML Compliance")

@st.cache_resource
def init_connections():
    graph = Neo4jGraph(
    url=st.secrets["NEO4J_URI"],
    username=st.secrets["NEO4J_USERNAME"],
    password=st.secrets["NEO4J_PASSWORD"],
    enhanced_schema=False
)
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vector_db = Chroma(persist_directory="vector_db", embedding_function=embeddings)
    llm = ChatOllama(model="llama3.2", temperature=0)
    return graph, vector_db, llm

graph, vector_db, llm = init_connections()

# --- SIDEBAR ---
st.sidebar.header("Audit Settings")
account_id = st.sidebar.text_input("Enter Account ID:", value="C1231006851")
run_btn = st.sidebar.button("Run Compliance Audit")

if run_btn:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📖 Step 1: Regulatory Retrieval (Neuro)")
        rules = vector_db.similarity_search("suspicious transaction reporting threshold", k=2)
        legal_context = "\n".join([d.page_content for d in rules])
        st.info(legal_context[:500] + "...")

    with col2:
        st.subheader("🕸️ Step 2: Graph Analysis (Symbolic)")
        # We check both outgoing AND incoming transactions to get the full picture
        cypher_query = f"""
        MATCH (c:Client {{id: '{account_id}'}})
        OPTIONAL MATCH (c)-[r]-()
        RETURN 
            c.id as id, 
            count(r) as total_tx, 
            sum(CASE WHEN startNode(r) = c THEN r.amount ELSE 0 END) as sent_val,
            sum(CASE WHEN endNode(r) = c THEN r.amount ELSE 0 END) as received_val,
            sum(r.isFraud) as fraud_count
        """
        graph_data = graph.query(cypher_query)
        
        if graph_data and graph_data[0]['id']:
            stats = graph_data[0]
            facts = f"""
            - Account: {stats['id']}
            - Total Activity Count: {stats['total_tx']}
            - Total Sent: ${stats['sent_val']:,.2f}
            - Total Received: ${stats['received_val']:,.2f}
            - Connections to Known Fraud: {stats['fraud_count']}
            """
            st.success("Graph Data Retrieved!")
            st.code(facts)
        else:
            facts = "Account not found in the transaction sample."
            st.error(facts)

    st.divider()
    st.subheader("⚖️ Step 3: Final Compliance Verdict")
    
    # We tell the AI how to interpret "0" data
    verdict_prompt = f"""
    You are a Senior AML Auditor. Analyze the risk of this account.
    
    LAWS: {legal_context}
    DATA: {facts}
    
    INSTRUCTIONS:
    1. If 'Connections to Known Fraud' > 0, verdict is HIGH RISK.
    2. If 'Total Activity' is 0, verdict is LOW RISK (Inactive Account).
    3. If 'Total Sent' is very high but no fraud markers, verdict is MEDIUM RISK.
    
    Provide:
    - RISK SCORE
    - JUSTIFICATION
    """
    with st.spinner("Analyzing..."):
        final_verdict = llm.invoke(verdict_prompt)
        st.markdown(f"### {final_verdict.content}")