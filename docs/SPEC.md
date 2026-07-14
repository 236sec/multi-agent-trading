# Multi-Agent Trading System — Specification

## Problem Statement

I want to build an automated quantitative trading system that generates daily trading signals from an ML model, screens them through risk management rules, and executes approved trades on a paper trading account — all while keeping a human in the loop for final approval. The system must be extensible to support additional models (regime detection, multiple strategies) in the future, run entirely locally, and provide a real-time dashboard for monitoring and manual control.

## Solution

A daily, event-driven pipeline of independent agent processes coordinated through a PostgreSQL message queue. At end-of-day, a data ingestion agent fetches market data from Yahoo Finance. A signal agent runs an offline-trained XGBoost/LightGBM classifier to generate buy/sell signals on a curated watchlist. A risk agent screens each signal against position limits, sector concentration, and drawdown guards. Approved orders sit in the database awaiting human confirmation. A Next.js dashboard displays the pipeline status in real time and lets the trader manually approve, reject, or retry orders. An execution agent picks up confirmed orders and places them via Webull OpenAPI paper trading.

## User Stories

### Data & Signals

1. As a quant trader, I want the system to automatically fetch daily OHLCV data from Yahoo Finance for my watchlist after market close, so that I don't have to manually download data every day.
2. As a quant trader, I want fetched market data cached in a local database, so that I can build training datasets and backtest without repeatedly hitting Yahoo Finance's rate limits.
3. As a quant trader, I want an ML model to generate buy/sell signals each day with a confidence score for each ticker on my watchlist, so that I have data-driven trade ideas without staring at charts.
4. As a quant trader, I want to be able to swap the ML model file without changing any agent code, so that I can iterate on my strategy independently of the production pipeline.
5. As a quant trader, I want the signal agent to use only price/volume technical features, so that the model works with data freely available from Yahoo Finance.
6. As a quant trader, I want to manually curate my watchlist in a configuration file, so that I can add or remove tickers without touching code.

### Risk Management

7. As a risk manager, I want the system to reject any signal that would make a single position exceed a configurable percentage of my portfolio, so that I maintain diversification.
8. As a risk manager, I want the system to reject signals that would push my sector exposure above a configurable threshold, so that I avoid concentration risk.
9. As a risk manager, I want the system to halt or reduce trading when my portfolio drawdown exceeds a configurable percentage from its peak, so that I protect capital during losing streaks.
10. As a risk manager, I want every risk decision (pass or reject) logged with a specific reason, so that I can audit why trades were blocked and tune my rules later.

### Execution & Human-in-the-Loop

11. As a trader, I want risk-approved orders to wait for my explicit confirmation before being sent to the broker, so that I retain final control over every trade in v1.
12. As a trader, I want to manually approve, reject, or cancel pending orders from the dashboard, so that I can apply judgment the system cannot.
13. As a trader, I want a "retry" button on failed orders, so that I can re-attempt execution if Webull had a transient error.
14. As a trader, I want the execution agent to support market orders, limit orders, and bracket orders (stop-loss + take-profit), so that I have flexible order control.

### Dashboard & Monitoring

15. As a trader, I want to see my current portfolio value, daily P&L, and an equity curve chart on the dashboard, so that I understand performance at a glance.
16. As a trader, I want to see the real-time status of each agent in the pipeline (data ingestion → signal → risk → execution), including last run time and any errors, so that I know the system is healthy.
17. As a trader, I want a filterable, scrollable table of all historical signals, risk decisions, and executions, so that I can review past activity and debug issues.
18. As a trader, I want the dashboard to update in real time via WebSocket as agents run, so that I don't need to refresh the page to see new signals or status changes.
19. As a developer, I want the dashboard to run locally without authentication, so that I can focus on the trading logic without building auth infrastructure.

### Observability & Debugging

20. As a developer, I want every agent to emit structured JSON logs to stdout and persist key events to a database log table, so that I can debug the pipeline from both the terminal and the dashboard.
21. As a developer, I want agent failures to be surfaced visibly on the dashboard with a timestamp and error message, so that I notice problems quickly.
22. As a developer, I want the full message trace (signal → risk decision → order execution) to be queryable for any ticker and date, so that I can reconstruct exactly what happened.

### Extensibility & Future-Proofing

23. As a system architect, I want all queue messages to carry an `agent_type` and `strategy_id` field, so that I can add a regime model and multiple strategy agents in the future without changing the message format.
24. As a system architect, I want each agent to run as an independent process communicating only through the database queue, so that I can add new agents by writing a new CLI entry point without modifying existing agents.

