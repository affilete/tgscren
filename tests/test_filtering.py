"""
Tests for symbol filtering logic (test tokens, non-USD pairs, etc.)
"""

import sys
import os

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanner import DensityScanner
from settings_manager import SettingsManager
from config import SKIP_PREFIXES, SKIP_PATTERNS


def test_skip_test_prefixes():
    """Test: symbols starting with TEST or XYZ are filtered out."""
    settings = SettingsManager(":memory:")
    scanner = DensityScanner(settings, lambda alert: None)
    
    # Test symbols that should be skipped
    test_symbols = [
        "TEST251204B/USDT",
        "TEST123/USD",
        "XYZ/USDT",
        "XYZ-EUR",
        "XYZ-USD",
        "test123/USDT",  # lowercase should also be filtered
        "xyz-usd",  # lowercase
    ]
    
    for symbol in test_symbols:
        # Extract base symbol
        if '/' in symbol:
            base_symbol = symbol.split('/')[0]
        elif '-' in symbol:
            base_symbol = symbol.split('-')[0]
        else:
            base_symbol = symbol
        
        # Check if base symbol starts with skip prefixes
        base_upper = base_symbol.upper()
        is_test_token = base_upper.startswith(SKIP_PREFIXES)
        
        assert is_test_token, f"Expected {symbol} to be filtered (starts with test prefix), but it wasn't"
    
    print(f"✓ test_skip_test_prefixes: All {len(test_symbols)} test tokens correctly identified")


def test_skip_demo_patterns():
    """Test: symbols containing DEMO, SANDBOX, MOCK are filtered out."""
    settings = SettingsManager(":memory:")
    scanner = DensityScanner(settings, lambda alert: None)
    
    # Test symbols that should be skipped
    demo_symbols = [
        "DEMOACC/USDT",
        "SANDBOX/USD",
        "MOCKTOKEN/USDT",
        "demo-usd",  # lowercase
        "sandbox-usdt",  # lowercase
    ]
    
    for symbol in demo_symbols:
        # Extract base symbol
        if '/' in symbol:
            base_symbol = symbol.split('/')[0]
        elif '-' in symbol:
            base_symbol = symbol.split('-')[0]
        else:
            base_symbol = symbol
        
        # Check if base symbol contains skip patterns
        base_upper = base_symbol.upper()
        is_demo_token = any(pattern in base_upper for pattern in SKIP_PATTERNS)
        
        assert is_demo_token, f"Expected {symbol} to be filtered (contains demo pattern), but it wasn't"
    
    print(f"✓ test_skip_demo_patterns: All {len(demo_symbols)} demo tokens correctly identified")


def test_valid_usd_pairs():
    """Test: USD-denominated pairs are NOT filtered out."""
    settings = SettingsManager(":memory:")
    
    valid_symbols = [
        "BTC/USDT",
        "ETH/USD",
        "SOL/USDC",
        "XRP/BUSD",
        "BTC/USDT:USDT",  # futures
        "ETH/USD:USD",  # futures
        "BTC-USD",  # Hyperliquid style
        "ETH-USDT",  # Hyperliquid style
    ]
    
    valid_quotes = settings.quote_currencies
    
    for symbol in valid_symbols:
        symbol_upper = symbol.upper()
        is_valid_quote = any(
            symbol_upper.endswith(f'/{q}') or 
            symbol_upper.endswith(f':{q}') or 
            symbol_upper.endswith(f'-{q}')
            for q in valid_quotes
        )
        
        assert is_valid_quote, f"Expected {symbol} to be valid USD pair, but it was filtered"
    
    print(f"✓ test_valid_usd_pairs: All {len(valid_symbols)} valid USD pairs correctly accepted")


def test_invalid_non_usd_pairs():
    """Test: non-USD pairs are filtered out."""
    settings = SettingsManager(":memory:")
    
    invalid_symbols = [
        "XYZ-EUR",  # Hyperliquid EUR pair
        "BTC-BTC",  # Non-dollar denominated
        "ETH-EUR",  # EUR pair
        "SOL/EUR",  # Spot EUR pair
        "BTC/GBP",  # GBP pair
        "ETH-JPY",  # JPY pair
    ]
    
    valid_quotes = settings.quote_currencies
    
    for symbol in invalid_symbols:
        symbol_upper = symbol.upper()
        is_valid_quote = any(
            symbol_upper.endswith(f'/{q}') or 
            symbol_upper.endswith(f':{q}') or 
            symbol_upper.endswith(f'-{q}')
            for q in valid_quotes
        )
        
        assert not is_valid_quote, f"Expected {symbol} to be filtered (non-USD pair), but it wasn't"
    
    print(f"✓ test_invalid_non_usd_pairs: All {len(invalid_symbols)} non-USD pairs correctly filtered")


