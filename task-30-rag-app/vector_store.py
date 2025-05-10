# vector_store.py

import numpy as np
from typing import List, Dict, Any
import logging
import uuid # For unique IDs for chunks

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory "vector store"
# Structure: { "collection_name": [ {id: "chunk_uuid", "embedding": [...], "document": "text", "metadata": {...} }, ... ] }
_in_memory_store: Dict[str, List[Dict[str, Any]]] = {}

def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Computes cosine similarity between two vectors."""
    # Ensure inputs are numpy arrays for dot product and norm calculations
    np_vec1 = np.array(vec1)
    np_vec2 = np.array(vec2)
    
    dot_product = np.dot(np_vec1, np_vec2)
    norm_vec1 = np.linalg.norm(np_vec1)
    norm_vec2 = np.linalg.norm(np_vec2)
    
    if norm_vec1 == 0 or norm_vec2 == 0:
        return 0.0  # Avoid division by zero if one vector is all zeros
    
    similarity = dot_product / (norm_vec1 * norm_vec2)
    return float(similarity)


def get_or_create_agent_collection(collection_name: str) -> List[Dict[str, Any]]:
    """Gets or creates a list in our in-memory store for an agent's knowledge."""
    if collection_name not in _in_memory_store:
        _in_memory_store[collection_name] = []
        logger.info(f"Created new in-memory collection: {collection_name}")
    else:
        logger.info(f"Retrieved existing in-memory collection: {collection_name}")
    return _in_memory_store[collection_name]

def add_text_chunks_to_collection(
    collection_name: str,
    chunks: List[str],
    embeddings: List[List[float]],
    metadatas: List[Dict[str, Any]],
    ids: List[str] # Unique ID for each chunk, corresponds to chunks, embeddings, metadatas
):
    """Adds text chunks and their embeddings to the specified in-memory collection."""
    collection = get_or_create_agent_collection(collection_name)
    for i, chunk_text in enumerate(chunks):
        collection.append({
            "id": ids[i],
            "document": chunk_text,
            "embedding": embeddings[i],
            "metadata": metadatas[i]
        })
    logger.info(f"Added {len(chunks)} chunks to in-memory collection {collection_name}")

def query_collection(
    collection_name: str,
    query_embedding: List[float],
    n_results: int = 3
) -> List[Dict[str, Any]]:
    """Queries the in-memory collection for similar documents."""
    if collection_name not in _in_memory_store or not _in_memory_store[collection_name]:
        logger.warning(f"Collection {collection_name} not found or is empty.")
        return []

    collection = _in_memory_store[collection_name]
    
    # Calculate similarities
    similarities = []
    for item in collection:
        similarity_score = _cosine_similarity(query_embedding, item["embedding"])
        similarities.append({
            "id": item["id"],
            "document": item["document"],
            "metadata": item["metadata"],
            "similarity": similarity_score # Using 'similarity' instead of 'distance'
        })
        
    # Sort by similarity in descending order
    sorted_results = sorted(similarities, key=lambda x: x["similarity"], reverse=True)
    
    logger.info(f"Querying collection {collection_name}, found {len(sorted_results)} potential matches.")
    return sorted_results[:n_results]

def delete_collection(collection_name: str):
    """Deletes an entire collection from the in-memory store."""
    if collection_name in _in_memory_store:
        del _in_memory_store[collection_name]
        logger.info(f"Deleted in-memory collection: {collection_name}")
    else:
        logger.warning(f"Attempted to delete non-existent in-memory collection: {collection_name}")

def delete_documents_from_collection(collection_name: str, knowledge_source_id_to_delete: str):
    """Deletes documents associated with a specific knowledge_source_id from a collection."""
    if collection_name not in _in_memory_store:
        logger.warning(f"Collection {collection_name} not found for deleting documents.")
        return

    original_count = len(_in_memory_store[collection_name])
    _in_memory_store[collection_name] = [
        doc for doc in _in_memory_store[collection_name]
        if doc.get("metadata", {}).get("source_knowledge_id") != knowledge_source_id_to_delete
    ]
    deleted_count = original_count - len(_in_memory_store[collection_name])
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} documents from collection {collection_name} for source_id {knowledge_source_id_to_delete}")
    else:
        logger.info(f"No documents found to delete in collection {collection_name} for source_id {knowledge_source_id_to_delete}")