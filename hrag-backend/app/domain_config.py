"""
Domain Configuration System
Defines domain-specific behavior for the LangGraph workflow.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class SlotConfig:
    """Configuration for slot filling."""
    required: List[str] = field(default_factory=list)
    optional: List[str] = field(default_factory=list)
    examples: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class PromptConfig:
    """Configuration for LLM prompts."""
    system_identity: str = ""
    capabilities: List[str] = field(default_factory=list)
    examples: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class QueryConfig:
    """Configuration for database queries."""
    primary_search: str = ""
    context_search: str = ""
    fallback_search: str = ""


@dataclass  
class DomainConfig:
    """
    Complete domain configuration.
    Defines how the LangGraph workflow behaves for a specific domain/dataset.
    """
    
    # Basic info
    name: str
    display_name: str
    description: str = ""
    
    # Schema reference (links to *_schema.py)
    schema_name: str = ""
    
    # Intent classification
    intents: List[str] = field(default_factory=lambda: ["question", "chat", "end"])
    intent_keywords: Dict[str, List[str]] = field(default_factory=dict)
    
    # Slot filling
    slots: SlotConfig = field(default_factory=SlotConfig)
    
    # Prompts
    classification_prompt: PromptConfig = field(default_factory=PromptConfig)
    clarification_prompt: PromptConfig = field(default_factory=PromptConfig)
    reasoning_prompt: PromptConfig = field(default_factory=PromptConfig)
    chat_prompt: PromptConfig = field(default_factory=PromptConfig)
    
    # Database queries
    graph_queries: QueryConfig = field(default_factory=QueryConfig)
    vector_filter_fields: List[str] = field(default_factory=list)
    
    # Response formatting
    response_language: str = "zh-TW"

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "DomainConfig":
        """Load domain config from YAML file."""
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "DomainConfig":
        """Create DomainConfig from dictionary."""
        slots_data = data.get("slots", {})
        slots = SlotConfig(
            required=slots_data.get("required", []),
            optional=slots_data.get("optional", []),
            examples=slots_data.get("examples", {}),
        )

        # Parse prompt configs
        def parse_prompt(prompt_data: Dict) -> PromptConfig:
            if not prompt_data:
                return PromptConfig()
            return PromptConfig(
                system_identity=prompt_data.get("system_identity", ""),
                capabilities=prompt_data.get("capabilities", []),
                examples=prompt_data.get("examples", []),
            )

        # Parse query config
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
            response_language=data.get("response_language", "zh-TW"),
        )


class DomainRegistry:
    """
    Registry for domain configurations.
    Manages loading and switching between domains at runtime.
    """

    _domains: Dict[str, DomainConfig] = {}
    _active_domain: Optional[str] = None
    _domains_path: Optional[Path] = None

    @classmethod
    def set_domains_path(cls, path: Path) -> None:
        """Set the path to search for domain YAML files."""
        cls._domains_path = path

    @classmethod
    def discover(cls, domains_path: Optional[Path] = None) -> List[str]:
        """
        Auto-discover *.yaml domain config files.
        
        Returns:
            List of domain names
        """
        if domains_path:
            cls._domains_path = domains_path

        if not cls._domains_path:
            raise ValueError("Domains path not set. Call set_domains_path() first.")

        if not cls._domains_path.exists():
            print(f"[DomainRegistry] Domains path does not exist: {cls._domains_path}")
            return []

        yaml_files = list(cls._domains_path.glob("*.yaml")) + list(cls._domains_path.glob("*.yml"))
        discovered = []

        for yaml_file in yaml_files:
            domain_name = yaml_file.stem
            discovered.append(domain_name)
            
            try:
                config = DomainConfig.from_yaml(yaml_file)
                cls._domains[config.name] = config
            except Exception as e:
                print(f"[DomainRegistry] Warning: Failed to load {yaml_file}: {e}")

        return discovered

    @classmethod
    def register(cls, config: DomainConfig) -> None:
        """Register a domain configuration."""
        cls._domains[config.name] = config

    @classmethod
    def get_domain(cls, name: str) -> Optional[DomainConfig]:
        """Get a domain configuration by name."""
        return cls._domains.get(name)

    @classmethod
    def get_active(cls) -> Optional[DomainConfig]:
        """Get the currently active domain configuration."""
        if cls._active_domain:
            return cls._domains.get(cls._active_domain)
        return None

    @classmethod
    def set_active(cls, name: str) -> bool:
        """
        Set the active domain.
        
        Returns:
            True if domain was set, False if domain not found
        """
        if name in cls._domains:
            cls._active_domain = name
            print(f"[DomainRegistry] Active domain set to: {name}")
            return True
        print(f"[DomainRegistry] Domain not found: {name}")
        return False

    @classmethod
    def get_active_name(cls) -> Optional[str]:
        """Get the name of the currently active domain."""
        return cls._active_domain

    @classmethod
    def list_domains(cls) -> List[str]:
        """List all registered domain names."""
        return list(cls._domains.keys())

    @classmethod
    def clear(cls) -> None:
        """Clear all registered domains."""
        cls._domains = {}
        cls._active_domain = None
