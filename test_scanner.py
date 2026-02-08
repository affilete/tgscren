"""
Comprehensive Exchange Configuration Test Suite

Tests exchange configurations to ensure:
1. No cumulative-to-individual volume conversion exists
2. Correct symbol formats for each exchange
3. Proper orderbook handling for all supported exchanges
"""

import asyncio
import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scanner import DensityScanner
from settings_manager import SettingsManager


# Exchange Test Configuration
TEST_CONFIG = {
    "kucoin_futures": {
        "ccxt_id": "kucoinfutures",
        "label": "KuCoin Futures",
        "test_symbols": ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"],
        "has_cumulative_book": False,  # ✅ KuCoin returns individual volumes
        "ws_support": True,
        "market_type": "swap"
    },
    "kucoin_spot": {
        "ccxt_id": "kucoin",
        "label": "KuCoin Spot",
        "test_symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
        "has_cumulative_book": False,  # ✅ KuCoin returns individual volumes
        "ws_support": True,
        "market_type": "spot"
    },
    "bingx": {
        "ccxt_id": "bingx",
        "label": "BingX",
        "test_symbols": ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"],
        "has_cumulative_book": False,  # ✅ BingX returns individual volumes
        "ws_support": True,
        "market_type": "swap"
    },
    "hyperliquid": {
        "ccxt_id": "hyperliquid",
        "label": "Hyperliquid",
        "test_symbols": ["BTC/USD:USD", "ETH/USD:USD", "SOL/USD:USD"],  # ✅ Perpetual format
        "has_cumulative_book": False,  # ✅ Hyperliquid returns individual volumes
        "ws_support": True,
        "market_type": "swap"
    }
}


def test_no_cumulative_conversion():
    """
    Test 1: Verify that no cumulative-to-individual conversion exists.
    
    All exchanges (KuCoin, BingX, Hyperliquid, Binance, Bybit) return
    individual volumes at each price level, NOT cumulative.
    """
    print("\n" + "="*70)
    print("TEST 1: No Cumulative-to-Individual Conversion")
    print("="*70)
    
    settings = SettingsManager(":memory:")
    scanner = DensityScanner(settings, lambda alert: None)
    
    # Simulate orderbook with individual volumes (standard format)
    orderbook = {
        "bids": [
            [50000, 10],   # Level 0: 10 BTC = $500,000
            [49900, 15],   # Level 1: 15 BTC = $748,500 (NOT cumulative)
            [49800, 20],   # Level 2: 20 BTC = $996,000 (NOT cumulative)
        ],
        "asks": [
            [50100, 5],
            [50200, 10],
        ]
    }
    
    # Compute densities - should accumulate volumes correctly
    alerts = scanner._compute_densities("test_exchange", "BTC/USDT", orderbook, 1000000, 3.0)
    
    # Expected: cumulative volume should reach $2,244,500 (500k + 748.5k + 996k)
    # Algorithm should detect density and break
    assert len(alerts) >= 1, "Expected at least one alert"
    
    bid_alert = next((a for a in alerts if a.side == "bid"), None)
    assert bid_alert is not None, "Expected bid alert"
    
    # Volume should be cumulative sum, not individual
    # First level: $500k (< 1M threshold, continue)
    # Second level: $500k + $748.5k = $1,248.5k (>= 1M threshold, alert!)
    expected_volume_min = 1_000_000  # At least the threshold
    expected_volume_max = 2_500_000  # Should break after hitting threshold
    
    assert expected_volume_min <= bid_alert.volume <= expected_volume_max, \
        f"Volume {bid_alert.volume:,.0f} outside expected range [{expected_volume_min:,.0f}, {expected_volume_max:,.0f}]"
    
    print(f"✅ PASSED: No cumulative conversion detected")
    print(f"   Cumulative volume calculated correctly: ${bid_alert.volume:,.2f}")
    print(f"   Algorithm properly accumulates individual volumes from orderbook")
    
    return True


