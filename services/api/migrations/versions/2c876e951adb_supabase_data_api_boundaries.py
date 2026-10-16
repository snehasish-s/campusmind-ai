"""Keep application records and future checkpoints inaccessible to Supabase client roles."""

from alembic import op
import sqlalchemy as sa

revision = "2c876e951adb"
down_revision = "ff50ef42cdb9"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    # Roles are fixed identifiers; no user-controlled SQL is interpolated.
    op.execute(
        sa.text("""
    DO $$ DECLARE t record; r text;
    BEGIN
      FOREACH r IN ARRAY ARRAY['anon','authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
          FOR t IN SELECT tablename FROM pg_tables WHERE schemaname='public'
            AND tablename IN ('institutions','departments','users','student_profiles','staff_roles','auth_sessions','invitations',
            'import_jobs','import_errors','resumes','companies','recruitment_drives','drive_applications','notifications','activity_events',
            'audit_logs','institutional_documents','skills','skill_evidence','resume_analysis','student_assessments','test_questions',
            'test_attempts','learning_roadmaps','learning_tasks','ai_workflow_runs','evidence_requirements','evidence_findings',
            'drive_reviews','eligibility_appeals','career_goals','document_chunks','conversations','data_requests','rate_limit_buckets','institutional_tasks')
          LOOP
            EXECUTE format('REVOKE ALL ON TABLE public.%I FROM %I',t.tablename,r);
            EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',t.tablename);
          END LOOP;
        END IF;
      END LOOP;
      CREATE SCHEMA IF NOT EXISTS campusmind_checkpoints;
      REVOKE ALL ON SCHEMA campusmind_checkpoints FROM PUBLIC;
    END $$;
    """)
    )


def downgrade():
    # Never reopen student data to public API roles during rollback.
    pass
