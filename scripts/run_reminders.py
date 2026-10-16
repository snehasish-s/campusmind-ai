"""Run one deterministic sweep for a local scheduler or an always-on worker."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services/api"))
from app.campus_services import automatic_tick  # noqa: E402

if __name__ == "__main__":
    automatic_tick()
    print("Reminder sweep completed. Inspect recorded deliveries in Campus automation.")
