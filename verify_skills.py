import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), "hrag-backend"))

from app.services.skill_loader import SkillLoader
from app.state import DynamicSlotInfo

async def verify():
    print("Loading skills...")
    SkillLoader.load_skills()
    skills = SkillLoader.get_all_skills()
    print(f"Loaded {len(skills)} skills:")
    for s in skills:
        print(f" - {s.name}: {s.description}")

    query = "Hello world, generic query"
    print(f"\nExecuting query: '{query}'")
    slots = DynamicSlotInfo()
    results = await SkillLoader.execute_relevant_skills(query, slots)
    
    print(f"\nResults ({len(results)}):")
    for r in results:
        print(f"Source: {r.source}")
        print(f"Title: {r.title}")
        print(f"Content: {r.content}")

if __name__ == "__main__":
    asyncio.run(verify())
