"""
Density Scanner - Order book analysis engine for detecting high liquidity zones.
"""

import asyncio
import logging
import time
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Callable, Dict, Set, Tuple
import ccxt.async_support as ccxt_async

logger = logging.getLogger(__name__)

# Try to import ccxt.pro for WebSocket support
try:
    import ccxt.pro as ccxtpro
    CCXT_PRO_AVAILABLE = True
except ImportError:
    CCXT_PRO_AVAILABLE = False
    ccxtpro = None
    logger.info("ccxt.pro not available, WebSocket support disabled. Install with: pip install ccxt[pro]")

from config import (
    SUPPORTED_EXCHANGES,
    RATE_LIMIT_SLEEP,
    MAX_RETRIES,
    RETRY_DELAY,
    ALERT_TEMPLATE,
    ALERT_COOLDOWN,
    EXCHANGE_TIMEOUT,
    EXCHANGE_DEPTH_LIMITS,
    EXCHANGE_TRADE_URLS,
    EXCHANGE_MARKET_TYPE,
    ALERT_COOLDOWN_SECONDS,
    ALERT_SIZE_CHANGE_THRESHOLD,
    ALERT_SIZE_SURGE_THRESHOLD,
    ALERT_PRICE_CHANGE_THRESHOLD,
    DENSITY_MISS_LIMIT,
    BATCH_SIZE,
    EXCHANGE_RATE_LIMITS,
    EXCHANGE_SCAN_CONFIG,
    DEFAULT_SCAN_CONFIG,
    SKIP_PREFIXES,
    SKIP_PATTERNS,
    EXCHANGE_CONCURRENCY,
    PRIORITY_TICKERS,
    WS_ENABLED,
    WS_RECONNECT_DELAY,
    WS_MAX_RECONNECTS,
    WS_MAX_SYMBOLS_PER_EXCHANGE,
)
from settings_manager import SettingsManager

logger = logging.getLogger(__name__)


# ===========================
# Helper Functions
# ===========================

def format_size(size: float) -> str:
    """
    Format size with K/M/B suffixes.
    Examples: $356.65K, $1.23M, $1.05B
    """
    if size >= 1_000_000_000:  # >= 1B
        return f"${size / 1_000_000_000:.2f}B"
    elif size >= 1_000_000:  # >= 1M
        return f"${size / 1_000_000:.2f}M"
    else:  # < 1M
        return f"${size / 1_000:.2f}K"


def format_lifetime(seconds: int) -> str:
    """
    Format lifetime as human-readable string.
    Examples: 45s, 2m 30s, 1h 5m
    """
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:  # < 1 hour
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}m {secs}s"
    else:  # >= 1 hour
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"


def get_trade_url(exchange: str, symbol: str) -> str:
    """
    Get trade URL for exchange and symbol.
    Returns the formatted URL or empty string if not available.
    """
    # Extract base symbol (remove /USDT, /USD, etc.)
    base_symbol = symbol.split('/')[0] if '/' in symbol else symbol
    
    url_template = EXCHANGE_TRADE_URLS.get(exchange, "")
    if url_template:
        return url_template.format(symbol=base_symbol)
    return ""


def get_size_emoji(size: float) -> str:
    """
    Get emoji based on alert size.
    < $500K → 📊
    $500K - $1M → 🔥
    $1M - $5M → 🔥🔥
    $5M - $10M → 💎
    > $10M → 💎💎💎
    """
    if size < 500_000:
        return "📊"
    elif size < 1_000_000:
        return "🔥"
    elif size < 5_000_000:
        return "🔥🔥"
    elif size < 10_000_000:
        return "💎"
    else:
        return "💎💎💎"


@dataclass
class DensityAlert:
    """Represents a density alert detected in the order book."""
    exchange: str
    symbol: str
    side: str  # "bid" or "ask"
    volume: float
    price: float
    distance_pct: float
    timestamp: str
    lifetime_seconds: int = 0  # How long the density has existed
    
    def format_message(self) -> str:
        """Format the alert as an HTML message with new beautiful format."""
        # Get exchange label (for display)
        exchange_label = SUPPORTED_EXCHANGES.get(self.exchange, {}).get("label", self.exchange.upper())
        
        # Get size emoji
        size_emoji = get_size_emoji(self.volume)
        
        # Format size
        size_formatted = format_size(self.volume)
        
        # Side emoji and text
        if self.side == "bid":
            side_emoji = "🟩"
            side_text = "BID (buy wall)"
        else:
            side_emoji = "🟥"
            side_text = "ASK (sell wall)"
        
        # Market type (PERP or SPOT)
        market_type = EXCHANGE_MARKET_TYPE.get(self.exchange, "PERP")
        
        # Get trade URL for clickable ticker
        trade_url = get_trade_url(self.exchange, self.symbol)
        
        # Extract base symbol for display
        base_symbol = self.symbol.split('/')[0] if '/' in self.symbol else self.symbol
        
        # Create clickable ticker link
        if trade_url:
            ticker_link = f'<a href="{trade_url}">{base_symbol}</a>'
        else:
            ticker_link = base_symbol
        
        # Format lifetime
        lifetime_str = format_lifetime(self.lifetime_seconds)
        
        # Build message
        message = f"{size_emoji} <b>{exchange_label}</b> | <b>{size_formatted}</b> | {self.side.upper()}\n"
        message += f"Рынок: {market_type}\n"
        message += f"Тикер: {ticker_link}\n"
        message += f"Сторона: {side_emoji} {side_text}\n"
        message += f"Цена: {self.price:.8f}\n"
        message += f"Размер: ${self.volume:,.0f}\n"
        message += f"Дистанция: {self.distance_pct:.2f}%\n"
        message += f"⏱️ Время жизни: {lifetime_str}"
        
        return message


