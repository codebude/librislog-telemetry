"""add version to daily_activity

Revision ID: 9a5e8c7d4b21
Revises: 0563d6d01623
Create Date: 2026-09-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "9a5e8c7d4b21"
down_revision: Union[str, Sequence[str], None] = "0563d6d01623"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "daily_activity",
        sa.Column(
            "version",
            sqlmodel.sql.sqltypes.AutoString(length=32),
            nullable=False,
            server_default="",
        ),
    )
    op.create_index(
        op.f("ix_daily_activity_version"),
        "daily_activity",
        ["version"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_daily_activity_version"), table_name="daily_activity")
    op.drop_column("daily_activity", "version")
