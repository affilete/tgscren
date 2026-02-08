# Migration Guide: Menu Restructuring

## Overview
This guide explains the changes made to restructure the bot's settings menu system. The main change is moving from a global settings model to a per-exchange settings model.

## Key Changes

### 1. Settings Structure
**Before:**
- Global `min_size` applied to all exchanges (float)
- Global `ticker_overrides` applied to all exchanges (float values)
- Optional per-exchange overrides for `min_size` and `distance_pct`
- Global `blacklist`

**After:**
- NO global `min_size` - each exchange has its own (int)
- NO global `ticker_overrides` - each exchange has its own (int values)
- Global `distance_pct` only (renamed to `global_distance_pct`, float)
- Global `blacklist` (renamed to `global_blacklist`)
- Per-exchange: `min_size` (int), `ticker_overrides` (dict[str, int]), `blacklist` (list)

**Note:** Min size values are now integers (whole USDT amounts) for simplicity and consistency.

### 2. Exchange Split
KuCoin has been split into two separate exchanges:
- `kucoin_futures` - KuCoin Futures (CCXT ID: `kucoinfutures`)
- `kucoin_spot` - KuCoin Spot (CCXT ID: `kucoin`)

### 3. Settings JSON Format

**Old Format:**
```json
{
  "min_size": 1000000,
  "distance_pct": 1.0,
  "blacklist": ["USDT"],
  "ticker_overrides": {
    "BTC": {"min_size": 50000000}
  },
  "exchange_settings": {
    "kucoin": {
      "min_size": 500000
    }
  }
}
```

**New Format:**
```json
{
  "global_distance_pct": 3.0,
  "global_blacklist": ["USDT", "USDC"],
  "exchanges": {
    "kucoin_futures": {
      "min_size": 300000,
      "ticker_overrides": {
        "BTC": 50000000,
        "ETH": 10000000
      },
      "blacklist": ["AVAX"]
    },
    "kucoin_spot": {
      "min_size": 500000,
      "ticker_overrides": {},
      "blacklist": []
    }
  }
}
```

### 4. API Changes

#### Removed Methods:
- `settings.global_min_size` (property)
- `settings.blacklist` → use `settings.global_blacklist`
- `settings.add_blacklist()` → use `settings.add_global_blacklist()`
- `settings.remove_blacklist()` → use `settings.remove_global_blacklist()`
- `settings.clear_blacklist()` → use `settings.clear_global_blacklist()`
- `settings.get_ticker_overrides()`
- `settings.set_ticker_override(ticker, min_size)`
- `settings.remove_ticker_override(ticker)`
- `settings.get_exchange_settings(exchange)`
- `settings.set_exchange_setting(exchange, key, value)`
- `settings.reset_exchange_settings(exchange)`
- `settings.resolve_distance(exchange)`

#### New Methods:
- `settings.get_exchange_min_size(exchange)` → int
- `settings.set_exchange_min_size(exchange, value)`
- `settings.get_exchange_ticker_overrides(exchange)` → dict
- `settings.set_exchange_ticker_override(exchange, ticker, min_size)`
- `settings.remove_exchange_ticker_override(exchange, ticker)`
- `settings.get_exchange_blacklist(exchange)` → list
- `settings.add_exchange_blacklist(exchange, ticker)`
- `settings.remove_exchange_blacklist(exchange, ticker)`
- `settings.clear_exchange_blacklist(exchange)`
- `settings.global_blacklist` (property) → list
- `settings.add_global_blacklist(ticker)`
- `settings.remove_global_blacklist(ticker)`
- `settings.clear_global_blacklist()`

#### Changed Methods:
- `settings.is_blacklisted(base_symbol)` → `settings.is_blacklisted(exchange, base_symbol)`
  - Now checks BOTH global and exchange-specific blacklists
- `settings.resolve_min_size(exchange, base_symbol)`
  - Now only checks exchange ticker_override, then exchange min_size
  - NO fallback to global (there is no global min_size)
- `settings.global_distance` - Still exists, uses `global_distance_pct` internally

## Migration Steps

### For Existing Users

