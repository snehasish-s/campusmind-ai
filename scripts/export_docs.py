"""Export the actual OpenAPI contract; configuration values are not serialized."""

import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "services/api"))
from app.main import app  # noqa: E402

(root / "docs/openapi.json").write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
print(f"Exported {len(app.openapi()['paths'])} API paths.")
