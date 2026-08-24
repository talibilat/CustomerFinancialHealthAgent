import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

MONEY = Numeric(12, 2)


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DemoState(Base):
    """The active fictional aggregate, present only for the controlled demo."""

    __tablename__ = "demo_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    active_customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False
    )
    active_preset: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (CheckConstraint("id = 1", name="ck_demo_state_singleton"),)


class ConfirmedSnapshot(Base):
    __tablename__ = "confirmed_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True
    )
    statement_period: Mapped[date] = mapped_column(Date, nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    calculation_policy_version: Mapped[str] = mapped_column(String, nullable=False)
    normalized_monthly_income: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    normalized_monthly_outgoings: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    monthly_headroom: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    result_code: Mapped[str] = mapped_column(String, nullable=False)
    warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # A correction points at the snapshot it replaces. The unique constraint
    # below allows many NULLs but only one successor per snapshot, so a
    # supersession chain can never fork.
    supersedes_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("confirmed_snapshots.id"), nullable=True
    )
    correction_reason: Mapped[str | None] = mapped_column(String, nullable=True)

    # Optional resilience information. Missing entirely (all NULL) when the
    # customer did not provide it; current_account_balance may be negative
    # (an overdraft) so it carries no non-negative check constraint.
    current_account_balance: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    accessible_savings: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    protected_reserve: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    known_arrears: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    savings_above_reserve: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    reserve_gap: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    resilience_result_code: Mapped[str | None] = mapped_column(String, nullable=True)
    resilience_warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    income_entries: Mapped[list["SnapshotIncomeEntry"]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan", order_by="SnapshotIncomeEntry.sort_order"
    )
    outgoing_entries: Mapped[list["SnapshotOutgoingEntry"]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan", order_by="SnapshotOutgoingEntry.sort_order"
    )

    __table_args__ = (
        CheckConstraint("normalized_monthly_income >= 0", name="ck_snapshot_income_non_negative"),
        CheckConstraint("normalized_monthly_outgoings >= 0", name="ck_snapshot_outgoings_non_negative"),
        CheckConstraint("accessible_savings >= 0", name="ck_snapshot_accessible_savings_non_negative"),
        CheckConstraint("protected_reserve >= 0", name="ck_snapshot_protected_reserve_non_negative"),
        CheckConstraint("known_arrears >= 0", name="ck_snapshot_known_arrears_non_negative"),
        UniqueConstraint("supersedes_snapshot_id", name="uq_snapshot_single_successor"),
        UniqueConstraint("id", "customer_id", name="uq_snapshot_id_customer"),
    )


class RepaymentScenario(Base):
    """An explicitly saved comparison tied to one immutable basis snapshot."""

    __tablename__ = "repayment_scenarios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True
    )
    basis_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    mode: Mapped[str] = mapped_column(String, nullable=False)
    selected_existing_commitment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("snapshot_outgoing_entries.id"), nullable=True
    )
    proposed_repayment: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    protected_monthly_buffer: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    basis_monthly_headroom: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    replaced_repayment: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    scenario_headroom: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    buffer_shortfall: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    result_code: Mapped[str] = mapped_column(String, nullable=False)
    warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    calculation_policy_version: Mapped[str] = mapped_column(String, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("proposed_repayment > 0", name="ck_scenario_proposed_positive"),
        CheckConstraint(
            "mode IN ('additional', 'change_existing')", name="ck_scenario_mode_supported"
        ),
        CheckConstraint(
            "result_code IN ('not_enough_reported_headroom', "
            "'may_leave_limited_room', "
            "'appears_manageable_from_the_information_provided')",
            name="ck_scenario_result_supported",
        ),
        CheckConstraint(
            "(mode = 'additional' AND selected_existing_commitment_id IS NULL "
            "AND replaced_repayment IS NULL) OR "
            "(mode = 'change_existing' AND selected_existing_commitment_id IS NOT NULL "
            "AND replaced_repayment IS NOT NULL)",
            name="ck_scenario_selected_commitment_matches_mode",
        ),
        CheckConstraint(
            "protected_monthly_buffer >= 0", name="ck_scenario_buffer_non_negative"
        ),
        CheckConstraint(
            "replaced_repayment >= 0", name="ck_scenario_replaced_non_negative"
        ),
        CheckConstraint(
            "buffer_shortfall >= 0", name="ck_scenario_buffer_shortfall_non_negative"
        ),
        UniqueConstraint(
            "customer_id", "idempotency_key", name="uq_scenario_customer_idempotency_key"
        ),
        ForeignKeyConstraint(
            ["basis_snapshot_id", "customer_id"],
            ["confirmed_snapshots.id", "confirmed_snapshots.customer_id"],
            name="fk_scenario_owned_basis",
        ),
    )


class PersonalizedExplanation(Base):
    """Plain-text optional wording bound to one owned immutable snapshot."""

    __tablename__ = "personalized_explanations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    request_outcome: Mapped[str] = mapped_column(String, nullable=False)
    deployment: Mapped[str | None] = mapped_column(String, nullable=True)
    prompt_version: Mapped[str] = mapped_column(String, nullable=False)
    schema_version: Mapped[str] = mapped_column(String, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "customer_id", "idempotency_key", name="uq_guidance_customer_idempotency_key"
        ),
        ForeignKeyConstraint(
            ["snapshot_id", "customer_id"],
            ["confirmed_snapshots.id", "confirmed_snapshots.customer_id"],
            name="fk_guidance_owned_snapshot",
        ),
    )


