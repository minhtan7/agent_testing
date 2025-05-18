"""
Dedicated module for handling image extraction from docling document objects.
"""
import os
import base64
from typing import List, Dict, Any, Optional

def extract_images_from_docling(document, base_dir: str, file_location: str, items: list) -> int:
    """
    Extract images from docling document object and save them to the file system.
    
    Args:
        document: Docling document object
        base_dir: Base directory for output files
        file_location: Path to the original PDF file
        items: List to append processed items to
        
    Returns:
        Number of images successfully extracted
    """
    image_count = 0
    
    try:
        # Method 1: Extract images directly from pages
        if hasattr(document, 'pages'):
            for page_idx, page in enumerate(document.pages):
                # Try to get page images if available
                if hasattr(page, 'pictures') and page.pictures:
                    print(f"Found {len(page.pictures)} pictures on page {page_idx+1}")
                    for img_idx, image in enumerate(page.pictures):
                        try:
                            # Try to get image data
                            if hasattr(image, 'data') and image.data:
                                # Save image to file
                                img_path = f"{base_dir}/images/page_{page_idx+1}_img_{img_idx+1}.png"
                                with open(img_path, 'wb') as f:
                                    f.write(image.data)
                                
                                # Create base64 representation for API
                                encoded_image = base64.b64encode(image.data).decode('utf-8')
                                
                                # Add to items
                                items.append({
                                    "page": page_idx,
                                    "type": "image",
                                    "path": img_path,
                                    "image": encoded_image  # Include base64 encoded image
                                })
                                image_count += 1
                        except Exception as e:
                            print(f"Error extracting image from page {page_idx+1}, image {img_idx+1}: {str(e)}")
        
        # Method 2: Get document-level images if available
        if hasattr(document, 'pictures') and document.pictures:
            print(f"Found {len(document.pictures)} document-level pictures")
            # Try to access the raw images list if available
            if hasattr(document, '_images') and document._images:
                print(f"Document has _images attribute with {len(document._images)} items")
                # Try to extract from raw _images list if available
                for i, img_data in enumerate(document._images):
                    try:
                        print(f"Raw image {i+1} type: {type(img_data)}")
                        # Try to save the raw image data
                        if hasattr(img_data, 'data') and img_data.data:
                            # Save image to file
                            img_path = f"{base_dir}/images/raw_img_{i+1}.png"
                            with open(img_path, 'wb') as f:
                                f.write(img_data.data)
                            print(f"Saved raw image {i+1} to {img_path}")
                            
                            # Create base64 representation for API
                            encoded_image = base64.b64encode(img_data.data).decode('utf-8')
                            
                            # Add to items
                            items.append({
                                "page": 0,  # Page number unknown for raw images
                                "type": "image",
                                "path": img_path,
                                "image": encoded_image
                            })
                            image_count += 1
                    except Exception as e:
                        print(f"Error extracting raw image {i+1}: {str(e)}")
            
            # Try to extract images using rect information from PictureItem objects
            if image_count == 0 and hasattr(document, 'pictures') and document.pictures:
                print("Attempting to extract images using rect information...")
                for img_idx, image in enumerate(document.pictures):
                    try:
                        if hasattr(image, 'rect') and image.rect:
                            print(f"Picture {img_idx+1} has rect: {image.rect}")
                            # If there's location data, we could try to extract this region using another method
                            # but would need PyMuPDF for this approach
                    except Exception as e:
                        print(f"Error checking rect for picture {img_idx+1}: {str(e)}")
            
            # Print details about each picture to debug
            for img_idx, image in enumerate(document.pictures):
                print(f"Picture {img_idx+1} type: {type(image)}")
                # Only print first few attributes to avoid overwhelming logs
                attributes = [attr for attr in dir(image) if not attr.startswith('__')]
                print(f"Picture {img_idx+1} attributes: {attributes}")
                
                # Check if the picture has a parent or page property that can help locate it
                if hasattr(image, 'parent') and image.parent:
                    print(f"Picture {img_idx+1} has parent: {type(image.parent)}")
                    
                    # Try to access image data through the parent RefItem
                    parent = image.parent
                    if hasattr(parent, 'content') and parent.content:
                        try:
                            print(f"Parent has content attribute, type: {type(parent.content)}")
                            # If content is binary data, try to save it
                            if isinstance(parent.content, bytes):
                                # Save the content as an image
                                img_path = f"{base_dir}/images/doc_img_{img_idx+1}_parent.png"
                                with open(img_path, 'wb') as f:
                                    f.write(parent.content)
                                
                                print(f"Saved parent content as image: {img_path}")
                                
                                # Create base64 representation for API
                                encoded_image = base64.b64encode(parent.content).decode('utf-8')
                                
                                # Add to items
                                page_num = getattr(image, 'page_number', 0) if hasattr(image, 'page_number') else 0
                                items.append({
                                    "page": page_num,
                                    "type": "image",
                                    "path": img_path,
                                    "image": encoded_image
                                })
                                image_count += 1
                                continue  # Go to next image
                        except Exception as e:
                            print(f"Error accessing parent content: {str(e)}")
                
                if hasattr(image, 'page_number'):
                    print(f"Picture {img_idx+1} page number: {image.page_number}")
                
                # See if we can find the image data through different attributes
                if hasattr(image, 'data'):
                    print(f"Picture {img_idx+1} has data attribute of type: {type(image.data)}")
                    print(f"Picture {img_idx+1} data length: {len(image.data) if image.data and hasattr(image.data, '__len__') else 'N/A'}")
                elif hasattr(image, 'pil_image') or hasattr(image, 'image') or hasattr(image, 'source'):
                    print(f"Picture {img_idx+1} has alternative image storage")
                
                # First try to use the get_image method if available
                try:
                    if hasattr(image, 'get_image') and callable(getattr(image, 'get_image')):
                        # Get image using the method - pass document as required argument
                        print(f"Trying to get image {img_idx+1} using get_image() method")
                        
                        # The error shows we need to pass the document as an argument
                        pil_image = image.get_image(doc=document)
                        
                        if pil_image:
                            print(f"Got PIL image from get_image(): {type(pil_image)}")
                            
                            # Get page number if available, otherwise default to 0
                            page_num = getattr(image, 'page_number', 0) if hasattr(image, 'page_number') else 0
                            
                            # Save image to file
                            img_path = f"{base_dir}/images/doc_img_{img_idx+1}_pil.png"
                            pil_image.save(img_path)
                            print(f"Successfully saved image {img_idx+1} to {img_path}")
                            
                            # Read back for base64 encoding
                            with open(img_path, 'rb') as f:
                                img_bytes = f.read()
                                encoded_image = base64.b64encode(img_bytes).decode('utf-8')
                            
                            # Add to items
                            items.append({
                                "page": page_num,
                                "type": "image",
                                "path": img_path,
                                "image": encoded_image
                            })
                            image_count += 1
                            print(f"Successfully processed image {img_idx+1} using get_image()")
                            continue  # Go to next image
                except Exception as e:
                    print(f"Error using get_image() for image {img_idx+1}: {str(e)}")
                
                # If get_image failed, try different attributes
                for attr in ['data', 'pil_image', 'image', 'source', 'content', 'bytes']:
                    try:
                        if hasattr(image, attr):
                            img_data = getattr(image, attr)
                            print(f"Found {attr} attribute, type: {type(img_data)}")
                            
                            # Special handling for image attribute in docling
                            if attr == 'image':
                                if img_data is None:
                                    print(f"Image attribute is None for picture {img_idx+1}")
                                    # Try to explicitly request image from document
                                    try:
                                        # Call the parent document's get_image_for function if available
                                        if hasattr(document, 'get_image_for') and callable(getattr(document, 'get_image_for')):
                                            print(f"Trying document.get_image_for method for picture {img_idx+1}")
                                            pil_img = document.get_image_for(image)
                                            if pil_img:
                                                # Get page number if available, otherwise default to 0
                                                page_num = getattr(image, 'page_number', 0) if hasattr(image, 'page_number') else 0
                                                
                                                # Save image to file
                                                img_path = f"{base_dir}/images/doc_img_{img_idx+1}_doc_method.png"
                                                pil_img.save(img_path)
                                                
                                                # Read back for base64 encoding
                                                with open(img_path, 'rb') as f:
                                                    img_bytes = f.read()
                                                    encoded_image = base64.b64encode(img_bytes).decode('utf-8')
                                                
                                                # Add to items
                                                items.append({
                                                    "page": page_num,
                                                    "type": "image",
                                                    "path": img_path,
                                                    "image": encoded_image
                                                })
                                                image_count += 1
                                                print(f"Successfully saved image {img_idx+1} using document.get_image_for")
                                                break
                                    except Exception as e:
                                        print(f"Error using document.get_image_for for image {img_idx+1}: {str(e)}")
                                    
                                    # Try to access internal image methods
                                    # Try _image_to_base64 method which might have direct access to image data
                                    if hasattr(image, '_image_to_base64') and callable(getattr(image, '_image_to_base64')):
                                        try:
                                            print(f"Trying to use _image_to_base64 method for picture {img_idx+1}")
                                            # This might return base64 encoded image data directly
                                            base64_data = image._image_to_base64()
                                            if base64_data:
                                                print(f"Found base64 data: {base64_data[:30]}...")
                                                # Decode base64 to binary
                                                try:
                                                    import base64 as python_base64
                                                    img_data = python_base64.b64decode(base64_data)
                                                    
                                                    # Get page number if available, otherwise default to 0
                                                    page_num = getattr(image, 'page_number', 0) if hasattr(image, 'page_number') else 0
                                                    
                                                    # Save image to file
                                                    img_path = f"{base_dir}/images/doc_img_{img_idx+1}_base64.png"
                                                    with open(img_path, 'wb') as f:
                                                        f.write(img_data)
                                                    print(f"Successfully saved image {img_idx+1} to {img_path} from _image_to_base64")
                                                    
                                                    # Add to items
                                                    items.append({
                                                        "page": page_num,
                                                        "type": "image",
                                                        "path": img_path,
                                                        "image": base64_data  # Already base64 encoded
                                                    })
                                                    image_count += 1
                                                    continue  # Go to next image
                                                except Exception as e:
                                                    print(f"Error decoding base64 data: {str(e)}")
                                        except Exception as e:
                                            print(f"Error using _image_to_base64: {str(e)}")
                                    
                                    # Try _image_to_hexhash method which might contain or provide access to image data
                                    if hasattr(image, '_image_to_hexhash') and callable(getattr(image, '_image_to_hexhash')):
                                        try:
                                            print(f"Trying to use _image_to_hexhash method for picture {img_idx+1}")
                                            hexhash = image._image_to_hexhash()
                                            print(f"Image {img_idx+1} hexhash: {hexhash}")
                                            # The hexhash itself isn't the image data, but it might be useful for debugging
                                        except Exception as e:
                                            print(f"Error using _image_to_hexhash: {str(e)}")
                                            
                                    # Try to get raw image data through hex_reference if available
                                    if hasattr(image, 'hex_reference') and image.hex_reference:
                                        try:
                                            print(f"Trying to use hex_reference for picture {img_idx+1}: {image.hex_reference}")
                                        except Exception as e:
                                            print(f"Error accessing hex_reference: {str(e)}")
                                elif hasattr(img_data, 'load_pil'):
                                    try:
                                        print(f"Trying to load PIL image using load_pil() method")
                                        pil_img = img_data.load_pil()
                                        if pil_img:
                                            # Get page number if available, otherwise default to 0
                                            page_num = getattr(image, 'page_number', 0) if hasattr(image, 'page_number') else 0
                                            
                                            # Save image to file
                                            img_path = f"{base_dir}/images/doc_img_{img_idx+1}_loadpil.png"
                                            pil_img.save(img_path)
                                            
                                            # Read back for base64 encoding
                                            with open(img_path, 'rb') as f:
                                                img_bytes = f.read()
                                                encoded_image = base64.b64encode(img_bytes).decode('utf-8')
                                            
                                            # Add to items
                                            items.append({
                                                "page": page_num,
                                                "type": "image",
                                                "path": img_path,
                                                "image": encoded_image
                                            })
                                            image_count += 1
                                            print(f"Successfully saved image {img_idx+1} using load_pil()")
                                            break
                                    except Exception as e:
                                        print(f"Error using load_pil for image {img_idx+1}: {str(e)}")
                            
                            # Try regular binary data processing
                            if img_data and hasattr(img_data, '__len__') and len(img_data) > 0:
                                # Get page number if available, otherwise default to 0
                                page_num = getattr(image, 'page_number', 0) if hasattr(image, 'page_number') else 0
                                
                                # Save image to file
                                img_path = f"{base_dir}/images/doc_img_{img_idx+1}_{attr}.png"
                                with open(img_path, 'wb') as f:
                                    # Handle the case when img_data is not bytes
                                    if isinstance(img_data, bytes):
                                        f.write(img_data)
                                    elif hasattr(img_data, 'tobytes'):
                                        f.write(img_data.tobytes())
                                    elif hasattr(img_data, 'save'):
                                        # Might be a PIL Image
                                        img_data.save(img_path)
                                        break  # Skip the rest of the code if save worked
                                    else:
                                        print(f"Don't know how to save data of type {type(img_data)}")
                                        continue
                                
                                # Read back for base64 encoding
                                with open(img_path, 'rb') as f:
                                    img_bytes = f.read()
                                    encoded_image = base64.b64encode(img_bytes).decode('utf-8')
                                
                                # Add to items
                                items.append({
                                    "page": page_num,
                                    "type": "image",
                                    "path": img_path,
                                    "image": encoded_image
                                })
                                image_count += 1
                                print(f"Successfully saved image {img_idx+1} using {attr} attribute")
                                break  # Success, so break out of the attribute loop
                    except Exception as e:
                        print(f"Error extracting document image {img_idx+1} attribute {attr}: {str(e)}")
        
        # Method 3: Try looking for binary attachments in the document if no images found
        if image_count == 0:
            print("No images found through regular methods, checking for attachments...")
            try:
                # Check if the document has attachments that might be images
                if hasattr(document, 'attachments'):
                    for idx, attachment in enumerate(document.attachments):
                        try:
                            if hasattr(attachment, 'data') and attachment.data:
                                # Try to determine if this might be an image
                                is_image = False
                                if hasattr(attachment, 'mime_type') and 'image' in attachment.mime_type.lower():
                                    is_image = True
                                elif hasattr(attachment, 'name') and any(ext in attachment.name.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']):
                                    is_image = True
                                    
                                if is_image:
                                    # Save as image
                                    name = getattr(attachment, 'name', f"attachment_{idx}.png")
                                    img_path = f"{base_dir}/images/{name}"
                                    with open(img_path, 'wb') as f:
                                        f.write(attachment.data)
                                        
                                    # Create base64 representation
                                    encoded_image = base64.b64encode(attachment.data).decode('utf-8')
                                    
                                    # Add to items
                                    items.append({
                                        "page": 0,  # We don't know the page
                                        "type": "image",
                                        "path": img_path,
                                        "image": encoded_image
                                    })
                                    image_count += 1
                        except Exception as e:
                            print(f"Error processing attachment {idx}: {str(e)}")
            except Exception as e:
                print(f"Error checking for attachments: {str(e)}")
                
            # Don't fall back to PyMuPDF as requested
                
    except Exception as e:
        print(f"Error during image extraction: {str(e)}")
        
    if image_count == 0:
        print("No images found in the document using docling methods.")
        print("Note: PyMuPDF fallback was disabled as requested.")
        print("")
        print("It seems docling is detecting images but not loading the actual image data.")
        print("This is likely a limitation of the current version of the docling library.")
        print("Options to consider:")
        print("1. Update the docling library if a newer version is available")
        print("2. Enable PyMuPDF fallback for image extraction only")
        print("3. Use a different PDF library specifically for image extraction")
    else:
        print(f"Extracted {image_count} images total")
    return image_count
