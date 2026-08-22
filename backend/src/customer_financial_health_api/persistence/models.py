import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, func
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
    )


class SnapshotIncomeEntry(Base):
    __tablename__ = "snapshot_income_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("confirmed_snapshots.id", ondelete="CASCADE"), nullable=False, index=True
    )
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
    original_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    original_frequency: Mapped[str] = mapped_column(String, nullable=False)
    normalized_monthly_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    snapshot: Mapped["ConfirmedSnapshot"] = relationship(back_populates="outgoing_entries")

    __table_args__ = (CheckConstraint("original_amount >= 0", name="ck_outgoing_entry_amount_non_negative"),)
