from typing import List
from pydantic import BaseModel


class UploadResponse(BaseModel):
    file_name: str
    status: str
    entities_extracted: int
    conflicts_found: int
    task_ids: List[str]


class IngestResponse(BaseModel):
    file_name: str
    domain: str
    status: str
    entities_created: int
    relations_created: int
    vectors_created: int
    errors: List[str] = []


class DocumentResponse(BaseModel):
    id: str | int
    content: str
    metadata: dict


class UpdateDocumentRequest(BaseModel):
    content: str


class NodeResponse(BaseModel):
    id: str
    labels: List[str]
    properties: dict


class UpdateNodeRequest(BaseModel):
    properties: dict
