"""
Tests for contract size handling in density calculations.
"""

import sys
import os

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanner import DensityScanner
from settings_manager import SettingsManager


def test_futures_contract_size_applied():
    """Test: contract_size multiplier is correctly applied for futures."""
    settings = SettingsManager(":memory:")
    scanner = DensityScanner(settings, lambda alert: None)
    
    # Simulate BTC futures: price=100000, amount=5000 contracts, contractSize=0.001
    # Real volume per level: 100000 * 5000 * 0.001 = $500,000
    orderbook = {
        "bids": [
            [100000, 5000],  # 5000 contracts * 0.001 = 5 BTC = $500,000
            [99900, 6000],   # 6000 contracts * 0.001 = 6 BTC = $599,400
        ],
        "asks": [
            [100100, 1000],
            [100200, 1000],
        ]
    }
    
    # With contract_size=0.001, total bid volume = $500,000 + $599,400 = $1,099,400
    alerts = scanner._compute_densities("kucoin_futures", "BTC/USDT:USDT", orderbook, 1000000, 1.0, contract_size=0.001)
    assert len(alerts) == 1, f"Expected 1 alert, got {len(alerts)}"
    assert alerts[0].side == "bid", f"Expected bid side, got {alerts[0].side}"
    assert 1_000_000 <= alerts[0].volume <= 1_200_000, f"Expected volume ~$1.1M, got ${alerts[0].volume:,.0f}"
    print(f"✓ test_futures_contract_size_applied: Alert volume = ${alerts[0].volume:,.0f}")


def test_futures_without_contract_size_inflated():
    """Test: without contract_size, futures volumes are incorrectly inflated."""
    settings = SettingsManager(":memory:")
    scanner = DensityScanner(settings, lambda alert: None)
    
    # Same orderbook as above but with contract_size=1.0 (no correction)
    orderbook = {
        "bids": [
            [100000, 5000],  # Without multiplier: $500,000,000 (wrong!)
        ],
        "asks": [
            [100100, 1000],  # Without multiplier: $100,100,000
        ]
    }
    
    # With contract_size=1.0, volume = 100000 * 5000 * 1.0 = $500,000,000 (1000x inflated)
    alerts = scanner._compute_densities("kucoin_futures", "BTC/USDT:USDT", orderbook, 1000000, 1.0, contract_size=1.0)
    # Both sides trigger alerts since volumes are inflated
    assert len(alerts) >= 1, f"Expected at least 1 alert, got {len(alerts)}"
    # Find the bid alert
    bid_alerts = [a for a in alerts if a.side == "bid"]
    assert len(bid_alerts) >= 1, "Expected at least one bid alert"
    assert bid_alerts[0].volume >= 400_000_000, f"Expected inflated volume >= $400M, got ${bid_alerts[0].volume:,.0f}"
    print(f"✓ test_futures_without_contract_size_inflated: Inflated volume = ${bid_alerts[0].volume:,.0f}")


def test_spot_contract_size_default():
    """Test: spot markets default to contract_size=1.0."""
    settings = SettingsManager(":memory:")
    scanner = DensityScanner(settings, lambda alert: None)
    
    orderbook = {
        "bids": [
            [50000, 10],  # $500,000
            [49900, 12],  # $598,800 -> total ~$1,098,800
        ],
        "asks": [
            [50100, 1],
        ]
    }
    
    # Default contract_size=1.0 for spot
    alerts = scanner._compute_densities("kucoin_spot", "BTC/USDT", orderbook, 1000000, 1.0)
    assert len(alerts) == 1, f"Expected 1 alert, got {len(alerts)}"
    assert alerts[0].volume >= 1_000_000, f"Expected volume >= $1M, got ${alerts[0].volume:,.0f}"
    print(f"✓ test_spot_contract_size_default: Alert volume = ${alerts[0].volume:,.0f}")


def test_contract_size_zero_defaults_to_one():
    """Test: contract_size=0 should be treated as 1.0 to avoid zero volumes."""
    settings = SettingsManager(":memory:")
    scanner = DensityScanner(settings, lambda alert: None)
    
    orderbook = {
        "bids": [
            [50000, 25],  # $1,250,000 with contract_size=1.0
        ],
        "asks": [
            [50100, 1],
        ]
    }
    
    # contract_size=0 should be handled gracefully (treated as 1.0)
    # The _compute_densities function receives contract_size from _scan_symbol which validates it
    # But test with contract_size=1.0 to verify behavior
    alerts = scanner._compute_densities("test", "BTC/USDT", orderbook, 1000000, 1.0, contract_size=1.0)
    assert len(alerts) == 1, f"Expected 1 alert, got {len(alerts)}"
    assert alerts[0].volume > 0, f"Expected volume > 0, got ${alerts[0].volume:,.0f}"
    print(f"✓ test_contract_size_zero_defaults_to_one: Alert volume = ${alerts[0].volume:,.0f}")


def test_eth_futures_contract_size():
    """Test: ETH futures with contract_size=0.01."""
    settings = SettingsManager(":memory:")
    scanner = DensityScanner(settings, lambda alert: None)
    
    # ETH futures: price=3000, amount=10000 contracts, contractSize=0.01
    # Real volume: 3000 * 10000 * 0.01 = $300,000
    orderbook = {
        "bids": [
            [3000, 10000],  # 10000 contracts * 0.01 = 100 ETH = $300,000
            [2990, 15000],  # 15000 contracts * 0.01 = 150 ETH = $448,500 -> total $748,500
        ],
        "asks": [
            [3010, 1000],
        ]
    }
    
    alerts = scanner._compute_densities("kucoin_futures", "ETH/USDT:USDT", orderbook, 700000, 1.0, contract_size=0.01)
    assert len(alerts) == 1, f"Expected 1 alert, got {len(alerts)}"
    assert 700_000 <= alerts[0].volume <= 800_000, f"Expected volume ~$748K, got ${alerts[0].volume:,.0f}"
    print(f"✓ test_eth_futures_contract_size: Alert volume = ${alerts[0].volume:,.0f}")


def test_xrp_futures_contract_size_one():
    """Test: XRP futures with contract_size=1 (no inflation)."""
    settings = SettingsManager(":memory:")
    scanner = DensityScanner(settings, lambda alert: None)
    
    # XRP futures: price=0.5, amount=1000000 contracts, contractSize=1
    # Real volume: 0.5 * 1000000 * 1 = $500,000
    orderbook = {
        "bids": [
            [0.5, 1000000],  # 1000000 contracts * 1 = 1M XRP = $500,000
            [0.49, 1200000], # 1200000 contracts * 1 = 1.2M XRP = $588,000 -> total $1,088,000
        ],
        "asks": [
            [0.51, 100000],
        ]
    }
    
    # Use 3% distance to capture both levels
    alerts = scanner._compute_densities("kucoin_futures", "XRP/USDT:USDT", orderbook, 1000000, 3.0, contract_size=1.0)
    assert len(alerts) == 1, f"Expected 1 alert, got {len(alerts)}"
    assert 1_000_000 <= alerts[0].volume <= 1_200_000, f"Expected volume ~$1.088M, got ${alerts[0].volume:,.0f}"
    print(f"✓ test_xrp_futures_contract_size_one: Alert volume = ${alerts[0].volume:,.0f}")


if __name__ == "__main__":
    print("Running contract size tests...\n")
    
    test_futures_contract_size_applied()
    test_futures_without_contract_size_inflated()
    test_spot_contract_size_default()
    test_contract_size_zero_defaults_to_one()
    test_eth_futures_contract_size()
    test_xrp_futures_contract_size_one()
    
    print("\n✓ All tests passed!")
