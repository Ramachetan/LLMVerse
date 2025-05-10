from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.sqlite import JSON # Or use Text and handle JSON manually for other DBs
from database import Base
import uuid
from datetime import datetime

class Agent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=True)
    system_prompt = Column(Text, nullable=False)
    llm_model_name = Column(String, default="gemini-2.5-flash-preview-04-17") # Default LLM
    embedding_model_name = Column(String, default="gemini-embedding-exp-03-07") # Default Embedding
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    knowledge_sources = relationship("KnowledgeSource", back_populates="agent", cascade="all, delete-orphan")

class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    source_name = Column(String, nullable=True) # e.g., "Return Policy Doc" or "FAQ section 1"
    content_type = Column(String, default="text") # "text", "file_pdf", "file_txt" etc.
    # For POC, we'll store text chunks and their embeddings in ChromaDB.
    # We might store metadata about the original source here.
    # For simplicity, we won't store vector IDs here yet.
    created_at = Column(DateTime, default=datetime.utcnow)

    agent = relationship("Agent", back_populates="knowledge_sources")