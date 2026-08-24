"""Exploring a repayment scenario against the customer's effective snapshot.

Preview only: nothing here writes anything, and the basis snapshot and the
editable statement are both untouched. The response reports the source totals
and the formula's inputs so the customer can check the arithmetic themselves.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from customer_financial_health_api.api.dependencies import get_db
from customer_financial_health_api.api.schemas import (
    SavedScenarioListResponse,
    SavedScenarioRequest,
    SavedScenarioResponse,
    ExistingRepaymentCommitmentOut,
    ScenarioBasisResponse,
    ScenarioRequest,
    ScenarioResponse,
)
from customer_financial_health_api.api.statement_support import _rejected
from customer_financial_health_api.domain.repayment import (
    ScenarioMode,
    calculate_scenario,
)
from customer_financial_health_api.domain.statement import FieldError, parse_money
from customer_financial_health_api.persistence.repository import (
    IdempotencyConflict,
    RepaymentScenarioView,
    ScenarioBasisNotCurrent,
    ScenarioNotFound,
    get_demo_customer,
    get_effective_snapshot,
    get_repayment_scenario,
    list_repayment_scenarios,
    save_repayment_scenario,
)

router = APIRouter(prefix="/repayment-scenario", tags=["repayment-scenario"])
saved_router = APIRouter(prefix="/repayment-scenarios", tags=["repayment-scenarios"])


def _optional_str(amount: Decimal | None) -> str | None:
    return str(amount) if amount is not None else None


@router.get("/basis", response_model=ScenarioBasisResponse)
def retrieve_scenario_basis(session: Session = Depends(get_db)) -> ScenarioBasisResponse:
    customer = get_demo_customer(session)
    snapshot = (
        get_effective_snapshot(session, customer_id=customer.id) if customer else None
    )
    if snapshot is None:
        raise HTTPException(status_code=404, detail="no_confirmed_snapshot")
    commitments = [
        ExistingRepaymentCommitmentOut(
            id=entry.id,
            description=entry.description or "Existing repayment commitment",
            normalized_monthly_amount=str(entry.normalized_monthly_amount),
        )
        for entry in snapshot.outgoing_entries
        if entry.section == "repayment_commitment" and entry.id is not None
    ]
    return ScenarioBasisResponse(
        basis_snapshot_id=snapshot.id,
        basis_statement_period=snapshot.statement_period,
        basis_monthly_headroom=str(snapshot.monthly_headroom),
        existing_repayment_commitments=commitments,
    )


@router.post("/preview", response_model=ScenarioResponse)
def preview_repayment_scenario(
    submission: ScenarioRequest, session: Session = Depends(get_db)
) -> ScenarioResponse:
    customer = get_demo_customer(session)
    snapshot = (
        get_effective_snapshot(session, customer_id=customer.id) if customer else None
    )
    if snapshot is None:
        raise HTTPException(status_code=404, detail="no_confirmed_snapshot")

    errors: list[FieldError] = []

    try:
        mode = ScenarioMode(submission.mode)
    except ValueError:
        errors.append(
            FieldError("mode", "mode_not_supported", "Choose one of the supported scenario modes.")
        )
        mode = None

    # The statement's money rules are reused here, so an amount refused in one
    # place cannot be accepted in the other.
    proposed = parse_money(submission.proposed_repayment, "proposed_repayment", errors)
    replaced = (
        parse_money(submission.replaced_repayment, "replaced_repayment", errors)
        if submission.replaced_repayment is not None
        else None
    )
    buffer = (
        parse_money(submission.protected_monthly_buffer, "protected_monthly_buffer", errors)
        if submission.protected_monthly_buffer is not None
        else None
    )

    if proposed is not None and proposed == 0:
        errors.append(
            FieldError(
                "proposed_repayment",
                "repayment_not_a_scenario",
                "Enter an amount above zero to compare.",
            )
        )
    if mode is ScenarioMode.CHANGE_EXISTING and replaced is None:
        errors.append(
            FieldError(
                "replaced_repayment",
                "commitment_not_selected",
                "Choose which repayment you would change.",
            )
        )

    if errors:
        raise _rejected(errors)

    result = calculate_scenario(
        monthly_headroom=snapshot.monthly_headroom,
        mode=mode,
        proposed_repayment=proposed,
        replaced_repayment=replaced,
        protected_monthly_buffer=buffer,
    )

    return ScenarioResponse(
        calculation_policy_version=result.calculation_policy_version,
        basis_snapshot_id=str(snapshot.id),
        basis_statement_period=snapshot.statement_period,
        basis_monthly_headroom=str(result.basis_monthly_headroom),
        mode=result.mode.value,
        proposed_repayment=str(result.proposed_repayment),
        replaced_repayment=_optional_str(result.replaced_repayment),
        scenario_headroom=str(result.scenario_headroom),
        protected_monthly_buffer=_optional_str(result.protected_monthly_buffer),
        buffer_shortfall=_optional_str(result.buffer_shortfall),
        result_code=result.result_code.value,
        warnings=list(result.warnings),
    )


def _saved_out(scenario: RepaymentScenarioView) -> SavedScenarioResponse:
    return SavedScenarioResponse(
        id=scenario.id,
        basis_snapshot_id=scenario.basis_snapshot_id,
        basis_statement_period=scenario.basis_statement_period,
        basis_is_superseded=scenario.basis_is_superseded,
        mode=scenario.mode.value,
        selected_existing_commitment_id=scenario.selected_existing_commitment_id,
        selected_existing_commitment_description=(
            scenario.selected_existing_commitment_description
        ),
        proposed_repayment=str(scenario.proposed_repayment),
        protected_monthly_buffer=_optional_str(scenario.protected_monthly_buffer),
        basis_monthly_headroom=str(scenario.basis_monthly_headroom),
        replaced_repayment=_optional_str(scenario.replaced_repayment),
        scenario_headroom=str(scenario.scenario_headroom),
        buffer_shortfall=_optional_str(scenario.buffer_shortfall),
        result_code=scenario.result_code.value,
        warnings=list(scenario.warnings),
        calculation_policy_version=scenario.calculation_policy_version,
        created_at=scenario.created_at,
    )


@saved_router.post("", response_model=SavedScenarioResponse, status_code=status.HTTP_201_CREATED)
def save_scenario(
    submission: SavedScenarioRequest,
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=1, max_length=200)
    ],
    session: Session = Depends(get_db),
) -> SavedScenarioResponse:
    errors: list[FieldError] = []
    try:
        mode = ScenarioMode(submission.mode)
    except ValueError:
        mode = None
        errors.append(
            FieldError("mode", "mode_not_supported", "Choose one of the supported scenario modes.")
        )
    proposed = parse_money(submission.proposed_repayment, "proposed_repayment", errors)
    buffer = (
        parse_money(submission.protected_monthly_buffer, "protected_monthly_buffer", errors)
        if submission.protected_monthly_buffer is not None
        else None
    )
    if proposed is not None and proposed == 0:
        errors.append(
            FieldError(
                "proposed_repayment",
                "repayment_not_a_scenario",
                "Enter an amount above zero to save.",
            )
        )
    if mode is ScenarioMode.CHANGE_EXISTING and submission.selected_existing_commitment_id is None:
        errors.append(
            FieldError(
                "selected_existing_commitment_id",
                "commitment_not_selected",
                "Choose which repayment you would change.",
            )
        )
    if mode is ScenarioMode.ADDITIONAL and submission.selected_existing_commitment_id is not None:
        errors.append(
            FieldError(
                "selected_existing_commitment_id",
                "commitment_not_allowed",
                "An additional repayment does not replace an existing commitment.",
            )
        )
    if errors:
        raise _rejected(errors)

    try:
        with session.begin():
            customer = get_demo_customer(session)
            if customer is None:
                raise ScenarioNotFound("no customer")
            saved = save_repayment_scenario(
                session,
                customer_id=customer.id,
                basis_snapshot_id=submission.basis_snapshot_id,
                mode=mode,
                selected_existing_commitment_id=(
                    submission.selected_existing_commitment_id
                ),
                proposed_repayment=proposed,
                protected_monthly_buffer=buffer,
                idempotency_key=idempotency_key,
                created_at=datetime.now(timezone.utc),
            )
    except IdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail="idempotency_key_conflict") from exc
    except ScenarioBasisNotCurrent as exc:
        raise HTTPException(status_code=409, detail="basis_snapshot_superseded") from exc
    except ScenarioNotFound as exc:
        raise HTTPException(status_code=404, detail="resource_not_found") from exc
    return _saved_out(saved)


@saved_router.get("", response_model=SavedScenarioListResponse)
def list_saved_scenarios(session: Session = Depends(get_db)) -> SavedScenarioListResponse:
    customer = get_demo_customer(session)
    scenarios = (
        list_repayment_scenarios(session, customer_id=customer.id) if customer else ()
    )
    return SavedScenarioListResponse(
        scenarios=[_saved_out(scenario) for scenario in scenarios], total=len(scenarios)
    )


@saved_router.get("/{scenario_id}", response_model=SavedScenarioResponse)
def retrieve_saved_scenario(
    scenario_id: UUID, session: Session = Depends(get_db)
) -> SavedScenarioResponse:
    customer = get_demo_customer(session)
    if customer is None:
        raise HTTPException(status_code=404, detail="resource_not_found")
    try:
        scenario = get_repayment_scenario(
            session, customer_id=customer.id, scenario_id=scenario_id
        )
    except ScenarioNotFound as exc:
        raise HTTPException(status_code=404, detail="resource_not_found") from exc
    return _saved_out(scenario)
