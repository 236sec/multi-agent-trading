# TODO — Multi-Agent Trading System

> Each completed task: update `docs/PROJECT.md` with summary + links.

---

## Phase 0: Foundation

### [x] 0.1 — Project scaffolding ✅ 2026-07-14
- `backend/pyproject.toml`: deps (typer, pydantic, pydantic-settings, pyyaml, fastapi, uvicorn)
- `backend/src/trading/cli.py`: Typer CLI with `trading run <agent>` subcommands (stubs) + `trading serve`
- `backend/src/trading/config.py`: load `.env` + `config.yaml` into typed Settings (pydantic-settings)
- `backend/src/trading/api/app.py`: FastAPI with `/health` endpoint + CORS
- `backend/.env.example`, `backend/config.yaml`
- Verify: `trading run signal` prints "not implemented", `trading serve` → `/health` returns ok

### [x] 0.2 — Database schema + migrations ✅ 2026-07-14
- Docker Compose: PostgreSQL 16
- Alembic init + migration for all 9 tables (SPEC.md schema)
- SQLAlchemy models (`backend/src/trading/db/models.py`)
- Seed script: insert sample watchlist rows
- Verify: `psql` — all tables exist, watchlist populated

---

## Phase 1: Deep Modules (shared libraries, no agents yet)

### [ ] 1.1 — MessageQueue module
- `backend/src/trading/db/queue.py`
- `enqueue()`, `dequeue()` with `FOR UPDATE SKIP LOCKED`, `ack()`, `nack()`
- Unit tests: state machine transitions (pending→processing→done/failed)
- Integration tests: concurrent consumers against test DB
- **Blocks**: 0.2 (needs DB)

### [ ] 1.2 — MarketData module
- `backend/src/trading/data/market.py`
- `fetch_daily()` via yfinance, `cache_ohlcv()` upsert to `market_data`, `get_cached()`
- Rate-limit handling, validation
- Unit tests: response parsing, validation
- Integration tests: cache hit/miss with mocked yfinance (httpx transport)
- **Blocks**: 0.2

### [x] 1.3 — FeatureEngine module ✅ 2026-07-14
- `backend/src/trading/features/engine.py`
- `compute(ohlcv_df) → features_df`
- Indicators: SMA, EMA, RSI, MACD, ATR, volume profile, returns, volatility
- `list_features()`, `validate_features()`
- Unit tests: known OHLCV fixtures → expected indicator values
- **Blocks**: nothing (pure computation)

### [ ] 1.4 — Webull Broker spike
- Research spike — NOT production code
- Register for Webull OpenAPI, create paper account
- Script: OAuth flow → place market/limit/bracket orders → query status/positions
- Document: auth lifecycle, rate limits, API contract in `docs/webull-spike.md`
- **Blocks**: nothing (external research)

### [ ] 1.5 — Broker module
- `backend/src/trading/broker/webull.py`
- Implement `Broker` interface: `place_order()`, `get_positions()`, `get_account()`, `cancel_order()`
- Token refresh logic, error handling
- Unit tests: request serialization, response parsing, auth header (mocked HTTP)
- **Blocks**: 1.4 (needs spike results)

### [ ] 1.6 — RiskEngine module
- `backend/src/trading/risk/engine.py`
- `evaluate(signal, portfolio) → RiskDecision`
- Three rules via strategy pattern: `PositionSizeRule`, `SectorConcentrationRule`, `DrawdownRule`
- Downsizing logic (reduce quantity vs reject)
- Unit tests: each rule in isolation, interaction of multiple rules
- **Blocks**: 0.1 (needs config for thresholds)

---

## Phase 2: ML Model Training (research)

### [ ] 2.1 — Train initial signal model
- `backend/notebooks/01_feature_exploration.ipynb`: explore features from FeatureEngine
- `backend/notebooks/02_model_training.ipynb`: XGBoost classifier for next-day direction
- Serialize model → `backend/models/signal_v1.pkl`
- Save feature importance, evaluation metrics
- Verify: model loads and predicts from notebook
- **Blocks**: 1.3 (needs features), 1.2 (needs historical data)

---

## Phase 3: Agents

### [ ] 3.1 — Data Ingestion agent
- `backend/src/trading/agents/ingestion.py`
- Read watchlist from config → fetch OHLCV via MarketData → cache to DB
- Enqueue `market_data_updated` message with ticker list
- CLI: `trading run ingestion`
- Integration test: mock yfinance → run agent → assert rows in `market_data` + queue msg
- **Blocks**: 1.1, 1.2

### [ ] 3.2 — Signal agent
- `backend/src/trading/agents/signal.py`
- Dequeue `market_data_updated` → load cached OHLCV → FeatureEngine.compute() → SignalModel.predict()
- Write signals to `signals` table, enqueue `signal_generated`
- CLI: `trading run signal`
- Integration test: seed market_data → run agent → assert signals in DB + queue msg
- **Blocks**: 1.1, 1.3, 2.1

### [ ] 3.3 — Risk agent
- `backend/src/trading/agents/risk.py`
- Dequeue `signal_generated` → load portfolio state → RiskEngine.evaluate() per signal
- Create `OrderRequest` in `orders` table (`approved_pending_human`), enqueue `order_approved`
- Write risk decisions to `risk_decisions` table
- CLI: `trading run risk`
- Integration test: seed signal → run agent → assert orders + risk_decisions in DB
- **Blocks**: 1.1, 1.6

