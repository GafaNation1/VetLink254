# apps/api/alembic/versions/001_initial_migration.py — Creates users, clinics, bookings tables
"""initial tables

Revision ID: 001_initial_migration
Revises:
Create Date: 2026-08-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial_migration"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="farmer"),
        sa.Column("ussd_only_flag", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_phone", "users", ["phone"], unique=True)

    op.create_table(
        "clinics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("unique_code", sa.String(length=50), nullable=True),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("county", sa.String(length=100), nullable=True),
        sa.Column("sub_county", sa.String(length=100), nullable=True),
        sa.Column("ward", sa.String(length=100), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("services", sa.JSON(), nullable=True),
        sa.Column("verification_status", sa.String(length=30), nullable=False, server_default="pending_verification"),
        sa.Column("wallet_balance", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_clinics_id", "clinics", ["id"])
    op.create_index("ix_clinics_unique_code", "clinics", ["unique_code"], unique=True)

    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ref_code", sa.String(length=50), nullable=False),
        sa.Column("farmer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("clinic_id", sa.Integer(), sa.ForeignKey("clinics.id"), nullable=True),
        sa.Column("vet_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("service_category_id", sa.Integer(), nullable=True),
        sa.Column("animal_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="requested"),
        sa.Column("channel", sa.String(length=20), nullable=False, server_default="ussd"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_bookings_id", "bookings", ["id"])
    op.create_index("ix_bookings_ref_code", "bookings", ["ref_code"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_bookings_ref_code", table_name="bookings")
    op.drop_index("ix_bookings_id", table_name="bookings")
    op.drop_table("bookings")
    op.drop_index("ix_clinics_unique_code", table_name="clinics")
    op.drop_index("ix_clinics_id", table_name="clinics")
    op.drop_table("clinics")
    op.drop_index("ix_users_phone", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")