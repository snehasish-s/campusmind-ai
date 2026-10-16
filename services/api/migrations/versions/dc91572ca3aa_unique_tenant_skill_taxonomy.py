"""Deduplicate controlled taxonomy records and enforce institution/name uniqueness."""

from alembic import op

revision = "dc91572ca3aa"
down_revision = "85b30a9f71db"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""UPDATE skill_evidence SET skill_id = (
        SELECT MIN(canonical.id) FROM skills AS canonical JOIN skills AS old ON old.id=skill_evidence.skill_id
        WHERE canonical.institution_id=old.institution_id AND canonical.name=old.name)""")
    op.execute("DELETE FROM skills WHERE id NOT IN (SELECT MIN(id) FROM skills GROUP BY institution_id,name)")
    with op.batch_alter_table("skills") as batch:
        batch.create_unique_constraint("uq_skills_tenant_name", ["institution_id", "name"])


def downgrade():
    with op.batch_alter_table("skills") as batch:
        batch.drop_constraint("uq_skills_tenant_name", type_="unique")
