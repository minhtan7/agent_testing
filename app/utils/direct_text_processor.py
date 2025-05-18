def process_text_elements_directly(document, base_dir: str, file_location: str, items: list) -> int:
    """
    Process text elements directly from a docling document and add them as text items.
    This ensures that text content is always extracted even if the regular processing pipeline fails.
    
    Args:
        document: A docling document object
        base_dir: Base directory for output
        file_location: Path to the original PDF file
        items: List to append processed items to
        
    Returns:
        Number of text elements processed
    """
    processed_count = 0
    
    # Make sure we have text elements to process
    if not hasattr(document, 'texts') or not document.texts:
        print("No text elements found in document")
        return 0
        
    # Create text directory
    text_dir = os.path.join(base_dir, "text")
    os.makedirs(text_dir, exist_ok=True)
    
    # Process each text element
    for i, text_element in enumerate(document.texts):
        if hasattr(text_element, 'text') and text_element.text:
            # Try to get page number, default to 0
            page_num = 0
            if hasattr(text_element, 'page_number'):
                page_num = text_element.page_number
            elif hasattr(text_element, 'page'):
                page_num = text_element.page
                
            # Save as a text file
            text_file = os.path.join(text_dir, f"{os.path.basename(file_location)}_element_{i}.txt")
            try:
                with open(text_file, 'w', encoding='utf-8') as f:
                    f.write(text_element.text)
                    
                # Add to items list
                items.append({
                    "page": page_num,
                    "type": "text",
                    "text": text_element.text,
                    "path": text_file,
                    "snippet": text_element.text[:100] + ('...' if len(text_element.text) > 100 else '')
                })
                processed_count += 1
            except Exception as e:
                print(f"Error processing text element {i}: {str(e)}")
                
    print(f"Directly processed {processed_count} text elements into text chunks")
    return processed_count
