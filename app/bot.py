from __future__ import annotations

import logging
from datetime import UTC, datetime
from html import escape

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden, TelegramError
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from app.config import Settings
from app.database import make_session_factory
from app.keyboards import anonymous_keyboard, category_keyboard, confirm_keyboard, join_keyboard, main_menu, moderation_keyboard, rules_keyboard
from app.models import QuestionStatus
from app.rules import rule_pages
from app.services import CATEGORIES, accept_rules, can_submit, create_question, get_question, list_user_questions, seed_categories, stats, upsert_user

logger = logging.getLogger(__name__)


class AskAnythingBot:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.sessions = make_session_factory(settings.database_url)
        with self.sessions() as session:
            seed_categories(session)

    def register(self, telegram_user):
        with self.sessions() as session:
            return upsert_user(session, telegram_user, self.settings.admin_ids)

    def is_admin(self, telegram_id: int) -> bool:
        return telegram_id in self.settings.admin_ids

    async def member(self, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
        try:
            chat_member = await context.bot.get_chat_member(self.settings.channel_id, user_id)
            status = getattr(chat_member.status, "value", chat_member.status)
            allowed = status in {"member", "administrator", "creator", "owner"} or (
                status == "restricted" and bool(getattr(chat_member, "is_member", False)))
            logger.info("membership user=%s status=%s allowed=%s", user_id, status, allowed)
            return allowed
        except (BadRequest, Forbidden) as exc:
            logger.warning("membership unavailable for channel %s: %s", self.settings.channel_id, exc)
            return False
        except TelegramError:
            logger.exception("Telegram error checking membership")
            return False

    async def show_menu(self, update: Update) -> None:
        text = "🏠 <b>Ask Anything</b>\n\nAsk, reflect, and join the discussion."
        if update.callback_query:
            await update.callback_query.message.edit_text(text, reply_markup=main_menu(), parse_mode=ParseMode.HTML)
        else:
            await update.effective_message.reply_text(text, reply_markup=main_menu(), parse_mode=ParseMode.HTML)

    async def show_join(self, update: Update) -> None:
        text = "👋 <b>Welcome to Ask Anything.</b>\n\nTo use this bot, first join our official Telegram channel."
        if update.callback_query:
            await update.callback_query.message.edit_text(text, reply_markup=join_keyboard(self.settings.channel_username), parse_mode=ParseMode.HTML)
        else:
            await update.effective_message.reply_text(text, reply_markup=join_keyboard(self.settings.channel_username), parse_mode=ParseMode.HTML)

    async def show_rules(self, update: Update) -> None:
        """Send the complete rules, then offer the one-time acceptance action."""
        message = update.callback_query.message if update.callback_query else update.effective_message
        for page in rule_pages():
            await message.reply_text(page)
        await message.reply_text("ህጎቹን ካነበቡ በኋላ ለመቀጠል ይስማሙ።", reply_markup=rules_keyboard())

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_user:
            return
        user = self.register(update.effective_user)
        if user.is_banned:
            await update.effective_message.reply_text("Your account cannot submit questions.")
        elif await self.member(user.telegram_id, context):
            if user.rules_accepted_at:
                await self.show_menu(update)
            else:
                await self.show_rules(update)
        else:
            await self.show_join(update)

    async def ask(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        if not await self.member(query.from_user.id, context):
            await self.show_join(update)
            return
        user = self.register(query.from_user)
        if not user.rules_accepted_at:
            await self.show_rules(update)
            return
        context.user_data.clear()
        context.user_data["state"] = "text"
        await query.message.reply_text("💬 Please write your question (5–1000 characters). Send /cancel to stop.")

    async def incoming_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_user or not update.message or not update.message.text:
            return
        user = self.register(update.effective_user)
        if user.is_banned:
            await update.message.reply_text("Your account cannot submit questions.")
            return
        if not user.rules_accepted_at:
            await self.show_rules(update)
            return
        if context.user_data.get("state") != "text":
            await update.message.reply_text("Use /start to open the menu.")
            return
        text = update.message.text.strip()
        if not 5 <= len(text) <= 1000:
            await update.message.reply_text("Please send a question between 5 and 1000 characters.")
            return
        if text.count("http://") + text.count("https://") > 2:
            await update.message.reply_text("Questions may contain at most two links.")
            return
        with self.sessions() as session:
            if not can_submit(session, user.id, self.settings.max_questions_per_hour):
                await update.message.reply_text("You have reached the submission limit. Please try again later.")
                return
        context.user_data["question_text"] = text
        context.user_data["state"] = "category"
        await update.message.reply_text("📚 Choose a category:", reply_markup=category_keyboard())

    async def submit(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        data = context.user_data
        if not all(key in data for key in ("question_text", "category", "anonymous")):
            await query.message.reply_text("Your draft expired. Please start again.")
            return
        user = self.register(query.from_user)
        with self.sessions() as session:
            question = create_question(session, user.id, data["question_text"], data["category"], data["anonymous"])
        context.user_data.clear()
        await query.message.reply_text("✅ Submitted for moderation. We will notify you after review.")
        await self.send_to_moderators(context, question)

    async def send_to_moderators(self, context: ContextTypes.DEFAULT_TYPE, question) -> None:
        if not self.settings.admin_ids:
            logger.error("Question %s pending but ADMIN_IDS is empty", question.id)
            return
        identity = "Hidden" if question.is_anonymous else f"@{question.user.username}" if question.user.username else question.user.first_name
        text = (f"🆕 <b>NEW QUESTION #{question.id}</b>\n\n<b>Question:</b>\n{escape(question.question_text)}\n\n"
                f"<b>Category:</b> {escape(question.category.name)}\n<b>User:</b> {escape(identity)}\n"
                f"<b>Anonymous:</b> {'Yes' if question.is_anonymous else 'No'}")
        for admin_id in self.settings.admin_ids:
            try:
                await context.bot.send_message(admin_id, text, parse_mode=ParseMode.HTML, reply_markup=moderation_keyboard(question.id))
            except TelegramError as exc:
                logger.warning("Could not notify admin %s for question %s: %s", admin_id, question.id, exc)

    async def moderate(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        if not self.is_admin(query.from_user.id):
            await query.message.reply_text("Not authorized.")
            return
        _, action, raw_id = query.data.split(":", 2)
        with self.sessions() as session:
            question = get_question(session, int(raw_id))
            if question is None or question.status != QuestionStatus.PENDING:
                await query.message.reply_text("This question is no longer pending.")
                return
            if action == "delete":
                question.status = QuestionStatus.DELETED
                session.commit()
                await query.message.edit_text(f"🗑 Question #{question.id} deleted.")
                return
            if action == "reject":
                question.status = QuestionStatus.REJECTED
                session.commit()
                await query.message.edit_text(f"❌ Question #{question.id} rejected.")
                await context.bot.send_message(question.user.telegram_id, "Your question was not approved.")
                return
            try:
                post = await context.bot.send_message(self.settings.channel_id, self.publish_text(question), parse_mode=ParseMode.HTML)
            except TelegramError as exc:
                logger.exception("Publishing question %s failed", question.id)
                await query.message.reply_text("Publishing failed. Check channel access and bot permissions.")
                return
            question.status = QuestionStatus.PUBLISHED
            question.channel_message_id = post.message_id
            question.published_at = datetime.now(UTC).replace(tzinfo=None)
            session.commit()
        await query.message.edit_text(f"✅ Question #{raw_id} published (channel message {post.message_id}).")
        await context.bot.send_message(question.user.telegram_id, "✅ Your question has been published!")

    @staticmethod
    def publish_text(question) -> str:
        author = "" if question.is_anonymous else f"\n\n👤 Asked by: @{escape(question.user.username)}" if question.user.username else ""
        tag = question.category.slug.replace("-", "")
        return f"🧠 <b>QUESTION OF THE DAY</b>\n\n❓ {escape(question.question_text)}\n\n💬 <b>What do you think?</b>\nShare your opinion in the comments.{author}\n\n#AskAnything #{tag}"

    async def callbacks(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query:
            return
        if query.data == "question:start":
            await self.ask(update, context); return
        if query.data == "join:check":
            await query.answer()
            if await self.member(query.from_user.id, context):
                user = self.register(query.from_user)
                if user.rules_accepted_at: await self.show_menu(update)
                else: await self.show_rules(update)
            else: await query.message.reply_text("Join the channel first, then try again.")
            return
        if query.data == "rules:accept":
            await query.answer()
            if not await self.member(query.from_user.id, context):
                await self.show_join(update)
                return
            with self.sessions() as session:
                accept_rules(session, query.from_user.id)
            logger.info("rules accepted user=%s", query.from_user.id)
            await query.message.reply_text("✅ ህጎቹን ተስማምተዋል። እንኳን ደህና መጡ!")
            await self.show_menu(update)
            return
        if query.data.startswith("moderate:"):
            await self.moderate(update, context); return
        if query.data == "submit":
            await self.submit(update, context); return
        await query.answer()
        if query.data.startswith("category:"):
            context.user_data["category"] = query.data.split(":", 1)[1]
            context.user_data["state"] = "anonymous"
            await query.message.reply_text("Do you want to publish anonymously?", reply_markup=anonymous_keyboard())
        elif query.data.startswith("anonymous:"):
            context.user_data["anonymous"] = query.data.endswith("yes")
            context.user_data["state"] = "confirm"
            await query.message.reply_text(f"<b>Your question:</b>\n{escape(context.user_data['question_text'])}\n\n<b>Publishing:</b> {'Anonymous' if context.user_data['anonymous'] else 'Public'}", parse_mode=ParseMode.HTML, reply_markup=confirm_keyboard())
        elif query.data == "cancel":
            context.user_data.clear(); await query.message.reply_text("Cancelled. Use /start when ready.")
        elif query.data == "my_questions": await self.my_questions(update, context)
        elif query.data == "categories": await query.message.reply_text("📚 " + ", ".join(name for name, _ in CATEGORIES))
        elif query.data == "today": await query.message.reply_text("🔥 Approved questions are published in the official channel.")
        elif query.data == "about": await query.message.reply_text("Ask Anything is a moderated community question platform.")
        elif query.data == "settings": await query.message.reply_text("⚙️ Settings are saved per account as the platform grows.")

    async def my_questions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        with self.sessions() as session:
            user = upsert_user(session, update.effective_user, self.settings.admin_ids)
            questions = list_user_questions(session, user.id)
        text = "👤 <b>Your Questions</b>\n\n" + ("\n\n".join(f"{q.id}. {escape(q.question_text[:100])}\nStatus: <b>{q.status.value.title()}</b>" for q in questions) if questions else "No questions yet.")
        await update.callback_query.message.reply_text(text, parse_mode=ParseMode.HTML)

    async def admin_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_user or not self.is_admin(update.effective_user.id):
            await update.effective_message.reply_text("Not authorized."); return
        with self.sessions() as session: data = stats(session)
        await update.effective_message.reply_text("📊 <b>Statistics</b>\n\n" + "\n".join(f"{k.title()}: {v}" for k, v in data.items()), parse_mode=ParseMode.HTML)

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        context.user_data.clear(); await update.effective_message.reply_text("Cancelled. Use /start when ready.")

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.effective_message.reply_text("Use /start to submit a question. Use /cancel to discard a draft.")

    async def error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.exception("Unhandled Telegram update error", exc_info=context.error)

    def application(self) -> Application:
        app = Application.builder().token(self.settings.bot_token).build()
        app.add_handler(CommandHandler("start", self.start)); app.add_handler(CommandHandler("help", self.help))
        app.add_handler(CommandHandler("cancel", self.cancel)); app.add_handler(CommandHandler("stats", self.admin_stats))
        app.add_handler(CommandHandler("admin_stats", self.admin_stats)); app.add_handler(CallbackQueryHandler(self.callbacks))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.incoming_text)); app.add_error_handler(self.error)
        return app
