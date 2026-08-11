"""
main.py — Entry point.  Runs the webhook server and Discord bot concurrently.
"""
from __future__ import annotations

import asyncio
import logging
import sys

import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import validate_config, TRADING_MODE
from database import Database
from broker import Broker
from discord_bot import DiscordBot
from webhook_handler import create_app
from scheduler import Scheduler

logging.basicConfig(level=logging.INFO, format="%(levelname)-5s %(name)-14s %(message)s")
logger = logging.getLogger("main")


async def run() -> None:
    validate_config()
    mode_label = "PAPER (fake money)" if TRADING_MODE == "paper" else "LIVE"
    logger.info(f"Starting trading bot in {mode_label}")

    db = Database()
    await db.init()

    broker = Broker()
    await broker.connect()

    discord_bot = DiscordBot(db=db, broker=broker)

    app = create_app(db=db, broker=broker, discord_bot=discord_bot)
    server_config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="warning")
    server = uvicorn.Server(server_config)
    logger.info("Webhook listening on port 8000 at POST /webhook")

    sched_obj = Scheduler(db=db, broker=broker, discord_bot=discord_bot)
    aps = AsyncIOScheduler(timezone="America/New_York")
    aps.add_job(sched_obj.morning_brief, CronTrigger(hour=8, minute=0, timezone="America/New_York"))
    aps.add_job(sched_obj.nightly_recap, CronTrigger(hour=21, minute=0, timezone="America/New_York"))
    aps.start()
    logger.info("Scheduled: morning brief 08:00 ET, nightly recap 21:00 ET")

    try:
        await asyncio.gather(server.serve(), discord_bot.start_bot())
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Shutting down")
    finally:
        aps.shutdown(wait=False)
        await discord_bot.close()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        sys.exit(0)
