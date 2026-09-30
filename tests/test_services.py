from types import SimpleNamespace

from app.database import make_session_factory
from app.services import can_submit, create_question, seed_categories, upsert_user


def test_create_question_and_rate_limit():
    sessions = make_session_factory("sqlite:///:memory:")
    with sessions() as session:
        seed_categories(session)
        user = upsert_user(session, SimpleNamespace(id=1, username="ada", first_name="Ada", last_name=None), frozenset())
        question = create_question(session, user.id, "Why do people fear change?", "psychology", True)
        assert question.id and question.is_anonymous
        assert can_submit(session, user.id, 2)
