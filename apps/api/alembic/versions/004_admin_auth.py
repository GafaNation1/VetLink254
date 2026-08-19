# apps/api/alembic/versions/004_admin_auth.py — adds users.password_hash for minimal JWT admin auth
"""add password_hash to users for minimal admin auth

Revision ID: 004_admin_auth
Revises: 003_verification_contact_phone
Create Date: 2026-08-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004_admin_auth"
down_revision: Union[str, None] = "003_verification_contact_phone"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_hash")