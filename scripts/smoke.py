"""Exercise the full running stack through the same gateway as the browser."""
import os
import time
from uuid import uuid4

import httpx


def main():
    base = os.getenv("BASE_URL", "http://127.0.0.1:8080").rstrip("/")
    with httpx.Client(base_url=base, timeout=15, trust_env=False) as client:
        assert client.get("/").status_code == 200
        for path in ("/api/health", "/notify/health", "/reports-api/health"):
            response = client.get(path)
            response.raise_for_status()
            assert response.json()["status"] == "ok"
        email = f"smoke-{uuid4().hex[:12]}@example.com"
        response = client.post("/api/users/register", json={"name":"Проверка", "email":email, "password":uuid4().hex})
        response.raise_for_status()
        token = response.json()["access_token"]
        client.headers["Authorization"] = f"Bearer {token}"
        response = client.post("/api/projects", json={"name":"Smoke test"})
        response.raise_for_status()
        project_id = response.json()["id"]
        try:
            response = client.post("/api/tasks", json={"project_id":project_id, "title":"Сквозная проверка"})
            response.raise_for_status()
            task_id = response.json()["id"]
            client.post(f"/api/tasks/{task_id}/comments", json={"body":"Проверка комментариев"}).raise_for_status()
            client.patch(f"/api/tasks/{task_id}", json={"status":"done"}).raise_for_status()
            response = client.get(f"/reports-api/reports/projects/{project_id}")
            response.raise_for_status()
            assert response.json()["completion_percent"] == 100
            response = client.get(f"/reports-api/reports/projects/{project_id}.csv")
            response.raise_for_status()
            assert "Сквозная проверка" in response.text
            deadline = time.monotonic() + 25
            while True:
                response = client.get("/notify/notifications")
                response.raise_for_status()
                if response.json()["total"] >= 3:
                    break
                if time.monotonic() > deadline:
                    raise AssertionError("Notifications were not delivered in 25 seconds")
                time.sleep(0.4)
            client.patch("/notify/notifications/read-all").raise_for_status()
            assert client.get("/notify/notifications").json()["unread_count"] == 0
            print("OK: frontend, auth, projects, tasks, comments, outbox, inbox, JSON/CSV reports")
        finally:
            client.delete(f"/api/projects/{project_id}").raise_for_status()


if __name__ == "__main__":
    main()
