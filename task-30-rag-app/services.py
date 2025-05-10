import os
import logging
import uuid
from typing import List

from dotenv import load_dotenv
from google import genai
from google.genai import types

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load API key
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize Gemini Client
genai_client = None
if GEMINI_API_KEY:
    try:
        genai_client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info("Google GenAI Client initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing Google GenAI Client: {e}")
else:
    logger.error("GEMINI_API_KEY not found in .env file. Google GenAI Client will not be functional.")


# Embedding: Single
def get_gemini_embedding(text_input: str, model_name: str = "gemini-embedding-exp-03-07") -> List[float]:
    if not genai_client:
        raise ValueError("Gemini client not initialized. Check GEMINI_API_KEY.")
    try:
        result = genai_client.models.embed_content(
            model=model_name,
            contents=text_input,
            config=types.EmbedContentConfig(task_type="SEMANTIC_SIMILARITY")
        )
        return result.embeddings[0].values
    except Exception as e:
        logger.error(f"Error generating Gemini embedding: {e}")
        raise


# Embedding: Batch
def get_gemini_embeddings_batch(texts: List[str], model_name: str = "gemini-embedding-exp-03-07") -> List[List[float]]:
    if not genai_client:
        raise ValueError("Gemini client not initialized.")
    try:
        result = genai_client.models.embed_content(
            model=model_name,
            contents=texts,
            config=types.EmbedContentConfig(task_type="SEMANTIC_SIMILARITY")
        )
        return [embedding.values for embedding in result.embeddings]
    except Exception as e:
        logger.error(f"Error generating Gemini batch embeddings: {e}")
        raise


# Text Generation
def generate_gemini_chat_response(
    model_name: str,
    system_prompt: str,
    context: str,
    user_query: str,
    max_tokens: int = 1000
) -> str:
    if not genai_client:
        raise ValueError("Gemini client not initialized.")

    # Compose the prompt
    effective_prompt = ""
    if system_prompt:
        effective_prompt += f"{system_prompt.strip()}\n\n"
    if context:
        effective_prompt += f"Context:\n{context.strip()}\n\n"
    effective_prompt += f"User: {user_query.strip()}"

    try:
        response = genai_client.models.generate_content(
            model=model_name,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=max_tokens
            ),
            contents=effective_prompt
        )
        return response.text
    except Exception as e:
        logger.error(f"Error generating Gemini response: {e}")
        return f"An error occurred: {str(e)}"


# Basic Chunker
def simple_text_chunker(text: str, chunk_size: int = 1000, chunk_overlap: int = 100) -> List[str]:
    if not text:
        return []
    chunk_size = max(1, chunk_size)
    chunk_overlap = min(max(0, chunk_overlap), chunk_size - 1)

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start += chunk_size - chunk_overlap
        if start <= (end - chunk_size):
            logger.warning("Chunker start index not advancing, breaking.")
            break
    return [chunk for chunk in chunks if chunk.strip()]
