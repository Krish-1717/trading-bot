"""webhook_handler.py — FastAPI app serving dashboard, REST API, WebSocket."""
from __future__ import annotations
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from config import WEBHOOK_SECRET, TRADING_MODE
from risk_engine import RiskEngine
if TYPE_CHECKING:
    from database import Database
    from broker import Broker
    from discord_bot import DiscordBot

logger = logging.getLogger("webhook")
_risk = RiskEngine()
_paused = False
_ws_clients: list = []

class SignalPayload(BaseModel):
    secret: str
    asset: str
    action: str = Field(..., pattern="^(buy|sell)$")
    price: float
    atr: float = 0.0

class ManualSignalPayload(BaseModel):
    asset: str
    action: str
    price: float
    atr: float = 0.0

async def broadcast(message: dict) -> None:
    dead = []
    for ws in _ws_clients:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.remove(ws)

def create_app(db, broker, discord_bot) -> FastAPI:
    app = FastAPI(title="Trading Bot", docs_url=None, redoc_url=None)
    _dashboard_path = Path(__file__).parent / "dashboard.html"

    @app.get("/", response_class=HTMLResponse)
    async def serve_dashboard():
        if _dashboard_path.exists():
            return HTMLResponse(_dashboard_path.read_text())
        return HTMLResponse("<h1>Dashboard loading...</h1>")

    @app.get("/health")
    async def health():
        return {"ok": True, "mode": TRADING_MODE}

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket):
        await websocket.accept()
        _ws_clients.append(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            if websocket in _ws_clients:
                _ws_clients.remove(websocket)

    @app.get("/api/positions")
    async def api_positions():
        positions = await db.get_open_positions()
        for p in positions:
            p["unrealised_pnl"] = 0.0
        return positions

    @app.get("/api/summary")
    async def api_summary():
        from datetime import datetime, timezone
        equity = await broker.get_account_equity()
        pnl = await db.get_daily_pnl()
        trades = await db.get_all_trades()
        today = datetime.now(timezone.utc).date().isoformat()
        today_trades = [t for t in trades if t["exit_time"].startswith(today)]
        wins = [t for t in trades if t["pnl"] > 0]
        win_rate = round(len(wins) / len(trades) * 100, 1) if trades else None
        return {"equity": equity or 100000, "daily_pnl": pnl,
                "trades_today": len(today_trades), "total_trades": len(trades), "win_rate": win_rate}

    @app.get("/api/signals")
    async def api_signals():
        return await db.get_recent_signals(20)

    @app.get("/api/pause")
    async def api_pause():
        global _paused
        _paused = True
        return {"paused": True}

    @app.get("/api/resume")
    async def api_resume():
        global _paused
        _paused = False
        return {"paused": False}

    @app.post("/api/manual-signal")
    async def api_manual_signal(payload: ManualSignalPayload):
        if payload.action.lower() == "sell":
            return await _handle_sell(payload.asset, payload.price, db, broker, discord_bot)
        return await _handle_buy(payload.asset, payload.price, payload.atr, db, broker, discord_bot)

    @app.post("/webhook")
    async def webhook(payload: SignalPayload):
        if payload.secret != WEBHOOK_SECRET:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid secret")
        if _paused:
            return JSONResponse({"approved": False, "reason": "trading is paused"})
        asset = payload.asset.upper()
        action = payload.action.lower()
        if action == "sell":
            return await _handle_sell(asset, payload.price, db, broker, discord_bot)
        return await _handle_buy(asset, payload.price, payload.atr, db, broker, discord_bot)

    return app

async def _handle_buy(asset, price, atr, db, broker, discord_bot):
    open_assets = await db.get_open_assets()
    approved, reason = _risk.validate_signal(asset=asset, action="buy", price=price, atr=atr, open_assets=open_assets)
    await db.log_signal(asset, "buy", price, atr, approved, reason)
    if not approved:
        await discord_bot.notify_rejected(asset, "buy", reason)
        await broadcast({"type": "signal_rejected", "asset": asset, "reason": reason})
        return JSONResponse({"approved": False, "reason": reason})
    shares, stop = _risk.size_position(price, atr)
    risk_dollars = _risk.dollar_risk()
    await broker.buy(asset, shares)
    await broker.place_stop(asset, shares, stop)
    await db.open_position(asset, shares, price, stop)
    await discord_bot.notify_opened(asset, shares, price, stop, risk_dollars)
    await broadcast({"type": "trade_opened", "asset": asset, "shares": shares, "price": price, "stop": stop})
    return JSONResponse({"approved": True, "asset": asset, "shares": shares, "stop": stop})

async def _handle_sell(asset, price, db, broker, discord_bot):
    await db.log_signal(asset, "sell", price, None, True, "sell signal approved")
    closed = await db.close_position(asset, price)
    if closed is None:
        msg = f"no open position found for {asset}"
        await discord_bot.notify_rejected(asset, "sell", msg)
        return JSONResponse({"approved": False, "reason": msg})
    await broker.sell(asset)
    await discord_bot.notify_closed(asset, closed["shares"], price, closed["pnl"])
    await broadcast({"type": "trade_closed", "asset": asset, "pnl": closed["pnl"]})
    return JSONResponse({"approved": True, "asset": asset, "pnl": closed["pnl"]})
