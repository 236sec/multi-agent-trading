# Multi-Agent Trading System — PRD

## Problem Statement

I want to run a quantitative trading system locally that generates daily ML-driven trading signals, screens them through risk management rules, and lets me manually approve trades before execution on a paper trading account. I need the system to be modular enough that I can swap signal models, add new agents, and backtest strategies without rewriting core infrastructure.

## Solution

A daily pipeline of independent agent processes communicating through a PostgreSQL message queue. The system is built around **deep modules** — each with a narrow, stable interface that encapsulates complex behavior. This lets me iterate on the ML model, risk rules, or broker integration independently. A Next.js dashboard provides real-time pipeline visibility and serves as the human-in-the-loop control surface. All state is persisted in PostgreSQL, giving me a full audit trail from signal to execution.

## User Stories

### Data Pipeline

1. As a trader, I want the system to automatically fetch daily OHLCV data from Yahoo Finance for my watchlist after market close, so that I never miss a day of data.
2. As a trader, I want market data cached locally so I can build training datasets without hitting API rate limits.
3. As a trader, I want to add or remove tickers from my watchlist by editing a config file, without touching agent code.
4. As a trader, I want the data ingestion agent to run on a cron schedule so I don't have to trigger it manually.

### Signal Generation

5. As a quant, I want an ML model to generate BUY/SELL/HOLD signals with confidence scores for each ticker daily, so I have data-driven trade ideas.
6. As a quant, I want to swap the model file without changing agent code, so I can iterate on strategies independently of the pipeline.
7. As a quant, I want the signal agent to use price/volume features only, so my model works with freely available Yahoo Finance data.
8. As a quant, I want to backtest my strategy in Jupyter notebooks using the same feature engineering code the live agent uses, so research translates directly to production.

### Risk Management

9. As a risk manager, I want the system to reject signals that would exceed my per-position size limit, so I stay diversified.
10. As a risk manager, I want the system to block trades that push my sector exposure above a threshold, so I avoid concentration risk.
11. As a risk manager, I want the system to halt or reduce trading when portfolio drawdown exceeds a configurable limit, so I protect capital.
12. As a risk manager, I want every rejection logged with an explicit reason, so I can audit and tune my rules.

### Execution

13. As a trader, I want all approved orders to wait for my explicit confirmation before hitting the broker, so I retain final control.
14. As a trader, I want to approve, reject, or cancel pending orders from the dashboard, so I can apply judgment the system lacks.
15. As a trader, I want a "retry" button on failed orders so I can re-attempt execution after transient errors.
16. As a trader, I want to place market, limit, and bracket orders (stop-loss + take-profit) so I have flexible execution control.

### Dashboard

17. As a trader, I want to see my portfolio value, P&L, and equity curve at a glance, so I understand performance.
18. As a trader, I want real-time visibility into each agent's status (running, idle, error, last run time), so I know the system is healthy.
19. As a trader, I want a filterable history of every signal, risk decision, and execution, so I can audit past activity.
20. As a trader, I want the dashboard to update in real time as agents run, without manual refresh.
21. As a developer, I want structured logs from every agent visible on the dashboard so I can debug without SSH.

### Operations

22. As an operator, I want to run any agent individually via CLI (`trading run signal`) so I can test, debug, or re-run a single step.
23. As an operator, I want secrets in `.env` and config in YAML, so sensitive values stay out of version control.
24. As an operator, I want cron to trigger the full pipeline on a set schedule, so the system runs automatically each trading day.

### Extensibility

25. As an architect, I want to add a new agent (e.g., regime detection) by writing a new CLI entry point that reads/writes to the message queue, without modifying existing agents.
26. As an architect, I want all messages to carry `agent_type` and `strategy_id` so the system supports multiple signal sources and model types in the future.

### Testing

27. As a developer, I want unit tests for each agent's core logic and integration tests for the full message flow, so I can refactor without breaking production.
28. As a developer, I want external APIs mocked in tests so tests are fast and offline.

## Implementation Decisions

### Deep Modules

The system is decomposed into deep modules — each has a narrow, stable interface and encapsulates substantial complexity. Modules communicate through the message queue and database, never through direct imports (outside shared libraries).

