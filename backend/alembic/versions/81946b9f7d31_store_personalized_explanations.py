"""store personalized explanations

Revision ID: 81946b9f7d31
Revises: c4a113d762fe
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "81946b9f7d31"
down_revision: Union[str, Sequence[str], None] = "c4a113d762fe"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "personalized_explanations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("request_outcome", sa.String(), nullable=False),
        sa.Column("deployment", sa.String(), nullable=True),
        sa.Column("prompt_version", sa.String(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("request_fingerprint", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(
            ["snapshot_id", "customer_id"],
            ["confirmed_snapshots.id", "confirmed_snapshots.customer_id"],
            name="fk_guidance_owned_snapshot",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "customer_id", "idempotency_key", name="uq_guidance_customer_idempotency_key"
        ),
    )
    op.create_index(
        op.f("ix_personalized_explanations_customer_id"),
        "personalized_explanations",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_personalized_explanations_snapshot_id"),
        "personalized_explanations",
        ["snapshot_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_personalized_explanations_snapshot_id"),
        table_name="personalized_explanations",
    )
    op.drop_index(
        op.f("ix_personalized_explanations_customer_id"),
        table_name="personalized_explanations",
    )
    op.drop_table("personalized_explanations")
