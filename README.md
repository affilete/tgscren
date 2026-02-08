# Cryptocurrency Density Scanner 🚀

A real-time cryptocurrency order book density scanner with Telegram bot integration. This bot monitors multiple exchanges for high liquidity zones (densities) and sends instant alerts to help day traders and scalpers identify profitable trading opportunities.

## 🎯 What is Density Scanning?

Density scanning analyzes order books to detect **high liquidity zones** - areas where large orders accumulate. These zones often indicate:
- Strong support/resistance levels
- Potential price walls
- Institutional interest
- Key trading zones for scalping

The scanner monitors bid and ask sides of the order book, calculating cumulative volume within a specified distance from the current spread. When the volume exceeds your threshold, you get an instant alert.

## ✨ Features

- **Multi-Exchange Support**: Monitors Hyperliquid, KuCoin, BingX, and more
- **Real-Time Alerts**: Instant Telegram notifications when densities are detected
- **Hierarchical Settings**: Global → Exchange → Ticker-specific configuration
- **Smart Cooldown**: Prevents alert spam with 5-minute cooldowns per symbol/side
- **Blacklist Management**: Exclude specific tickers from scanning
- **Thread-Safe**: Concurrent scanning across exchanges with proper synchronization
- **Persistent Settings**: All configurations saved to JSON
- **Easy Configuration**: Manage all settings via Telegram bot commands
- **Public APIs Only**: No API keys required - uses public order book data

## 📋 Supported Exchanges

- **Hyperliquid** (`hyperliquid`)
- **KuCoin** (`kucoin`)
- **BingX** (`bingx`)
- **AsterDex** (`asterdex`) - if available in CCXT
- **Lither** (`lither`) - if available in CCXT

*Note: Exchanges not available in CCXT will be gracefully skipped with a warning.*

## 🔧 Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Setup

1. **Clone the repository:**
```bash
git clone https://github.com/memscalping-del/tgscren.git
cd tgscren
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Configure (Optional):**
   - The bot token is pre-configured
   - You can set your chat ID via command line or Telegram commands
   - Default settings will be created automatically on first run

## 🚀 Usage

### Basic Usage

Start the bot with default settings:
```bash
python main.py
```

### With Custom Chat ID

Specify your Telegram chat ID for alerts:
```bash
python main.py --chat_id -1001234567890
```

To find your chat ID:
1. Start the bot with `/start`
2. Your user ID will be shown
3. For group/channel IDs, forward a message from the group to @userinfobot

### Running in Production

#### Using nohup
```bash
nohup python main.py --chat_id YOUR_CHAT_ID > output.log 2>&1 &
```

#### Using systemd

Create `/etc/systemd/system/densityscanner.service`:
```ini
[Unit]
Description=Cryptocurrency Density Scanner
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/tgscren
ExecStart=/usr/bin/python3 main.py --chat_id YOUR_CHAT_ID
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable densityscanner
sudo systemctl start densityscanner
sudo systemctl status densityscanner
```

## 📱 Telegram Bot Commands

### Alert Control
- `/enable_alerts` - Enable density alerts
- `/disable_alerts` - Disable density alerts

### Settings Management
- `/show_settings` - Display all current settings
- `/set_global min_size [value]` - Set global minimum size (in quote currency)
  - Example: `/set_global min_size 500000`
- `/set_global distance [value]` - Set global distance percentage
  - Example: `/set_global distance 0.5`
- `/set_distance [value]` - Set global distance (shortcut)
- `/set_chat_id [id]` - Set alert chat ID

### Exchange-Specific Settings
- `/select_exchange` - Interactive menu for exchange-specific settings
  - Set custom min_size per exchange
  - Set custom distance per exchange

### Ticker Overrides
- `/set_ticker [TICKER] [min_size]` - Set ticker-specific minimum size
  - Example: `/set_ticker BTC 30000000`
  - Useful for high-volume pairs like BTC that need higher thresholds

### Blacklist
- `/add_blacklist [TICKER]` - Exclude a ticker from scanning
  - Example: `/add_blacklist AVAX`
- `/remove_blacklist [TICKER]` - Re-enable a blacklisted ticker
  - Example: `/remove_blacklist AVAX`

### Info
- `/start` - Welcome message and current settings
- `/help` - List all available commands

## ⚙️ Settings Hierarchy

The scanner uses a hierarchical settings resolution system:

**Priority (highest to lowest):**
1. **Ticker Override** - Specific settings for individual tickers (e.g., BTC)
2. **Exchange Setting** - Settings for a specific exchange (e.g., KuCoin)
3. **Global Setting** - Default fallback settings

### Example Configuration

```
Global min_size: $1,000,000
├── Exchange: KuCoin min_size: $500,000 (overrides global for KuCoin)
└── Ticker: BTC min_size: $30,000,000 (overrides all for BTC on any exchange)
```

This allows you to:
- Set conservative defaults globally
- Lower thresholds for smaller exchanges
- Raise thresholds for high-volume pairs

## 🔍 How Density Detection Works

### Algorithm

1. **Fetch Order Book**: Retrieves top N levels (default: 50) from the exchange
2. **Calculate Mid Price**: `(best_bid + best_ask) / 2`
3. **Set Distance Threshold**: `mid_price * (distance_pct / 100)`
4. **Analyze Each Side**:
   - Walk through bid/ask levels within the distance threshold
   - Accumulate quote currency volume: `Σ(price × amount)`
   - Calculate volume-weighted average price
5. **Trigger Alert**: When cumulative volume ≥ min_size threshold

### Example

```
Mid Price: $50,000
Distance: 1% = $500
Min Size: $1,000,000

