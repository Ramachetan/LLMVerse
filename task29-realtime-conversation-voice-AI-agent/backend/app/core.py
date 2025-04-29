import os
import uuid
import json
from google import generativeai as genai  # Update the import
from langchain_text_splitters import RecursiveCharacterTextSplitter
import faiss
import numpy as np
from pathlib import Path

# --- Configuration ---
DATA_DIR = Path(__file__).parent / "data"
KBS_DIR = DATA_DIR / "kbs"
INDICES_DIR = DATA_DIR / "indices"
EMBEDDING_MODEL = "models/embedding-001"
GENERATION_MODEL = "gemini-1.5-flash-latest" # Or other suitable model
TEXT_SPLITTER_CHUNK_SIZE = 1000
TEXT_SPLITTER_CHUNK_OVERLAP = 150
FAISS_DIMENSION = 768 # Dimension for models/embedding-001
TOP_K_RESULTS = 3

# Ensure data directories exist
KBS_DIR.mkdir(parents=True, exist_ok=True)
INDICES_DIR.mkdir(parents=True, exist_ok=True)

# Configure Google Generative AI (call this at app startup)
def configure_genai():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set.")
    genai.configure(api_key=api_key)  # This now works with the correct import
    print("Google Generative AI configured.")



# --- Knowledge Base Processing ---

def process_kb_file(file_path: Path, kb_id: str):
    """Reads, chunks, embeds, and stores a KB file."""
    try:
        text = file_path.read_text(encoding='utf-8')

        # 1. Chunk Text
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=TEXT_SPLITTER_CHUNK_SIZE,
            chunk_overlap=TEXT_SPLITTER_CHUNK_OVERLAP,
        )
        chunks = text_splitter.split_text(text)

        if not chunks:
            print(f"Warning: No text chunks generated for {kb_id}")
            return None, None # Indicate failure or empty content

        print(f"Generated {len(chunks)} chunks for KB {kb_id}")

        # 2. Embed Chunks
        # Note: Batching might be needed for very large files to avoid API limits
        # Using task_type="RETRIEVAL_DOCUMENT" is recommended for documents to be retrieved
        result = genai.embed_content(
            model=EMBEDDING_MODEL,
            content=chunks,
            task_type="RETRIEVAL_DOCUMENT",
            # Optional: title=f"KB {kb_id}" # Add metadata if desired
        )
        embeddings = result['embedding']

        # 3. Create and Save FAISS Index
        index = faiss.IndexFlatL2(FAISS_DIMENSION) # Using L2 distance
        index.add(np.array(embeddings, dtype=np.float32))

        index_path = INDICES_DIR / f"{kb_id}.faiss"
        faiss.write_index(index, str(index_path))

        # 4. Save Chunks Mapping (mapping index position to text chunk)
        chunks_path = INDICES_DIR / f"{kb_id}_chunks.json"
        with open(chunks_path, 'w', encoding='utf-8') as f:
            json.dump(chunks, f)

        print(f"Successfully processed and saved index/chunks for KB {kb_id}")
        return str(index_path), str(chunks_path)

    except Exception as e:
        print(f"Error processing KB file {file_path}: {e}")
        # Consider more robust error handling/logging
        return None, None


# --- RAG Core Logic ---

def get_rag_response(query_text: str, kb_id: str) -> str:
    """Performs RAG to answer a query based on a specific KB."""
    index_path = INDICES_DIR / f"{kb_id}.faiss"
    chunks_path = INDICES_DIR / f"{kb_id}_chunks.json"

    if not index_path.exists() or not chunks_path.exists():
        print(f"Error: Index or chunks file not found for KB {kb_id}")
        return "I'm sorry, I cannot access the knowledge base information right now."

    try:
        # 1. Load Index and Chunks
        index = faiss.read_index(str(index_path))
        with open(chunks_path, 'r', encoding='utf-8') as f:
            chunks = json.load(f)

        # 2. Embed the Query
        # Using task_type="RETRIEVAL_QUERY" for queries
        query_embedding_result = genai.embed_content(
            model=EMBEDDING_MODEL,
            content=query_text,
            task_type="RETRIEVAL_QUERY"
        )
        query_embedding = np.array(query_embedding_result['embedding'], dtype=np.float32).reshape(1, -1)

        # 3. Search the Vector Store
        distances, indices = index.search(query_embedding, TOP_K_RESULTS)

        # 4. Retrieve Relevant Chunks
        relevant_chunks = [chunks[i] for i in indices[0]] # indices[0] because query is single vector

        # 5. Construct Prompt for LLM
        context = "\n---\n".join(relevant_chunks)
        prompt = f"""You are a helpful assistant answering questions based *only* on the provided context. Your knowledge is limited to the text given below. If the answer is not found in the context, you MUST say 'I don't have information on that.' Do not make up answers.

Context:
{context}

Question: {query_text}

Answer:"""

        # 6. Call Google GenAI Model
        model = genai.GenerativeModel(GENERATION_MODEL)
        response = model.generate_content(prompt)

        return response.text.strip()

    except Exception as e:
        print(f"Error during RAG for query '{query_text}' on KB {kb_id}: {e}")
        # Consider more robust error handling/logging
        return "I encountered an error while trying to answer your question."