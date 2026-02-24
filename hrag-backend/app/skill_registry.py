"""
Skill Registry — unified discovery, activation, and handler execution.

Replaces the old DomainRegistry + SchemaRegistry + SkillLoader with a single
registry that manages all skills from the `skills/` directory.
"""

import importlib.util
import inspect
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from app.core.config import settings
from app.core.logger import logger
from app.skill_config import SkillConfig


class _SkillHandler:
    """Base interface for executable skill handlers found in handler.py."""

    name: str = "base_handler"
    description: str = ""

    async def execute(self, query: str, slots: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def can_handle(self, query: str, slots: Dict[str, Any]) -> bool:
        return True


class SkillRegistry:
    """
    Singleton-style class-level registry for all discovered skills.

    Usage:
        SkillRegistry.discover(Path("skills"))
        skill = SkillRegistry.get_active()
    """

    _skills: Dict[str, SkillConfig] = {}
    _handlers: Dict[str, _SkillHandler] = {}
    _active_skill: Optional[str] = None
    _skills_path: Optional[Path] = None

    # ───────────── Discovery ─────────────

    @classmethod
    def discover(cls, skills_path: Optional[Path] = None) -> List[str]:
        """
        Scan the skills directory for skill.yaml files and register them.
        Each skill is a sub-folder: skills/<name>/skill.yaml
        """
        if skills_path:
            cls._skills_path = skills_path

        if not cls._skills_path:
            raise ValueError("Skills path not set.")

        if not cls._skills_path.exists():
            logger.warning(f"Skills path does not exist: {cls._skills_path}")
            return []

        discovered: List[str] = []

        for skill_dir in sorted(cls._skills_path.iterdir()):
            if not skill_dir.is_dir():
                continue

            yaml_path = skill_dir / "skill.yaml"
            if not yaml_path.exists():
                yaml_path = skill_dir / "skill.yml"
            if not yaml_path.exists():
                continue

            try:
                config = SkillConfig.from_yaml(yaml_path)
                cls._skills[config.name] = config
                discovered.append(config.name)
                logger.info(f"Discovered skill: {config.name} ({config.display_name})")

                # Load handler if exists
                if config.handler_module:
                    cls._load_handler(config.name, Path(config.handler_module))

            except Exception as e:
                logger.warning(f"Failed to load skill from {skill_dir}: {e}")

        return discovered

    @classmethod
    def _load_handler(cls, skill_name: str, handler_path: Path) -> None:
        """Dynamically load a handler.py from a skill directory."""
        try:
            spec = importlib.util.spec_from_file_location(
                f"skill_handler_{skill_name}", handler_path
            )
            if spec is None or spec.loader is None:
                return

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            for _attr_name, obj in inspect.getmembers(module):
                if (
                    inspect.isclass(obj)
                    and hasattr(obj, "execute")
                    and obj is not _SkillHandler
                ):
                    try:
                        instance = obj()
                        handler_name = getattr(instance, "name", skill_name)
                        cls._handlers[handler_name] = instance
                        logger.info(f"Loaded handler: {handler_name} from {handler_path.name}")
                    except Exception as init_err:
                        logger.warning(f"Failed to instantiate handler {obj}: {init_err}")

        except Exception as e:
            logger.error(f"Failed to load handler {handler_path}: {e}")

    # ───────────── Activation ─────────────

    @classmethod
    def set_active(cls, name: str) -> bool:
        if name in cls._skills:
            cls._active_skill = name
            logger.info(f"Active skill set to: {name}")
            return True
        logger.warning(f"Skill not found: {name}")
        return False

    @classmethod
    def get_active(cls) -> Optional[SkillConfig]:
        if cls._active_skill:
            return cls._skills.get(cls._active_skill)
        return None

    @classmethod
    def get_active_name(cls) -> Optional[str]:
        return cls._active_skill

    # ───────────── Lookup ─────────────

    @classmethod
    def get_skill(cls, name: str) -> Optional[SkillConfig]:
        return cls._skills.get(name)

    @classmethod
    def list_skills(cls) -> List[str]:
        return list(cls._skills.keys())

    @classmethod
    def get_handler(cls, name: str) -> Optional[_SkillHandler]:
        return cls._handlers.get(name)

    @classmethod
    def list_handlers(cls) -> List[str]:
        return list(cls._handlers.keys())

    # ───────────── Handler Execution ─────────────

    @classmethod
    async def execute_handlers(
        cls, query: str, slots: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Execute all handlers that claim they can handle the current query.
        Returns a list of result dicts.
        """
        results: List[Dict[str, Any]] = []

        for handler_name, handler in cls._handlers.items():
            try:
                if handler.can_handle(query, slots):
                    output = await handler.execute(query, slots)
                    if output:
                        results.append(
                            {
                                "handler_name": handler_name,
                                "output": output,
                            }
                        )
            except Exception as e:
                logger.error(f"Error executing handler {handler_name}: {e}")

        return results

    # ───────────── Initialization (replaces domain_init) ─────────────

    @classmethod
    def initialize(
        cls,
        skills_path: Optional[Path] = None,
        active_skill: Optional[str] = None,
    ) -> SkillConfig:
        """
        Full initialization: discover skills and set active.
        Replaces the old `initialize_domain_system()`.
        """
        base_path = Path(__file__).parent.parent

        if skills_path is None:
            skills_dir = getattr(settings, "skills_dir", "skills")
            skills_path = base_path / skills_dir

        if active_skill is None:
            active_skill = getattr(settings, "active_skill", None)

        logger.info("Initializing skill system...")
        logger.info(f"   Skills path: {skills_path}")

        discovered = cls.discover(skills_path)
        logger.info(f"   Discovered skills: {discovered}")

        if not discovered:
            raise ValueError(f"No skills found in {skills_path}")

        # Auto-select active skill
        if not active_skill:
            active_skill = discovered[0]
            logger.info(f"   No active skill configured, defaulting to '{active_skill}'")

        if active_skill not in cls._skills:
            logger.warning(f"   Skill '{active_skill}' not found, using first available")
            active_skill = discovered[0]

        success = cls.set_active(active_skill)
        if not success:
            raise ValueError(f"Failed to set active skill: {active_skill}")

        config = cls.get_active()
        if config is None:
            raise ValueError("No active skill configuration")

        logger.info(f"   Active skill: {config.display_name}")
        logger.info(f"   Intents: {config.intents}")
        logger.info(f"   Required slots: {config.slots.required}")
        logger.info(f"   Handlers loaded: {cls.list_handlers()}")

        return config

    # ───────────── Reset ─────────────

    @classmethod
    def clear(cls) -> None:
        cls._skills = {}
        cls._handlers = {}
        cls._active_skill = None


# ──────────── Convenience functions (backward-compat shims) ────────────


def get_active_skill() -> Optional[SkillConfig]:
    """Drop-in replacement for old get_active_domain()."""
    return SkillRegistry.get_active()


def switch_skill(name: str) -> bool:
    """Drop-in replacement for old switch_domain()."""
    return SkillRegistry.set_active(name)


def list_available_skills() -> List[str]:
    """Drop-in replacement for old list_available_domains()."""
    return SkillRegistry.list_skills()
