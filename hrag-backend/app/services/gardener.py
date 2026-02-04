from typing import Dict
from app.schemas.common import EntityConflict

# In-memory storage for gardener tasks
# In production, this should be Redis or a database
gardener_tasks: Dict[str, EntityConflict] = {}

def get_all_tasks():
    return list(gardener_tasks.values())

def get_task(task_id: str):
    return gardener_tasks.get(task_id)

def add_task(task_id: str, task: EntityConflict):
    gardener_tasks[task_id] = task

def remove_task(task_id: str):
    if task_id in gardener_tasks:
        del gardener_tasks[task_id]
