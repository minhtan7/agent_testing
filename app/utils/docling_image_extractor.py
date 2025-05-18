"""
Dedicated module for handling image extraction from docling document objects.
Using the DocumentConverter with proper options to enable figure crops.
"""
import os
import base64
import traceback
from io import BytesIO
from pathlib import Path
from typing import List, Dict, Any, Optional

# Import docling components needed for image extraction
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.base_models import InputFormat
from PIL import Image  # pip install pillow

# Helper function to safely access an attribute that might be a method
def safe_access(obj, attr_name, default=None):
    """Safely access an attribute that might be a method without parameters."""
    if not hasattr(obj, attr_name):
        return default
    attr = getattr(obj, attr_name)
    if callable(attr):
        try:
            return attr()
        except TypeError:  # Only handle wrong signature
            print(f"Error calling {attr_name}: wrong signature")
            return default
        except Exception as e:
            print(f"Error calling {attr_name}: {e}")
            return default
    return attr

def load_pdf_with_figures(pdf_path: str, dpi_scale: float = 2.0):
    """
    Return a DoclingDocument whose PictureItems already contain a PIL image.
    Only figure crops are generated – no full page bitmaps.
    
    Args:
        pdf_path: Path to the PDF file
        dpi_scale: Resolution scale factor (1.0 = 72dpi)
        
    Returns:
        DoclingDocument with loaded images
    """
    pdf_path = Path(pdf_path)

    opts = PdfPipelineOptions(
        images_scale=dpi_scale,           # 72 dpi × scale ⇒ 144 dpi here
        generate_picture_images=True,     # <-- keep the figure crops
        generate_page_images=False,       # <-- default, but explicit for clarity
        # artifacts_path="/tmp/docling_artifacts"  # uncomment if you need to force images to disk
    )

    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
    )

    result = converter.convert(pdf_path)
    return result.document        # DoclingDocument

def extract_figures(doc, out_dir: str = "./figures"):
    """
    Saves every PictureItem as PNG and returns a list of metadata dicts.
    Filters out decorative images and extracts available captions.
    
    Args:
        doc: DoclingDocument with loaded images
        out_dir: Directory to save images to
        
    Returns:
        List of dictionaries with image metadata
    """
    import numpy as np
    from scipy.stats import entropy
    import imagehash
    
    os.makedirs(out_dir, exist_ok=True)
    figures = []
    processed_hashes = set()  # To track duplicate images
    
    # Get pictures safely - doc.pictures might be a method
    pictures = safe_access(doc, 'pictures', [])
    print(f"Found {len(pictures) if pictures else 0} pictures in document")
    
    for idx, pic in enumerate(pictures):
        img: Image.Image = pic.get_image(doc)   # now always a PIL.Image
        if img is None:                         # safety guard
            continue
            
        # 1. First, check if docling already has a caption_text (which may be a method)
        caption = safe_access(pic, "caption_text", "")
        if caption:
            trunc = f"{caption[:50]}..." if len(caption) > 50 else caption
            print(f"Found caption from docling: {trunc}")
        
        # 2. Filter decorative images
        
        # Size filter - skip if min(width, height) < 80 px or area < 5000 px
        width, height = img.size
        if min(width, height) < 80 or (width * height) < 5000:
            print(f"Skipping small decorative image: {width}x{height}")
            continue
            
        # Aspect ratio filter - skip if w/h > 8 or h/w > 8 (ribbons, rules)
        aspect_ratio = width / height if height > 0 else float('inf')
        inverse_aspect_ratio = height / width if width > 0 else float('inf')
        if aspect_ratio > 8 or inverse_aspect_ratio > 8:
            print(f"Skipping decorative image with extreme aspect ratio: {aspect_ratio:.2f}")
            continue
            
        # Color entropy filter - skip if Shannon entropy < 1.0 bit
        try:
            # Convert to grayscale and calculate entropy
            gray_img = img.convert('L')
            img_array = np.array(gray_img)
            hist = np.histogram(img_array, bins=256, range=(0, 256))[0] / img_array.size
            img_entropy = entropy(hist, base=2)  # Shannon entropy in bits
            
            if img_entropy < 1.0:
                print(f"Skipping low-entropy decorative image: {img_entropy:.2f} bits")
                continue
        except Exception as e:
            print(f"Error calculating image entropy, including image anyway: {str(e)}")
            
        # Duplicate hash - skip if pHash distance < 5 with any previously processed image
        try:
            img_hash = imagehash.phash(img)
            
            # Check if this image is too similar to one we've already processed
            is_duplicate = False
            for existing_hash in processed_hashes:
                if img_hash - existing_hash < 5:  # Hash distance threshold
                    print(f"Skipping duplicate image with hash distance < 5")
                    is_duplicate = True
                    break
                    
            if is_duplicate:
                continue
                
            # Add this hash to our set of processed hashes
            processed_hashes.add(img_hash)
            
        except Exception as e:
            print(f"Error calculating image hash, including image anyway: {str(e)}")
        
        # Image passed all filters, save it
        filename = f"docling_image_{idx + 1}.png"
        path = os.path.join(out_dir, filename)
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # Save the image
        img.save(path)
        print(f"Saved image to {path}")

        # convert to base-64 for downstream APIs
        with BytesIO() as buf:
            img.save(buf, format="PNG")
            encoded = base64.b64encode(buf.getvalue()).decode()

        # Add image to figures list with any caption found
        figures.append({
            "page": safe_access(pic, "page_number", 0),
            "type": "image",
            "path": path,
            "image": encoded,
            "text": caption  # Save caption as text for DocumentChunk text_content
        })

    return figures

def extract_images_with_docling(file_location: str, base_dir: str, items: list) -> int:
    """
    Extract images from a PDF file using docling with the proper configuration.
    
    Args:
        file_location: Path to the PDF file
        base_dir: Base directory for output files
        items: List to append processed items to
        
    Returns:
        Number of images successfully extracted
    """
    # Create images directory if it doesn't exist
    images_dir = os.path.join(base_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    
    try:
        # Load the document with figure crops enabled
        print(f"Loading PDF with docling DocumentConverter: {file_location}")
        document = load_pdf_with_figures(file_location, dpi_scale=2.0)
        
        # Extract the figures - safely handle document object
        print(f"Extracting figures from document")
        if document is None:
            print("Document is None, cannot extract figures")
            return 0
            
        figures = extract_figures(document, out_dir=images_dir)
        
        # Add the figures to the items list - safely handle figures variable
        if figures is None:
            figures = []
            
        items.extend(figures)
        
        print(f"Successfully extracted {len(figures)} images from document")
        return len(figures)
    except Exception as e:
        print(f"Error extracting images with docling: {str(e)}")
        traceback.print_exc()  # Print the full traceback for debugging
        return 0
