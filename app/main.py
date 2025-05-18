from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import router
from app.vectorstore.pinecone_ops import init_pinecone, get_embedder

app = FastAPI()

# Add CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "*"],  # Allow requests from the React frontend
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Initialize Pinecone and embedder at application startup
@app.on_event("startup")
async def startup_db_client():
    # Initialize Pinecone index
    init_pinecone()
    # Initialize embedder
    get_embedder()
    print("Initialized Pinecone index and embedder at startup")

app.include_router(router)
