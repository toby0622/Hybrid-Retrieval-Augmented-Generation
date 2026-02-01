import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class EntityType:
    name: str
    description: str
    properties: List[str] = field(default_factory=list)
    extraction_hints: str = ""


@dataclass
class RelationType:
    name: str
    source: str
    target: str
    description: str = ""
    properties: List[str] = field(default_factory=list)


@dataclass
class Schema:
    name: str
    display_name: str
    description: str
    entities: List[EntityType]
    relations: List[RelationType]

    extraction_prompt: str = ""

    module: Optional[Any] = None

    def get_entity(self, name: str) -> Optional[EntityType]:
        for e in self.entities:
            if e.name.lower() == name.lower():
                return e
        return None

    def get_primary_entity(self) -> Optional[EntityType]:
        return self.entities[0] if self.entities else None

    def get_entity_names(self) -> List[str]:
        return [e.name for e in self.entities]

    def get_relation_names(self) -> List[str]:
        return [r.name for r in self.relations]


class SchemaRegistry:

    _schemas: Dict[str, Schema] = {}
    _scripts_path: Optional[Path] = None

    @classmethod
    def set_scripts_path(cls, path: Path) -> None:
        cls._scripts_path = path

    @classmethod
    def discover(cls, scripts_path: Optional[Path] = None) -> List[str]:
        if scripts_path:
            cls._scripts_path = scripts_path

        if not cls._scripts_path:
            raise ValueError("Scripts path not set. Call set_scripts_path() first.")

        schema_files = list(cls._scripts_path.glob("*_schema.py"))
        discovered = []

        for schema_file in schema_files:
            schema_name = schema_file.stem.replace("_schema", "")
            discovered.append(schema_name)

            try:
                cls._load_schema_from_file(schema_name, schema_file)
            except Exception as e:
                print(f"[SchemaRegistry] Warning: Failed to load {schema_file}: {e}")

        return discovered

    @classmethod
    def _load_schema_from_file(cls, name: str, file_path: Path) -> Schema:
        spec = importlib.util.spec_from_file_location(f"{name}_schema", file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module from {file_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        entities = []
        relations = []

        if hasattr(module, "ENTITY_SCHEMAS"):
            entity_dict = module.ENTITY_SCHEMAS
            for entity_type, schema in entity_dict.items():
                hints = getattr(schema, "extraction_hints", [])
                if isinstance(hints, list):
                    hints = "\n".join(hints)
                entities.append(
                    EntityType(
                        name=schema.name,
                        description=schema.description,
                        properties=schema.properties,
                        extraction_hints=hints,
                    )
                )

        if hasattr(module, "RELATION_SCHEMAS"):
            relation_data = module.RELATION_SCHEMAS

            if isinstance(relation_data, dict):
                for relation_type, schema in relation_data.items():
                    source = (
                        schema.from_entity.value
                        if hasattr(schema.from_entity, "value")
                        else str(schema.from_entity)
                    )
                    target = (
                        schema.to_entity.value
                        if hasattr(schema.to_entity, "value")
                        else str(schema.to_entity)
                    )
                    relations.append(
                        RelationType(
                            name=schema.name,
                            source=source,
                            target=target,
                            description=schema.description,
                            properties=schema.properties,
                        )
                    )

            elif isinstance(relation_data, list):
                for schema in relation_data:
                    relations.append(
                        RelationType(
                            name=schema.name,
                            source=schema.source,
                            target=schema.target,
                            description=schema.description,
                            properties=getattr(schema, "properties", []),
                        )
                    )

        if not entities and hasattr(module, "EntityType"):
            entity_enum = module.EntityType
            for entity in entity_enum:
                if isinstance(entity.value, dict):
                    entities.append(
                        EntityType(
                            name=entity.name,
                            description=entity.value.get("description", ""),
                            properties=entity.value.get("properties", []),
                            extraction_hints=entity.value.get("extraction_hints", ""),
                        )
                    )
                else:
                    entities.append(
                        EntityType(
                            name=entity.name,
                            description=entity.value,
                            properties=[],
                            extraction_hints="",
                        )
                    )

        if not relations and hasattr(module, "RelationType"):
            relation_enum = module.RelationType
            for relation in relation_enum:
                if isinstance(relation.value, dict):
                    relations.append(
                        RelationType(
                            name=relation.name,
                            source=relation.value.get("source", ""),
                            target=relation.value.get("target", ""),
                            description=relation.value.get("description", ""),
                            properties=relation.value.get("properties", []),
                        )
                    )
                else:
                    relations.append(
                        RelationType(
                            name=relation.name,
                            source="",
                            target="",
                            description=relation.value,
                            properties=[],
                        )
                    )

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
        return cls._schemas.get(name)

    @classmethod
    def get_all_schemas(cls) -> Dict[str, Schema]:
        return cls._schemas.copy()

    @classmethod
    def list_schemas(cls) -> List[str]:
        return list(cls._schemas.keys())

    @classmethod
    def clear(cls) -> None:
        cls._schemas = {}
