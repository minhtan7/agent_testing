"""
Enhanced study plan generator module.
Implements the improved RAG pipeline for generating structured study plans.
"""

import uuid
import json
import os
from typing import List, Dict, Any, Optional, Tuple

from sqlalchemy.orm import Session
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import Document as LangchainDocument

from app.models.study_plan import StudyPlan
from app.models.document import Document
from app.models.enums import StudyPlanStatusEnum
from app.utils.document_parser import parse_pdf_hierarchically, filter_documents_by_goal, extract_goal_keywords
from app.utils.study_plan_validator import (
    validate_checklist,
    critique_checklist,
    parse_checklist_text
)

# Example of a well-formed study plan checklist (two-shot prompt)
EXAMPLE_CHECKLIST = """1. Introduction to Patient Communication — understand the importance of establishing rapport [Core] ★★
   ↳ Prompt: How does effective communication impact patient outcomes?

2. Active Listening Techniques — grasp key methods for patient engagement [Core] ★★★
   ↳ Prompt: Which technique seems most challenging to implement?

3. Patient Concerns Exercise — practice identifying hidden concerns [Practice] ★★★★
   ↳ Prompt: What verbal cues might signal an unstated concern?

4. Medical Terminology Review — identify jargon to avoid with patients [Overview] ★★
"""

def generate_enhanced_study_plan(
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    familiarity: Optional[str] = None,
    goal: Optional[str] = None,
    db: Session = None,
    text_chunks: Optional[List[Dict[str, Any]]] = None,
    max_retries: int = 2
) -> uuid.UUID:
    """
    Generate an enhanced study plan using hierarchical document parsing,
    goal-directed filtering, and quality validation.
    
    Args:
        document_id: UUID of the document
        user_id: UUID of the user
        familiarity: User's familiarity with the subject
        goal: User's learning goal
        db: Database session
        text_chunks: Pre-processed text chunks (to avoid double processing)
        max_retries: Maximum number of retries for LLM generation
        
    Returns:
        UUID of the created study plan
    """
    # 1. Get document details
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise ValueError(f"Document with ID {document_id} not found")
    
    # 2. Create structured documents from text chunks or from storage
    structured_docs = []
    
    # If text_chunks are provided, use them directly (avoids double processing)
    if text_chunks:
        for chunk in text_chunks:
            if isinstance(chunk, dict) and chunk.get("type") == "text" and chunk.get("text"):
                # Safely get page number with a default of 0
                page = chunk.get("page", 0)
                doc = LangchainDocument(
                    page_content=chunk["text"],
                    metadata={
                        "page": page,
                        "source": document.storage_url
                    }
                )
                structured_docs.append(doc)
    else:
        # Otherwise, try to parse the document from storage
        file_path = document.storage_url
        try:
            if not file_path or not os.path.exists(file_path):
                print(f"Warning: File path does not exist: {file_path}")
            else:
                structured_docs = parse_pdf_hierarchically(file_path)
                if not structured_docs:
                    print(f"Warning: Hierarchical parsing returned no documents for {document_id}")
        except Exception as e:
            print(f"Error parsing document hierarchically: {str(e)}")
    
    # 3. Filter by goal if provided
    if goal:
        keywords = extract_goal_keywords(goal)
        filtered_docs = filter_documents_by_goal(structured_docs, keywords)
    else:
        filtered_docs = structured_docs
    
    # 4. Extract content for prompt
    outline = _create_document_outline(filtered_docs)
    
    # 5. Generate study plan with self-critique loop
    final_plan = _generate_plan_with_critique(
        outline=outline,
        familiarity=familiarity,
        goal=goal,
        max_retries=max_retries
    )
    
    # 6. Convert to structured format
    structured_plan = _create_structured_plan(final_plan)
    
    # 7. Save to database
    study_plan = StudyPlan(
        user_id=user_id,
        document_id=document_id,
        plan=structured_plan,
        title=f"Study Plan – {document.title or document.original_filename}",
        familiarity=familiarity,
        goal=goal,
        status=StudyPlanStatusEnum.draft,
    )
    
    db.add(study_plan)
    db.flush()
    db.commit()
    
    return study_plan.id

def _create_document_outline(docs: List[LangchainDocument]) -> str:
    """
    Create a structured outline from document chunks.
    
    Args:
        docs: List of document chunks
        
    Returns:
        Document outline text
    """
    # Simple approach - concatenate content with headers
    all_content = "\n\n".join(doc.page_content for doc in docs)
    
    # Limit to reasonable size
    max_chars = 12000
    if len(all_content) > max_chars:
        all_content = all_content[:max_chars] + "\n\n[Content truncated due to length...]"
    
    return all_content

