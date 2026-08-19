# apps/api/alembic/versions/003_verification_contact_phone.py — adds contact_phone to verification_documents
"""add contact_phone to verification_documents

Revision ID: 003_verification_contact_phone
Revises: 002_verification_kyc
Create Date: 2026-08-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003_verification_contact_phone"
down_revision: Union[str, None] = "002_verification_kyc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("verification_documents", sa.Column("contact_phone", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("verification_documents", "contact_phone")
