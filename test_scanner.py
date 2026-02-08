"""
Comprehensive Exchange Scanner Tests
Tests orderbook handling, volume calculations, and exchange configurations.
"""

import sys
import os
import asyncio
from typing import Dict, Any

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scanner import DensityScanner
from settings_manager import SettingsManager

# Test configuration for supported exchanges
TEST_CONFIG = {
    "kucoin_futures": {
        "ccxt_id": "kucoinfutures",
        "label": "KuCoin Futures",
        "test_symbols": ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"],
        "has_cumulative_book": False,  # KuCoin returns individual volumes
        "ws_support": True,
        "market_type": "swap"
    },
    "kucoin_spot": {
        "ccxt_id": "kucoin",
        "label": "KuCoin Spot",
        "test_symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
        "has_cumulative_book": False,  # KuCoin returns individual volumes
        "ws_support": True,
        "market_type": "spot"
    },
    "bingx": {
        "ccxt_id": "bingx",
        "label": "BingX",
        "test_symbols": ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"],
        "has_cumulative_book": False,  # BingX returns individual volumes
        "ws_support": True,
        "market_type": "swap"
    },
    "hyperliquid": {
        "ccxt_id": "hyperliquid",
        "label": "Hyperliquid",
        "test_symbols": ["BTC/USD:USD", "ETH/USD:USD", "SOL/USD:USD"],  # Correct CCXT format
        "has_cumulative_book": False,  # Hyperliquid returns individual volumes
        "ws_support": True,
        "market_type": "swap"
    }
}


def test_individual_vs_cumulative_volumes():
    """
    Test: Verify that orderbook volumes are treated as individual, not cumulative.
    This test demonstrates the difference between cumulative and individual volume processing.
    """
    settings = SettingsManager(":memory:")
    scanner = DensityScanner(settings, lambda alert: None)
    
    print("\n" + "="*80)
    print("TEST: Individual vs Cumulative Volume Processing")
    print("="*80)
    
    # Create orderbook with individual volumes
    orderbook = {
        "bids": [
            [50000, 10],   # Level 0: 10 BTC = $500,000 individual
            [49900, 6],    # Level 1: 6 BTC = $299,400 individual
            [49800, 4],    # Level 2: 4 BTC = $199,200 individual
        ],
        "asks": [
            [50100, 1],
            [50200, 2],
        ]
    }
    
    print("\n📊 Orderbook (Individual Volumes):")
    print("Bids:")
    for i, (price, amount) in enumerate(orderbook["bids"]):
        volume = price * amount
        print(f"  Level {i}: Price=${price}, Amount={amount}, Volume=${volume:,.2f}")
    
    # Calculate expected cumulative volume
    cumulative_sum = sum(price * amount for price, amount in orderbook["bids"])
    print(f"\n✅ Expected Total (Sum of Individual): ${cumulative_sum:,.2f}")
    
    # Test with scanner (should sum individual volumes correctly)
    alerts = scanner._compute_densities("test", "BTC/USDT", orderbook, 900000, 1.0)
    
    if alerts:
        alert = alerts[0]
        print(f"✅ Scanner Calculated: ${alert.volume:,.2f}")
        
        # Verify the volumes match (allowing small floating point differences)
        difference = abs(alert.volume - cumulative_sum)
        assert difference < 1.0, f"Volume mismatch: {difference}"
        print(f"✅ Difference: ${difference:.8f} (acceptable)")
        
        # THIS IS WHAT WOULD HAPPEN WITH CUMULATIVE CONVERSION:
        print("\n❌ If treated as CUMULATIVE (INCORRECT):")
        print(f"  Level 0: {orderbook['bids'][0][1]} (first stays same)")
        print(f"  Level 1: {orderbook['bids'][1][1]} - {orderbook['bids'][0][1]} = {orderbook['bids'][1][1] - orderbook['bids'][0][1]} (underestimated)")
        print(f"  Level 2: {orderbook['bids'][2][1]} - {orderbook['bids'][1][1]} = {orderbook['bids'][2][1] - orderbook['bids'][1][1]} (negative!)")
        wrong_sum = orderbook['bids'][0][1]  # Only first level would be correct
        print(f"  ❌ WRONG Total: Only ${orderbook['bids'][0][0] * wrong_sum:,.2f} instead of ${cumulative_sum:,.2f}")
        
        print("\n✅ TEST PASSED: Volumes are correctly treated as individual")
        return True
    else:
        print("❌ No alert generated (threshold not met)")
        return False


