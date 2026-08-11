# AI Trading Bot - How It Works

## Overview
This bot trades 5 markets 24/7 using paper (simulated) trading via Alpaca.
It sends alerts to Discord and shows a live web dashboard.

## Markets & Strategies

| Market | Symbol | Strategy | Timeframe |
|--------|--------|----------|-----------|
| S&P 500 | SPY | Mean Reversion (RSI + Bollinger Bands) | 15 min |
| NASDAQ | QQQ | Mean Reversion (RSI + Bollinger Bands) | 15 min |
| Bitcoin | BTCUSD | Momentum Breakout | 1 hour |
| Gold | GLD | Trend Following (EMA + ADX) | 4 hour |
| Oil | USO | Trend Following (EMA + ADX) | 4 hour |

## Risk Management
- Hard 1% stop loss on every trade
- ATR-based position sizing (risk / ATR x multiplier)
- Maximum 5 simultaneous positions
- Correlated assets cannot be held at the same time (SPY/QQQ, GLD/USO)

## Sending a Signal (TradingView Webhook)
POST to `https://your-railway-url/webhook` with JSON:
```json
{
  "secret": "your_webhook_secret",
  "asset": "SPY",
  "action": "buy",
  "price": 450.00,
  "atr": 2.5
}
```

## Discord Commands
- `!status` - bot health and uptime
- `!positions` - open positions with P&L
- `!pnl` - today's P&L summary
- `!signals` - recent signals
- `!markets` - market status
- `!pause` - pause trading (no new entries)
- `!resume` - resume trading
- `!help` - show all commands

## Files
- `main.py` - entry point, runs bot + server together
- `config.py` - loads environment variables
- `risk_engine.py` - position sizing and risk checks
- `database.py` - SQLite state (positions, trades, signals)
- `broker.py` - Alpaca API wrapper (paper trading)
- `discord_bot.py` - Discord commands and notifications
- `webhook_handler.py` - FastAPI server, dashboard, webhook endpoint
- `scheduler.py` - morning brief (8am ET) and nightly recap (9pm ET)
- `dashboard.html` - web dashboard with live charts

## Environment Variables
See `.env.template` for all required variables.
Set these in Railway under your project's Variables tab.