1. **Backup your current settings.json**
2. **Create new settings.json** with the new structure:
   ```json
   {
     "alerts_enabled": true,
     "chat_id": "YOUR_CHAT_ID",
     "global_distance_pct": 3.0,
     "global_blacklist": [],
     "scan_interval": 30,
     "orderbook_depth": 50,
     "exchanges": {
       "kucoin_futures": {"min_size": 300000, "ticker_overrides": {}, "blacklist": []},
       "kucoin_spot": {"min_size": 500000, "ticker_overrides": {}, "blacklist": []},
       "hyperliquid": {"min_size": 1000000, "ticker_overrides": {}, "blacklist": []},
       "asterdex": {"min_size": 200000, "ticker_overrides": {}, "blacklist": []},
       "lither": {"min_size": 200000, "ticker_overrides": {}, "blacklist": []},
       "bingx": {"min_size": 500000, "ticker_overrides": {}, "blacklist": []}
     },
     "authorized_users": [],
     "quote_currencies": ["USDT", "USD", "USDC", "BUSD"]
   }
   ```
3. **Migrate your settings**:
   - Copy `distance_pct` → `global_distance_pct`
   - Copy `blacklist` → `global_blacklist`
   - For each exchange you used:
     - Set `min_size` from old `exchange_settings` or use default
     - Move ticker overrides to exchange-specific `ticker_overrides`
   - If you had `kucoin` configured, decide settings for both `kucoin_futures` and `kucoin_spot`

### For Developers

If you have custom code using the settings manager:

1. **Update blacklist calls:**
   ```python
   # Old:
   if settings.is_blacklisted(symbol):
   
   # New:
   if settings.is_blacklisted(exchange, symbol):
   ```

2. **Update min_size resolution:**
   ```python
   # Old:
   min_size = settings.resolve_min_size(exchange, symbol)
   distance = settings.resolve_distance(exchange)
   
   # New:
   min_size = settings.resolve_min_size(exchange, symbol)
   distance = settings.global_distance
   ```

3. **Update exchange IDs:**
   ```python
   # Old:
   if exchange == "kucoin":
   
   # New:
   if exchange in ["kucoin_futures", "kucoin_spot"]:
   ```

## Menu Structure

### New Menu Hierarchy

```
/start → Главное меню
├── [🔔/🔕 Вкл/Выкл алерты]
├── [⚙️ Настройки]
│   ├── [🌐 Глобальные настройки]
│   │   ├── [📏 Расстояние до плотности] → input percentage
│   │   └── [🚫 Чёрный список] → add/remove tickers
│   ├── [📊 По биржам]
│   │   └── [Exchange Name]
│   │       ├── [💰 Минимальный размер] → input USDT amount
│   │       ├── [🏷 Индивидуальный размер] → add/remove ticker overrides
│   │       └── [🚫 Чёрный список] → add/remove exchange-specific blacklist
│   └── [« Назад]
└── [📊 Текущие настройки] → view all settings
```

## Supported Exchanges

The bot now supports 6 exchanges:
1. **KuCoin Futures** (`kucoin_futures`) - CCXT: `kucoinfutures`
2. **KuCoin Spot** (`kucoin_spot`) - CCXT: `kucoin`
3. **HL (Hyperliquid)** (`hyperliquid`) - CCXT: `hyperliquid`
4. **AsterDEX** (`asterdex`) - CCXT: `asterdex`
5. **Lither** (`lither`) - CCXT: `lither`
6. **BingX** (`bingx`) - CCXT: `bingx`

Each exchange has completely independent settings.

## Benefits of New Structure

1. **Clearer separation** - Each exchange has its own complete configuration
2. **More flexible** - Different settings per exchange without complex overrides
3. **Better UX** - Settings are organized by exchange, easier to understand
4. **Simpler logic** - No complex fallback hierarchy for min_size
5. **Future-proof** - Easy to add new per-exchange settings

## Troubleshooting

### Bot won't start after update
- Check that your `settings.json` follows the new format
- Ensure all 6 exchanges are defined in the `exchanges` object
- Verify `global_distance_pct` and `global_blacklist` are present

### Settings not persisting
- Check file permissions on `settings.json`
- Verify the JSON is valid (use a JSON validator)

### Exchange not working
- Check that exchange ID matches the new naming (e.g., `kucoin_futures` not `kucoin`)
- Verify the exchange is defined in `config.py` SUPPORTED_EXCHANGES

## Questions?

If you encounter any issues during migration, please check:
1. Your `settings.json` format matches the new structure
2. All required fields are present
3. Exchange IDs are correct (especially for KuCoin split)
