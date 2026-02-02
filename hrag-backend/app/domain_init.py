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
    base_path = Path(__file__).parent.parent

    DEFAULT_SCRIPTS_PATH = "scripts"
    DEFAULT_DOMAINS_PATH = "config/domains"

    if scripts_path is None:
        scripts_path = base_path / DEFAULT_SCRIPTS_PATH

    if domains_path is None:
        domains_path = base_path / DEFAULT_DOMAINS_PATH

    if active_domain is None:
        active_domain = settings.active_domain

    print(f"[Domain] Initializing domain system...")
    print(f"   Scripts path: {scripts_path}")
    print(f"   Domains path: {domains_path}")

    schemas = SchemaRegistry.discover(scripts_path)
    print(f"   Discovered schemas: {schemas}")

    domains = DomainRegistry.discover(domains_path)
    print(f"   Discovered domains: {domains}")

    if not domains:
        raise ValueError(f"No domain configs found in {domains_path}")

    if not active_domain:
        if domains:
            print(f"   [INFO] No active domain configured, defaulting to '{domains[0]}'")
            active_domain = domains[0]
    
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
    return DomainRegistry.get_active()


def get_active_schema() -> Optional[Schema]:
    domain = DomainRegistry.get_active()
    if domain and domain.schema_name:
        return SchemaRegistry.get_schema(domain.schema_name)
    return None


def switch_domain(domain_name: str) -> bool:
    return DomainRegistry.set_active(domain_name)


def list_available_domains() -> list[str]:
    return DomainRegistry.list_domains()


def list_available_schemas() -> list[str]:
    return SchemaRegistry.list_schemas()
