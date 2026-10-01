# Build from the repository root:  docker build -f backend/Dockerfile .
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv

WORKDIR /srv

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY ml/ ml/

RUN useradd --create-home evision
USER evision

EXPOSE 8000
# Apply migrations, then serve. PORT is set by most PaaS hosts (Render, Railway, Fly).
CMD ["sh", "-c", "alembic -c backend/alembic.ini upgrade head && uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-2}"]
