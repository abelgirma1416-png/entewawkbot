from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import Category, Question, QuestionStatus, User

CATEGORIES = (
    ("Relationships", "relationships"), ("Psychology", "psychology"),
    ("Money & Business", "money-business"), ("Education", "education"),
    ("Technology", "technology"), ("Ethiopia", "ethiopia"),
    ("Religion", "religion"), ("Entertainment", "entertainment"),
    ("General Knowledge", "general-knowledge"), ("Philosophy", "philosophy"),
    ("Life", "life"), ("Other", "other"),
)


def seed_categories(session: Session) -> None:
    if session.scalar(select(func.count(Category.id))) == 0:
        session.add_all(Category(name=name, slug=slug) for name, slug in CATEGORIES)
        session.commit()


def upsert_user(session: Session, telegram_user, admin_ids: frozenset[int]) -> User:
    user = session.scalar(select(User).where(User.telegram_id == telegram_user.id))
    now = datetime.now(UTC).replace(tzinfo=None)
    if user is None:
        user = User(telegram_id=telegram_user.id, username=telegram_user.username,
                    first_name=telegram_user.first_name or "User", last_name=telegram_user.last_name,
                    is_admin=telegram_user.id in admin_ids, last_seen_at=now)
        session.add(user)
    else:
        user.username, user.first_name, user.last_name, user.last_seen_at = (
            telegram_user.username, telegram_user.first_name or "User", telegram_user.last_name, now)
        user.is_admin = user.is_admin or telegram_user.id in admin_ids
    session.commit()
    return user


def can_submit(session: Session, user_id: int, limit: int) -> bool:
    since = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1)
    count = session.scalar(select(func.count(Question.id)).where(
        Question.user_id == user_id, Question.created_at >= since)) or 0
    return count < limit


def accept_rules(session: Session, telegram_id: int) -> User | None:
    user = session.scalar(select(User).where(User.telegram_id == telegram_id))
    if user is not None:
        user.rules_accepted_at = datetime.now(UTC).replace(tzinfo=None)
        session.commit()
    return user


def create_question(session: Session, user_id: int, text: str, category_slug: str, anonymous: bool) -> Question:
    category = session.scalar(select(Category).where(Category.slug == category_slug, Category.is_active.is_(True)))
    if category is None:
        raise ValueError("Unknown category")
    question = Question(user_id=user_id, question_text=text, category_id=category.id, is_anonymous=anonymous)
    session.add(question)
    session.commit()
    session.refresh(question)
    return session.scalar(select(Question).options(joinedload(Question.user), joinedload(Question.category)).where(Question.id == question.id))


def get_question(session: Session, question_id: int) -> Question | None:
    return session.scalar(select(Question).options(joinedload(Question.user), joinedload(Question.category)).where(Question.id == question_id))


def list_user_questions(session: Session, user_id: int) -> list[Question]:
    return list(session.scalars(select(Question).options(joinedload(Question.category)).where(
        Question.user_id == user_id).order_by(Question.created_at.desc()).limit(10)))


def stats(session: Session) -> dict[str, int]:
    total_users = session.scalar(select(func.count(User.id))) or 0
    total_questions = session.scalar(select(func.count(Question.id))) or 0
    result = {"users": total_users, "questions": total_questions}
    for status in QuestionStatus:
        result[status.value.lower()] = session.scalar(select(func.count(Question.id)).where(Question.status == status)) or 0
    return result
