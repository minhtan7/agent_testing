from fastapi import FastAPI
from app.routers import router
from app.vectorstore.pinecone_ops import init_pinecone, get_embedder

app = FastAPI()

# Initialize Pinecone and embedder at application startup
@app.on_event("startup")
async def startup_db_client():
    # Initialize Pinecone index
    init_pinecone()
    # Initialize embedder
    get_embedder()
    print("Initialized Pinecone index and embedder at startup")

app.include_router(router)
