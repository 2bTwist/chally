# Use Alpine for smaller attack surface and fewer vulnerabilities
FROM python:3.13-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Etc/UTC

# Install security updates and required packages
# Update package list, upgrade all packages to latest security patches
RUN apk update && apk upgrade && \
    # Try to install the latest OpenSSL version with security fixes
    apk add --no-cache \
        'openssl>=3.5.4-r0' \
        curl \
        ca-certificates \
        build-base \
        tzdata \
        libffi-dev \
        openssl-dev \
    && rm -rf /var/cache/apk/* \
    # Verify OpenSSL version for security
    && openssl version

WORKDIR /app

# Copy metadata first (better layer caching)
COPY pyproject.toml README.md /app/

# Copy code & tests
COPY app /app/app
COPY tests /app/tests
COPY alembic.ini /app/alembic.ini
COPY migrations /app/migrations

# Create non-root user for security
RUN addgroup -g 1001 -S appuser && \
    adduser -u 1001 -S appuser -G appuser

# Install project with dev extras (pytest, httpx, alembic)
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[dev]"

# Change ownership of the app directory to the non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Accept Git SHA as build argument
ARG GIT_SHA=dev

ENV ENVIRONMENT=dev \
    APP_NAME=chally-api \
    APP_DISPLAY_NAME=Chally \
    APP_VERSION=0.1.0 \
    GIT_SHA=${GIT_SHA} \
    API_HOST=0.0.0.0 \
    API_PORT=8000

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
