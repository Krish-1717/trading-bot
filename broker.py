"""
broker.py — Alpaca paper/live trading wrapper.
"""
from __future__ import annotations
import logging
from typing import Any
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest, StopOrderRequest
from config import ALPACA_API_KEY, ALPACA_SECRET_KEY, TRADING_MODE

logger = logging.getLogger("broker")


class Broker:
    def __init__(self):
        self._client = None
        self.paper = TRADING_MODE == "paper"

    async def connect(self):
        if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
            logger.warning("Alpaca keys not set — broker running in MOCK mode.")
            return
        try:
            self._client = TradingClient(
                api_key=ALPACA_API_KEY, secret_key=ALPACA_SECRET_KEY, paper=self.paper)
            acct = self._client.get_account()
            logger.info(f"Broker connected in {'PAPER' if self.paper else 'LIVE'} mode")
        except Exception as exc:
            logger.error(f"Broker connection failed: {exc}")
            self._client = None

    async def buy(self, symbol, shares):
        logger.info(f"BUY {shares} x {symbol}")
        if self._client is None:
            return self._mock_order("buy", symbol, shares)
        req = MarketOrderRequest(symbol=symbol, qty=shares, side=OrderSide.BUY, time_in_force=TimeInForce.DAY)
        return self._client.submit_order(req).dict()

    async def sell(self, symbol):
        logger.info(f"SELL {symbol}")
        if self._client is None:
            return self._mock_order("sell", symbol, 0)
        try:
            self._client.close_position(symbol)
            return {"symbol": symbol, "action": "sell", "status": "closed"}
        except Exception as exc:
            logger.error(f"Failed to close {symbol}: {exc}")
            return {"symbol": symbol, "action": "sell", "status": "error", "detail": str(exc)}

    async def place_stop(self, symbol, shares, stop_price):
        logger.info(f"STOP {symbol} x {shares} @ {stop_price}")
        if self._client is None:
            return self._mock_order("stop", symbol, shares, stop_price=stop_price)
        req = StopOrderRequest(symbol=symbol, qty=shares, side=OrderSide.SELL,
                               time_in_force=TimeInForce.GTC, stop_price=stop_price)
        return self._client.submit_order(req).dict()

    async def get_account_equity(self):
        if self._client is None:
            return 0.0
        try:
            return float(self._client.get_account().equity)
        except Exception:
            return 0.0

    async def get_positions(self):
        if self._client is None:
            return []
        try:
            return [p.dict() for p in self._client.get_all_positions()]
        except Exception:
            return []

    @staticmethod
    def _mock_order(action, symbol, qty, stop_price=None):
        return {"symbol": symbol, "action": action, "qty": qty,
                "stop_price": stop_price, "status": "mock — no Alpaca keys"}
