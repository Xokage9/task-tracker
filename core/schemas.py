from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator

from core.models import Priority, Status

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
ProjectName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
Description = Annotated[str, StringConstraints(max_length=10000)]
Body = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Register(Input):
    name: Name
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class Login(Input):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(ORM):
    id: int
    email: str
    name: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ProjectCreate(Input):
    name: ProjectName
    description: Description = ""


class NonNullPatch(Input):
    @model_validator(mode="after")
    def reject_nulls(self):
        for field in self.model_fields_set - {"assignee_id", "due_date"}:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class ProjectUpdate(NonNullPatch):
    name: ProjectName | None = None
    description: Description | None = None


class ProjectOut(ORM):
    id: int
    name: str
    description: str
    owner_id: int
    created_at: datetime


class MemberAdd(Input):
    email: EmailStr


class TaskCreate(Input):
    project_id: int = Field(gt=0)
    title: Title
    description: Description = ""
    status: Status = Status.todo
    priority: Priority = Priority.medium
    assignee_id: int | None = Field(default=None, gt=0)
    due_date: date | None = None


class TaskUpdate(NonNullPatch):
    title: Title | None = None
    description: Description | None = None
    status: Status | None = None
    priority: Priority | None = None
    assignee_id: int | None = Field(default=None, gt=0)
    due_date: date | None = None


class TaskOut(ORM):
    id: int
    project_id: int
    title: str
    description: str
    status: Status
    priority: Priority
    creator_id: int
    assignee_id: int | None
    due_date: date | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class CommentCreate(Input):
    body: Body


class CommentOut(ORM):
    id: int
    task_id: int
    author_id: int
    body: str
    created_at: datetime
    author: UserOut
