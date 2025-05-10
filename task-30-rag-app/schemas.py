# schemas.py

from pydantic import BaseModel, Field, model_validator # For Pydantic V2
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

# --- Agent Schemas ---
class AgentBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = None
    system_prompt: str = Field(..., min_length=10)
    llm_model_name: str = Field(default="gemini-2.5-flash-preview-04-17")
    embedding_model_name: str = Field(default="gemini-embedding-exp-03-07")

class AgentCreate(AgentBase):
    pass

class AgentResponse(AgentBase):
    id: uuid.UUID # FastAPI will handle str to UUID conversion
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True} # Pydantic V2 style

# --- Knowledge Schemas ---
class KnowledgeTextCreate(BaseModel):
    text_content: str = Field(..., min_length=10)
    source_name: Optional[str] = "text_input"

class KnowledgeSourceResponse(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    source_name: Optional[str]
    content_type: str
    created_at: datetime

    model_config = {"from_attributes": True} # Pydantic V2 style

# --- Chat Schemas ---
class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1)
    max_tokens_response: Optional[int] = 1000

class ChatResponse(BaseModel):
    agent_id: uuid.UUID
    query: str
    response: str
    retrieved_source_names: Optional[List[str]] = None