from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.core.logger import logger
from app.domain_config import DomainConfig, DomainRegistry
from app.schema_registry import Schema, SchemaRegistry


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

    logger.info("Initializing domain system...")
    logger.info(f"   Scripts path: {scripts_path}")
    logger.info(f"   Domains path: {domains_path}")

    schemas = SchemaRegistry.discover(scripts_path)
    logger.info(f"   Discovered schemas: {schemas}")

    domains = DomainRegistry.discover(domains_path)
    logger.info(f"   Discovered domains: {domains}")

    if not domains:
        raise ValueError(f"No domain configs found in {domains_path}")

    if not active_domain:
        if domains:
            logger.info(
                f"   No active domain configured, defaulting to '{domains[0]}'"
            )
            active_domain = domains[0]

    if active_domain not in domains:
        logger.warning(
            f"   Domain '{active_domain}' not found, using first available"
        )
        active_domain = domains[0]

    success = DomainRegistry.set_active(active_domain)
    if not success:
        raise ValueError(f"Failed to set active domain: {active_domain}")

    config = DomainRegistry.get_active()
    if config is None:
        raise ValueError("No active domain configuration")

    logger.info(f"   Active domain: {config.display_name}")
    logger.info(f"   Intents: {config.intents}")
    logger.info(f"   Required slots: {config.slots.required}")

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
