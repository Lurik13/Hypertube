"""oauth accounts

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-27
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Links a user to their identity at an OAuth provider (42 or Google).
    op.create_table(
        "oauth_accounts",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", name="oauth_accounts_user_id_fkey", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_user_id", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("provider IN ('42', 'google')", name="oauth_accounts_provider_check"),
        sa.UniqueConstraint("provider", "provider_user_id", name="oauth_accounts_provider_provider_user_id_key"),
        # Also serves as the index on user_id (leading column).
        sa.UniqueConstraint("user_id", "provider", name="oauth_accounts_user_id_provider_key"),
    )


def downgrade() -> None:
    op.drop_table("oauth_accounts")