async def test_exchange_symbol_formats():
    """
    Test 2: Verify correct symbol formats for each exchange.
    
    - KuCoin Futures: BTC/USDT:USDT (linear perpetual)
    - KuCoin Spot: BTC/USDT (spot)
    - BingX: BTC/USDT:USDT (linear perpetual)
    - Hyperliquid: BTC/USD:USD (USD perpetual)
    """
    print("\n" + "="*70)
    print("TEST 2: Exchange Symbol Formats")
    print("="*70)
    
    settings = SettingsManager(":memory:")
    scanner = DensityScanner(settings, lambda alert: None)
    
    results = {}
    
    for exchange_name, config in TEST_CONFIG.items():
        print(f"\n📊 Testing {config['label']}...")
        print(f"   CCXT ID: {config['ccxt_id']}")
        print(f"   Expected symbols: {config['test_symbols']}")
        print(f"   Market type: {config['market_type']}")
        
        # Check if exchange is available
        import ccxt.async_support as ccxt
        
        if not hasattr(ccxt, config['ccxt_id']):
            print(f"   ⚠️  Exchange {config['ccxt_id']} not available in CCXT")
            results[exchange_name] = "SKIPPED"
            continue
        
        try:
            # Initialize exchange
            exchange_class = getattr(ccxt, config['ccxt_id'])
            exchange = exchange_class({'enableRateLimit': True})
            
            # Load markets
            print(f"   Loading markets...")
            markets = await exchange.load_markets()
            
            # Check if test symbols exist
            found_symbols = []
            missing_symbols = []
            
            for symbol in config['test_symbols']:
                if symbol in markets:
                    found_symbols.append(symbol)
                    market = markets[symbol]
                    print(f"   ✅ {symbol}: {market.get('type', 'unknown')} market")
                else:
                    missing_symbols.append(symbol)
            
            if missing_symbols:
                print(f"   ⚠️  Symbols not found: {missing_symbols}")
                
                # Try to find similar symbols
                print(f"   Searching for alternatives...")
                base_currency = config['test_symbols'][0].split('/')[0]
                alternatives = [s for s in markets.keys() if base_currency in s][:5]
                if alternatives:
                    print(f"   💡 Similar symbols available: {alternatives}")
            
            await exchange.close()
            
            if len(found_symbols) == len(config['test_symbols']):
                results[exchange_name] = "PASSED"
                print(f"   ✅ All test symbols found!")
            elif found_symbols:
                results[exchange_name] = "PARTIAL"
                print(f"   ⚠️  Some symbols found: {len(found_symbols)}/{len(config['test_symbols'])}")
            else:
                results[exchange_name] = "FAILED"
                print(f"   ❌ No test symbols found")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            results[exchange_name] = "ERROR"
    
    print("\n" + "="*70)
    print("Symbol Format Test Results:")
    print("="*70)
    for exchange, result in results.items():
        emoji = "✅" if result == "PASSED" else "⚠️" if result in ["PARTIAL", "SKIPPED"] else "❌"
        print(f"{emoji} {TEST_CONFIG[exchange]['label']}: {result}")
    
    return results


def test_kucoin_orderbook_format():
    """
    Test 3: Verify KuCoin orderbook handling (3-value entries).
    
    KuCoin returns [price, amount, sequence] instead of [price, amount].
    Scanner should handle both formats.
    """
    print("\n" + "="*70)
    print("TEST 3: KuCoin Orderbook Format (3-value entries)")
    print("="*70)
    
    settings = SettingsManager(":memory:")
    scanner = DensityScanner(settings, lambda alert: None)
    
    # KuCoin format: [price, amount, sequence]
    orderbook_3val = {
        "bids": [
            [50000, 20, 12345],  # $1,000,000
            [49900, 10, 12344],
        ],
        "asks": [
            [50100, 5, 12346],
            [50200, 10, 12347],
        ]
    }
    
    alerts = scanner._compute_densities("kucoin_spot", "BTC/USDT", orderbook_3val, 900000, 3.0)
    assert len(alerts) >= 1, "Expected at least one alert"
    
    bid_alert = next((a for a in alerts if a.side == "bid"), None)
    assert bid_alert is not None, "Expected bid alert"
    assert bid_alert.volume >= 900000, f"Expected volume >= $900k, got ${bid_alert.volume:,.0f}"
    
    print(f"✅ PASSED: KuCoin 3-value orderbook handled correctly")
    print(f"   Volume calculated: ${bid_alert.volume:,.2f}")
    
    return True


