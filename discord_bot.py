"""discord_bot.py — Discord bot with commands and trade alerts."""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING
import discord
from discord.ext import commands
from config import DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID, TRADING_MODE, TOTAL_CAPITAL
if TYPE_CHECKING:
    from database import Database
    from broker import Broker
logger = logging.getLogger("discord_bot")
MARKET_EMOJI = {
    "SP500": "📈", "SPY": "📈", "NASDAQ": "📊", "QQQ": "📊",
    "BTC": "₿", "BITCOIN": "₿", "GOLD": "🏅", "GLD": "🏅",
    "OIL": "🛢", "USO": "🛢",
}
STRATEGY_MAP = {
    "SPY": "Mean Reversion · 15m", "QQQ": "Mean Reversion · 15m",
    "BTC": "Momentum Breakout · 1h", "BITCOIN": "Momentum Breakout · 1h",
    "GLD": "Trend Following · 4h", "USO": "Trend Following · 4h",
}

class DiscordBot:
    def __init__(self, db, broker):
        self.db = db
        self.broker = broker
        self._channel_id = DISCORD_CHANNEL_ID
        self._paused = False
        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
        self._channel = None
        self._register_events()
        self._register_commands()

    async def start_bot(self):
        await self.bot.start(DISCORD_BOT_TOKEN)

    async def close(self):
        await self.bot.close()

    async def _get_channel(self):
        if self._channel is not None:
            return self._channel
        ch = self.bot.get_channel(self._channel_id)
        if ch and isinstance(ch, discord.TextChannel):
            self._channel = ch
        return self._channel

    async def send(self, message):
        ch = await self._get_channel()
        if ch is None:
            logger.warning(f"Channel {self._channel_id} not found")
            return
        while len(message) > 1990:
            await ch.send(message[:1990])
            message = message[1990:]
        await ch.send(message)

    def _register_events(self):
        @self.bot.event
        async def on_ready():
            logger.info(f"Discord bot ready as {self.bot.user}")
            await self.send(
                f"🤖 **Bot online** | mode: `{TRADING_MODE.upper()}` | capital: `${TOTAL_CAPITAL:,.0f}`\nType `!help` to see all commands."
            )
        @self.bot.event
        async def on_command_error(ctx, error):
            logger.warning(f"Command error: {error}")

    def _register_commands(self):
        @self.bot.command(name="help")
        async def cmd_help(ctx):
            await ctx.send(
                "**Trading Bot Commands**\n```\n"
                "!status     — Bot mode, equity, open positions\n"
                "!positions  — All open trades with entry & stop\n"
                "!pnl        — Today's realised P&L and win rate\n"
                "!signals    — Last 10 signals and their outcome\n"
                "!markets    — Quick overview of all 5 markets\n"
                "!pause      — Pause automated trading\n"
                "!resume     — Resume trading\n"
                "!help       — This menu\n```"
            )

        @self.bot.command(name="status")
        async def cmd_status(ctx):
            equity = await self.broker.get_account_equity()
            positions = await self.db.get_open_positions()
            pnl = await self.db.get_daily_pnl()
            trades = await self.db.get_all_trades()
            wins = [t for t in trades if t["pnl"] > 0]
            win_rate = f"{round(len(wins)/len(trades)*100,1)}%" if trades else "—"
            status_str = "⏸ PAUSED" if self._paused else "▶ ACTIVE"
            sign = "+" if pnl >= 0 else ""
            await ctx.send(
                f"**Trading Bot Status**\nStatus: `{status_str}` | Mode: `{TRADING_MODE.upper()}`\n"
                f"Equity: `${equity or TOTAL_CAPITAL:,.2f}`\nOpen positions: `{len(positions)} / 5`\n"
                f"Today's P&L: `{sign}${pnl:,.2f}`\nAll-time win rate: `{win_rate}` ({len(trades)} trades)"
            )

        @self.bot.command(name="positions")
        async def cmd_positions(ctx):
            positions = await self.db.get_open_positions()
            if not positions:
                await ctx.send("📭 No open positions right now.")
                return
            lines = ["**Open Positions**"]
            for p in positions:
                emoji = MARKET_EMOJI.get(p["asset"], "📌")
                strategy = STRATEGY_MAP.get(p["asset"], "")
                since = p["entry_time"][:16].replace("T", " ")
                lines.append(
                    f"{emoji} **{p['asset']}** — {p['shares']} shares\n"
                    f"    Entry: `${p['entry_price']:.2f}` | Stop: `${p['stop_price']:.2f}`\n"
                    f"    Strategy: `{strategy}` | Since: `{since} UTC`"
                )
            await ctx.send("\n".join(lines))

        @self.bot.command(name="pnl")
        async def cmd_pnl(ctx):
            pnl = await self.db.get_daily_pnl()
            trades = await self.db.get_all_trades()
            today = datetime.now(timezone.utc).date().isoformat()
            today_trades = [t for t in trades if t["exit_time"].startswith(today)]
            wins = [t for t in today_trades if t["pnl"] > 0]
            losses = [t for t in today_trades if t["pnl"] < 0]
            sign = "+" if pnl >= 0 else ""
            emoji = "🟢" if pnl >= 0 else "🔴"
            lines = [f"{emoji} **Today's P&L: {sign}${pnl:,.2f}**"]
            if today_trades:
                lines.append(f"Trades: `{len(today_trades)}` | Wins: `{len(wins)}` | Losses: `{len(losses)}`")
                best = max(today_trades, key=lambda t: t["pnl"])
                worst = min(today_trades, key=lambda t: t["pnl"])
                lines.append(f"Best: `{best['asset']} +${best['pnl']:.2f}` | Worst: `{worst['asset']} ${worst['pnl']:.2f}`")
            else:
                lines.append("No trades closed today yet.")
            await ctx.send("\n".join(lines))

        @self.bot.command(name="signals")
        async def cmd_signals(ctx):
            signals = await self.db.get_recent_signals(10)
            if not signals:
                await ctx.send("📭 No signals received yet.")
                return
            lines = ["**Last 10 Signals**"]
            for s in signals:
                icon = "✅" if s["approved"] else "❌"
                ts = s["timestamp"][:16].replace("T", " ")
                emoji = MARKET_EMOJI.get(s["asset"], "📌")
                lines.append(f"{icon} {emoji} `{s['asset']}` {s['action'].upper()} @ `${s['price']:.2f}` — {s['reason']} _{ts}_")
            await ctx.send("\n".join(lines))

        @self.bot.command(name="markets")
        async def cmd_markets(ctx):
            await ctx.send(
                "**Market Overview**\n\n"
                "📈 **S&P 500 (SPY)** — Mean Reversion · 15m candles\n"
                "📊 **NASDAQ (QQQ)** — Mean Reversion · 15m candles\n"
                "₿ **Bitcoin (BTC)** — Momentum Breakout · 1h candles\n"
                "🏅 **Gold (GLD)** — Trend Following · 4h candles\n"
                "🛢 **Oil (USO)** — Trend Following · 4h candles\n\n"
                "_All trades: hard 1% stop · position size adjusted by daily ATR_"
            )

        @self.bot.command(name="pause")
        async def cmd_pause(ctx):
            self._paused = True
            await ctx.send("⏸ **Trading paused.** Use `!resume` to restart.")

        @self.bot.command(name="resume")
        async def cmd_resume(ctx):
            self._paused = False
            await ctx.send("▶ **Trading resumed.** Bot is active again.")

    async def notify_opened(self, asset, shares, entry, stop, risk):
        emoji = MARKET_EMOJI.get(asset, "📌")
        strategy = STRATEGY_MAP.get(asset, "")
        await self.send(f"{emoji} **OPENED {asset}** | {shares} shares @ `${entry:.2f}`\n    Stop: `${stop:.2f}` | Risk: `${risk:.2f}` | Strategy: `{strategy}`")

    async def notify_closed(self, asset, shares, exit_price, pnl):
        sign = "+" if pnl >= 0 else ""
        emoji = "🟢" if pnl >= 0 else "🔴"
        moji = MARKET_EMOJI.get(asset, "📌")
        await self.send(f"{emoji} **CLOSED {asset}** {moji} | {shares} shares @ `${exit_price:.2f}`\n    P&L: `{sign}${pnl:.2f}`")

    async def notify_rejected(self, asset, action, reason):
        await self.send(f"🚫 **{action.upper()} {asset} rejected** — {reason}")

    async def notify_morning_brief(self, equity, open_count):
        await self.send(
            f"☀️ **Morning Brief** — {datetime.now().strftime('%A %B %d')}\n"
            f"Equity: `${equity:,.2f}` | Open positions: `{open_count}`\n"
            f"Market opens in ~30 min. Bot active on 5 markets:\n"
            f"📈 SPY/QQQ (mean reversion · 15m)\n₿  BTC (momentum · 1h)\n🏅 GLD + 🛢 USO (trend following · 4h)\n"
            f"Risk per trade: `1%` hard stop · positions auto-sized by ATR"
        )

    async def notify_nightly_recap(self, pnl, closed_today):
        sign = "+" if pnl >= 0 else ""
        emoji = "🟢" if pnl >= 0 else "🔴"
        await self.send(
            f"🌙 **Nightly Recap**\n{emoji} Today's P&L: `{sign}${pnl:,.2f}`\n"
            f"Trades closed: `{closed_today}`\n_Market closed. Bot monitoring overnight for BTC breakouts._"
        )
