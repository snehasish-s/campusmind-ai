"""Recoverable import processing leases for ephemeral hosting."""

from alembic import op
import sqlalchemy as sa

revision = "85b30a9f71db"
down_revision = "2c876e951adb"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("import_jobs", sa.Column("lease_expires_at", sa.DateTime(), nullable=True))
    op.add_column("import_jobs", sa.Column("lease_token", sa.String(64), nullable=True))


def downgrade():
    op.drop_column("import_jobs", "lease_token")
    op.drop_column("import_jobs", "lease_expires_at")
