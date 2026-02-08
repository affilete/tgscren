"""
Telegram Bot with hierarchical inline menu (Russian).
Complete management through inline buttons.
"""

import logging
from functools import wraps
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)
from telegram.constants import ParseMode

from config import BOT_TOKEN, SUPPORTED_EXCHANGES, OWNER_USER_ID
from settings_manager import SettingsManager

logger = logging.getLogger(__name__)

# Conversation states
(
    AWAITING_GLOBAL_DIST,
    AWAITING_EXCHANGE_MIN,
    AWAITING_EXCHANGE_TICKER_INPUT,
    AWAITING_GLOBAL_BLACKLIST_ADD,
    AWAITING_EXCHANGE_BLACKLIST_ADD,
    AWAITING_EXCHANGE_LIFETIME,
    AWAITING_GLOBAL_TICKER_INPUT,
) = range(7)


def authorized_only(func):
    """Decorator to check user authorization - only OWNER_USER_ID can interact."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        # Get user_id from either message or callback query
        if update.callback_query:
            user_id = update.callback_query.from_user.id
        else:
            user_id = update.effective_user.id
        
        if user_id != OWNER_USER_ID:
            if update.callback_query:
                await update.callback_query.answer(
                    "⛔ Доступ запрещён",
                    show_alert=True
                )
            else:
                await update.message.reply_text("⛔ Доступ запрещён")
            return ConversationHandler.END
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper


# ===========================
# Keyboard Generator Functions
# ===========================

def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Generate cancel button keyboard for input states."""
    keyboard = [
        [InlineKeyboardButton("« Назад", callback_data="cancel_input")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_main_menu_keyboard(settings: SettingsManager) -> InlineKeyboardMarkup:
    """Generate main menu keyboard."""
    toggle_text = "🔕 Выключить алерты" if settings.alerts_enabled else "🔔 Включить алерты"
    
    keyboard = [
        [InlineKeyboardButton(toggle_text, callback_data="toggle_alerts")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="menu:settings")],
        [InlineKeyboardButton("📊 Текущие настройки", callback_data="show_current")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_settings_keyboard() -> InlineKeyboardMarkup:
    """Generate settings menu keyboard."""
    keyboard = [
        [InlineKeyboardButton("🌐 Глобальные настройки", callback_data="menu:global")],
        [InlineKeyboardButton("📊 По биржам", callback_data="menu:exchanges")],
        [InlineKeyboardButton("« Назад", callback_data="back:main")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_global_settings_keyboard() -> InlineKeyboardMarkup:
    """Generate global settings menu keyboard."""
    keyboard = [
        [InlineKeyboardButton("📏 Расстояние до плотности", callback_data="action:set_global_dist")],
        [InlineKeyboardButton("🏷 Индивидуальный размер", callback_data="menu:global_tickers")],
        [InlineKeyboardButton("🚫 Чёрный список", callback_data="menu:global_blacklist")],
        [InlineKeyboardButton("« Назад", callback_data="back:settings")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_exchanges_keyboard() -> InlineKeyboardMarkup:
    """Generate exchanges list keyboard."""
    keyboard = []
    for exch_key, exch_info in SUPPORTED_EXCHANGES.items():
        label = exch_info["label"]
        keyboard.append([InlineKeyboardButton(label, callback_data=f"menu:exchange:{exch_key}")])
    keyboard.append([InlineKeyboardButton("« Назад", callback_data="back:settings")])
    return InlineKeyboardMarkup(keyboard)


def get_exchange_settings_keyboard(exchange: str) -> InlineKeyboardMarkup:
    """Generate exchange-specific settings keyboard."""
    keyboard = [
        [InlineKeyboardButton("💰 Минимальный размер", callback_data=f"action:set_exch_min:{exchange}")],
        [InlineKeyboardButton("⏱ Фильтр время жизни", callback_data=f"action:set_exch_lifetime:{exchange}")],
        [InlineKeyboardButton("🏷 Индивидуальный размер", callback_data=f"menu:exch_tickers:{exchange}")],
        [InlineKeyboardButton("🚫 Чёрный список", callback_data=f"menu:exch_blacklist:{exchange}")],
        [InlineKeyboardButton("« Назад к биржам", callback_data="back:exchanges")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_delete_blacklist_keyboard(settings: SettingsManager) -> InlineKeyboardMarkup:
    """Generate keyboard with blacklist delete buttons."""
    keyboard = []
    blacklist = settings.global_blacklist
    
    for ticker in blacklist:
        keyboard.append([InlineKeyboardButton(f"🗑 {ticker}", callback_data=f"action:del_global_bl:{ticker}")])
    
    keyboard.append([InlineKeyboardButton("« Назад", callback_data="menu:global_blacklist")])
    return InlineKeyboardMarkup(keyboard)


def get_exchange_tickers_keyboard(exchange: str, settings: SettingsManager) -> InlineKeyboardMarkup:
    """Generate exchange ticker overrides menu keyboard."""
    keyboard = [
        [InlineKeyboardButton("➕ Добавить/изменить тикер", callback_data=f"action:add_exch_ticker:{exchange}")],
    ]
    
    # Show delete buttons only if there are ticker overrides
    ticker_overrides = settings.get_exchange_ticker_overrides(exchange)
    if ticker_overrides:
        keyboard.append([InlineKeyboardButton("🗑 Удалить тикер", callback_data=f"action:show_del_exch_ticker:{exchange}")])
    
    keyboard.append([InlineKeyboardButton("« Назад", callback_data=f"menu:exchange:{exchange}")])
    return InlineKeyboardMarkup(keyboard)


def get_delete_exchange_tickers_keyboard(exchange: str, settings: SettingsManager) -> InlineKeyboardMarkup:
    """Generate keyboard with exchange ticker delete buttons."""
    keyboard = []
    ticker_overrides = settings.get_exchange_ticker_overrides(exchange)
    
    for ticker in ticker_overrides.keys():
        keyboard.append([InlineKeyboardButton(f"🗑 {ticker}", callback_data=f"action:del_exch_ticker:{exchange}:{ticker}")])
    
    keyboard.append([InlineKeyboardButton("« Назад", callback_data=f"menu:exch_tickers:{exchange}")])
    return InlineKeyboardMarkup(keyboard)


def get_exchange_tickers_text(exchange: str, settings: SettingsManager) -> str:
    """Get exchange ticker overrides menu text."""
    exch_label = SUPPORTED_EXCHANGES.get(exchange, {}).get("label", exchange.upper())
    ticker_overrides = settings.get_exchange_ticker_overrides(exchange)
    
    text = f"🏷 Индивидуальный размер: {exch_label}\n\n"
    text += "Текущие настройки:\n"
    
    if ticker_overrides:
        for ticker, min_size in ticker_overrides.items():
            text += f"• {ticker}: {min_size:,.0f} USDT\n"
    else:
        text += "• Не установлено"
    
    return text


def get_exchange_blacklist_keyboard(exchange: str, settings: SettingsManager) -> InlineKeyboardMarkup:
    """Generate exchange blacklist menu keyboard."""
    keyboard = [
        [InlineKeyboardButton("➕ Добавить тикер", callback_data=f"action:add_exch_bl:{exchange}")],
    ]
    
    blacklist = settings.get_exchange_blacklist(exchange)
    if blacklist:
        keyboard.append([InlineKeyboardButton("🗑 Удалить тикер", callback_data=f"action:show_del_exch_bl:{exchange}")])
        keyboard.append([InlineKeyboardButton("🧹 Очистить список", callback_data=f"action:clear_exch_bl:{exchange}")])
    
    keyboard.append([InlineKeyboardButton("« Назад", callback_data=f"menu:exchange:{exchange}")])
    return InlineKeyboardMarkup(keyboard)


def get_delete_exchange_blacklist_keyboard(exchange: str, settings: SettingsManager) -> InlineKeyboardMarkup:
    """Generate keyboard with exchange blacklist delete buttons."""
    keyboard = []
    blacklist = settings.get_exchange_blacklist(exchange)
    
    for ticker in blacklist:
        keyboard.append([InlineKeyboardButton(f"🗑 {ticker}", callback_data=f"action:del_exch_bl:{exchange}:{ticker}")])
    
    keyboard.append([InlineKeyboardButton("« Назад", callback_data=f"menu:exch_blacklist:{exchange}")])
    return InlineKeyboardMarkup(keyboard)


def get_exchange_blacklist_text(exchange: str, settings: SettingsManager) -> str:
    """Get exchange blacklist menu text."""
    exch_label = SUPPORTED_EXCHANGES.get(exchange, {}).get("label", exchange.upper())
    blacklist = settings.get_exchange_blacklist(exchange)
    
    text = f"🚫 Чёрный список: {exch_label}\n\n"
    text += "Текущий список: "
    
    if blacklist:
        text += ", ".join(blacklist)
    else:
        text += "Пусто"
    
    return text


def get_global_blacklist_keyboard(settings: SettingsManager) -> InlineKeyboardMarkup:
    """Generate global blacklist menu keyboard."""
    keyboard = [
        [InlineKeyboardButton("➕ Добавить тикер", callback_data="action:add_global_bl")],
    ]
    
    blacklist = settings.global_blacklist
    if blacklist:
        keyboard.append([InlineKeyboardButton("🗑 Удалить тикер", callback_data="action:show_del_global_bl")])
        keyboard.append([InlineKeyboardButton("🧹 Очистить список", callback_data="action:clear_global_bl")])
    
    keyboard.append([InlineKeyboardButton("« Назад", callback_data="menu:global")])
    return InlineKeyboardMarkup(keyboard)


def get_global_blacklist_text(settings: SettingsManager) -> str:
    """Get global blacklist menu text."""
    blacklist = settings.global_blacklist
    
    text = "🚫 Глобальный чёрный список\n\n"
    text += "Текущий список: "
    
    if blacklist:
        text += ", ".join(blacklist)
    else:
        text += "Пусто"
    
    return text


def get_global_tickers_keyboard(settings: SettingsManager) -> InlineKeyboardMarkup:
    """Generate global ticker overrides menu keyboard."""
    keyboard = [
        [InlineKeyboardButton("➕ Добавить/изменить тикер", callback_data="action:add_global_ticker")],
    ]
    
    ticker_overrides = settings.global_ticker_overrides
    if ticker_overrides:
        keyboard.append([InlineKeyboardButton("🗑 Удалить тикер", callback_data="action:show_del_global_ticker")])
    
    keyboard.append([InlineKeyboardButton("« Назад", callback_data="menu:global")])
    return InlineKeyboardMarkup(keyboard)


def get_delete_global_tickers_keyboard(settings: SettingsManager) -> InlineKeyboardMarkup:
    """Generate keyboard with global ticker delete buttons."""
    keyboard = []
    ticker_overrides = settings.global_ticker_overrides
    
    for ticker in ticker_overrides.keys():
        keyboard.append([InlineKeyboardButton(f"🗑 {ticker}", callback_data=f"action:del_global_ticker:{ticker}")])
    
    keyboard.append([InlineKeyboardButton("« Назад", callback_data="menu:global_tickers")])
    return InlineKeyboardMarkup(keyboard)


def get_global_tickers_text(settings: SettingsManager) -> str:
    """Get global ticker overrides menu text."""
    ticker_overrides = settings.global_ticker_overrides
    
    text = "🏷 Глобальный индивидуальный размер\n\n"
    text += "Текущие настройки:\n"
    
    if ticker_overrides:
        for ticker, min_size in ticker_overrides.items():
            text += f"• {ticker}: {min_size:,.0f} USDT\n"
    else:
        text += "• Не установлено"
    
    return text


# ===========================
# Menu Display Functions
# ===========================

def get_main_menu_text(settings: SettingsManager) -> str:
    """Get main menu text."""
    alerts_status = "✅ Включены" if settings.alerts_enabled else "❌ Выключены"
    return f"🏠 Главное меню\n\nАлерты: {alerts_status}"


def get_settings_menu_text() -> str:
    """Get settings menu text."""
    return "⚙️ Настройки\n\nВыберите раздел:"


def get_global_settings_text(settings: SettingsManager) -> str:
    """Get global settings menu text."""
    global_dist = settings.global_distance
    global_blacklist = settings.global_blacklist
    global_tickers = settings.global_ticker_overrides
    
    text = "🌐 Глобальные настройки\n\n"
    text += f"📏 Расстояние до плотности: {global_dist:.2f}%\n\n"
    
    # Global ticker overrides
    text += "🏷 Индивидуальный размер:\n"
    if global_tickers:
        ticker_strs = [f"{t}={v:,.0f}" for t, v in global_tickers.items()]
        text += ", ".join(ticker_strs[:3])  # Show max 3
        if len(global_tickers) > 3:
            text += f" (+{len(global_tickers) - 3})"
    else:
        text += "Не установлено"
    
    text += "\n\n🚫 Чёрный список: "
    if global_blacklist:
        text += ", ".join(global_blacklist)
    else:
        text += "Пусто"
    
    return text


def get_exchanges_menu_text() -> str:
    """Get exchanges list menu text."""
    return "📊 Настройки по биржам\n\nВыберите биржу:"


def get_exchange_settings_text(exchange: str, settings: SettingsManager) -> str:
    """Get exchange-specific settings text."""
    # Get exchange label
    exch_label = SUPPORTED_EXCHANGES.get(exchange, {}).get("label", exchange.upper())
    
    # Get exchange-specific values
    min_val = settings.get_exchange_min_size(exchange)
    min_lifetime = settings.get_exchange_min_lifetime(exchange)
    ticker_overrides = settings.get_exchange_ticker_overrides(exchange)
    blacklist = settings.get_exchange_blacklist(exchange)
    
    text = f"📊 {exch_label}\n\n"
    text += f"💰 Мин. размер: {min_val:,.0f} USDT\n"
    text += f"⏱ Мин. время жизни: {min_lifetime} сек\n\n"
    
    # Ticker overrides
    text += "🏷 Индивидуальные тикеры:\n"
    if ticker_overrides:
        for ticker, min_size in ticker_overrides.items():
            text += f"• {ticker}: {min_size:,.0f} USDT\n"
    else:
        text += "• Не установлено\n"
    
    text += "\n"
    
    # Blacklist
    text += "🚫 Чёрный список: "
    if blacklist:
        text += ", ".join(blacklist)
    else:
        text += "Пусто"
    
    return text


# ===========================
# Helper Functions
# ===========================

async def _send_or_edit(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                        text: str, reply_markup=None, parse_mode=None):
    """Send or edit bot message. Delete user's text message if possible."""
    # Try to delete user's message
    if update.message:
        try:
            await update.message.delete()
        except Exception:
            pass
    
    chat_id = update.effective_chat.id
    bot_msg_id = context.user_data.get("last_bot_message_id")
    
    if bot_msg_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=bot_msg_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
            return
        except Exception:
            pass
    
    # Fallback: send new message
    kwargs = {"text": text, "reply_markup": reply_markup}
    if parse_mode:
        kwargs["parse_mode"] = parse_mode
    
    if update.message:
        sent = await update.message.reply_text(**kwargs)
    else:
        sent = await context.bot.send_message(chat_id=chat_id, **kwargs)
    
    context.user_data["last_bot_message_id"] = sent.message_id


# ===========================
# Command Handlers
# ===========================

@authorized_only
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /start and /menu commands."""
    settings = context.bot_data["settings"]
    
    text = get_main_menu_text(settings)
    keyboard = get_main_menu_keyboard(settings)
    
    await _send_or_edit(update, context, text, reply_markup=keyboard)
    return ConversationHandler.END


# ===========================
# Callback Query Handlers
# ===========================

@authorized_only
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle all callback queries."""
    query = update.callback_query
    await query.answer()
    
    settings = context.bot_data["settings"]
    data = query.data
    
    # Handle cancel_input (back button during input states)
    if data == "cancel_input":
        exchange = context.user_data.get("exchange")
        if exchange:
            text = get_exchange_settings_text(exchange, settings)
            keyboard = get_exchange_settings_keyboard(exchange)
        else:
            text = get_global_settings_text(settings)
            keyboard = get_global_settings_keyboard()
        await query.edit_message_text(text, reply_markup=keyboard)
        # Save message_id before clearing user data
        msg_id = query.message.message_id
        context.user_data.clear()
        context.user_data["last_bot_message_id"] = msg_id
        return ConversationHandler.END
    
    # Toggle alerts
    elif data == "toggle_alerts":
        settings.alerts_enabled = not settings.alerts_enabled
        text = get_main_menu_text(settings)
        keyboard = get_main_menu_keyboard(settings)
        await query.edit_message_text(text, reply_markup=keyboard)
        context.user_data["last_bot_message_id"] = query.message.message_id
        return ConversationHandler.END
    
    # Show current settings
    elif data == "show_current":
        text = settings.format_current_settings()
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data="back:main")]])
        await query.edit_message_text(text, reply_markup=keyboard)
        context.user_data["last_bot_message_id"] = query.message.message_id
        return ConversationHandler.END
    
    # Menu navigation
    elif data == "menu:settings":
        text = get_settings_menu_text()
        keyboard = get_settings_keyboard()
        await query.edit_message_text(text, reply_markup=keyboard)
        context.user_data["last_bot_message_id"] = query.message.message_id
        return ConversationHandler.END
    
    elif data == "menu:global":
        text = get_global_settings_text(settings)
        keyboard = get_global_settings_keyboard()
        await query.edit_message_text(text, reply_markup=keyboard)
        context.user_data["last_bot_message_id"] = query.message.message_id
        return ConversationHandler.END
    
    elif data == "menu:exchanges":
        text = get_exchanges_menu_text()
        keyboard = get_exchanges_keyboard()
        await query.edit_message_text(text, reply_markup=keyboard)
        context.user_data["last_bot_message_id"] = query.message.message_id
        return ConversationHandler.END
    
    elif data.startswith("menu:exchange:"):
        exchange = data.split(":")[-1]
        text = get_exchange_settings_text(exchange, settings)
        keyboard = get_exchange_settings_keyboard(exchange)
        await query.edit_message_text(text, reply_markup=keyboard)
        context.user_data["last_bot_message_id"] = query.message.message_id
        return ConversationHandler.END
    
    elif data.startswith("menu:exch_tickers:"):
        exchange = data.split(":")[-1]
        text = get_exchange_tickers_text(exchange, settings)
        keyboard = get_exchange_tickers_keyboard(exchange, settings)
        await query.edit_message_text(text, reply_markup=keyboard)
        context.user_data["last_bot_message_id"] = query.message.message_id
        return ConversationHandler.END
    
    elif data.startswith("menu:exch_blacklist:"):
        exchange = data.split(":")[-1]
        text = get_exchange_blacklist_text(exchange, settings)
        keyboard = get_exchange_blacklist_keyboard(exchange, settings)
        await query.edit_message_text(text, reply_markup=keyboard)
        context.user_data["last_bot_message_id"] = query.message.message_id
        return ConversationHandler.END
    
    elif data == "menu:global_blacklist":
        text = get_global_blacklist_text(settings)
        keyboard = get_global_blacklist_keyboard(settings)
        await query.edit_message_text(text, reply_markup=keyboard)
        context.user_data["last_bot_message_id"] = query.message.message_id
        return ConversationHandler.END
    
    elif data == "menu:global_tickers":
        text = get_global_tickers_text(settings)
        keyboard = get_global_tickers_keyboard(settings)
        await query.edit_message_text(text, reply_markup=keyboard)
        context.user_data["last_bot_message_id"] = query.message.message_id
        return ConversationHandler.END
    
    # Back navigation
    elif data == "back:main":
        text = get_main_menu_text(settings)
        keyboard = get_main_menu_keyboard(settings)
        await query.edit_message_text(text, reply_markup=keyboard)
        context.user_data["last_bot_message_id"] = query.message.message_id
        return ConversationHandler.END
    
    elif data == "back:settings":
        text = get_settings_menu_text()
        keyboard = get_settings_keyboard()
        await query.edit_message_text(text, reply_markup=keyboard)
        context.user_data["last_bot_message_id"] = query.message.message_id
        return ConversationHandler.END
    
    elif data == "back:exchanges":
        text = get_exchanges_menu_text()
        keyboard = get_exchanges_keyboard()
        await query.edit_message_text(text, reply_markup=keyboard)
        context.user_data["last_bot_message_id"] = query.message.message_id
        return ConversationHandler.END
    
    # Actions requiring input - handled by conversation handler
    elif data == "action:set_global_dist":
        context.user_data["awaiting_action"] = "global_dist"
        text = (
            f"📏 Введите расстояние (в %):\n\n"
            f"Текущее значение: {settings.global_distance:.2f}%"
        )
        await query.edit_message_text(text, reply_markup=get_cancel_keyboard())
        context.user_data["last_bot_message_id"] = query.message.message_id
        return AWAITING_GLOBAL_DIST
    
    elif data.startswith("action:set_exch_min:"):
        exchange = data.split(":")[-1]
        context.user_data["exchange"] = exchange
        exch_label = SUPPORTED_EXCHANGES.get(exchange, {}).get("label", exchange.upper())
        
        # Get current value
        current_val = settings.get_exchange_min_size(exchange)
        
        text = (
            f"💰 Введите минимальный размер для {exch_label} (в USDT):\n\n"
            f"Текущее значение: {current_val:,.0f} USDT"
        )
        await query.edit_message_text(text, reply_markup=get_cancel_keyboard())
        context.user_data["last_bot_message_id"] = query.message.message_id
        return AWAITING_EXCHANGE_MIN
    
    elif data.startswith("action:set_exch_lifetime:"):
        exchange = data.split(":")[-1]
        context.user_data["exchange"] = exchange
        exch_label = SUPPORTED_EXCHANGES.get(exchange, {}).get("label", exchange.upper())
        
        # Get current value
        current_val = settings.get_exchange_min_lifetime(exchange)
        
        text = (
            f"⏱ Введите минимальное время жизни для {exch_label} (в секундах):\n\n"
            f"Текущее значение: {current_val} сек\n\n"
            f"Плотности с временем жизни меньше указанного НЕ будут отправляться."
        )
        await query.edit_message_text(text, reply_markup=get_cancel_keyboard())
        context.user_data["last_bot_message_id"] = query.message.message_id
        return AWAITING_EXCHANGE_LIFETIME
    
    # Exchange ticker overrides
    elif data.startswith("action:add_exch_ticker:"):
        exchange = data.split(":")[-1]
        context.user_data["exchange"] = exchange
        exch_label = SUPPORTED_EXCHANGES.get(exchange, {}).get("label", exchange.upper())
        text = (
            f"➕ Добавить/изменить тикер для {exch_label}\n\n"
            "Введите тикер и min размер одной строкой:\n"
            "Формат: <code>BTC 50000000</code>\n\n"
            "Пример: BTC 50000000"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=get_cancel_keyboard())
        context.user_data["last_bot_message_id"] = query.message.message_id
        return AWAITING_EXCHANGE_TICKER_INPUT
    
    elif data.startswith("action:show_del_exch_ticker:"):
        exchange = data.split(":")[-1]
        text = "🗑 Удалить тикер\n\nВыберите тикер для удаления:"
        keyboard = get_delete_exchange_tickers_keyboard(exchange, settings)
        await query.edit_message_text(text, reply_markup=keyboard)
        context.user_data["last_bot_message_id"] = query.message.message_id
        return ConversationHandler.END
    
    elif data.startswith("action:del_exch_ticker:"):
        parts = data.split(":")
        exchange = parts[3]
        ticker = parts[4]
        settings.remove_exchange_ticker_override(exchange, ticker)
        
        exch_label = SUPPORTED_EXCHANGES.get(exchange, {}).get("label", exchange.upper())
        text = f"✅ Тикер {ticker} удалён из {exch_label}\n\n"
        text += get_exchange_tickers_text(exchange, settings)
        keyboard = get_exchange_tickers_keyboard(exchange, settings)
        await query.edit_message_text(text, reply_markup=keyboard)
        context.user_data["last_bot_message_id"] = query.message.message_id
        return ConversationHandler.END
    
    # Global blacklist
    elif data == "action:add_global_bl":
        text = (
            "➕ Добавить тикер в глобальный чёрный список\n\n"
            "Введите тикер (например: BTC):"
        )
        await query.edit_message_text(text, reply_markup=get_cancel_keyboard())
        context.user_data["last_bot_message_id"] = query.message.message_id
        return AWAITING_GLOBAL_BLACKLIST_ADD
    
    elif data == "action:show_del_global_bl":
        text = "🗑 Удалить тикер из глобального чёрного списка\n\nВыберите тикер для удаления:"
        keyboard = get_delete_blacklist_keyboard(settings)
        await query.edit_message_text(text, reply_markup=keyboard)
        context.user_data["last_bot_message_id"] = query.message.message_id
        return ConversationHandler.END
    
    elif data.startswith("action:del_global_bl:"):
        ticker = data.split(":")[-1]
        settings.remove_global_blacklist(ticker)
        
        text = f"✅ Тикер {ticker} удалён из глобального чёрного списка\n\n"
        text += get_global_blacklist_text(settings)
        keyboard = get_global_blacklist_keyboard(settings)
        await query.edit_message_text(text, reply_markup=keyboard)
        context.user_data["last_bot_message_id"] = query.message.message_id
        return ConversationHandler.END
    
    elif data == "action:clear_global_bl":
        settings.clear_global_blacklist()
        
        text = "✅ Глобальный чёрный список очищен\n\n"
        text += get_global_blacklist_text(settings)
        keyboard = get_global_blacklist_keyboard(settings)
        await query.edit_message_text(text, reply_markup=keyboard)
        context.user_data["last_bot_message_id"] = query.message.message_id
        return ConversationHandler.END
    
    # Global ticker overrides
    elif data == "action:add_global_ticker":
        text = (
            "➕ Добавить/изменить глобальный тикер\n\n"
            "Введите тикер и min размер одной строкой:\n"
            "Формат: <code>BTC 30000000</code>\n\n"
            "Пример: BTC 30000000"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=get_cancel_keyboard())
        context.user_data["last_bot_message_id"] = query.message.message_id
        return AWAITING_GLOBAL_TICKER_INPUT
    
    elif data == "action:show_del_global_ticker":
        text = "🗑 Удалить глобальный тикер\n\nВыберите тикер для удаления:"
        keyboard = get_delete_global_tickers_keyboard(settings)
        await query.edit_message_text(text, reply_markup=keyboard)
        context.user_data["last_bot_message_id"] = query.message.message_id
        return ConversationHandler.END
    
    elif data.startswith("action:del_global_ticker:"):
        ticker = data.split(":")[-1]
        settings.remove_global_ticker_override(ticker)
        
        text = f"✅ Глобальный тикер {ticker} удалён\n\n"
        text += get_global_tickers_text(settings)
        keyboard = get_global_tickers_keyboard(settings)
        await query.edit_message_text(text, reply_markup=keyboard)
        context.user_data["last_bot_message_id"] = query.message.message_id
        return ConversationHandler.END
    
    # Exchange blacklist
    elif data.startswith("action:add_exch_bl:"):
        exchange = data.split(":")[-1]
        context.user_data["exchange"] = exchange
        exch_label = SUPPORTED_EXCHANGES.get(exchange, {}).get("label", exchange.upper())
        text = (
            f"➕ Добавить тикер в чёрный список {exch_label}\n\n"
            "Введите тикер (например: BTC):"
        )
        await query.edit_message_text(text, reply_markup=get_cancel_keyboard())
        context.user_data["last_bot_message_id"] = query.message.message_id
        return AWAITING_EXCHANGE_BLACKLIST_ADD
    
    elif data.startswith("action:show_del_exch_bl:"):
        exchange = data.split(":")[-1]
        text = "🗑 Удалить тикер из чёрного списка\n\nВыберите тикер для удаления:"
        keyboard = get_delete_exchange_blacklist_keyboard(exchange, settings)
        await query.edit_message_text(text, reply_markup=keyboard)
        context.user_data["last_bot_message_id"] = query.message.message_id
        return ConversationHandler.END
    
    elif data.startswith("action:del_exch_bl:"):
        parts = data.split(":")
        exchange = parts[3]
        ticker = parts[4]
        settings.remove_exchange_blacklist(exchange, ticker)
        
        exch_label = SUPPORTED_EXCHANGES.get(exchange, {}).get("label", exchange.upper())
        text = f"✅ Тикер {ticker} удалён из чёрного списка {exch_label}\n\n"
        text += get_exchange_blacklist_text(exchange, settings)
        keyboard = get_exchange_blacklist_keyboard(exchange, settings)
        await query.edit_message_text(text, reply_markup=keyboard)
        context.user_data["last_bot_message_id"] = query.message.message_id
        return ConversationHandler.END
    
    elif data.startswith("action:clear_exch_bl:"):
        exchange = data.split(":")[-1]
        settings.clear_exchange_blacklist(exchange)
        
        exch_label = SUPPORTED_EXCHANGES.get(exchange, {}).get("label", exchange.upper())
        text = f"✅ Чёрный список {exch_label} очищен\n\n"
        text += get_exchange_blacklist_text(exchange, settings)
        keyboard = get_exchange_blacklist_keyboard(exchange, settings)
        await query.edit_message_text(text, reply_markup=keyboard)
        context.user_data["last_bot_message_id"] = query.message.message_id
        return ConversationHandler.END
    
    # Unknown callback - return to main menu
    logger.warning(f"Unknown callback data: {data}")
    return ConversationHandler.END


# ===========================
# Cancel Input Handler
# ===========================

@authorized_only
async def cancel_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle cancel button clicks during input states."""
    query = update.callback_query
    await query.answer()
    
    settings = context.bot_data["settings"]
    
    # Determine which menu to return to based on context
    exchange = context.user_data.get("exchange")
    
    if exchange:
        # Return to exchange settings menu
        text = get_exchange_settings_text(exchange, settings)
        keyboard = get_exchange_settings_keyboard(exchange)
    else:
        # Return to global settings menu
        text = get_global_settings_text(settings)
        keyboard = get_global_settings_keyboard()
    
    await query.edit_message_text(text, reply_markup=keyboard)
    
    # Save message_id before clearing user data
    msg_id = query.message.message_id
    context.user_data.clear()
    context.user_data["last_bot_message_id"] = msg_id
    
    return ConversationHandler.END


# ===========================
# Text Input Handlers
# ===========================

@authorized_only
async def handle_global_dist_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle global distance input."""
    settings = context.bot_data["settings"]
    
    try:
        value = float(update.message.text.replace(",", ".").replace(" ", ""))
        settings.global_distance = value
        
        text = f"✅ Глобальное расстояние установлено: {value:.2f}%\n\n"
        text += get_global_settings_text(settings)
        keyboard = get_global_settings_keyboard()
        
        await _send_or_edit(update, context, text, reply_markup=keyboard)
        return ConversationHandler.END
    except ValueError:
        text = (
            "❌ Ошибка: введите корректное число\n\n"
            f"Попробуйте ещё раз или используйте /menu для возврата в меню"
        )
        await _send_or_edit(update, context, text)
        return AWAITING_GLOBAL_DIST


@authorized_only
async def handle_exchange_min_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle exchange min size input."""
    settings = context.bot_data["settings"]
    exchange = context.user_data.get("exchange")
    
    if not exchange:
        text = "❌ Ошибка: биржа не указана. Используйте /menu"
        await _send_or_edit(update, context, text)
        return ConversationHandler.END
    
    try:
        value = int(update.message.text.replace(",", "").replace(" ", ""))
        settings.set_exchange_min_size(exchange, value)
        
        exch_label = SUPPORTED_EXCHANGES.get(exchange, {}).get("label", exchange.upper())
        text = f"✅ Min размер для {exch_label} установлен: {value:,.0f} USDT\n\n"
        text += get_exchange_settings_text(exchange, settings)
        keyboard = get_exchange_settings_keyboard(exchange)
        
        await _send_or_edit(update, context, text, reply_markup=keyboard)
        return ConversationHandler.END
    except ValueError:
        text = (
            "❌ Ошибка: введите корректное число\n\n"
            f"Попробуйте ещё раз или используйте /menu для возврата в меню"
        )
        await _send_or_edit(update, context, text)
        return AWAITING_EXCHANGE_MIN


@authorized_only
async def handle_exchange_lifetime_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle exchange min lifetime input."""
    settings = context.bot_data["settings"]
    exchange = context.user_data.get("exchange")
    
    if not exchange:
        text = "❌ Ошибка: биржа не указана. Используйте /menu"
        await _send_or_edit(update, context, text)
        return ConversationHandler.END
    
    try:
        value = int(update.message.text.replace(",", "").replace(" ", ""))
        settings.set_exchange_min_lifetime(exchange, value)
        
        exch_label = SUPPORTED_EXCHANGES.get(exchange, {}).get("label", exchange.upper())
        text = f"✅ Min время жизни для {exch_label} установлено: {value} сек\n\n"
        text += get_exchange_settings_text(exchange, settings)
        keyboard = get_exchange_settings_keyboard(exchange)
        
        await _send_or_edit(update, context, text, reply_markup=keyboard)
        return ConversationHandler.END
    except ValueError:
        text = (
            "❌ Ошибка: введите корректное число\n\n"
            f"Попробуйте ещё раз или используйте /menu для возврата в меню"
        )
        await _send_or_edit(update, context, text)
        return AWAITING_EXCHANGE_LIFETIME


@authorized_only
async def handle_exchange_ticker_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle exchange ticker override input."""
    settings = context.bot_data["settings"]
    exchange = context.user_data.get("exchange")
    
    if not exchange:
        text = "❌ Ошибка: биржа не указана. Используйте /menu"
        await _send_or_edit(update, context, text)
        return ConversationHandler.END
    
    try:
        parts = update.message.text.strip().upper().split()
        
        if len(parts) != 2:
            raise ValueError("Invalid format")
        
        ticker = parts[0]
        min_size = int(parts[1].replace(",", ""))
        
        settings.set_exchange_ticker_override(exchange, ticker, min_size)
        
        exch_label = SUPPORTED_EXCHANGES.get(exchange, {}).get("label", exchange.upper())
        text = f"✅ Тикер {ticker} установлен для {exch_label}: min = {min_size:,.0f} USDT\n\n"
        text += get_exchange_tickers_text(exchange, settings)
        keyboard = get_exchange_tickers_keyboard(exchange, settings)
        
        await _send_or_edit(update, context, text, reply_markup=keyboard)
        return ConversationHandler.END
    except (ValueError, IndexError):
        text = (
            "❌ Ошибка: неверный формат\n\n"
            "Используйте формат: <code>BTC 50000000</code>\n\n"
            "Попробуйте ещё раз или используйте /menu для возврата в меню"
        )
        await _send_or_edit(update, context, text, parse_mode=ParseMode.HTML)
        return AWAITING_EXCHANGE_TICKER_INPUT


@authorized_only
async def handle_global_blacklist_add_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle global blacklist add input."""
    settings = context.bot_data["settings"]
    
    ticker = update.message.text.strip().upper()
    
    if not ticker:
        text = (
            "❌ Ошибка: введите корректный тикер\n\n"
            "Попробуйте ещё раз или используйте /menu для возврата в меню"
        )
        await _send_or_edit(update, context, text)
        return AWAITING_GLOBAL_BLACKLIST_ADD
    
    settings.add_global_blacklist(ticker)
    
    text = f"✅ Тикер {ticker} добавлен в глобальный чёрный список\n\n"
    text += get_global_blacklist_text(settings)
    keyboard = get_global_blacklist_keyboard(settings)
    
    await _send_or_edit(update, context, text, reply_markup=keyboard)
    return ConversationHandler.END


@authorized_only
async def handle_global_ticker_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle global ticker override input."""
    settings = context.bot_data["settings"]
    
    try:
        parts = update.message.text.strip().upper().split()
        
        if len(parts) != 2:
            raise ValueError("Invalid format")
        
        ticker = parts[0]
        min_size = int(parts[1].replace(",", ""))
        
        settings.set_global_ticker_override(ticker, min_size)
        
        text = f"✅ Глобальный тикер {ticker} установлен: min = {min_size:,.0f} USDT\n\n"
        text += get_global_tickers_text(settings)
        keyboard = get_global_tickers_keyboard(settings)
        
        await _send_or_edit(update, context, text, reply_markup=keyboard)
        return ConversationHandler.END
    except (ValueError, IndexError):
        text = (
            "❌ Ошибка: неверный формат\n\n"
            "Используйте формат: <code>BTC 30000000</code>\n\n"
            "Попробуйте ещё раз или используйте /menu для возврата в меню"
        )
        await _send_or_edit(update, context, text, parse_mode=ParseMode.HTML)
        return AWAITING_GLOBAL_TICKER_INPUT


@authorized_only
async def handle_exchange_blacklist_add_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle exchange blacklist add input."""
    settings = context.bot_data["settings"]
    exchange = context.user_data.get("exchange")
    
    if not exchange:
        text = "❌ Ошибка: биржа не указана. Используйте /menu"
        await _send_or_edit(update, context, text)
        return ConversationHandler.END
    
    ticker = update.message.text.strip().upper()
    
    if not ticker:
        text = (
            "❌ Ошибка: введите корректный тикер\n\n"
            "Попробуйте ещё раз или используйте /menu для возврата в меню"
        )
        await _send_or_edit(update, context, text)
        return AWAITING_EXCHANGE_BLACKLIST_ADD
    
    settings.add_exchange_blacklist(exchange, ticker)
    
    exch_label = SUPPORTED_EXCHANGES.get(exchange, {}).get("label", exchange.upper())
    text = f"✅ Тикер {ticker} добавлен в чёрный список {exch_label}\n\n"
    text += get_exchange_blacklist_text(exchange, settings)
    keyboard = get_exchange_blacklist_keyboard(exchange, settings)
    
    await _send_or_edit(update, context, text, reply_markup=keyboard)
    return ConversationHandler.END


@authorized_only
async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the current conversation and return to main menu."""
    settings = context.bot_data["settings"]
    
    text = get_main_menu_text(settings)
    keyboard = get_main_menu_keyboard(settings)
    
    await _send_or_edit(update, context, text, reply_markup=keyboard)
    return ConversationHandler.END


# ===========================
# Build Application
# ===========================

def build_bot_app(settings: SettingsManager) -> Application:
    """Build and configure the Telegram bot application."""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Store settings in bot_data
    application.bot_data["settings"] = settings
    
    # Create conversation handler
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start_command),
            CommandHandler("menu", start_command),
            CallbackQueryHandler(callback_handler),
        ],
        states={
            AWAITING_GLOBAL_DIST: [
                CallbackQueryHandler(cancel_input_handler, pattern="^cancel_input$"),
                CallbackQueryHandler(callback_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_global_dist_input)
            ],
            AWAITING_EXCHANGE_MIN: [
                CallbackQueryHandler(cancel_input_handler, pattern="^cancel_input$"),
                CallbackQueryHandler(callback_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_exchange_min_input)
            ],
            AWAITING_EXCHANGE_LIFETIME: [
                CallbackQueryHandler(cancel_input_handler, pattern="^cancel_input$"),
                CallbackQueryHandler(callback_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_exchange_lifetime_input)
            ],
            AWAITING_EXCHANGE_TICKER_INPUT: [
                CallbackQueryHandler(cancel_input_handler, pattern="^cancel_input$"),
                CallbackQueryHandler(callback_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_exchange_ticker_input)
            ],
            AWAITING_GLOBAL_BLACKLIST_ADD: [
                CallbackQueryHandler(cancel_input_handler, pattern="^cancel_input$"),
                CallbackQueryHandler(callback_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_global_blacklist_add_input)
            ],
            AWAITING_GLOBAL_TICKER_INPUT: [
                CallbackQueryHandler(cancel_input_handler, pattern="^cancel_input$"),
                CallbackQueryHandler(callback_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_global_ticker_input)
            ],
            AWAITING_EXCHANGE_BLACKLIST_ADD: [
                CallbackQueryHandler(cancel_input_handler, pattern="^cancel_input$"),
                CallbackQueryHandler(callback_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_exchange_blacklist_add_input)
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_input_handler, pattern="^cancel_input$"),
            CallbackQueryHandler(callback_handler),
            CommandHandler("menu", cancel_conversation),
            CommandHandler("start", cancel_conversation),
        ],
        allow_reentry=True,
        per_message=False,
        per_chat=True,
        per_user=True,
        name="bot_conversation",
        persistent=False,
    )
    
    # Add handlers
    application.add_handler(conv_handler)
    
    # Log when bot is ready
    logger.info("Bot application built successfully")
    
    return application
