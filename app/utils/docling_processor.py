"""
Enhanced PDF processing module using the docling library.
This provides improved structure preservation and metadata extraction from PDFs.
"""

import os
import base64
import re
import datetime
from typing import List, Dict, Any, Optional
from fastapi import UploadFile
import tempfile
import json
from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.models.upload import FileID

# Import docling and related packages
import docling
import docling_core
import docling_parse

# Import our custom helpers for PDF processing
try:
    from app.utils.direct_text_processor import process_text_elements_directly
except ImportError:
    # Define fallback if import fails
    def process_text_elements_directly(document, base_dir, file_location, items):
        print("Direct text processor not available")
        return 0
        
# Import image extraction helper
try:
    from app.utils.docling_image_extractor import extract_images_with_docling
except ImportError:
    # Define fallback if image extractor is not available
    def extract_images_with_docling(file_location, base_dir, items):
        print("Image extraction module not available")
        return 0

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
        # Use docling PYTHON API directly to process the PDF
        print(f"Processing PDF with docling Python API: {file_location}")
        
        # Create a directory for docling output
        docling_output_dir = os.path.join(base_dir, "docling_output")
        os.makedirs(docling_output_dir, exist_ok=True)
        
        # Create a debug directory
        debug_dir = os.path.join(base_dir, "debug")
        os.makedirs(debug_dir, exist_ok=True)
        
        # Always use docling for testing
        print("NOTE: Docling is enabled by default for testing")
        
        # Use docling's Python API for direct processing
        from pathlib import Path
        from docling.document_converter import DocumentConverter
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        
        # Convert the file path to a Path object
        pdf_path = Path(file_location)
        output_path = Path(docling_output_dir)
        
        try:
            # Try a simpler approach with the converter
            converter = DocumentConverter()
            
            # Set up basic options - OCR off for speed
            pipeline = PdfPipelineOptions(do_ocr=False)
            
            # Create conversion result object
            doc = converter.convert(pdf_path)
            
            # Save the output to a JSON file
            json_path = output_path / f"{pdf_path.stem}.json"
            docling_json_path = os.path.join(debug_dir, f"docling_raw.json")
            
            # Inspect the return type and structure to understand what we're getting
            print(f"Docling returned object of type: {type(doc)}")
            print(f"Available attributes/methods: {dir(doc)}")
            
            # Try to save the raw docling output as JSON if possible
            try:
                if hasattr(doc, 'model_dump_json'):
                    # For Pydantic models
                    with open(docling_json_path, 'w', encoding='utf-8') as f:
                        f.write(doc.model_dump_json(indent=2))
                    print(f"Saved raw docling output to {docling_json_path}")
                elif hasattr(doc, 'json'):
                    # For objects with json method
                    with open(docling_json_path, 'w', encoding='utf-8') as f:
                        f.write(doc.json())
                    print(f"Saved raw docling output to {docling_json_path}")
            except Exception as json_err:
                print(f"Could not save raw docling output: {str(json_err)}")
            
            # Extract document content for processing
            docling_data = {}
            
            # Debug what document properties are available
            if hasattr(doc, 'document'):
                document = doc.document
                print(f"Document object type: {type(document)}")
                print(f"Document properties: {dir(document)}")
                
                # Save raw document text
                raw_text_path = os.path.join(debug_dir, "raw_document_text.txt")
                try:
                    if hasattr(document, 'text'):
                        with open(raw_text_path, 'w', encoding='utf-8') as f:
                            f.write(document.text)
                        print(f"Saved raw document text to {raw_text_path}")
                except Exception as e:
                    print(f"Could not save raw document text: {str(e)}")
                    
                # Extract images using our improved method
                print("Extracting images using the improved docling image extractor...")
                # Get document_id from the base_dir path (eg: ./uploads/123 -> 123)
                doc_id = os.path.basename(base_dir)
                
                # Create document-specific image directory
                doc_image_dir = os.path.join(base_dir, "images")
                os.makedirs(doc_image_dir, exist_ok=True)
                
                # Use the new approach that properly loads images during PDF conversion
                image_count = extract_images_with_docling(file_location, base_dir, items)
                print(f"Extracted {image_count} images from document")
                    
                # Extract and process pages - this is where we'll get our text from
                if hasattr(document, 'pages') and document.pages:
                    print(f"Document has {len(document.pages)} pages")
                    
                    # Process each page to extract text
                    for page_idx, page in enumerate(document.pages):
                        print(f"Processing page {page_idx+1}")
                        page_text = ""
                        
                        # Try to extract text using different methods
                        # Document's export_to_text doesn't accept page_range parameter
                        # Try to get text from the page directly
                        if hasattr(page, 'text') and isinstance(page.text, str):
                            page_text = page.text
                            print(f"Got text from page.text: {len(page_text)} chars")
                        
                        # Method 2: Check if page has texts attribute
                        if not page_text and hasattr(page, 'texts') and page.texts:
                            try:
                                page_text = '\n'.join([t.text for t in page.texts if hasattr(t, 'text') and t.text])
                                print(f"Got text from page.texts: {len(page_text)} chars")
                            except Exception as e:
                                print(f"Error extracting from page.texts: {str(e)}")
                        
                        # Method 3: Try to access text elements if available
                        if hasattr(page, 'text_elements') and page.text_elements:
                            # Extract text from each text element on the page
                            for elem_idx, text_elem in enumerate(page.text_elements):
                                if hasattr(text_elem, 'text') and text_elem.text and text_elem.text.strip():
                                    # Save this text to a file
                                    text_file_name = f"{base_dir}/text/element_{elem_idx:03d}_p{page_idx}.txt"
                                    with open(text_file_name, 'w', encoding='utf-8') as f:
                                        f.write(text_elem.text)
                                    
                                    # Add to items list
                                    items.append({
                                        "page": page_idx,
                                        "type": "text",
                                        "text": text_elem.text,
                                        "path": text_file_name
                                    })
                        
                        # Method 4: Check if document.texts contains elements for this page
                        if not items and hasattr(document, 'texts'):
                            try:
                                page_texts = [t for t in document.texts if hasattr(t, 'page_number') and t.page_number == page_idx]
                                for t_idx, text in enumerate(page_texts):
                                    if hasattr(text, 'text') and text.text and text.text.strip():
                                        text_file_name = f"{base_dir}/text/doc_text_{t_idx:03d}_p{page_idx}.txt"
                                        with open(text_file_name, 'w', encoding='utf-8') as f:
                                            f.write(text.text)
                                        
                                        # Add to items list
                                        items.append({
                                            "page": page_idx,
                                            "type": "text",
                                            "text": text.text,
                                            "path": text_file_name
                                        })
                                print(f"Got {len(page_texts)} text elements from document.texts for page {page_idx+1}")
                            except Exception as e:
                                print(f"Error extracting from document.texts: {str(e)}")
                        
                        # If we have page text (from any method), chunk it
                        if page_text:
                            chunks = text_splitter.split_text(page_text)
                            for chunk_idx, chunk in enumerate(chunks):
                                text_file_name = f"{base_dir}/text/page_{page_idx:03d}_chunk_{chunk_idx:03d}.txt"
                                with open(text_file_name, 'w', encoding='utf-8') as f:
                                    f.write(chunk)
                                
                                # Add to items list
                                items.append({
                                    "page": page_idx,
                                    "type": "text",
                                    "text": chunk,
                                    "path": text_file_name
                                })
                                
                # Try methods available from full document object
                # Method 5: Try export_to_text method for the whole document
                
                # Initialize text_splitter here to ensure it's available in all code paths
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
                
                try:
                    if hasattr(document, 'export_to_text'):
                        full_text = document.export_to_text()
                        if full_text and full_text.strip():
                            # Save the full document text
                            full_text_path = os.path.join(base_dir, "text", "full_document.txt")
                            with open(full_text_path, 'w', encoding='utf-8') as f:
                                f.write(full_text)
                            print(f"Saved full document text: {len(full_text)} chars")
                                
                            # Split into chunks
                            chunks = text_splitter.split_text(full_text)
                            for chunk_idx, chunk in enumerate(chunks):
                                text_file_name = f"{base_dir}/text/document_chunk_{chunk_idx:03d}.txt"
                                with open(text_file_name, 'w', encoding='utf-8') as f:
                                    f.write(chunk)
                                
                                # Add to items list
                                items.append({
                                    "page": 0,  # Assign to first page as we don't know the page number
                                    "type": "text",
                                    "text": chunk,
                                    "path": text_file_name
                                })
                except Exception as e:
                    print(f"Error using document.export_to_text(): {str(e)}")
                
                # Method 6: Try export_to_markdown method
                if not items:
                    try:
                        if hasattr(document, 'export_to_markdown'):
                            markdown_text = document.export_to_markdown()
                            if markdown_text and markdown_text.strip():
                                # Save the markdown text
                                markdown_path = os.path.join(debug_dir, "document_markdown.md")
                                with open(markdown_path, 'w', encoding='utf-8') as f:
                                    f.write(markdown_text)
                                print(f"Saved markdown text: {len(markdown_text)} chars")
                                
                                # Split into chunks
                                chunks = text_splitter.split_text(markdown_text)
                                for chunk_idx, chunk in enumerate(chunks):
                                    text_file_name = f"{base_dir}/text/markdown_chunk_{chunk_idx:03d}.txt"
                                    with open(text_file_name, 'w', encoding='utf-8') as f:
                                        f.write(chunk)
                                    
                                    # Add to items list
                                    items.append({
                                        "page": 0,  # Assign to first page
                                        "type": "text",
                                        "text": chunk,
                                        "path": text_file_name
                                    })
                    except Exception as e:
                        print(f"Error using document.export_to_markdown(): {str(e)}")
                
                # Method 7: Try get all document.texts as a fallback
                if not items and hasattr(document, 'texts') and document.texts:
                    try:
                        # Process all text elements in the document
                        for text_idx, text_item in enumerate(document.texts):
                            if hasattr(text_item, 'text') and text_item.text and text_item.text.strip():
                                # Get page number if available
                                page_num = getattr(text_item, 'page_number', 0) if hasattr(text_item, 'page_number') else 0
                                
                                # Save to file
                                text_file_name = f"{base_dir}/text/text_item_{text_idx:03d}.txt"
                                with open(text_file_name, 'w', encoding='utf-8') as f:
                                    f.write(text_item.text)
                                
                                # Add to items
                                items.append({
                                    "page": page_num,
                                    "type": "text",
                                    "text": text_item.text,
                                    "path": text_file_name
                                })
                        print(f"Processed {len(document.texts)} text items from document.texts")
                    except Exception as e:
                        print(f"Error processing document.texts: {str(e)}")
                        
                # If all else fails, try to get document.text attribute directly
                if not items and hasattr(document, 'text') and document.text and document.text.strip():
                    # Save the full document text
                    full_text_path = os.path.join(base_dir, "text", "full_document.txt")
                    with open(full_text_path, 'w', encoding='utf-8') as f:
                        f.write(document.text)
                        print(f"Saved document.text: {len(document.text)} chars")
                    
                    # Split into chunks
                    chunks = text_splitter.split_text(document.text)
                    for chunk_idx, chunk in enumerate(chunks):
                        text_file_name = f"{base_dir}/text/document_chunk_{chunk_idx:03d}.txt"
                        with open(text_file_name, 'w', encoding='utf-8') as f:
                            f.write(chunk)
                        
                        # Add to items list
                        items.append({
                            "page": 0,  # Assign to first page
                            "type": "text",
                            "text": chunk,
                            "path": text_file_name
                        })
        except Exception as e:
            print(f"Error using docling Python API: {str(e)}")
            raise RuntimeError(f"Docling Python API processing failed: {str(e)}")
    
        # Method 7: Try get all document.texts as a fallback
        if not items and hasattr(document, 'texts') and document.texts:
            try:
                # Process all text elements in the document
                for text_idx, text_item in enumerate(document.texts):
                    if hasattr(text_item, 'text') and text_item.text and text_item.text.strip():
                        # Get page number if available
                        page_num = getattr(text_item, 'page_number', 0) if hasattr(text_item, 'page_number') else 0
                        
                        # Save to file
                        text_file_name = f"{base_dir}/text/text_item_{text_idx:03d}.txt"
                        with open(text_file_name, 'w', encoding='utf-8') as f:
                            f.write(text_item.text)
                        
                        # Add to items
                        items.append({
                            "page": page_num,
                            "type": "text",
                            "text": text_item.text,
                            "path": text_file_name
                        })
                print(f"Processed {len(document.texts)} text items from document.texts")
            except Exception as e:
                print(f"Error processing document.texts: {str(e)}")
        
        # Prepare metadata from docling output
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
                            
                        # Add the table to our items list
                        items.append({
                            "page": page_number,
                            "type": "table",
                            "path": table_file_path,
                            "metadata": table_metadata
                        })
                    except Exception as e:
                        print(f"Error processing table {i}: {str(e)}")
        except Exception as e:
            print(f"Error using tabula for table extraction: {str(e)}")
        
        # Save the document structure to a debug file if we have a document object
        if 'document' in locals() or 'document' in globals():
            try:
                doc_structure_path = os.path.join(debug_dir, "document_structure.json")
                
                # Helper function to safely handle callable attributes
                def _safe(val):
                    if callable(val):
                        try:
                            return val()  # call zero-arg methods
                        except TypeError:
                            return str(val)  # fall back to string representation
                    return val
                
                # Basic structure information
                doc_structure = {
                    "num_pages": _safe(getattr(document, "num_pages", 0)),
                    "num_text_elements": len(document.texts) if hasattr(document, 'texts') else 0,
                    "num_tables": len(document.tables) if hasattr(document, 'tables') else 0,
                    "num_images": len(document.pictures) if hasattr(document, 'pictures') else 0,
                    "timestamp": str(datetime.datetime.now()),
                    "docling_version": getattr(docling, "__version__", "unknown")
                }
                
                # Instead of trying to access all properties, create a safe subset
                safe_props = {}
                
                # Only examine a safe list of properties we know should be serializable
                safe_property_names = [
                    "title", "author", "creator", "subject", "keywords",
                    "producer", "created", "modified", "format", "language"
                ]
                
                for prop_name in safe_property_names:
                    if hasattr(document, prop_name):
                        try:
                            value = getattr(document, prop_name)
                            # Skip callable objects and private attributes
                            if not callable(value) and not isinstance(value, type):
                                # Convert non-basic types to string representation
                                if not isinstance(value, (str, int, float, bool, list, dict, type(None))):
                                    safe_props[prop_name] = str(value)
                                else:
                                    safe_props[prop_name] = value
                        except Exception:
                            # Skip properties that can't be accessed or serialized
                            pass
                                
                doc_structure['properties'] = safe_props
                
                with open(doc_structure_path, 'w', encoding='utf-8') as f:
                    json.dump(doc_structure, f, indent=2, default=str)
            except Exception as struct_err:
                print(f"Error saving document structure: {str(struct_err)}")
                
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
        
        # For testing purposes, do not fall back to PyMuPDF
        print("NOT falling back to PyMuPDF as requested for testing")
        return {
            "file_location": file_location if 'file_location' in locals() else None,
            "filename": file.filename,
            "items": items if 'items' in locals() else [],
            "error": f"Docling error: {str(e)}",
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
