import logging

from app.bot import AskAnythingBot
from app.config import Settings


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    AskAnythingBot(Settings.from_env()).application().run_polling()


if __name__ == "__main__":
    main()
