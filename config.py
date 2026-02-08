"""
Configuration constants and defaults for the cryptocurrency density scanner.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Check for .env file existence
env_path = Path('.env')
if not env_path.exists():
    print("⚠️ WARNING: .env file not found! Create it from .env.example")
    print("Required variables: BOT_TOKEN, OWNER_USER_ID, DEFAULT_CHAT_ID")

# Telegram Bot Configuration
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN or BOT_TOKEN == "your_bot_token_here":
    raise ValueError(
        "❌ BOT_TOKEN is not set or is placeholder value. "
        "Please set a valid token in .env file"
    )

DEFAULT_CHAT_ID = os.environ.get("DEFAULT_CHAT_ID", "-1001234567890")  # Placeholder - user should replace

# Owner User ID - required for bot authorization
OWNER_USER_ID_STR = os.environ.get("OWNER_USER_ID", "0")
try:
    OWNER_USER_ID = int(OWNER_USER_ID_STR)
    if OWNER_USER_ID == 0:
        raise ValueError("OWNER_USER_ID cannot be 0")
except ValueError as e:
    raise ValueError(
        f"❌ OWNER_USER_ID must be a valid Telegram user ID, got: {OWNER_USER_ID_STR}"
    ) from e

# Supported Exchanges (name -> ccxt_id and label)
SUPPORTED_EXCHANGES = {
    "kucoin_futures": {"ccxt_id": "kucoinfutures", "label": "KuCoin Futures"},
    "kucoin_spot": {"ccxt_id": "kucoin", "label": "KuCoin Spot"},
    "hyperliquid": {"ccxt_id": "hyperliquid", "label": "HL (Hyperliquid)"},
    "asterdex": {"ccxt_id": "asterdex", "label": "AsterDEX"},
    "lither": {"ccxt_id": "lither", "label": "Lither"},
    "bingx": {"ccxt_id": "bingx", "label": "BingX"},
}

# Default Exchange Settings
DEFAULT_EXCHANGE_SETTINGS = {
    "min_size": 1000000,  # Minimum cumulative volume in quote currency
    "ticker_overrides": {},  # Ticker-specific min_size for this exchange
    "blacklist": [],  # List of tickers to skip on this exchange
    "min_lifetime": 0,  # Minimum lifetime in seconds for density to trigger alert
}

# Test/demo token prefixes to skip (applies to ALL exchanges)
SKIP_PREFIXES = ("TEST", "XYZ")

# Test/demo/sandbox patterns to filter (case-insensitive)
SKIP_PATTERNS = ("DEMO", "SANDBOX", "MOCK")

# Default Global Settings
DEFAULT_SETTINGS = {
    "global_distance_pct": 3.0,  # Distance from spread in %
    "global_blacklist": ["BCH", "QQQ", "TSLA", "XAU", "HAG", "PAXG", "XAG", "USDC"],  # Global list of tickers to skip
    "global_ticker_overrides": {
        "BTC": 30000000,
        "ETH": 20000000,
        "SOL": 10000000,
        "XRP": 10000000,
        "HYPE": 5000000,
        "KPEPE": 1000000,
        "DOGE": 1000000,
        "BNB": 10000000,
        "SEI": 500000,
        "ZEC": 1000000,
        "LTC": 2000000,
        "AAVE": 1000000,
        "SUI": 10000000,
        "PUMP": 500000,
        "ASTER": 1000000,
        "DASH": 1000000,
        "LINK": 1000000,
        "PEPE": 1000000,
        "XLM": 1000000,
        "ADA": 1000000,
        "NEAR": 1000000,
    },
    "scan_interval": 30,  # Seconds between scans
    "orderbook_depth": 50,  # Number of order book levels to fetch
    "alerts_enabled": False,  # Alerts disabled by default
    "authorized_users": [],  # List of authorized Telegram user IDs (empty = allow all)
    "quote_currencies": ["USDT", "USD", "USDC", "BUSD"],  # Supported quote currencies
    "chat_id": DEFAULT_CHAT_ID,
    "exchanges": {
        "kucoin_futures": {"min_size": 300000, "ticker_overrides": {}, "blacklist": [], "min_lifetime": 0},
        "kucoin_spot": {"min_size": 500000, "ticker_overrides": {}, "blacklist": [], "min_lifetime": 0},
        "hyperliquid": {"min_size": 1000000, "ticker_overrides": {}, "blacklist": [], "min_lifetime": 0},
        "asterdex": {"min_size": 200000, "ticker_overrides": {}, "blacklist": [], "min_lifetime": 0},
        "lither": {"min_size": 200000, "ticker_overrides": {}, "blacklist": [], "min_lifetime": 0},
        "bingx": {"min_size": 500000, "ticker_overrides": {}, "blacklist": [], "min_lifetime": 0},
    },
}

# Alert Template (HTML formatted)
ALERT_TEMPLATE = """
🚨 <b>Density Alert</b> 🚨

