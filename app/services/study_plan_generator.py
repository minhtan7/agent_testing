"""
Study plan generation service using OpenAI (LangChain ≥ 0.3).
Switched to `load_summarize_chain(chain_type="map_reduce")`, which cleanly
handles custom map/combine prompts without forbidden extras and is stable
despite recent deprecations.
"""
import json
import os
import re
import uuid
from typing import List, Dict, Any

import multiprocessing as mp

from app.models.study_plan_section import StudyPlanSection  # <- Added to prevent leaked semaphore warning

try:
    mp.set_start_method("spawn", force=True)
except RuntimeError:
    # If the context is already set, ignore.
    pass

from dotenv import load_dotenv
from sqlalchemy.orm import Session

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import Document as LangchainDocument
from langchain.chains.summarize import load_summarize_chain

from app.models.study_plan import StudyPlan
from app.models.enums import StudyPlanStatusEnum

load_dotenv()

def generate_study_plan(
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    text_chunks: List[Dict[str, Any]],
    db: Session,
    user_prefs: str | None = None,
    familiarity: str | None = None,
    goal: str | None = None
) -> uuid.UUID:
    """Generate a study plan from PDF chunks and persist it."""

    # Print information about chunks and images for debugging
    print(f"Processing document with {len(text_chunks)} chunks, including {len([chunk for chunk in text_chunks if chunk.get('type') == 'image'])} images")
    
    # Print details about any images found
    image_chunks = [chunk for chunk in text_chunks if chunk.get('type') == 'image']
    for i, image in enumerate(image_chunks):
        print(f"Image {i+1}: {image.get('path')}")
    
    # 0️⃣ Convert chunks → LangChain documents
    docs: List[LangchainDocument] = []
    for chunk in text_chunks:
        if chunk.get("type") == "text" and chunk.get("text"):
            docs.append(
                LangchainDocument(
                    page_content=chunk["text"].strip(),
                    metadata={"page": chunk.get("page")},
                )
            )

    if not docs:
        raise ValueError("No text content found in the document")

    # 1️⃣ Initialise LLM
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set")

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3, openai_api_key=openai_api_key)

    # 2️⃣ Summarise via Map‑Reduce to get a compact outline
    map_prompt = ChatPromptTemplate.from_messages(
        [
           ("system", "You are an expert teacher summarising materials."),
            ("human", "Summarise the following passage in 2‑4 sentences and use bullet points where helpful.\n\n{context}"),
        ]
    )

    combine_prompt = ChatPromptTemplate.from_template(
        "Combine the summaries below into a hierarchical outline (top‑level bullets for chapters, indented sub‑bullets for main ideas).\n\n{context}"
    )

    outline_chain = load_summarize_chain(
        llm,
        chain_type="map_reduce",
        map_prompt=map_prompt,
        combine_prompt=combine_prompt,
        token_max=8_000,  # forwarded internally
        map_reduce_document_variable_name="context",
        combine_document_variable_name="context",
    )

    # use .invoke instead of deprecated .run
    outline: str = outline_chain.invoke({"input_documents": docs})["output_text"]

    print(f"Outline: {outline}")

    # Generate the full study plan using the OpenAI API
    # Strictly follow the PM's prompt format
    system_msg = (
        "### ROLE  \n"
        "You are an expert instructional designer.  \n"
        "Create a lean, numbered checklist that an interactive tutor (Lumora) can follow and adapt on-the-fly. "
        "The ultimate objective for Lumora is to tutor and help users achieve what they want in a personalized way. \n"
        "Return only the checklist—no headings, commentary, or metadata.\n\n"
        "### INPUTS (supplied to you):\n\n"
        "• {document} – e.g., research article, clinical guideline, textbook chapter, full book, Study Protocol or Grant Proposal, "
        "Case Report / Case Series, Position Statement or Consensus Statement, White Paper / Industry Report, Technical Manual or User Guide, "
        "Standard Operating Procedure (SOP), Government Health Policy Brief, Lecture Slide Deck (exported as PDF), Conference Abstract Booklet / "
        "Proceedings, Workbook or Exercise Sheets, Quick-Reference Pocket Guide / Cheat-Sheet, Thesis or Dissertation…  \n"
        "• {familiarity} – learner's self-described familiarity background \n"
        "• {goal} – learner's desired outcome \n\n"
        "### CHECKLIST DESIGN PRINCIPLES:\n\n"
        "• Maximum 15 main items (preferably less than 9 if that's sufficient, you decide the optimal number of items); each under 20 words  \n"
        "• One item ≈ one logical chunk (section, chapter, slide cluster)  \n"
        "• Tag each item: Core | Practice | Overview | Optional  \n"
        "• Include a ★–★★★★★ effort rating  \n"
        "• Add one optional reflection prompt (≤ 15 words) per item  \n"
        "• Do not prescribe exact actions—note where Lumora may slow down, skip, or dive deeper\n\n"
        "### ADAPTATION GUIDELINES (embed implicitly):\n\n"
        "• Beginners → more \"Overview\", glossary first, slower effort estimates  \n"
        "• Intermediate → bridge refreshers to new content, balanced pace  \n"
        "• Advanced → merge basic parts, mark them \"Optional\", faster pace  \n"
        "• Exam goal → tag definitions & tables \"Core\"; add memory hooks  \n"
        "• Practice goal → highlight case examples; tag them \"Practice\"  \n"
        "• Big-picture goal → add synthesis prompts; emphasize connections  \n"
        "• Quick overview → compress to 4–5 items; many \"Overview\" tags\n\n"
        "### ITEM TEMPLATE  \n"
        "<n>. <Module label> — <one-line objective> [Tag] <effort>  \n"
        "   ↳ Prompt: <critical-thinking question> (optional)\n\n"
        "### STYLE EXAMPLE (for reference only—omit in your output)  \n"
        "1. Objectives & Key Questions — map big ideas [Overview] ★  \n"
        "   ↳ Prompt: Why is this topic timely?  \n"
        "2. Section 1: Mechanisms — grasp core process [Core] ★★  \n"
        "   ↳ Prompt: Which step is rate-limiting?  \n"
        "3. Figures & Tables — extract diagnostic cut-offs [Practice] ★  \n"
        "4. Advanced Debate — scan controversies (Optional) ★  \n"
        "5. Wrap-Up — list three takeaways [Core] ★\n\n"
        "### REMINDERS  \n"
        "• Use plain numbers (1., 2., 3.…).  \n"
        "• Start every line with an action verb (\"Explore…\", \"Grasp…\", \"Describe…\", \"Summarize…\", \"Critique…\").  \n"
        "• Do not mention inputs or these instructions explicitly; weave adaptations implicitly.  \n"
        "• Output the checklist only.\n\n"
        "Afterwards convert the checklist to a simple JSON format for storage.\n"
    )

    # Format the variables to match what the PM's prompt expects
    # Use provided familiarity or default to no familiarity
    if familiarity:
        familiarity_text = familiarity.strip()
    else:
        familiarity_text = "The student has no familiarity with the subject"
    
    # Use provided goal or default to mastery
    if goal:
        goal_text = goal.strip()
    else:
        goal_text = "Master the material effectively and efficiently"
    
    # Use the exact prompt format required by PM
    plan_prompt = ChatPromptTemplate.from_messages([
        ("system", system_msg),
        (
            "human",
            "### INPUTS:\n\n"
            "• {document} – Here is the outline of the material: {outline}\n\n"
            "• {familiarity} – {familiarity_text}\n\n"
            "• {goal} – {goal_text}\n\n"
            "Generate a personalized study plan formatted as a numbered checklist."
        ),
    ])

    # Include all required variables for the prompt with user-provided data
    inputs = {
        "document": "Medical document with outline",
        "outline": outline,
        "familiarity": "Learner's familiarity",
        "familiarity_text": familiarity_text,
        "goal": "Learner's goal",
        "goal_text": goal_text
    }
    
    # Print the formatted prompt for debugging
    print("\n==== STUDY PLAN PROMPT ====")
    print("TESTING MODE - OpenAI API calls disabled")
    print("==== END OF PROMPT ====")
    
    # study_plan_result = (plan_prompt | llm).invoke(inputs).content  # <- Invoke with inputs - COMMENTED OUT FOR TESTING
    
    # Print image count for testing
    image_count = len([chunk for chunk in text_chunks if chunk.get("type") == "image"])
    print(f"Testing mode: Found {image_count} images in document")

    # 4️⃣ Parse JSON (fallback to raw text)
    try:
        study_plan_json = json.loads(study_plan_result)
    except json.JSONDecodeError:
        code_block = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", study_plan_result)
        if code_block:
            try:
                study_plan_json = json.loads(code_block.group(1))
            except json.JSONDecodeError:
                study_plan_json = {"raw_response": study_plan_result}
        else:
            study_plan_json = {"raw_response": study_plan_result}

    # 5️⃣ Process the checklist to our database format
    # 
    # The LLM will return a checklist in text format, but we need to store it as structured JSON
    # in our database. The structured_plan converts the text checklist into a standard format
    # with fields that match our application needs (goals, weekly breakdown, etc.)
    # This structured format makes it easier to display and work with in the frontend.
    
    # Convert response to a structured plan
    structured_plan = {}
    
    # Parse checklist items from the text response if needed
    if isinstance(study_plan_json, str):
        # If we got raw text instead of JSON, extract checklist items
        
        checklist_items = []
        # Regular expression to match checklist items with the specified format
        pattern = r'(\d+)\. ([^—]+) — ([^\[]+) \[(Core|Practice|Overview|Optional)\] (★+)(?:\s*↳ Prompt: ([^\n]+))?'
        
        matches = re.finditer(pattern, study_plan_result)
        for match in matches:
            number = int(match.group(1))
            label = match.group(2).strip()
            objective = match.group(3).strip()
            tag = match.group(4)
            stars = len(match.group(5))  # Count number of star characters
            prompt = match.group(6).strip() if match.group(6) else ""
            
            checklist_items.append({
                "number": number,
                "label": label,
                "objective": objective,
                "tag": tag,
                "effort": stars,
                "prompt": prompt
            })
        
        # Create a basic structured plan
        structured_plan = {
            "goals": ["Master the medical material effectively"],
            "duration_weeks": 1,
            "weekly_breakdown": [
                {
                    "week": 1,
                    "title": "Medical Document Study Week",
                    "estimated_minutes": len(checklist_items) * 30,  # rough estimate
                    "learning_objectives": [item["objective"] for item in checklist_items],
                    "resources": [],
                    "activities": [],
                    "assessment": "Review all items and answer reflection prompts",
                    "checklist": checklist_items
                }
            ]
        }
    else:
        # If we already have JSON, ensure it has the checklist property
        structured_plan = study_plan_json
        if "weekly_breakdown" in structured_plan:
            for week in structured_plan["weekly_breakdown"]:
                if "checklist" not in week:
                    week["checklist"] = []
    
    title_default = "Document Study Plan"
    if isinstance(structured_plan.get("goals"), list) and structured_plan["goals"]:
        title_default = f"Study Plan – {structured_plan['goals'][0][:60]}"

    print(f"Study plan: {structured_plan}")
    study_plan = StudyPlan(
        user_id=user_id,
        document_id=document_id,
        plan=structured_plan,
        title=title_default,
        familiarity=familiarity,
        goal=goal,
        status=StudyPlanStatusEnum.draft,
    )

    db.add(study_plan)
    db.flush()  # get study_plan.id before inserting children

    sections_payload = study_plan_json.get("weekly_breakdown", [])
    # for section in sections_payload:
    #     db.add(
    #         StudyPlanSection(
    #             study_plan_id=study_plan.id,
    #             title=section["title"],
    #             description=", ".join(section["learning_objectives"]),
    #             order=section["week"],
    #             estimated_minutes=section.get("estimated_minutes"),
    #             content=section,  # full JSON for flexibility
    #         )
    #     )

    db.commit()
    db.refresh(study_plan)
    return study_plan.id
