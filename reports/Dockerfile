FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-lock.txt ./
COPY reports/requirements.txt reports/requirements.txt
RUN pip install --no-cache-dir -r reports/requirements.txt && useradd --uid 10001 --create-home app
COPY reports ./reports
USER app
EXPOSE 5001
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "2", "--threads", "2", "--access-logfile", "-", "reports.app:create_app()"]
