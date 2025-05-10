from app.models.upload import FileID
from fastapi import UploadFile
import os
import pymupdf
from langchain.text_splitter import RecursiveCharacterTextSplitter
from tqdm import tqdm
from app.utils.pdf_parser import create_directories, process_tables, process_text_chunks, process_images, process_page_images


def process_pdf(file: UploadFile):
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
