# Algorithmic Trading Strategies Research (2025-2026)
## For Retail/Small Fund Traders ($1K-$50K Capital)

---

## Table of Contents
1. [Earnings Momentum / PEAD](#1-earnings-momentum--pead)
2. [Pre-Market Gap Trading](#2-pre-market-gap-trading)
3. [Mean Reversion Strategies](#3-mean-reversion-strategies)
4. [Pairs Trading](#4-pairs-trading)
5. [Sector Rotation / Momentum](#5-sector-rotation--momentum)
6. [Options Strategies for Income](#6-options-strategies-for-income)
7. [Volume Profile Analysis](#7-volume-profile-analysis)
8. [Schwab API Capabilities](#8-schwab-api-capabilities)
9. [Risk Parity](#9-risk-parity)
10. [Seasonality and Calendar Effects](#10-seasonality-and-calendar-effects)
11. [Strategy Comparison Matrix](#11-strategy-comparison-matrix)

---

## 1. Earnings Momentum / PEAD

### What It Is
Post-Earnings Announcement Drift (PEAD) is the tendency for a stock's price to continue drifting in the direction of an earnings surprise for weeks or months after the announcement. First documented by Ball and Brown (1968), it remains one of the most studied anomalies in finance.

### Academic Evidence
- **Bernard and Thomas (1990)**: Zero-investment portfolios based on earnings surprises generated ~8-9% abnormal returns per quarter (~35% annualized before transaction costs)
- **Higher-alpha variant**: Portfolios constructed 15 days before subsequent earnings and held through generated ~67% annualized abnormal returns
- **Chinese market evidence**: 6.78% excess return per quarter, uncorrelated with Fama-French factors

### Implementation
- **Entry**: Go long stocks from the intersection of top SUE (Standardized Unexpected Earnings) and EAR (Earnings Announcement Return) quintiles; short bottom quintiles
- **Timing**: Enter the second day after earnings announcement
- **Holding period**: 5-60 trading days (one quarter typical)
- **Exit rules**: Signal decay, stop-loss trigger, or holding period expiration
- **Enhancement**: Blend with momentum indicators; focus on sectors with historically higher drift (tech, biotech)

### Current Status (2025-2026)
- **Declining in liquid US large-caps**: Magnitude has decreased from ~18% annualized to near insignificance for large-cap stocks
- **Still alive in specific niches**:
  - Low analyst coverage stocks
  - Higher illiquidity / information asymmetry firms
  - Microcap stocks (bottom 20th percentile NYSE market cap)
  - Markets with higher passive institutional ownership (ETFs/index funds reduce price efficiency)
- **Academic debate**: Two 2025 papers contradict Martineau's 2022 "death of PEAD" finding, but disagreement centers on whether microcaps are included

### Realistic Expectations for Retail ($1K-$50K)
- **Annualized alpha**: 5-15% in small/micro-cap universe (before costs)
- **Sharpe ratio**: ~0.5-0.8 historically, likely lower going forward
- **Key risk**: Microcap liquidity; wide bid-ask spreads can consume alpha
- **Capital efficiency**: Works with small accounts since you can trade individual stocks

### Sources
- [Quantpedia - Post-Earnings Announcement Effect](https://quantpedia.com/strategies/post-earnings-announcement-effect)
- [UCLA Anderson Review - Is PEAD a Thing?](https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again)
- [Wikipedia - PEAD](https://en.wikipedia.org/wiki/Post%E2%80%93earnings-announcement_drift)
- [ScienceDirect - PEAD with investor attention](https://www.sciencedirect.com/science/article/abs/pii/S1057521924003922)
- [Financial Modeling Prep - Tracking PEAD](https://site.financialmodelingprep.com/education/other/tracking-postearnings-announcement-drift-with-fmps-market-data)

---

## 2. Pre-Market Gap Trading

### Gap-and-Go Strategy
Targets stocks with significant overnight price gaps, riding momentum after the open.

**Entry Criteria:**
- Gap of 4%+ (some use 3%+ minimum)
- Pre-market volume at least 200% of average by 8:00 AM EST
- Clear catalyst (earnings, FDA, M&A, major news)
- Price range: $5-$50
- Float under 50 million shares preferred
- Stock trading 10%+ of float in pre-market is ideal

**Execution:**
- Buy the break of pre-market high on the first 1-minute candle at 9:30 AM
- Alternative: Wait 15 minutes for pattern confirmation
- Stop-loss at low of first candle or 2-3% below entry
- Target: Take partials at 1:1 and 2:1 risk-reward

### Gap-Fade Strategy
Bets on gap reversal (mean reversion). Goes against the gap direction.

**Key findings:**
- Most small gaps fill same day; larger gaps take days
- Stocks generally tend to fade gaps more than other asset classes
- Profitability has declined as algorithmic trading arbitrages the edge away

### Win Rate & Returns
- **No reliable published win rate data** - varies enormously by implementation
- Gap trading is "not nearly as profitable as it used to be"
- Strategies are cyclical: work for periods, then stop, then resume
- The edge window is shrinking with increased computing power

### Risk Management
- Stop-loss: 2-3% below entry
- Risk per trade: 1-2% of capital
- Pre-market volume is lower = more volatile price action
- Only trade catalyst-driven gaps, not random drift

### Suitability for Small Accounts
- **Well-suited**: Can trade with small position sizes
- **Challenge**: PDT rule (Pattern Day Trader) requires $25K for unlimited day trades; under $25K you get only 3 day trades per 5 business days
- **Workaround**: Use a cash account (no margin) for unlimited day trades with settled funds

### Sources
- [HighStrike - Gap and Go Strategy 2025](https://highstrike.com/gap-and-go-strategy/)
- [Warrior Trading - Gap and Go](https://www.warriortrading.com/gap-go/)
- [QuantifiedStrategies - Gap Fill Trading](https://www.quantifiedstrategies.com/gap-fill-trading-strategies/)
- [QuantifiedStrategies - Gap Trading Strategy](https://www.quantifiedstrategies.com/gap-trading-strategies/)
- [Trade with the Pros - Pre-Market Gap Trading](https://tradewiththepros.com/pre-market-stock-gap-trading/)

---

## 3. Mean Reversion Strategies

### RSI-Based Strategies

**2-Period RSI Strategy (Larry Connors):**
- When 2-day RSI drops below 10, buy; sell when RSI crosses above 70
- **Backtested win rate: 91%**
- Average gain per trade: 0.82%
- Max drawdown: 33%
- Works best on large-cap indices and ETFs (SPY, QQQ)

**Standard RSI (14-period):**
- Buy when RSI < 30 (oversold); sell when RSI > 70 (overbought)
- Typical win rate: 60-70% in range-bound markets
- Fails in strong trends (price "walks" the overbought/oversold zone)

### Bollinger Band Strategies

**Classic Mean Reversion:**
- Buy when price touches lower band AND RSI < 30
- Sell when price touches upper band AND RSI > 70
- Settings: 20-period SMA, 2 standard deviations
- Use ATR (14-period) for dynamic stop-loss sizing

**Combined Strategy Performance:**
- 0.75 risk-reward ratio optimized for higher win rates
- Average return: 2.3% per trade in ranging markets
- Win rate: 71% during ranging conditions

### More Sophisticated Approaches

**Multi-Factor Mean Reversion:**
- Combine price deviation from mean + RSI + volume confirmation
- Add trend filter (only take mean reversion trades in direction of higher timeframe trend)
- Use Keltner Channels or Donchian Channels as alternatives to Bollinger Bands

**Statistical Approaches:**
- Z-score of price relative to rolling mean
- Entry at Z < -2, exit at Z = 0
- Lookback period: 20-60 days for equities

### Performance Metrics
| Metric | Typical Range |
|---|---|
| Annual return | 8-15% |
| Win rate | 60-70% (up to 91% with 2-day RSI) |
| Sharpe ratio | 0.4-1.75 (varies widely) |
| Max drawdown | 15-33% |
| Best timeframes | 4-hour and daily charts |

### Critical Warning
**Mean reversion fails catastrophically in strong trends.** The 2020 COVID crash, 2022 rate hike cycle, and similar regime changes can wipe out years of gains. Always use stop-losses (2-3% max loss per trade) and consider a trend filter overlay.

### Best Markets
- Large-cap stocks, utilities, consumer staples
- Major forex pairs
- Equity indices (SPY, QQQ)
- High-liquidity, low-momentum environments

### Sources
- [QuantifiedStrategies - RSI Trading Strategy (91% Win Rate)](https://www.quantifiedstrategies.com/rsi-trading-strategy/)
- [BacktestMe - Mean Reversion Guide](https://backtestme.com/guides/mean-reversion-strategies)
- [EzAlgo - 6 Mean Reverting Strategies 2025](https://www.ezalgo.ai/blog/mean-reverting-trading-strategies)
- [TradeFundrr - Mean Reversion 2024](https://tradefundrr.com/mean-reversion-strategies/)
- [TraderVPS - RSI Strategy Backtest 2025](https://www.tradervps.com/blog/rsi-trading-strategy)

---

## 4. Pairs Trading

### Finding Cointegrated Pairs

**Three-Phase Process:**
1. **Pairs Selection**: Screen for candidates within same sector/industry
2. **Cointegration Test**: Engle-Granger or Johansen test for stationarity of the spread
3. **Trading Rules**: Define entry/exit based on spread z-score

**Why Cointegration > Correlation:**
- Correlation measures direction similarity; cointegration measures spread stability
- Two stocks can be highly correlated but NOT cointegrated
- Cointegration means the spread (log(A) - n*log(B)) is stationary with constant mean/variance

### Entry/Exit Rules

**Entry:**
- Z-score of spread reaches +/- 2 sigma (aggressive: +/- 1.2 sigma)
- Lower thresholds = more trades, higher Sharpe, but more volatility and drawdowns

**Exit:**
- Z-score crosses 0 (mean reversion complete)
- Optimized exits improve profitability and reduce turnover

**Stop-Loss:**
- If entry at 2-sigma, stop at 3-sigma
- If cointegration breaks while position is on, cut immediately

### How Often Pairs Break Down
- Cointegration is NOT stable over time
- Relationships can break during regime changes, M&A activity, or fundamental shifts
- Spread series are often affected by permanent shocks
- **Must retest cointegration regularly** (monthly or quarterly)
- Advanced fix: Time-varying cointegration via Kalman filter

### Backtested Performance
| Method | Mean Monthly Excess Return (after costs) |
|---|---|
| Distance method | 36 bps |
| Cointegration method | 33 bps |
| Copula method | 5 bps |

- Overall, pairs trading **fails to outperform the market benchmark** from 1990-2020 using distance/cointegration methods
- **Performs strongly during bear markets** (market-neutral nature provides hedge)
- Profitability has dropped significantly in recent years
- Distance and cointegration methods have fewer trading opportunities; copula frequency is more stable

### Advanced Approaches (2025)
- Machine learning (neural networks, SVM, random forests) to find non-linear relationships
- Partial cointegration allowing random walk component
- Kalman filter for dynamic hedge ratio adjustment

### Suitability for Small Accounts
- **Challenge**: Requires short selling (margin account, borrow costs)
- **Capital**: Need enough for both legs; minimum ~$5K-$10K practical
- **ETF pairs** are more accessible than individual stock pairs (easier to borrow, more liquid)

### Sources
- [QuantInsti - Pairs Trading Basics](https://blog.quantinsti.com/pairs-trading-basics/)
- [Springer - Cointegration-based pairs trading with ETFs (2025)](https://link.springer.com/article/10.1057/s41260-025-00416-0)
- [ChartWatcher - 7 Innovative Pairs Trading Strategies 2025](https://chartswatcher.com/pages/blog/7-innovative-pairs-trading-strategies-for-2025)
- [Interactive Brokers - Pairs Trading Basics](https://www.interactivebrokers.com/campus/ibkr-quant-news/pairs-trading-basics-correlation-cointegration-and-strategy-part-i/)
- [Quantpedia - Pairs Trading with Stocks](https://quantpedia.com/strategies/pairs-trading-with-stocks)
- [QuantifiedStrategies - Pairs Trading Strategy](https://www.quantifiedstrategies.com/pairs-trading-strategy/)

---

## 5. Sector Rotation / Momentum

### Faber's Sector Rotation
Based on Mebane Faber's research using sector/industry data from the 1920s:
- Simple momentum strategy outperformed buy-and-hold ~70% of the time over 80+ years
- Works across 1, 3, 6, 9, and 12-month lookback periods
- Performance improves with a trend-following filter (e.g., price > 10-month SMA)

**Implementation:**
- Use 3-month Rate-of-Change (ROC) as compromise lookback
- Buy top 3 sectors, equal weight (33% each)
- Rebalance monthly
- Common ETFs: XLK, XLF, XLE, XLV, XLY, XLP, XLI, XLB, XLU, XLRE, XLC

### Dual Momentum (Gary Antonacci)
Combines relative momentum + absolute momentum:

**Rules:**
1. If SPY is trending up (12-month return > 0), buy top 4 sectors by 12-month momentum
2. If SPY is trending down, move 100% to AGG (bonds)
3. Rebalance monthly

**This provides both offense (relative momentum picks winners) and defense (absolute momentum exits to bonds in downtrends).**

### Faber's Tactical Asset Allocation (TAA)
Uses 5 ETFs: SPY (US stocks), EFA (foreign stocks), BND (bonds), VNQ (REITs), GSG (commodities)
- Pick top 3 by 12-month momentum
- Equal weight, monthly rebalance
- Decreases overall risk and improves risk-adjusted returns

### Performance
- Fidelity study: Sector rotation outperformed S&P 500 by 3.6% annually over 15 years
- Country/industry momentum: ~5% annual excess return using actual ETF data
- **Alpha has diminished over time** as more capital chases the same signals

### Suitability for Small Accounts
- **Excellent fit**: Only requires buying 3-5 ETFs
- Minimal trading (monthly rebalance)
- No leverage, no shorting needed
- Can start with $1K+ easily
- Low transaction costs (commission-free ETFs at most brokers)

### Tools
- [Portfolio Visualizer](https://www.portfoliovisualizer.com/analysis) - Free backtesting
- [AllocateSmartly](https://allocatesmartly.com) - TAA strategy library with live tracking
- [QuantConnect](https://www.quantconnect.com) - Open-source backtesting

### Sources
- [StockCharts - Faber's Sector Rotation](https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/fabers-sector-rotation-trading-strategy)
- [Quantpedia - Sector Momentum](https://quantpedia.com/strategies/sector-momentum-rotational-system)
- [Quantpedia - Momentum Asset Allocation](https://quantpedia.com/strategies/asset-class-momentum-rotational-system)
- [QuantConnect - Dual Momentum Sector Rotation](https://www.quantconnect.com/forum/discussion/527/dual-momentum-sector-rotation/)
- [Quantpedia - How to Improve ETF Sector Momentum](https://quantpedia.com/how-to-improve-etf-sector-momentum/)

---

## 6. Options Strategies for Income

### The Wheel Strategy

**Mechanics:**
1. Sell cash-secured puts on a stock you want to own
2. If assigned, buy the shares
3. Sell covered calls on the shares
4. If called away, restart at step 1

**Backtested Returns:**
- **Optimistic**: ~10-19% annualized (one SPY analysis showed 1.6% monthly = ~19%/year)
- **Spintwig backtest (rigorous)**: NOT a single SPY Wheel 45-DTE strategy outperformed buy-and-hold. The long stock position accounted for 94-99% of total return; options were inconsequential.
- **QuantConnect backtest**: Sharpe ratio 1.083 vs SPY buy-and-hold 0.7 (outperformed across all parameter combinations)
- **Realistic expectation**: ~10-15% annually in favorable conditions

**Small Account Challenge:**
- Cash-secured puts require capital to buy 100 shares at strike price
- $50 stock = $5,000 tied up per contract
- Limits small accounts to cheaper stocks ($5-$20 range)

### Iron Condors

**Structure:** Sell OTM bear call spread + OTM bull put spread, same expiration

**Performance:**
- Return per trade: 10-20% of capital at risk
- Win rate: 60-75% depending on strike selection
- Monthly returns: 5-8% on deployed capital (when it works)
- Best with 30-45 DTE, manage at 50-75% of max profit

**Risk Management:**
- Never risk more than 2-3% of capital per trade
- Avoid earnings weeks
- Close or roll when tested (don't wait for full loss)

### Credit Spreads

**Realistic returns**: 2-20% in premiums per trade with optimal:
- DTE: 21-60 days
- Delta: 10-30 (probability of being ITM)
- IV environment: Low-to-medium implied volatility
- Theta decay provides the edge

### Comparison Table

| Strategy | Annual Return | Win Rate | Min Capital | Complexity |
|---|---|---|---|---|
| Wheel (SPY) | 10-15% | High (with quality stocks) | ~$5K-$45K per position | Low |
| Iron Condor | Variable (5-8%/month on deployed) | 60-75% | $500-$2K per spread | Medium |
| Credit Spreads | 2-20% per trade | Varies by delta | $500-$2K per spread | Low-Medium |

### Critical Reality Check
- The Wheel strategy may add **very little** over simply buying and holding the underlying stock
- Iron condors suffer in trending markets or volatility spikes
- Commissions and bid-ask spreads on 4-leg options strategies eat into small account returns
- Options income is NOT passive -- requires active monitoring and management

### Sources
- [Charles Schwab - Wheel Strategy](https://www.schwab.com/learn/story/three-things-to-know-about-wheel-strategy)
- [Spintwig - SPY Wheel 45-DTE Backtest](https://spintwig.com/spy-wheel-45-dte-options-backtest/)
- [Option Alpha - Wheel Strategy Guide](https://optionalpha.com/blog/wheel-strategy)
- [QuantConnect - Automating the Wheel Strategy](https://www.quantconnect.com/research/17871/automating-the-wheel-strategy/)
- [Option Alpha - Iron Condor](https://optionalpha.com/strategies/iron-condor)
- [Fidelity - Iron Condor Strategy](https://www.fidelity.com/viewpoints/active-investor/iron-condor-strategy)
- [SlashTraders - SPY Wheel Strategy](https://slashtraders.com/en/blog/sp500-spy-etf-wheel-strategy/)

---

## 7. Volume Profile Analysis

### How Institutions Use VWAP
- VWAP is an **execution benchmark**, not an entry signal for institutions
- Large orders are split across the day; performance measured against VWAP
- Algorithms (VWAP, TWAP) execute to minimize market impact
- When price pulls back to VWAP in an uptrend, institutional algorithms often trigger buys

### Detecting Accumulation/Distribution
- **Above VWAP on high volume** = institutional buying pressure (accumulation)
- **Below VWAP on high volume** = institutional selling (distribution)
- VWAP defense during pullbacks signals institutional support

### Volume Profile Concepts
- **High Volume Nodes (HVN)**: Price acceptance zones, act as support/resistance
- **Low Volume Nodes (LVN)**: Price rejection zones, price moves through quickly
- **Point of Control (POC)**: Price level with highest traded volume

### Key Trading Strategies

**1. VWAP Trend Bias**
- Price > VWAP = bullish bias (only take longs)
- Price < VWAP = bearish bias (only take shorts)

**2. VWAP Bounce/Pullback**
- In established trend, buy/sell pullbacks to VWAP
- Institutional algorithms often defend VWAP level

**3. VWAP Mean Reversion**
- When price deviates 1-2 standard deviations from VWAP, trade toward VWAP
- Requires volume confirmation of reversal

**4. VWAP Breakout**
- Price breaks above/below VWAP on volume 2x the 20-period average
- Confirms institutional participation in the move

**5. Anchored VWAP + POC**
- Buy when price < VWAP AND < POC, volume > 3x 20-day average, RSI < 40
- Sell when price > VWAP AND > POC, volume > 3x 20-day average, RSI > 60

### Important Caveats
- VWAP unreliable in first 30-60 minutes (insufficient cumulative volume)
- Low float stocks (<$1B market cap) lack institutional participation; VWAP is meaningless
- Dark pool/off-exchange activity means visible VWAP misses some institutional flow
- Algorithms test VWAP creating false breaks that trap retail traders

### Sources
- [TradingShastra - VWAP Institutional Indicator 2025](https://tradingshastra.com/vwap-institutional-indicator/)
- [Charles Schwab - Volume-Weighted Indicators](https://www.schwab.com/learn/story/how-to-use-volume-weighted-indicators-trading)
- [Tickrad - Volume Analysis Mastery 2025](https://www.tickrad.com/blog/volume-analysis-mastery-institutional-footprints-2025)
- [FibAlgo - VWAP Trading Strategy 2026](https://fibalgo.com/education/vwap-trading-strategy-institutional-benchmark)
- [Mind Math Money - VWAP Complete Guide 2025](https://www.mindmathmoney.com/articles/vwap-trading-strategy-the-ultimate-guide-to-volume-weighted-average-price-in-tradingview-2025)

---

## 8. Schwab API Capabilities

### Overview
The Schwab Trader API (successor to TD Ameritrade API, fully transitioned as of May 2024) provides free API access with any brokerage account. No minimum balance required.

### Two Main API Groups
1. **Accounts and Trading Production**: Positions, balances, cash available, order placement
2. **Market Data Production**: Quotes, price history, daily movers

### Data Availability

| Data Type | Availability | Details |
|---|---|---|
| Real-time quotes | Yes (streaming) | WebSocket-based, up-to-the-second |
| Level 1 quotes | Yes | Equities, options, futures |
| Level 2 data | Yes | NYSE and NASDAQ |
| Options chains | Yes | Full chains, all strikes/expirations |
| Historical bars (daily) | Yes | Up to 15 years for equities/ETFs |
| Historical bars (intraday) | Yes | Up to 6 months |
| Options streaming | Yes | No hard 100-line limit per symbol |
| Futures streaming | Yes (quotes only) | No historical bars for futures |

### Order Capabilities
- Market, limit, stop-loss, stop-limit orders
- Stocks, ETFs, options, mutual funds
- Real-time status updates, modification, cancellation
- **Limitation**: Multi-leg/spread options and advanced orders not fully supported

### Rate Limits
- Data requests: 120 requests/minute (application level)
- Trade requests: 2-4 per second
- Streaming: Hundreds of symbols simultaneously

### Authentication
- OAuth 2.0 standard
- **Manual refresh required every 7 days** (significant limitation for fully automated systems)

### Key Limitations
- No native paper trading
- Multi-leg options support is limited
- Futures: streaming quotes only, no historical data or trading
- App approval process: Describe use case simply (avoid "advanced algorithmic trading" language)
- Less sophisticated than Interactive Brokers TWS API for complex order types

### Community Libraries
- **schwab-py** (Python) - Most popular; supports streaming, Level 2, options
- **schwabr** (R package)
- **QuantConnect** - Live trading integration
- **Lumibot** - Direct integration for equities and options

### Cost
- **Free** with any Schwab brokerage account
- No monthly API fees (unlike many competitors charging $50-200/month)

### Sources
- [Schwab Developer Portal](https://developer.schwab.com/products/trader-api--individual)
- [schwab-py Documentation](https://schwab-py.readthedocs.io/en/latest/streaming.html)
- [PickMyTrade - TD Ameritrade API 2025](https://blog.pickmytrade.trade/td-ameritrade-have-api-2025/)
- [TradersPost - TD Ameritrade API Status](https://blog.traderspost.io/article/does-td-ameritrade-have-api)
- [Medium - Unofficial Guide to Schwab APIs](https://medium.com/@carstensavage/the-unofficial-guide-to-charles-schwabs-trader-apis-14c1f5bc1d57)
- [QuantConnect - Schwab Documentation](https://www.quantconnect.com/docs/v2/cloud-platform/live-trading/brokerages/charles-schwab)

---

## 9. Risk Parity

### The Core Idea
Traditional 60/40 portfolios derive ~90% of volatility from equities despite only 60% capital allocation. Risk parity allocates based on **risk contribution**, not capital, so each asset class contributes equally to total portfolio volatility.

### Bridgewater's All Weather Approach
Ray Dalio's principles:
1. Balance risk across economic environments (growth up/down, inflation up/down)
2. Build 10-15 uncorrelated return streams
3. Accept you cannot predict the future

**In practice**: ~1 unit stocks + 3-4 units bonds (leveraged up to match stock volatility)

### Simplified Retail Implementation

**DIY Approach:**
1. Calculate volatility of each asset class (stocks, bonds, commodities, REITs, gold)
2. Allocate inversely proportional to volatility
3. Rebalance quarterly
4. Use Portfolio Visualizer to optimize

**New in 2025: SPDR Bridgewater All Weather ETF (ALLW)**
- Launched March 2025 by State Street + Bridgewater
- Uses ~1.8x leverage via futures
- Expense ratio: ~0.85%
- Direct retail access to Bridgewater's approach without managing leverage yourself

### Performance Reality Check (Critical 2025 Research)
- Risk parity generally **underperforms** a traditional 60/40 portfolio
- Delivers lower annualized returns AND inferior Sharpe and Sortino ratios
- Bond yield levels and changes critically drive performance
- 2022-2023 was catastrophic for leveraged duration strategies (stocks AND bonds fell together)
- Adding a simple expected return model to the framework materially improves outcomes

### Key Risks
1. **Leverage dependency**: Must lever bonds to achieve competitive returns; leverage amplifies losses
2. **Correlation breakdown**: When stock-bond correlation turns positive (as in 2022), diversification thesis fails
3. **Rising rate environment**: Bonds (the largest allocation) suffer sustained drawdowns
4. **Historical dependence**: Volatility and correlation estimates from the past may not hold

### Suitability for Small Accounts
- **ALLW ETF**: Most practical option; buy one ETF, get Bridgewater's approach
- **DIY**: Challenging without futures access for leverage
- **Capital needed**: $1K+ for ALLW; $5K+ for DIY multi-asset version
- **Best used as**: Core allocation complement, not standalone strategy

### Sources
- [Bridgewater - The All Weather Story](https://www.bridgewater.com/research-and-insights/the-all-weather-story)
- [Tokenist - Risk Parity Explained 2025](https://tokenist.com/investing/risk-parity/)
- [AQR - Understanding Risk Parity](https://www.aqr.com/-/media/AQR/Documents/Insights/White-Papers/Understanding-Risk-Parity.pdf)
- [QuantInsti - Risk Parity Portfolio Python](https://blog.quantinsti.com/risk-parity-portfolio/)
- [EBC - Ray Dalio Strategy Explained](https://www.ebc.com/forex/ray-dalio-strategy-explained-all-weather-risk-parity)
- [LongTail Alpha - Risk Parity with Trend-Following (2025)](https://www.longtailalpha.com/wp-content/uploads/2025/09/LongTail-Alpha-Risk-Parity-With-Trend-Following-1.pdf)

---

## 10. Seasonality and Calendar Effects

### January Effect
- Small-cap stocks historically delivered 3.8% January returns vs 1.2% for large-caps
- **Largely dead**: Averaged 1.85% gains through 1993, but only 0.28% since then
- Not a standalone strategy anymore; at best a contextual factor

### January Barometer
- "As January goes, so goes the year"
- Up January: average annual return ~17%; Down January: average -1.7%
- BUT stocks are positive 67% of the time anyway -- predictive power may be coincidental

### Sell in May and Go Away
- November-April historically delivers meaningfully stronger returns than May-October
- **Beats the market 80%+ of the time over 5-year horizons**
- However, staying fully invested still beats timing in/out due to missing best days
- Recently, May has not been reliably bad; the pattern has shifted somewhat

### Best and Worst Months (2006-2025)
- **Best**: November (strongest on average), March, April, October, December
- **Worst**: September (only month with negative average returns: -0.6% since 1950), January, February, June, August

### Santa Claus Rally
- Last 5 trading days of December + first 2 of January
- Positive 78% of the time since 1950
- Average gain: 1.3% in 7 trading days

### FOMC Pre-Announcement Drift (MAJOR FINDING)

**This is one of the most robust calendar anomalies still documented:**

- S&P 500 increased 49 bps on average in the 24 hours before FOMC announcements (since 1994)
- **80% of the annual US equity premium was earned in just the 24 hours before FOMC meetings**
- Annualized Sharpe ratio >1.1 for a strategy holding only during these windows
- Extended "monetary momentum" shows returns drifting up to 25 days before decisions
- **Still persistent through December 2024** despite being published over a decade ago

**Practical Implementation:**
- Buy SPY 24-48 hours before FOMC announcement
- Sell after announcement
- Stronger effect around meetings with press conferences
- Can be leveraged (only ~8 days of market exposure per year)

**Options angle:** IV rises but RV compresses pre-FOMC. Selling ATM straddles at T-5, closing at T-1 produced 69.6% win rate with +2.1% average return on capital at risk.

### Options Expiration (OPEX) Effects
- Large-cap stocks with actively traded options have higher returns during OPEX week
- Caused by hedge rebalancing by market makers
- OPEX day itself has negative returns on average
- Day after OPEX: average gain is zero (vs 0.04% for random day)
- Pin risk: stocks gravitate toward heavily traded strikes near expiration
- **Triple Witching** (quarterly): >$1 trillion in delta notional expires; increased volatility

### Combined Seasonal Strategy
A model combining Sell-in-May + Turn-of-Month + FOMC drift + State-Dependent Momentum:
- 9.56% annualized returns
- 6.28% volatility
- Sharpe ratio: 0.77 (nearly 2x buy-and-hold Sharpe)

### Modern Caveats
- Algorithmic trading arbitrages simple calendar effects away
- Central bank policy now dominates seasonal factors
- Missing just 10 best days in 30 years cuts returns roughly in half
- **Best use: contextual awareness, not standalone strategies**

### Sources
- [Investing.com - Seasonality in S&P 500](https://www.investing.com/analysis/seasonality-in-the-sp-500-revisiting-calendar-effects-in-a-modern-market-200672384)
- [American Century - January Effect](https://www.americancentury.com/insights/the-january-effect-and-stock-market-seasonality/)
- [QuantifiedStrategies - January Effect Backtest](https://www.quantifiedstrategies.com/january-effect-in-stocks/)
- [NY Fed - Pre-FOMC Announcement Drift](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr512.pdf)
- [Quantpedia - FOMC Meeting Effect](https://quantpedia.com/strategies/federal-open-market-committee-meeting-effect-in-stocks)
- [QuantifiedStrategies - FOMC Trading Strategy](https://www.quantifiedstrategies.com/fomc-meeting-trading-strategy/)
- [QuantifiedStrategies - OPEX Week Effect](https://www.quantifiedstrategies.com/the-option-expiration-week-effect/)
- [Quantpedia - OPEX Week Effect](https://quantpedia.com/strategies/option-expiration-week-effect)
- [InvestorPlace - Timing Pattern Beating the Market](https://investorplace.com/hypergrowthinvesting/2026/01/the-simple-timing-pattern-thats-beating-the-market/)
- [Trade That Swing - Best and Worst Months](https://tradethatswing.com/seasonal-patterns-of-the-stock-market/)

---

## 11. Strategy Comparison Matrix

### For $1K-$50K Accounts

| Strategy | Min Capital | Expected Annual Return | Sharpe Ratio | Win Rate | Complexity | Time Required | Best Market |
|---|---|---|---|---|---|---|---|
| **PEAD (microcap)** | $1K | 5-15% alpha | 0.5-0.8 | 55-60% | Medium | Low (quarterly) | All |
| **Gap-and-Go** | $1K ($25K for unlimited day trades) | Highly variable | N/A | Variable | Medium | High (daily active) | Volatile/news |
| **Mean Reversion (RSI)** | $1K | 8-15% | 0.4-1.75 | 60-91% | Low-Medium | Medium | Range-bound |
| **Pairs Trading** | $5K-$10K | 3-5% alpha | 0.3-0.6 | 50-60% | High | Medium | Bear markets |
| **Sector Rotation** | $1K | 3-5% alpha | 0.5-0.8 | ~70% (monthly) | Low | Very Low (monthly) | Trending |
| **Dual Momentum TAA** | $1K | Market-like with lower risk | 0.6-0.9 | ~70% | Low | Very Low (monthly) | All |
| **Wheel Strategy** | $5K+ | 10-15% | ~1.0 | High | Low-Medium | Medium | Sideways/bull |
| **Iron Condors** | $500-$2K | 5-8%/month deployed | Variable | 60-75% | Medium | Medium-High | Low vol |
| **VWAP Trading** | $1K ($25K for day trading) | Variable | N/A | Variable | Medium-High | High (intraday) | Trending |
| **Risk Parity (ALLW)** | $100+ | 5-8% (lower vol) | 0.4-0.6 | N/A | Very Low | Very Low | All |
| **FOMC Drift** | $1K | 8-9% (leveraged) | >1.1 | ~70% | Low | Very Low (8 days/yr) | All |
| **Seasonal Composite** | $1K | ~9.5% | 0.77 | ~65% | Low | Low | All |

### Top Recommendations by Account Size

**$1K-$5K:**
1. Dual Momentum / Sector Rotation (monthly ETF rotation)
2. Mean Reversion on SPY/QQQ (2-day RSI)
3. FOMC pre-announcement drift (8 trades/year)
4. Seasonal composite strategy

**$5K-$25K:**
All of the above, plus:
5. Wheel strategy on $5-$20 stocks
6. Credit spreads / iron condors
7. PEAD on small-cap earnings surprises

**$25K-$50K:**
All of the above, plus:
8. Gap-and-Go day trading (PDT rule cleared)
9. Pairs trading with ETFs
10. VWAP-based intraday strategies

### Key Principles for All Account Sizes
1. **Risk per trade**: Never more than 1-2% of account
2. **Diversify strategies**: Combine uncorrelated approaches
3. **Backtest everything**: Use QuantConnect, Portfolio Visualizer, or Python before risking real money
4. **Transaction costs matter**: More so for smaller accounts
5. **PDT rule**: Accounts under $25K limited to 3 day trades per 5 business days (margin accounts)
6. **Start simple**: Sector rotation + mean reversion + FOMC drift is a solid three-strategy combination
