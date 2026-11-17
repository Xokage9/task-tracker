FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-lock.txt ./
COPY core/requirements.txt core/requirements.txt
RUN pip install --no-cache-dir -r core/requirements.txt && useradd --uid 10001 --create-home app
COPY shared ./shared
COPY core ./core
USER app
EXPOSE 8000
CMD ["uvicorn", "core.main:app", "--host", "0.0.0.0", "--port", "8000"]
