"""
Main entry point for the Cryptocurrency Density Scanner.
Runs the Telegram bot and scanner concurrently in a single async event loop.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from settings_manager import SettingsManager
from scanner import DensityScanner, DensityAlert
from bot import build_bot_app


def setup_logging():
    """Configure logging to console and file."""
    logger = logging.getLogger()
    if logger.handlers:
        return logger  # Already configured

    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logger.setLevel(logging.INFO)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler("scanner.log")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(file_handler)

    return logger


logger = setup_logging()


async def async_main():
    """Async main entry point."""
    parser = argparse.ArgumentParser(description="Cryptocurrency Density Scanner Bot")
    parser.add_argument("--chat_id", type=str, help="Telegram chat ID for alerts")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Starting Cryptocurrency Density Scanner")
    logger.info("=" * 60)

    settings = SettingsManager("settings.json")
    logger.info("Settings loaded")

    if args.chat_id:
        settings.chat_id = args.chat_id
        logger.info(f"Chat ID set from CLI: {args.chat_id}")

    bot_app = build_bot_app(settings)
    logger.info("Telegram bot initialized")

    alert_queue = asyncio.Queue()

    def alert_callback(alert: DensityAlert):
        alert_queue.put_nowait(alert)

    async def process_alerts():
        while True:
            alert = await alert_queue.get()
            try:
                message = alert.format_message()
                await bot_app.bot.send_message(
                    chat_id=settings.chat_id,
                    text=message,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                logger.debug(f"Alert sent: {alert.symbol}")
            except Exception as e:
                logger.error(f"Error sending alert: {e}")

    scanner = DensityScanner(settings, alert_callback)

    async with bot_app:
        await bot_app.start()
        await bot_app.updater.start_polling(
            allowed_updates=["message", "callback_query"]
        )
        logger.info("Bot is ready! Use /start to begin")

        scanner_task = asyncio.create_task(scanner.run())
        alert_task = asyncio.create_task(process_alerts())

        try:
            await scanner_task
        except asyncio.CancelledError:
            pass
        finally:
            logger.info("Shutting down...")
            scanner.stop()
            alert_task.cancel()
            try:
                await alert_task
            except asyncio.CancelledError:
                pass
            await bot_app.updater.stop()
            await bot_app.stop()
            await bot_app.shutdown()
            logger.info("Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, exiting")