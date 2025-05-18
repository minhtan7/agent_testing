"""
Test script for the new docling image extraction approach.
"""

import os
import sys
from pathlib import Path

# Add the project root to the path so we can import the app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from app.utils.docling_image_extractor import load_pdf_with_figures, extract_figures

def test_image_extraction():
    # Find a PDF file in the uploads directory
    upload_dir = './uploads'
    pdf_files = []
    
    for root, dirs, files in os.walk(upload_dir):
        for file in files:
            if file.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(root, file))
    
    if not pdf_files:
        print("No PDF files found in the uploads directory!")
        return
    
    # Use the first PDF file for testing
    test_file = pdf_files[1]
    print(f"Testing with PDF file: {test_file}")
    
    # Create test output directory
    test_dir = './test_image_output'
    os.makedirs(test_dir, exist_ok=True)
    
    try:
        # Load the document with figure crops enabled
        print(f"Loading PDF with docling DocumentConverter...")
        document = load_pdf_with_figures(test_file, dpi_scale=2.0)
        
        print(f"Document loaded successfully")
        print(f"Document has {len(document.pictures) if hasattr(document, 'pictures') else 0} pictures")
        
        # Extract the figures
        print(f"Extracting figures from document...")
        items = []
        figures = extract_figures(document, out_dir=os.path.join(test_dir, "images"))
        items.extend(figures)
        
        print(f"Successfully extracted {len(figures)} images from document")
        
        # Print the paths of the extracted images
        if figures:
            print("\nExtracted images:")
            for i, figure in enumerate(figures):
                print(f"  {i+1}. {figure['path']}")
    except Exception as e:
        print(f"Error testing image extraction: {str(e)}")

if __name__ == "__main__":
    test_image_extraction()
