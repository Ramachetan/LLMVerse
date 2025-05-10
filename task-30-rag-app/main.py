from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import logging
import uuid
import crud
import models
import schemas
import services
import vector_store
from database import engine, get_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="LLM Agent POC Backend", version="0.1.0")

def get_agent_or_404(agent_id: str, db: Session = Depends(get_db)):
    db_agent = crud.get_agent(db, agent_id=agent_id)
    if db_agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return db_agent

@app.post("/agents/", response_model=schemas.AgentResponse, status_code=status.HTTP_201_CREATED, tags=["Agents"])
def create_agent(agent: schemas.AgentCreate, db: Session = Depends(get_db)):
    db_agent = crud.create_agent(db=db, agent=agent)
    logger.info(f"Agent created: {db_agent.id} - {db_agent.name}")
    return db_agent

@app.get("/agents/", response_model=List[schemas.AgentResponse], tags=["Agents"])
def read_agents(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_agents(db, skip=skip, limit=limit)

@app.get("/agents/{agent_id}", response_model=schemas.AgentResponse, tags=["Agents"])
def read_agent(agent: models.Agent = Depends(get_agent_or_404)):
    return agent

@app.post("/agents/{agent_id}/knowledge/text", response_model=schemas.KnowledgeSourceResponse, status_code=status.HTTP_201_CREATED, tags=["Knowledge"])
def add_text_knowledge_to_agent(
    agent_id: str,
    knowledge_data: schemas.KnowledgeTextCreate,
    db: Session = Depends(get_db)
):
    db_agent = get_agent_or_404(agent_id, db)
    db_knowledge_source = crud.create_knowledge_source(
        db=db,
        agent_id=db_agent.id,
        source_name=knowledge_data.source_name,
        content_type="text"
    )
    logger.info(f"Knowledge source record created: {db_knowledge_source.id} for agent {db_agent.id}")

    chunks = services.simple_text_chunker(knowledge_data.text_content, chunk_size=500, chunk_overlap=50)
    if not chunks:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No text content to process after chunking.")

    try:
        embeddings = services.get_gemini_embeddings_batch(texts=chunks, model_name=db_agent.embedding_model_name)
    except Exception as e:
        logger.error(f"Failed to get embeddings for agent {db_agent.id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate embeddings: {e}")

    chroma_ids = [f"{db_knowledge_source.id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [{"source_knowledge_id": str(db_knowledge_source.id), "agent_id": str(db_agent.id), "chunk_index": i, "original_source_name": knowledge_data.source_name} for i in range(len(chunks))]

    collection_name = f"agent_{db_agent.id}_knowledge"
    try:
        vector_store.add_text_chunks_to_collection(
            collection_name=collection_name,
            chunks=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=chroma_ids
        )
        logger.info(f"Added {len(chunks)} chunks to ChromaDB for agent {db_agent.id}, knowledge {db_knowledge_source.id}")
    except Exception as e:
        logger.error(f"Failed to add chunks to ChromaDB for agent {db_agent.id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to store knowledge in vector store: {e}")

    return db_knowledge_source

@app.post("/agents/{agent_id}/chat", response_model=schemas.ChatResponse, tags=["Interaction"])
def chat_with_agent(
    agent_id: str,
    chat_request: schemas.ChatRequest,
    db: Session = Depends(get_db)
):
    db_agent = get_agent_or_404(agent_id, db)

    try:
        query_embedding = services.get_gemini_embedding(
            text_input=chat_request.query,
            model_name=db_agent.embedding_model_name,
        )
    except Exception as e:
        logger.error(f"Failed to embed query for agent {db_agent.id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process query embedding: {e}")

    collection_name = f"agent_{db_agent.id}_knowledge"
    retrieved_docs = vector_store.query_collection(
        collection_name=collection_name,
        query_embedding=query_embedding,
        n_results=3
    )

    context_for_llm = "\n\n".join([doc['document'] for doc in retrieved_docs if doc['document']])
    retrieved_source_names = list(set([doc['metadata'].get('original_source_name', 'Unknown') for doc in retrieved_docs if doc.get('metadata')]))

    if not context_for_llm:
        logger.info(f"No relevant context found for query for agent {db_agent.id}.")

    try:
        llm_response_text = services.generate_gemini_chat_response(
            model_name=db_agent.llm_model_name,
            system_prompt=db_agent.system_prompt,
            context=context_for_llm,
            user_query=chat_request.query,
            max_tokens=chat_request.max_tokens_response
        )
    except Exception as e:
        logger.error(f"Failed to get LLM response for agent {db_agent.id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="LLM interaction failed: {e}")

    return schemas.ChatResponse(
        agent_id=db_agent.id,
        query=chat_request.query,
        response=llm_response_text,
        retrieved_source_names=retrieved_source_names
    )
    
@app.delete("/agents/{agent_id}", status_code=status.HTTP_200_OK, tags=["Agents"])
def delete_agent(agent_id: str, db: Session = Depends(get_db)):
    db_agent = get_agent_or_404(agent_id, db)
    crud.delete_agent(db=db, agent_id=db_agent.id)
    logger.info(f"Agent deleted: {db_agent.id}")
    return {"detail": "Agent deleted successfully."}

@app.delete("/agents/{agent_id}/knowledge/{knowledge_source_id}", status_code=status.HTTP_200_OK, tags=["Knowledge"])
def delete_knowledge_source(
    agent_id: str,
    knowledge_source_id: str,
    db: Session = Depends(get_db)
):
    db_agent = get_agent_or_404(agent_id, db)
    db_knowledge_source = crud.get_knowledge_source(db, knowledge_source_id=knowledge_source_id)
    if db_knowledge_source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge source not found")

    collection_name = f"agent_{db_agent.id}_knowledge"
    vector_store.delete_documents_from_collection(
        collection_name=collection_name,
        knowledge_source_id_to_delete=db_knowledge_source.id
    )

    crud.delete_knowledge_source(db=db, knowledge_source_id=db_knowledge_source.id)
    logger.info(f"Knowledge source deleted: {db_knowledge_source.id} for agent {db_agent.id}")
    return {"detail": "Knowledge source deleted successfully."}

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Uvicorn server for LLM Agent POC.")
    uvicorn.run(app, host="0.0.0.0", port=8000)