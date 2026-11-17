from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import select, update

from core.access import project_for
from core.auth import CurrentUser, DB
from core.models import Membership, Project, Task, User
from core.schemas import MemberAdd, ProjectCreate, ProjectOut, ProjectUpdate, TaskOut, UserOut

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
def list_projects(db: DB, user: CurrentUser, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200)):
    return db.scalars(select(Project).join(Membership).where(Membership.user_id == user.id)
                      .order_by(Project.id.desc()).offset(offset).limit(limit)).all()


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(data: ProjectCreate, db: DB, user: CurrentUser):
    project = Project(**data.model_dump(), owner_id=user.id)
    db.add(project)
    db.flush()
    db.add(Membership(project_id=project.id, user_id=user.id))
    db.commit()
    return project


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: DB, user: CurrentUser):
    return project_for(db, project_id, user.id)


@router.patch("/{project_id}", response_model=ProjectOut)
def edit_project(project_id: int, data: ProjectUpdate, db: DB, user: CurrentUser):
    project = project_for(db, project_id, user.id, owner=True)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.commit()
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, db: DB, user: CurrentUser):
    db.delete(project_for(db, project_id, user.id, owner=True))
    db.commit()
    return Response(status_code=204)


@router.get("/{project_id}/members", response_model=list[UserOut])
def members(project_id: int, db: DB, user: CurrentUser):
    project_for(db, project_id, user.id)
    return db.scalars(select(User).join(Membership).where(Membership.project_id == project_id).order_by(User.name)).all()


@router.post("/{project_id}/members", response_model=UserOut, status_code=201)
def add_member(project_id: int, data: MemberAdd, db: DB, user: CurrentUser):
    project_for(db, project_id, user.id, owner=True)
    member = db.scalar(select(User).where(User.email == str(data.email).lower()))
    if not member:
        raise HTTPException(404, "Пользователь с этим email ещё не зарегистрирован")
    # Locking the project serializes concurrent membership additions in PostgreSQL.
    db.execute(select(Project).where(Project.id == project_id).with_for_update())
    if db.get(Membership, (project_id, member.id)):
        raise HTTPException(409, "Пользователь уже в проекте")
    db.add(Membership(project_id=project_id, user_id=member.id))
    db.commit()
    return member


@router.delete("/{project_id}/members/{user_id}", status_code=204)
def remove_member(project_id: int, user_id: int, db: DB, user: CurrentUser):
    project = project_for(db, project_id, user.id, owner=True)
    if project.owner_id == user_id:
        raise HTTPException(400, "Владельца проекта нельзя исключить")
    membership = db.get(Membership, (project_id, user_id))
    if not membership:
        raise HTTPException(404, "Участник не найден")
    db.execute(update(Task).where(Task.project_id == project_id, Task.assignee_id == user_id).values(assignee_id=None))
    db.delete(membership)
    db.commit()
    return Response(status_code=204)


@router.get("/{project_id}/report-data")
def report_data(project_id: int, db: DB, user: CurrentUser):
    project = project_for(db, project_id, user.id)
    tasks = db.scalars(select(Task).where(Task.project_id == project_id).order_by(Task.id)).all()
    return {"project": ProjectOut.model_validate(project).model_dump(mode="json"),
            "tasks": [TaskOut.model_validate(task).model_dump(mode="json") for task in tasks]}