### Operations

25. As an operator, I want to trigger the full pipeline via cron or systemd timers at a configurable time, so that the system runs automatically every trading day.
26. As an operator, I want all secrets (API keys, DB credentials) in a `.env` file and all operational config (watchlist, risk parameters, model path) in a YAML file, so that configuration is cleanly separated from code and sensitive values are never committed.
27. As an operator, I want a single CLI with subcommands (`trading run signal`, `trading run risk`, etc.) to run each agent individually, so that I can test, debug, or re-run a single step in the pipeline.

### Testing & Backtesting

28. As a developer, I want unit tests for each agent's core logic (signal generation, risk checks) and integration tests for the full message flow through a test database, so that I can refactor with confidence.
29. As a quant researcher, I want to backtest my signal strategy in Jupyter notebooks using the same feature engineering code the live agent uses, so that my research translates directly to production.
30. As a developer, I want external dependencies (yfinance, Webull API) mocked in tests, so that tests are fast and don't require live API access.

## Implementation Decisions

### Architecture

- **Event-driven with PostgreSQL message queue**: Agents communicate exclusively through a `message_queue` table using PostgreSQL's `FOR UPDATE SKIP LOCKED` pattern. No in-memory IPC, no external message broker. This is the single integration seam for the entire system.
- **Separate processes**: Each agent (data ingestion, signal, risk, execution) runs as an independent Python process. A single crash does not take down the pipeline. Cron triggers each process at its scheduled time.
- **Human-in-the-loop execution**: Risk-approved orders are stored with status `approved_pending_human`. The trader reviews them on the dashboard and clicks "Send to Webull" to dispatch. No automatic order placement in v1.
- **Retryable failures**: Failed operations (data fetch failures, Webull errors) are surfaced on the dashboard with a manual retry button. No automatic retry loop — human decides whether to retry.

### Agent Responsibilities

| Agent | Trigger | Input | Output |
|---|---|---|---|
| Data Ingestion | Cron, daily after close | Watchlist from config | OHLCV rows in `market_data` table |
| Signal Agent | Cron, after ingestion | OHLCV from `market_data` | Signal rows in `signals` table + queue message |
| Risk Agent | Cron, after signal | Signal from queue + portfolio state | Risk decision + order in `orders` table (`approved_pending_human`) |
| Execution Agent | Dashboard dispatch | Order with status `human_confirmed` | Webull API call → updated order status |

### ML Model

- **Framework**: scikit-learn / XGBoost / LightGBM, serialized via pickle or joblib.
- **Target**: Binary classification — next-day return direction (up vs. down).
- **Features**: Price/volume-derived technical indicators (moving averages, RSI, volatility, volume profile, etc.) computed from daily OHLCV data.
- **Training**: Manual, offline via Jupyter notebooks or standalone scripts. The signal agent loads a serialized model file at startup. Model retraining is a separate research workflow, not part of the live pipeline.
- **Watchlist**: 10–50 tickers, manually curated in `config.yaml`. Fixed, not dynamically screened.

### Risk Controls (v1)

1. **Max position size**: No single position exceeds X% of total portfolio value (configurable). Oversized signals are downsized rather than rejected when possible.
2. **Max sector concentration**: No sector exceeds Y% of total portfolio value (configurable). Requires ticker-to-sector mapping (from Yahoo Finance).
3. **Max drawdown guard**: If portfolio NAV drawdown from peak exceeds Z% (configurable), all signals are rejected or position sizes are reduced.

### Database Schema

Core tables:

- `watchlist` — ticker, sector, added_date
- `market_data` — ticker, date, open, high, low, close, volume (cached OHLCV)
- `positions` — ticker, quantity, avg_cost, current_price, last_updated
- `portfolio_nav` — date, total_value, cash, drawdown_pct
- `signals` — id, ticker, action (BUY/SELL/HOLD), quantity, confidence, timestamp, status
- `risk_decisions` — signal_id, passed (bool), reject_reason, position_check_pct, sector_check_pct, drawdown_check_pct
- `orders` — id, signal_id, ticker, action, quantity, order_type (MARKET/LIMIT/BRACKET), stop_loss, take_profit, status (approved_pending_human → human_confirmed → sent_to_webull → filled/partially_filled/rejected), webull_order_id, created_at, updated_at
- `event_log` — id, agent, event_type, payload (JSONB), created_at
- `message_queue` — id, agent_type, strategy_id, event_type, payload (JSONB), status (pending/processing/done/failed), retries, created_at, processed_at

