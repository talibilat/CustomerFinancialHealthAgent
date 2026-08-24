"""Exploring a repayment scenario against the customer's effective snapshot.

Preview only: nothing here writes anything, and the basis snapshot and the
editable statement are both untouched. The response reports the source totals
and the formula's inputs so the customer can check the arithmetic themselves.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from customer_financial_health_api.api.dependencies import get_db
from customer_financial_health_api.api.schemas import ScenarioRequest, ScenarioResponse
from customer_financial_health_api.api.statement_support import _rejected
from customer_financial_health_api.domain.repayment import (
    ScenarioMode,
    calculate_scenario,
)
from customer_financial_health_api.domain.statement import FieldError, parse_money
from customer_financial_health_api.persistence.repository import (
    get_demo_customer,
    get_effective_snapshot,
)

router = APIRouter(prefix="/repayment-scenario", tags=["repayment-scenario"])


def _optional_str(amount: Decimal | None) -> str | None:
    return str(amount) if amount is not None else None


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
