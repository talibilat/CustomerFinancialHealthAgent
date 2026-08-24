"""save repayment scenarios

Revision ID: b784ba9c975d
Revises: 8d271b25c24f
Create Date: 2026-08-24 03:56:00.551137

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b784ba9c975d'
down_revision: Union[str, Sequence[str], None] = '8d271b25c24f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("snapshot_outgoing_entries", sa.Column("entry_key", sa.String(), nullable=True))
    op.add_column("snapshot_outgoing_entries", sa.Column("section", sa.String(), nullable=True))
    op.execute(
        "UPDATE snapshot_outgoing_entries "
        "SET section = CASE "
        "WHEN outgoing_treatment = 'existing_credit_commitment' "
        "THEN 'repayment_commitment' ELSE 'outgoing' END"
    )
    op.alter_column("snapshot_outgoing_entries", "section", nullable=False)
    op.create_unique_constraint(
        "uq_snapshot_id_customer", "confirmed_snapshots", ["id", "customer_id"]
    )
    op.create_table(
        "repayment_scenarios",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("basis_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "selected_existing_commitment_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("proposed_repayment", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "protected_monthly_buffer", sa.Numeric(precision=12, scale=2), nullable=True
        ),
        sa.Column("basis_monthly_headroom", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("replaced_repayment", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("scenario_headroom", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("buffer_shortfall", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("result_code", sa.String(), nullable=False),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("calculation_policy_version", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("request_fingerprint", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("proposed_repayment > 0", name="ck_scenario_proposed_positive"),
        sa.CheckConstraint(
            "mode IN ('additional', 'change_existing')", name="ck_scenario_mode_supported"
        ),
        sa.CheckConstraint(
            "result_code IN ('not_enough_reported_headroom', "
            "'may_leave_limited_room', "
            "'appears_manageable_from_the_information_provided')",
            name="ck_scenario_result_supported",
        ),
        sa.CheckConstraint(
            "(mode = 'additional' AND selected_existing_commitment_id IS NULL "
            "AND replaced_repayment IS NULL) OR "
            "(mode = 'change_existing' AND selected_existing_commitment_id IS NOT NULL "
            "AND replaced_repayment IS NOT NULL)",
            name="ck_scenario_selected_commitment_matches_mode",
        ),
        sa.CheckConstraint(
            "protected_monthly_buffer >= 0", name="ck_scenario_buffer_non_negative"
        ),
        sa.CheckConstraint(
            "replaced_repayment >= 0", name="ck_scenario_replaced_non_negative"
        ),
        sa.CheckConstraint(
            "buffer_shortfall >= 0", name="ck_scenario_buffer_shortfall_non_negative"
        ),
        sa.ForeignKeyConstraint(
            ["basis_snapshot_id", "customer_id"],
            ["confirmed_snapshots.id", "confirmed_snapshots.customer_id"],
            name="fk_scenario_owned_basis",
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(
            ["selected_existing_commitment_id"], ["snapshot_outgoing_entries.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "customer_id", "idempotency_key", name="uq_scenario_customer_idempotency_key"
        ),
    )
    op.create_index(
        op.f("ix_repayment_scenarios_basis_snapshot_id"),
        "repayment_scenarios",
        ["basis_snapshot_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_repayment_scenarios_customer_id"),
        "repayment_scenarios",
        ["customer_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_repayment_scenarios_customer_id"), table_name="repayment_scenarios")
    op.drop_index(
        op.f("ix_repayment_scenarios_basis_snapshot_id"), table_name="repayment_scenarios"
    )
    op.drop_table("repayment_scenarios")
    op.drop_constraint("uq_snapshot_id_customer", "confirmed_snapshots", type_="unique")
    op.drop_column("snapshot_outgoing_entries", "section")
    op.drop_column("snapshot_outgoing_entries", "entry_key")
