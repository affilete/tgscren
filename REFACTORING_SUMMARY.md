# Refactoring Summary: Inline Keyboard Bot Interface

## Overview
Complete refactoring of the Telegram bot to use inline keyboard buttons instead of text commands, with full Russian language interface.

## Changes Made

### 1. Config Changes (`config.py`)
- **Added**: `EXCHANGE_DEPTH_LIMITS` dictionary
  - Maps exchange names to their specific orderbook depth limits
  - KuCoin configured to use `limit=20` (only accepts 20 or 100)
  - Fixes the "fetchOrderBook() limit argument must be 20 or 100" error

### 2. Scanner Changes (`scanner.py`)
- **Fixed KuCoin depth limit bug**:
  - Now uses exchange-specific depth limits from `EXCHANGE_DEPTH_LIMITS`
  - Falls back to global `orderbook_depth` setting if no specific limit exists
  
- **Improved error logging**:
  - BingX "symbol not found" errors now logged at DEBUG level instead of ERROR
  - Reduces log noise for expected errors

### 3. Settings Manager Changes (`settings_manager.py`)
- **Added new methods**:
  - `reset_exchange_settings(exchange)`: Reset exchange to use global settings
  - `get_exchange_blacklist(exchange)`: Get exchange-specific blacklist
  - `add_exchange_blacklist(exchange, ticker)`: Add ticker to exchange blacklist
  - `remove_exchange_blacklist(exchange, ticker)`: Remove from exchange blacklist

### 4. Bot Complete Refactoring (`bot.py`)
Complete rewrite with the following features:

#### Menu Structure (All in Russian)
1. **Main Menu** (`/start`)
   - Shows alert status (🟢/🔴)
   - Toggle alerts button
   - Settings button
   - Show current settings button

2. **Settings Menu**
   - Global settings
   - Exchange settings
   - Individual tickers
   - Blacklist (global)

3. **Global Settings Menu**
   - Change min_size
   - Change distance
   - Shows current values

4. **Exchange Settings**
   - Select exchange from list
   - Set exchange-specific min_size (or use global)
   - Set exchange-specific distance (or use global)
   - Manage exchange-specific blacklist
   - Reset exchange to global settings

5. **Ticker Overrides Menu**
   - Add new ticker override
   - Edit existing ticker
   - Delete ticker override
   - Shows all current overrides

6. **Blacklist Menu**
   - Add ticker to global blacklist
   - Remove ticker from global blacklist
   - Show current blacklist

7. **Exchange Blacklist Menu**
   - Add ticker to exchange-specific blacklist
   - Remove from exchange blacklist
   - Show exchange blacklist

#### Technical Implementation
- **ConversationHandler**: Used for multi-step interactions (entering values)
- **13 conversation states**: Each input flow has dedicated states
- **Inline keyboards**: All navigation through InlineKeyboardButton
- **Immediate persistence**: All changes saved instantly to `settings.json`
- **Authorization**: Maintains existing user authorization system
- **Russian interface**: All messages, buttons, and prompts in Russian

#### Removed Features
- All text command handlers removed (except `/start`)
- No more `/set_global`, `/set_ticker`, `/add_blacklist`, etc.
- Old command-based interface completely replaced

#### Key Features
1. **Hierarchical settings display**:
   - Shows "глобальный ($X)" when exchange uses global settings
   - Shows actual value when exchange has override
   
2. **One-click toggles**:
   - Alert enable/disable from main menu
   - Immediate visual feedback

3. **Context-aware navigation**:
   - Back buttons return to appropriate parent menu
   - Breadcrumb-style navigation

4. **Input validation**:
   - Numeric validation for all numeric inputs
   - Clear error messages in Russian
   - Allows comma/space in numbers

5. **Settings hierarchy**:
   - Ticker-specific > Exchange-specific > Global
   - Displayed and applied correctly throughout

## Testing
Created `test_refactoring.py` to verify:
- ✅ SettingsManager all methods work correctly
- ✅ Hierarchical resolution works as expected
- ✅ Exchange settings and blacklists
- ✅ Ticker overrides
- ✅ Configuration changes (KuCoin depth limit)
- ✅ Bot keyboard generation

All tests passed successfully.

## Migration Notes

### For Users
- No manual migration needed
- Existing `settings.json` will work with new code
- All old settings preserved and accessible through new UI
- Just run `/start` to see new interface

### For Developers
- Old bot.py saved as bot_old.py (gitignored)
- All old functionality preserved but accessed through buttons
- Settings persistence unchanged
- Scanner continues to work with same settings structure

## Example Usage

### Setting up Hyperliquid to scan full orderbook
1. `/start` → Click "⚙️ Настройки"
2. Click "📊 Настройки бирж"
3. Click "Hyperliquid"
4. Click "📏 Изменить дистанцию"
5. Type: `100`
6. Done! Hyperliquid now scans 100% of orderbook

### Setting BTC minimum size to $50M
1. `/start` → Click "⚙️ Настройки"
2. Click "🏷 Индивидуальные тикеры"
3. Click "➕ Добавить тикер"
4. Type: `BTC`
5. Type: `50000000`
6. Done! BTC densities below $50M are now filtered

### Adding AVAX to blacklist
1. `/start` → Click "⚙️ Настройки"
2. Click "🚫 Чёрный список"
3. Click "➕ Добавить в ЧС"
4. Type: `AVAX`
5. Done! AVAX alerts disabled globally

## Files Changed
- `config.py`: Added EXCHANGE_DEPTH_LIMITS
- `scanner.py`: Fixed KuCoin bug, improved logging
- `settings_manager.py`: Added exchange blacklist methods
- `bot.py`: Complete refactoring (1089 insertions, 241 deletions)
- `.gitignore`: Added bot_old.py, test_refactoring.py

## Compatibility
- ✅ Backward compatible with existing settings.json
- ✅ Works with existing scanner.py
- ✅ Works with existing main.py
- ✅ All dependencies unchanged (requirements.txt)
