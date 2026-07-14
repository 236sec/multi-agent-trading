# PROJECT.md — Multi-Agent Trading System

## 0.1 — Project Scaffolding ✅

**Completed:** 2026-07-14

### What was done
- Added deps: `typer`, `pydantic`, `pydantic-settings`, `pyyaml`, `fastapi`, `uvicorn[standard]`
- Created `backend/src/trading/` package with:
  - `config.py` — `Settings(BaseSettings)` loading `.env` + `config.yaml`
  - `cli.py` — Typer CLI: `trading serve` + `trading run {ingestion,signal,risk,execution}`
  - `api/app.py` — FastAPI with `/health` endpoint + CORS for `localhost:3000`
- Created `backend/config.yaml` with defaults (watchlist, risk, model, schedule, broker)
- Created `backend/.env.example`
- `[project.scripts]` entry point: `trading` → `trading.cli:app`

### Verification
```bash
uv run trading run signal    # → "not implemented"
uv run trading serve         # → uvicorn on :8000, /health → {"status":"ok"}
```

### Files
- `backend/pyproject.toml`
- `backend/src/trading/__init__.py`
- `backend/src/trading/config.py`
- `backend/src/trading/cli.py`
- `backend/src/trading/api/__init__.py`
- `backend/src/trading/api/app.py`
- `backend/config.yaml`
- `backend/.env.example`

## 0.2 — Database Layer ✅

**Completed:** 2026-07-14

### What was done
- Added deps: `sqlalchemy[asyncio]`, `asyncpg`, `alembic`
- Created `docker-compose.yml` at project root (PostgreSQL 16, port 5432)
- Created `backend/src/trading/db/` package with:
  - `models.py` — 9 SQLAlchemy 2.0 declarative models (Watchlist, MarketData, Position, PortfolioNAV, Signal, RiskDecision, Order, EventLog, MessageQueue) using `Mapped` typing, UUID PKs, timezone-aware timestamps, JSONB payloads, FK relationships
  - `session.py` — async engine/session factory using `async_sessionmaker`, reads URL from settings
  - `seed.py` — `run_seed()` seeds watchlist from config.yaml
  - `__init__.py` — empty
- Configured Alembic:
  - `alembic/env.py` — async, reads `DATABASE_URL` from env, imports models
  - `alembic.ini` — commented out `sqlalchemy.url` (set in env.py)
- Created initial migration `alembic/versions/001_initial_schema.py` (all 9 tables with FKs, indexes, constraints)
- Extended CLI with `trading db init` and `trading db seed` commands

### Verification
```bash
uv run alembic upgrade head --sql   # generates correct SQL for all 9 tables
uv run python -c "from trading.db.models import Base; print(len(Base.metadata.tables))"  # → 9
uv run trading db --help            # shows seed + init commands
```

### Files
- `docker-compose.yml`
- `backend/pyproject.toml` (updated deps)
- `backend/src/trading/db/__init__.py`
- `backend/src/trading/db/models.py`
- `backend/src/trading/db/session.py`
- `backend/src/trading/db/seed.py`
- `backend/alembic/env.py`
- `backend/alembic.ini`
- `backend/alembic/versions/001_initial_schema.py`
