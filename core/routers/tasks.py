from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import select

from core.access import project_for, task_for
from core.auth import CurrentUser, DB
from core.events import notify_project
from core.models import Comment, Membership, Priority, Project, Status, Task, utcnow
from core.schemas import CommentCreate, CommentOut, TaskCreate, TaskOut, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])


def check_assignee(db, project_id, assignee_id):
    if assignee_id is not None and not db.get(Membership, (project_id, assignee_id)):
        raise HTTPException(422, "Исполнитель должен быть участником проекта")


@router.get("", response_model=list[TaskOut])
def list_tasks(db: DB, user: CurrentUser, project_id: int = Query(..., gt=0),
               status: Status | None = None, priority: Priority | None = None,
               assignee_id: int | None = Query(None, gt=0), q: str = Query("", max_length=200),
               offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200)):
    project_for(db, project_id, user.id)
    query = select(Task).where(Task.project_id == project_id)
    if status:
        query = query.where(Task.status == status.value)
    if priority:
        query = query.where(Task.priority == priority.value)
    if assignee_id:
        query = query.where(Task.assignee_id == assignee_id)
    if q.strip():
        query = query.where(Task.title.icontains(q.strip(), autoescape=True))
    return db.scalars(query.order_by(Task.id.desc()).offset(offset).limit(limit)).all()


@router.post("", response_model=TaskOut, status_code=201)
def create_task(data: TaskCreate, db: DB, user: CurrentUser):
    project_for(db, data.project_id, user.id)
    check_assignee(db, data.project_id, data.assignee_id)
    task = Task(**data.model_dump(), creator_id=user.id,
                completed_at=utcnow() if data.status == Status.done else None)
    db.add(task)
    db.flush()
    notify_project(db, task.project_id, "task.created", "Новая задача", f"{user.name}: {task.title}", task.id)
    db.commit()
    return task


@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: int, db: DB, user: CurrentUser):
    return task_for(db, task_id, user.id)


@router.patch("/{task_id}", response_model=TaskOut)
def edit_task(task_id: int, data: TaskUpdate, db: DB, user: CurrentUser):
    task = task_for(db, task_id, user.id)
    patch = data.model_dump(exclude_unset=True)
    if "assignee_id" in patch:
        check_assignee(db, task.project_id, patch["assignee_id"])
    changed = any(getattr(task, field) != value for field, value in patch.items())
    if not changed:
        return task
    if "status" in patch and patch["status"] != task.status:
        task.completed_at = utcnow() if patch["status"] == Status.done else None
    for field, value in patch.items():
        setattr(task, field, value)
    notify_project(db, task.project_id, "task.updated", "Задача обновлена", f"{user.name}: {task.title}", task.id)
    db.commit()
    return task


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, db: DB, user: CurrentUser):
    task = task_for(db, task_id, user.id)
    project = db.get(Project, task.project_id)
    if user.id not in (task.creator_id, project.owner_id):
        raise HTTPException(403, "Удалить задачу может её автор или владелец проекта")
    notify_project(db, task.project_id, "task.deleted", "Задача удалена", f"{user.name}: {task.title}")
    db.delete(task)
    db.commit()
    return Response(status_code=204)


@router.get("/{task_id}/comments", response_model=list[CommentOut])
def comments(task_id: int, db: DB, user: CurrentUser,
             offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200)):
    task_for(db, task_id, user.id)
    return db.scalars(select(Comment).where(Comment.task_id == task_id).order_by(Comment.id)
                      .offset(offset).limit(limit)).all()


@router.post("/{task_id}/comments", response_model=CommentOut, status_code=201)
def add_comment(task_id: int, data: CommentCreate, db: DB, user: CurrentUser):
    task = task_for(db, task_id, user.id)
    comment = Comment(task_id=task_id, author_id=user.id, body=data.body)
    db.add(comment)
    notify_project(db, task.project_id, "comment.created", "Новый комментарий", f"{user.name}: {data.body}", task.id)
    db.commit()
    return comment


@router.delete("/{task_id}/comments/{comment_id}", status_code=204)
def delete_comment(task_id: int, comment_id: int, db: DB, user: CurrentUser):
    task = task_for(db, task_id, user.id)
    comment = db.get(Comment, comment_id)
    if not comment or comment.task_id != task_id:
        raise HTTPException(404, "Комментарий не найден")
    if user.id not in (comment.author_id, db.get(Project, task.project_id).owner_id):
        raise HTTPException(403, "Удалить комментарий может его автор или владелец проекта")
    db.delete(comment)
    db.commit()
    return Response(status_code=204)
