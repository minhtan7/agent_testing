#!/usr/bin/env python3

# Test script for image extraction with docling
from fastapi import UploadFile
import os
from app.utils.docling_processor import process_pdf_with_docling

# Create a mock file object that mimics FastAPI's UploadFile
class MockFile:
    def __init__(self, path):
        self.file = open(path, 'rb')
        self.filename = os.path.basename(path)
    
    async def read(self):
        return self.file.read()

# Use the other existing PDF file in the uploads directory
pdf_path = './uploads/0/2405.19941v1.pdf'
if not os.path.exists(pdf_path):
    print(f"Test PDF file not found at {pdf_path}")
    # Try the alternative PDF
    pdf_path = './uploads/0/bain_brief_agile_innovation.pdf'
    if not os.path.exists(pdf_path):
        print(f"No test PDF files found in uploads directory")
        exit(1)
    
print(f"Using PDF file: {pdf_path}")

# Process the PDF with our enhanced docling processor
print("Testing image extraction with docling...")
file = MockFile(pdf_path)
result = process_pdf_with_docling(file)

# Check for images in the result
image_items = [item for item in result.get("items", []) if item.get("type") == "image"]
print(f"\nSummary:")
print(f"Total items: {len(result.get('items', []))}")
print(f"Images extracted: {len(image_items)}")

if image_items:
    print("\nExtracted images:")
    for i, img in enumerate(image_items):
        print(f"  {i+1}. {img.get('path')}")
else:
    print("\nNo images were extracted. Check the logs above for details.")
