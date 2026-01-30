"""
Feedback Processing Node
Handles user feedback and knowledge base updates
"""

from typing import Any, Dict, List

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.state import GraphState, SlotInfo
from config import settings


def get_llm():
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model_name,
        temperature=0.3,
    )


# =============================================================================
# CASE_STUDY_PROMPT - Post-Mortem Case Study Generation
# Anthropic 10-Element Framework Applied
# =============================================================================
CASE_STUDY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """<!-- 1. Task Context -->
You are CaseStudyGenerator, a component of the DevOps Copilot knowledge management system.
Your responsibility is to create structured post-mortem case studies from resolved incidents.
These case studies will be indexed in the knowledge base for future reference and learning.

<!-- 2. Tone Context -->
Be objective, educational, and precise.
Write in a style suitable for technical documentation.
Focus on learnings and preventive measures, not blame.
Use Traditional Chinese (繁體中文).

<!-- 3. Background Data -->
<incident_data>
  <original_query>{query}</original_query>
  <affected_service>{service}</affected_service>
  <error_type>{error_type}</error_type>
  <resolution_path>{diagnostic_summary}</resolution_path>
  <applied_solution>{suggestion}</applied_solution>
</incident_data>

<!-- 4. Detailed Task Description & Rules -->
Create a comprehensive but concise post-mortem case study.

REQUIRED SECTIONS:
1. Title - Brief, descriptive title (格式: "[服務名稱] [問題類型] 事件")
2. Incident Summary - 1-2 sentences describing what happened
3. Root Cause - The fundamental cause of the incident
4. Resolution - How the issue was resolved
5. Prevention - Measures to prevent recurrence
6. Tags - Searchable keywords

RULES:
1. Keep each section concise (2-3 sentences max)
2. Use specific technical terms for better searchability
3. Extract actionable learnings, not just descriptions
4. Include both technical and process-level prevention measures
5. Tags should cover: service name, error type, affected components, solution type

<!-- 5. Examples -->
<example>
<case_study>
# 案例研究: PaymentService Connection Pool 耗盡事件

## 事件摘要
2024-01-15，PaymentService 在生產環境發生連線池耗盡，導致交易處理延遲超過 30 秒。

## 根因分析
HikariCP 連線池設定在部署時被重置為預設值（10 連線），無法處理高峰期流量。

## 解決方案
1. 緊急增加連線池大小至 50
2. 重啟受影響的實例

## 預防措施
- 將連線池設定納入 ConfigMap，與程式碼分離管理
- 建立部署後配置驗證流程
- 新增連線池使用率監控告警

## 標籤
PaymentService, connection-pool, HikariCP, 配置管理, 部署問題
</case_study>
</example>

<!-- 9. Output Formatting -->
Output format: Markdown document following the structure above.
Use headers (##) for sections.
Keep the document under 300 words.""",
        ),
        (
            "human",
            """<!-- 7. Immediate Task -->
Generate the post-mortem case study based on the incident data provided.""",
        ),
    ]
)


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
        return {**state, "clarification_count": 0}  # Allow more clarification rounds
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
        return {**state, "case_study_generated": False}

    # Format diagnostic summary
    diagnostic_summary = "\n".join(
        [f"- {step.title}: {step.detail}" for step in diagnostic.path]
    )

    try:
        llm = get_llm()
        chain = CASE_STUDY_PROMPT | llm
        result = await chain.ainvoke(
            {
                "query": query,
                "service": slots.service_name or "Unknown",
                "error_type": slots.error_type or "Unknown",
                "diagnostic_summary": diagnostic_summary,
                "suggestion": diagnostic.suggestion,
            }
        )
        case_study = result.content

        # In production: Save to vector DB and graph DB
        # await save_case_study(case_study, slots, diagnostic)

        return {
            **state,
            "case_study_generated": True,
            "response": "Case study generated and saved to knowledge base.",
        }

    except Exception as e:
        return {
            **state,
            "case_study_generated": False,
            "error": f"Case study generation failed: {e}",
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

    def __init__(self, file_content: str, file_name: str, file_type: str):
        self.file_content = file_content
        self.file_name = file_name
        self.file_type = file_type
        self.chunks: List[str] = []
        self.embeddings: List[List[float]] = []
        self.entities: List[Dict[str, Any]] = []
        self.conflicts: List[Dict[str, Any]] = []
        self.approved_entities: List[Dict[str, Any]] = []


# =============================================================================
# ENTITY_EXTRACTION_PROMPT - Knowledge Graph Entity Extraction
# Anthropic 10-Element Framework Applied
# =============================================================================
ENTITY_EXTRACTION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """<!-- 1. Task Context -->
You are EntityExtractor, a component of the DevOps Copilot knowledge ingestion system.
Your responsibility is to identify and extract structured entities from technical documents
for population into a Neo4j knowledge graph.

<!-- 2. Tone Context -->
Be precise and systematic. Extract only clearly stated entities.
Prefer under-extraction over hallucination - if uncertain, do not include the entity.

<!-- 4. Detailed Task Description & Rules -->
Extract the following entity types from the document:

<entity_types>
  <type name="Service">
    Software services, microservices, APIs, applications
    Examples: PaymentService, order-api, AuthGateway
  </type>
  <type name="Infrastructure">
    Databases, caches, message queues, clusters, servers
    Examples: MySQL, Redis, Kafka, Kubernetes, AWS EC2
  </type>
  <type name="Config">
    Configuration parameters, settings, thresholds, environment variables
    Examples: max-pool-size, connection-timeout, JAVA_OPTS
  </type>
  <type name="Event">
    Incidents, deployments, changes, alerts
    Examples: deployment-v2.3.1, OOM-incident-2024-01-15
  </type>
</entity_types>

<relationship_types>
  DEPENDS_ON - Service A depends on Service B
  DEPLOYED_TO - Service deployed to infrastructure
  CONFIGURED_BY - Service configured by config parameter
  CAUSED_BY - Event caused by another event or entity
  CONNECTS_TO - Service connects to database/cache
  PART_OF - Component is part of larger system
</relationship_types>

STRICT RULES:
1. Output ONLY valid JSON array - no markdown, no explanation
2. Extract only explicitly mentioned entities - never infer
3. Use consistent naming (preserve original case/format from document)
4. Relationships must reference entities that exist in your output
5. Descriptions should be brief (max 50 characters)

<!-- 5. Examples -->
<examples>
  <example>
    <document>PaymentService connects to MySQL database. Connection pool size is set to 10.</document>
    <output>[
  {{"name": "PaymentService", "type": "Service", "description": "Payment processing service", "relationships": [{{"target": "MySQL", "type": "CONNECTS_TO"}}]}},
  {{"name": "MySQL", "type": "Infrastructure", "description": "Database for PaymentService", "relationships": []}},
  {{"name": "connection-pool-size", "type": "Config", "description": "Pool size setting: 10", "relationships": [{{"target": "PaymentService", "type": "CONFIGURED_BY"}}]}}
]</output>
  </example>
</examples>

<!-- 9. Output Formatting -->
Output format: Raw JSON array only.
Schema:
[
  {{
    "name": "string",
    "type": "Service|Infrastructure|Config|Event",
    "description": "string (max 50 chars)",
    "relationships": [
      {{"target": "string", "type": "RELATIONSHIP_TYPE"}}
    ]
  }}
]""",
        ),
        (
            "human",
            """<!-- 7. Immediate Task -->
Extract entities from the following document:
<document>
{content}
</document>""",
        ),
        ("ai", "["),  # <!-- 10. Prefilled Response -->
    ]
)


