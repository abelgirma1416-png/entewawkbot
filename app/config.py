from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv


def _csv_ints(value: str) -> frozenset[int]:
    values: set[int] = set()
    for item in value.split(","):
        item = item.strip()
        if item:
            values.add(int(item))
    return frozenset(values)


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str
    channel_username: str
    channel_id: int | str
    discussion_group_id: int | None
    admin_ids: frozenset[int]
    database_url: str
    max_questions_per_hour: int

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        token = os.getenv("BOT_TOKEN", "").strip()
        username = os.getenv("CHANNEL_USERNAME", "").strip()
        raw_channel_id = os.getenv("CHANNEL_ID", "").strip()
        if not token:
            raise ValueError("BOT_TOKEN is required")
        if not username:
            raise ValueError("CHANNEL_USERNAME is required")
        # Public channels can use their @username. Private channels require -100... ID.
        channel_id: int | str = username
        if raw_channel_id:
            try:
                channel_id = int(raw_channel_id)
            except ValueError:
                raise ValueError("CHANNEL_ID must be a numeric Telegram chat ID") from None
        raw_discussion = os.getenv("DISCUSSION_GROUP_ID", "").strip()
        return cls(
            bot_token=token,
            channel_username=username,
            channel_id=channel_id,
            discussion_group_id=int(raw_discussion) if raw_discussion else None,
            admin_ids=_csv_ints(os.getenv("ADMIN_IDS", "")),
            database_url=os.getenv("DATABASE_URL", "sqlite:///ask_anything.db"),
            max_questions_per_hour=int(os.getenv("MAX_QUESTIONS_PER_HOUR", "5")),
        )
