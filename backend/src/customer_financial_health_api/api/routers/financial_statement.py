"""Retrieve, update, and preview the customer's editable financial statement.

None of these operations confirms a snapshot. Preview is a pure recalculation
from the submitted statement, and update replaces only the editable working
copy, so confirmed history is never touched here.
"""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from customer_financial_health_api.api.dependencies import get_db
from customer_financial_health_api.api.schemas import (
    EditableStatementOut,
    EditableStatementResponse,
    ExpectedChangeOut,
    LookingAheadOut,
    ResilienceOut,
    ResilienceSectionOut,
    StatementEntryOut,
    StatementPreviewResponse,
    StatementSubmission,
    StatementUpdateRequest,
)
from customer_financial_health_api.domain.statement import (
    ExpectedChange,
    FinancialStatement,
    StatementEntry,
    StatementValidationError,
    preview_statement,
    validate_statement,
)
from customer_financial_health_api.persistence.repository import (
    EditableStatementView,
    StaleStatementVersion,
    get_demo_customer,
    get_editable_statement,
    save_editable_statement,
)

router = APIRouter(prefix="/financial-statement", tags=["financial-statement"])


def _optional_str(amount: Decimal | None) -> str | None:
    return str(amount) if amount is not None else None


def _entries_out(entries: tuple[StatementEntry, ...]) -> list[StatementEntryOut]:
    return [
        StatementEntryOut(
            entry_id=entry.entry_id,
            description=entry.description,
            original_amount=str(entry.amount),
            original_frequency=entry.frequency.value,
            normalized_monthly_amount=str(entry.normalized_monthly_amount),
        )
        for entry in entries
    ]


def _changes_out(changes: tuple[ExpectedChange, ...]) -> list[ExpectedChangeOut]:
    return [
        ExpectedChangeOut(
            entry_id=change.entry_id,
            description=change.description,
            kind=change.kind.value,
            original_amount=str(change.amount),
            original_frequency=change.frequency.value,
            normalized_monthly_amount=str(change.normalized_monthly_amount),
        )
        for change in changes
    ]


def _statement_out(statement: FinancialStatement) -> EditableStatementOut:
    return EditableStatementOut(
        statement_period=statement.statement_period,
        currency=statement.currency,
        income_entries=_entries_out(statement.income_entries),
        outgoing_entries=_entries_out(statement.outgoing_entries),
        repayment_commitments=_entries_out(statement.repayment_commitments),
        resilience=ResilienceSectionOut(
            accessible_savings=_optional_str(statement.resilience.accessible_savings),
            protected_reserve=_optional_str(statement.resilience.protected_reserve),
            current_account_balance=_optional_str(statement.resilience.current_account_balance),
            known_arrears=_optional_str(statement.resilience.known_arrears),
        ),
        looking_ahead=LookingAheadOut(
            irregular_costs=_entries_out(statement.looking_ahead.irregular_costs),
            protected_future_provisions=_entries_out(
                statement.looking_ahead.protected_future_provisions
            ),
            expected_changes=_changes_out(statement.looking_ahead.expected_changes),
        ),
    )


def _statement_response(stored: EditableStatementView) -> EditableStatementResponse:
    return EditableStatementResponse(
        version=stored.version,
        updated_at=stored.updated_at,
        statement=_statement_out(stored.statement),
    )


def _validated(submission: StatementSubmission) -> FinancialStatement:
    """Validate a submission, translating field errors into one safe response."""
    payload = submission.model_dump(exclude={"expected_version"})
    try:
        return validate_statement(payload)
    except StatementValidationError as invalid:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "statement_invalid",
                "message": "Nothing was saved. Check the highlighted fields and try again.",
                "errors": [
                    {"field": error.field, "code": error.code, "message": error.message}
                    for error in invalid.errors
                ],
            },
        ) from invalid


def _current_customer(session: Session):
    customer = get_demo_customer(session)
    if customer is None:
        raise HTTPException(status_code=404, detail="no_customer_data")
    return customer


@router.get("", response_model=EditableStatementResponse)
def retrieve_financial_statement(
    statement_period: date, session: Session = Depends(get_db)
) -> EditableStatementResponse:
    customer = _current_customer(session)
    stored = get_editable_statement(
        session, customer_id=customer.id, statement_period=statement_period
    )
    if stored is None:
        raise HTTPException(status_code=404, detail="no_editable_statement")
    return _statement_response(stored)


@router.put("", response_model=EditableStatementResponse)
def update_financial_statement(
    submission: StatementUpdateRequest, session: Session = Depends(get_db)
) -> EditableStatementResponse:
    customer = _current_customer(session)
    statement = _validated(submission)

    try:
        saved = save_editable_statement(
            session,
            customer_id=customer.id,
            statement=statement,
            expected_version=submission.expected_version,
        )
    except StaleStatementVersion as conflict:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "statement_version_conflict",
                "message": "Someone changed this statement. Refresh to see the current version.",
                "current_version": conflict.current,
            },
        ) from conflict

    session.commit()
    return _statement_response(saved)


@router.post("/preview", response_model=StatementPreviewResponse)
def preview_financial_statement(submission: StatementSubmission) -> StatementPreviewResponse:
    preview = preview_statement(_validated(submission))

    return StatementPreviewResponse(
        calculation_policy_version=preview.calculation_policy_version,
        normalized_monthly_income=str(preview.position.normalized_monthly_income),
        normalized_monthly_outgoings=str(preview.position.normalized_monthly_outgoings),
        monthly_headroom=str(preview.position.monthly_headroom),
        result_code=preview.position.result_code.value,
        warnings=list(preview.position.warnings) + list(preview.warnings),
        normalized_monthly_repayment_commitments=str(
            preview.normalized_monthly_repayment_commitments
        ),
        normalized_monthly_irregular_costs=str(preview.normalized_monthly_irregular_costs),
        normalized_monthly_protected_future_provisions=str(
            preview.normalized_monthly_protected_future_provisions
        ),
        expected_changes=_changes_out(preview.expected_changes),
        resilience=ResilienceOut(
            accessible_savings=_optional_str(preview.resilience.accessible_savings),
            protected_reserve=_optional_str(preview.resilience.protected_reserve),
            current_account_balance=_optional_str(preview.resilience.current_account_balance),
            known_arrears=_optional_str(preview.resilience.known_arrears),
            savings_above_reserve=_optional_str(preview.resilience.savings_above_reserve),
            reserve_gap=_optional_str(preview.resilience.reserve_gap),
            result_code=preview.resilience.result_code.value
            if preview.resilience.result_code
            else None,
            warnings=list(preview.resilience.warnings),
        ),
    )
