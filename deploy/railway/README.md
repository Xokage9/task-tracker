# Конфигурация Railway

Проект **tracker**, окружение **production**. Публичный адрес: [Трек](https://frontend-production-714fdaed.up.railway.app).

## Сервисы

| Сервис | Dockerfile / образ | Порт | Healthcheck |
|:---|:---|:---:|:---|
| core | `core/Dockerfile` | 8000 | `/health` |
| notifications | `notifications/Dockerfile` | 5000 | `/health` |
| reports | `reports/Dockerfile` | 5001 | `/health` |
| frontend | `frontend/Dockerfile` | 8080 | `/` |
| Postgres | `postgres:17-alpine` | 5432 | — |

Контекст сборки — корень репозитория: сервисам нужны общие `shared/` и `requirements-lock.txt`. У приложений выбран builder `DOCKERFILE`, путь к Dockerfile задаётся в настройках Railway и `RAILWAY_DOCKERFILE_PATH`.

Действующие сервисы получили исходники через Railway CLI. Автоматическое развёртывание из GitHub не включено. Идентификаторы ресурсов и параметры хранения находятся в [deployment.json](deployment.json).

## Переменные окружения

`JWT_SECRET` и `SERVICE_TOKEN` хранятся в shared variables Railway. Core и notifications используют ссылки `${{shared.JWT_SECRET}}` и `${{shared.SERVICE_TOKEN}}`. Пароль PostgreSQL хранится в переменной сервиса `POSTGRES_PASSWORD`. Значения секретов в репозиторий не включаются.

| Сервис | Переменная | Значение |
|:---|:---|:---|
| Postgres | `POSTGRES_USER` / `POSTGRES_DB` | `tracker` / `tracker` |
| Postgres | `PGDATA` | `/var/lib/postgresql/data/pgdata` |
| core | `DATABASE_URL` | `postgresql+psycopg://${{Postgres.POSTGRES_USER}}:${{Postgres.POSTGRES_PASSWORD}}@${{Postgres.RAILWAY_PRIVATE_DOMAIN}}:5432/${{Postgres.POSTGRES_DB}}` |
| core | `ROOT_PATH` / `PORT` | `/api` / `8000` |
| core | `OUTBOX_EMBEDDED` | `true` |
| core | `NOTIFICATIONS_URL` | `http://${{notifications.RAILWAY_PRIVATE_DOMAIN}}:5000` |
| notifications | `PORT` / `NOTIFICATIONS_DB` | `5000` / `/data/notifications.db` |
| reports | `PORT` / `CORE_URL` | `5001` / `http://${{core.RAILWAY_PRIVATE_DOMAIN}}:8000` |
| frontend | `PORT` | `8080` |
| frontend | `CORE_UPSTREAM` | `${{core.RAILWAY_PRIVATE_DOMAIN}}:8000` |
| frontend | `NOTIFICATIONS_UPSTREAM` | `${{notifications.RAILWAY_PRIVATE_DOMAIN}}:5000` |
| frontend | `REPORTS_UPSTREAM` | `${{reports.RAILWAY_PRIVATE_DOMAIN}}:5001` |

`OUTBOX_EMBEDDED=true` включает поток доставки событий внутри единственного процесса Core. Это позволяет разместить приложение в пяти сервисах. В Docker Compose обработчик outbox выделен в отдельный контейнер.

## Хранилища и сеть

| Том | Размер | Точка монтирования |
|:---|:---:|:---|
| `postgres-data` | 500 MB | `/var/lib/postgresql/data` |
| `notifications-data` | 500 MB | `/data` |

Entrypoint уведомлений задаёт владельца директории базы и через `gosu` передаёт процесс пользователю `app` с UID 10001.

Публичный домен подключён только к frontend, target port **8080**. Внутренние сервисы используют приватную сеть Railway. Nginx направляет `/api/` в Core, `/notify/` в notifications и `/reports-api/` в reports; внутренний приём событий `/notify/events` закрыт во внешнем прокси.

Для Nginx используется `frontend/nginx.conf.template`: адреса upstream и порт подставляются из переменных окружения. Настройки Docker Compose остаются в `docker-compose.yml`, шаблон локальных переменных — в `.env.example`.

## Почта

Внутренняя лента работает без SMTP. Для почтового обработчика предусмотрены `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM`, `SMTP_USER`, `SMTP_PASSWORD` и `SMTP_STARTTLS`. Значения по умолчанию: порт `587`, STARTTLS включён. Отдельного почтового обработчика в текущей схеме Railway нет.
