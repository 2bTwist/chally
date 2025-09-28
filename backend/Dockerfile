FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy metadata first (better layer caching)
COPY pyproject.toml README.md /app/

# Copy code & tests
COPY app /app/app
COPY tests /app/tests
COPY alembic.ini /app/alembic.ini
COPY migrations /app/migrations

# Install project with dev extras (pytest, httpx, alembic)
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[dev]"

ENV ENVIRONMENT=dev \
    APP_NAME=peerpush-api \
    APP_VERSION=0.1.0 \
    API_HOST=0.0.0.0 \
    API_PORT=8000

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
