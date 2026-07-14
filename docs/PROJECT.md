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
