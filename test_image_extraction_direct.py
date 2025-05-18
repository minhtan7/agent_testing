#!/usr/bin/env python3

import os
import sys
from app.utils.extract_docling_images import extract_images_from_docling
from app.models.upload import FileID
import docling

def test_image_extraction(pdf_path):
    """
    Test the image extraction function directly with a given PDF file.
    """
    if not os.path.exists(pdf_path):
        print(f"PDF file not found: {pdf_path}")
        return
    
    print(f"Testing image extraction with file: {pdf_path}")
    
    # Create output directory
    base_dir = f"./uploads/{FileID.id}"
    FileID.id += 1
    os.makedirs(base_dir, exist_ok=True)
    os.makedirs(f"{base_dir}/images", exist_ok=True)
    
    # Create debug directory
    debug_dir = f"{base_dir}/debug"
    os.makedirs(debug_dir, exist_ok=True)
    
    try:
        print("Opening document with docling...")
        # Try to open the document directly with docling
        document = docling.Document(path_or_stream=pdf_path)
        print(f"Document opened successfully with {len(document.pages)} pages")
        
        # Check if document has pictures
        if hasattr(document, 'pictures'):
            print(f"Document has {len(document.pictures)} pictures")
            for i, pic in enumerate(document.pictures):
                print(f"Picture {i+1} type: {type(pic)}")
                print(f"Picture {i+1} attributes: {[a for a in dir(pic) if not a.startswith('_')]}")
        else:
            print("Document has no 'pictures' attribute")
        
        # Extract images using our function
        print("Extracting images...")
        items = []
        image_count = extract_images_from_docling(document, base_dir, pdf_path, items)
        print(f"Extracted {image_count} images")
        
        # Print details about extracted images
        if items:
            print("\nExtracted image details:")
            for i, item in enumerate(items):
                if item['type'] == 'image':
                    print(f"  {i+1}. Path: {item['path']}")
                    if os.path.exists(item['path']):
                        print(f"     File exists: {os.path.getsize(item['path'])} bytes")
                    else:
                        print(f"     File does not exist")
        else:
            print("\nNo images were extracted")
            
    except Exception as e:
        print(f"Error processing document: {str(e)}")

if __name__ == "__main__":
    # Check if a PDF file was provided as argument
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        test_image_extraction(pdf_path)
    else:
        print("Usage: python test_image_extraction_direct.py path/to/pdf/file.pdf")
