from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from customer_financial_health_api.api.dependencies import get_db

router = APIRouter()

BACKEND_ROOT = Path(__file__).resolve().parents[4]


def _expected_head_revision() -> str | None:
    alembic_cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return ScriptDirectory.from_config(alembic_cfg).get_current_head()


@router.get("/health/live")
def liveness() -> dict:
    return {"status": "ok"}


@router.get("/health/ready")
def readiness(response: Response, session: Session = Depends(get_db)) -> dict:
    try:
        current_revision = session.execute(text("select version_num from alembic_version")).scalar_one_or_none()
    except Exception:
        response.status_code = 503
        return {"status": "not_ready", "database": "unreachable", "ai": "not_configured"}

    if current_revision != _expected_head_revision():
        response.status_code = 503
        return {"status": "not_ready", "database": "schema_mismatch", "ai": "not_configured"}

    return {"status": "ready", "database": "ok", "ai": "not_configured"}
