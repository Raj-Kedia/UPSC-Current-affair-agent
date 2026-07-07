import os
import json
import chromadb
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from src.config import DATA_DIR, GEMINI_API_KEY, logger

# Initialize ChromaDB
CHROMA_PATH = os.path.join(DATA_DIR, 'chroma_db')
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)

# Use Gemini embeddings
def get_embeddings():
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY is not set. Cannot use Gemini embeddings.")
        return None
    return GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=GEMINI_API_KEY)

def load_local_pyqs():
    """Load local mains PYQs database if it exists."""
    path = os.path.join(DATA_DIR, 'upsc_mains_pyqs.json')
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading local PYQs: {e}")
    return {}

def initialize_pyq_vector_store():
    """Reads the JSON PYQ database and ingests it into ChromaDB if not already present."""
    collection = chroma_client.get_or_create_collection(name="upsc_pyqs")
    
    # Check if we already have documents
    if collection.count() > 0:
        logger.info(f"Vector DB already initialized with {collection.count()} PYQs.")
        return collection
        
    embeddings_model = get_embeddings()
    if not embeddings_model:
        logger.warning("Cannot initialize Vector DB without embeddings model.")
        return collection
        
    logger.info("Initializing Vector DB with PYQs...")
    local_pyqs = load_local_pyqs()
    if not local_pyqs:
        logger.warning("No local PYQs found to embed.")
        return collection
        
    documents = []
    metadatas = []
    ids = []
    
    for paper_key, questions in local_pyqs.items():
        for q in questions:
            q_id = f"pyq_{q.get('Id')}_{paper_key}_{q.get('Year')}"
            q_text = q.get('Question', '')
            
            if q_text:
                documents.append(q_text)
                metadatas.append({
                    'Paper': paper_key,
                    'Year': q.get('Year', ''),
                    'Marks': q.get('Marks', ''),
                    'type': 'pyq'
                })
                ids.append(q_id)
                
    # Batch add to avoid limits (Chroma handles this automatically up to a point, but good practice)
    batch_size = 100
    for i in range(0, len(documents), batch_size):
        logger.info(f"Adding batch {i//batch_size + 1} of PYQs to Vector DB...")
        batch_docs = documents[i:i+batch_size]
        batch_metadatas = metadatas[i:i+batch_size]
        batch_ids = ids[i:i+batch_size]
        
        # We need to manually embed if using raw chromadb with langchain embeddings
        embeddings = embeddings_model.embed_documents(batch_docs)
        
        collection.add(
            documents=batch_docs,
            embeddings=embeddings,
            metadatas=batch_metadatas,
            ids=batch_ids
        )
        
    logger.info(f"Successfully added {len(documents)} PYQs to Vector DB.")
    return collection

def semantic_search_pyqs(query, max_results=3):
    """Search ChromaDB for related questions based on semantic meaning."""
    collection = chroma_client.get_or_create_collection(name="upsc_pyqs")
    if collection.count() == 0:
        logger.warning("Vector DB is empty. Initializing now...")
        collection = initialize_pyq_vector_store()
        
    if collection.count() == 0:
        return []
        
    embeddings_model = get_embeddings()
    if not embeddings_model:
        return []
        
    query_embedding = embeddings_model.embed_query(query)
    
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=max_results
    )
    
    matches = []
    if results['documents'] and len(results['documents']) > 0:
        for i in range(len(results['documents'][0])):
            matches.append({
                'Question': results['documents'][0][i],
                'Paper': results['metadatas'][0][i].get('Paper'),
                'Year': results['metadatas'][0][i].get('Year'),
                'Marks': results['metadatas'][0][i].get('Marks')
            })
            
    return matches

if __name__ == "__main__":
    initialize_pyq_vector_store()
