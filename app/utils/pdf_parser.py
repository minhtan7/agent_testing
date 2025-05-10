import os
import tabula
import pymupdf
import base64


def create_directories(base_dir):
    directories = ["images", "text", "tables", "page_images"]
    for dir in directories:
        os.makedirs(os.path.join(base_dir, dir), exist_ok=True)


def process_tables(file_location, page_num, base_dir, items):
    try:
        tables = tabula.read_pdf(file_location, pages=page_num + 1, multiple_tables=True)
        print("tables", tables)
        if not tables:
            return
        for table_idx, table in enumerate(tables):
            table_text = "\n".join([" | ".join(map(str, row)) for row in table.values])
            table_file_name = f"{base_dir}/tables/{os.path.basename(file_location)}_table_{page_num}_{table_idx}.txt"
            with open(table_file_name, 'w') as f:
                f.write(table_text)
            items.append({"page": page_num, "type": "table", "text": table_text, "path": table_file_name})
    except Exception as e:
        print(f"Error extracting tables from page {page_num}: {str(e)}")


# Process text chunks with improved structure preservation
def process_text_chunks(text, text_splitter, page_num, base_dir, items, file_location):
    # First, try to identify potential headings in the text
    lines = text.split('\n')
    headings = []
    
    # Simple heuristic: potential headings are short lines that don't end with punctuation
    # and don't have lowercase letters in them or start with numbers followed by periods (like 1. 2. etc)
    for i, line in enumerate(lines):
        line = line.strip()
        if line and len(line) < 50 and not line[-1] in '.,:;?!'\
           and (line.isupper() or any(word[0].isupper() for word in line.split()))\
           and not (line.startswith(tuple(str(n) + '.' for n in range(10)))):
            headings.append((i, line))
    
    # Split text into chunks
    chunks = text_splitter.split_text(text)
    
    for i, chunk in enumerate(chunks):
        # Find which headings are in this chunk
        chunk_headings = []
        for line_idx, heading in headings:
            if heading in chunk:
                chunk_headings.append(heading)
        
        # Create metadata about the chunk context
        metadata = {
            "page": page_num,
            "chunk_index": i,
            "headings": chunk_headings,
            "total_chunks": len(chunks)
        }
        
        # Save to file
        text_file_name = f"{base_dir}/text/{os.path.basename(file_location)}_text_{page_num}_{i}.txt"
        with open(text_file_name, 'w') as f:
            f.write(chunk)
        
        # Add broader context snippet (first 200 chars for quick preview)
        snippet = chunk[:200] + ('...' if len(chunk) > 200 else '')
        
        # Add to items with enhanced metadata
        items.append({
            "page": page_num, 
            "type": "text", 
            "text": chunk, 
            "path": text_file_name,
            "metadata": metadata,
            "snippet": snippet,
            "headings": chunk_headings
        })


# Process images
def process_images(page, page_num, base_dir, items, file_location):
    images = page.get_images(full=True)
    print("images", images)
    for idx, image in enumerate(images):
        try:
            xref = image[0]
            pix = pymupdf.Pixmap(page.parent, xref)
            
            # Convert to RGB if needed (fixes unsupported colorspace issue)
            if pix.n > 4:  # CMYK, DeviceN or other complex colorspace
                pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
            elif pix.colorspace and pix.colorspace.name not in ("DeviceRGB", "DeviceGray"):
                pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
            
            image_name = f"{base_dir}/images/{os.path.basename(file_location)}_image_{page_num}_{idx}_{xref}.png"
            pix.save(image_name)
            with open(image_name, 'rb') as f:
                encoded_image = base64.b64encode(f.read()).decode('utf8')
            items.append({"page": page_num, "type": "image", "path": image_name, "image": encoded_image})
        except Exception as e:
            print(f"Error processing image {idx} on page {page_num}: {str(e)}")
            # Continue processing other images


# Process page images
def process_page_images(page, page_num, base_dir, items):
    try:
        pix = page.get_pixmap()
        
        # Convert to RGB if needed (fixes unsupported colorspace issue)
        if pix.n > 4:  # CMYK, DeviceN or other complex colorspace
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        elif pix.colorspace and pix.colorspace.name not in ("DeviceRGB", "DeviceGray"):
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
            
        page_path = os.path.join(base_dir, f"page_images/page_{page_num:03d}.png")
        pix.save(page_path)
        with open(page_path, 'rb') as f:
            page_image = base64.b64encode(f.read()).decode('utf8')
            items.append({"page": page_num, "type": "page_image", "path": page_path, "image": page_image})
    except Exception as e:
        print(f"Error processing page image for page {page_num}: {str(e)}")
        # Continue processing other pages