@dataclass
class ExchangeState:
    """State tracking for an exchange."""
    name: str
    ccxt_id: str
    label: str
    client: Optional[object] = None
    ws_client: Optional[object] = None  # WebSocket client for real-time updates
    markets_loaded: bool = False
    symbols: list = None
    last_error: Optional[str] = None
    consecutive_errors: int = 0
    ws_enabled: bool = False  # Whether WebSocket is enabled for this exchange
    
    def __post_init__(self):
        if self.symbols is None:
            self.symbols = []


class DensityScanner:
    """
    Main scanner that detects order book densities across multiple exchanges.
    Runs asynchronously and triggers alerts via callback.
    """
    
    def __init__(self, settings: SettingsManager, alert_callback: Callable[[DensityAlert], None]):
        self.settings = settings
        self.alert_callback = alert_callback
        self._running = False
        self._exchanges: Dict[str, ExchangeState] = {}
        
        # Alert cooldown tracking: (exchange, symbol, side) -> (last_alert_time, last_size, last_price)
        self._alert_cooldowns: Dict[Tuple[str, str, str], Tuple[float, float, float]] = {}
        
        # Density lifetime tracking: (exchange, symbol, side, price_level) -> first_seen_timestamp
        self._density_tracker: Dict[Tuple[str, str, str, float], float] = {}
        
        # Miss counter for cleanup: (exchange, symbol, side, price_level) -> miss_count
        self._miss_counter: Dict[Tuple[str, str, str, float], int] = {}
        
        # Contract size cache: "exchange:symbol" -> contract_size
        self._contract_size_cache: Dict[str, float] = {}
        
        logger.info("DensityScanner initialized")
    
    async def _initialize_exchanges(self):
        """Initialize exchange clients."""
        logger.info("Initializing exchanges...")
        
        for name, config in SUPPORTED_EXCHANGES.items():
            ccxt_id = config["ccxt_id"]
            label = config["label"]
            
            # Check if exchange exists in CCXT
            if not hasattr(ccxt_async, ccxt_id):
                logger.warning(f"Exchange {label} ({ccxt_id}) not available in CCXT, skipping")
                continue
            
            try:
                # Create exchange client
                exchange_class = getattr(ccxt_async, ccxt_id)
                client = exchange_class({
                    'enableRateLimit': True,
                    'timeout': EXCHANGE_TIMEOUT,
                })
                
                # Try to initialize WebSocket client if available
                ws_client = None
                ws_enabled = False
                if CCXT_PRO_AVAILABLE and WS_ENABLED and hasattr(ccxtpro, ccxt_id):
                    try:
                        ws_exchange_class = getattr(ccxtpro, ccxt_id)
                        ws_client = ws_exchange_class({
                            'enableRateLimit': True,
                            'timeout': EXCHANGE_TIMEOUT,
                        })
                        ws_enabled = True
                        logger.info(f"WebSocket enabled for {label}")
                    except Exception as e:
                        logger.warning(f"WebSocket not available for {label}: {e}")
                
                self._exchanges[name] = ExchangeState(
                    name=name,
                    ccxt_id=ccxt_id,
                    label=label,
                    client=client,
                    ws_client=ws_client,
                    ws_enabled=ws_enabled
                )
                logger.info(f"Initialized {label}")
            except Exception as e:
                logger.error(f"Failed to initialize {label}: {e}")
    
    def _sort_symbols_by_priority(self, symbols: list) -> list:
        """
        Sort symbols by priority - priority tickers first, then normal tickers.
        Priority tickers are those in PRIORITY_TICKERS list.
        """
        priority = []
        normal = []
        
        for symbol in symbols:
            # Extract base symbol from different formats: BTC/USDT, BTC/USDT:USDT, BTC-USD
            if '/' in symbol:
                base = symbol.split('/')[0]
            elif '-' in symbol:
                base = symbol.split('-')[0]
            else:
                base = symbol
            
            # Check if base is in priority list (case-insensitive)
            if base.upper() in PRIORITY_TICKERS:
                priority.append(symbol)
            else:
                normal.append(symbol)
        
        return priority + normal
    
    async def _load_markets(self, exchange_state: ExchangeState):
        """Load and filter markets for an exchange."""
        if exchange_state.markets_loaded:
            return
        
        try:
            logger.info(f"Loading markets for {exchange_state.label}...")
            
            # Load markets with timeout handling
            try:
                markets = await exchange_state.client.load_markets()
            except asyncio.TimeoutError:
                logger.error(f"Timeout loading markets for {exchange_state.label}")
                raise
            except Exception as e:
                logger.error(f"Failed to load markets for {exchange_state.label}: {e}")
                raise
            
            # Filter symbols to those ending with quote currencies
            quote_currencies = self.settings.quote_currencies
            filtered_symbols = []
            
            for symbol, market_info in markets.items():
                # For futures/swap contracts (e.g., BTC/USDT:USDT)
                if ':' in symbol:
                    # Check if it's a linear contract with supported quote currency
                    for quote in quote_currencies:
                        if symbol.endswith(f':{quote}'):
                            # Also verify it's linear and quote matches
                            if (market_info.get('linear', False) and 
                                market_info.get('quote') == quote):
                                filtered_symbols.append(symbol)
                                break
                # For Hyperliquid-style pairs (e.g., BTC-USD, XYZ-EUR)
                elif '-' in symbol:
                    # Extract the part after the last '-' as quote currency
                    parts = symbol.split('-')
                    if len(parts) >= 2:
                        quote = parts[-1]
                        if quote in quote_currencies:
                            filtered_symbols.append(symbol)
                # For spot markets (e.g., BTC/USDT)
                elif '/' in symbol:
                    for quote in quote_currencies:
                        if symbol.endswith(f"/{quote}"):
                            filtered_symbols.append(symbol)
                            break
            
            exchange_state.symbols = filtered_symbols
            exchange_state.markets_loaded = True
            exchange_state.consecutive_errors = 0
            
            # Sort symbols by priority (priority tickers first)
            exchange_state.symbols = self._sort_symbols_by_priority(exchange_state.symbols)
            
            # Clear contract size cache for this exchange after successful market load
            keys_to_clear = [k for k in self._contract_size_cache if k.startswith(f"{exchange_state.name}:")]
            for k in keys_to_clear:
                del self._contract_size_cache[k]
            
            logger.info(f"Loaded {len(filtered_symbols)} symbols for {exchange_state.label}")
        except Exception as e:
            exchange_state.last_error = str(e)
            exchange_state.consecutive_errors += 1
            logger.error(f"Failed to load markets for {exchange_state.label}: {e}")
            # Set empty symbols list on error to prevent crashes
            exchange_state.symbols = []
    
    def _compute_densities(self, exchange: str, symbol: str, orderbook: dict, 
                          min_size: float, distance_pct: float, contract_size: float = 1.0) -> list:
        """
        Compute densities from order book.
        Returns list of DensityAlert objects.
        """
        alerts = []
        
        if not orderbook or 'bids' not in orderbook or 'asks' not in orderbook:
            return alerts
        
        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])
        
        if not bids or not asks:
            return alerts
        
        # Calculate mid price
        best_bid = bids[0][0] if bids else 0
        best_ask = asks[0][0] if asks else 0
        
        if best_bid == 0 or best_ask == 0:
            return alerts
        
        mid_price = (best_bid + best_ask) / 2
        
        # Calculate distance threshold
        max_distance = mid_price * (distance_pct / 100)
        
        # Check bids (below mid price)
        bid_volume = 0
        bid_price_sum = 0
        bid_count = 0
        
        for entry in bids:
            price, amount = float(entry[0]), float(entry[1])
            distance = mid_price - price
            if distance > max_distance:
                break
            
            quote_volume = price * amount * contract_size
            bid_volume += quote_volume
            bid_price_sum += price * quote_volume
            bid_count += 1
            
            if bid_volume >= min_size:
                # Calculate volume-weighted average price
                avg_price = bid_price_sum / bid_volume if bid_volume > 0 else price
                distance_from_mid = ((mid_price - avg_price) / mid_price) * 100
                
                alerts.append(DensityAlert(
                    exchange=exchange,
                    symbol=symbol,
                    side="bid",
                    volume=bid_volume,
                    price=avg_price,
                    distance_pct=distance_from_mid,
                    timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ))
                break
        
        # Check asks (above mid price)
        ask_volume = 0
        ask_price_sum = 0
        ask_count = 0
        
        for entry in asks:
            price, amount = float(entry[0]), float(entry[1])
            distance = price - mid_price
            if distance > max_distance:
                break
            
            quote_volume = price * amount * contract_size
            ask_volume += quote_volume
            ask_price_sum += price * quote_volume
            ask_count += 1
            
            if ask_volume >= min_size:
                # Calculate volume-weighted average price
                avg_price = ask_price_sum / ask_volume if ask_volume > 0 else price
                distance_from_mid = ((avg_price - mid_price) / mid_price) * 100
                
                alerts.append(DensityAlert(
                    exchange=exchange,
                    symbol=symbol,
                    side="ask",
                    volume=ask_volume,
                    price=avg_price,
                    distance_pct=distance_from_mid,
                    timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ))
                break
        
        return alerts
    
    def _check_cooldown(self, exchange: str, symbol: str, side: str) -> bool:
        """Check if alert is on cooldown. Returns True if on cooldown."""
        key = (exchange, symbol, side)
        current_time = time.time()
        
        if key in self._alert_cooldowns:
            last_alert_time = self._alert_cooldowns[key][0]
            if current_time - last_alert_time < ALERT_COOLDOWN:
                return True
        
        return False
    
    def _set_cooldown(self, exchange: str, symbol: str, side: str, size: float, price: float):
        """Set cooldown for an alert with size and price tracking."""
        key = (exchange, symbol, side)
        self._alert_cooldowns[key] = (time.time(), size, price)
    
    def _should_send_alert(self, exchange: str, symbol: str, side: str, size: float, price: float) -> Tuple[bool, str]:
        """
        Check if alert should be sent based on anti-spam rules.
        Returns (should_send, reason).
        
        Rules:
        - Send if no previous alert exists
        - Don't send if within cooldown AND size/price haven't changed significantly
        - Send if size increased by 50%+ (surge)
        - Send if price changed by 0.5%+
        - Send if cooldown expired (5 minutes)
        """
        key = (exchange, symbol, side)
        current_time = time.time()
        
        # No previous alert - send it
        if key not in self._alert_cooldowns:
            return (True, "first_alert")
        
        last_alert_time, last_size, last_price = self._alert_cooldowns[key]
        time_since_last = current_time - last_alert_time
        
        # Calculate changes
        size_change_pct = abs(size - last_size) / last_size if last_size > 0 else 1.0
        price_change_pct = abs(price - last_price) / last_price if last_price > 0 else 1.0
        size_increase_pct = (size - last_size) / last_size if last_size > 0 else 0.0
        
        # Check if size surged (50%+ increase)
        if size_increase_pct >= ALERT_SIZE_SURGE_THRESHOLD:
            return (True, "size_surge")
        
        # Check if price changed significantly (0.5%+)
        if price_change_pct >= ALERT_PRICE_CHANGE_THRESHOLD:
            return (True, "price_change")
        
        # Check if cooldown expired
        if time_since_last >= ALERT_COOLDOWN_SECONDS:
            return (True, "cooldown_expired")
        
        # Within cooldown and no significant changes
        if size_change_pct < ALERT_SIZE_CHANGE_THRESHOLD:
            return (False, "cooldown_active")
        
        # Size changed but not enough to override cooldown
        return (False, "cooldown_active")
    
    def _get_density_lifetime(self, exchange: str, symbol: str, side: str, price: float) -> int:
        """
        Get lifetime of a density in seconds.
        Densities are matched by exchange, symbol, side, and price within 0.1%.
        """
        current_time = time.time()
        
        # Find matching density (price within 0.1%)
        for key, first_seen in self._density_tracker.items():
            tracked_exchange, tracked_symbol, tracked_side, tracked_price = key
            
            if (tracked_exchange == exchange and 
                tracked_symbol == symbol and 
                tracked_side == side):
                # Check if price is within 0.1%
                price_diff_pct = abs(price - tracked_price) / tracked_price if tracked_price > 0 else 1.0
                if price_diff_pct <= 0.001:  # 0.1%
                    return int(current_time - first_seen)
        
        # New density - track it
        key = (exchange, symbol, side, price)
        self._density_tracker[key] = current_time
        self._miss_counter[key] = 0
        
        return 0
    
    def _mark_density_seen(self, exchange: str, symbol: str, side: str, price: float):
        """Mark a density as seen (reset miss counter)."""
        # Find matching density
        for key in list(self._miss_counter.keys()):
            tracked_exchange, tracked_symbol, tracked_side, tracked_price = key
            
            if (tracked_exchange == exchange and 
                tracked_symbol == symbol and 
                tracked_side == side):
                # Check if price is within 0.1%
                price_diff_pct = abs(price - tracked_price) / tracked_price if tracked_price > 0 else 1.0
                if price_diff_pct <= 0.001:  # 0.1%
                    self._miss_counter[key] = 0
                    return
    
    def _cleanup_missing_densities(self):
        """Clean up densities that haven't been seen for DENSITY_MISS_LIMIT scans."""
        keys_to_remove = []
        
        for key, miss_count in self._miss_counter.items():
            if miss_count >= DENSITY_MISS_LIMIT:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            if key in self._density_tracker:
                del self._density_tracker[key]
            if key in self._miss_counter:
                del self._miss_counter[key]
            
            # Also clean up cooldown for this density
            exchange, symbol, side, _ = key
            cooldown_key = (exchange, symbol, side)
            if cooldown_key in self._alert_cooldowns:
                del self._alert_cooldowns[cooldown_key]
        
        if keys_to_remove:
            logger.debug(f"Cleaned up {len(keys_to_remove)} missing densities")
    
    async def _scan_symbol(self, exchange_state: ExchangeState, symbol: str):
        """Scan a single symbol on an exchange. Returns True if successful."""
        if not self._running:
            return False
        
        exchange_name = exchange_state.name
        
        try:
            # Extract base symbol for blacklist check
            # Handle different symbol formats: BTC/USDT, BTC/USDT:USDT, BTC-USD
            if '/' in symbol:
                base_symbol = symbol.split('/')[0]
            elif ':' in symbol:
                base_symbol = symbol.split(':')[0].split('/')[0]
            elif '-' in symbol:
                base_symbol = symbol.split('-')[0]
            else:
                base_symbol = symbol
            
            # Check blacklist (both global and exchange-specific)
            if self.settings.is_blacklisted(exchange_name, base_symbol):
                return True  # Not an error, just skipped
            
            # Filter out test/demo tokens
            base_symbol_upper = base_symbol.upper()
            if base_symbol_upper.startswith(SKIP_PREFIXES):
                logger.debug(f"Skipping test/demo token: {symbol} on {exchange_state.label}")
                return True  # Skip test/demo contracts
            
            # Filter out demo/sandbox/mock patterns
            for pattern in SKIP_PATTERNS:
                if pattern in base_symbol_upper:
                    logger.debug(f"Skipping test/demo token: {symbol} on {exchange_state.label}")
                    return True
            
            # Validate quote currency - final safety check for USD-denominated pairs
            symbol_upper = symbol.upper()
            valid_quotes = self.settings.quote_currencies
            is_valid_quote = any(
                symbol_upper.endswith(f'/{q}') or 
                symbol_upper.endswith(f':{q}') or 
                symbol_upper.endswith(f'-{q}')
                for q in valid_quotes
            )
            if not is_valid_quote:
                logger.debug(f"Skipping non-USD pair: {symbol} on {exchange_state.label}")
                return True  # Skip non-USD pairs
            
            # Resolve settings for this symbol
            min_size = self.settings.resolve_min_size(exchange_name, base_symbol)
            distance_pct = self.settings.global_distance
            depth = self.settings.orderbook_depth
            
            # Use exchange-specific depth limit if available
            if exchange_name in EXCHANGE_DEPTH_LIMITS:
                depth = EXCHANGE_DEPTH_LIMITS[exchange_name]
            
            # Fetch order book with retries
            orderbook = None
            for attempt in range(MAX_RETRIES):
                try:
                    orderbook = await exchange_state.client.fetch_order_book(symbol, limit=depth)
                    break
                except ccxt_async.RateLimitExceeded as e:
                    logger.debug(f"Rate limited on {exchange_name}/{symbol}, waiting 5s")
                    await asyncio.sleep(5)
                    break
                except (ccxt_async.NetworkError, ccxt_async.ExchangeNotAvailable) as e:
                    if attempt < MAX_RETRIES - 1:
                        logger.warning(f"Network error on {exchange_state.label} for {symbol}, retrying...")
                        await asyncio.sleep(RETRY_DELAY)
                    else:
                        logger.error(f"Failed to fetch orderbook for {symbol} on {exchange_state.label}: {e}")
                        break
                except ccxt_async.ExchangeError as e:
                    # Handle 429 errors
                    if '429' in str(e):
                        logger.debug(f"Rate limited on {exchange_name}/{symbol}, waiting 5s")
                        await asyncio.sleep(5)
                        break
                    # For BingX, "symbol not found" errors are expected and should be logged as DEBUG
                    error_msg = str(e).lower()
                    if exchange_name == "bingx" and ("symbol" in error_msg and "not found" in error_msg):
                        logger.debug(f"Symbol {symbol} not found on {exchange_state.label}")
                        break
                    else:
                        logger.debug(f"Exchange error {exchange_name}/{symbol}: {e}")
                        break
                except ccxt_async.BaseError as e:
                    logger.debug(f"Exchange error for {symbol} on {exchange_state.label}: {e}")
                    break
            
            if orderbook:
                # Get contract size for futures/swap markets
                cache_key = f"{exchange_name}:{symbol}"
                if cache_key in self._contract_size_cache:
                    contract_size = self._contract_size_cache[cache_key]
                else:
                    contract_size = 1.0
                    try:
                        market_info = exchange_state.client.market(symbol)
                        if market_info:
                            # Check if this is a contract (futures/swap) market
                            is_contract = market_info.get('contract', False)
                            
                            if is_contract:
                                # Primary: CCXT unified contractSize
                                cs = market_info.get('contractSize')
                                
                                # Fallback: exchange-specific fields in info dict
                                if cs is None:
                                    info = market_info.get('info', {})
                                    cs = info.get('multiplier') or info.get('contractSize') or info.get('lotSize')
                                
                                if cs is not None:
                                    contract_size = float(cs)
                                    if contract_size <= 0:
                                        logger.warning(f"Invalid contract size {cs} for {symbol} on {exchange_state.label}, defaulting to 1.0")
                                        contract_size = 1.0
                                    else:
                                        logger.debug(f"Contract size for {symbol} on {exchange_state.label}: {contract_size}")
                                else:
                                    logger.warning(f"No contract size found for futures symbol {symbol} on {exchange_state.label}, defaulting to 1.0")
                            # else: spot market, contract_size stays 1.0
                    except Exception as e:
                        logger.warning(f"Could not fetch contract size for {exchange_name}/{symbol}: {e}, defaulting to 1.0")
                        contract_size = 1.0
                    
                    # Log non-trivial contract sizes (only on first fetch, before caching)
                    if contract_size != 1.0:
                        logger.info(f"Using contract size {contract_size} for {symbol} on {exchange_state.label}")
                    
                    # Cache the contract size
                    self._contract_size_cache[cache_key] = contract_size
                
                # Compute densities (using exchange_name key for URL/type lookups, not display label)
                densities = self._compute_densities(
                    exchange_name,
                    symbol,
                    orderbook,
                    min_size,
                    distance_pct,
                    contract_size
                )
                
                # Fire alerts if enabled
                if self.settings.alerts_enabled:
                    for alert in densities:
                        # Get lifetime for this density
                        lifetime = self._get_density_lifetime(
                            exchange_name,
                            symbol,
                            alert.side,
                            alert.price
                        )
                        alert.lifetime_seconds = lifetime
                        
                        # Mark density as seen
                        self._mark_density_seen(exchange_name, symbol, alert.side, alert.price)
                        
                        # Check if we should send alert (anti-spam)
                        should_send, reason = self._should_send_alert(
                            exchange_name,
                            symbol,
                            alert.side,
                            alert.volume,
                            alert.price
                        )
                        
                        if should_send:
                            # Check min_lifetime filter
                            min_lifetime = self.settings.get_exchange_min_lifetime(exchange_name)
                            if alert.lifetime_seconds < min_lifetime:
                                logger.debug(f"Skipped alert (lifetime too short): {exchange_state.label} {symbol} {alert.side} ${alert.volume:,.0f} (lifetime: {alert.lifetime_seconds}s < {min_lifetime}s)")
                                continue
                            
                            self.alert_callback(alert)
                            self._set_cooldown(exchange_name, symbol, alert.side, alert.volume, alert.price)
                            logger.info(f"Alert ({reason}): {exchange_state.label} {symbol} {alert.side} ${alert.volume:,.0f} (lifetime: {alert.lifetime_seconds}s)")
                        else:
                            logger.debug(f"Skipped alert ({reason}): {exchange_state.label} {symbol} {alert.side} ${alert.volume:,.0f}")
                
                return True
            
            return False
            
        except Exception as e:
            # Catch-all for any 429 errors
            if '429' in str(e) or 'rate limit' in str(e).lower():
                logger.debug(f"Rate limited on {exchange_name}/{symbol}, waiting 5s")
                await asyncio.sleep(5)
            else:
                logger.debug(f"Unexpected error scanning {symbol} on {exchange_state.label}: {e}")
            return False
    
    async def _scan_exchange(self, exchange_state: ExchangeState):
        """Scan a single exchange with parallel symbol processing using semaphore."""
        if not exchange_state.markets_loaded:
            await self._load_markets(exchange_state)
        
        if not exchange_state.symbols:
            return
        
        exchange_name = exchange_state.name
        symbols = exchange_state.symbols
        total_symbols = len(symbols)
        
        # Get exchange-specific concurrency limit
        max_concurrent = EXCHANGE_CONCURRENCY.get(exchange_name, 10)
        semaphore = asyncio.Semaphore(max_concurrent)
        
        logger.debug(f"Starting parallel scan of {total_symbols} symbols on {exchange_state.label} (concurrency: {max_concurrent})")
        
        # Track results
        success_count = 0
        error_count = 0
        
        async def scan_with_limit(symbol):
            """Scan symbol with semaphore rate limiting."""
            nonlocal success_count, error_count
            
            async with semaphore:
                if not self._running:
                    return
                
                try:
                    result = await self._scan_symbol(exchange_state, symbol)
                    if result:
                        success_count += 1
                    else:
                        error_count += 1
                except Exception as e:
                    if '429' in str(e) or 'rate limit' in str(e).lower():
                        # Add jitter to avoid thundering herd when many tasks hit rate limit
                        jitter = random.uniform(0, 1)
                        logger.debug(f"Rate limited on {exchange_name}, pausing {2 + jitter:.1f}s...")
                        await asyncio.sleep(2 + jitter)
                    else:
                        logger.debug(f"Error scanning {symbol} on {exchange_name}: {e}")
                    error_count += 1
        
        # Create tasks for all symbols
        tasks = [scan_with_limit(symbol) for symbol in symbols]
        
        # Execute all tasks concurrently (limited by semaphore)
        # Note: Semaphore prevents all tasks from running at once, controlling concurrency
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Update error counter based on scan results
        if error_count > 0:
            exchange_state.consecutive_errors += 1
        else:
            exchange_state.consecutive_errors = 0
        
        logger.info(f"Scan complete for {exchange_name}: {success_count} successful, {error_count} errors from {total_symbols} symbols")
    
    async def _ws_scan_symbol(self, exchange_state: ExchangeState, symbol: str):
        """
        WebSocket-based scanning for a single symbol — receives orderbook updates in real-time.
        This is a long-running task that continuously watches the orderbook.
        """
        exchange_name = exchange_state.name
        reconnect_count = 0
        
        while self._running and reconnect_count < WS_MAX_RECONNECTS:
            try:
                # Extract base symbol for blacklist check
                if '/' in symbol:
                    base_symbol = symbol.split('/')[0]
                elif ':' in symbol:
                    base_symbol = symbol.split(':')[0].split('/')[0]
                elif '-' in symbol:
                    base_symbol = symbol.split('-')[0]
                else:
                    base_symbol = symbol
                
                # Check blacklist
                if self.settings.is_blacklisted(exchange_name, base_symbol):
                    return  # Exit this task
                
                # Filter out test/demo tokens
                base_symbol_upper = base_symbol.upper()
                if base_symbol_upper.startswith(SKIP_PREFIXES):
                    return
                
                for pattern in SKIP_PATTERNS:
                    if pattern in base_symbol_upper:
                        return
                
                # Watch orderbook updates
                while self._running:
                    try:
                        orderbook = await exchange_state.ws_client.watch_order_book(symbol)
                        
                        # Get contract size from cache
                        cache_key = f"{exchange_name}:{symbol}"
                        contract_size = self._contract_size_cache.get(cache_key, 1.0)
                        
                        # Resolve settings
                        min_size = self.settings.resolve_min_size(exchange_name, base_symbol)
                        distance_pct = self.settings.global_distance
                        
                        # Compute densities
                        densities = self._compute_densities(
                            exchange_name,
                            symbol,
                            orderbook,
                            min_size,
                            distance_pct,
                            contract_size
                        )
                        
                        # Process alerts
                        if self.settings.alerts_enabled:
                            for alert in densities:
                                lifetime = self._get_density_lifetime(
                                    exchange_name, symbol, alert.side, alert.price
                                )
                                alert.lifetime_seconds = lifetime
                                
                                self._mark_density_seen(exchange_name, symbol, alert.side, alert.price)
                                
                                should_send, reason = self._should_send_alert(
                                    exchange_name, symbol, alert.side, alert.volume, alert.price
                                )
                                
                                if should_send:
                                    min_lifetime = self.settings.get_exchange_min_lifetime(exchange_name)
                                    if alert.lifetime_seconds >= min_lifetime:
                                        self.alert_callback(alert)
                                        self._set_cooldown(exchange_name, symbol, alert.side, alert.volume, alert.price)
                                        logger.info(f"WS Alert ({reason}): {exchange_state.label} {symbol} {alert.side} ${alert.volume:,.0f}")
                        
                        reconnect_count = 0  # Reset on success
                        
                    except Exception as e:
                        if '429' in str(e) or 'rate limit' in str(e).lower():
                            await asyncio.sleep(2)
                        else:
                            raise  # Re-raise to outer exception handler
                            
            except Exception as e:
                reconnect_count += 1
                
                # Reduce log spam: DEBUG for first 2 attempts, WARNING for 3+
                if reconnect_count <= 2:
                    logger.debug(f"WS reconnecting {exchange_state.label}/{symbol} (attempt {reconnect_count}/{WS_MAX_RECONNECTS}): {e}")
                else:
                    logger.warning(f"WS error {exchange_state.label}/{symbol} (reconnect {reconnect_count}/{WS_MAX_RECONNECTS}): {e}")
                
                if reconnect_count < WS_MAX_RECONNECTS:
                    await asyncio.sleep(WS_RECONNECT_DELAY)
                else:
                    logger.error(f"WS max reconnects reached for {exchange_state.label}/{symbol}, giving up")
                    return
    
    async def _ws_scan_exchange(self, exchange_state: ExchangeState):
        """
        WebSocket-based scanning for an entire exchange.
        Creates a task for each PRIORITY symbol to watch orderbook updates in real-time.
        All other symbols are scanned via REST in parallel.
        """
        if not exchange_state.markets_loaded:
            await self._load_markets(exchange_state)
        
        if not exchange_state.symbols:
            return
        
        # Filter to only priority symbols for WebSocket
        ws_symbols = []
        for symbol in exchange_state.symbols:
            # Extract base symbol
            if '/' in symbol:
                base = symbol.split('/')[0]
            elif ':' in symbol:
                base = symbol.split(':')[0].split('/')[0]
            elif '-' in symbol:
                base = symbol.split('-')[0]
            else:
                base = symbol
            
            # Check if base is in priority tickers
            if base.upper() in PRIORITY_TICKERS:
                ws_symbols.append(symbol)
        
        # Apply safety limit to prevent too many WebSocket connections
        if len(ws_symbols) > WS_MAX_SYMBOLS_PER_EXCHANGE:
            logger.warning(
                f"WebSocket symbols ({len(ws_symbols)}) exceed limit ({WS_MAX_SYMBOLS_PER_EXCHANGE}) "
                f"for {exchange_state.label}, truncating to first {WS_MAX_SYMBOLS_PER_EXCHANGE}"
            )
            ws_symbols = ws_symbols[:WS_MAX_SYMBOLS_PER_EXCHANGE]
        
        if not ws_symbols:
            logger.info(f"No priority symbols for WebSocket on {exchange_state.label}, using REST only")
            return
        
        logger.info(
            f"Starting WebSocket scan for {exchange_state.label}: "
            f"{len(ws_symbols)} priority symbols (out of {len(exchange_state.symbols)} total)"
        )
        
        # Create a task for each priority symbol
        tasks = [self._ws_scan_symbol(exchange_state, symbol) for symbol in ws_symbols]
        
        # Run all symbol watchers concurrently
        # Note: These are long-running tasks that only complete on error or shutdown
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log any exceptions that occurred
        for symbol, result in zip(ws_symbols, results):
            if isinstance(result, Exception):
                logger.error(f"WS task for {exchange_state.label}/{symbol} completed with error: {result}")
    
    async def _scan_all_exchanges(self):
        """Scan all exchanges concurrently with proper error handling."""
        # Increment miss counters before scan (will be reset for seen densities)
        for key in list(self._miss_counter.keys()):
            self._miss_counter[key] = self._miss_counter.get(key, 0) + 1
        
        # Build list of exchange states and tasks
        exchange_states = []
        tasks = []
        for exchange_state in self._exchanges.values():
            # Reset markets if too many consecutive errors
            if exchange_state.consecutive_errors > 10:
                logger.warning(f"Resetting markets for {exchange_state.label} due to consecutive errors")
                exchange_state.markets_loaded = False
                exchange_state.consecutive_errors = 0
            
            exchange_states.append(exchange_state)
            tasks.append(self._scan_exchange(exchange_state))
        
        if tasks:
            # Gather all tasks with exception handling
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Log any exceptions that occurred and increment error counter
            for exchange_state, result in zip(exchange_states, results):
                if isinstance(result, Exception):
                    logger.error(f"Error scanning {exchange_state.label}: {result}")
                    exchange_state.consecutive_errors += 1
        
        # After scanning, clean up densities that weren't seen
        self._cleanup_missing_densities()
    
    async def _scan_all_exchanges_rest(self, exchange_states: list):
        """Scan specific exchanges using REST API concurrently."""
        # Increment miss counters before scan (will be reset for seen densities)
        for key in list(self._miss_counter.keys()):
            self._miss_counter[key] = self._miss_counter.get(key, 0) + 1
        
        # Build tasks for specified exchanges
        tasks = []
        for exchange_state in exchange_states:
            # Reset markets if too many consecutive errors
            if exchange_state.consecutive_errors > 10:
                logger.warning(f"Resetting markets for {exchange_state.label} due to consecutive errors")
                exchange_state.markets_loaded = False
                exchange_state.consecutive_errors = 0
            
            tasks.append(self._scan_exchange(exchange_state))
        
        if tasks:
            # Gather all tasks with exception handling
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Log any exceptions that occurred and increment error counter
            for exchange_state, result in zip(exchange_states, results):
                if isinstance(result, Exception):
                    logger.error(f"Error scanning {exchange_state.label}: {result}")
                    exchange_state.consecutive_errors += 1
        
        # After scanning, clean up densities that weren't seen
        self._cleanup_missing_densities()
    
    async def _ensure_connection(self, exchange_state: ExchangeState) -> bool:
        """Check and restore connection to exchange if needed."""
        try:
            # Simple connection test - try to load markets
            if not exchange_state.symbols or len(exchange_state.symbols) == 0:
                logger.info(f"Reconnecting to {exchange_state.label}...")
                await exchange_state.client.load_markets(reload=True)
                await self._load_markets(exchange_state)
                return True
            return True
        except Exception as e:
            logger.error(f"Failed to reconnect to {exchange_state.label}: {e}")
            return False
    
    async def _cleanup(self):
        """Close all exchange connections."""
        logger.info("Closing exchange connections...")
        for exchange_state in self._exchanges.values():
            if exchange_state.client:
                try:
                    await exchange_state.client.close()
                except Exception as e:
                    logger.error(f"Error closing REST client {exchange_state.label}: {e}")
            
            if exchange_state.ws_client:
                try:
                    await exchange_state.ws_client.close()
                except Exception as e:
                    logger.error(f"Error closing WS client {exchange_state.label}: {e}")
    
    async def run(self):
        """Main scanner loop with WebSocket support and REST fallback."""
        self._running = True
        logger.info("Starting density scanner...")
        
        try:
            # Initialize exchanges
            await self._initialize_exchanges()
            
            if not self._exchanges:
                logger.error("No exchanges initialized, exiting")
                return
            
            # Determine scanning mode based on WebSocket availability
            ws_exchanges = [e for e in self._exchanges.values() if e.ws_enabled]
            all_exchanges = list(self._exchanges.values())
            
            if ws_exchanges:
                logger.info(f"WebSocket enabled for {len(ws_exchanges)} exchanges (priority tickers only)")
                logger.info(f"REST scanning will cover ALL symbols on all {len(all_exchanges)} exchanges")
                
                # Start WebSocket scanning tasks for WS-enabled exchanges (priority tickers only)
                ws_tasks = []
                for exchange_state in ws_exchanges:
                    task = asyncio.create_task(self._ws_scan_exchange(exchange_state))
                    ws_tasks.append(task)
                
                # Run REST scanning loop for ALL exchanges (covers all symbols)
                # This runs in parallel with WebSocket to ensure complete coverage
                while self._running:
                    try:
                        # Scan ALL exchanges via REST (including WS-enabled ones)
                        await self._scan_all_exchanges_rest(all_exchanges)
                    except Exception as e:
                        logger.error(f"Error in REST scan loop: {e}")
                        await asyncio.sleep(5)
                        continue
                    
                    # Sleep until next scan interval
                    scan_interval = self.settings.scan_interval
                    for _ in range(scan_interval):
                        if not self._running:
                            break
                        await asyncio.sleep(1)
            else:
                # No WebSocket support, use REST polling for all exchanges
                logger.info("Using REST polling for all exchanges")
                while self._running:
                    try:
                        await self._scan_all_exchanges()
                    except Exception as e:
                        logger.error(f"Error in scan loop: {e}")
                        await asyncio.sleep(5)
                        continue
                    
                    # Sleep until next scan interval
                    scan_interval = self.settings.scan_interval
                    for _ in range(scan_interval):
                        if not self._running:
                            break
                        await asyncio.sleep(1)
        
        finally:
            await self._cleanup()
            logger.info("Scanner stopped")
    
    def stop(self):
        """Stop the scanner."""
        logger.info("Stopping scanner...")
        self._running = False
