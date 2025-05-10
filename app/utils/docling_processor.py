"""
Enhanced PDF processing module using the docling library.
This provides improved structure preservation and metadata extraction from PDFs.
"""

import os
import base64
import re
from typing import List, Dict, Any, Optional
from fastapi import UploadFile
import tempfile
import json
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Import docling and related packages
import docling
import docling_core
import docling_parse
from app.models.upload import FileID

def create_directories(base_dir: str) -> None:
    """
    Create necessary directories for storing processed PDF content.
    
    Args:
        base_dir: Base directory for storing processed content
    """
    directories = ["images", "text", "tables", "page_images", "metadata"]
    for dir in directories:
        os.makedirs(os.path.join(base_dir, dir), exist_ok=True)

def process_pdf_with_docling(file: UploadFile) -> Dict[str, Any]:
    """
    Process a PDF file using docling tools to extract text, tables, and images
    with improved structure preservation.
    
    Args:
        file: FastAPI UploadFile object containing the PDF
        
    Returns:
        Dictionary containing processed items and metadata
    """
    # Create a unique directory for this upload
    base_dir = f"./uploads/{FileID.id}"
    FileID.id += 1
    os.makedirs(base_dir, exist_ok=True)
    file_location = os.path.join(base_dir, file.filename)

    # Save the uploaded file
    with open(file_location, "wb") as buffer:
        buffer.write(file.file.read())
    
    # Create necessary directories
    create_directories(base_dir)
    
    # Initialize result items list
    items = []
    
    # Define metadata_path here so it's available in all scopes including fallback
    metadata_path = os.path.join(base_dir, "metadata", f"{os.path.basename(file_location)}_metadata.json")
    
    try:
        # Use docling command-line to process the PDF
        print(f"Processing PDF with docling: {file_location}")
        
        # Create a directory for docling output
        docling_output_dir = os.path.join(base_dir, "docling_output")
        os.makedirs(docling_output_dir, exist_ok=True)
        
        # Check if we should skip docling entirely based on previous failures or environment vars
        USE_DOCLING = os.environ.get('USE_DOCLING', 'True').lower() in ('true', '1', 't')
        
        if not USE_DOCLING:
            print("Skipping docling processing due to environment settings")
            raise RuntimeError("Docling processing skipped by configuration")
        
        # Use subprocess to run docling CLI
        import subprocess
        docling_json_path = os.path.join(docling_output_dir, "output_data.json")
        docling_script_path = os.path.join(os.path.dirname(__file__), 'docling_script.py')
        
        # Try to run docling CLI with JSON output format
        try:
            # Set environment variables to handle SSL certificate issues
            env = os.environ.copy()
            # Run our custom script that disables SSL verification
            subprocess.run([
                "python", 
                docling_script_path,
                file_location, 
                "--to", "json", 
                "--output", docling_json_path,
                "--device", "cpu"  # Force CPU to avoid CUDA/MPS issues
            ], check=True, env=env, timeout=60)  # Add timeout to prevent hanging
            
            # Make sure the output file exists
            if not os.path.isfile(docling_json_path):
                print(f"Docling output file not found at {docling_json_path}")
                raise FileNotFoundError(f"Docling did not create the expected output file")
        except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
            print(f"Docling CLI error: {str(e)}")
            # If docling fails, we'll fall back to traditional processing
            raise RuntimeError(f"Docling CLI processing failed: {str(e)}")
        
        # Open and parse the JSON output from docling
        with open(docling_json_path, 'r') as f:
            docling_data = json.load(f)
        
        # Import pymupdf to get basic metadata as a fallback
        import pymupdf
        pdf_doc = pymupdf.open(file_location)
        num_pages = pdf_doc.page_count if hasattr(pdf_doc, 'page_count') else len(pdf_doc)
        
        # Prepare metadata from docling output and pymupdf
        doc_metadata = {
            "title": docling_data.get("title", ""),
            "author": docling_data.get("author", ""),
            "creation_date": "",
            "num_pages": num_pages,
            "format": "PDF",
            "producer": "",
            # Add docling-specific metadata
            "processed_with_docling": True,
            "has_structure": True,
            "processing_time": docling_data.get("processing_time", 0)
        }
        
        # Save metadata
        with open(metadata_path, 'w') as f:
            json.dump(doc_metadata, f, indent=2)
        
        # Initialize text splitter with improved structure awareness
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1500,
            chunk_overlap=300,
            length_function=len,
            # More sophisticated separator list that preserves document structure
            separators=[
                "\n# ", "\n## ", "\n### ",  # Markdown-style headers
                "\nChapter ", "\nSection ",  # Common document divisions
                "\n\n", "\n",  # Paragraph breaks
                ".", "!", "?",  # Sentence boundaries
                ",", ";", ":",  # Clause boundaries
                " ", ""  # Word boundaries as last resort
            ]
        )
        
        # Initialize text splitter
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1500,
            chunk_overlap=300,
            length_function=len,
            separators=[
                "\n# ", "\n## ", "\n### ",  # Markdown-style headers
                "\nChapter ", "\nSection ",  # Common document divisions
                "\n\n", "\n",  # Paragraph breaks
                ".", "!", "?",  # Sentence boundaries
                ",", ";", ":",  # Clause boundaries
                " ", ""  # Word boundaries as last resort
            ]
        )
        
        # Process the content from docling output
        if "elements" in docling_data:
            for element_idx, element in enumerate(docling_data["elements"]):
                # Check if this is a text element
                if element.get("type") == "text":
                    text = element.get("text", "")
                    page_num = element.get("page", 0) 
                    
                    # Extract heading information if available
                    is_heading = element.get("is_heading", False)
                    heading_level = element.get("heading_level", 0)
                    heading_text = text if is_heading else ""
                    
                    # Create element metadata
                    element_metadata = {
                        "is_heading": is_heading,
                        "heading_level": heading_level,
                        "page": page_num,
                        "index": element_idx
                    }
                    
                    # Split content into chunks
                    if text:
                        chunks = text_splitter.split_text(text)
                        
                        # Process each chunk
                        for chunk_idx, chunk in enumerate(chunks):
                            text_file_name = f"{base_dir}/text/element_{element_idx}_chunk_{chunk_idx}.txt"
                            with open(text_file_name, 'w') as f:
                                f.write(chunk)
                            
                            # Add snippet for preview
                            snippet = chunk[:200] + ('...' if len(chunk) > 200 else '')
                            
                            # Add the chunk to items
                            items.append({
                                "page": page_num, 
                                "type": "text", 
                                "text": chunk, 
                                "path": text_file_name,
                                "metadata": {
                                    **element_metadata,
                                    "chunk_index": chunk_idx,
                                    "total_chunks": len(chunks),
                                    "estimated_tokens": len(chunk.split()) * 1.3
                                },
                                "snippet": snippet,
                                "heading": heading_text if is_heading else ""
                            })
                # Handle tables if present
                elif element.get("type") == "table":
                    # Extract table data
                    page_num = element.get("page", 0)
                    table_data = element.get("data", [])
                    
                    if table_data:
                        # Convert to CSV format
                        import pandas as pd
                        table_df = pd.DataFrame(table_data)
                        table_file_name = f"{base_dir}/tables/table_{element_idx}.csv"
                        table_df.to_csv(table_file_name, index=False)
                        
                        items.append({
                            "page": page_num,
                            "type": "table",
                            "path": table_file_name,
                            "metadata": {
                                "rows": len(table_data),
                                "columns": len(table_data[0]) if table_data and len(table_data) > 0 else 0
                            }
                        })
            
        # Try to process tables with docling approach
        try:
            from tabula import read_pdf
            # This is experimental and based on docling concepts
            tables = read_pdf(file_location, pages='all', multiple_tables=True, guess=True)
            
            if tables and len(tables) > 0:
                for i, table in enumerate(tables):
                    try:
                        # Save table to a file
                        table_file_path = os.path.join(base_dir, "tables", f"{os.path.basename(file_location)}_table_{i}.csv")
                        table.to_csv(table_file_path, index=False)
                        
                        # Extract the page number from the table if available
                        page_number = i // 2  # Rough estimate of page number
                        
                        # Create more detailed table metadata
                        table_metadata = {
                            "rows": len(table),
                            "columns": len(table.columns),
                            "estimated_page": page_number,
                            "column_names": table.columns.tolist()
                        }
                        
                        items.append({
                            "page": page_number,
                            "type": "table",
                            "path": table_file_path,
                            "metadata": table_metadata
                        })
                    except Exception as e:
                        print(f"Error processing table {i}: {str(e)}")
        except Exception as e:
            print(f"Error with table extraction: {str(e)}")
            
        # Return the processed results
        return {
            "file_location": file_location,
            "filename": file.filename,
            "items": items,
            "num_pages": doc_metadata["num_pages"],
            "size_bytes": os.path.getsize(file_location) if os.path.exists(file_location) else None,
            "metadata": doc_metadata
        }
    
    except Exception as e:
        print(f"Error in docling processing: {str(e)}")
        
        # If docling processing fails, fall back to PyMuPDF-based processing
        try:
            print("Falling back to PyMuPDF-based processing...")
            import pymupdf
            doc = pymupdf.open(file_location)
            
            # Get the number of pages
            num_pages = doc.page_count if hasattr(doc, 'page_count') else len(doc)
            
            # Basic metadata extraction
            doc_metadata = {
                "title": doc.metadata.get("title", "") if hasattr(doc, "metadata") else "",
                "author": doc.metadata.get("author", "") if hasattr(doc, "metadata") else "",
                "creation_date": str(doc.metadata.get("creationDate", "")) if hasattr(doc, "metadata") else "",
                "num_pages": num_pages,
                "format": "PDF",
                "producer": doc.metadata.get("producer", "") if hasattr(doc, "metadata") else "",
                "fallback_processing": True  # Indicate this used fallback processing
            }
            
            # Create text splitter for processing
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1500,
                chunk_overlap=300,
                length_function=len,
                separators=[
                    "\n# ", "\n## ", "\n### ",  # Markdown-style headers
                    "\nChapter ", "\nSection ",  # Common document divisions
                    "\n\n", "\n",  # Paragraph breaks
                    ".", "!", "?",  # Sentence boundaries
                    ",", ";", ":",  # Clause boundaries
                    " ", ""  # Word boundaries as last resort
                ]
            )
            
            # Save metadata
            with open(metadata_path, 'w') as f:
                json.dump(doc_metadata, f, indent=2)
                
            # Process each page using PyMuPDF
            for page_idx in range(num_pages):
                page = doc[page_idx]
                
                # Extract text with potential heading detection
                text = page.get_text() if callable(page.get_text) else ""
                
                # Try to detect headings and structure in the text
                try:
                    process_enhanced_text(text, page_idx, base_dir, items, file_location, text_splitter)
                except Exception as text_err:
                    print(f"Error processing text on page {page_idx}: {str(text_err)}")
                    # Create a simple chunk without structure detection
                    if text:
                        text_file_path = os.path.join(base_dir, "text", f"page_{page_idx}.txt")
                        with open(text_file_path, 'w') as f:
                            f.write(text)
                        items.append({
                            "page": page_idx,
                            "type": "text",
                            "text": text,
                            "path": text_file_path,
                            "snippet": text[:200] + ('...' if len(text) > 200 else '')
                        })
                
            # Return processed results
            return {
                "file_location": file_location,
                "filename": file.filename,
                "items": items,
                "num_pages": doc_metadata["num_pages"],
                "size_bytes": os.path.getsize(file_location) if os.path.exists(file_location) else None,
                "metadata": doc_metadata,
                "used_fallback": True
            }
        except Exception as fallback_error:
            print(f"Fallback processing also failed: {str(fallback_error)}")
            return {
                "file_location": file_location if 'file_location' in locals() else None,
                "filename": file.filename,
                "items": items if 'items' in locals() else [],
                "error": f"Docling error: {str(e)}. Fallback error: {str(fallback_error)}",
                "size_bytes": os.path.getsize(file_location) if 'file_location' in locals() and os.path.exists(file_location) else None
            }

