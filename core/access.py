from fastapi import HTTPException
from sqlalchemy.orm import Session

from core.models import Membership, Project, Task


def project_for(db: Session, project_id: int, user_id: int, *, owner=False) -> Project:
    project = db.get(Project, project_id)
    if not project or not db.get(Membership, (project_id, user_id)):
        raise HTTPException(404, "Проект не найден")
    if owner and project.owner_id != user_id:
        raise HTTPException(403, "Это действие доступно владельцу проекта")
    return project


def task_for(db: Session, task_id: int, user_id: int) -> Task:
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Задача не найдена")
    project_for(db, task.project_id, user_id)
    return task
