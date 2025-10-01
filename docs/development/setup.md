# Development Setup Guide

## Overview

This guide provides comprehensive instructions for setting up a local development environment for PeerPush, including all dependencies, services, and development tools.

## Prerequisites

### System Requirements
- **Operating System**: macOS 10.15+, Ubuntu 18.04+, or Windows 10 with WSL2
- **Memory**: 8GB RAM minimum, 16GB recommended
- **Storage**: 20GB free space for development environment
- **Network**: Stable internet connection for external service integration

### Required Software

#### Core Development Tools
```bash
# Python 3.11 or higher
python3 --version  # Should show 3.11+

# Package manager
pip --version

# Git version control
git --version

# Docker and Docker Compose
docker --version
docker-compose --version

# Node.js (for frontend development)
node --version  # v18+ recommended
npm --version
```

#### Database Systems
```bash
# PostgreSQL 15+
psql --version

# Redis 7+
redis-cli --version
```

#### Development Environment Tools
```bash
# Code editor (recommended)
code --version  # VS Code

# API testing tools
curl --version
# Postman or Insomnia (GUI alternative)

# Environment management
pyenv --version  # Python version management
```

## Quick Setup (Recommended)

### 1. Repository Setup
```bash
# Clone the repository
git clone https://github.com/2bTwist/peerpush.git
cd peerpush

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Development tools
```

### 2. Environment Configuration
```bash
# Copy environment template
cp .env.example .env.dev

# Edit environment variables
nano .env.dev  # or use your preferred editor
```

**Required Environment Variables**:
```bash
# Database Configuration
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/peerpush_dev
REDIS_URL=redis://localhost:6379/0

# JWT Configuration
JWT_SECRET=your-super-secret-jwt-key-at-least-32-characters-long
ACCESS_TTL_MIN=15
REFRESH_TTL_MIN=10080

# Stripe Configuration (Test Mode)
STRIPE_SECRET_KEY=sk_test_your_stripe_test_secret_key
STRIPE_PUBLISHABLE_KEY=pk_test_your_stripe_test_publishable_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret

# File Storage Configuration
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=peerpush-dev

# API Configuration
API_HOST=http://localhost:8000
CORS_ORIGINS=http://localhost:3000,http://localhost:8080

# Email Configuration (Optional for development)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

### 3. Infrastructure Services
```bash
# Start all required services
docker-compose -f infra/compose.dev.yml up -d

# Verify services are running
docker-compose -f infra/compose.dev.yml ps

# Expected output:
# NAME                COMMAND                  SERVICE             STATUS              PORTS
# peerpush-db-1       "docker-entrypoint.s…"   db                  running             0.0.0.0:5432->5432/tcp
# peerpush-redis-1    "docker-entrypoint.s…"   redis               running             0.0.0.0:6379->6379/tcp
# peerpush-minio-1    "/usr/bin/docker-ent…"   minio               running             0.0.0.0:9000-9001->9000-9001/tcp
```

### 4. Database Setup
```bash
# Run database migrations
alembic upgrade head

# Verify database tables
docker-compose -f infra/compose.dev.yml exec db psql -U postgres -d peerpush_dev -c "\dt"

# Create initial data (optional)
python scripts/create_sample_data.py
```

### 5. Start Development Server
```bash
# Start FastAPI development server
uvicorn main:app --reload --port 8000 --log-level debug

# Server should start at http://localhost:8000
# API documentation available at http://localhost:8000/docs
```

### 6. Verify Setup
```bash
# Test API health check
curl http://localhost:8000/health

# Expected response:
# {"status": "healthy", "timestamp": "2025-09-30T12:00:00Z"}

# Test database connection
curl http://localhost:8000/health/db

# Test Redis connection
curl http://localhost:8000/health/redis
```

## Detailed Setup Instructions

### Python Environment Management

#### Using pyenv (Recommended)
```bash
# Install pyenv (macOS)
brew install pyenv

# Install pyenv (Ubuntu)
curl https://pyenv.run | bash

