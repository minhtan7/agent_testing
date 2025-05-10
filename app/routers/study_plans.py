from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import uuid

from app.db.session import SessionLocal
from app.models.study_plan import StudyPlan
from app.models.document import Document
from app.models.enums import StudyPlanStatusEnum

router = APIRouter()

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Response models
class StudyPlanListItem(BaseModel):
    id: str
    document_id: str
    title: str
    status: str
    created_at: str
    updated_at: str

class StudyPlanDetail(StudyPlanListItem):
    plan: Dict[str, Any]  # Full JSON plan data
    version: int

@router.get("/", response_model=List[StudyPlanListItem])
async def list_study_plans(db: Session = Depends(get_db)):
    """
    List all study plans with their basic metadata.
    """
    study_plans = db.query(StudyPlan).order_by(StudyPlan.created_at.desc()).all()
    
    return [
        {
            "id": str(plan.id),
            "document_id": str(plan.document_id),
            "title": plan.title,
            "status": plan.status.value,
            "created_at": plan.created_at.isoformat() if plan.created_at else None,
            "updated_at": plan.updated_at.isoformat() if plan.updated_at else None
        } 
        for plan in study_plans
    ]

@router.get("/document/{document_id}", response_model=List[StudyPlanListItem])
async def get_study_plans_for_document(document_id: str, db: Session = Depends(get_db)):
    """
    Get all study plans associated with a specific document.
    """
    try:
        uuid_obj = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")
    
    # Verify document exists
    document = db.query(Document).filter(Document.id == uuid_obj).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
        
    # Get all study plans for this document
    study_plans = db.query(StudyPlan).filter(StudyPlan.document_id == uuid_obj).order_by(StudyPlan.created_at.desc()).all()
    
    return [
        {
            "id": str(plan.id),
            "document_id": str(plan.document_id),
            "title": plan.title,
            "status": plan.status.value,
            "created_at": plan.created_at.isoformat() if plan.created_at else None,
            "updated_at": plan.updated_at.isoformat() if plan.updated_at else None
        } 
        for plan in study_plans
    ]

@router.get("/{study_plan_id}", response_model=StudyPlanDetail)
async def get_study_plan(study_plan_id: str, db: Session = Depends(get_db)):
    """
    Get detailed information for a specific study plan by ID, including the full plan data.
    """
    try:
        uuid_obj = uuid.UUID(study_plan_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid study plan ID format")
        
    study_plan = db.query(StudyPlan).filter(StudyPlan.id == uuid_obj).first()
    
    if not study_plan:
        raise HTTPException(status_code=404, detail="Study plan not found")
        
    return {
        "id": str(study_plan.id),
        "document_id": str(study_plan.document_id),
        "title": study_plan.title,
        "status": study_plan.status.value,
        "plan": study_plan.plan,
        "version": study_plan.version,
        "created_at": study_plan.created_at.isoformat() if study_plan.created_at else None,
        "updated_at": study_plan.updated_at.isoformat() if study_plan.updated_at else None
    }

@router.get("/latest/{document_id}", response_model=StudyPlanDetail)
async def get_latest_study_plan_for_document(document_id: str, db: Session = Depends(get_db)):
    """
    Get the latest study plan for a specific document.
    """
    try:
        uuid_obj = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")
    
    # Verify document exists
    document = db.query(Document).filter(Document.id == uuid_obj).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get the latest study plan for this document
    study_plan = db.query(StudyPlan).filter(StudyPlan.document_id == uuid_obj).order_by(StudyPlan.created_at.desc()).first()
    
    if not study_plan:
        raise HTTPException(status_code=404, detail="No study plan found for this document")
    
    return {
        "id": str(study_plan.id),
        "document_id": str(study_plan.document_id),
        "title": study_plan.title,
        "status": study_plan.status.value,
        "plan": study_plan.plan,
        "version": study_plan.version,
        "created_at": study_plan.created_at.isoformat() if study_plan.created_at else None,
        "updated_at": study_plan.updated_at.isoformat() if study_plan.updated_at else None
    }
