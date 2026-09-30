"""Initial Ask Anything schema."""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("users", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, unique=True), sa.Column("username", sa.String(255)),
        sa.Column("first_name", sa.String(255), nullable=False), sa.Column("last_name", sa.String(255)),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_banned", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()), sa.Column("last_seen_at", sa.DateTime(), server_default=sa.func.now()))
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])
    op.create_table("categories", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(80), nullable=False, unique=True),
        sa.Column("slug", sa.String(80), nullable=False, unique=True), sa.Column("description", sa.String(255)), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()))
    op.create_index("ix_categories_slug", "categories", ["slug"])
    status = sa.Enum("PENDING", "APPROVED", "REJECTED", "PUBLISHED", "DELETED", name="questionstatus")
    op.create_table("questions", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False), sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=False), sa.Column("is_anonymous", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", status, nullable=False, server_default="PENDING"), sa.Column("rejection_reason", sa.Text()), sa.Column("channel_message_id", sa.Integer()), sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()), sa.Column("published_at", sa.DateTime()))
    op.create_index("ix_questions_user_id", "questions", ["user_id"]); op.create_index("ix_questions_category_id", "questions", ["category_id"]); op.create_index("ix_questions_status", "questions", ["status"])
    op.create_table("reports", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id"), nullable=False), sa.Column("reporter_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("reason", sa.Text(), nullable=False), sa.Column("status", sa.String(30), nullable=False, server_default="OPEN"), sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()))
    op.create_index("ix_reports_question_id", "reports", ["question_id"]); op.create_index("ix_reports_reporter_user_id", "reports", ["reporter_user_id"])


def downgrade() -> None:
    op.drop_table("reports"); op.drop_table("questions"); op.drop_table("categories"); op.drop_table("users")