### Message Queue State Machine

```
pending → processing → done
                    ↘ failed → pending (on human retry)
```

Messages use `SELECT ... FOR UPDATE SKIP LOCKED` for safe concurrent consumption. Each agent polls its relevant `agent_type` messages.

### API (FastAPI)

Key endpoints:

- `GET /api/portfolio` — current portfolio state, NAV, P&L
- `GET /api/portfolio/history` — NAV time series for equity curve
- `GET /api/signals?date=&status=&ticker=` — filterable signal history
- `GET /api/orders?status=` — order pipeline status
- `POST /api/orders/{id}/confirm` — human confirms → dispatches to execution agent
- `POST /api/orders/{id}/cancel` — human cancels pending order
- `POST /api/orders/{id}/retry` — retry a failed execution
- `GET /api/agents/status` — last run time and health of each agent
- `GET /api/events?agent=&date=` — event log queries
- `WS /ws/pipeline` — WebSocket for real-time pipeline updates

### Frontend (Next.js)

Four views:

1. **Portfolio Overview**: NAV chart (equity curve), daily P&L, current positions table with unrealized gains, cash balance, drawdown gauge.
2. **Pipeline Status**: Live agent status cards showing each agent's last run time, current state (idle/running/error), and latest log entry. Updates via WebSocket.
3. **Trade History**: Filterable table of signals → risk decisions → orders. Columns: date, ticker, signal action, confidence, risk result, order status. Click to expand full audit trail.
4. **Pending Orders**: Queue of `approved_pending_human` orders with Approve/Reject buttons. Failed orders with Retry button.

Real-time updates via WebSocket connection to FastAPI.

### Configuration

- `.env`: `DATABASE_URL`, `WEBULL_API_KEY`, `WEBULL_API_SECRET`, `WEBULL_ACCOUNT_ID`
- `config.yaml`:
  ```yaml
  watchlist:
    - ticker: AAPL
      sector: Technology
    - ticker: JPM
      sector: Financials
  risk:
    max_position_pct: 0.20
    max_sector_pct: 0.40
    max_drawdown_pct: 0.15
  model:
    path: models/signal_v1.pkl
  schedule:
    data_ingestion_time: "16:30"
    signal_time: "17:00"
    risk_time: "17:30"
  ```

### Logging

- **Stdout**: Structured JSON logs from each agent: `{"ts": "...", "agent": "signal", "event": "signal_generated", "ticker": "AAPL", "action": "BUY", "confidence": 0.82, "duration_ms": 145}`
- **Database**: `event_log` table for dashboard-queryable event history. Agents write both.

### Extensibility

All `message_queue` rows include `agent_type` (e.g., `signal`, `risk`, `regime`) and `strategy_id` (e.g., `ml_v1`, `momentum_v2`). When a regime model or additional strategy agents are added, they publish to the same queue with their own `agent_type`/`strategy_id`. The risk agent can consume from multiple signal sources by filtering on `agent_type`. No schema migration needed to add new agent types.

### Project Structure

Monorepo:

```
multi-agent-trading/
├── backend/                  # Python, uv package manager
│   ├── pyproject.toml
│   ├── src/
│   │   └── trading/
│   │       ├── cli.py              # Single CLI entry point
│   │       ├── agents/
│   │       │   ├── ingestion.py    # Data ingestion agent
│   │       │   ├── signal.py       # Signal generation agent
│   │       │   ├── risk.py         # Risk management agent
│   │       │   └── execution.py    # Order execution agent
│   │       ├── db/
│   │       │   ├── models.py       # SQLAlchemy/Pydantic models
│   │       │   ├── queue.py        # Message queue operations
│   │       │   └── repository.py   # CRUD operations
│   │       ├── api/
│   │       │   ├── app.py          # FastAPI application
│   │       │   ├── routes/         # API route handlers
│   │       │   └── ws.py           # WebSocket handler
│   │       ├── features/           # Feature engineering (shared with backtesting)
│   │       ├── broker/
│   │       │   └── webull.py       # Webull OpenAPI client
│   │       └── config.py           # Configuration loading
│   ├── tests/
│   ├── notebooks/                  # Research & backtesting
│   ├── models/                     # Serialized ML models
│   ├── config.yaml
│   └── .env.example
├── frontend/                 # Next.js
│   ├── package.json
│   ├── src/
│   │   ├── app/              # App router pages
│   │   ├── components/       # Dashboard components
│   │   └── lib/              # API client, WebSocket hook
│   └── ...
└── SPEC.md
```

