"""
Enhanced study plan router.
Provides endpoints for generating high-quality, structured study plans.
"""

from fastapi import APIRouter, Depends, HTTPException, Form, UploadFile, File, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
import uuid
import os

from app.db.session import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.user import User
from app.models.enums import ContentTypeEnum, UploadStatusEnum, StorageProvider
from app.services.pdf_processing import process_pdf
from app.services.enhanced_study_plan import generate_enhanced_study_plan
from app.vectorstore.pinecone_ops import upsert_text_chunks
import glob

router = APIRouter()

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/pdf")
async def upload_enhanced_pdf(
    file: UploadFile = File(...),
    familiarity: Optional[str] = Form(None, description="Learner's self-described familiarity with the topic"),
    goal: Optional[str] = Form(None, description="What the learner wants to achieve from studying this material"),
    db: Session = Depends(get_db)
):
    """
    Generate an enhanced study plan using hierarchical document parsing,
    goal-directed filtering, and quality validation.
    
    This endpoint uses a more advanced pipeline that:
    1. Preserves document structure (headings, rubrics)
    2. Filters content based on the learner's goal
    3. Implements self-critique to ensure high quality
    4. Validates output format before saving
    
    Args:
        document_id: ID of the document to generate a study plan for
        familiarity: Learner's familiarity with the subject
        goal: Learner's learning goals
        
    Returns:
        Generated study plan ID
    """
    try:
        # Process the PDF file and extract contents using docling for better structure preservation
        result = process_pdf(file, use_docling=True)
        
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
            )
            
            db.add(document_chunk)
            chunk_index += 1  # Increment chunk index
        
        # Set the Pinecone namespace for this document (using the document UUID)
        new_document.pinecone_namespace = str(new_document.id)
        
        # Commit all changes to the database
        db.commit()

        # Add document text chunks to vector store for semantic search
        try:
            upsert_text_chunks(
                document_id=new_document.id,
                chunks=[item for item in result["items"] if item.get("type") == "text"],
            )
        except Exception as e:
            print(f"Pinecone upsert failed: {e}")
        
        # Generate an enhanced study plan from the extracted content
        try:
            # Extract text chunks to pass to the generator (to avoid double processing)
            text_chunks = [item for item in result["items"] if item.get("type") == "text"]
            image_chunks = [item for item in result["items"] if item.get("type") == "image"]
            print(f'text_chunks count: {len(text_chunks)}')
            print(f'image_chunks count: {len(image_chunks)}')
            if image_chunks:
                print(f'First image path: {image_chunks[0].get("path", "No path")}')
            
            # Generate the enhanced study plan
            try:
                study_plan_id = generate_enhanced_study_plan(
                    document_id=new_document.id,
                    user_id=user.id,
                    familiarity=familiarity,
                    goal=goal,
                    text_chunks=text_chunks,
                    db=db
                )
            except Exception as e:
                print(f"Error generating enhanced study plan: {str(e)}")
                study_plan_id = None
            
            return {
                "document_id": str(new_document.id),
                "study_plan_id": str(study_plan_id),
                "file_name": file.filename,
                "status": "completed",
                "chunks_saved": chunk_index,
                "message": f"File '{file.filename}' processed with enhanced study plan generation."
            }
        except Exception as e:
            # Return success even if study plan generation fails
            print(f"Error generating enhanced study plan: {str(e)}")
            return {
                "document_id": str(new_document.id),
                "file_name": file.filename,
                "status": "completed",
                "chunks_saved": chunk_index,
                "message": f"File processed, but enhanced study plan generation failed: {str(e)}"
            }
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Failed to process file: {str(e)}"},
        )


@router.get("/text-chunks/{document_id}")
def get_text_chunks(document_id: str, db: Session = Depends(get_db)):
    """Get all text chunks from a specific document.
    
    Args:
        document_id: The document ID to retrieve chunks for
        
    Returns:
        List of text chunks with content and metadata
    """
    # Query the database for text chunks related to this document
    try:
        # Find the document
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail=f"Document with ID {document_id} not found")
        
        # Get all text chunks for this document
        document_chunks = db.query(DocumentChunk).filter(
            DocumentChunk.document_id == document_id,
            # DocumentChunk.content_type == ContentTypeEnum.text  # Only get text chunks
        ).order_by(DocumentChunk.page_number, DocumentChunk.chunk_index).all()
        
        if not document_chunks:
            return {
                "document_id": document_id,
                "document_name": document.title,
                "total_chunks": 0,
                "chunks": []
            }
        
        # Format response
        chunks = []
        for chunk in document_chunks:
            content = chunk.text_content or ""
            chunks.append({
                "id": str(chunk.id),
                "chunk_index": chunk.chunk_index,
                "page": chunk.page_number,
                "content": content[:200] + "..." if len(content) > 200 else content,
                "length": len(content) if content else 0,
                "token_count": chunk.token_count,
                "type": chunk.content_type.value,
                "blob_url": chunk.blob_url,
            })
        
        return {
            "document_id": document_id,
            "document_name": document.title,
            "total_chunks": len(chunks),
            "chunks": chunks
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving document chunks: {str(e)}")
