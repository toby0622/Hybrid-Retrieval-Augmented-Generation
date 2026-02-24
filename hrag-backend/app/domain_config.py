from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from app.core.logger import logger


@dataclass
class SlotConfig:
    required: List[str] = field(default_factory=list)
    optional: List[str] = field(default_factory=list)
    examples: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class PromptConfig:
    system_identity: str = ""
    capabilities: List[str] = field(default_factory=list)
    examples: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class QueryConfig:
    primary_search: str = ""
    context_search: str = ""
    fallback_search: str = ""


@dataclass
class DomainConfig:
    name: str
    display_name: str
    description: str = ""

    schema_name: str = ""

    intents: List[str] = field(default_factory=lambda: ["question", "chat", "end"])
    intent_keywords: Dict[str, List[str]] = field(default_factory=dict)

    slots: SlotConfig = field(default_factory=SlotConfig)

    classification_prompt: PromptConfig = field(default_factory=PromptConfig)
    clarification_prompt: PromptConfig = field(default_factory=PromptConfig)
    reasoning_prompt: PromptConfig = field(default_factory=PromptConfig)
    chat_prompt: PromptConfig = field(default_factory=PromptConfig)

    graph_queries: QueryConfig = field(default_factory=QueryConfig)
    vector_filter_fields: List[str] = field(default_factory=list)

    routing_keywords: List[str] = field(default_factory=list)

    response_language: str = "zh-TW"

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "DomainConfig":
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "DomainConfig":
        slots_data = data.get("slots", {})
        slots = SlotConfig(
            required=slots_data.get("required", []),
            optional=slots_data.get("optional", []),
            examples=slots_data.get("examples", {}),
        )

        def parse_prompt(prompt_data: Dict) -> PromptConfig:
            if not prompt_data:
                return PromptConfig()
            return PromptConfig(
                system_identity=prompt_data.get("system_identity", ""),
                capabilities=prompt_data.get("capabilities", []),
                examples=prompt_data.get("examples", []),
            )

        queries_data = data.get("graph_queries", {})
        queries = QueryConfig(
            primary_search=queries_data.get("primary_search", ""),
            context_search=queries_data.get("context_search", ""),
            fallback_search=queries_data.get("fallback_search", ""),
        )

        return cls(
            name=data.get("name", "unknown"),
            display_name=data.get("display_name", "Unknown Domain"),
            description=data.get("description", ""),
            schema_name=data.get("schema", ""),
            intents=data.get("intents", ["question", "chat", "end"]),
            intent_keywords=data.get("intent_keywords", {}),
            slots=slots,
            classification_prompt=parse_prompt(data.get("classification_prompt", {})),
            clarification_prompt=parse_prompt(data.get("clarification_prompt", {})),
            reasoning_prompt=parse_prompt(data.get("reasoning_prompt", {})),
            chat_prompt=parse_prompt(data.get("chat_prompt", {})),
            graph_queries=queries,
            vector_filter_fields=data.get("vector_filter_fields", []),
            routing_keywords=data.get("routing_keywords", []),
            response_language=data.get("response_language", "zh-TW"),
        )


class DomainRegistry:
    _domains: Dict[str, DomainConfig] = {}
    _active_domain: Optional[str] = None
    _domains_path: Optional[Path] = None

    @classmethod
    def set_domains_path(cls, path: Path) -> None:
        cls._domains_path = path

    @classmethod
    def discover(cls, domains_path: Optional[Path] = None) -> List[str]:
        if domains_path:
            cls._domains_path = domains_path

        if not cls._domains_path:
            raise ValueError("Domains path not set. Call set_domains_path() first.")

        if not cls._domains_path.exists():
            logger.warning(f"Domains path does not exist: {cls._domains_path}")
            return []

        yaml_files = list(cls._domains_path.glob("*.yaml")) + list(
            cls._domains_path.glob("*.yml")
        )
        discovered = []

        for yaml_file in yaml_files:
            domain_name = yaml_file.stem
            discovered.append(domain_name)

            try:
                config = DomainConfig.from_yaml(yaml_file)
                cls._domains[config.name] = config
            except Exception as e:
                logger.warning(f"Failed to load domain config {yaml_file}: {e}")

        return discovered

    @classmethod
    def register(cls, config: DomainConfig) -> None:
        cls._domains[config.name] = config

    @classmethod
    def get_domain(cls, name: str) -> Optional[DomainConfig]:
        return cls._domains.get(name)

    @classmethod
    def get_active(cls) -> Optional[DomainConfig]:
        if cls._active_domain:
            return cls._domains.get(cls._active_domain)
        return None

    @classmethod
    def set_active(cls, name: str) -> bool:
        if name in cls._domains:
            cls._active_domain = name
            logger.info(f"Active domain set to: {name}")
            return True
        logger.warning(f"Domain not found: {name}")
        return False

    @classmethod
    def get_active_name(cls) -> Optional[str]:
        return cls._active_domain

    @classmethod
    def list_domains(cls) -> List[str]:
        return list(cls._domains.keys())

    @classmethod
    def clear(cls) -> None:
        cls._domains = {}
        cls._active_domain = None
