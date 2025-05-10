from fastapi import APIRouter
from app.routers.upload import router as upload_router
from app.routers.query import router as query_router
from app.routers.documents import router as documents_router
from app.routers.study_plans import router as study_plans_router

router = APIRouter()

# Include all routers
router.include_router(upload_router, prefix="/upload", tags=["upload"])
router.include_router(query_router, prefix="/query", tags=["query"])
router.include_router(documents_router, prefix="/documents", tags=["documents"])
router.include_router(study_plans_router, prefix="/study-plans", tags=["study-plans"])
