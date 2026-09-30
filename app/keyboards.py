from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.services import CATEGORIES


def join_keyboard(username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("📢 JOIN CHANNEL", url=f"https://t.me/{username.lstrip('@')}")],
                                 [InlineKeyboardButton("✅ I JOINED", callback_data="join:check")]])


def rules_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("✅ ህጎቹን አንብቤ ተስማምቻለሁ", callback_data="rules:accept")]])


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Ask a Question", callback_data="question:start")],
        [InlineKeyboardButton("🔥 Today's Questions", callback_data="today")],
        [InlineKeyboardButton("📚 Categories", callback_data="categories")],
        [InlineKeyboardButton("👤 My Questions", callback_data="my_questions")],
        [InlineKeyboardButton("ℹ️ About", callback_data="about")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
    ])


def category_keyboard() -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(name, callback_data=f"category:{slug}")] for name, slug in CATEGORIES]
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
    return InlineKeyboardMarkup(buttons)


def anonymous_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("👤 Publish with my name", callback_data="anonymous:no")],
                                 [InlineKeyboardButton("🕶️ Anonymous", callback_data="anonymous:yes")],
                                 [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("✅ Submit", callback_data="submit")],
                                 [InlineKeyboardButton("✏️ Edit", callback_data="question:start")],
                                 [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])


def moderation_keyboard(question_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("✅ Approve & Publish", callback_data=f"moderate:approve:{question_id}")],
                                 [InlineKeyboardButton("❌ Reject", callback_data=f"moderate:reject:{question_id}")],
                                 [InlineKeyboardButton("🗑 Delete", callback_data=f"moderate:delete:{question_id}")]])
