"""
Domain System Initialization
Sets up schema registry and domain configurations on app startup.
"""

from pathlib import Path
from typing import Optional

from app.domain_config import DomainConfig, DomainRegistry
from app.schema_registry import Schema, SchemaRegistry
from config import settings


def initialize_domain_system(
    scripts_path: Optional[Path] = None,
    domains_path: Optional[Path] = None,
    active_domain: Optional[str] = None,
) -> DomainConfig:
    """
    Initialize the domain configuration system.
    
    1. Discovers available schemas from *_schema.py files
    2. Loads domain configs from *.yaml files
    3. Sets the active domain
    
    Args:
        scripts_path: Path to scripts directory (default: from settings)
        domains_path: Path to domains directory (default: from settings)
        active_domain: Domain to activate (default: from settings)
    
    Returns:
        The active DomainConfig
    
    Raises:
        ValueError: If no domains are found or active domain is invalid
    """
    # Use defaults from settings
    base_path = Path(__file__).parent.parent
    
    if scripts_path is None:
        scripts_path = base_path / settings.scripts_path
    
    if domains_path is None:
        domains_path = base_path / settings.domains_path
    
    if active_domain is None:
        active_domain = settings.active_domain

    print(f"[Domain] Initializing domain system...")
    print(f"   Scripts path: {scripts_path}")
    print(f"   Domains path: {domains_path}")

    # Step 1: Discover schemas
    schemas = SchemaRegistry.discover(scripts_path)
    print(f"   Discovered schemas: {schemas}")

    # Step 2: Discover domain configs
    domains = DomainRegistry.discover(domains_path)
    print(f"   Discovered domains: {domains}")

    if not domains:
        raise ValueError(f"No domain configs found in {domains_path}")

    # Step 3: Set active domain
    if active_domain not in domains:
        print(f"   [WARN] Domain '{active_domain}' not found, using first available")
        active_domain = domains[0]

    success = DomainRegistry.set_active(active_domain)
    if not success:
        raise ValueError(f"Failed to set active domain: {active_domain}")

    config = DomainRegistry.get_active()
    if config is None:
        raise ValueError("No active domain configuration")

    print(f"   Active domain: {config.display_name}")
    print(f"   Intents: {config.intents}")
    print(f"   Required slots: {config.slots.required}")

    return config


def get_active_domain() -> Optional[DomainConfig]:
    """Get the currently active domain configuration."""
    return DomainRegistry.get_active()


def get_active_schema() -> Optional[Schema]:
    """Get the schema for the currently active domain."""
    domain = DomainRegistry.get_active()
    if domain and domain.schema_name:
        return SchemaRegistry.get_schema(domain.schema_name)
    return None


def switch_domain(domain_name: str) -> bool:
    """
    Switch to a different domain at runtime.
    
    Returns:
        True if switch was successful
    """
    return DomainRegistry.set_active(domain_name)


def list_available_domains() -> list[str]:
    """List all available domain names."""
    return DomainRegistry.list_domains()


def list_available_schemas() -> list[str]:
    """List all available schema names."""
    return SchemaRegistry.list_schemas()
