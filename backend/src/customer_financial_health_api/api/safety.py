"""Turning any unexpected failure into a response that discloses nothing.

An exception message can carry anything: a database URL with a password, a
reported amount, a provider's response, a customer's own wording. None of it
may reach the customer or the logs, so only the exception *type* and a
correlation identifier are recorded.

That is a deliberate trade-off. It makes a production failure harder to
diagnose from logs alone, and it is the only version that cannot leak.
"""

import logging
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError

logger = logging.getLogger(__name__)

SAFE_MESSAGE = (
    "Something went wrong on our side. Your information has not been lost. "
    "Please try again in a moment."
)
DATA_CONFLICT_MESSAGE = (
    "We could not save this change because it conflicts with another record. "
    "Refresh and try again."
)
RETRYABLE_CONFLICT_MESSAGE = (
    "We could not complete this change because related information changed at the same time. "
    "Refresh and try again."
)


def _is_retryable_transaction_conflict(failure: Exception) -> bool:
    if not isinstance(failure, OperationalError):
        return False
    origin = failure.orig
    sqlstate = getattr(origin, "sqlstate", None) or getattr(origin, "pgcode", None)
    return sqlstate in {"40001", "40P01"}


async def safe_failure_middleware(request: Request, call_next):
    """Catch anything the routers did not, and answer safely."""
    try:
        return await call_next(request)
    except Exception as failure:  # noqa: BLE001 - the point is to catch everything
        correlation_id = str(uuid.uuid4())
        if _is_retryable_transaction_conflict(failure):
            status_code = 409
            code = "retryable_conflict"
            message = RETRYABLE_CONFLICT_MESSAGE
            category = "retryable_transaction_conflict"
        elif isinstance(failure, IntegrityError):
            status_code = 409
            code = "data_conflict"
            message = DATA_CONFLICT_MESSAGE
            category = "database_constraint"
        else:
            status_code = 500
            code = "internal_error"
            message = SAFE_MESSAGE
            category = "unexpected"
        # Deliberately not the message, and deliberately no traceback: either
        # can contain credentials, connection strings, or financial detail.
        logger.error(
            "unhandled_request_failure",
            extra={
                "correlation_id": correlation_id,
                "operation": f"{request.method} {request.url.path}",
                "failure_type": type(failure).__name__,
                "failure_category": category,
            },
        )
        return JSONResponse(
            status_code=status_code,
            content={
                "detail": {
                    "code": code,
                    "message": message,
                    "correlation_id": correlation_id,
                }
            },
        )
