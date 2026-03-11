# Project Notes

## Trading Bot Design (saved for future implementation)

Full plan at: `/root/.claude/plans/giggly-gathering-ritchie.md`

### Summary
Standalone Python trading bot (separate repo from FlipFinder) for PythonAnywhere + GitHub deployment.

### Two Modes
1. **Crypto Anomaly Scanner** — Coinbase REST API polling (5s intervals), detects price moves >0.11%, trades after 9-16s delay
2. **Stock Gap Scanner + Swing Trader** — Schwab API, pre-market gap scanning, RSI/technical screening, earnings momentum

### Key Decisions
- **Coinbase** for crypto (not Binance) — better US access
- **Schwab** for stocks — OAuth 2.0 with refresh tokens
- **PythonAnywhere** deployment — no WebSocket support, so REST polling for crypto; scheduled tasks for stocks (9AM + 4PM ET)
- **Paper trading by default** — no real money until explicitly enabled
- Consider VPS migration later if real-time WebSocket needed for crypto edge

### Architecture
- ~500-600 lines Python, 3 dependencies (aiohttp, pyyaml, python-dotenv)
- `crypto/` module: scanner, detector, trader
- `stocks/` module: scanner, screener, schwab_api, trader
- `core/` module: stats (SQLite), alerts (email), display (CLI)
- `config.yaml` for all tunable parameters
- Entry points: `run_crypto.py`, `run_stocks.py`, `run_both.py`

### Risk Management
- Position limits (max 5 open stock positions)
- Stop losses (3% default)
- Trade size caps per trade
- Cooldowns between signals on same asset
- Live mode requires explicit config + env confirmation