# Install Python 3.11
pyenv install 3.11.5
pyenv local 3.11.5

# Create virtual environment
python -m venv venv
source venv/bin/activate
```

#### Using conda (Alternative)
```bash
# Create conda environment
conda create -n peerpush python=3.11
conda activate peerpush

# Install pip dependencies
pip install -r requirements.txt
```

### Database Configuration

#### PostgreSQL Setup

**Using Docker (Recommended)**:
```bash
# Already included in docker-compose.dev.yml
docker-compose -f infra/compose.dev.yml up -d db
```

**Local Installation**:
```bash
# macOS
brew install postgresql@15
brew services start postgresql@15

# Ubuntu
sudo apt update
sudo apt install postgresql-15 postgresql-contrib

# Create database and user
sudo -u postgres psql
CREATE DATABASE peerpush_dev;
CREATE USER peerpush_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE peerpush_dev TO peerpush_user;
\q
```

#### Redis Setup

**Using Docker (Recommended)**:
```bash
# Already included in docker-compose.dev.yml
docker-compose -f infra/compose.dev.yml up -d redis
```

**Local Installation**:
```bash
# macOS
brew install redis
brew services start redis

# Ubuntu
sudo apt install redis-server
sudo systemctl start redis-server
```

### File Storage Setup

#### MinIO (S3-Compatible Storage)
```bash
# Start MinIO service
docker-compose -f infra/compose.dev.yml up -d minio

# Access MinIO console at http://localhost:9001
# Username: minioadmin
# Password: minioadmin

# Create development bucket
mc alias set myminio http://localhost:9000 minioadmin minioadmin
mc mb myminio/peerpush-dev
mc policy set public myminio/peerpush-dev
```

### Stripe Configuration

#### Test Account Setup
1. **Create Stripe Account**: Visit [stripe.com](https://stripe.com) and create test account
2. **Get API Keys**: Navigate to Developers > API Keys
3. **Copy Test Keys**: Use test keys (starting with `sk_test_` and `pk_test_`)
4. **Webhook Setup**: Configure webhook endpoint for local development

#### Webhook Configuration
```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe  # macOS
# or download from https://github.com/stripe/stripe-cli/releases

# Login to Stripe
stripe login

# Forward webhooks to local development
stripe listen --forward-to localhost:8000/stripe/webhook

# Copy webhook signing secret from CLI output
# Add to .env.dev as STRIPE_WEBHOOK_SECRET
```

## Development Workflow

### Code Organization

```
peerpush/
├── app/                    # Main application code
│   ├── api/               # API route handlers
│   ├── core/              # Core configuration and utilities
│   ├── models/            # SQLAlchemy models
│   ├── schemas/           # Pydantic schemas
│   ├── services/          # Business logic services
│   └── utils/             # Utility functions
├── alembic/               # Database migrations
├── docs/                  # Documentation
├── infra/                 # Infrastructure configuration
├── scripts/               # Utility scripts
├── tests/                 # Test suite
├── requirements.txt       # Python dependencies
├── requirements-dev.txt   # Development dependencies
└── main.py               # Application entry point
```

### Development Commands

#### Database Management
```bash
# Create new migration
alembic revision --autogenerate -m "Add new feature"

# Run migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1

# Reset database (CAUTION: Destroys all data)
alembic downgrade base
alembic upgrade head
```

#### Testing
```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=app tests/

# Run specific test file
pytest tests/test_auth.py

# Run tests in watch mode
pytest-watch

# Generate coverage report
pytest --cov=app --cov-report=html tests/
```

#### Code Quality
```bash
# Format code with black
black app/ tests/

# Check code style
flake8 app/ tests/

# Type checking
mypy app/

# Import sorting
isort app/ tests/

# All quality checks
make lint  # If Makefile is configured
```

#### Development Server Options
```bash
# Standard development server
uvicorn main:app --reload --port 8000

# With debug logging
uvicorn main:app --reload --port 8000 --log-level debug