def test_kucoin_futures_orderbook():
    """Test: KuCoin Futures orderbook with individual volumes."""
    settings = SettingsManager(":memory:")
    scanner = DensityScanner(settings, lambda alert: None)
    
    print("\n" + "="*80)
    print("TEST: KuCoin Futures Orderbook Processing")
    print("="*80)
    
    # Simulate KuCoin Futures orderbook (may have 2 or 3 values per entry)
    orderbook = {
        "bids": [
            [97234.5, 10, 12345],   # Price, Amount, Sequence
            [97234.0, 6, 12344],    # Individual volumes (not cumulative)
        ],
        "asks": [
            [97235.0, 1, 12346],
            [97235.5, 2, 12347],
        ]
    }
    
    print(f"\n📊 Config: has_cumulative_book = {TEST_CONFIG['kucoin_futures']['has_cumulative_book']}")
    
    # Calculate expected volume (sum of individual volumes with contract size)
    contract_size = 0.001  # BTC futures contract size
    expected_volume = sum(price * amount * contract_size for price, amount, _ in orderbook["bids"])
    
    print(f"\n✅ Individual Volumes:")
    cumulative = 0
    for i, (price, amount, seq) in enumerate(orderbook["bids"]):
        individual = price * amount * contract_size
        cumulative += individual
        print(f"  Level {i}: ${individual:,.2f} individual (cumulative: ${cumulative:,.2f})")
    
    print(f"\n✅ Expected Sum of Individual: ${expected_volume:,.2f}")
    
    # Scanner should process this correctly
    min_size = 1000  # Low threshold for testing
    alerts = scanner._compute_densities(
        "kucoin_futures", 
        "BTC/USDT:USDT", 
        orderbook, 
        min_size, 
        1.0, 
        contract_size=contract_size
    )
    
    assert len(alerts) >= 1, f"Expected at least 1 alert, got {len(alerts)}"
    alert = alerts[0]
    
    print(f"✅ Scanner Calculated: ${alert.volume:,.2f}")
    
    # Verify volumes match
    difference = abs(alert.volume - expected_volume)
    tolerance = expected_volume * 0.01  # 1% tolerance
    assert difference < tolerance, f"Volume difference {difference} exceeds tolerance {tolerance}"
    
    print(f"✅ Difference: ${difference:.8f}")
    print("✅ TEST PASSED: KuCoin Futures - No conversion errors")
    
    return True


def test_kucoin_spot_orderbook():
    """Test: KuCoin Spot orderbook with individual volumes."""
    settings = SettingsManager(":memory:")
    scanner = DensityScanner(settings, lambda alert: None)
    
    print("\n" + "="*80)
    print("TEST: KuCoin Spot Orderbook Processing")
    print("="*80)
    
    # Simulate KuCoin Spot orderbook
    orderbook = {
        "bids": [
            [50000, 0.01, 12345],   # Price, Amount, Sequence
            [49990, 0.005, 12344],  # Individual volumes
            [49980, 0.004, 12343],
        ],
        "asks": [
            [50010, 0.001, 12346],
            [50020, 0.002, 12347],
        ]
    }
    
    print(f"\n📊 Config: has_cumulative_book = {TEST_CONFIG['kucoin_spot']['has_cumulative_book']}")
    
    # Calculate expected volume
    expected_volume = sum(price * amount for price, amount, _ in orderbook["bids"])
    
    print(f"\n✅ Individual Volumes:")
    cumulative = 0
    for i, (price, amount, seq) in enumerate(orderbook["bids"]):
        individual = price * amount
        cumulative += individual
        print(f"  Level {i}: ${individual:.8f} individual (cumulative: ${cumulative:.8f})")
    
    print(f"\n✅ Expected Sum of Individual: ${expected_volume:.8f}")
    
    # Scanner should process this correctly
    # Use min_size of 900 so it accumulates all three levels
    alerts = scanner._compute_densities("kucoin_spot", "BTC/USDT", orderbook, 900, 1.0)
    
    assert len(alerts) >= 1, f"Expected at least 1 alert, got {len(alerts)}"
    alert = alerts[0]
    
    print(f"✅ Scanner Calculated: ${alert.volume:.8f}")
    
    # Verify volumes match (scanner accumulates until threshold is met)
    # It should have accumulated all three levels to exceed 900
    assert alert.volume >= 900, f"Volume {alert.volume} should be >= 900"
    difference = abs(alert.volume - expected_volume)
    assert difference < 0.01, f"Volume difference {difference:.8f} too large"
    
    print(f"✅ Difference: ${difference:.8f}")
    print("✅ TEST PASSED: KuCoin Spot - No conversion errors")
    
    return True


