from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import uuid

from app.db.session import SessionLocal
from app.models.document import Document

router = APIRouter()

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Response model for document listing
class DocumentListItem(BaseModel):
    id: str
    title: Optional[str] = None
    original_filename: str
    pages: Optional[int] = None
    pinecone_namespace: Optional[str] = None
    created_at: str

@router.get("/list", response_model=List[DocumentListItem])
async def list_documents(db: Session = Depends(get_db)):
    """
    List all documents with their IDs and basic metadata.
    This is useful for finding document IDs to use in the query API.
    """
    documents = db.query(Document).order_by(Document.created_at.desc()).all()
    
    return [
        {
            "id": str(doc.id),
            "title": doc.title,
            "original_filename": doc.original_filename,
            "pages": doc.pages,
            "pinecone_namespace": doc.pinecone_namespace,
            "created_at": doc.created_at.isoformat() if doc.created_at else None
        } 
        for doc in documents
    ]

@router.get("/{document_id}", response_model=DocumentListItem)
async def get_document(document_id: str, db: Session = Depends(get_db)):
    """
    Get details for a specific document by ID.
    """
    try:
        uuid_obj = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")
        
    document = db.query(Document).filter(Document.id == uuid_obj).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
        
    return {
        "id": str(document.id),
        "title": document.title,
        "original_filename": document.original_filename,
        "pages": document.pages,
        "pinecone_namespace": document.pinecone_namespace,
        "created_at": document.created_at.isoformat() if document.created_at else None
    }
