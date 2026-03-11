# Trading Bot Design (Future Project — Separate Repo)

Full architecture plan at: `/root/.claude/plans/giggly-gathering-ritchie.md`
Detailed strategy research at: `TRADING_STRATEGIES_RESEARCH.md`

## Summary
Standalone Python trading bot (separate repo from FlipFinder) for PythonAnywhere + GitHub deployment.

## Two Modes
1. **Crypto Anomaly Scanner** — Coinbase REST API polling (5s intervals), detects price moves >0.11%, trades after 9-16s delay
2. **Stock Gap Scanner + Swing Trader** — Schwab API, pre-market gap scanning, RSI/technical screening, earnings momentum

## Key Decisions
- **Coinbase** for crypto (not Binance) — better US access
- **Schwab** for stocks — OAuth 2.0 with refresh tokens
- **PythonAnywhere** deployment — no WebSocket support, so REST polling for crypto; scheduled tasks for stocks (9AM + 4PM ET)
- **Paper trading by default** — no real money until explicitly enabled
- Consider VPS migration later if real-time WebSocket needed for crypto edge

## Architecture
- ~500-600 lines Python, 3 dependencies (aiohttp, pyyaml, python-dotenv)
- `crypto/` module: scanner, detector, trader
- `stocks/` module: scanner, screener, schwab_api, trader
- `core/` module: stats (SQLite), alerts (email), display (CLI)
- `config.yaml` for all tunable parameters
- Entry points: `run_crypto.py`, `run_stocks.py`, `run_both.py`

## Risk Management
- Position limits (max 5 open stock positions)
- Stop losses (3% default)
- Trade size caps per trade
- Cooldowns between signals on same asset
- Live mode requires explicit config + env confirmation

---

## Strategy Research Brainstorm (March 2026)

Comprehensive hedge fund strategy research saved in `TRADING_STRATEGIES_RESEARCH.md`.

### Upgraded Architecture: Multi-Strategy Engine

Instead of 2 strategies, build a **pluggable strategy engine** with 6-8 strategies running simultaneously. Each strategy implements a common interface (`check_signals`, `get_position_size`, `get_exit_rules`). The engine manages risk across all strategies.

### Crypto Strategies (Ranked by Conviction)

1. **Funding Rate Arbitrage** (HIGHEST conviction) — Delta-neutral: long spot + short perp, collect funding every 8h. 5-15% net APY. Low risk. Coinbase + exchange with perps needed.
2. **Multi-Signal Momentum** — Upgrade the original anomaly detector to require 2-3 confirming signals: price move + volume spike + cross-asset confirmation + on-chain flow. Each alone is ~51% accurate; combined pushes to 55-60%.
3. **Trend Following** — SMA9 or 15/150 MA crossover on 4h/daily charts. 15/150 crossover backtested at +97.87% return. ~85% signal alignment when combining MACD/RSI/KDJ/Bollinger.
4. **On-Chain Flow Signals** — Whale wallet tracking (Whale Ratio >85% = bearish, <70% = bullish), exchange inflow/outflow, MVRV ratio. Best for medium-term positioning (days-weeks).
5. **Volatility-Adjusted Thresholds** — Replace static 0.11% threshold with Bollinger Band-style dynamic threshold based on rolling volatility.

### Stock Strategies (Ranked by Conviction)

1. **FOMC Pre-Announcement Drift** (HIGHEST conviction) — Buy SPY 24h before FOMC announcement, sell after. 80% of annual equity premium earned in just 8 trading days/year. Sharpe >1.1. Still persistent through 2024.
2. **Dual Momentum / Sector Rotation** — Monthly: compare SPY vs EFA 12-month returns; hold winner if positive, else bonds. Outperformed buy-and-hold ~70% of the time over 80+ years. Only trades monthly.
3. **RSI(2) Mean Reversion** — Buy when 2-day RSI < 10 on SPY/QQQ (must be above 200-day MA). 91% backtested win rate, 0.82% avg gain per trade. Fails in strong trends — needs stop losses.
4. **Seasonal Composite** — Sell-in-May + FOMC drift + Turn-of-Month + momentum = 9.56% annualized, Sharpe 0.77 (2x buy-and-hold Sharpe).
5. **PEAD (Earnings Drift)** — Still alive in microcaps/low-coverage stocks. 5-15% alpha. Enter on first pullback after >5% earnings surprise. Hold 20-60 days.

### Strategies with Diminishing Edge (Deprioritize)
- Cross-exchange crypto arbitrage (margins compressed to 0.05-0.2%, institutional dominated)
- Pairs trading (fails to beat market benchmark overall; only useful in bear markets)
- January Effect (essentially dead since 1990s)
- Gap trading (profitability declining as algos arbitrage the edge)
- Wheel strategy (94-99% of returns come from stock position, not options premium)

### Critical Risk Management Upgrades
1. **Kelly Criterion position sizing** — Use quarter-Kelly (25% of full Kelly) based on actual win rate + avg win/loss from paper trading data.
2. **Correlation-aware portfolio** — BTC/ETH/SOL are 0.85+ correlated; treat concurrent signals as ONE bet, not three.
3. **Regime detection** — ADX >25 = trending (use momentum), ADX <20 = ranging (use mean reversion), VIX >25 = reduce size 50%, VIX >40 = go to cash.
4. **Circuit breakers** — Daily loss >2% = stop trading; weekly >5% = stop; monthly >10% = review everything.
5. **Dynamic thresholds** — Adjust anomaly detection threshold based on rolling volatility, not static 0.11%.

### Schwab API Notes
- Free with any account, no minimum balance
- Real-time streaming, Level 2, full options chains, 15 years daily data
- OAuth 2.0 with **manual refresh every 7 days** (limitation for automation)
- Best Python wrapper: `schwab-py`
- No native paper trading (we build our own)
- Rate limits: 120 requests/min data, 2-4/sec trades

### Recommended Implementation Priority
1. Core engine + config + stats (shared infrastructure)
2. FOMC drift (easiest, highest conviction, 8 trades/year)
3. Dual momentum (monthly, low effort, well-proven)
4. RSI(2) mean reversion (daily, high win rate)
5. Crypto multi-signal momentum (the original strategy, upgraded)
6. Funding rate arbitrage (if exchange with perps available)
7. On-chain signals (as confirming layer for crypto strategies)
8. PEAD earnings drift (quarterly, microcap focused)

### Key Insight from Research
Renaissance Technologies' edge comes from combining **thousands of weak signals** (51-53% each) into strong composite signals. Our bot should follow the same principle: no single strategy is the answer. The multi-strategy engine with correlation-aware risk management is the architecture that works.
