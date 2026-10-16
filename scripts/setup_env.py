"""Create an ignored local configuration with unique random database credentials."""

import argparse
import secrets
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--sqlite", action="store_true", help="Single-process fallback without Docker. Not for production.")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
path = root / ".env"
if path.exists():
    raise SystemExit(".env already exists; preserving your configuration.")
admin_secret, app_secret = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
text = (root / ".env.example").read_text(encoding="utf-8")
text = (
    text.replace("POSTGRES_PASSWORD=\n", f"POSTGRES_PASSWORD={admin_secret}\n")
    .replace("APP_DB_PASSWORD=\n", f"APP_DB_PASSWORD={app_secret}\n")
    .replace("REPLACE_WITH_APP_DB_PASSWORD", app_secret)
)
if args.sqlite:
    text = (
        text.replace(f"postgresql+psycopg://campusmind_app:{app_secret}@localhost:5432/campusmind", "sqlite:///./data/campusmind.db")
        .replace("QUEUE_MODE=rq", "QUEUE_MODE=sync")
        .replace("RATE_LIMIT_BACKEND=redis", "RATE_LIMIT_BACKEND=memory")
    )
path.write_text(text, encoding="utf-8")
path.chmod(0o600)
(root / "data").mkdir(exist_ok=True)
print("Created local .env with unique database credentials. Keep this file private and out of version control.")
