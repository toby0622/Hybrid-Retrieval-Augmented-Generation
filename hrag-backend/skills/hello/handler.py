"""
Hello Skill handler — migrated from app/skills/hello.py.

This is an example of an executable skill handler that runs alongside
the HRAG pipeline. Handlers are auto-discovered by SkillRegistry.
"""

from typing import Any, Dict


class HelloHandler:
    """Responds to hello/hi greetings with a friendly message."""

    name = "hello_skill"
    description = "Responds to hello/hi greetings."

    def can_handle(self, query: str, slots: Dict[str, Any]) -> bool:
        return "hello" in query.lower() or "hi" in query.lower()

    async def execute(self, query: str, slots: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Hello! I am a skill running from the Skills system.",
            "status": "success",
        }
