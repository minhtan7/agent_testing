from app.models.upload import FileID
from fastapi import UploadFile
import os
import pymupdf
from langchain.text_splitter import RecursiveCharacterTextSplitter
from tqdm import tqdm
from typing import Dict, Any, Optional, List
from app.utils.pdf_parser import create_directories, process_tables, process_text_chunks, process_images, process_page_images

# Import the docling processor (conditionally to handle potential import errors)
try:
    # First try importing docling directly to check if it's properly installed
    import docling
    print(f"Docling package is available")
    
    # Now try importing our docling processor
    from app.utils.docling_processor import process_pdf_with_docling
    DOCLING_AVAILABLE = True
    print("Successfully imported docling_processor module")
except Exception as e:
    DOCLING_AVAILABLE = False
    print(f"Warning: Could not use docling processor. Error: {str(e)}")
    print("Falling back to standard PDF processing.")

# Default to not using docling due to SSL issues
# Can be enabled via environment variable
ENABLE_DOCLING = os.environ.get('ENABLE_DOCLING', 'False').lower() in ('true', '1', 't')
if not ENABLE_DOCLING and DOCLING_AVAILABLE:
    print("NOTE: Docling is available but disabled by default due to SSL certificate issues.")
    print("Set ENABLE_DOCLING=True to enable it.")


def process_pdf(file: UploadFile, use_docling: bool = False) -> Dict[str, Any]:
    """
    Process a PDF file to extract text, tables, and images.
    
    Args:
        file: The PDF file to process
        use_docling: Whether to use the docling library for improved structure extraction
        
    Returns:
        Dictionary containing processed items and metadata
    """
    try:
        # Only use docling if explicitly requested AND enabled in environment AND available
        if use_docling and DOCLING_AVAILABLE and ENABLE_DOCLING:
            try:
                print(f"Using docling for PDF processing")
                result = process_pdf_with_docling(file)
                
                # Check if docling used fallback (PyMuPDF) internally
                if result.get('used_fallback'):
                    print("Note: Docling used internal PyMuPDF fallback for processing")
                return result
            except Exception as e:
                print(f"Docling processing failed: {str(e)}")
                print(f"Falling back to standard PDF processing")
        else:
            if not ENABLE_DOCLING:
                print("Docling is disabled. Set ENABLE_DOCLING=True to enable it.")
            elif not DOCLING_AVAILABLE:
                print("Docling not available, using standard processing")
            elif not use_docling:
                print("Standard processing requested")
    except Exception as e:
        print(f"Error using docling: {str(e)}. Falling back to standard processing.")
        # Fall back to standard processing if docling fails
        return process_pdf_with_pymupdf(file)
    else:
        # Use standard PyMuPDF-based processing
        return process_pdf_with_pymupdf(file)


def process_pdf_with_pymupdf(file: UploadFile) -> Dict[str, Any]:
    """
    Process a PDF file using the standard PyMuPDF-based approach.
    This is the original implementation and is kept for backward compatibility.
    
    Args:
        file: The PDF file to process
        
    Returns:
        Dictionary containing processed items and metadata
    """
    base_dir = f"./uploads/{FileID.id}"
    FileID.id += 1
    os.makedirs(base_dir, exist_ok=True)
    file_location = os.path.join(base_dir, file.filename)

    if not os.path.exists(file_location):
        with open(file_location, "wb") as buffer:
            buffer.write(file.file.read())

    doc = pymupdf.open(file_location)
    num_pages = len(doc)

    create_directories(base_dir)
    # Increased chunk size for better context and structure preservation
    # 1500 characters is around 200-300 words, which should better preserve document structure
    # 300 character overlap ensures continuity between chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500,  # Increased from 700
        chunk_overlap=300,  # Increased from 200
        length_function=len,
        separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
    )
    items = []

    for page_num in tqdm(range(num_pages), desc="Processing PDF pages"):
        page = doc[page_num]
        text = page.get_text()
        process_tables(file_location, page_num, base_dir, items)
        process_text_chunks(text, text_splitter, page_num, base_dir, items, file_location)
        process_images(page, page_num, base_dir, items, file_location)
        process_page_images(page, page_num, base_dir, items)

    return {
        "file_location": file_location,
        "filename": file.filename,
        "items": items,
        "num_pages": num_pages,
        "size_bytes": os.path.getsize(file_location) if os.path.exists(file_location) else None
    }


def process_pdf_text_only(file: UploadFile) -> Dict[str, Any]:
    """
    Process a PDF file to extract only text with minimal processing.
    This is useful for cases where only the text content is needed.
    
    Args:
        file: The PDF file to process
        
    Returns:
        Dictionary containing text items and metadata
    """
    base_dir = f"./uploads/{FileID.id}"
    FileID.id += 1
    os.makedirs(base_dir, exist_ok=True)
    file_location = os.path.join(base_dir, file.filename)

    if not os.path.exists(file_location):
        with open(file_location, "wb") as buffer:
            buffer.write(file.file.read())

    # Use PyMuPDF for efficient text extraction
    doc = pymupdf.open(file_location)
    num_pages = len(doc)
    
    # Create only the text directory
    os.makedirs(os.path.join(base_dir, "text"), exist_ok=True)
    
    # Use a text splitter with larger chunks for better context
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=400,
        length_function=len,
        separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
    )
    
    items = []

    for page_num in tqdm(range(num_pages), desc="Extracting text"):
        page = doc[page_num]
        text = page.get_text()
        
        # Split text into chunks
        chunks = text_splitter.split_text(text)
        
        for i, chunk in enumerate(chunks):
            # Save to file
            text_file_name = f"{base_dir}/text/{os.path.basename(file_location)}_text_{page_num}_{i}.txt"
            with open(text_file_name, 'w') as f:
                f.write(chunk)
            
            # Add to items list
            items.append({
                "page": page_num, 
                "type": "text", 
                "text": chunk, 
                "path": text_file_name
            })

    return {
        "file_location": file_location,
        "filename": file.filename,
        "items": items,
        "num_pages": num_pages,
        "size_bytes": os.path.getsize(file_location) if os.path.exists(file_location) else None
    }
