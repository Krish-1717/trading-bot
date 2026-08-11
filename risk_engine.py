"""
risk_engine.py — Position sizing, correlation filter, and signal validation.
"""
from __future__ import annotations
from config import TOTAL_CAPITAL, RISK_PER_TRADE, ATR_MULTIPLIER, MAX_POSITIONS, CORRELATION_GROUPS


class RiskEngine:
    def __init__(self, total_capital=TOTAL_CAPITAL, risk_per_trade=RISK_PER_TRADE,
                 atr_multiplier=ATR_MULTIPLIER, max_positions=MAX_POSITIONS):
        self.total_capital = total_capital
        self.risk_per_trade = risk_per_trade
        self.atr_multiplier = atr_multiplier
        self.max_positions = max_positions

    def dollar_risk(self):
        return self.total_capital * self.risk_per_trade

    def stop_distance(self, atr):
        return atr * self.atr_multiplier

    def size_position(self, price, atr):
        if atr <= 0 or price <= 0:
            return 0, 0.0
        dist = self.stop_distance(atr)
        shares = int(self.dollar_risk() / dist)
        stop_price = round(price - dist, 2)
        return shares, stop_price

    def find_correlation_conflict(self, new_asset, open_assets):
        key = new_asset.upper()
        for group in CORRELATION_GROUPS:
            if key in group:
                for held in open_assets:
                    if held.upper() in group and held.upper() != key:
                        return held
        return None

    def can_open_position(self, num_open):
        return num_open < self.max_positions

    def validate_signal(self, asset, action, price, atr, open_assets):
        if action.lower() == "sell":
            return True, "sell signal approved"
        if price <= 0:
            return False, f"invalid price {price}"
        if atr <= 0:
            return False, f"invalid ATR {atr}"
        if not self.can_open_position(len(open_assets)):
            return False, f"max positions reached ({self.max_positions})"
        conflict = self.find_correlation_conflict(asset, open_assets)
        if conflict:
            return False, f"{conflict} is already long and moves with {asset}"
        shares, stop = self.size_position(price, atr)
        if shares < 1:
            return False, "sized below 1 share"
        return True, f"approved: {shares} shares @ stop {stop:.2f}"