<b>Exchange:</b> {exchange}
<b>Ticker:</b> {symbol}
<b>Side:</b> {side_emoji} {side_text}
<b>Volume:</b> ${volume:,.2f}
<b>Price Level:</b> ${price:.8f}
<b>Distance:</b> {distance:.2f}%
<b>Time:</b> {timestamp}
"""

# Rate Limiting and Retry Settings
RATE_LIMIT_SLEEP = 0.15  # Seconds to sleep between API calls
MAX_RETRIES = 3  # Maximum number of retries for failed requests
RETRY_DELAY = 5  # Seconds to wait before retrying

# Cooldown Settings
ALERT_COOLDOWN = 300  # Seconds (5 minutes) - prevent duplicate alerts

# Exchange API Settings
EXCHANGE_TIMEOUT = 30000  # 30 seconds in milliseconds

# Exchange-specific depth limits
EXCHANGE_DEPTH_LIMITS = {
    "kucoin_spot": 20,  # KuCoin accepts only 20 or 100
    "kucoin_futures": 20,  # KuCoin Futures accepts only 20 or 100
    "hyperliquid": 20,  # Public API max = 20 levels
}

# Exchange Trade URLs for clickable links
EXCHANGE_TRADE_URLS = {
    "hyperliquid": "https://app.hyperliquid.xyz/trade/{symbol}",
    "kucoin_futures": "https://www.kucoin.com/futures/trade/{symbol}USDT",
    "kucoin_spot": "https://www.kucoin.com/trade/{symbol}-USDT",
    "bingx": "https://bingx.com/en/futures/{symbol}USDT/",
    "asterdex": "https://app.asterdex.com/trade/{symbol}",
    "lither": "https://app.lither.com/trade/{symbol}",
}

# Exchange Market Type (PERP or SPOT)
EXCHANGE_MARKET_TYPE = {
    "hyperliquid": "PERP",
    "kucoin_futures": "FUTURES",
    "kucoin_spot": "SPOT",
    "bingx": "PERP",
    "asterdex": "PERP",
    "lither": "PERP",
}

# Anti-spam settings
ALERT_COOLDOWN_SECONDS = 300  # 5 minutes
ALERT_SIZE_CHANGE_THRESHOLD = 0.20  # 20% size change to ignore
ALERT_SIZE_SURGE_THRESHOLD = 0.50  # 50% size increase to resend
ALERT_PRICE_CHANGE_THRESHOLD = 0.005  # 0.5% price change
DENSITY_MISS_LIMIT = 3  # Number of scans to miss before cleanup

# Scanner stability settings
BATCH_SIZE = 50  # Number of symbols to process per batch (deprecated - use EXCHANGE_SCAN_CONFIG)
# Rate limit (seconds) to sleep between batches for each exchange
EXCHANGE_RATE_LIMITS = {
    "hyperliquid": 0.1,
    "kucoin_futures": 0.2,
    "kucoin_spot": 0.2,
    "bingx": 0.1,
    "asterdex": 0.1,
    "lither": 0.1,
}

# Exchange-specific scan configuration for rate limiting
EXCHANGE_SCAN_CONFIG = {
    "hyperliquid": {"batch_size": 10, "batch_delay": 0.1, "symbol_delay": 0.05},
    "kucoin_futures": {"batch_size": 3, "batch_delay": 0.5, "symbol_delay": 0.15},
    "kucoin_spot": {"batch_size": 3, "batch_delay": 0.5, "symbol_delay": 0.15},
    "bingx": {"batch_size": 10, "batch_delay": 0.1, "symbol_delay": 0.05},
}

DEFAULT_SCAN_CONFIG = {"batch_size": 5, "batch_delay": 0.2, "symbol_delay": 0.1}

# Parallel scanning configuration
EXCHANGE_CONCURRENCY = {
    "kucoin_futures": 8,   # KuCoin rate limit: ~30 req/s
    "kucoin_spot": 8,
    "hyperliquid": 20,     # Hyperliquid is fast
    "bingx": 20,           # BingX is fast
    "asterdex": 10,
    "lither": 10,
}

# Priority tickers — scanned first in each cycle
PRIORITY_TICKERS = [
    "BTC", "ETH", "SOL", "XRP", "DOGE", "PEPE", "WIF", 
    "HYPE", "SUI", "AAVE", "BNB", "LINK", "SEI", "PUMP"
]

# WebSocket configuration
# WS_ENABLED: Set to False to disable WebSocket and use REST only. When enabled,
#             exchanges that support WebSocket will use real-time streaming for faster alerts.
WS_ENABLED = True

# WS_RECONNECT_DELAY: Seconds to wait before attempting to reconnect after a WebSocket error.
#                     Adjust based on network conditions (increase for unstable networks).
WS_RECONNECT_DELAY = 5

# WS_MAX_RECONNECTS: Maximum reconnection attempts per symbol before giving up.
#                    After max reconnects, the symbol will stop being monitored via WebSocket.
#                    The scanner will continue running for other symbols.
WS_MAX_RECONNECTS = 10

# WS_MAX_SYMBOLS_PER_EXCHANGE: Maximum WebSocket subscriptions per exchange.
#                               Exchanges typically limit to ~50-100 concurrent WS connections.
#                               This prevents mass disconnections due to too many open connections.
WS_MAX_SYMBOLS_PER_EXCHANGE = 30
