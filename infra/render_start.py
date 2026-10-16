"""One free web service: Next.js public port, FastAPI private loopback port."""
import os
import signal
import subprocess
import sys
import time

subprocess.run([sys.executable, "-m", "alembic", "-c", "services/api/alembic.ini", "upgrade", "head"], check=True)
children = []


def stop(*_):
    for child in children:
        if child.poll() is None:
            child.terminate()
    for child in children:
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()


signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
try:
    children.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--no-access-log"]))
    environment = {**os.environ, "HOSTNAME": "0.0.0.0", "PORT": os.environ.get("PORT", "10000")}
    children.append(subprocess.Popen(["node", "web/server.js"], env=environment))
    while all(child.poll() is None for child in children):
        time.sleep(1)
finally:
    stop()