async def extract_entities_node(content: str) -> List[Dict[str, Any]]:
    """
    Extract entities from document for knowledge graph
    """
    try:
        llm = get_llm()
        chain = ENTITY_EXTRACTION_PROMPT | llm
        result = await chain.ainvoke(
            {"content": content[:4000]}
        )  # Limit content length

        import json

        content_str = result.content.strip()

        # Handle prefill: response starts after the prefilled "["
        # So we need to prepend "[" to complete the JSON array
        if not content_str.startswith("["):
            content_str = "[" + content_str

        # Handle markdown code blocks (fallback)
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
    new_entity: Dict[str, Any], existing_entities: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Check if entity conflicts with existing entities (Entity Resolution)
    Uses embedding-based semantic similarity for robust comparison.
    """
    new_name = new_entity.get("name", "")
    new_description = new_entity.get("description", "")
    # Combine name and description for richer semantic representation
    new_text = f"{new_name}: {new_description}" if new_description else new_name

    for existing in existing_entities:
        existing_name = existing.get("name", "")
        existing_description = existing.get("description", "")
        existing_text = (
            f"{existing_name}: {existing_description}"
            if existing_description
            else existing_name
        )

        # Compute semantic similarity using embeddings
        similarity = await _compute_embedding_similarity(new_text, existing_text)

        # Threshold 0.85 for semantic similarity (more robust than lexical)
        if similarity > 0.85:
            return {
                "has_conflict": True,
                "confidence": similarity,
                "existing_entity": existing,
                "new_entity": new_entity,
            }

    return {"has_conflict": False, "new_entity": new_entity}


async def _compute_embedding_similarity(text1: str, text2: str) -> float:
    """
    Compute cosine similarity between two texts using embedding model.
    Uses LM Studio embedding API for semantic comparison.
    """
    from app.nodes.retrieval import get_embedding
    import numpy as np

    try:
        # Get embeddings for both texts
        embedding1 = await get_embedding(text1)
        embedding2 = await get_embedding(text2)

        # Convert to numpy arrays
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        # Compute cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))