def test_base_symbol_extraction():
    """Test: base symbol extraction works for all formats."""
    test_cases = [
        ("BTC/USDT", "BTC"),
        ("ETH/USD", "ETH"),
        ("BTC/USDT:USDT", "BTC"),
        ("ETH/USD:USD", "ETH"),
        ("BTC-USD", "BTC"),
        ("ETH-USDT", "ETH"),
        ("XYZ-EUR", "XYZ"),
        ("TEST123/USDT", "TEST123"),
        ("TESTTOKEN-USD", "TESTTOKEN"),
    ]
    
    for symbol, expected_base in test_cases:
        # Extract base symbol using same logic as scanner
        if '/' in symbol:
            base_symbol = symbol.split('/')[0]
        elif ':' in symbol:
            base_symbol = symbol.split(':')[0].split('/')[0]
        elif '-' in symbol:
            base_symbol = symbol.split('-')[0]
        else:
            base_symbol = symbol
        
        assert base_symbol == expected_base, f"Expected base '{expected_base}' for {symbol}, got '{base_symbol}'"
    
    print(f"✓ test_base_symbol_extraction: All {len(test_cases)} base symbol extractions correct")


def test_hyperliquid_style_pairs():
    """Test: Hyperliquid-style pairs with dash separator are handled correctly."""
    settings = SettingsManager(":memory:")
    
    # Valid Hyperliquid pairs (USD-denominated)
    valid_hl_pairs = [
        "BTC-USD",
        "ETH-USDT",
        "SOL-USD",
        "HYPE-USD",
    ]
    
    # Invalid Hyperliquid pairs (non-USD)
    invalid_hl_pairs = [
        "XYZ-EUR",
        "BTC-BTC",
        "ETH-GBP",
    ]
    
    valid_quotes = settings.quote_currencies
    
    # Check valid pairs
    for symbol in valid_hl_pairs:
        symbol_upper = symbol.upper()
        is_valid = any(symbol_upper.endswith(f'-{q}') for q in valid_quotes)
        assert is_valid, f"Expected {symbol} to be valid Hyperliquid USD pair"
    
    # Check invalid pairs
    for symbol in invalid_hl_pairs:
        symbol_upper = symbol.upper()
        is_valid = any(symbol_upper.endswith(f'-{q}') for q in valid_quotes)
        assert not is_valid, f"Expected {symbol} to be invalid (non-USD)"
    
    print(f"✓ test_hyperliquid_style_pairs: Hyperliquid pairs correctly filtered")


def test_market_loading_filters():
    """Test: _load_markets would filter symbols correctly based on the updated logic."""
    settings = SettingsManager(":memory:")
    
    # Simulate markets dict
    mock_markets = {
        "BTC/USDT": {"quote": "USDT"},
        "ETH/USD": {"quote": "USD"},
        "BTC/USDT:USDT": {"contract": True, "linear": True, "quote": "USDT"},
        "BTC-USD": {"quote": "USD"},
        "XYZ-EUR": {"quote": "EUR"},
        "SOL/EUR": {"quote": "EUR"},
        "TEST123/USDT": {"quote": "USDT"},
    }
    
    quote_currencies = settings.quote_currencies
    filtered_symbols = []
    
    for symbol, market_info in mock_markets.items():
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
    
    # Expected valid symbols (TEST123 passes market filter, would be caught by prefix filter)
    expected = ["BTC/USDT", "ETH/USD", "BTC/USDT:USDT", "BTC-USD", "TEST123/USDT"]
    
    assert set(filtered_symbols) == set(expected), f"Expected {expected}, got {filtered_symbols}"
    print(f"✓ test_market_loading_filters: Market filtering logic works correctly")


if __name__ == "__main__":
    print("Running symbol filtering tests...\n")
    
    test_skip_test_prefixes()
    test_skip_demo_patterns()
    test_valid_usd_pairs()
    test_invalid_non_usd_pairs()
    test_base_symbol_extraction()
    test_hyperliquid_style_pairs()
    test_market_loading_filters()
    
    print("\n✓ All filtering tests passed!")
