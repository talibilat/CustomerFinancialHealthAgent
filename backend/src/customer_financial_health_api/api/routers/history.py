"""The customer's confirmed history and what changed between periods.

Every value here is read from what was stored at confirmation. Nothing is
recalculated with today's policy, and no provider is involved in choosing or
wording the explanation.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from customer_financial_health_api.api.dependencies import get_db
from customer_financial_health_api.api.schemas import (
    ChangeExplanationOut,
    CorrectedSnapshotResponse,
    CorrectionRequest,
    ClassificationOut,
    ComponentChangeOut,
    HistoryResponse,
    HistorySnapshotOut,
    SeriesPointOut,
    StatementEntryOut,
)
from customer_financial_health_api.domain.classification import TAXONOMY_VERSION
from customer_financial_health_api.domain.history import (
    INCOME,
    OUTGOING,
    PeriodTotals,
    ReportedComponent,
    explain_change,
)
from customer_financial_health_api.api.statement_support import (
    _rejected,
    _resolve_classifications,
    _submitted_classifications,
    _validated,
    confirmed_response,
)
from customer_financial_health_api.domain.statement import FieldError
from customer_financial_health_api.persistence.repository import (
    ConfirmedSnapshotView,
    CorrectionReasonInvalid,
    IdempotencyConflict,
    SnapshotAlreadySuperseded,
    SnapshotNotFound,
    UnresolvedClassifications,
    correct_snapshot,
    get_customer_preferences,
    get_demo_customer,
    list_confirmed_history,
    list_effective_series,
)

router = APIRouter(prefix="/history", tags=["history"])


def _entries_out(entries, *, classified: bool) -> list[StatementEntryOut]:
    return [
        StatementEntryOut(
            entry_id=str(index),
            description=entry.description or "",
            original_amount=str(entry.original_amount),
            original_frequency=entry.original_frequency.value,
            normalized_monthly_amount=str(entry.normalized_monthly_amount),
            classification=(
                ClassificationOut(
                    display_category=entry.display_category.value,
                    outgoing_treatment=(
                        entry.outgoing_treatment.value if entry.outgoing_treatment else None
                    ),
                    source=(
                        entry.classification_source.value if entry.classification_source else None
                    ),
                    # The taxonomy the customer confirmed under, not today's.
                    taxonomy_version=entry.taxonomy_version or TAXONOMY_VERSION,
                    requires_confirmation=False,
                    reason_code=None,
                )
                if classified and entry.display_category is not None
                else None
            ),
        )
        for index, entry in enumerate(entries)
    ]


def _snapshot_out(
    snapshot: ConfirmedSnapshotView, effective_ids: set
) -> HistorySnapshotOut:
    return HistorySnapshotOut(
        snapshot_id=str(snapshot.id),
        statement_period=snapshot.statement_period,
        confirmed_at=snapshot.confirmed_at,
        supersedes_snapshot_id=(
            str(snapshot.supersedes_snapshot_id) if snapshot.supersedes_snapshot_id else None
        ),
        correction_reason=snapshot.correction_reason,
        is_effective=snapshot.id in effective_ids,
        calculation_policy_version=snapshot.calculation_policy_version,
        normalized_monthly_income=str(snapshot.normalized_monthly_income),
        normalized_monthly_outgoings=str(snapshot.normalized_monthly_outgoings),
        monthly_headroom=str(snapshot.monthly_headroom),
        result_code=snapshot.result_code.value,
        warnings=list(snapshot.warnings),
        income_entries=_entries_out(snapshot.income_entries, classified=False),
        outgoing_entries=_entries_out(snapshot.outgoing_entries, classified=True),
    )


def _totals(snapshot: ConfirmedSnapshotView) -> PeriodTotals:
    components = [
        ReportedComponent(
            description=entry.description or "Unlabelled",
            section=INCOME,
            monthly_amount=entry.normalized_monthly_amount,
        )
        for entry in snapshot.income_entries
    ] + [
        ReportedComponent(
            description=entry.description or "Unlabelled",
            section=OUTGOING,
            monthly_amount=entry.normalized_monthly_amount,
        )
        for entry in snapshot.outgoing_entries
    ]
    return PeriodTotals(
        statement_period=snapshot.statement_period,
        normalized_monthly_income=snapshot.normalized_monthly_income,
        normalized_monthly_outgoings=snapshot.normalized_monthly_outgoings,
        components=tuple(components),
    )


def _change_out(explanation) -> ChangeExplanationOut:
    def components(changes) -> list[ComponentChangeOut]:
        return [
            ComponentChangeOut(
                description=change.description,
                section=change.section,
                previous_monthly=str(change.previous_monthly),
                current_monthly=str(change.current_monthly),
                signed_headroom_effect=str(change.signed_headroom_effect),
            )
            for change in changes
        ]

    return ChangeExplanationOut(
        is_baseline=explanation.is_baseline,
        previous_period=explanation.previous_period,
        current_period=explanation.current_period,
        monthly_headroom_change=(
            str(explanation.monthly_headroom_change)
            if explanation.monthly_headroom_change is not None
            else None
        ),
        increases=components(explanation.increases),
        decreases=components(explanation.decreases),
        warnings=list(explanation.warnings),
    )


@router.get("", response_model=HistoryResponse)
def get_history(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db),
) -> HistoryResponse:
    customer = get_demo_customer(session)
    if customer is None:
        # No history yet is a state to act on, not an error.
        return HistoryResponse(
            total=0, limit=limit, offset=offset, snapshots=[], series=[], latest_change=None
        )

    page = list_confirmed_history(
        session, customer_id=customer.id, limit=limit, offset=offset
    )
    series = list_effective_series(session, customer_id=customer.id)
    effective_ids = {s.id for s in series}

    # The explanation compares the two most recent effective periods, so it does
    # not change with the page the customer happens to be reading.
    latest_change = None
    if series:
        latest_change = _change_out(
            explain_change(
                previous=_totals(series[-2]) if len(series) > 1 else None,
                current=_totals(series[-1]),
            )
        )

    return HistoryResponse(
        total=page.total,
        limit=page.limit,
        offset=page.offset,
        snapshots=[_snapshot_out(s, effective_ids) for s in page.snapshots],
        series=[
            SeriesPointOut(
                snapshot_id=str(s.id),
                statement_period=s.statement_period,
                normalized_monthly_income=str(s.normalized_monthly_income),
                normalized_monthly_outgoings=str(s.normalized_monthly_outgoings),
                monthly_headroom=str(s.monthly_headroom),
                result_code=s.result_code.value,
            )
            for s in series
        ],
        latest_change=latest_change,
    )


@router.post(
    "/{snapshot_id}/correct", response_model=CorrectedSnapshotResponse, status_code=201
)
def correct_confirmed_snapshot(
    snapshot_id: uuid.UUID,
    submission: CorrectionRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    session: Session = Depends(get_db),
) -> CorrectedSnapshotResponse:
    customer = get_demo_customer(session)
    if customer is None:
        raise HTTPException(status_code=404, detail="snapshot_not_found")

    statement = _validated(submission)
    confirmed, _ = _submitted_classifications(submission)
    preferences = get_customer_preferences(session, customer_id=customer.id)
    classifications = _resolve_classifications(
        statement, confirmed=confirmed, preferences=preferences
    )

    try:
        correction = correct_snapshot(
            session,
            customer_id=customer.id,
            supersedes_snapshot_id=snapshot_id,
            statement=statement,
            classifications=classifications,
            correction_reason=submission.correction_reason,
            idempotency_key=idempotency_key,
            confirmed_at=datetime.now(timezone.utc),
        )
    except CorrectionReasonInvalid as invalid:
        session.rollback()
        raise _rejected(
            [
                FieldError(
                    "correction_reason",
                    "correction_reason_invalid",
                    "Tell us briefly what was wrong, in 500 characters or fewer.",
                )
            ]
        ) from invalid
    except SnapshotNotFound as missing:
        session.rollback()
        # The same response as a snapshot that never existed, so ownership
        # cannot be probed by trying identifiers.
        raise HTTPException(status_code=404, detail="snapshot_not_found") from missing
    except SnapshotAlreadySuperseded as superseded:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "snapshot_already_superseded",
                "message": "This record has already been corrected. Refresh your history.",
            },
        ) from superseded
    except UnresolvedClassifications as unresolved:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "classifications_unresolved",
                "message": "Tell us what each outgoing was for before correcting this.",
                "entry_ids": list(unresolved.entry_ids),
            },
        ) from unresolved
    except IdempotencyConflict as conflict:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "idempotency_key_conflict",
                "message": "This correction reference was already used for a different change.",
            },
        ) from conflict

    session.commit()

    base = confirmed_response(correction)
    return CorrectedSnapshotResponse(
        **base.model_dump(),
        supersedes_snapshot_id=str(correction.supersedes_snapshot_id),
        correction_reason=correction.correction_reason or "",
    )
