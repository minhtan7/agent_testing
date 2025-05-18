from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import time

from app.db.session import SessionLocal
from app.vectorstore.pinecone_ops import get_index, get_embedder
from app.models.document import Document
from app.services.llm_service import get_answer_from_llm

router = APIRouter()

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Define request and response models
class QueryRequest(BaseModel):
    query: str
    document_id: Optional[str] = None  # Optional: filter by document ID
    top_k: int = 10  # Increased default number of results to return

class QueryResponse(BaseModel):
    # answer: Optional[str]
    sources: List[Dict[str, Any]]

@router.post("/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest, db: Session = Depends(get_db)):
    try:
        # Start overall timing
        start_time_total = time.time()
        
        # Get Pinecone index and embedder - should be nearly instant now with app-level initialization
        index = get_index()
        embedder = get_embedder()
        
        # Create embeddings for the query
        embedding_start = time.time()
        query_embedding = embedder.embed_query(request.query)
        embedding_time = time.time() - embedding_start
        print(f"[TIMING] Query embedding time: {embedding_time:.4f} seconds")
        
        # Prepare filter if document_id is provided
        filter_dict = {}
        namespace = None
        
        if request.document_id:
            # Verify document exists
            document = db.query(Document).filter(Document.id == request.document_id).first()
            if not document:
                raise HTTPException(status_code=404, detail="Document not found")
                
            # Use the stored pinecone_namespace if available, otherwise fall back to document ID
            if document.pinecone_namespace:
                namespace = document.pinecone_namespace
            else:
                namespace = str(document.id)
        
        # Query Pinecone - don't filter by score in the initial query
        # For complex or structural queries, use a slightly higher top_k value
        query_words = request.query.lower().split()
        query_length = len(query_words)
        
        # Determine if this is a complex query (asking about document structure or organization)
        is_complex_query = query_length > 5 or any(word in request.query.lower() 
                                                for word in ['structure', 'organization', 'outline', 
                                                            'overview', 'framework', 'model', 'approach'])
        
        # Keep retrieval count reasonable - we want to be selective!
        # Complex queries need more context, but still keep it focused
        actual_top_k = 7 if is_complex_query else max(request.top_k, 5)

        # Query Pinecone - don't filter by score in the initial query
        vector_search_start = time.time()
        query_results = index.query(
            namespace=namespace,
            vector=query_embedding,
            top_k=actual_top_k,  # Retrieve more results than requested
            include_metadata=True
        )
        vector_search_time = time.time() - vector_search_start
        print(f"[TIMING] Vector search time: {vector_search_time:.4f} seconds")
        
        # Process the query results
        
        # Extract all context from query results without filtering by score
        contexts = []
        for match in query_results.matches:
            # Include all matches regardless of score
            context_text = match.metadata.get("snippet", "")
            if not context_text:  # Skip empty contexts
                continue
                
            # Extract headings information if available
            headings = match.metadata.get("headings", [])
            headings_text = "" if not headings else f"[HEADINGS: {', '.join(headings)}]\n"
            
            # Get page number
            page = match.metadata.get("page", 0)
            

            
            # Add to contexts with enhanced metadata
            contexts.append({
                "text": f"{headings_text}{context_text}",  # Prepend headings info
                "page": page,
                "score": match.score,
                "headings": headings
            })
        
        # Sort contexts by page number for better document flow
        contexts = sorted(contexts, key=lambda x: x.get('page', 0))
        
        # If no relevant context found
        if not contexts:
            return QueryResponse(
                # answer="I couldn't find any relevant information to answer your query.",
                sources=[]
            )
        
        # Generate answer using the LLM service
        llm_start = time.time()
        # answer = get_answer_from_llm(
        #     query=request.query,
        #     contexts=contexts,
        #     document_id=request.document_id 
        # )
        # llm_time = time.time() - llm_start
        # print(f"[TIMING] LLM answer generation time: {llm_time:.4f} seconds")
        
        # # Calculate total time
        # total_time = time.time() - start_time_total
        # print(f"[TIMING] Total query processing time: {total_time:.4f} seconds")
        # print(f"[TIMING] Summary: Embedding={embedding_time:.4f}s, Vector Search={vector_search_time:.4f}s, LLM={llm_time:.4f}s")
        
        return QueryResponse(
            sources=contexts,
            # answer=answer
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")
