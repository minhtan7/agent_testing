"""
Study plan validator module.
Provides functions to validate and critique study plans
to ensure they meet the quality standards.
"""

import re
from typing import Dict, List, Any, Tuple, Optional
import pydantic
from langchain_openai import ChatOpenAI

# Model for a checklist item
class ChecklistItem(pydantic.BaseModel):
    number: int
    label: str
    objective: str
    tag: str
    effort: int
    prompt: Optional[str] = None
    
    @pydantic.validator('tag')
    def tag_must_be_valid(cls, v):
        valid_tags = {'Core', 'Practice', 'Overview', 'Optional'}
        if v not in valid_tags:
            raise ValueError(f'Tag must be one of {valid_tags}')
        return v
    
    @pydantic.validator('effort')
    def effort_must_be_valid(cls, v):
        if not 1 <= v <= 5:
            raise ValueError('Effort must be between 1 and 5 stars')
        return v

# Model for a complete checklist
class Checklist(pydantic.BaseModel):
    items: List[ChecklistItem]
    
    @pydantic.validator('items')
    def validate_items(cls, items):
        if len(items) > 15:
            raise ValueError('Checklist should have at most 15 items')
        
        if not any(item.tag == 'Practice' for item in items):
            raise ValueError('Checklist must include at least one Practice item')
            
        if not any(item.prompt for item in items):
            raise ValueError('Checklist must include at least one reflection prompt')
            
        return items

def parse_checklist_text(text: str) -> List[Dict[str, Any]]:
    """
    Parse a text checklist into structured data.
    
    Args:
        text: Checklist text with numbered items
        
    Returns:
        List of dictionaries representing checklist items
    """
    # Regular expression to extract checklist items
    # Format: <number>. <label> — <objective> [Tag] <stars>
    # Optional: ↳ Prompt: <prompt text>
    pattern = r'(\d+)\.\s+([^—]+)—\s+([^\[]+)\s+\[(Core|Practice|Overview|Optional)\]\s+(★+)(?:\s*↳\s*Prompt:\s*([^\n]+))?'
    
    matches = re.finditer(pattern, text, re.MULTILINE)
    
    items = []
    for match in matches:
        number = int(match.group(1))
        label = match.group(2).strip()
        objective = match.group(3).strip()
        tag = match.group(4)
        stars = len(match.group(5))  # Count number of star characters
        prompt = match.group(6).strip() if match.group(6) else None
        
        items.append({
            "number": number,
            "label": label,
            "objective": objective,
            "tag": tag,
            "effort": stars,
            "prompt": prompt
        })
    
    return items

def validate_checklist(text: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a checklist against quality criteria.
    
    Args:
        text: Checklist text
        
    Returns:
        (is_valid, error_message)
    """
    try:
        # Parse text to structured format
        items = parse_checklist_text(text)
        
        if not items:
            return False, "Failed to parse checklist format"
        
        # Validate using pydantic model
        checklist = Checklist(items=items)
        return True, None
        
    except Exception as e:
        return False, str(e)

# LLM-based critic for study plans
CRITIC_PROMPT = """You are a QA agent for study plan checklists. Check that:
1. ≤15 items; each formatted as 'n. Label — objective [Tag] ★…'
2. Tags must be one of: Core, Practice, Overview, Optional
3. At least one Practice item is included
4. At least one reflection prompt is included (line starting with '↳ Prompt:')
5. All efforts are represented by 1-5 stars (★)

Return "OK" if all criteria are met, or list all deviations.

CHECKLIST:
{checklist}
"""

def critique_checklist(checklist_text: str, model: str = "gpt-4o-mini") -> str:
    """
    Use LLM to critique a checklist for quality and format.
    
    Args:
        checklist_text: The checklist to critique
        model: LLM model to use
        
    Returns:
        Critique results - "OK" or list of issues
    """
    llm = ChatOpenAI(model=model, temperature=0)
    # Use invoke instead of predict to fix deprecation warning
    response = llm.invoke(CRITIC_PROMPT.format(checklist=checklist_text))
    # Extract content from the response object
    result = response.content if hasattr(response, 'content') else str(response)
    return result
