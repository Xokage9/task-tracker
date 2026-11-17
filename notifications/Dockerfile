FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-lock.txt ./
COPY notifications/requirements.txt notifications/requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends gosu && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r notifications/requirements.txt \
    && useradd --uid 10001 --create-home app && mkdir /data && chown app:app /data
COPY shared ./shared
COPY notifications ./notifications
COPY notifications/entrypoint.sh /usr/local/bin/notifications-entrypoint
RUN chmod +x /usr/local/bin/notifications-entrypoint
ENTRYPOINT ["notifications-entrypoint"]
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--access-logfile", "-", "notifications.app:create_app()"]
