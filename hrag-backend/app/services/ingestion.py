import uuid as uuid_mod
from dataclasses import dataclass, field
from typing import Any, Dict, List

from app.core.config import settings
from app.core.db import get_neo4j_driver, get_qdrant_client
from app.core.logger import logger
from app.core.utils import parse_llm_json, validate_neo4j_label
from app.llm_factory import get_embedding, get_llm
from app.skill_registry import SkillRegistry, list_available_skills, switch_skill
from langchain_core.prompts import ChatPromptTemplate
from qdrant_client.models import Distance, PointStruct, VectorParams


@dataclass
class ExtractedEntity:
    name: str
    type: str
    properties: Dict[str, Any] = field(default_factory=dict)
    relationships: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class IngestResult:
    success: bool
    skill: str
    entities_created: int
    relations_created: int
    vectors_created: int
    errors: List[str] = field(default_factory=list)


def _build_extraction_prompt(schema) -> ChatPromptTemplate:
    """Build entity extraction prompt from a SkillSchemaConfig."""
    entity_types_xml = "<entity_types>\n"
    for entity in schema.entities:
        props = (
            ", ".join(entity.properties) if entity.properties else "name, description"
        )
        entity_types_xml += f'  <type name="{entity.name}">\n'
        entity_types_xml += f"    Description: {entity.description}\n"
        entity_types_xml += f"    Properties: {props}\n"
        if entity.extraction_hints:
            entity_types_xml += f"    Hints: {entity.extraction_hints}\n"
        entity_types_xml += "  </type>\n"
    entity_types_xml += "</entity_types>"

    relation_types_xml = "<relationship_types>\n"
    for rel in schema.relations:
        relation_types_xml += (
            f"  {rel.name} - (:{rel.source})-[:{rel.name}]->(:{rel.target})"
        )
        if rel.description:
            relation_types_xml += f" - {rel.description}"
        relation_types_xml += "\n"
    relation_types_xml += "</relationship_types>"

    entity_names = " | ".join([e.name for e in schema.entities])
    relation_names = " | ".join([r.name for r in schema.relations])

    display_name = getattr(schema, "display_name", "this skill")

    system_prompt = f"""<!-- 1. Task Context -->
You are EntityExtractor for the {display_name} skill.
Your task is to extract structured entities and relationships from documents.

<!-- 2. Tone Context -->
Be precise, systematic, and conservative. Only extract entities that are explicitly mentioned.
Never infer or assume relationships that are not directly stated in the text.

<!-- 3. Background Data -->
{entity_types_xml}

{relation_types_xml}

<!-- 4. Detailed Task Description & Rules -->
RULES:
1. Output ONLY valid JSON array - no markdown, no explanation
2. Extract only explicitly mentioned entities
3. Use entity types from the schema: {entity_names}
4. Use relationship types from the schema: {relation_names}
5. Properties should match the schema definition
6. If no entities are found, return an empty array []

<!-- 5. Examples -->
<examples>
  <example>
    <input>The Auth-Service depends on Redis for session caching and connects to PostgreSQL.</input>
    <output>[
      {{"name": "Auth-Service", "type": "Service", "properties": {{}}, "relationships": [{{"target": "Redis", "type": "DEPENDS_ON"}}, {{"target": "PostgreSQL", "type": "CONNECTS_TO"}}]}},
      {{"name": "Redis", "type": "Service", "properties": {{"purpose": "session caching"}}, "relationships": []}},
      {{"name": "PostgreSQL", "type": "Database", "properties": {{}}, "relationships": []}}
    ]</output>
  </example>
</examples>

<!-- 9. Output Formatting -->
OUTPUT FORMAT:
[
  {{
    "name": "entity name",
    "type": "{entity_names}",
    "properties": {{"key": "value"}},
    "relationships": [
      {{"target": "other entity name", "type": "{relation_names}"}}
    ]
  }}
]"""

    return ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "<document>\n{content}\n</document>"),
            ("ai", "["),
        ]
    )


async def extract_entities_with_schema(content: str, schema) -> List[ExtractedEntity]:

    llm = get_llm()
    prompt = _build_extraction_prompt(schema)
    chain = prompt | llm

    try:
        result = await chain.ainvoke({"content": content[:6000]})
        content_str = result.content.strip()

        entities_data = parse_llm_json(content_str, fallback_regex=False, prefix="[")
        entities = []
        if entities_data and isinstance(entities_data, list):
            for e in entities_data:
                entities.append(
                    ExtractedEntity(
                        name=e.get("name", "Unknown"),
                        type=e.get("type", "Unknown"),
                        properties=e.get("properties", {}),
                        relationships=e.get("relationships", []),
                    )
                )

        logger.info(f"Extracted {len(entities)} entities")
        return entities

    except Exception as e:
        logger.error(f"Entity extraction error: {e}")
        return []


