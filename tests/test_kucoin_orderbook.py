"""
Tests for KuCoin Spot WebSocket orderbook parsing with 3-value entries.
"""

import sys
import os

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanner import DensityScanner
from settings_manager import SettingsManager


def test_kucoin_spot_three_value_orderbook():
    """Test: KuCoin Spot orderbook with 3-value entries [price, amount, sequence]."""
    settings = SettingsManager(":memory:")
    scanner = DensityScanner(settings, lambda alert: None)
    
    # KuCoin Spot returns 3-value entries: [price, amount, sequence/timestamp]
    orderbook = {
        "bids": [
            [50000, 10, 12345],  # $500,000 - with sequence number
            [49900, 12, 12344],  # $598,800 - with sequence number
        ],
        "asks": [
            [50100, 1, 12346],   # with sequence number
            [50200, 2, 12347],   # with sequence number
        ]
    }
    
    # Should work without error now (previously failed with "too many values to unpack")
    alerts = scanner._compute_densities("kucoin_spot", "BTC/USDT", orderbook, 1000000, 1.0)
    assert len(alerts) == 1, f"Expected 1 alert, got {len(alerts)}"
    assert alerts[0].side == "bid", f"Expected bid side, got {alerts[0].side}"
    assert 1_000_000 <= alerts[0].volume <= 1_200_000, f"Expected volume ~$1.1M, got ${alerts[0].volume:,.0f}"
    print(f"✓ test_kucoin_spot_three_value_orderbook: Alert volume = ${alerts[0].volume:,.0f}")


def test_two_value_orderbook_still_works():
    """Test: Standard 2-value orderbook entries still work correctly."""
    settings = SettingsManager(":memory:")
    scanner = DensityScanner(settings, lambda alert: None)
    
    # Standard orderbook with 2-value entries: [price, amount]
    orderbook = {
        "bids": [
            [50000, 10],  # $500,000
            [49900, 12],  # $598,800
        ],
        "asks": [
            [50100, 1],
            [50200, 2],
        ]
    }
    
    # Should work as before
    alerts = scanner._compute_densities("binance", "BTC/USDT", orderbook, 1000000, 1.0)
    assert len(alerts) == 1, f"Expected 1 alert, got {len(alerts)}"
    assert alerts[0].side == "bid", f"Expected bid side, got {alerts[0].side}"
    assert 1_000_000 <= alerts[0].volume <= 1_200_000, f"Expected volume ~$1.1M, got ${alerts[0].volume:,.0f}"
    print(f"✓ test_two_value_orderbook_still_works: Alert volume = ${alerts[0].volume:,.0f}")


def test_mixed_value_lengths():
    """Test: Orderbook with mixed 2-value and 3-value entries (edge case)."""
    settings = SettingsManager(":memory:")
    scanner = DensityScanner(settings, lambda alert: None)
    
    # Edge case: mixed formats (should still work with index-based access)
    orderbook = {
        "bids": [
            [50000, 10, 12345],  # 3-value entry
            [49900, 12],          # 2-value entry
        ],
        "asks": [
            [50100, 1],           # 2-value entry
            [50200, 2, 12346],    # 3-value entry
        ]
    }
    
    # Index-based access should handle both formats
    alerts = scanner._compute_densities("test", "BTC/USDT", orderbook, 1000000, 1.0)
    assert len(alerts) == 1, f"Expected 1 alert, got {len(alerts)}"
    print(f"✓ test_mixed_value_lengths: Alert volume = ${alerts[0].volume:,.0f}")


def test_kucoin_spot_ask_alert():
    """Test: KuCoin Spot ask-side alert with 3-value entries."""
    settings = SettingsManager(":memory:")
    scanner = DensityScanner(settings, lambda alert: None)
    
    # Test ask side with 3-value entries
    orderbook = {
        "bids": [
            [49900, 1, 12343],
        ],
        "asks": [
            [50000, 10, 12345],  # $500,000
            [50100, 12, 12346],  # $601,200 -> total ~$1,101,200
        ]
    }
    
    alerts = scanner._compute_densities("kucoin_spot", "BTC/USDT", orderbook, 1000000, 1.0)
    assert len(alerts) == 1, f"Expected 1 alert, got {len(alerts)}"
    assert alerts[0].side == "ask", f"Expected ask side, got {alerts[0].side}"
    assert 1_000_000 <= alerts[0].volume <= 1_200_000, f"Expected volume ~$1.1M, got ${alerts[0].volume:,.0f}"
    print(f"✓ test_kucoin_spot_ask_alert: Alert volume = ${alerts[0].volume:,.0f}")


if __name__ == "__main__":
    print("Running KuCoin Spot orderbook parsing tests...\n")
    
    test_kucoin_spot_three_value_orderbook()
    test_two_value_orderbook_still_works()
    test_mixed_value_lengths()
    test_kucoin_spot_ask_alert()
    
    print("\n✓ All KuCoin orderbook tests passed!")
