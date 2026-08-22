import json
from pathlib import Path

from customer_financial_health_api.api.app import app

BACKEND_ROOT = Path(__file__).resolve().parents[3]


def main() -> None:
    output_path = BACKEND_ROOT / "openapi.json"
    output_path.write_text(json.dumps(app.openapi(), indent=2) + "\n")
    print(f"wrote {output_path}")


if __name__ == "__main__":
    main()