# With specific host binding
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# With custom configuration
uvicorn main:app --reload --env-file .env.dev
```

### VS Code Setup

#### Recommended Extensions
```json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.black-formatter",
    "ms-python.flake8",
    "ms-python.mypy-type-checker",
    "ms-python.isort",
    "ms-vscode.vscode-json",
    "redhat.vscode-yaml",
    "ms-vscode.docker",
    "bradlc.vscode-tailwindcss",
    "esbenp.prettier-vscode"
  ]
}
```

#### Workspace Settings
```json
{
  "python.defaultInterpreterPath": "./venv/bin/python",
  "python.formatting.provider": "black",
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.linting.mypyEnabled": true,
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  },
  "files.exclude": {
    "**/__pycache__": true,
    "**/*.pyc": true,
    ".coverage": true,
    "htmlcov/": true
  }
}
```

#### Debug Configuration
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI Development",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/venv/bin/uvicorn",
      "args": ["main:app", "--reload", "--port", "8000"],
      "console": "integratedTerminal",
      "envFile": "${workspaceFolder}/.env.dev",
      "cwd": "${workspaceFolder}"
    },
    {
      "name": "Run Tests",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": ["tests/", "-v"],
      "console": "integratedTerminal",
      "cwd": "${workspaceFolder}"
    }
  ]
}
```

## Advanced Development Setup

### Pre-commit Hooks
```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

**Pre-commit Configuration** (`.pre-commit-config.yaml`):
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.7.0
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
        additional_dependencies: [flake8-docstrings]

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
        args: ["--profile", "black"]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.4.1
    hooks:
      - id: mypy
        additional_dependencies: [types-requests, types-redis]
```

### Docker Development Environment

#### Complete Docker Setup
```bash
# Build development image
docker build -f Dockerfile.dev -t peerpush:dev .

# Run with docker-compose
docker-compose -f docker-compose.dev.yml up --build

# Access container for debugging
docker-compose -f docker-compose.dev.yml exec app bash
```

**Docker Compose Development Configuration**:
```yaml
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile.dev
    ports:
      - "8000:8000"
    volumes:
      - .:/app
      - /app/venv  # Prevent overwriting venv
    environment:
      - PYTHONPATH=/app
    env_file:
      - .env.dev
    depends_on:
      - db
      - redis
      - minio
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload

  db:
    image: postgres:15
    environment:
      POSTGRES_DB: peerpush_dev
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  minio:
    image: minio/minio:latest
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - minio_data:/data
    command: server /data --console-address ":9001"

volumes:
  postgres_data:
  minio_data:
```

### Performance Development Tools

#### Database Performance Monitoring
```bash
# Install PostgreSQL extensions
docker-compose -f infra/compose.dev.yml exec db psql -U postgres -d peerpush_dev

# Enable query logging
ALTER SYSTEM SET log_statement = 'all';
ALTER SYSTEM SET log_min_duration_statement = 100;  -- Log slow queries
SELECT pg_reload_conf();

# Monitor query performance
SELECT query, calls, total_time, mean_time 
FROM pg_stat_statements 
ORDER BY total_time DESC 
LIMIT 10;
```

#### API Performance Profiling
```python
# Add to development dependencies
# pip install py-spy line_profiler memory_profiler

# Profile API endpoints
@profile  # Add this decorator to functions
def slow_function():
    # Your code here
    pass

# Run with profiling
kernprof -l -v your_script.py

# Memory profiling
python -m memory_profiler your_script.py
```

#### Load Testing Setup
```bash
# Install locust for load testing
pip install locust

# Create load test file (locustfile.py)
from locust import HttpUser, task, between

class PeerPushUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        # Login and get token
        response = self.client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "testpassword"
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    @task(3)
    def get_challenges(self):
        self.client.get("/challenges", headers=self.headers)
    
    @task(1)
    def get_wallet(self):
        self.client.get("/wallet", headers=self.headers)

# Run load test
locust -f locustfile.py --host=http://localhost:8000
```

