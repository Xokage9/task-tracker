"""Opt-in demo data for a local installation. No production data is modified."""
import os
from datetime import datetime, timedelta, timezone

import httpx

EMAIL = "demo@example.com"
PASSWORD = "TrackerDemo2026!"


def main():
    base = os.getenv("BASE_URL", "http://127.0.0.1:8080").rstrip("/")
    with httpx.Client(base_url=base, timeout=15, trust_env=False) as client:
        response=client.post("/api/users/register",json={"name":"Демо пользователь","email":EMAIL,"password":PASSWORD})
        if response.status_code == 409:
            response=client.post("/api/users/login",json={"email":EMAIL,"password":PASSWORD})
        response.raise_for_status()
        data=response.json()
        user_id=data["user"]["id"]
        client.headers["Authorization"]="Bearer "+data["access_token"]
        response=client.get("/api/projects")
        response.raise_for_status()
        if any(project["name"]=="Запуск таск-трекера" for project in response.json()):
            print("Demo project already exists.")
            return
        response=client.post("/api/projects",json={"name":"Запуск таск-трекера","description":"От идеи до первого релиза. Делаем работу команды чуть проще."})
        response.raise_for_status()
        project_id=response.json()["id"]
        today=datetime.now(timezone.utc).date()
        tasks=[
            ("Подготовить документацию API","Описать запросы, ответы и примеры для команды.","todo","medium",4,False),
            ("Настроить почтовые уведомления","Подключить SMTP и проверить доставку писем.","todo","low",6,False),
            ("Собрать доску задач","Карточки, фильтры по приоритету и поиск по названию.","in_progress","high",2,True),
            ("Подключить отчёты по проектам","Показать прогресс и количество задач по статусам.","in_progress","medium",-1,True),
            ("Проверить доступ участников","Участник видит только свои проекты и задачи.","review","high",1,True),
            ("Пройти сценарий регистрации","Проверить вход, ошибки формы и сохранение сессии.","review","low",3,False),
            ("Спроектировать модель данных","Пользователи, проекты, задачи и комментарии.","done","medium",-3,True),
            ("Собрать сервисы в Docker Compose","Единый запуск приложения и базы данных.","done","low",-2,True),
        ]
        for title,description,status,priority,days,assigned in tasks:
            response=client.post("/api/tasks",json={"project_id":project_id,"title":title,"description":description,
                "status":status,"priority":priority,"due_date":(today+timedelta(days=days)).isoformat(),"assignee_id":user_id if assigned else None})
            response.raise_for_status()
            if status=="review":
                client.post(f'/api/tasks/{response.json()["id"]}/comments',json={"body":"Готово к проверке. Посмотри, пожалуйста, когда будет время."}).raise_for_status()
        print(f"Demo created. Email: {EMAIL}; password: {PASSWORD}")


if __name__ == "__main__":
    main()
