"""
Skill Configuration — Anthropic-style modular skill definitions.

Each skill is a self-contained package that defines:
- Intent classification & routing
- Slot filling requirements
- LLM prompts for each pipeline stage
- Graph (Neo4j) query templates
- Vector (Qdrant) filter configuration
- Optional knowledge-graph schema
- Optional executable handler code
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field


# ──────────────────────── Sub-configurations ────────────────────────


class SlotConfig(BaseModel):
    """Defines required / optional slots and extraction examples."""

    required: List[str] = Field(default_factory=list)
    optional: List[str] = Field(default_factory=list)
    examples: Dict[str, List[str]] = Field(default_factory=dict)


class PromptConfig(BaseModel):
    """Prompt template for a pipeline stage (classification, clarification, etc.)."""

    system_identity: str = ""
    capabilities: List[str] = Field(default_factory=list)
    examples: List[Dict[str, str]] = Field(default_factory=list)


class QueryConfig(BaseModel):
    """Cypher query templates for Neo4j retrieval."""

    primary_search: str = ""
    context_search: str = ""
    fallback_search: str = ""


class EntitySchema(BaseModel):
    """Schema definition for a knowledge-graph entity type."""

    name: str
    description: str = ""
    properties: List[str] = Field(default_factory=list)
    extraction_hints: str = ""


class RelationSchema(BaseModel):
    """Schema definition for a knowledge-graph relation type."""

    name: str
    source: str
    target: str
    description: str = ""
    properties: List[str] = Field(default_factory=list)


class SkillSchemaConfig(BaseModel):
    """Inline knowledge-graph schema (replaces external *_schema.py files)."""

    entities: List[EntitySchema] = Field(default_factory=list)
    relations: List[RelationSchema] = Field(default_factory=list)
    extraction_prompt: str = ""

    def get_entity(self, name: str) -> Optional[EntitySchema]:
        for e in self.entities:
            if e.name.lower() == name.lower():
                return e
        return None

    def get_entity_names(self) -> List[str]:
        return [e.name for e in self.entities]

    def get_relation_names(self) -> List[str]:
        return [r.name for r in self.relations]

    def build_extraction_prompt(self) -> str:
        """Auto-generate an extraction prompt from schema if none provided."""
        if self.extraction_prompt:
            return self.extraction_prompt

        lines = ["Entity types and their properties:"]
        for e in self.entities:
            props = ", ".join(e.properties) if e.properties else "none"
            lines.append(f"  - {e.name}: {e.description} (properties: {props})")
            if e.extraction_hints:
                lines.append(f"    Hints: {e.extraction_hints}")

        lines.append("\nRelation types:")
        for r in self.relations:
            lines.append(f"  - {r.name}: {r.source} -> {r.target} ({r.description})")

        return "\n".join(lines)


# ──────────────────────── Main SkillConfig ────────────────────────


class SkillConfig(BaseModel):
    """
    Complete configuration for a single Skill.

    Absorbs the responsibilities of the old DomainConfig, SchemaRegistry entry,
    and SkillLoader definition into one unified model.
    """

    # ── Identity ──
    name: str
    display_name: str
    description: str = ""
    version: str = "1.0.0"

    # ── Routing ──
    routing_keywords: List[str] = Field(default_factory=list)

    # ── Intent classification ──
    intents: List[str] = Field(
        default_factory=lambda: ["question", "chat", "end"]
    )
    intent_keywords: Dict[str, List[str]] = Field(default_factory=dict)

    # ── Slot filling ──
    slots: SlotConfig = Field(default_factory=SlotConfig)

    # ── Prompts (keyed by pipeline stage) ──
    prompts: Dict[str, PromptConfig] = Field(default_factory=dict)

    # ── Retrieval ──
    graph_queries: QueryConfig = Field(default_factory=QueryConfig)
    vector_filter_fields: List[str] = Field(default_factory=list)

    # ── Knowledge-graph schema (optional, inline) ──
    # Named kg_schema to avoid shadowing BaseModel.schema()
    kg_schema: Optional[SkillSchemaConfig] = None

    # ── Response ──
    response_language: str = "zh-TW"

    # ── File paths (populated by SkillRegistry during discovery) ──
    skill_dir: Optional[str] = None
    handler_module: Optional[str] = None
    skill_md_path: Optional[str] = None

    # ── Convenience accessors (backward-compat with old DomainConfig API) ──

    @property
    def classification_prompt(self) -> PromptConfig:
        return self.prompts.get("classification", PromptConfig())

    @property
    def clarification_prompt(self) -> PromptConfig:
        return self.prompts.get("clarification", PromptConfig())

    @property
    def reasoning_prompt(self) -> PromptConfig:
        return self.prompts.get("reasoning", PromptConfig())

    @property
    def chat_prompt(self) -> PromptConfig:
        return self.prompts.get("chat", PromptConfig())

    # ── Factory ──

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "SkillConfig":
        """Load a SkillConfig from a skill.yaml file."""
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return cls._from_dict(data, skill_dir=str(yaml_path.parent))

    @classmethod
    def _from_dict(
        cls, data: Dict[str, Any], skill_dir: Optional[str] = None
    ) -> "SkillConfig":
        """Parse raw dict (from YAML) into a SkillConfig."""

        # Parse slots
        slots_data = data.get("slots", {})
        slots = SlotConfig(
            required=slots_data.get("required", []),
            optional=slots_data.get("optional", []),
            examples=slots_data.get("examples", {}),
        )

        # Parse prompts dict
        prompts: Dict[str, PromptConfig] = {}
        prompts_data = data.get("prompts", {})
        for stage, prompt_data in prompts_data.items():
            if isinstance(prompt_data, dict):
                prompts[stage] = PromptConfig(
                    system_identity=prompt_data.get("system_identity", ""),
                    capabilities=prompt_data.get("capabilities", []),
                    examples=prompt_data.get("examples", []),
                )

        # Parse graph queries
        queries_data = data.get("graph_queries", {})
        graph_queries = QueryConfig(
            primary_search=queries_data.get("primary_search", ""),
            context_search=queries_data.get("context_search", ""),
            fallback_search=queries_data.get("fallback_search", ""),
        )

        # Parse inline schema
        schema_config = None
        schema_data = data.get("schema")
        if schema_data and isinstance(schema_data, dict):
            entities = []
            for e in schema_data.get("entities", []):
                entities.append(
                    EntitySchema(
                        name=e.get("name", ""),
                        description=e.get("description", ""),
                        properties=e.get("properties", []),
                        extraction_hints=e.get("extraction_hints", ""),
                    )
                )
            relations = []
            for r in schema_data.get("relations", []):
                relations.append(
                    RelationSchema(
                        name=r.get("name", ""),
                        source=r.get("source", ""),
                        target=r.get("target", ""),
                        description=r.get("description", ""),
                        properties=r.get("properties", []),
                    )
                )
            schema_config = SkillSchemaConfig(
                entities=entities,
                relations=relations,
                extraction_prompt=schema_data.get("extraction_prompt", ""),
            )

        # Detect handler.py and SKILL.md
        handler_module = None
        skill_md_path = None
        if skill_dir:
            handler_path = Path(skill_dir) / "handler.py"
            if handler_path.exists():
                handler_module = str(handler_path)
            md_path = Path(skill_dir) / "SKILL.md"
            if md_path.exists():
                skill_md_path = str(md_path)

        return cls(
            name=data.get("name", "unknown"),
            display_name=data.get("display_name", "Unknown Skill"),
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            routing_keywords=data.get("routing_keywords", []),
            intents=data.get("intents", ["question", "chat", "end"]),
            intent_keywords=data.get("intent_keywords", {}),
            slots=slots,
            prompts=prompts,
            graph_queries=graph_queries,
            vector_filter_fields=data.get("vector_filter_fields", []),
            kg_schema=schema_config,
            response_language=data.get("response_language", "zh-TW"),
            skill_dir=skill_dir,
            handler_module=handler_module,
            skill_md_path=skill_md_path,
        )