async def write_entities_to_neo4j(entities: List[ExtractedEntity]) -> tuple[int, int]:
    nodes_created = 0
    rels_created = 0

    driver = get_neo4j_driver()

    try:
        async with driver.session() as session:
            for entity in entities:
                # Validate label to prevent Cypher injection
                try:
                    safe_label = validate_neo4j_label(entity.type)
                except ValueError as label_err:
                    logger.warning(f"Skipping entity with invalid label: {label_err}")
                    continue

                props = {"name": entity.name, **entity.properties}
                props_str = ", ".join([f"{k}: ${k}" for k in props.keys()])

                query = f"""
                MERGE (n:{safe_label} {{name: $name}})
                SET n += {{{props_str}}}
                RETURN n
                """

                await session.run(query, **props)
                nodes_created += 1

            for entity in entities:
                for rel in entity.relationships:
                    target_name = rel.get("target")
                    rel_type = rel.get("type")

                    if target_name and rel_type:
                        target_entity = next(
                            (e for e in entities if e.name == target_name), None
                        )
                        target_type = target_entity.type if target_entity else "Entity"

                        # Validate labels to prevent injection
                        try:
                            safe_source_label = validate_neo4j_label(entity.type)
                            safe_target_label = validate_neo4j_label(target_type)
                            safe_rel_type = validate_neo4j_label(rel_type)
                        except ValueError as label_err:
                            logger.warning(f"Skipping relationship with invalid label: {label_err}")
                            continue

                        query = f"""
                        MATCH (a:{safe_source_label} {{name: $source_name}})
                        MATCH (b:{safe_target_label} {{name: $target_name}})
                        MERGE (a)-[r:{safe_rel_type}]->(b)
                        RETURN r
                        """

                        try:
                            await session.run(
                                query, source_name=entity.name, target_name=target_name
                            )
                            rels_created += 1
                        except Exception as rel_err:
                            logger.error(f"Relation error: {rel_err}")

    except Exception as e:
        logger.error(f"Neo4j write error: {e}")
        raise e
        # We don't close the shared Sync driver here, it's managed by db.py

    return nodes_created, rels_created


async def write_document_to_qdrant(
    content: str, filename: str, skill: str, doc_type: str = "document"
) -> int:
    client = get_qdrant_client()

    collections = client.get_collections()
    collection_names = [c.name for c in collections.collections]

    if settings.qdrant_collection not in collection_names:

        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=settings.embedding_dim, distance=Distance.COSINE),
        )

    chunks = _chunk_document(content)
    points = []

    for i, chunk in enumerate(chunks):
        embed_text = f"{filename}\n\n{chunk}"
        embedding = await get_embedding(embed_text)

        point_id = str(uuid_mod.uuid4())
        points.append(
            PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "title": filename,
                    "content": chunk,
                    "doc_type": doc_type,
                    "skill": skill,
                    "chunk_index": i,
                },
            )
        )

    if points:
        client.upsert(collection_name=settings.qdrant_collection, points=points)

    logger.info(f"Qdrant: {len(points)} vectors")
    return len(points)


def _chunk_document(
    content: str, max_chunk_size: int = 1000, chunk_overlap: int = 200
) -> List[str]:
    """Split document into chunks with configurable overlap."""
    paragraphs = content.split("\n\n")

    chunks = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current_chunk) + len(para) < max_chunk_size:
            current_chunk += para + "\n\n"
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
                # Keep overlap from end of previous chunk
                if chunk_overlap > 0:
                    overlap_text = current_chunk.strip()[-chunk_overlap:]
                    current_chunk = overlap_text + "\n\n" + para + "\n\n"
                else:
                    current_chunk = para + "\n\n"
            else:
                current_chunk = para + "\n\n"

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks if chunks else [content]


async def detect_skill_from_content(content: str) -> str:
    """Detect the most appropriate skill for the given content."""
    available_skills = list_available_skills()

    if not available_skills:
        return "unknown"

    if len(available_skills) == 1:
        return available_skills[0]

    from app.nodes.input_guard import _detect_skill_async

    detected = await _detect_skill_async(content[:1000])

    return detected or available_skills[0]


async def ingest_document(
    content: str, filename: str, doc_type: str = "document"
) -> IngestResult:
    errors = []

    skill_name = await detect_skill_from_content(content)
    logger.info(f"Detected skill: {skill_name}")

    switch_skill(skill_name)

    skill_config = SkillRegistry.get_skill(skill_name)
    schema = skill_config.kg_schema if skill_config else None

    entities = []
    nodes_created = 0
    rels_created = 0

    if schema:
        entities = await extract_entities_with_schema(content, schema)

        if entities:
            try:
                nodes_created, rels_created = await write_entities_to_neo4j(entities)
            except Exception as e:
                logger.error(f"Neo4j write error: {e}")
                errors.append(f"Neo4j write error: {e}")
    else:
        logger.warning(
            f"No schema found for skill {skill_name}, skipping entity extraction"
        )

    vectors_created = 0
    try:
        vectors_created = await write_document_to_qdrant(
            content, filename, skill_name, doc_type
        )
    except Exception as e:
        logger.error(f"Qdrant write error: {e}")
        errors.append(f"Qdrant write error: {e}")

    return IngestResult(
        success=len(errors) == 0,
        skill=skill_name,
        entities_created=nodes_created,
        relations_created=rels_created,
        vectors_created=vectors_created,
        errors=errors,
    )
