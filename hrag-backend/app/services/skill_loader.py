import importlib.util
import inspect
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type

from app.core.logger import logger
from app.state import DynamicSlotInfo, GraphState, RetrievalResult, SlotInfo


class Skill(ABC):
    name: str = "base_skill"
    description: str = "Base skill description"

    @abstractmethod
    async def execute(self, query: str, slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the skill logic.
        Returns a dictionary representing the result.
        """
        pass

    def can_handle(self, query: str, slots: Dict[str, Any]) -> bool:
        """
        Determine if this skill checks should handle the request.
        Default is True if manually selected, but logic can be added here.
        """
        return True


class SkillLoader:
    _skills: Dict[str, Skill] = {}
    _skills_dir: str = os.path.join(os.path.dirname(__file__), "..", "skills")

    @classmethod
    def load_skills(cls) -> None:
        """
        Dynamically load skills from the app/skills directory.
        """
        cls._skills = {}
        if not os.path.exists(cls._skills_dir):
            os.makedirs(cls._skills_dir)

        for filename in os.listdir(cls._skills_dir):
            if filename.endswith(".py") and filename != "__init__.py":
                module_name = filename[:-3]
                file_path = os.path.join(cls._skills_dir, filename)
                
                try:
                    spec = importlib.util.spec_from_file_location(module_name, file_path)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        
                        # Find classes inheriting from Skill
                        for name, obj in inspect.getmembers(module):
                            if (
                                inspect.isclass(obj)
                                and issubclass(obj, Skill)
                                and obj is not Skill
                            ):
                                skill_instance = obj()
                                cls._skills[skill_instance.name] = skill_instance
                                logger.info(f"Loaded skill: {skill_instance.name}")
                except Exception as e:
                    logger.error(f"Failed to load skill {filename}: {e}")

    @classmethod
    def get_skill(cls, name: str) -> Optional[Skill]:
        if not cls._skills:
            cls.load_skills()
        return cls._skills.get(name)

    @classmethod
    def get_all_skills(cls) -> List[Skill]:
        if not cls._skills:
            cls.load_skills()
        return list(cls._skills.values())

    @classmethod
    async def execute_relevant_skills(
        cls, query: str, slots: DynamicSlotInfo
    ) -> List[RetrievalResult]:
        """
        Execute skills that are relevant to the query/slots.
        For now, we can implement a simple keyword match or LLM selector.
        
        To keep it simple for the generic folder approach:
        We will execute all skills that say they can_handle the request.
        """
        if not cls._skills:
            cls.load_skills()

        filled_slots = slots.get_filled_slots()
        results = []

        for skill in cls._skills.values():
            if skill.can_handle(query, filled_slots):
                try:
                    output = await skill.execute(query, filled_slots)
                    
                    if output:
                        # Convert output to string representation for content
                        content_str = "\n".join([f"{k}: {v}" for k, v in output.items()])
                        
                        results.append(
                            RetrievalResult(
                                source="skill",
                                title=f"Skill: {skill.name}",
                                content=content_str,
                                metadata={"skill_name": skill.name},
                                confidence=0.9, # Placeholder confidence
                                raw_data=output
                            )
                        )
                except Exception as e:
                    logger.error(f"Error executing skill {skill.name}: {e}")

        return results
