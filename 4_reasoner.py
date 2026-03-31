import os
from langchain_ollama import ChatOllama
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
from langchain_chroma import Chroma 
from langchain_openai import ChatOpenAI
# 1. SETUP
os.environ["LANGCHAIN_TRACING_V2"] = "false"

# 2. CONNECT TO NEO4J (Symbolic)
graph = Neo4jGraph(
    url="bolt://localhost:7687", 
    username="neo4j", 
    password="password123" 
)

# 3. CONNECT TO VECTOR DB (Neuro/RAG)
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vector_db = Chroma(persist_directory="vector_db", embedding_function=embeddings)

# 4. LLM

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    api_key=st.secrets["OPENAI_API_KEY"]
)

# 5. THE REASONER FUNCTION
def run_audit(account_id):
    print(f"\n--- Auditing Account: {account_id} ---")
    
    # 1. RAG - Get Law
    # Using a safer way to get the context
    rules = vector_db.similarity_search("money laundering suspicious patterns", k=2)
    law = "\n".join([d.page_content for d in rules])
    
    # 2. Graph - Get Facts
    # We use llama3.2 here for better speed and stability
    llm_local = ChatOllama(model="llama3.2", temperature=0)
    
    chain = GraphCypherQAChain.from_llm(
        llm_local, 
        graph=graph, 
        verbose=True, 
        allow_dangerous_requests=True
    )
    
    # We make the question very specific to help the smaller model
    query = f"MATCH (c:Client {{id: '{account_id}'}}) OPTIONAL MATCH (c)-[r:SENT_MONEY_TO]->() RETURN count(r) as trans_count, sum(r.amount) as total_val"
    
    try:
        facts = chain.invoke({"query": query})
        facts_result = facts['result']
    except Exception as e:
        facts_result = f"Database query failed, but account exists. Error: {e}"
    
    # 3. Final Verdict
    prompt = f"""
    Compare these Rules to these Facts.
    Rules: {law}
    Facts: {facts_result}
    Verdict: Is account {account_id} suspicious? Explain.
    """
    return llm_local.invoke(prompt).content

# TEST IT
# Use an ID from your cleaned_transactions.csv
print(run_audit("C1231006851"))