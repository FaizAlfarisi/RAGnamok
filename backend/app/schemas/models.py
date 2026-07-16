from typing import Optional

from pydantic import BaseModel


class UploadResponse(BaseModel):
    doc_id: str
    message: str
    filename: str


class TaskStatus(BaseModel):
    task_id: str
    doc_id: Optional[str] = None
    status: str
    progress: Optional[str] = None
    error: Optional[str] = None


class ChatRequest(BaseModel):
    query: str
    top_k: int = 5


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]
    images: list[str]


class DocumentResponse(BaseModel):
    id: str
    filename: str
    status: str
    enabled: bool
    created_at: Optional[str] = None
    chunk_count: int = 0


class IndexResponse(BaseModel):
    task_id: str
    message: str
    doc_id: str


class ToggleResponse(BaseModel):
    enabled: bool
    doc_id: str


class DeleteResponse(BaseModel):
    message: str
    document_id: str


# --- Chat Session ---

class SessionCreateRequest(BaseModel):
    title: str = "New Chat"


class SessionUpdateRequest(BaseModel):
    title: str


class SessionResponse(BaseModel):
    id: str
    title: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    message_count: int = 0


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    sources: Optional[list] = None
    images: Optional[list] = None
    created_at: Optional[str] = None


class ChatHistoryRequest(BaseModel):
    query: str
    top_k: int = 5


class ChatHistoryResponse(BaseModel):
    message_id: str
    answer: str
    sources: list[str]
    images: list[str]
