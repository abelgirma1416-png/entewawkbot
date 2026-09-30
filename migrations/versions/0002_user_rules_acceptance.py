"""Store the time a user accepted the community rules."""

from alembic import op
import sqlalchemy as sa

revision = "0002_user_rules_acceptance"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("rules_accepted_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "rules_accepted_at")
