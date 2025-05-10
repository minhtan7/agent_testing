from typing import Union, Optional
from fastapi import FastAPI, File, UploadFile
from pydantic import BaseModel
from utils import create_directories, process_tables, process_text_chunks, process_images, process_page_images
from langchain.text_splitter import RecursiveCharacterTextSplitter
from tqdm import tqdm
import pymupdf
import os

app = FastAPI()


class Item(BaseModel):
    name: str
    price: float
    is_offer: Union[bool, None] = None


class FileID:
    id = 0

@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}


@app.put("/items/{item_id}")
def update_item(item_id: int, item: Item):
    return {"item_name": item.name, "item_id": item_id}


@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    print("file", file)
    base_dir = f"./uploads/{FileID.id}"
    FileID.id += 1 
    os.makedirs(base_dir, exist_ok=True)
    file_location = os.path.join(base_dir, file.filename)
    
    # Check if file already exists
    if not os.path.exists(file_location):
        with open(file_location, "wb") as buffer:
            buffer.write(await file.read())

    doc = pymupdf.open(file_location)
    num_pages = len(doc)

    # Creating the directories
    create_directories(base_dir)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=200, length_function=len)
    items = []

    # Process each page of the PDF
    for page_num in tqdm(range(num_pages), desc="Processing PDF pages"):
        page = doc[page_num]
        text = page.get_text()
        process_tables(file_location, page_num, base_dir, items)
        process_text_chunks(text, text_splitter, page_num, base_dir, items, file_location)
        process_images(page, page_num, base_dir, items, file_location)
        process_page_images(page, page_num, base_dir, items)

    return {"info": f"file '{file.filename}' processed and saved at '{file_location}'"}


@app.post("/query-pdf")
async def query_pdf(document_id: int, text_query: str, query_text: bool = True, query_table: bool = False, query_image: bool = False):
    base_dir = f"./uploads/{document_id}"
    items = []
    response = {"text": [], "tables": [], "images": []}

    # Load extracted items from the processing step
    for item in items:
        if query_text and item['type'] == 'text' and text_query.lower() in item['text'].lower():
            response["text"].append({"page": item['page'], "text": item['text']})
        if query_table and item['type'] == 'table':
            response["tables"].append({"page": item['page'], "table": item['text']})
        if query_image and item['type'] == 'image':
            response["images"].append({"page": item['page'], "image": item['image']})

    if not any(response.values()):
        return {"error": "No relevant data found"}

    return response