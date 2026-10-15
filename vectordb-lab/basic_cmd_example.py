import os
import chromadb
from chromadb.utils import embedding_functions
import dotenv
dotenv.load_dotenv() 
OPEN_API_KEY = os.getenv("OPENAI_API_KEY")
 
client = chromadb.Client()

openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=OPEN_API_KEY,
    model_name="text-embedding-3-small"
)

collection = client.create_collection(
    name="pe_orgair_kb",
    embedding_function=openai_ef,
    metadata={"hnsw:space": "cosine"}
)

documents = [
    {"id": "aapl-mda-2024", "content": "Apple's AI strategy focuses on on-device intelligence and privacy-preserving ML across all product lines.", "metadata": {"ticker": "AAPL", "section": "MD&A", "year": 2024}},
    {"id": "aapl-risk-2024", "content": "Risks related to AI regulation include potential compliance costs and restrictions on model deployment.", "metadata": {"ticker": "AAPL", "section": "Risk Factors", "year": 2024}},
    {"id": "msft-mda-2024", "content": "Microsoft Copilot integration across Office 365 drove 45% growth in Azure AI services revenue.", "metadata": {"ticker": "MSFT", "section": "MD&A", "year": 2024}},
    {"id": "meta-capex-2024", "content": "Meta plans to invest 35-40 billion in AI infrastructure including custom silicon and data centers.", "metadata": {"ticker": "META", "section": "MD&A", "year": 2024}},
]

collection.add(
    documents=[d["content"] for d in documents],
    ids=[d["id"] for d in documents],
    metadatas=[d["metadata"] for d in documents]
)

# Query
query = "What are companies investing in AI infrastructure?"
results = collection.query(query_texts=[query], n_results=3)

# Display results
for doc_id, doc, distance, meta in zip(
    results["ids"][0],
    results["documents"][0],
    results["distances"][0],
    results["metadatas"][0]
):
    similarity = 1.0 - distance
    print(f"[{meta['ticker']} | {meta['section']}] Score: {similarity:.3f}")
    print(f"  {doc[:80]}...")
    print()