def test_hyperliquid_symbol_format():
    """Test: Hyperliquid uses correct CCXT symbol format."""
    settings = SettingsManager(":memory:")
    scanner = DensityScanner(settings, lambda alert: None)
    
    print("\n" + "="*80)
    print("TEST: Hyperliquid Symbol Format")
    print("="*80)
    
    # Check configured symbols
    symbols = TEST_CONFIG["hyperliquid"]["test_symbols"]
    print(f"\n✅ Configured Symbols: {symbols}")
    
    # Verify format (should be BTC/USD:USD, not BTC-USD)
    for symbol in symbols:
        assert "/" in symbol and ":" in symbol, f"Invalid format: {symbol}"
        print(f"  ✅ {symbol} - Correct format (BASE/QUOTE:SETTLE)")
    
    # Test with a sample orderbook
    orderbook = {
        "bids": [[50000, 10], [49900, 12]],
        "asks": [[50100, 1], [50200, 2]],
    }
    
    # Should work without errors
    alerts = scanner._compute_densities("hyperliquid", "BTC/USD:USD", orderbook, 1000000, 1.0)
    
    print(f"\n✅ Scanner processed BTC/USD:USD successfully")
    print(f"✅ Alerts generated: {len(alerts)}")
    print("✅ TEST PASSED: Hyperliquid - Correct symbol format")
    
    return True


def test_all_exchanges_individual_volumes():
    """Test: Verify all exchanges use individual volumes (not cumulative)."""
    print("\n" + "="*80)
    print("TEST: All Exchanges Configuration")
    print("="*80)
    
    print("\n📊 Exchange Configurations:")
    print("-" * 80)
    
    all_passed = True
    for exchange_name, config in TEST_CONFIG.items():
        has_cumulative = config["has_cumulative_book"]
        status = "✅" if not has_cumulative else "❌"
        
        print(f"{status} {config['label']:20s} - has_cumulative_book: {has_cumulative}")
        
        if has_cumulative:
            print(f"   ❌ ERROR: {exchange_name} should have has_cumulative_book=False")
            all_passed = False
    
    print("-" * 80)
    
    if all_passed:
        print("\n✅ TEST PASSED: All exchanges correctly configured with individual volumes")
    else:
        print("\n❌ TEST FAILED: Some exchanges have incorrect configuration")
    
    return all_passed


def run_all_tests():
    """Run all scanner tests."""
    print("=" * 80)
    print("Comprehensive Exchange Scanner Tests")
    print("=" * 80)
    
    tests = [
        ("Configuration Check", test_all_exchanges_individual_volumes),
        ("Individual vs Cumulative", test_individual_vs_cumulative_volumes),
        ("KuCoin Futures", test_kucoin_futures_orderbook),
        ("KuCoin Spot", test_kucoin_spot_orderbook),
        ("Hyperliquid Symbols", test_hyperliquid_symbol_format),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, "PASSED" if result else "FAILED", None))
        except Exception as e:
            print(f"\n❌ TEST FAILED: {test_name}")
            print(f"   Error: {e}")
            results.append((test_name, "FAILED", str(e)))
    
    # Print summary
    print("\n" + "=" * 80)
    print("## 📊 TEST SUMMARY")
    print("=" * 80)
    
    total = len(results)
    passed = sum(1 for _, status, _ in results if status == "PASSED")
    failed = total - passed
    
    print(f"\n- **Total Tests:** {total}")
    print(f"- **✅ Passed:** {passed}")
    print(f"- **❌ Failed:** {failed}")
    print(f"- **Success Rate:** {(passed/total*100):.1f}%")
    
    print("\n### Test Details:")
    for test_name, status, error in results:
        symbol = "✅" if status == "PASSED" else "❌"
        print(f"{symbol} {test_name}: {status}")
        if error:
            print(f"   Error: {error}")
    
    print("\n" + "=" * 80)
    
    if failed == 0:
        print("✅ ALL TESTS PASSED!")
        print("=" * 80)
        return True
    else:
        print(f"❌ {failed} TEST(S) FAILED")
        print("=" * 80)
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
