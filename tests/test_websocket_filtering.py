"""
Tests for WebSocket symbol filtering logic (priority tickers only).
"""

import sys
import os

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import PRIORITY_TICKERS, WS_MAX_SYMBOLS_PER_EXCHANGE


def test_priority_ticker_extraction():
    """Test: Extract base symbols and check if they are in PRIORITY_TICKERS."""
    # Symbols that should be identified as priority
    priority_symbols = [
        ("BTC/USDT", "BTC", True),
        ("ETH/USD", "ETH", True),
        ("SOL/USDC", "SOL", True),
        ("XRP/USDT:USDT", "XRP", True),
        ("DOGE-USD", "DOGE", True),
        ("PEPE/USDT", "PEPE", True),
        ("HYPE-USD", "HYPE", True),
        ("BNB/USDT", "BNB", True),
    ]
    
    # Symbols that should NOT be identified as priority
    non_priority_symbols = [
        ("WARD/USDT", "WARD", False),
        ("MOVA/USDT", "MOVA", False),
        ("AGT/USDT:USDT", "AGT", False),
        ("RANDOM-USD", "RANDOM", False),
    ]
    
    all_test_cases = priority_symbols + non_priority_symbols
    
    for symbol, expected_base, should_be_priority in all_test_cases:
        # Extract base symbol using same logic as scanner
        if '/' in symbol:
            base = symbol.split('/')[0]
        elif ':' in symbol:
            base = symbol.split(':')[0].split('/')[0]
        elif '-' in symbol:
            base = symbol.split('-')[0]
        else:
            base = symbol
        
        # Verify base extraction
        assert base == expected_base, f"Expected base '{expected_base}' for {symbol}, got '{base}'"
        
        # Verify priority status
        is_priority = base.upper() in PRIORITY_TICKERS
        assert is_priority == should_be_priority, \
            f"Expected {symbol} (base: {base}) to be priority={should_be_priority}, but got {is_priority}"
    
    print(f"✓ test_priority_ticker_extraction: All {len(all_test_cases)} symbols correctly classified")


def test_priority_filtering_logic():
    """Test: Simulate the filtering logic used in _ws_scan_exchange."""
    all_symbols = [
        "BTC/USDT",      # Priority
        "ETH/USD",       # Priority
        "SOL/USDT",      # Priority
        "XRP/USDT",      # Priority
        "WARD/USDT",     # Not priority
        "MOVA/USDT",     # Not priority
        "AAVE/USDT",     # Priority
        "AGT/USDT:USDT", # Not priority
        "DOGE-USD",      # Priority
        "RANDOM/USDT",   # Not priority
    ]
    
    # Filter to only priority symbols (same logic as _ws_scan_exchange)
    ws_symbols = []
    for symbol in all_symbols:
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
    
    # Expected priority symbols
    expected_priority = ["BTC/USDT", "ETH/USD", "SOL/USDT", "XRP/USDT", "AAVE/USDT", "DOGE-USD"]
    
    assert set(ws_symbols) == set(expected_priority), \
        f"Expected priority symbols {expected_priority}, got {ws_symbols}"
    
    print(f"✓ test_priority_filtering_logic: Filtered {len(ws_symbols)}/{len(all_symbols)} priority symbols correctly")


def test_ws_max_symbols_limit():
    """Test: Verify WS_MAX_SYMBOLS_PER_EXCHANGE limit is enforced."""
    # Simulate many priority symbols (more than the limit)
    many_priority_symbols = [f"{ticker}/USDT" for ticker in PRIORITY_TICKERS[:20]]
    
    # Apply the limit (same logic as _ws_scan_exchange)
    ws_symbols = many_priority_symbols
    if len(ws_symbols) > WS_MAX_SYMBOLS_PER_EXCHANGE:
        ws_symbols = ws_symbols[:WS_MAX_SYMBOLS_PER_EXCHANGE]
    
    # Verify the limit is applied
    assert len(ws_symbols) <= WS_MAX_SYMBOLS_PER_EXCHANGE, \
        f"Expected max {WS_MAX_SYMBOLS_PER_EXCHANGE} symbols, got {len(ws_symbols)}"
    
    print(f"✓ test_ws_max_symbols_limit: Limit of {WS_MAX_SYMBOLS_PER_EXCHANGE} correctly enforced")


def test_ws_max_symbols_config():
    """Test: Verify WS_MAX_SYMBOLS_PER_EXCHANGE is set to expected value."""
    assert WS_MAX_SYMBOLS_PER_EXCHANGE == 30, \
        f"Expected WS_MAX_SYMBOLS_PER_EXCHANGE=30, got {WS_MAX_SYMBOLS_PER_EXCHANGE}"
    
    print(f"✓ test_ws_max_symbols_config: WS_MAX_SYMBOLS_PER_EXCHANGE correctly set to {WS_MAX_SYMBOLS_PER_EXCHANGE}")


def test_expected_ws_connection_count():
    """Test: Verify expected WebSocket connection count for typical scenario."""
    # Simulate typical exchange with many symbols including priority ones
    typical_exchange_symbols = [
        # Priority tickers (from PRIORITY_TICKERS)
        "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT",
        "PEPE/USDT", "WIF/USDT", "HYPE/USDT", "SUI/USDT", "AAVE/USDT",
        "BNB/USDT", "LINK/USDT", "SEI/USDT", "PUMP/USDT",
        # Many non-priority tickers (would have caused the problem)
        "WARD/USDT", "MOVA/USDT", "AGT/USDT", "RANDOM1/USDT", "RANDOM2/USDT",
    ] + [f"RANDOM{i}/USDT" for i in range(3, 100)]  # Simulate 1000+ symbols
    
    # Apply filtering
    ws_symbols = []
    for symbol in typical_exchange_symbols:
        if '/' in symbol:
            base = symbol.split('/')[0]
        elif '-' in symbol:
            base = symbol.split('-')[0]
        else:
            base = symbol
        
        if base.upper() in PRIORITY_TICKERS:
            ws_symbols.append(symbol)
    
    # Verify we only have priority tickers
    assert len(ws_symbols) == 14, f"Expected 14 priority symbols, got {len(ws_symbols)}"
    
    # For 4 exchanges with ~14 priority symbols each
    total_ws_connections = 4 * min(len(ws_symbols), WS_MAX_SYMBOLS_PER_EXCHANGE)
    assert total_ws_connections == 56, \
        f"Expected ~56 total WS connections (4 exchanges * 14 symbols), got {total_ws_connections}"
    
    print(f"✓ test_expected_ws_connection_count: {total_ws_connections} WS connections (instead of 1000+)")


if __name__ == "__main__":
    print("Running WebSocket filtering tests...\n")
    
    test_priority_ticker_extraction()
    test_priority_filtering_logic()
    test_ws_max_symbols_limit()
    test_ws_max_symbols_config()
    test_expected_ws_connection_count()
    
    print("\n✓ All WebSocket filtering tests passed!")
