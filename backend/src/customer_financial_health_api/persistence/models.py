import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
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
    supersedes_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("confirmed_snapshots.id"), nullable=True
    )

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
