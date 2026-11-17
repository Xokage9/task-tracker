from datetime import date, timedelta

from sqlalchemy import select

from conftest import register
from core.database import SessionLocal
from core.models import Comment, OutboxEvent, Task


def make_task(client, headers, project_id, **extra):
    response = client.post("/tasks", headers=headers, json={"project_id": project_id, "title": "Написать API", **extra})
    assert response.status_code == 201, response.text
    return response.json()


def test_auth_registration_login_and_duplicate(client):
    user, headers = register(client, "Owner@Example.com")
    assert user["email"] == "owner@example.com"
    assert "password_hash" not in user
    assert client.get("/users/me", headers=headers).json()["id"] == user["id"]
    assert client.get("/users/me").status_code == 401
    assert client.get("/users/me", headers={"Authorization": "Bearer broken"}).status_code == 401
    assert client.post("/users/login", json={"email":"owner@example.com", "password":"bad"}).status_code == 401
    assert client.post("/users/login", json={"email":"owner@example.com", "password":"StrongPass123!"}).status_code == 200
    assert client.post("/users/register", json={"name":"Другой", "email":"owner@example.com", "password":"12345678"}).status_code == 409


def test_task_lifecycle_comments_and_filters(client, owner, project):
    user, headers = owner
    task = make_task(client, headers, project["id"], assignee_id=user["id"], priority="high",
                     due_date=(date.today()+timedelta(days=2)).isoformat())
    assert task["status"] == "todo" and task["completed_at"] is None
    for status in ["in_progress", "review", "done"]:
        response = client.patch(f'/tasks/{task["id"]}', json={"status":status}, headers=headers)
        assert response.status_code == 200
    assert response.json()["completed_at"] is not None
    reopened = client.patch(f'/tasks/{task["id"]}', json={"status":"todo", "assignee_id":None,"due_date":None}, headers=headers).json()
    assert reopened["completed_at"] is None and reopened["due_date"] is None and reopened["assignee_id"] is None
    comment = client.post(f'/tasks/{task["id"]}/comments', json={"body":"Проверил — всё работает"}, headers=headers)
    assert comment.status_code == 201
    assert comment.json()["author"]["name"] == user["name"]
    tasks = client.get(f'/tasks?project_id={project["id"]}&q=API&priority=high&status=todo', headers=headers).json()
    assert len(tasks)==1
    assert client.get(f'/tasks?project_id={project["id"]}&status=review', headers=headers).json()==[]
    assert client.delete(f'/tasks/{task["id"]}', headers=headers).status_code == 204
    with SessionLocal() as db:
        assert db.get(Task, task["id"]) is None
        assert not db.scalars(select(Comment)).all()
        assert len(db.scalars(select(OutboxEvent)).all()) == 7


def test_private_projects_and_membership_rules(client, owner, project):
    task = make_task(client, owner[1], project["id"])
    outsider, headers = register(client,"other@example.com", "Мария")
    assert client.get("/projects",headers=headers).json()==[]
    for path in [f'/projects/{project["id"]}', f'/tasks/{task["id"]}',f'/tasks/{task["id"]}/comments',f'/projects/{project["id"]}/report-data']:
        assert client.get(path,headers=headers).status_code==404
    assert client.patch(f'/tasks/{task["id"]}',headers=headers,json={"title":"Чужое"}).status_code==404
    assert client.post(f'/projects/{project["id"]}/members',headers=owner[1],json={"email":outsider["email"]}).status_code==201
    assert client.get(f'/tasks/{task["id"]}',headers=headers).status_code==200
    assert client.patch(f'/tasks/{task["id"]}',headers=headers,json={"assignee_id":outsider["id"]}).status_code==200
    assert client.patch(f'/projects/{project["id"]}',headers=headers,json={"name":"Новое"}).status_code==403
    assert client.delete(f'/tasks/{task["id"]}',headers=headers).status_code==403
    assert client.delete(f'/projects/{project["id"]}/members/{owner[0]["id"]}',headers=owner[1]).status_code==400
    assert client.delete(f'/projects/{project["id"]}/members/{outsider["id"]}',headers=owner[1]).status_code==204
    assert client.get(f'/tasks/{task["id"]}',headers=owner[1]).json()["assignee_id"] is None
    assert client.get(f'/tasks/{task["id"]}',headers=headers).status_code==404


def test_validation_and_atomic_outbox(client, owner, project):
    task = make_task(client, owner[1], project["id"])
    with SessionLocal() as db:
        before = len(db.scalars(select(OutboxEvent)).all())
    for patch in [{"title":None},{"title":" "},{"status":"other"},{"status":None},{"description":None},{"creator_id":999},{"assignee_id":999}]:
        assert client.patch(f'/tasks/{task["id"]}',headers=owner[1],json=patch).status_code==422
    assert client.patch(f'/projects/{project["id"]}',headers=owner[1],json={"name":None}).status_code==422
    assert client.post(f'/tasks/{task["id"]}/comments',headers=owner[1],json={"body":"  "}).status_code==422
    assert client.get(f'/tasks?project_id={project["id"]}&limit=-1',headers=owner[1]).status_code==422
    assert client.get(f'/tasks?project_id={project["id"]}&q=%25',headers=owner[1]).json()==[]
    assert client.patch(f'/tasks/{task["id"]}',headers=owner[1],json={"title":task["title"]}).status_code==200
    with SessionLocal() as db:
        assert len(db.scalars(select(OutboxEvent)).all())==before
        assert db.get(Task,task["id"]).title==task["title"]


def test_project_delete_cascades(client, owner, project):
    task = make_task(client, owner[1], project["id"])
    client.post(f'/tasks/{task["id"]}/comments',headers=owner[1],json={"body":"Комментарий"})
    assert client.delete(f'/projects/{project["id"]}',headers=owner[1]).status_code==204
    assert client.get(f'/tasks/{task["id"]}',headers=owner[1]).status_code==404
    with SessionLocal() as db:
        assert db.scalars(select(Comment)).all()==[]