def _generate_plan_with_critique(
    outline: str,
    familiarity: Optional[str] = None,
    goal: Optional[str] = None,
    max_retries: int = 2
) -> str:
    """
    Generate a study plan with self-critique loop.
    
    Args:
        outline: Document outline
        familiarity: User's familiarity
        goal: User's learning goal
        max_retries: Maximum number of retries
        
    Returns:
        Final study plan checklist
    """
    # Handle case where outline is empty or too short
    if not outline or len(outline.strip()) < 20:
        outline = "No document content was successfully extracted. This document may contain primarily images or non-textual content."
    # Format the familiarity and goal text
    familiarity_text = familiarity or "The student has no prior familiarity with this subject"
    goal_text = goal or "Master the material effectively and efficiently"
    
    # System prompt for study plan generation
    system_msg = """### ROLE  
You are an expert instructional designer.  
Create a lean, numbered checklist that an interactive tutor (Lumora) can follow and adapt on-the-fly. 
The ultimate objective for Lumora is to tutor and help users achieve what they want in a personalized way.
Return only the checklist—no headings, commentary, or metadata.

### CHECKLIST DESIGN PRINCIPLES:
  
• Maximum 15 main items (preferably less than 9 if that's sufficient); each under 20 words  
• One item ≈ one logical chunk (section, chapter, slide cluster)  
• Tag each item: Core | Practice | Overview | Optional  
• Include a ★–★★★★★ effort rating  
• Add one optional reflection prompt (≤ 15 words) per item  
• Do not prescribe exact actions—note where Lumora may slow down, skip, or dive deeper

### ADAPTATION GUIDELINES (embed implicitly):
  
• Beginners → more "Overview", glossary first, slower effort estimates  
• Intermediate → bridge refreshers to new content, balanced pace  
• Advanced → merge basic parts, mark them "Optional", faster pace  
• Exam goal → tag definitions & tables "Core"; add memory hooks  
• Practice goal → highlight case examples; tag them "Practice"  
• Big-picture goal → add synthesis prompts; emphasize connections  
• Quick overview → compress to 4–5 items; many "Overview" tags

### ITEM TEMPLATE  
<n>. <Module label> — <one-line objective> [Tag] <effort>  
   ↳ Prompt: <critical-thinking question> (optional)

### EXAMPLE FORMAT (follow this exactly)
{example}

Output the checklist ONLY - no explanations or metadata.
"""
    
    # Human prompt with outline and context
    human_msg = """### INPUTS:

• DOCUMENT – Here is the outline of the material: 
{outline}

• FAMILIARITY – {familiarity}

• GOAL – {goal}

Generate a personalized study plan formatted as a numbered checklist.
"""
    
    # Create prompt template
    plan_prompt = ChatPromptTemplate.from_messages([
        ("system", system_msg),
        ("human", human_msg),
    ])
    
    # Initialize LLM
    llm = ChatOpenAI(model="gpt-4o", temperature=0.2)
    
    # Generate initial plan
    inputs = {
        "example": EXAMPLE_CHECKLIST,
        "outline": outline,
        "familiarity": familiarity_text,
        "goal": goal_text
    }
    
    # Use invoke instead of predict (to fix deprecation warning)
    response = llm.invoke(plan_prompt.format(**inputs))
    # Extract the content from the response object
    current_plan_content = response.content
    print(f"Generated initial plan with {len(current_plan_content)} characters")
    
    # Self-critique loop
    for attempt in range(max_retries):
        # Initialize critique variable
        critique = None
        
        # Validate the current plan
        is_valid, error = validate_checklist(current_plan_content)
        if is_valid:
            # Plan passes validation, check with LLM critic
            critique = critique_checklist(current_plan_content)
            if critique == "OK":
                # Both validations pass
                return current_plan_content
        
        # If we got here, validation failed - get LLM critique
        if not critique:
            critique = critique_checklist(current_plan_content)
        
        # Revise the plan
        revision_prompt = ChatPromptTemplate.from_messages([
            ("system", system_msg),
            ("human", human_msg),
            ("assistant", current_plan_content),
            ("human", f"""Your checklist needs revision based on these issues:
{critique if critique != "OK" else error}

Please provide a revised checklist that addresses these issues.""")
        ])
        
        # Generate revised plan (use invoke instead of predict)
        response = llm.invoke(revision_prompt.format(**inputs))
        current_plan_content = response.content
        print(f"Generated revised plan (attempt {attempt+1}) with {len(current_plan_content)} characters")
    
    # Return best plan we have, even if it didn't pass all validations
    return current_plan_content

def _create_structured_plan(checklist_text: str) -> Dict[str, Any]:
    """
    Convert checklist text to structured JSON format.
    
    Args:
        checklist_text: The text of the checklist
        
    Returns:
        Structured plan as a dictionary
    """
    # Parse the checklist text
    items = parse_checklist_text(checklist_text)
    
    # Get goals from the first few checklist items
    goals = []
    if items and len(items) > 0:
        goals = [item["objective"] for item in items[:3]]
    
    # Create a weekly breakdown with the checklist
    structured_plan = {
        "goals": goals,
        "duration_weeks": 1,
        "weekly_breakdown": []
    }
    
    # Only add the breakdown if we have items
    if items:
        activities = []
        for item in items:
            activities.append(f"{item['number']}. {item['label']} — {item['objective']}")
            
        breakdown = {
            "week": 1,
            "title": "Medical Document Study Week",
            "estimated_minutes": len(items) * 30,  # Rough estimate
            "learning_objectives": [item["objective"] for item in items],
            "resources": [],
            "activities": activities,
            "assessment": "Review all items and answer reflection prompts",
            "checklist": items
        }
        structured_plan["weekly_breakdown"] = [breakdown]
    
    return structured_plan
