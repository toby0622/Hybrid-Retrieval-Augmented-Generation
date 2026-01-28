"""
Feedback Processing Node
Handles user feedback and knowledge base updates
"""

from typing import Dict, Any, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from config import settings
from app.state import GraphState, SlotInfo


def get_llm():
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key, 
        model=settings.llm_model_name,
        temperature=0.3,
    )


CASE_STUDY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are creating a post-mortem case study from a resolved incident.

## Incident Details
Query: {query}
Service: {service}
Error Type: {error_type}

## Resolution Path
{diagnostic_summary}

## Final Recommendation
{suggestion}

Create a concise case study in the following format:

# Case Study: [Brief Title]

## Incident Summary
(1-2 sentences describing what happened)

## Root Cause
(What was the fundamental cause)

## Resolution
(How it was resolved)

## Prevention
(How to prevent in future)

## Tags
(Relevant keywords for search)
"""),
    ("human", "Generate the case study.")
])


async def feedback_node(state: GraphState) -> GraphState:
    """
    Process user feedback and route accordingly
    """
    feedback = state.get("feedback")
    
    if feedback == "resolved":
        # Trigger case study generation
        return await _generate_case_study(state)
    elif feedback == "more_info":
        # Reset for more investigation
        return {
            **state,
            "clarification_count": 0  # Allow more clarification rounds
        }
    else:
        # End conversation
        return state


async def _generate_case_study(state: GraphState) -> GraphState:
    """
    Generate case study from resolved incident
    """
    slots = state.get("slots", SlotInfo())
    diagnostic = state.get("diagnostic")
    query = state.get("query", "")
    
    if not diagnostic:
        return {
            **state,
            "case_study_generated": False
        }
    
    # Format diagnostic summary
    diagnostic_summary = "\n".join([
        f"- {step.title}: {step.detail}"
        for step in diagnostic.path
    ])
    
    try:
        llm = get_llm()
        chain = CASE_STUDY_PROMPT | llm
        result = await chain.ainvoke({
            "query": query,
            "service": slots.service_name or "Unknown",
            "error_type": slots.error_type or "Unknown",
            "diagnostic_summary": diagnostic_summary,
            "suggestion": diagnostic.suggestion
        })
        case_study = result.content
        
        # In production: Save to vector DB and graph DB
        # await save_case_study(case_study, slots, diagnostic)
        
        return {
            **state,
            "case_study_generated": True,
            "response": "Case study generated and saved to knowledge base."
        }
        
    except Exception as e:
        return {
            **state,
            "case_study_generated": False,
            "error": f"Case study generation failed: {e}"
        }


def route_after_feedback(state: GraphState) -> str:
    """Route based on feedback type"""
    feedback = state.get("feedback")
    
    if feedback == "resolved":
        return "end"
    elif feedback == "more_info":
        return "slot_check"
    else:
        return "end"


# --- Knowledge Ingestion Pipeline ---

class KnowledgeIngestionState:
    """State for knowledge ingestion pipeline"""
    def __init__(
        self,
        file_content: str,
        file_name: str,
        file_type: str
    ):
        self.file_content = file_content
        self.file_name = file_name
        self.file_type = file_type
        self.chunks: List[str] = []
        self.embeddings: List[List[float]] = []
        self.entities: List[Dict[str, Any]] = []
        self.conflicts: List[Dict[str, Any]] = []
        self.approved_entities: List[Dict[str, Any]] = []


ENTITY_EXTRACTION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are extracting knowledge graph entities from a technical document.

Identify:
1. **Services/Components** - Named software services, microservices, databases
2. **Configurations** - Config parameters, settings, thresholds
3. **Events** - Incidents, deployments, changes
4. **Relationships** - How entities relate (DEPENDS_ON, DEPLOYED_TO, CAUSED_BY, etc.)

Return JSON array:
[
  {{
    "name": "EntityName",
    "type": "Service|Config|Event|Infrastructure",
    "description": "Brief description",
    "relationships": [
      {{"target": "OtherEntity", "type": "RELATIONSHIP_TYPE"}}
    ]
  }}
]

Only extract clearly stated entities, not implicit ones."""),
    ("human", "Document content:\n{content}")
])


async def extract_entities_node(content: str) -> List[Dict[str, Any]]:
    """
    Extract entities from document for knowledge graph
    """
    try:
        llm = get_llm()
        chain = ENTITY_EXTRACTION_PROMPT | llm
        result = await chain.ainvoke({"content": content[:4000]})  # Limit content length
        
        import json
        content_str = result.content.strip()
        
        # Handle markdown code blocks
        if "```" in content_str:
            content_str = content_str.split("```")[1]
            if content_str.startswith("json"):
                content_str = content_str[4:]
        
        entities = json.loads(content_str)
        return entities
        
    except Exception as e:
        print(f"Entity extraction error: {e}")
        return []


async def check_entity_conflicts(
    new_entity: Dict[str, Any],
    existing_entities: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Check if entity conflicts with existing entities (Entity Resolution)
    """
    for existing in existing_entities:
        # Simple similarity check - in production use embeddings
        name_similarity = _compute_name_similarity(
            new_entity.get("name", ""),
            existing.get("name", "")
        )
        
        if name_similarity > 0.8:
            return {
                "has_conflict": True,
                "confidence": name_similarity,
                "existing_entity": existing,
                "new_entity": new_entity
            }
    
    return {
        "has_conflict": False,
        "new_entity": new_entity
    }


def _compute_name_similarity(name1: str, name2: str) -> float:
    """Simple name similarity computation"""
    name1 = name1.lower().replace("_", " ").replace("-", " ")
    name2 = name2.lower().replace("_", " ").replace("-", " ")
    
    words1 = set(name1.split())
    words2 = set(name2.split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1 & words2
    union = words1 | words2
    
    return len(intersection) / len(union)
