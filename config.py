"""
config.py — Load and validate all environment variables.
"""
import os
from dotenv import load_dotenv

load_dotenv()

ALPACA_API_KEY: str = os.environ.get("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY: str = os.environ.get("ALPACA_SECRET_KEY", "")
DISCORD_BOT_TOKEN: str = os.environ.get("DISCORD_BOT_TOKEN", "")
DISCORD_CHANNEL_ID: int = int(os.environ.get("DISCORD_CHANNEL_ID", "0"))
WEBHOOK_SECRET: str = os.environ.get("WEBHOOK_SECRET", "")

TRADING_MODE: str = os.environ.get("TRADING_MODE", "paper").lower()
TOTAL_CAPITAL: float = float(os.environ.get("TOTAL_CAPITAL", "100000"))
DB_PATH: str = os.environ.get("DB_PATH", "bot_state.db")
RISK_PER_TRADE: float = float(os.environ.get("RISK_PER_TRADE", "0.01"))
ATR_MULTIPLIER: float = float(os.environ.get("ATR_MULTIPLIER", "1.5"))
MAX_POSITIONS: int = int(os.environ.get("MAX_POSITIONS", "5"))

CORRELATION_GROUPS: list = [
    {"SP500", "NASDAQ", "SPY", "QQQ", "NDX", "SPX", "ES", "NQ"},
    {"GOLD", "GLD", "GDX", "GDXJ"},
    {"OIL", "USO", "XOP", "CL"},
    {"BONDS", "TLT", "IEF", "AGG", "ZB"},
    {"BTC", "BITCOIN", "ETH", "CRYPTO"},
]

_PLACEHOLDER = "REPLACE_ME"


def validate_config() -> None:
    if TRADING_MODE not in ("paper", "live"):
        raise ValueError(f"TRADING_MODE must be 'paper' or 'live', got '{TRADING_MODE}'")
    if not WEBHOOK_SECRET or WEBHOOK_SECRET == _PLACEHOLDER:
        raise EnvironmentError("FATAL: WEBHOOK_SECRET is the placeholder.")
    if not DISCORD_BOT_TOKEN:
        raise EnvironmentError("DISCORD_BOT_TOKEN is not set in .env")
    if not DISCORD_CHANNEL_ID:
        raise EnvironmentError("DISCORD_CHANNEL_ID is not set in .env")
    if TRADING_MODE == "live":
        if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
            raise EnvironmentError("ALPACA keys required for live trading")