### [ ] 3.4 — Execution agent
- `backend/src/trading/agents/execution.py`
- Dequeue `order_confirmed` (dispatched by API) → Broker.place_order()
- Update order status, enqueue `order_executed`
- CLI: `trading run execution`
- Integration test: seed confirmed order → run agent → assert order status updated
- **Blocks**: 1.1, 1.5

---

## Phase 4: API Layer

### [ ] 4.1 — FastAPI app skeleton
- `backend/src/trading/api/app.py`: FastAPI instance, CORS, lifespan
- `backend/src/trading/api/deps.py`: DB session dependency
- `backend/src/trading/api/routes/`: empty route files
- Verify: `uvicorn` starts, `/docs` shows OpenAPI

### [ ] 4.2 — REST endpoints
- `GET /api/portfolio`, `GET /api/portfolio/history`
- `GET /api/signals`, `GET /api/orders`
- `POST /api/orders/{id}/confirm`, `POST /api/orders/{id}/cancel`, `POST /api/orders/{id}/retry`
- `GET /api/agents/status`, `GET /api/events`
- Pydantic response models
- Integration tests with FastAPI TestClient
- **Blocks**: 4.1, 1.1 (queue for confirm/retry)

### [ ] 4.3 — WebSocket
- `backend/src/trading/api/ws.py`
- `WS /ws/pipeline`: accept → broadcast events from `event_log`
- Agent status push (idle/running/error)
- Integration test: connect WS → insert event → assert client receives
- **Blocks**: 4.1

---

## Phase 5: Frontend (Next.js)

### [ ] 5.1 — API client & WebSocket hook
- `frontend/src/lib/api.ts`: typed fetch wrappers for all endpoints
- `frontend/src/lib/useWebSocket.ts`: hook for pipeline WS
- SWR or React Query for data fetching

### [ ] 5.2 — Layout & navigation
- App shell with sidebar nav (Portfolio / Pipeline / History / Orders)
- Dark theme, responsive

### [ ] 5.3 — Portfolio view
- Equity curve chart (recharts), daily P&L card, positions table
- Drawdown gauge

### [ ] 5.4 — Pipeline view
- Agent status cards (ingestion/signal/risk/execution)
- Live updates via WebSocket
- Last run time, error state

### [ ] 5.5 — Trade History view
- Filterable table: date, ticker, signal, confidence, risk result, order status
- Click-through to full audit trail

### [ ] 5.6 — Pending Orders view
- Order queue with Approve/Reject buttons
- Failed orders with Retry button
- Confirm dialog with order details

---

## Phase 6: Integration & Polish

### [ ] 6.1 — Structured logging
- JSON log format: `{ts, agent, event, ...}` to stdout
- `event_log` DB writes for dashboard visibility
- All 4 agents log consistently

### [ ] 6.2 — Cron scheduling
- Crontab entries for ingestion (16:30), signal (17:00), risk (17:30)
- Each entry: `cd backend && trading run <agent>`
- Execution agent: run as long-lived process polling for confirmed orders (or on-demand)

### [ ] 6.3 — End-to-end integration test
- TestDB → seed watchlist + market_data
- Run ingestion → signal → risk in sequence
- Assert: signals in DB, risk_decisions in DB, orders with `approved_pending_human`
- Mock broker → confirm order via API → run execution → assert order filled

### [ ] 6.4 — README & docs
- `README.md`: setup instructions, architecture overview, how to run
- `docs/PROJECT.md`: final project summary
- Verify: fresh clone → follow README → running system

---

## Dependency Graph

```
0.1 (scaffolding) ─────────────────────────────────────────────────┐
0.2 (DB schema) ─────┬── 1.1 (MessageQueue) ──── 3.1 (Ingestion) ──┤
                     ├── 1.2 (MarketData) ────── 3.1 (Ingestion) ──┤
                     │                                              │
1.3 (FeatureEngine) ─┼── 2.1 (ML model) ──────── 3.2 (Signal) ─────┤
                     │                                              │
1.4 (Webull spike) ──┼── 1.5 (Broker) ────────── 3.4 (Execution) ──┤
                     │                                              │
0.1 ─────────────────┼── 1.6 (RiskEngine) ────── 3.3 (Risk) ────────┤
                     │                                              │
                     │    4.1 (API skeleton) ── 4.2 (REST) ─────────┤
                     │                       └─ 4.3 (WebSocket) ────┤
                     │                                              │
                     └──── 5.x (Frontend, needs 4.2 + 4.3) ─────────┤
                                                                     │
                         6.x (Integration, needs all 3.x + 5.x) ◄────┘
```

## Parallelizable Tracks

Once Phase 0 is done, these can proceed in parallel:
- **Track A**: 1.1 → 1.2 → 3.1 (Data pipeline)
- **Track B**: 1.3 → 2.1 → 3.2 (ML + signals)
- **Track C**: 1.4 → 1.5 → 3.4 (Broker integration)
- **Track D**: 1.6 → 3.3 (Risk)
- **Track E**: 4.1 → 4.2 → 4.3 (API, can start after 0.2)
- **Track F**: 5.x (Frontend, needs Track E)
