"""add active demo state

Revision ID: c4a113d762fe
Revises: 8d271b25c24f
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c4a113d762fe"
down_revision: Union[str, Sequence[str], None] = "8d271b25c24f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "demo_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("active_customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("active_preset", sa.String(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name="ck_demo_state_singleton"),
        sa.ForeignKeyConstraint(["active_customer_id"], ["customers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("demo_state")
