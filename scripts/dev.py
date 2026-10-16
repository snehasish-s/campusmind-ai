"""Run the existing FastAPI and Next.js apps together for local development."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
os.chdir(root)
if not (root / ".env").exists() or not (root / "apps/web/node_modules").exists():
    raise SystemExit("Complete README installation first: create .env, install dependencies, and apply migrations.")
environment = {**os.environ, "PYTHONPATH": str(root / "services/api"), "NEXT_TELEMETRY_DISABLED": "1"}
web_command = ["cmd", "/c", "npm.cmd", "run", "dev"] if os.name == "nt" else ["npm", "run", "dev"]
children = []


def stop(*_):
    for child in children:
        if child.poll() is None:
            child.terminate()


signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)
try:
    children.append(
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"], cwd=root, env=environment
        )
    )
    children.append(subprocess.Popen(web_command, cwd=root / "apps/web", env=environment))
    print("CampusMind: http://localhost:3000 · API: http://localhost:8000/docs · Ctrl+C stops the servers.")
    while all(child.poll() is None for child in children):
        time.sleep(1)
finally:
    stop()
