"""Record measured JUnit results, including failures; never substitute expected counts."""

import json
from pathlib import Path
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

root = Path(__file__).resolve().parents[1]


def junit(path):
    result = ET.parse(path).getroot()
    suites = [result] if result.get("tests") is not None else list(result.iter("testsuite"))
    return {
        key: sum(float(suite.get(key, "0")) for suite in suites) if key == "time" else sum(int(suite.get(key, "0")) for suite in suites)
        for key in ("tests", "failures", "errors", "skipped", "time")
    }


if __name__ == "__main__":
    record = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "backend": junit(root / "data/backend-results.xml"),
        "browser": junit(root / "apps/web/test-results/browser-results.xml"),
        "verified_checks": [
            "Next.js production build",
            "TypeScript typecheck",
            "ESLint",
            "Ruff",
            "Local SQLite Alembic upgrade/check",
            "PostgreSQL migrations compiled to offline SQL",
            "Base and AI Docker Compose configuration validation",
            "pip check",
            "Synthetic campus seed executed twice without resetting accounts",
        ],
        "not_verified": [
            "Actual merchant checkout, refunds and bank settlement; gateway HTTP transport was mocked in API tests",
            "Live PostgreSQL concurrency and distributed worker load",
            "Background Web Push (not implemented)",
            "Ollama translation quality; manual/unavailable fallback tested",
            "This local extension has not been deployed to Render",
        ],
        "sources": ["data/backend-results.xml", "apps/web/test-results/browser-results.xml"],
    }
    (root / "docs/verification-results.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"backend": record["backend"], "browser": record["browser"]}))
    if any(record[area][key] for area in ("backend", "browser") for key in ("failures", "errors")):
        raise SystemExit("Results recorded with failures. Repair and rerun the relevant tests.")