## Testing Setup

### Test Database Configuration
```bash
# Create test database
docker-compose -f infra/compose.dev.yml exec db psql -U postgres -c "CREATE DATABASE peerpush_test;"

# Set test environment variables
export DATABASE_URL_TEST=postgresql://postgres:postgres@localhost:5432/peerpush_test
export REDIS_URL_TEST=redis://localhost:6379/1
```

### Pytest Configuration
**pytest.ini**:
```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
python_classes = Test*
addopts = 
    -v
    --strict-markers
    --strict-config
    --tb=short
    --cov=app
    --cov-report=term-missing
    --cov-report=html:htmlcov
    --cov-fail-under=80
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    slow: Slow running tests
```

### Test Structure
```
tests/
├── conftest.py           # Test configuration and fixtures
├── unit/                 # Unit tests
│   ├── test_models.py
│   ├── test_services.py
│   └── test_utils.py
├── integration/          # Integration tests
│   ├── test_api.py
│   ├── test_database.py
│   └── test_redis.py
├── e2e/                 # End-to-end tests
│   ├── test_user_flow.py
│   └── test_challenge_flow.py
└── fixtures/            # Test data and fixtures
    ├── sample_users.json
    └── sample_challenges.json
```

## Troubleshooting

### Common Issues

#### Database Connection Errors
```bash
# Check if PostgreSQL is running
docker-compose -f infra/compose.dev.yml ps db

# Check database logs
docker-compose -f infra/compose.dev.yml logs db

# Reset database connection
docker-compose -f infra/compose.dev.yml restart db

# Verify connection manually
psql postgresql://postgres:postgres@localhost:5432/peerpush_dev
```

#### Redis Connection Issues
```bash
# Test Redis connection
redis-cli -h localhost -p 6379 ping

# Check Redis logs
docker-compose -f infra/compose.dev.yml logs redis

# Clear Redis cache
redis-cli -h localhost -p 6379 FLUSHDB
```

#### Stripe Webhook Issues
```bash
# Verify webhook endpoint
curl -X POST http://localhost:8000/stripe/webhook \
  -H "Content-Type: application/json" \
  -d '{"type": "test.event"}'

# Check Stripe CLI status
stripe listen --forward-to localhost:8000/stripe/webhook

# Verify webhook secret
echo $STRIPE_WEBHOOK_SECRET
```

#### File Upload Issues
```bash
# Check MinIO access
curl http://localhost:9000/minio/health/live

# Access MinIO console
open http://localhost:9001

# Verify bucket exists
mc ls myminio/peerpush-dev
```

### Development Performance Tips

#### Database Optimization
- Use database connection pooling
- Add indexes for frequently queried fields
- Use EXPLAIN ANALYZE for slow queries
- Implement query result caching with Redis

#### API Response Time
- Implement response caching for static data
- Use async/await for I/O operations
- Optimize serialization with orjson
- Implement request rate limiting

#### Memory Usage
- Monitor memory usage with memory_profiler
- Use generators for large data sets
- Implement pagination for list endpoints
- Clear unused variables and references

### Debug Configuration

#### Logging Setup
```python
# Development logging configuration
import logging
import sys

# Configure root logger
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/development.log')
    ]
)

# Configure specific loggers
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
logging.getLogger('uvicorn.access').setLevel(logging.INFO)
```

#### Debug Middleware
```python
# Add to FastAPI app for request/response logging
@app.middleware("http")
async def debug_middleware(request: Request, call_next):
    start_time = time.time()
    
    # Log request
    logger.debug(f"Request: {request.method} {request.url}")
    
    response = await call_next(request)
    
    # Log response
    process_time = time.time() - start_time
    logger.debug(f"Response: {response.status_code} ({process_time:.3f}s)")
    
    return response
```

---

*This setup guide provides everything needed for productive PeerPush development. Follow the Quick Setup for immediate development, or use the Detailed Setup for customized environments.*