class EditableFinancialStatement(Base):
    """The customer's current editable statement for one statement period.

    This is mutable working state, deliberately separate from the immutable
    confirmed snapshots. ``version`` advances on every save so a submission
    built from stale data can be refused instead of silently overwriting a
    newer edit.
    """

    __tablename__ = "editable_financial_statements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True
    )
    statement_period: Mapped[date] = mapped_column(Date, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="GBP")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Optional resilience information. current_account_balance may be negative
    # (an overdraft), so it carries no non-negative check constraint.
    current_account_balance: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    accessible_savings: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    protected_reserve: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    known_arrears: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)

    entries: Mapped[list["EditableStatementEntry"]] = relationship(
        back_populates="statement",
        cascade="all, delete-orphan",
        order_by="EditableStatementEntry.sort_order",
    )
    expected_changes: Mapped[list["EditableStatementExpectedChange"]] = relationship(
        back_populates="statement",
        cascade="all, delete-orphan",
        order_by="EditableStatementExpectedChange.sort_order",
    )

    __table_args__ = (
        UniqueConstraint("customer_id", "statement_period", name="uq_editable_statement_customer_period"),
        CheckConstraint("version >= 1", name="ck_editable_statement_version_positive"),
        CheckConstraint("accessible_savings >= 0", name="ck_editable_accessible_savings_non_negative"),
        CheckConstraint("protected_reserve >= 0", name="ck_editable_protected_reserve_non_negative"),
        CheckConstraint("known_arrears >= 0", name="ck_editable_known_arrears_non_negative"),
    )


class EditableStatementEntry(Base):
    """One reported line of an editable statement, tagged by which section it belongs to."""

    __tablename__ = "editable_statement_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    statement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("editable_financial_statements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section: Mapped[str] = mapped_column(String, nullable=False)
    entry_key: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    original_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    original_frequency: Mapped[str] = mapped_column(String, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # The confirmed classification, when the customer has settled one. All NULL
    # while unresolved: an unclassified outgoing stores nothing rather than a
    # fabricated default.
    display_category: Mapped[str | None] = mapped_column(String, nullable=True)
    outgoing_treatment: Mapped[str | None] = mapped_column(String, nullable=True)
    classification_source: Mapped[str | None] = mapped_column(String, nullable=True)
    taxonomy_version: Mapped[str | None] = mapped_column(String, nullable=True)

    statement: Mapped["EditableFinancialStatement"] = relationship(back_populates="entries")

    __table_args__ = (
        CheckConstraint("original_amount >= 0", name="ck_editable_entry_amount_non_negative"),
    )


class ConfirmationIdempotencyKey(Base):
    """One customer's confirmation attempt, recorded so a retry cannot duplicate history.

    The fingerprint distinguishes a genuine retry of the same request from a
    different request that happens to reuse the key.
    """

    __tablename__ = "confirmation_idempotency_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("confirmed_snapshots.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("customer_id", "idempotency_key", name="uq_idempotency_customer_key"),
    )


class CustomerClassificationPreference(Base):
    """A classification rule the customer created by correcting a suggestion.

    Scoped to one customer: two customers may hold opposite preferences for the
    same phrase, and correcting one never affects the other or the global rules.
    """

    __tablename__ = "customer_classification_preferences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True
    )
    normalized_description: Mapped[str] = mapped_column(String, nullable=False)
    display_category: Mapped[str] = mapped_column(String, nullable=False)
    outgoing_treatment: Mapped[str] = mapped_column(String, nullable=False)
    taxonomy_version: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "customer_id", "normalized_description", name="uq_preference_customer_description"
        ),
    )


class EditableStatementExpectedChange(Base):
    """A change the customer expects in a future period. It never alters this period."""

    __tablename__ = "editable_statement_expected_changes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    statement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("editable_financial_statements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entry_key: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    original_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    original_frequency: Mapped[str] = mapped_column(String, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    statement: Mapped["EditableFinancialStatement"] = relationship(back_populates="expected_changes")

    __table_args__ = (
        CheckConstraint("original_amount >= 0", name="ck_editable_change_amount_non_negative"),
    )


class SnapshotIncomeEntry(Base):
    __tablename__ = "snapshot_income_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("confirmed_snapshots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Nullable so the migration is safe against snapshots confirmed before
    # descriptions were recorded; every new confirmation sets it.
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    original_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    original_frequency: Mapped[str] = mapped_column(String, nullable=False)
    normalized_monthly_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    snapshot: Mapped["ConfirmedSnapshot"] = relationship(back_populates="income_entries")

    __table_args__ = (CheckConstraint("original_amount >= 0", name="ck_income_entry_amount_non_negative"),)


class SnapshotOutgoingEntry(Base):
    __tablename__ = "snapshot_outgoing_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("confirmed_snapshots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entry_key: Mapped[str | None] = mapped_column(String, nullable=True)
    section: Mapped[str] = mapped_column(String, nullable=False)
    # Nullable so the migration is safe against snapshots confirmed before
    # these were recorded; every new confirmation sets them.
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    display_category: Mapped[str | None] = mapped_column(String, nullable=True)
    outgoing_treatment: Mapped[str | None] = mapped_column(String, nullable=True)
    classification_source: Mapped[str | None] = mapped_column(String, nullable=True)
    taxonomy_version: Mapped[str | None] = mapped_column(String, nullable=True)
    original_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    original_frequency: Mapped[str] = mapped_column(String, nullable=False)
    normalized_monthly_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    snapshot: Mapped["ConfirmedSnapshot"] = relationship(back_populates="outgoing_entries")

    __table_args__ = (CheckConstraint("original_amount >= 0", name="ck_outgoing_entry_amount_non_negative"),)