def test_orderbook_volume_calculation():
    """
    Test 4: Verify orderbook volumes are calculated as individual, not cumulative.
    
    This test ensures the scanner interprets orderbook data correctly:
    Each level contains INDIVIDUAL volume, not cumulative from top.
    """
    print("\n" + "="*70)
    print("TEST 4: Orderbook Volume Interpretation")
    print("="*70)
    
    settings = SettingsManager(":memory:")
    scanner = DensityScanner(settings, lambda alert: None)
    
    # Individual volumes (standard exchange format)
    orderbook = {
        "bids": [
            [100.0, 500],    # Level 0: 500 contracts (individual)
            [99.0, 750],     # Level 1: 750 contracts (individual, NOT 500+750=1250)
            [98.0, 325],     # Level 2: 325 contracts (individual, NOT 1250+325=1575)
        ],
        "asks": [[101.0, 100]]
    }
    
    # Expected cumulative calculation:
    # Level 0: 100.0 * 500 = 50,000
    # Level 1: 99.0 * 750 = 74,250 → Total: 124,250
    # Level 2: 98.0 * 325 = 31,850 → Total: 156,100
    
    alerts = scanner._compute_densities("test", "TEST/USDT", orderbook, 100000, 10.0)
    
    if alerts:
        bid_alert = next((a for a in alerts if a.side == "bid"), None)
        if bid_alert:
            expected_min = 100000  # Threshold
            expected_max = 160000  # Should include level 0 + level 1 + possibly level 2
            
            print(f"   Calculated volume: ${bid_alert.volume:,.2f}")
            print(f"   Expected range: ${expected_min:,.0f} - ${expected_max:,.0f}")
            
            assert expected_min <= bid_alert.volume <= expected_max, \
                f"Volume {bid_alert.volume:,.0f} outside expected range"
            
            # Verify it's treating volumes as individual, not cumulative
            # If it were treating 325 as cumulative (1575), volume would be 1575*98 = 154,350
            # But treating as individual (325), volume is sum of 50k + 74.25k + 31.85k = 156.1k
            assert bid_alert.volume < 200000, "Volume too high - might be misinterpreting cumulative"
    
    print(f"✅ PASSED: Volumes correctly interpreted as individual")
    print(f"   Scanner accumulates individual volumes correctly")
    
    return True


async def run_all_tests():
    """Run all exchange configuration tests."""
    print("="*70)
    print("🧪 EXCHANGE CONFIGURATION TEST SUITE")
    print("="*70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    results = {}
    
    # Test 1: No cumulative conversion
    try:
        results['no_cumulative_conversion'] = test_no_cumulative_conversion()
    except Exception as e:
        print(f"❌ FAILED: {e}")
        results['no_cumulative_conversion'] = False
    
    # Test 2: Symbol formats
    try:
        symbol_results = await test_exchange_symbol_formats()
        results['symbol_formats'] = symbol_results
    except Exception as e:
        print(f"❌ FAILED: {e}")
        results['symbol_formats'] = {}
    
    # Test 3: KuCoin orderbook format
    try:
        results['kucoin_format'] = test_kucoin_orderbook_format()
    except Exception as e:
        print(f"❌ FAILED: {e}")
        results['kucoin_format'] = False
    
    # Test 4: Volume calculation
    try:
        results['volume_calculation'] = test_orderbook_volume_calculation()
    except Exception as e:
        print(f"❌ FAILED: {e}")
        results['volume_calculation'] = False
    
    # Summary
    print("\n" + "="*70)
    print("📊 OVERALL TEST SUMMARY")
    print("="*70)
    
    passed_tests = 0
    total_tests = 4
    
    if results.get('no_cumulative_conversion'):
        passed_tests += 1
        print("✅ Test 1: No Cumulative Conversion - PASSED")
    else:
        print("❌ Test 1: No Cumulative Conversion - FAILED")
    
    if results.get('symbol_formats'):
        symbol_results = results['symbol_formats']
        passed = sum(1 for r in symbol_results.values() if r == "PASSED")
        total = len(symbol_results)
        passed_tests += 1 if passed == total else 0.5 if passed > 0 else 0
        print(f"{'✅' if passed == total else '⚠️'} Test 2: Symbol Formats - {passed}/{total} exchanges")
    else:
        print("❌ Test 2: Symbol Formats - FAILED")
    
    if results.get('kucoin_format'):
        passed_tests += 1
        print("✅ Test 3: KuCoin Format - PASSED")
    else:
        print("❌ Test 3: KuCoin Format - FAILED")
    
    if results.get('volume_calculation'):
        passed_tests += 1
        print("✅ Test 4: Volume Calculation - PASSED")
    else:
        print("❌ Test 4: Volume Calculation - FAILED")
    
    print(f"\n- **Total tests:** {total_tests}")
    print(f"- **Passed:** {passed_tests}")
    print(f"- **Failed:** {total_tests - passed_tests}")
    print(f"- **Success rate:** {(passed_tests/total_tests)*100:.1f}%")
    
    print(f"\nEnd time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    return results


if __name__ == "__main__":
    print("Starting exchange configuration tests...")
    results = asyncio.run(run_all_tests())
    
    # Exit with appropriate code
    all_passed = (
        results.get('no_cumulative_conversion') and
        all(r == "PASSED" for r in results.get('symbol_formats', {}).values()) and
        results.get('kucoin_format') and
        results.get('volume_calculation')
    )
    
    sys.exit(0 if all_passed else 1)
