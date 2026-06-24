# Douyin Shop Automation

Automated operations platform for Douyin (TikTok China) e-commerce shops. Handles order processing, inventory sync, product management, and scheduled tasks via a FastAPI backend with Celery workers.

## Quick Start

```bash
# Clone and configure
cp backend/.env.example backend/.env
# Edit backend/.env with your credentials

# Install frontend dependencies
cd frontend && npm install

# Start the website
cd ..
make dev

# Start all services
cd docker
docker-compose up -d

# Run database migrations
docker-compose exec app alembic upgrade head
```

The API will be available at http://localhost:8000. Interactive docs at http://localhost:8000/docs.
The frontend will be available at http://127.0.0.1:3000.

## Project Structure

```
douyin-shop-automation/
├── backend/                # FastAPI application
│   ├── app/
│   │   ├── api/            # Route handlers
│   │   ├── core/           # Config, security, celery setup
│   │   ├── db/             # Database session and base model
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── schemas/        # Pydantic request/response schemas
│   │   ├── services/       # Business logic layer
│   │   ├── tasks/          # Celery async tasks
│   │   └── main.py         # Application entrypoint
│   ├── alembic/            # Database migrations
│   ├── alembic.ini         # Alembic configuration
│   ├── requirements.txt    # Python dependencies
│   └── .env.example        # Environment variable template
├── docker/
│   ├── Dockerfile          # Multi-stage Python build
│   └── docker-compose.yml  # Service orchestration
└── .gitignore
```

## Modules

| Module | Description |
|--------|-------------|
| **API** | RESTful endpoints for orders, products, inventory, and shop config |
| **Services** | Douyin Open API integration, order fulfillment logic, inventory sync |
| **Tasks** | Celery workers for async jobs: order polling, stock updates, notifications |
| **Beat** | Scheduled tasks: periodic sync, report generation, health checks |
| **DB** | PostgreSQL with async SQLAlchemy, Alembic migrations |
| **Cache** | Redis for task broker, result backend, and application caching |

## Development

```bash
# Run tests
docker-compose exec app pytest

# Create a new migration
docker-compose exec app alembic revision --autogenerate -m "description"

# View logs
docker-compose logs -f app worker
```