def process_enhanced_text(
    text: str,
    page_idx: int, 
    base_dir: str, 
    items: List[Dict[str, Any]], 
    file_location: str,
    text_splitter: RecursiveCharacterTextSplitter
) -> None:
    """
    Process and chunk text from a page while preserving structure.
    
    Args:
        text: The text content to process
        page_idx: Page index
        base_dir: Base directory for output
        items: List to append processed items to
        file_location: PDF file location
        text_splitter: Text splitter for chunking
    """
    try:
        # Extract headings using improved heuristics
        headings = []
        lines = text.split('\n')
        
        # Better heading detection with more comprehensive rules
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # Potential heading indicators
            is_short = len(line) < 80
            has_caps = line.isupper() or line[0].isupper()
            ends_without_punct = not line[-1] in '.,:;?!'
            has_chapter_section = any(marker in line.lower() for marker in ['chapter', 'section', 'part '])
            has_numbering = bool(re.match(r'^\d+[.\s]|^[IVX]+[.\s]|^[A-Z][.\s]', line))
            
            # Combined rules for heading detection
            if is_short and has_caps and (ends_without_punct or has_chapter_section or has_numbering):
                headings.append(line)
                        
        # Split text into chunks with structure preservation
        chunks = text_splitter.split_text(text)
        
        for i, chunk in enumerate(chunks):
            # Find which headings are in this chunk
            chunk_headings = []
            for heading in headings:
                if heading in chunk:
                    chunk_headings.append(heading)
            
            # Create richer metadata about the chunk context
            metadata = {
                "page": page_idx,
                "chunk_index": i,
                "headings": chunk_headings,
                "total_chunks": len(chunks),
                "estimated_tokens": len(chunk.split()) * 1.3  # Rough token count estimation
            }
            
            # Save to file
            text_file_name = f"{base_dir}/text/{os.path.basename(file_location)}_text_{page_idx}_{i}.txt"
            with open(text_file_name, 'w') as f:
                f.write(chunk)
            
            # Add snippet for preview
            snippet = chunk[:200] + ('...' if len(chunk) > 200 else '')
            
            items.append({
                "page": page_idx, 
                "type": "text", 
                "text": chunk, 
                "path": text_file_name,
                "metadata": metadata,
                "snippet": snippet,
                "headings": chunk_headings
            })
    except Exception as e:
        print(f"Error processing enhanced text on page {page_idx}: {str(e)}")
