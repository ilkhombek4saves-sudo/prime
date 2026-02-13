"""
Knowledge Base API — CRUD for knowledge bases, document upload, and indexing status.

Endpoints:
  GET    /knowledge-bases                     — list all KBs
  POST   /knowledge-bases                     — create KB
  GET    /knowledge-bases/{kb_id}             — get KB with documents
  PATCH  /knowledge-bases/{kb_id}             — update KB
  DELETE /knowledge-bases/{kb_id}             — delete KB + all documents

  POST   /knowledge-bases/{kb_id}/documents   — upload document (multipart)
  GET    /knowledge-bases/{kb_id}/documents   — list documents
  DELETE /knowledge-bases/{kb_id}/documents/{doc_id} — delete document + chunks

  POST   /knowledge-bases/{kb_id}/search      — test retrieval (debug)
"""
from __future__ import annotations

import base64
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.persistence.database import SessionLocal
from app.persistence.models import Agent, Document, DocumentChunk, DocumentStatus, KnowledgeBase

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


# ── Dependency ────────────────────────────────────────────────────────────────

def get_db():
    with SessionLocal() as db:
        yield db


DbDep = Annotated[Session, Depends(get_db)]
UserDep = Annotated[dict, Depends(get_current_user)]


# ── Schemas ───────────────────────────────────────────────────────────────────

class KBCreate(BaseModel):
    name: str
    description: str = ""
    agent_id: uuid.UUID | None = None


class KBUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    active: bool | None = None
    agent_id: uuid.UUID | None = None


class KBOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    agent_id: uuid.UUID | None
    active: bool
    document_count: int

    class Config:
        from_attributes = True


class DocumentOut(BaseModel):
    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    status: str
    chunk_count: int
    error: str | None

    class Config:
        from_attributes = True


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[KBOut])
def list_knowledge_bases(db: DbDep, _: UserDep):
    kbs = db.query(KnowledgeBase).filter(KnowledgeBase.active.is_(True)).all()
    result = []
    for kb in kbs:
        doc_count = db.query(Document).filter(Document.knowledge_base_id == kb.id).count()
        result.append(KBOut(
            id=kb.id,
            name=kb.name,
            description=kb.description,
            agent_id=kb.agent_id,
            active=kb.active,
            document_count=doc_count,
        ))
    return result


@router.post("", response_model=KBOut, status_code=status.HTTP_201_CREATED)
def create_knowledge_base(body: KBCreate, db: DbDep, user: UserDep):
    # Validate agent_id if provided
    if body.agent_id and not db.get(Agent, body.agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")

    kb = KnowledgeBase(
        id=uuid.uuid4(),
        name=body.name,
        description=body.description,
        agent_id=body.agent_id,
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return KBOut(id=kb.id, name=kb.name, description=kb.description,
                 agent_id=kb.agent_id, active=kb.active, document_count=0)


@router.get("/{kb_id}", response_model=KBOut)
def get_knowledge_base(kb_id: uuid.UUID, db: DbDep, _: UserDep):
    kb = _get_kb_or_404(db, kb_id)
    doc_count = db.query(Document).filter(Document.knowledge_base_id == kb.id).count()
    return KBOut(id=kb.id, name=kb.name, description=kb.description,
                 agent_id=kb.agent_id, active=kb.active, document_count=doc_count)


@router.patch("/{kb_id}", response_model=KBOut)
def update_knowledge_base(kb_id: uuid.UUID, body: KBUpdate, db: DbDep, _: UserDep):
    kb = _get_kb_or_404(db, kb_id)
    if body.name is not None:
        kb.name = body.name
    if body.description is not None:
        kb.description = body.description
    if body.active is not None:
        kb.active = body.active
    if body.agent_id is not None:
        kb.agent_id = body.agent_id
    db.commit()
    doc_count = db.query(Document).filter(Document.knowledge_base_id == kb.id).count()
    return KBOut(id=kb.id, name=kb.name, description=kb.description,
                 agent_id=kb.agent_id, active=kb.active, document_count=doc_count)


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge_base(kb_id: uuid.UUID, db: DbDep, _: UserDep):
    kb = _get_kb_or_404(db, kb_id)
    # Cascade: delete chunks → documents → kb
    doc_ids = [d.id for d in db.query(Document).filter(Document.knowledge_base_id == kb_id).all()]
    for doc_id in doc_ids:
        db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).delete()
    db.query(Document).filter(Document.knowledge_base_id == kb_id).delete()
    db.delete(kb)
    db.commit()


# ── Documents ─────────────────────────────────────────────────────────────────

@router.post("/{kb_id}/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    kb_id: uuid.UUID,
    db: DbDep,
    _: UserDep,
    file: UploadFile = File(...),
):
    _get_kb_or_404(db, kb_id)

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"File too large (max {MAX_FILE_SIZE // 1024 // 1024}MB)")

    doc = Document(
        id=uuid.uuid4(),
        knowledge_base_id=kb_id,
        filename=file.filename or "upload",
        content_type=file.content_type or "text/plain",
        size_bytes=len(contents),
        status=DocumentStatus.pending,
        # Store raw bytes as base64 in meta so the worker can access them
        # For large files this should be replaced with object storage (S3)
    )
    # Attach raw bytes to meta for the indexing worker
    doc.meta = {"raw_b64": base64.b64encode(contents).decode("ascii")}  # type: ignore[attr-defined]
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return DocumentOut(
        id=doc.id, filename=doc.filename, content_type=doc.content_type,
        size_bytes=doc.size_bytes, status=doc.status.value,
        chunk_count=doc.chunk_count, error=doc.error,
    )


@router.get("/{kb_id}/documents", response_model=list[DocumentOut])
def list_documents(kb_id: uuid.UUID, db: DbDep, _: UserDep):
    _get_kb_or_404(db, kb_id)
    docs = db.query(Document).filter(Document.knowledge_base_id == kb_id).all()
    return [
        DocumentOut(id=d.id, filename=d.filename, content_type=d.content_type,
                    size_bytes=d.size_bytes, status=d.status.value,
                    chunk_count=d.chunk_count, error=d.error)
        for d in docs
    ]


@router.delete("/{kb_id}/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(kb_id: uuid.UUID, doc_id: uuid.UUID, db: DbDep, _: UserDep):
    _get_kb_or_404(db, kb_id)
    doc = db.query(Document).filter(
        Document.id == doc_id, Document.knowledge_base_id == kb_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).delete()
    db.delete(doc)
    db.commit()


@router.post("/{kb_id}/search")
def search_kb(kb_id: uuid.UUID, body: SearchRequest, db: DbDep, _: UserDep):
    """Debug endpoint — test retrieval against a knowledge base."""
    _get_kb_or_404(db, kb_id)
    from app.services.rag_service import get_rag_service
    results = get_rag_service().search(db, kb_id, body.query, top_k=body.top_k)
    return {"query": body.query, "results": results}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_kb_or_404(db: Session, kb_id: uuid.UUID) -> KnowledgeBase:
    kb = db.get(KnowledgeBase, kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return kb
