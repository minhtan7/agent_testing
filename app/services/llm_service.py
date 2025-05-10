import os
import json
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, AIMessage, SystemMessage

# Initialize OpenAI API key from environment variable
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def get_answer_from_llm(query: str, contexts: List[Dict[str, Any]], document_id: Optional[str] = None) -> str:
    """
    Generate an answer using LLM based on retrieved contexts from Pinecone.
    
    Args:
        query: The user's query
        contexts: List of context snippets from Pinecone with their metadata
        document_id: Optional document ID for reference
        
    Returns:
        Generated answer as a string
    """
    # Initialize the LLM
    llm = ChatOpenAI(
        model_name="gpt-3.5-turbo",  # You can use "gpt-4" for better results if available
        temperature=0.2,  # Low temperature for more factual responses
        api_key=OPENAI_API_KEY,
    )
    
    # Create the system prompt
    system_prompt = """You are a precise and accurate medical education assistant that answers questions based ONLY on the provided context.
    
    CRITICAL INSTRUCTIONS:
    1. ONLY use information explicitly stated in the provided context snippets.
    2. READ ALL CONTENT BLOCKS COMPLETELY before answering. Ensure your answer incorporates information from ALL relevant blocks.
    3. Maintain the exact hierarchy and structure shown in the document.
    4. When asked about document structure or content, provide COMPREHENSIVE information from ALL relevant sections.
    5. When answering about numbered or categorized sections, include ALL such sections found in the context.
    6. If you don't have complete information, clearly state which parts are missing.
    7. NEVER make up or infer information that isn't directly in the context.
    8. Always cite the page numbers where you found information (e.g., "According to page 3...")
    9. Be concise but complete.
    10. If the document structure is unclear from the context, acknowledge this instead of guessing.
    """
    
    # Format the context for the prompt
    formatted_context = ""
    
    # Filter contexts: only use high-relevance chunks (score >= 0.2)
    filtered_contexts = [ctx for ctx in contexts if ctx.get('score', 0) >= 0.2]
    
    # Sort filtered contexts by page number to maintain document order
    sorted_contexts = sorted(filtered_contexts, key=lambda x: x.get('page', 0))
    
    # Create a structured summary of all headings found in the document
    all_headings = []
    for ctx in sorted_contexts:
        if ctx.get('headings'):
            for heading in ctx.get('headings'):
                if heading not in all_headings:
                    all_headings.append(heading)
    
    # Add document structure overview if headings are available
    if all_headings:
        formatted_context += "DOCUMENT STRUCTURE OVERVIEW:\n"
        formatted_context += ", ".join(all_headings) + "\n\n"
        formatted_context += "-----------------------------------\n\n"
    
    # Show limited contexts (max 5) in page order with improved formatting
    # Prioritize sources with highest scores if we need to limit
    if len(sorted_contexts) > 5:
        # Take a slice with the most relevant contexts (by score)
        relevance_sorted = sorted(sorted_contexts, key=lambda x: x.get('score', 0), reverse=True)
        context_to_show = relevance_sorted[:5]
        # Resort by page to maintain document flow
        context_to_show = sorted(context_to_show, key=lambda x: x.get('page', 0))
    else:
        context_to_show = sorted_contexts
        
    # Print the amount of chunks we're using
    print(f"DEBUG: Using {len(context_to_show)} chunks out of {len(contexts)} retrieved")
    
    # Add selected contexts in page order
    for i, ctx in enumerate(context_to_show):
        # Format with clearer page and content separation
        formatted_context += f"[CONTENT BLOCK {i+1}] (Page {ctx.get('page', 'unknown')}, Score: {ctx.get('score', 0):.2f}):\n{ctx.get('text', '')}\n\n"
    
    # Create the user message with the query and context
    user_prompt = f"""
    Question: {query}
    
    Here is the ONLY context you should use for answering:
    {formatted_context}
    
    IMPORTANT GUIDELINES:
    1. Only respond based on the context above
    2. READ THROUGH ALL CONTENT BLOCKS before answering
    3. If the query asks for a list or structure of items, include ALL items found in the context
    4. Carefully maintain the exact hierarchy and structure presented in the document
    5. If information is missing about any part of the question, explicitly say so
    6. DO NOT invent or hallucinate information not present in the context
    7. Cite page numbers for your information
    8. When asked about document structure, provide a COMPLETE overview based on all available content blocks
    9. Make sure you don't stop midway - your answer should be complete and cover ALL relevant information from the context
    """
    # print(f"DEBUG: System prompt: {system_prompt}")
    # print(f"DEBUG: User prompt: {user_prompt}")
    # Create the chat messages
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]
    
    try:
        # Generate the response
        response = llm.invoke(messages)
        
        # Just return the response directly without special handling
        return response.content
    except Exception as e:
        # Fallback response in case of API errors
        return f"I couldn't generate a response due to an error: {str(e)}"