#### 1. MessageQueue

**Interface**: `enqueue(agent_type, strategy_id, event_type, payload) -> message_id`, `dequeue(consumer_agent_type, limit) -> list[Message]`, `ack(message_id)`, `nack(message_id, error)`

**Encapsulates**: PostgreSQL `FOR UPDATE SKIP LOCKED` semantics, connection pool management, message status state machine (`pending → processing → done | failed`), retry tracking, and JSONB payload storage. All agent-to-agent communication flows through this single interface.

**Why deep**: Callers never touch SQL or know about the queue implementation. If we swap PostgreSQL for Redis Streams later, only this module changes.

#### 2. MarketData

**Interface**: `fetch_daily(ticker, start_date, end_date) -> DataFrame`, `cache_ohlcv(ticker, records)`, `get_cached(ticker, start_date, end_date) -> DataFrame`

**Encapsulates**: yfinance API calls, rate-limit handling, response parsing, local PostgreSQL caching (upsert logic), and data validation. Callers get a DataFrame — they don't know or care where the data came from.

**Why deep**: Swapping Yahoo Finance for Polygon.io or Alpaca data means implementing this interface against a different API. Nothing else in the system changes.

#### 3. FeatureEngine

**Interface**: `compute(ohlcv_df) -> features_df`

**Encapsulates**: All technical indicator calculations (moving averages, RSI, MACD, volatility measures, volume profile). Accepts a standardized OHLCV DataFrame, returns a feature DataFrame with named columns.

**Why deep**: This is the shared contract between research and production. Adding a new indicator adds a column to the output DataFrame. The interface never changes. Jupyter notebooks and the live signal agent both call `compute()` — zero duplication.

#### 4. SignalModel

**Interface**: `load(model_path) -> SignalModel`, `predict(features_df) -> signals_df` where `signals_df` has columns: `ticker, action (BUY/SELL/HOLD), quantity, confidence`

**Encapsulates**: Model deserialization (pickle/joblib), feature validation, inference execution, and output formatting into a standardized signals DataFrame. Handles model-not-found and incompatible-model errors.

**Why deep**: Swapping from XGBoost to LightGBM or a deep learning model only changes this module's internals. The rest of the system sees a DataFrame of signals regardless.

#### 5. RiskEngine

**Interface**: `evaluate(signal: Signal, portfolio: PortfolioState) -> RiskDecision` where `RiskDecision` has: `passed: bool, reject_reason: str | None, adjusted_quantity: int | None, checks: {position_pct, sector_pct, drawdown_pct}`

**Encapsulates**: All three risk rules (position sizing, sector concentration, drawdown guard). Each rule is a strategy object implementing a `check(signal, portfolio) -> CheckResult` interface. The engine runs all checks, aggregates results, and potentially downsizes rather than rejects.

**Why deep**: Adding a fourth risk rule means implementing one new strategy class. The `evaluate()` interface and the signal agent's interaction with it never change.

#### 6. Broker

**Interface**: `place_order(order: OrderRequest) -> OrderResult`, `get_positions() -> list[Position]`, `get_account() -> Account`, `cancel_order(order_id) -> bool`

**Encapsulates**: Webull OpenAPI authentication (OAuth), token lifecycle, order placement (market/limit/bracket), order status polling, position queries, error handling, and rate limiting.

**Why deep**: Swapping Webull for Interactive Brokers or Alpaca means implementing this interface against a different API. The execution agent and dashboard don't know which broker is behind it.

#### 7. PipelineScheduler

**Interface**: Each agent is a CLI entry point (`trading run <agent>`). The scheduler is cron, not a module. But each agent process shares a common lifecycle: `connect_db() -> poll_queue() -> process_messages() -> cleanup()`.

**Encapsulates**: Database connection setup, queue polling loop, error handling, structured logging setup, and graceful shutdown. Each agent's `process_message()` is the pluggable part.

### Agent-to-Queue Contract

Each agent reads from and writes to the message queue. The contract is defined by message types:

