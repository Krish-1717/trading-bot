"""
database.py — Async SQLite wrapper for all persistent bot state.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any
import aiosqlite
from config import DB_PATH

logger = logging.getLogger("database")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS positions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    asset       TEXT    NOT NULL,
    shares      INTEGER NOT NULL,
    entry_price REAL    NOT NULL,
    stop_price  REAL    NOT NULL,
    entry_time  TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'open'
);
CREATE TABLE IF NOT EXISTS signals (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    asset     TEXT NOT NULL,
    action    TEXT NOT NULL,
    price     REAL NOT NULL,
    atr       REAL,
    approved  INTEGER NOT NULL,
    reason    TEXT,
    timestamp TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trades (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    asset       TEXT NOT NULL,
    shares      INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    exit_price  REAL NOT NULL,
    pnl         REAL NOT NULL,
    entry_time  TEXT NOT NULL,
    exit_time   TEXT NOT NULL
);
"""

def _now():
    return datetime.now(timezone.utc).isoformat()

class Database:
    def __init__(self, path=DB_PATH):
        self._path = path

    async def init(self):
        async with aiosqlite.connect(self._path) as db:
            await db.executescript(_SCHEMA)
            await db.commit()
        logger.info(f"Database ready at {self._path}")

    async def open_position(self, asset, shares, entry_price, stop_price):
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                "INSERT INTO positions (asset, shares, entry_price, stop_price, entry_time) VALUES (?, ?, ?, ?, ?)",
                (asset.upper(), shares, entry_price, stop_price, _now()),
            )
            await db.commit()
            return cur.lastrowid

    async def close_position(self, asset, exit_price):
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM positions WHERE asset=? AND status='open' LIMIT 1", (asset.upper(),)
            )
            row = await cur.fetchone()
            if row is None:
                return None
            pos = dict(row)
            pnl = (exit_price - pos["entry_price"]) * pos["shares"]
            await db.execute("UPDATE positions SET status='closed' WHERE id=?", (pos["id"],))
            await db.execute(
                "INSERT INTO trades (asset, shares, entry_price, exit_price, pnl, entry_time, exit_time) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (pos["asset"], pos["shares"], pos["entry_price"], exit_price, pnl, pos["entry_time"], _now()),
            )
            await db.commit()
            pos["exit_price"] = exit_price
            pos["pnl"] = pnl
            return pos

    async def get_open_positions(self):
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM positions WHERE status='open' ORDER BY entry_time")
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def get_open_assets(self):
        positions = await self.get_open_positions()
        return [p["asset"] for p in positions]

    async def log_signal(self, asset, action, price, atr, approved, reason):
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                "INSERT INTO signals (asset, action, price, atr, approved, reason, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (asset.upper(), action, price, atr, int(approved), reason, _now()),
            )
            await db.commit()

    async def get_recent_signals(self, limit=10):
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM signals ORDER BY id DESC LIMIT ?", (limit,))
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def get_daily_pnl(self):
        today = datetime.now(timezone.utc).date().isoformat()
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute("SELECT COALESCE(SUM(pnl), 0) FROM trades WHERE exit_time LIKE ?", (f"{today}%",))
            row = await cur.fetchone()
            return float(row[0])

    async def get_all_trades(self):
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM trades ORDER BY exit_time DESC")
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
