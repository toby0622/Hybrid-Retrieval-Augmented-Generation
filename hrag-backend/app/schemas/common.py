from typing import List, Optional
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    neo4j: str
    qdrant: str
    model_name: str


class EntityConflict(BaseModel):
    id: str
    type: str
    entity_name: str
    source: str
    confidence: float
    existing_entity: Optional[dict] = None
    new_entity: dict
    description: Optional[str] = None


class GardenerTask(BaseModel):
    tasks: List[EntityConflict]


class GardenerAction(BaseModel):
    entity_id: str
    action: str
    modified_entity: Optional[dict] = None
