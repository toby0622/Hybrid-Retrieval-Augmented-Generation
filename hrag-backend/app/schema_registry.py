"""
Schema Registry
Auto-discovers and manages domain schemas from *_schema.py files.
"""

import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class EntityType:
    """Definition of an entity type in the schema."""
    name: str
    description: str
    properties: List[str] = field(default_factory=list)
    extraction_hints: str = ""


@dataclass
class RelationType:
    """Definition of a relation type in the schema."""
    name: str
    source: str
    target: str
    description: str = ""
    properties: List[str] = field(default_factory=list)


@dataclass
class Schema:
    """Complete schema definition for a domain."""
    name: str
    display_name: str
    description: str
    entities: List[EntityType]
    relations: List[RelationType]
    
    # LLM prompting hints
    extraction_prompt: str = ""
    
    # Original module reference
    module: Optional[Any] = None

    def get_entity(self, name: str) -> Optional[EntityType]:
        """Get entity by name."""
        for e in self.entities:
            if e.name.lower() == name.lower():
                return e
        return None

    def get_primary_entity(self) -> Optional[EntityType]:
        """Get the primary entity (first in list)."""
        return self.entities[0] if self.entities else None

    def get_entity_names(self) -> List[str]:
        """Get all entity type names."""
        return [e.name for e in self.entities]

    def get_relation_names(self) -> List[str]:
        """Get all relation type names."""
        return [r.name for r in self.relations]


class SchemaRegistry:
    """
    Registry for domain schemas.
    Auto-discovers *_schema.py files and loads their definitions.
    """

    _schemas: Dict[str, Schema] = {}
    _scripts_path: Optional[Path] = None

    @classmethod
    def set_scripts_path(cls, path: Path) -> None:
        """Set the path to search for schema files."""
        cls._scripts_path = path

    @classmethod
    def discover(cls, scripts_path: Optional[Path] = None) -> List[str]:
        """
        Auto-discover *_schema.py files in the scripts directory.
        
        Returns:
            List of schema names (without _schema.py suffix)
        """
        if scripts_path:
            cls._scripts_path = scripts_path
        
        if not cls._scripts_path:
            raise ValueError("Scripts path not set. Call set_scripts_path() first.")

        schema_files = list(cls._scripts_path.glob("*_schema.py"))
        discovered = []

        for schema_file in schema_files:
            # Extract schema name: enron_schema.py -> enron
            schema_name = schema_file.stem.replace("_schema", "")
            discovered.append(schema_name)
            
            # Try to load the schema
            try:
                cls._load_schema_from_file(schema_name, schema_file)
            except Exception as e:
                print(f"[SchemaRegistry] Warning: Failed to load {schema_file}: {e}")

        return discovered

    @classmethod
    def _load_schema_from_file(cls, name: str, file_path: Path) -> Schema:
        """Load a schema from a Python file."""
        # Dynamically import the module
        spec = importlib.util.spec_from_file_location(f"{name}_schema", file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module from {file_path}")
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Extract schema information from module
        entities = []
        relations = []

        # Check for ENTITY_SCHEMAS dict (dataclass-based pattern from enron_schema.py)
        if hasattr(module, "ENTITY_SCHEMAS"):
            entity_dict = module.ENTITY_SCHEMAS
            for entity_type, schema in entity_dict.items():
                # schema is an EntitySchema dataclass
                hints = getattr(schema, "extraction_hints", [])
                if isinstance(hints, list):
                    hints = "\n".join(hints)
                entities.append(EntityType(
                    name=schema.name,
                    description=schema.description,
                    properties=schema.properties,
                    extraction_hints=hints,
                ))

        if hasattr(module, "RELATION_SCHEMAS"):
            relation_dict = module.RELATION_SCHEMAS
            for relation_type, schema in relation_dict.items():
                # schema is a RelationSchema dataclass
                # Get source/target entity names
                source = schema.from_entity.value if hasattr(schema.from_entity, "value") else str(schema.from_entity)
                target = schema.to_entity.value if hasattr(schema.to_entity, "value") else str(schema.to_entity)
                relations.append(RelationType(
                    name=schema.name,
                    source=source,
                    target=target,
                    description=schema.description,
                    properties=schema.properties,
                ))

        # Fallback: Check for EntityType enum (dict-value pattern)
        if not entities and hasattr(module, "EntityType"):
            entity_enum = module.EntityType
            for entity in entity_enum:
                # Check if it uses dict values or just string
                if isinstance(entity.value, dict):
                    entities.append(EntityType(
                        name=entity.name,
                        description=entity.value.get("description", ""),
                        properties=entity.value.get("properties", []),
                        extraction_hints=entity.value.get("extraction_hints", ""),
                    ))
                else:
                    # Simple string enum (like EntityType.PERSON = "Person")
                    entities.append(EntityType(
                        name=entity.name,
                        description=entity.value,
                        properties=[],
                        extraction_hints="",
                    ))

        if not relations and hasattr(module, "RelationType"):
            relation_enum = module.RelationType
            for relation in relation_enum:
                if isinstance(relation.value, dict):
                    relations.append(RelationType(
                        name=relation.name,
                        source=relation.value.get("source", ""),
                        target=relation.value.get("target", ""),
                        description=relation.value.get("description", ""),
                        properties=relation.value.get("properties", []),
                    ))
                else:
                    # Simple string enum
                    relations.append(RelationType(
                        name=relation.name,
                        source="",
                        target="",
                        description=relation.value,
                        properties=[],
                    ))

        # Get schema metadata
        display_name = getattr(module, "SCHEMA_NAME", name.title())
        description = getattr(module, "SCHEMA_DESCRIPTION", "")
        extraction_prompt = ""
        
        if hasattr(module, "get_schema_for_llm_prompt"):
            extraction_prompt = module.get_schema_for_llm_prompt()

        schema = Schema(
            name=name,
            display_name=display_name,
            description=description,
            entities=entities,
            relations=relations,
            extraction_prompt=extraction_prompt,
            module=module,
        )

        cls._schemas[name] = schema
        return schema

    @classmethod
    def get_schema(cls, name: str) -> Optional[Schema]:
        """Get a loaded schema by name."""
        return cls._schemas.get(name)

    @classmethod
    def get_all_schemas(cls) -> Dict[str, Schema]:
        """Get all loaded schemas."""
        return cls._schemas.copy()

    @classmethod
    def list_schemas(cls) -> List[str]:
        """List all loaded schema names."""
        return list(cls._schemas.keys())

    @classmethod
    def clear(cls) -> None:
        """Clear all loaded schemas."""
        cls._schemas = {}
