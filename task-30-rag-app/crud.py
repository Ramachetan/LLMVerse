from sqlalchemy.orm import Session
import models
import schemas
from typing import List, Optional

# --- Agent CRUD ---
def create_agent(db: Session, agent: schemas.AgentCreate) -> models.Agent:
    db_agent = models.Agent(**agent.model_dump()) # For Pydantic v2, use model_dump()
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    return db_agent

def get_agent(db: Session, agent_id: str) -> Optional[models.Agent]:
    return db.query(models.Agent).filter(models.Agent.id == agent_id).first()

def get_agents(db: Session, skip: int = 0, limit: int = 100) -> List[models.Agent]:
    return db.query(models.Agent).offset(skip).limit(limit).all()

def delete_agent(db: Session, agent_id: str) -> Optional[models.Agent]:
    db_agent = get_agent(db, agent_id)
    if db_agent:
        db.delete(db_agent)
        db.commit()
        return db_agent
    return None



# --- KnowledgeSource CRUD ---
def create_knowledge_source(db: Session, agent_id: str, source_name: str, content_type: str = "text") -> models.KnowledgeSource:
    db_knowledge = models.KnowledgeSource(
        agent_id=agent_id,
        source_name=source_name,
        content_type=content_type
    )
    db.add(db_knowledge)
    db.commit()
    db.refresh(db_knowledge)
    return db_knowledge

def get_knowledge_sources_for_agent(db: Session, agent_id: str) -> List[models.KnowledgeSource]:
    return db.query(models.KnowledgeSource).filter(models.KnowledgeSource.agent_id == agent_id).all()