from typing import Any, Dict

from app.services.skill_loader import Skill


class HelloSkill(Skill):
    name = "hello_skill"
    description = "Responds to hello/hi greetings."

    def can_handle(self, query: str, slots: Dict[str, Any]) -> bool:
        return "hello" in query.lower() or "hi" in query.lower()

    async def execute(self, query: str, slots: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Hello! I am a skill running from the new Skills folder.",
            "status": "success"
        }
