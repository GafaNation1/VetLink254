# apps/api/alembic/versions/002_verification_kyc.py — Creates verification_documents table and clinic verification columns
"""verification KYC tables and columns

Revision ID: 002_verification_kyc
Revises: 001_initial_migration
Create Date: 2026-08-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_verification_kyc"
down_revision: Union[str, None] = "001_initial_migration"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "verification_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("clinic_id", sa.Integer(), sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column("doc_type", sa.String(length=50), nullable=False),
        sa.Column("file_url", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("reviewed_by", sa.String(length=100), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_verification_documents_id", "verification_documents", ["id"])
    op.create_index("ix_verification_documents_clinic_id", "verification_documents", ["clinic_id"])

    op.add_column("clinics", sa.Column("verifying_authority", sa.String(length=50), nullable=True))
    op.add_column("clinics", sa.Column("verification_note", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("clinics", "verification_note")
    op.drop_column("clinics", "verifying_authority")

    op.drop_index("ix_verification_documents_clinic_id", table_name="verification_documents")
    op.drop_index("ix_verification_documents_id", table_name="verification_documents")
    op.drop_table("verification_documents")