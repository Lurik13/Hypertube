"""password reset tokens

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-27
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", name="password_reset_tokens_user_id_fkey", ondelete="CASCADE"),
            nullable=False,
        ),
        # SHA-256 of the token sent by email: the raw token is never stored.
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        # Set when the link is used: a token works only once.
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("token_hash", name="password_reset_tokens_token_hash_key"),
    )
    op.create_index("password_reset_tokens_user_id_idx", "password_reset_tokens", ["user_id"])
    op.create_index("password_reset_tokens_expires_at_idx", "password_reset_tokens", ["expires_at"])


def downgrade() -> None:
    op.drop_table("password_reset_tokens")
