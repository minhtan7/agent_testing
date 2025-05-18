"""
Enhanced document parsing using hierarchical structure.
This module preserves heading structure and relationships in PDFs,
allowing for more context-aware study plan generation.
"""

import tempfile
import os
from typing import List, Dict, Any, Optional

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document as LangchainDocument
from app.services.pdf_processing import process_pdf

def parse_pdf_hierarchically(file_path: str, chunk_size: int = 4000) -> List[LangchainDocument]:
    """
    Parse a PDF file with an advanced structure-preserving approach.
    Uses existing PDF processor but with improved chunking.
    
    Args:
        file_path: Path to the PDF file or document storage_url
        chunk_size: Maximum token size for each chunk
    
    Returns:
        List of LangchainDocument objects with preserved structure
    """
    # We'll use the existing PDF processor but with improved chunking
    # Create a mock file object to use with process_pdf
    from io import BytesIO
    import os
    from types import SimpleNamespace
    
    # If the file_path is a URL, we'll use it directly. 
    # This works with the existing document.storage_url
    if os.path.isfile(file_path):
        with open(file_path, 'rb') as f:
            file_content = f.read()
            filename = os.path.basename(file_path)
    else:
        # If it's not a file, assume it's already processed and create empty docs
        return []
    
    # Create a mock file object similar to what FastAPI provides
    mock_file = SimpleNamespace(
        filename=filename,
        content_type="application/pdf",
        file=BytesIO(file_content)
    )
    
    # Use the existing PDF processor
    try:
        result = process_pdf(mock_file)
        
        # Convert the result to LangchainDocument objects
        docs = []
        
        # First check if result is not None and contains items
        if result and isinstance(result, dict) and "items" in result and result["items"]:
            for item in result["items"]:
                # Verify each item has the expected structure before accessing
                if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                    # Check if page exists, default to 0 if not
                    page = item.get("page", 0)
                    # Create a document with page number as metadata
                    doc = LangchainDocument(
                        page_content=item["text"],
                        metadata={
                            "page": page,
                            "source": file_path
                        }
                    )
                    docs.append(doc)
        else:
            print(f"Warning: PDF processing result doesn't contain valid items structure for {file_path}")
                
        # Apply improved chunking to better preserve structure
        if docs:
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=200,  # More overlap to maintain context
                separators=["\n# ", "\n## ", "\n### ", "\n\n", "\n", ". ", " ", ""]
            )
            
            processed_docs = splitter.split_documents(docs)
            return processed_docs
        return docs
    except Exception as e:
        print(f"Error in parsing PDF hierarchically: {str(e)}")
        return []

def filter_documents_by_goal(docs: List[LangchainDocument], goal_keywords: List[str]) -> List[LangchainDocument]:
    """
    Filter documents to only include those matching the user's goal keywords.
    
    Args:
        docs: List of LangchainDocument objects
        goal_keywords: List of keywords to filter by
    
    Returns:
        Filtered list of LangchainDocument objects
    """
    # If no keywords provided, return all documents
    if not goal_keywords:
        return docs
    
    # Convert keywords to lowercase for case-insensitive matching
    lowercase_keywords = [kw.lower() for kw in goal_keywords]
    
    # Filter documents containing any of the keywords
    filtered_docs = [
        doc for doc in docs 
        if any(kw in doc.page_content.lower() for kw in lowercase_keywords)
    ]
    
    # Return all docs if filtering removed everything (fallback)
    if not filtered_docs and docs:
        return docs
        
    return filtered_docs

def extract_goal_keywords(goal: str) -> List[str]:
    """
    Extract relevant keywords from the user's goal description.
    
    Args:
        goal: User's study goal text
    
    Returns:
        List of extracted keywords
    """
    # Simple approach - split by common separators and filter out stop words
    # In a production system, you might use NLP for better keyword extraction
    stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "with", "about"}
    
    # Split by common separators
    words = goal.lower().replace(',', ' ').replace('.', ' ').replace(';', ' ').split()
    
    # Filter out stop words and short words
    keywords = [word for word in words if word not in stop_words and len(word) > 2]
    
    return keywords
