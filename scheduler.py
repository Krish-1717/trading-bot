"""
scheduler.py — Scheduled tasks (morning brief, nightly recap).
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from database import Database
from broker import Broker
from discord_bot import DiscordBot

logger = logging.getLogger("scheduler")


class Scheduler:
    def __init__(self, db, broker, discord_bot):
        self.db = db
        self.broker = broker
        self.discord = discord_bot

    async def morning_brief(self):
        logger.info("Sending morning brief")
        try:
            equity = await self.broker.get_account_equity()
            positions = await self.db.get_open_positions()
            await self.discord.notify_morning_brief(equity, len(positions))
        except Exception as exc:
            logger.error(f"Morning brief failed: {exc}")

    async def nightly_recap(self):
        logger.info("Sending nightly recap")
        try:
            pnl = await self.db.get_daily_pnl()
            trades = await self.db.get_all_trades()
            today = datetime.now(timezone.utc).date().isoformat()
            closed_today = sum(1 for t in trades if t["exit_time"].startswith(today))
            await self.discord.notify_nightly_recap(pnl, closed_today)
        except Exception as exc:
            logger.error(f"Nightly recap failed: {exc}")