| Producer | Event Type | Consumer |
|---|---|---|
| Data Ingestion | `market_data_updated` | Signal Agent |
| Signal Agent | `signal_generated` | Risk Agent |
| Risk Agent | `order_approved` | Dashboard (pending human) |
| Dashboard (API) | `order_confirmed` | Execution Agent |
| Execution Agent | `order_executed` | Dashboard (status update) |

### Database Schema

Nine tables (detailed in SPEC.md). Key design points:

- `message_queue` is the sole integration seam. It uses `SELECT ... FOR UPDATE SKIP LOCKED` for concurrent-safe dequeuing.
- `signals` → `risk_decisions` → `orders` forms a traceable chain. Every order can be traced back to its originating signal and risk decision.
- `event_log` stores structured agent events as JSONB for dashboard queries.
- `market_data` uses `(ticker, date)` unique constraint with upsert for idempotent data ingestion.
- `portfolio_nav` is append-only — a daily snapshot of total value, cash, and drawdown.

### API Contracts (FastAPI)

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/portfolio` | GET | Current portfolio state, NAV, P&L |
| `/api/portfolio/history` | GET | NAV time series for equity curve |
| `/api/signals` | GET | Filterable signal history (date, status, ticker) |
| `/api/orders` | GET | Order pipeline with status filter |
| `/api/orders/{id}/confirm` | POST | Human approves → dispatches to execution agent |
| `/api/orders/{id}/cancel` | POST | Human cancels pending order |
| `/api/orders/{id}/retry` | POST | Retry a failed execution |
| `/api/agents/status` | GET | Health and last-run for each agent |
| `/api/events` | GET | Event log query |
| `/ws/pipeline` | WS | Real-time pipeline events pushed to dashboard |

### Frontend Views (Next.js)

Four dashboard views, updated via WebSocket:

1. **Portfolio** — Equity curve, daily P&L, current positions, drawdown gauge.
2. **Pipeline** — Agent status cards (ingestion, signal, risk, execution), last run timestamps, error states.
3. **History** — Filterable table: signals → risk decisions → executions. Click-through audit trail.
4. **Orders** — Pending approval queue with Approve/Reject buttons. Failed orders with Retry button.

### Configuration

Secrets in `.env` (never committed): `DATABASE_URL`, `WEBULL_API_KEY`, `WEBULL_API_SECRET`, `WEBULL_ACCOUNT_ID`.

Operational config in `config.yaml`:
```yaml
watchlist:
  - ticker: AAPL
    sector: Technology
risk:
  max_position_pct: 0.20
  max_sector_pct: 0.40
  max_drawdown_pct: 0.15
model:
  path: models/signal_v1.pkl
broker:
  mode: paper  # paper | live
schedule:
  data_ingestion: "16:30"
  signal: "17:00"
  risk: "17:30"
```

### Technology Stack

| Layer | Choice | Rationale |
|---|---|---|
| Language | Python 3.12+ | ML ecosystem, FastAPI, yfinance |
| Package manager | uv | Fast, modern, lockfile support |
| ML framework | scikit-learn / XGBoost / LightGBM | Battle-tested for tabular data |
| API framework | FastAPI | Async, Pydantic, WebSocket, OpenAPI docs |
| Database | PostgreSQL | Message queue (SKIP LOCKED), JSONB for events, relational for portfolio |
| Frontend | Next.js (App Router) | React ecosystem, good DX for dashboards |
| Realtime | FastAPI WebSocket | Push pipeline events to dashboard |
| Scheduling | cron / systemd timer | Simple, no extra dependency |
| Broker | Webull OpenAPI | Paper trading, bracket orders |
| Data | Yahoo Finance (yfinance) | Free, reliable daily OHLCV |

### Project Structure

Monorepo: `/backend` (Python, uv workspace) and `/frontend` (Next.js). Single Python package with one CLI supporting subcommands (`trading run signal`, `trading run risk`, etc.). Agents share the `db`, `features`, and `broker` modules. Research notebooks live in `backend/notebooks/`.

### Message Queue State Machine

```
pending ──→ processing ──→ done
                │
                └──→ failed ──→ pending (on dashboard retry click)