## Testing Decisions

### Testing Seam

The primary integration seam is the PostgreSQL message queue. Every agent reads messages from the queue and writes results back to the queue or database. This means:

- **Unit tests**: Each agent's core logic is tested in isolation by calling internal functions directly with known inputs and asserting outputs. No database or queue needed.
- **Integration tests**: A test PostgreSQL database is populated with input messages. An agent process is run. Output messages and database rows are asserted. External APIs (yfinance, Webull) are mocked at the HTTP level.
- **API tests**: FastAPI endpoints are tested with `TestClient`, asserting status codes and response shapes against a test database.

### What Makes a Good Test

- Test external behavior, not internal implementation: assert on the output message in the queue, not on which internal function was called.
- Mock external boundaries: yfinance and Webull are mocked with `responses` or `httpx` mock transports. Tests never hit live APIs.
- Test error paths: what happens when yfinance returns an empty response, when Webull returns a 503, when the model file is missing.

### Modules Under Test

| Module | Test Type | What's Verified |
|---|---|---|
| `features/` | Unit | Indicator calculations produce expected values for known OHLCV inputs |
| `agents/signal.py` | Unit | Model loading, feature vector construction, signal output shape |
| `agents/risk.py` | Unit | Each risk rule (position, sector, drawdown) correctly blocks/approves given portfolio state |
| `agents/execution.py` | Unit | Order payload construction matches Webull API spec |
| `db/queue.py` | Integration | Message enqueue/dequeue with FOR UPDATE SKIP LOCKED, status transitions |
| Full pipeline | Integration | End-to-end: seed market data → run signal → run risk → assert order in DB with correct status |
| `api/` | Integration | All endpoints return correct data from seeded DB, WebSocket receives events |
| `broker/webull.py` | Unit | Request formatting, response parsing, error handling (no live calls) |

### No Prior Art

This is a greenfield project. Tests follow standard pytest patterns with fixtures for database setup/teardown and mock patches for external services.

## Out of Scope

- **Authentication**: No login, user management, or session handling. The dashboard runs locally and is assumed to be accessed only by the operator.
- **Automatic trading (v1)**: All orders require human confirmation. No automated execution path exists yet.
- **Regime model**: Market regime detection is planned for a future iteration. The message schema is designed to accommodate it.
- **Multiple strategy agents**: v1 has one signal agent with one ML model. The `strategy_id` field exists but only one strategy runs.
- **Real-time/tick-level trading**: Daily end-of-day only. No intraday signal generation, no streaming data feeds, no WebSocket market data.
- **Deployment/containerization**: Runs directly on the local machine via cron. No Docker, no cloud deployment, no CI/CD pipeline.
- **Multi-user support**: Single operator, single paper trading account.
- **Tax/commission accounting**: Paper trading only. No real P&L tracking with commissions, fees, or tax lots.
- **Fundamental/macro features**: v1 signals use technical features only. Fundamental data (P/E, earnings) and macro indicators (VIX, rates) are out of scope for the initial model.
- **Dynamic watchlist screening**: Watchlist is a static, manually curated list. No automated screening for new tickers.
- **Automated model retraining**: Model updates are manual offline research. No scheduled retraining pipeline.
- **Performance optimization**: Agents process a ~50 ticker watchlist. No batching, parallelism, or throughput optimizations are needed.

## Further Notes

### Webull Spike

The Webull OpenAPI integration is a known unknown. Before building the execution agent, spike:
1. Register for Webull OpenAPI access and paper trading.
2. Authenticate programmatically (OAuth flow).
3. Place a market order, a limit order, and a bracket order on the paper account.
4. Query order status and positions.
5. Document the API contract, auth token lifecycle, and rate limits.

### Agent Startup Order

Cron should sequence agents with buffer time:
- Data ingestion: 4:30 PM ET (30 min after close — ensures Yahoo Finance data is updated)
- Signal: 5:00 PM ET
- Risk: 5:30 PM ET
- Human reviews orders that evening or next morning
- Execution: on-demand when human clicks "Send to Webull"

If an earlier agent fails, downstream agents will find no messages to process and log a warning. The retry flow is manual — the operator fixes the issue and re-runs the failed agent via CLI.

### Configuration: Webull Paper vs. Live

The `config.yaml` should include a `broker.mode` field (`paper` or `live`). The execution agent reads this at startup and routes to the appropriate Webull endpoint. v1 is always `paper`.