Bid Analysis:
  $49,900 x 10 BTC = $499,000
  $49,800 x 15 BTC = $747,000
  $49,700 x 5 BTC  = $248,500
  Total: $1,494,500 ✅ ALERT!
  
Weighted Avg Price: $49,817.89
Distance from Mid: 0.36%
```

## 📊 Configuration Files

### settings.json

All settings are persisted to `settings.json`:
```json
{
  "alerts_enabled": false,
  "chat_id": "-1001234567890",
  "min_size": 1000000,
  "distance_pct": 1.0,
  "scan_interval": 30,
  "orderbook_depth": 50,
  "blacklist": ["SHIB", "DOGE"],
  "ticker_overrides": {
    "BTC": {
      "min_size": 30000000
    }
  },
  "exchange_settings": {
    "kucoin": {
      "min_size": 500000,
      "distance_pct": 0.8
    }
  },
  "authorized_users": [123456789],
  "quote_currencies": ["USDT", "USD", "USDC", "BUSD"]
}
```

### config.py

Constants and defaults (edit if needed):
- Bot token
- Default settings
- Rate limiting parameters
- Alert template

## 🛡️ Authorization

The bot supports user authorization:

- **First user** is automatically authorized on `/start`
- If `authorized_users` list is empty, all users are allowed
- To restrict access, users must be in the `authorized_users` list
- Unauthorized users will see their user ID when they try to interact

## 🐛 Troubleshooting

### Bot not responding
- Check that the bot token is valid
- Ensure your chat ID is correct
- Verify the bot has permission to send messages

### No alerts
- Check if alerts are enabled: `/show_settings`
- Verify your thresholds aren't too high for current market conditions
- Check scanner.log for errors

### Exchange errors
- Some exchanges may have rate limits
- The scanner automatically retries with exponential backoff
- Check `scanner.log` for detailed error messages

### Missing exchanges
- If an exchange is not available in CCXT, it will be skipped
- Check the logs for warnings about unavailable exchanges

### High CPU/Memory usage
- Reduce `orderbook_depth` (default: 50)
- Increase `scan_interval` (default: 30s)
- Add more tickers to blacklist

## 📝 Logging

Logs are written to:
- **Console**: Real-time output
- **scanner.log**: Persistent file for debugging

Log format includes timestamps, logger names, and log levels.

## 🔐 Security Notes

- **No API Keys Required**: Uses only public endpoints
- **No Trading Capabilities**: Read-only market data
- **Settings Encryption**: Consider encrypting settings.json if it contains sensitive chat IDs
- **Bot Token**: Keep the bot token secure; don't commit to public repos

## 📈 Performance Tips

1. **Start Conservative**: Begin with higher min_size thresholds
2. **Monitor Logs**: Watch for rate limit warnings
3. **Adjust Per Exchange**: Smaller exchanges may need lower thresholds
4. **Use Blacklist**: Exclude low-quality or manipulated pairs
5. **Ticker Overrides**: Set higher thresholds for major pairs like BTC/ETH

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

This project is provided as-is for educational and trading purposes.

## ⚠️ Disclaimer

**This software is for informational purposes only. Trading cryptocurrencies carries risk. Always do your own research and trade responsibly. The authors are not responsible for any financial losses.**

## 🆘 Support

For issues, questions, or feature requests:
- Open an issue on GitHub
- Check the logs in `scanner.log`
- Use `/help` command in the bot

---

**Happy Trading! 🚀📈**
