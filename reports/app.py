import csv
import io
import os
from collections import Counter
from datetime import date, datetime, timezone

import httpx
from dotenv import load_dotenv
from pyramid.config import Configurator
from pyramid.httpexceptions import HTTPException
from pyramid.response import Response

STATUS_NAMES = {"todo": "К работе", "in_progress": "В работе", "review": "На проверке", "done": "Готово"}
PRIORITY_NAMES = {"low": "Низкий", "medium": "Средний", "high": "Высокий"}


def aggregate(snapshot, today=None):
    today = today or datetime.now(timezone.utc).date()
    tasks = snapshot["tasks"]
    statuses = Counter(task["status"] for task in tasks)
    priorities = Counter(task["priority"] for task in tasks)
    completed = statuses["done"]
    overdue = [t for t in tasks if t["due_date"] and date.fromisoformat(t["due_date"]) < today and t["status"] != "done"]
    return {
        "project": snapshot["project"], "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(tasks), "completed": completed, "overdue": len(overdue),
        "completion_percent": round(completed * 100 / len(tasks), 1) if tasks else 0,
        "by_status": {key: statuses[key] for key in STATUS_NAMES},
        "by_priority": {key: priorities[key] for key in PRIORITY_NAMES},
        "workload": [{"assignee_id": key, "tasks": value} for key, value in
                     Counter(t["assignee_id"] for t in tasks if t["status"] != "done").items()],
    }


def csv_cell(value):
    text = "" if value is None else str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) or text.startswith(("\t", "\r")) else text


def make_csv(snapshot):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["ID", "Задача", "Статус", "Приоритет", "ID исполнителя", "Срок", "Создана", "Завершена"])
    for task in snapshot["tasks"]:
        writer.writerow([csv_cell(v) for v in [task["id"], task["title"], STATUS_NAMES[task["status"]],
                         PRIORITY_NAMES[task["priority"]], task["assignee_id"], task["due_date"],
                         task["created_at"], task["completed_at"]]])
    return "\ufeff" + output.getvalue()


def create_app(fetcher=None):
    load_dotenv()

    def report(request):
        authorization = request.headers.get("Authorization", "")
        if not authorization.lower().startswith("bearer "):
            return Response(json_body={"detail": "Нужно войти в аккаунт"}, status=401)
        project_id = int(request.matchdict["project_id"])
        try:
            if fetcher:
                response = fetcher(project_id, authorization)
            else:
                response = httpx.get(os.getenv("CORE_URL", "http://core:8000") + f"/projects/{project_id}/report-data",
                                     headers={"Authorization": authorization}, timeout=10, trust_env=False)
            if response.status_code in (401, 403, 404):
                return Response(json_body={"detail": "Проект недоступен или сеанс истёк"}, status=response.status_code)
            response.raise_for_status()
            snapshot = response.json()
            if request.matched_route.name == "report_csv":
                result = Response(body=make_csv(snapshot).encode("utf-8"), content_type="text/csv", charset="utf-8")
                result.headers["Content-Disposition"] = f'attachment; filename="project-{project_id}.csv"'
            else:
                result = Response(json_body=aggregate(snapshot))
            result.headers["Cache-Control"] = "no-store"
            return result
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return Response(json_body={"detail": "Не удалось построить отчёт. Попробуйте позже."}, status=503)

    with Configurator() as config:
        config.add_route("health", "/health")
        config.add_view(lambda request: {"status": "ok", "service": "reports"}, route_name="health", renderer="json", request_method="GET")
        config.add_route("report_csv", r"/reports/projects/{project_id:\d+}.csv")
        config.add_route("report", r"/reports/projects/{project_id:\d+}")
        for name in ("report_csv", "report"):
            config.add_view(report, route_name=name, request_method="GET")
            config.add_view(lambda request: Response(json_body={"detail": "Method Not Allowed"}, status=405,
                                                     headerlist=[("Content-Type", "application/json"), ("Allow", "GET")]),
                            route_name=name)
        config.add_exception_view(lambda error, request: Response(json_body={"detail": error.title}, status=error.status_code),
                                  context=HTTPException)
        return config.make_wsgi_app()
