"""users and sessions

Revision ID: 0001
Revises:
Create Date: 2026-11-27
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Shared helper: every table with an updated_at column attaches this trigger.
    op.execute(
        """
        CREATE FUNCTION set_updated_at() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$
        """
    )

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("username", sa.String(30), nullable=False),
        sa.Column("first_name", sa.String(50), nullable=False),
        sa.Column("last_name", sa.String(50), nullable=False),
        # argon2id hash; NULL for OAuth-only accounts that never set a password.
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # Case-insensitive uniqueness, also used by login and "forgot password" lookups.
    op.create_index("users_email_lower_key", "users", [sa.text("lower(email)")], unique=True)
    op.create_index("users_username_lower_key", "users", [sa.text("lower(username)")], unique=True)
    op.execute(
        "CREATE TRIGGER users_set_updated_at BEFORE UPDATE ON users "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", name="sessions_user_id_fkey", ondelete="CASCADE"),
            nullable=False,
        ),
        # SHA-256 of the cookie value: the raw token is never stored.
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("token_hash", name="sessions_token_hash_key"),
    )
    op.create_index("sessions_user_id_idx", "sessions", ["user_id"])
    op.create_index("sessions_expires_at_idx", "sessions", ["expires_at"])


def downgrade() -> None:
    op.drop_table("sessions")
    op.drop_table("users")
    op.execute("DROP FUNCTION set_updated_at()")
