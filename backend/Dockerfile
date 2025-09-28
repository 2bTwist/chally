FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml /app/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir "fastapi>=0.115" "uvicorn[standard]>=0.30" \
       "pydantic>=2.8" "python-json-logger>=2.0.7" "structlog>=24.1.0" \
       "redis>=5.0.7" "rq>=1.16.2" "asyncpg>=0.29.0" "SQLAlchemy[asyncio]>=2.0.34" \
       "pytest>=8.3" "httpx>=0.27"

COPY app /app/app
COPY tests /app/tests

ENV ENVIRONMENT=dev \
    APP_NAME=peerpush-api \
    APP_VERSION=0.1.0 \
    API_HOST=0.0.0.0 \
    API_PORT=8000

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