```

Only the dequeuing agent transitions `pending → processing`. Only that same agent transitions to `done` or `failed`. The dashboard API transitions `failed → pending` on retry.

## Testing Decisions

### Testing Seam

The message queue is the single integration seam. Each agent can be integration-tested in isolation:
1. Seed the queue with an input message.
2. Run the agent.
3. Assert the output message and database rows.

### Deep Module Test Strategy

Each deep module is tested at its interface boundary:

- **Unit tests** verify module logic with known inputs and expected outputs. No database, no network.
- **Integration tests** verify module behavior against a real (test) PostgreSQL instance. External HTTP calls are mocked.

| Module | Unit Tests | Integration Tests |
|---|---|---|
| MessageQueue | State machine transitions, message serialization | Enqueue/dequeue with real PG, concurrent consumers, SKIP LOCKED behavior |
| MarketData | Response parsing, data validation | yfinance mocked via httpx — cache hit/miss, upsert semantics |
| FeatureEngine | Indicator calculations against known OHLCV fixtures | N/A (pure computation, no I/O) |
| SignalModel | Model loading errors, feature validation, output formatting | Load a tiny trained model, run predict, assert signal DataFrame shape |
| RiskEngine | Each rule in isolation, interaction of multiple rules, downsizing logic | N/A (pure computation against portfolio state input) |
| Broker | Request serialization, response parsing, auth header construction | Webull API mocked — order placement, status polling, error responses |
| Pipeline (end-to-end) | N/A | Seed market data → run signal → run risk → assert order in DB. Full agent chain. |
| API | N/A | TestClient against test DB — all endpoints, WebSocket event push |

### What Makes a Good Test

- **Test the interface, not the implementation**: Assert on the output message in the queue, not which internal function was called.
- **Mock at the HTTP boundary**: `yfinance` and Webull are mocked with `respx` or `httpx` transport mocks. Tests never hit live APIs.
- **Test error paths**: Empty API responses, 5xx errors, missing model files, malformed config.
- **No `unittest.mock` on internal modules**: Only external I/O boundaries are mocked.

## Out of Scope

- Authentication or user management — single-user local application
- Automatic order execution — all orders require human confirmation in v1
- Regime detection model — future iteration, schema supports it
- Multiple strategy agents — v1 has one signal agent
- Intraday or real-time trading — daily EOD only
- Deployment, containerization (Docker), CI/CD
- Tax/commission tracking — paper trading only
- Fundamental or macroeconomic features — technical features only
- Dynamic watchlist screening — static curated list
- Automated model retraining — manual offline research
- Mobile or multi-device support — single local dashboard
- Performance optimization — 50-ticker watchlist doesn't need it

## Further Notes

### Webull Spike (Prerequisite)

Before building the execution agent, the Webull OpenAPI must be spiked:
- Register for OpenAPI access and paper trading account.
- Implement OAuth authentication flow programmatically.
- Place and verify: one market order, one limit order, one bracket order on paper.
- Determine auth token lifetime and refresh strategy.
- Document the API contract for order placement, cancellation, and position queries.

### Agent Execution Order

Cron sequence with buffer time between agents:
1. Data ingestion: 4:30 PM ET (30 min post-close)
2. Signal agent: 5:00 PM ET
3. Risk agent: 5:30 PM ET
4. Human reviews orders (evening or next morning)
5. Execution: on-demand via dashboard confirmation

If an upstream agent fails, downstream agents find an empty queue and log a warning. Recovery is manual: fix the issue, re-run the failed agent via CLI.

### Extensibility Path

Adding a new agent type (e.g., regime detection) requires:
1. A new Python module implementing the agent lifecycle (poll queue, process, publish results).
2. A new `trading run regime` CLI subcommand.
3. A new `agent_type` value in queue messages.
4. (Optional) A new cron entry.
5. No changes to existing agents.

Adding a new signal strategy:
1. Train a new model file.
2. Point a second signal agent instance at it with a different `strategy_id`.
3. Risk agent consumes from both `strategy_id` values.
4. No code changes — purely configuration.

### Config: Paper vs Live Guardrail

The `broker.mode` field in `config.yaml` (`paper` | `live`) is read at execution agent startup. If `live`, the agent could require an additional confirmation step or refuse to start without an explicit `--allow-live` CLI flag. v1 is always `paper`.
