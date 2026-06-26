# Prahari — Agentic Compliance Intelligence for Indian Banking

Prahari is a five-stage autonomous pipeline that ingests RBI/SEBI/DPDP regulatory
circulars, extracts Mandatory Action Points (MAPs) using an LLM, routes them to
bank departments, collects evidence, and validates evidence using a second
independent LLM agent. Everything is logged to an append-only audit trail.

## Architecture

```
Circular (URL/PDF)
  → Stage 1: Ingest (parse, deduplicate, hash)
  → Stage 2: Extract MAPs (Claude claude-sonnet-4-6)
  → Stage 3: Route (keyword + LLM fallback)
  → Stage 4: Evidence Intake (file upload → MinIO)
  → Stage 5: Judge Agent (independent Claude verdict)
  → Audit Trail (append-only, immutable)
```

## Tech Stack

| Layer    | Technology                                  |
|----------|---------------------------------------------|
| Backend  | Python 3.11, FastAPI, SQLAlchemy (async), Alembic |
| Database | PostgreSQL                                  |
| LLM      | Anthropic Claude API (claude-sonnet-4-6)           |
| Storage  | MinIO (S3-compatible)                       |
| Frontend | React + Vite + Tailwind CSS v4 + shadcn/ui  |
| PDF      | pdfplumber                                  |
| HTTP     | httpx, axios                                |

## Quick Start

### 1. Start infrastructure

```bash
docker-compose up -d
```

This starts PostgreSQL and MinIO.

### 2. Run database migrations

```bash
cd backend
alembic upgrade head
```

### 3. Set environment variables

Create a `.env` file in `backend/`:

```env
DATABASE_URL=postgresql+asyncpg://prahari:prahari@localhost:5432/prahari
ANTHROPIC_API_KEY=sk-ant-...
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=prahari-evidence
```

### 4. Start the backend

Run these commands from the project root (`prahari/`), not the parent `Prahar/` folder.

```bash
cd backend
python -m uvicorn main:app --reload
```

API docs available at: **http://localhost:8000/docs**

### 5. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend available at: **http://localhost:5173**

## Seed Data

To populate a sample circular with 3 MAPs for demo purposes:

```bash
cd backend
python seed.py
```

This creates an RBI IT Framework circular with 3 action points and routes them
to departments. Requires `ANTHROPIC_API_KEY` for MAP extraction; falls back
gracefully if not set.

## Ingest a Live Circular

1. Open **http://localhost:5173/ingest**
2. Paste an RBI/SEBI circular URL or upload a PDF
3. The system will automatically parse, extract MAPs, and route them

## API Endpoints

| Group       | Prefix             | Description                                |
|-------------|--------------------|--------------------------------------------|
| Ingest      | `/api/ingest`      | URL and PDF upload ingestion               |
| MAPs        | `/api/maps`        | List, detail, approve, reject MAP items    |
| Evidence    | `/api/evidence`    | Submit evidence files for MAPs             |
| Judgments   | `/api/judgments`   | Trigger LLM judgment, override, list       |
| Dashboard   | `/api/dashboard`   | Aggregated stats, circular/department view |
| Audit       | `/api/audit`       | Paginated audit log query + CSV export     |

## Frontend Pages

| Route                  | Page              | Description                          |
|------------------------|-------------------|--------------------------------------|
| `/`                    | Dashboard         | Stats, circulars table, review queue |
| `/ingest`              | IngestPage        | URL/PDF ingestion                    |
| `/circular/:id`        | CircularDetail    | MAPs with evidence/judgment actions  |
| `/department/:dept`    | DepartmentView    | Department-scoped MAP workspace      |
| `/audit`               | AuditPage         | Filterable audit trail + CSV export  |

## Project Structure

```
prahari/
  backend/
    app/
      api/           # FastAPI routers (7 routers)
      agents/        # LLM agents (extractor, judge)
      models/        # SQLAlchemy ORM models
      schemas/       # Pydantic validation schemas
      services/      # Business logic (ingest, routing, evidence)
      core/          # Config, database, MinIO client
      utils/         # PDF parser, hashing, date resolver
    tests/           # Integration tests (30 passing)
    alembic/         # Database migrations
    main.py          # Application entry point
    seed.py          # Demo data seeder
  frontend/
    src/
      api/           # Axios client + API wrappers
      components/    # StatusBadge, ConfidencePill, MapCard, AuditTable
      pages/         # Dashboard, CircularDetail, DepartmentView, IngestPage, AuditPage
      App.jsx        # Router + navigation
```
