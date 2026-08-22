import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from customer_financial_health_api.persistence.seed import seed_demo_data

BACKEND_ROOT = Path(__file__).resolve().parents[3]


def main() -> None:
    database_url = os.environ["DATABASE_URL"]

    alembic_cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(database_url)
    with Session(engine) as session:
        seed_demo_data(session)
        session.commit()


if __name__ == "__main__":
    main()
