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

## 1.3 — FeatureEngine ✅

**Completed:** 2026-07-14

### What was done
- Added deps: `pandas>=2.0.0`, `numpy>=1.24.0`, `pytest>=8.0.0` (dev)
- Created `backend/src/trading/features/` package with:
  - `engine.py` — `FeatureEngine` class: `compute(ohlcv_df) → features_df`, `list_features()`, `validate_features()`
  - `__init__.py` — exports FeatureEngine
- 21 technical indicators computed from OHLCV: returns (4), SMA ratios (4), EMA ratios (2), RSI, MACD (3), ATR normalized, volume profile (3), annualized volatility (3)
- All computation is pure pandas/numpy — zero external TA libraries
- Null/missing value handling: `min_periods` on all rolling windows propagates NaN safely; `validate_features()` rejects DataFrames with NaN/Inf in the latest row
- Structured logging via `logging.getLogger(__name__)`: logs input quality (NaN presence, row count), output summary (feature count, latest-row NaN columns)

### Verification
```bash
uv run pytest tests/ -v              # 9 tests, all pass
uv run python -c "from trading.features import FeatureEngine; print(len(FeatureEngine.list_features()))"  # → 21
```

### Test scenarios
| Test | What it verifies |
|---|---|
| `test_rising_prices_rsi_high` | RSI > 70 for monotonic uptrend |
| `test_falling_prices_rsi_low` | RSI < 30 for monotonic downtrend |
| `test_constant_prices_returns_zero` | Flat prices → returns ≈ 0, volatility ≈ 0 |
| `test_output_shape` | Correct columns, index preserved |
| `test_list_features_matches_output` | 21 features, all subset of compute() output |
| `test_validate_features_passes` | Valid df passes validation |
| `test_validate_features_fails_missing_column` | Missing column → fail |
| `test_validate_features_fails_nan_in_latest` | NaN in latest row → fail |
| `test_missing_columns_raises` | compute() raises ValueError on bad input |

### Design decisions
- **21 not 20 features**: the original plan estimated 20; actual implementation is 21 (4 returns + 4 SMA + 2 EMA + 4 oscillators + 1 ATR + 3 volume + 3 volatility). `list_features()` and tests are self-consistent.
- **Log-level checks not assertions**: logging calls are NOT asserted in tests (would couple tests to log format). Tests verify behavior (output values, validation results).
- **No ta / ta-lib dependency**: all indicators computed with pandas rolling/ewm operations to keep the dependency footprint small and the code transparent.

### Files
- `backend/pyproject.toml` (+pandas, +numpy, +pytest dev dep)
- `backend/src/trading/features/__init__.py`
- `backend/src/trading/features/engine.py`
- `backend/tests/__init__.py`
- `backend/tests/test_features.py`
