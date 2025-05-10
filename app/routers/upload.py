from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import uuid
from typing import List, Dict, Any, Optional
import os

from app.services.pdf_processing import process_pdf
from app.services.study_plan_generator import generate_study_plan
from app.db.session import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.user import User
from app.models.enums import ContentTypeEnum, UploadStatusEnum, StorageProvider
from app.vectorstore.pinecone_ops import upsert_text_chunks

router = APIRouter()


# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    familiarity: Optional[str] = Form(None, description="Learner's self-described familiarity with the topic"),
    goal: Optional[str] = Form(None, description="What the learner wants to achieve from studying this material"),
    db: Session = Depends(get_db)
):
    # Process the PDF file and extract contents
    result = process_pdf(file)
    
    # Find an existing user or create a dummy test user
    user = db.query(User).first()
    if not user:
        # Create a dummy user for testing purposes
        test_user = User(
            email="test@example.com",
            password_hash="$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # hashed 'password'
            is_active=True,
            name="Test User"
        )
        db.add(test_user)
        db.flush()
        user = test_user
    
    # Create a new document record
    new_document = Document(
        user_id=user.id,  # Use actual user ID
        storage_provider=StorageProvider.cloudinary,  # Should match your storage configuration
        storage_url=result["file_location"],
        storage_public_id=f"pdf/{os.path.basename(result['file_location'])}",
        original_filename=file.filename,
        mime_type=file.content_type,
        size_bytes=result.get("size_bytes"),
        pages=result.get("num_pages"),
        title=file.filename,
        status=UploadStatusEnum.completed,
    )
    
    db.add(new_document)
    db.flush()  # Flush to get the ID without committing
    
    # Save extracted content items to the database as DocumentChunks
    chunk_index = 0  # Initialize chunk index counter
    for item in result["items"]:
        content_type = ContentTypeEnum.text
        text_content = None
        blob_url = None
        
        # Set content type and appropriate content field
        if item["type"] == "image" or item["type"] == "page_image":
            content_type = ContentTypeEnum.image
            blob_url = item["path"]
        elif item["type"] == "table":
            content_type = ContentTypeEnum.table
            text_content = item.get("text", "")
        else:  # Text content
            text_content = item.get("text", "")
        
        # Get token count (approximated by word count * 1.3 for English)
        token_count = None
        if text_content:
            token_count = int(len(text_content.split()) * 1.3)  # Rough approximation
        
        # Create DocumentChunk
        document_chunk = DocumentChunk(
            document_id=new_document.id,
            chunk_index=chunk_index,
            page_number=item["page"] + 1,  # Converting 0-based to 1-based page numbering
            content_type=content_type,
            text_content=text_content,
            blob_url=blob_url,
            token_count=token_count,
            # We don't have precise coordinates from the extraction yet
            # These could be added in future enhancements
        )
        
        db.add(document_chunk)
        chunk_index += 1  # Increment chunk index
    
    # Set the Pinecone namespace for this document (using the document UUID)
    new_document.pinecone_namespace = str(new_document.id)
    
    # Commit all changes to the database
    db.commit()

    try:
        upsert_text_chunks(
            document_id=new_document.id,
            chunks=[item for item in result["items"] if item.get("type") == "text"],
        )
    except Exception as e:
        print(f"Pinecone upsert failed: {e}")
    
    # Generate a study plan from the extracted content
    try:
        # Get text chunks for study plan generation
        text_chunks = [item for item in result["items"] if item.get("type") == "text"]
        
        # Generate the study plan with user preferences
        study_plan_id = generate_study_plan(
            document_id=new_document.id,
            user_id=user.id,
            text_chunks=text_chunks,
            db=db,
            familiarity=familiarity,
            goal=goal
        )
        
        return {
            "document_id": str(new_document.id),
            "study_plan_id": str(study_plan_id),
            "file_name": file.filename,
            "status": "completed",
            "chunks_saved": chunk_index,
            "message": f"File '{file.filename}' processed and saved with {chunk_index} content chunks. Study plan generated."
        }
    except Exception as e:
        # Return success even if study plan generation fails
        print(f"Error generating study plan: {str(e)}")
        return {
            "document_id": str(new_document.id),
            "file_name": file.filename,
            "status": "completed",
            "chunks_saved": chunk_index,
            "message": f"File '{file.filename}' processed and saved with {chunk_index} content chunks. Study plan generation failed: {str(e)}"
        }
    