# Quick Start Guide

## Installation

```bash
# Clone the repository
git clone https://github.com/memscalping-del/tgscren.git
cd tgscren

# Install dependencies
pip install -r requirements.txt
```

## Basic Usage

```bash
# Start with default settings
python main.py

# Start with custom chat ID
python main.py --chat_id -1001234567890
```

## Essential Commands

Once the bot is running, use these commands in Telegram:

1. **First Time Setup:**
   ```
   /start              # Initialize and auto-authorize
   /set_chat_id -100X  # Set your chat/group ID
   /enable_alerts      # Turn on alerts
   ```

2. **Quick Configuration:**
   ```
   /set_global min_size 500000    # $500k minimum
   /set_global distance 0.5       # 0.5% from spread
   /add_blacklist SHIB            # Skip low-quality pairs
   ```

3. **Advanced Settings:**
   ```
   /set_ticker BTC 30000000       # BTC needs $30M
   /select_exchange               # Per-exchange settings
   ```

4. **Check Status:**
   ```
   /show_settings      # View all current settings
   /help               # Command reference
   ```

## Settings Hierarchy

The scanner applies settings in this order (first match wins):

1. **Ticker Override** - Specific to a token (e.g., BTC)
2. **Exchange Setting** - Specific to an exchange (e.g., KuCoin)  
3. **Global Setting** - Default for everything

**Example:**
```
Global min_size: $1,000,000
  ├─ KuCoin override: $500,000 (applies to all KuCoin pairs)
  └─ BTC override: $30,000,000 (applies to BTC on all exchanges)

Result:
  BTC/USDT on KuCoin:   $30,000,000  (ticker wins)
  ETH/USDT on KuCoin:   $500,000     (exchange wins)
  SOL/USDT on Binance:  $1,000,000   (global default)
```

## Alert Example

When a density is detected, you'll receive:

```
🚨 Density Alert 🚨

Exchange: KuCoin
Ticker: BTC/USDT
Side: 🟢 BID
Volume: $2,450,000.00
Price Level: $43,250.50000000
Distance: 0.42%
Time: 2024-02-07 14:45:23
```

## Common Issues

**Bot not starting?**
- Check Python 3.8+ is installed
- Verify dependencies: `pip install -r requirements.txt`

**No alerts?**
- Run `/show_settings` to check if alerts are enabled
- Verify your thresholds aren't too high
- Check `scanner.log` for errors

**Rate limit errors?**
- The scanner automatically retries
- Consider increasing `scan_interval` in settings

## Production Deployment

**Using systemd:**

1. Create service file `/etc/systemd/system/densityscanner.service`:
```ini
[Unit]
Description=Crypto Density Scanner
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/home/youruser/tgscren
ExecStart=/usr/bin/python3 main.py --chat_id YOUR_CHAT_ID
Restart=always

[Install]
WantedBy=multi-user.target
```

2. Enable and start:
```bash
sudo systemctl enable densityscanner
sudo systemctl start densityscanner
sudo systemctl status densityscanner
```

**Using screen/tmux:**
```bash
screen -S scanner
python main.py --chat_id YOUR_CHAT_ID
# Ctrl+A, D to detach
```

## Support

- Check the full README.md for detailed documentation
- Review `scanner.log` for debugging
- Use `/help` in Telegram for command reference
