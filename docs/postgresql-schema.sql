BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> f394a8c83449

CREATE TABLE institutions (
    slug VARCHAR(80) NOT NULL, 
    name VARCHAR(200) NOT NULL, 
    city VARCHAR NOT NULL, 
    privacy_notice TEXT NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (slug)
);

CREATE TABLE activity_events (
    title VARCHAR NOT NULL, 
    kind VARCHAR NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id)
);

CREATE INDEX ix_activity_events_institution_id ON activity_events (institution_id);

CREATE TABLE ai_workflow_runs (
    status VARCHAR NOT NULL, 
    provider VARCHAR NOT NULL, 
    schema_version INTEGER NOT NULL, 
    payload JSON NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id)
);

CREATE INDEX ix_ai_workflow_runs_institution_id ON ai_workflow_runs (institution_id);

CREATE TABLE companies (
    name VARCHAR(150) NOT NULL, 
    website VARCHAR NOT NULL, 
    sector VARCHAR NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id), 
    UNIQUE (institution_id, name)
);

CREATE INDEX ix_companies_institution_id ON companies (institution_id);

CREATE TABLE departments (
    code VARCHAR(40) NOT NULL, 
    name VARCHAR(150) NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id), 
    UNIQUE (institution_id, code)
);

CREATE INDEX ix_departments_institution_id ON departments (institution_id);

CREATE TABLE evidence_requirements (
    title VARCHAR NOT NULL, 
    schema_version INTEGER NOT NULL, 
    payload JSON NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id)
);

CREATE INDEX ix_evidence_requirements_institution_id ON evidence_requirements (institution_id);

CREATE TABLE skills (
    name VARCHAR NOT NULL, 
    schema_version INTEGER NOT NULL, 
    payload JSON NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id)
);

CREATE INDEX ix_skills_institution_id ON skills (institution_id);

CREATE TABLE student_assessments (
    title VARCHAR NOT NULL, 
    schema_version INTEGER NOT NULL, 
    payload JSON NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id)
);

CREATE INDEX ix_student_assessments_institution_id ON student_assessments (institution_id);

CREATE TABLE recruitment_drives (
    company_id VARCHAR(36) NOT NULL, 
    position VARCHAR(160) NOT NULL, 
    description TEXT NOT NULL, 
    employment_type VARCHAR NOT NULL, 
    location VARCHAR NOT NULL, 
    ctc VARCHAR NOT NULL, 
    required_skills JSON NOT NULL, 
    min_cgpa FLOAT NOT NULL, 
    max_backlogs INTEGER NOT NULL, 
    eligible_branches JSON NOT NULL, 
    graduation_year INTEGER NOT NULL, 
    deadline TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    drive_date TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    selection_rounds JSON NOT NULL, 
    additional_requirements TEXT NOT NULL, 
    status VARCHAR NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CHECK (status IN ('draft','published','closed')), 
    FOREIGN KEY(company_id) REFERENCES companies (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id)
);

CREATE INDEX ix_drives_tenant_status ON recruitment_drives (institution_id, status);

CREATE INDEX ix_recruitment_drives_institution_id ON recruitment_drives (institution_id);

CREATE TABLE test_questions (
    assessment_id VARCHAR(36) NOT NULL, 
    schema_version INTEGER NOT NULL, 
    payload JSON NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(assessment_id) REFERENCES student_assessments (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id)
);

CREATE INDEX ix_test_questions_institution_id ON test_questions (institution_id);

CREATE TABLE users (
    email VARCHAR(254) NOT NULL, 
    roll_no VARCHAR(80) NOT NULL, 
    full_name VARCHAR(150) NOT NULL, 
    role VARCHAR(30) NOT NULL, 
    password_hash VARCHAR(255), 
    active BOOLEAN NOT NULL, 
    department_id VARCHAR(36), 
    consent_at TIMESTAMP WITHOUT TIME ZONE, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CHECK (role IN ('platform_admin','institution_admin','placement_officer','hod','student')), 
    FOREIGN KEY(department_id) REFERENCES departments (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id), 
    UNIQUE (institution_id, email), 
    UNIQUE (institution_id, roll_no)
);

CREATE INDEX ix_users_institution_id ON users (institution_id);

CREATE TABLE audit_logs (
    actor_id VARCHAR(36), 
    action VARCHAR NOT NULL, 
    target_id VARCHAR, 
    details JSON NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(actor_id) REFERENCES users (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id)
);

CREATE INDEX ix_audit_logs_institution_id ON audit_logs (institution_id);

CREATE TABLE auth_sessions (
    user_id VARCHAR(36) NOT NULL, 
    token_hash VARCHAR(64) NOT NULL, 
    csrf_hash VARCHAR(64) NOT NULL, 
    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id), 
    FOREIGN KEY(user_id) REFERENCES users (id), 
    UNIQUE (token_hash)
);

CREATE INDEX ix_auth_sessions_institution_id ON auth_sessions (institution_id);

CREATE INDEX ix_auth_sessions_user_id ON auth_sessions (user_id);

CREATE TABLE drive_applications (
    drive_id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    status VARCHAR NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(drive_id) REFERENCES recruitment_drives (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id), 
    FOREIGN KEY(user_id) REFERENCES users (id), 
    UNIQUE (drive_id, user_id)
);

CREATE INDEX ix_drive_applications_institution_id ON drive_applications (institution_id);

CREATE TABLE import_jobs (
    actor_id VARCHAR(36) NOT NULL, 
    filename VARCHAR NOT NULL, 
    fingerprint VARCHAR(64) NOT NULL, 
    policy VARCHAR NOT NULL, 
    status VARCHAR NOT NULL, 
    rows JSON NOT NULL, 
    total INTEGER NOT NULL, 
    processed INTEGER NOT NULL, 
    created INTEGER NOT NULL, 
    updated INTEGER NOT NULL, 
    skipped INTEGER NOT NULL, 
    errors INTEGER NOT NULL, 
    failure TEXT, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(actor_id) REFERENCES users (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id), 
    UNIQUE (institution_id, fingerprint)
);

CREATE INDEX ix_import_jobs_institution_id ON import_jobs (institution_id);

CREATE TABLE institutional_documents (
    title VARCHAR NOT NULL, 
    category VARCHAR NOT NULL, 
    storage_key VARCHAR NOT NULL, 
    filename VARCHAR NOT NULL, 
    size_bytes INTEGER NOT NULL, 
    mime_type VARCHAR NOT NULL, 
    uploaded_by VARCHAR(36) NOT NULL, 
    status VARCHAR NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id), 
    FOREIGN KEY(uploaded_by) REFERENCES users (id)
);

CREATE INDEX ix_institutional_documents_institution_id ON institutional_documents (institution_id);

CREATE TABLE invitations (
    user_id VARCHAR(36) NOT NULL, 
    token_hash VARCHAR(64) NOT NULL, 
    purpose VARCHAR NOT NULL, 
    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    used_at TIMESTAMP WITHOUT TIME ZONE, 
    revoked_at TIMESTAMP WITHOUT TIME ZONE, 
    delivery_status VARCHAR NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id), 
    FOREIGN KEY(user_id) REFERENCES users (id), 
    UNIQUE (token_hash)
);

CREATE INDEX ix_invitations_institution_id ON invitations (institution_id);

CREATE INDEX ix_invitations_user_id ON invitations (user_id);

CREATE TABLE learning_roadmaps (
    user_id VARCHAR(36) NOT NULL, 
    schema_version INTEGER NOT NULL, 
    payload JSON NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_learning_roadmaps_institution_id ON learning_roadmaps (institution_id);

CREATE TABLE notifications (
    user_id VARCHAR(36), 
    title VARCHAR NOT NULL, 
    message TEXT NOT NULL, 
    read_at TIMESTAMP WITHOUT TIME ZONE, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_notifications_institution_id ON notifications (institution_id);

CREATE INDEX ix_notifications_user_id ON notifications (user_id);

CREATE TABLE resumes (
    user_id VARCHAR(36) NOT NULL, 
    filename VARCHAR NOT NULL, 
    storage_key VARCHAR NOT NULL, 
    text_key VARCHAR NOT NULL, 
    mime_type VARCHAR NOT NULL, 
    size_bytes INTEGER NOT NULL, 
    version INTEGER NOT NULL, 
    extraction_status VARCHAR NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id), 
    FOREIGN KEY(user_id) REFERENCES users (id), 
    UNIQUE (user_id, version)
);

CREATE INDEX ix_resumes_institution_id ON resumes (institution_id);

CREATE INDEX ix_resumes_user_id ON resumes (user_id);

CREATE TABLE skill_evidence (
    user_id VARCHAR(36) NOT NULL, 
    skill_id VARCHAR(36) NOT NULL, 
    schema_version INTEGER NOT NULL, 
    payload JSON NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id), 
    FOREIGN KEY(skill_id) REFERENCES skills (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_skill_evidence_institution_id ON skill_evidence (institution_id);

CREATE TABLE staff_roles (
    user_id VARCHAR(36) NOT NULL, 
    role VARCHAR(30) NOT NULL, 
    department_id VARCHAR(36), 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(department_id) REFERENCES departments (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id), 
    FOREIGN KEY(user_id) REFERENCES users (id), 
    UNIQUE (user_id)
);

CREATE INDEX ix_staff_roles_institution_id ON staff_roles (institution_id);

CREATE TABLE student_profiles (
    user_id VARCHAR(36) NOT NULL, 
    graduation_year INTEGER NOT NULL, 
    cgpa FLOAT NOT NULL, 
    active_backlogs INTEGER NOT NULL, 
    phone VARCHAR(30) NOT NULL, 
    bio TEXT NOT NULL, 
    projects JSON NOT NULL, 
    internships JSON NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CHECK (active_backlogs >= 0), 
    CHECK (cgpa >= 0 AND cgpa <= 10), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id), 
    FOREIGN KEY(user_id) REFERENCES users (id), 
    UNIQUE (user_id)
);

CREATE INDEX ix_student_profiles_institution_id ON student_profiles (institution_id);

CREATE TABLE test_attempts (
    assessment_id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    schema_version INTEGER NOT NULL, 
    payload JSON NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(assessment_id) REFERENCES student_assessments (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_test_attempts_institution_id ON test_attempts (institution_id);

CREATE TABLE evidence_findings (
    document_id VARCHAR(36) NOT NULL, 
    requirement_id VARCHAR(36) NOT NULL, 
    schema_version INTEGER NOT NULL, 
    payload JSON NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(document_id) REFERENCES institutional_documents (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id), 
    FOREIGN KEY(requirement_id) REFERENCES evidence_requirements (id)
);

CREATE INDEX ix_evidence_findings_institution_id ON evidence_findings (institution_id);

CREATE TABLE import_errors (
    job_id VARCHAR(36) NOT NULL, 
    row_number INTEGER NOT NULL, 
    message TEXT NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id), 
    FOREIGN KEY(job_id) REFERENCES import_jobs (id)
);

CREATE INDEX ix_import_errors_institution_id ON import_errors (institution_id);

CREATE INDEX ix_import_errors_job_id ON import_errors (job_id);

CREATE TABLE learning_tasks (
    roadmap_id VARCHAR(36) NOT NULL, 
    schema_version INTEGER NOT NULL, 
    payload JSON NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id), 
    FOREIGN KEY(roadmap_id) REFERENCES learning_roadmaps (id)
);

CREATE INDEX ix_learning_tasks_institution_id ON learning_tasks (institution_id);

CREATE TABLE resume_analysis (
    resume_id VARCHAR(36) NOT NULL, 
    schema_version INTEGER NOT NULL, 
    payload JSON NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id), 
    FOREIGN KEY(resume_id) REFERENCES resumes (id)
);

CREATE INDEX ix_resume_analysis_institution_id ON resume_analysis (institution_id);

INSERT INTO alembic_version (version_num) VALUES ('f394a8c83449') RETURNING alembic_version.version_num;

-- Running upgrade f394a8c83449 -> 65bbfb53fcef

CREATE TABLE career_goals (
    user_id VARCHAR(36) NOT NULL, 
    schema_version INTEGER NOT NULL, 
    payload JSON NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id), 
    FOREIGN KEY(user_id) REFERENCES users (id), 
    UNIQUE (user_id)
);

CREATE INDEX ix_career_goals_institution_id ON career_goals (institution_id);

CREATE TABLE conversations (
    user_id VARCHAR(36) NOT NULL, 
    title VARCHAR NOT NULL, 
    schema_version INTEGER NOT NULL, 
    payload JSON NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_conversations_institution_id ON conversations (institution_id);

CREATE INDEX ix_conversations_user_id ON conversations (user_id);

CREATE TABLE data_requests (
    user_id VARCHAR(36) NOT NULL, 
    kind VARCHAR NOT NULL, 
    status VARCHAR NOT NULL, 
    schema_version INTEGER NOT NULL, 
    payload JSON NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_data_requests_institution_id ON data_requests (institution_id);

CREATE TABLE drive_reviews (
    drive_id VARCHAR(36) NOT NULL, 
    approved_by VARCHAR(36), 
    approved_at TIMESTAMP WITHOUT TIME ZONE, 
    schema_version INTEGER NOT NULL, 
    payload JSON NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(approved_by) REFERENCES users (id), 
    FOREIGN KEY(drive_id) REFERENCES recruitment_drives (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id), 
    UNIQUE (drive_id)
);

CREATE INDEX ix_drive_reviews_institution_id ON drive_reviews (institution_id);

CREATE TABLE eligibility_appeals (
    drive_id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    status VARCHAR NOT NULL, 
    schema_version INTEGER NOT NULL, 
    payload JSON NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(drive_id) REFERENCES recruitment_drives (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_eligibility_appeals_institution_id ON eligibility_appeals (institution_id);

CREATE TABLE document_chunks (
    document_id VARCHAR(36) NOT NULL, 
    chunk_index INTEGER NOT NULL, 
    page INTEGER, 
    content TEXT NOT NULL, 
    content_hash VARCHAR(64) NOT NULL, 
    vector_status VARCHAR NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(document_id) REFERENCES institutional_documents (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id), 
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX ix_document_chunks_document_id ON document_chunks (document_id);

CREATE INDEX ix_document_chunks_institution_id ON document_chunks (institution_id);

ALTER TABLE activity_events ADD COLUMN user_id VARCHAR(36);

ALTER TABLE activity_events ADD COLUMN payload JSON DEFAULT '{}' NOT NULL;

CREATE INDEX ix_activity_events_user_id ON activity_events (user_id);

ALTER TABLE activity_events ADD CONSTRAINT fk_activity_user FOREIGN KEY(user_id) REFERENCES users (id);

ALTER TABLE institutional_documents ADD COLUMN content_hash VARCHAR(64);

ALTER TABLE institutional_documents ADD COLUMN version INTEGER DEFAULT '1' NOT NULL;

ALTER TABLE institutional_documents ADD COLUMN parent_id VARCHAR(36);

ALTER TABLE institutional_documents ADD COLUMN department_id VARCHAR(36);

ALTER TABLE institutional_documents ADD COLUMN owner_id VARCHAR(36);

ALTER TABLE institutional_documents ADD COLUMN expires_at TIMESTAMP WITHOUT TIME ZONE;

ALTER TABLE institutional_documents ADD COLUMN metadata_json JSON DEFAULT '{}' NOT NULL;

CREATE INDEX ix_institutional_documents_content_hash ON institutional_documents (content_hash);

ALTER TABLE institutional_documents ADD CONSTRAINT fk_document_owner FOREIGN KEY(owner_id) REFERENCES users (id);

ALTER TABLE institutional_documents ADD CONSTRAINT fk_document_parent FOREIGN KEY(parent_id) REFERENCES institutional_documents (id);

ALTER TABLE institutional_documents ADD CONSTRAINT fk_document_department FOREIGN KEY(department_id) REFERENCES departments (id);

ALTER TABLE test_questions ALTER COLUMN assessment_id DROP NOT NULL;

ALTER TABLE recruitment_drives DROP CONSTRAINT recruitment_drives_status_check;

ALTER TABLE recruitment_drives ADD CONSTRAINT ck_drive_lifecycle CHECK (status IN ('draft','reviewed','published','open','closed','completed'));

UPDATE alembic_version SET version_num='65bbfb53fcef' WHERE alembic_version.version_num = 'f394a8c83449';

-- Running upgrade 65bbfb53fcef -> ff50ef42cdb9

CREATE TABLE rate_limit_buckets (
    key VARCHAR(100) NOT NULL, 
    count INTEGER NOT NULL, 
    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (key)
);

CREATE TABLE institutional_tasks (
    title VARCHAR NOT NULL, 
    assigned_to VARCHAR(36) NOT NULL, 
    department_id VARCHAR(36), 
    status VARCHAR NOT NULL, 
    schema_version INTEGER NOT NULL, 
    payload JSON NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(assigned_to) REFERENCES users (id), 
    FOREIGN KEY(department_id) REFERENCES departments (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id)
);

CREATE INDEX ix_institutional_tasks_institution_id ON institutional_tasks (institution_id);

UPDATE alembic_version SET version_num='ff50ef42cdb9' WHERE alembic_version.version_num = '65bbfb53fcef';

-- Running upgrade ff50ef42cdb9 -> 2c876e951adb

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
            EXECUTE format('REVOKE ALL ON TABLE public.%%I FROM %%I',t.tablename,r);
            EXECUTE format('ALTER TABLE public.%%I ENABLE ROW LEVEL SECURITY',t.tablename);
          END LOOP;
        END IF;
      END LOOP;
      CREATE SCHEMA IF NOT EXISTS campusmind_checkpoints;
      REVOKE ALL ON SCHEMA campusmind_checkpoints FROM PUBLIC;
    END $$;;

UPDATE alembic_version SET version_num='2c876e951adb' WHERE alembic_version.version_num = 'ff50ef42cdb9';

-- Running upgrade 2c876e951adb -> 85b30a9f71db

ALTER TABLE import_jobs ADD COLUMN lease_expires_at TIMESTAMP WITHOUT TIME ZONE;

ALTER TABLE import_jobs ADD COLUMN lease_token VARCHAR(64);

UPDATE alembic_version SET version_num='85b30a9f71db' WHERE alembic_version.version_num = '2c876e951adb';

-- Running upgrade 85b30a9f71db -> dc91572ca3aa

UPDATE skill_evidence SET skill_id = (
        SELECT MIN(canonical.id) FROM skills AS canonical JOIN skills AS old ON old.id=skill_evidence.skill_id
        WHERE canonical.institution_id=old.institution_id AND canonical.name=old.name);

DELETE FROM skills WHERE id NOT IN (SELECT MIN(id) FROM skills GROUP BY institution_id,name);

ALTER TABLE skills ADD CONSTRAINT uq_skills_tenant_name UNIQUE (institution_id, name);

UPDATE alembic_version SET version_num='dc91572ca3aa' WHERE alembic_version.version_num = '85b30a9f71db';

-- Running upgrade dc91572ca3aa -> d7e25ded6e9f

CREATE TABLE campus_authorities (
    user_id VARCHAR(36) NOT NULL, 
    office VARCHAR(40) NOT NULL, 
    department_id VARCHAR(36), 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(department_id) REFERENCES departments (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id), 
    FOREIGN KEY(user_id) REFERENCES users (id), 
    UNIQUE (user_id)
);

CREATE INDEX ix_campus_authorities_institution_id ON campus_authorities (institution_id);

CREATE TABLE campus_imports (
    actor_id VARCHAR(36) NOT NULL, 
    kind VARCHAR(20) NOT NULL, 
    fingerprint VARCHAR(64) NOT NULL, 
    rows JSON NOT NULL, 
    errors JSON NOT NULL, 
    confirmed_at TIMESTAMP WITHOUT TIME ZONE, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(actor_id) REFERENCES users (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id), 
    UNIQUE (institution_id, fingerprint)
);

CREATE INDEX ix_campus_imports_institution_id ON campus_imports (institution_id);

CREATE TABLE campus_posts (
    author_id VARCHAR(36) NOT NULL, 
    office VARCHAR(40) NOT NULL, 
    title VARCHAR(200) NOT NULL, 
    message TEXT NOT NULL, 
    kind VARCHAR(20) NOT NULL, 
    audience JSON NOT NULL, 
    subject VARCHAR(100) NOT NULL, 
    due_at TIMESTAMP WITHOUT TIME ZONE, 
    storage_key VARCHAR, 
    filename VARCHAR, 
    mime VARCHAR, 
    withdrawn BOOLEAN NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(author_id) REFERENCES users (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id)
);

CREATE INDEX ix_campus_posts_institution_id ON campus_posts (institution_id);

CREATE TABLE campus_receipts (
    post_id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    read_at TIMESTAMP WITHOUT TIME ZONE, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id), 
    FOREIGN KEY(post_id) REFERENCES campus_posts (id), 
    FOREIGN KEY(user_id) REFERENCES users (id), 
    UNIQUE (post_id, user_id)
);

CREATE INDEX ix_campus_receipts_institution_id ON campus_receipts (institution_id);

CREATE TABLE teaching_slots (
    import_id VARCHAR(36) NOT NULL, 
    department_id VARCHAR(36) NOT NULL, 
    graduation_year INTEGER NOT NULL, 
    academic_year INTEGER NOT NULL, 
    semester INTEGER NOT NULL, 
    section VARCHAR(30) NOT NULL, 
    subject VARCHAR(100) NOT NULL, 
    teacher_id VARCHAR(36) NOT NULL, 
    weekday INTEGER NOT NULL, 
    starts VARCHAR(5) NOT NULL, 
    ends VARCHAR(5) NOT NULL, 
    room VARCHAR(80) NOT NULL, 
    valid_from VARCHAR(10) NOT NULL, 
    valid_until VARCHAR(10) NOT NULL, 
    active BOOLEAN NOT NULL, 
    institution_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(department_id) REFERENCES departments (id), 
    FOREIGN KEY(import_id) REFERENCES campus_imports (id), 
    FOREIGN KEY(institution_id) REFERENCES institutions (id), 
    FOREIGN KEY(teacher_id) REFERENCES users (id)
);

CREATE INDEX ix_teaching_slots_department_id ON teaching_slots (department_id);

CREATE INDEX ix_teaching_slots_institution_id ON teaching_slots (institution_id);

ALTER TABLE student_profiles ADD COLUMN section VARCHAR(30) DEFAULT '' NOT NULL;

ALTER TABLE student_profiles ADD COLUMN academic_year INTEGER;

ALTER TABLE student_profiles ADD COLUMN semester INTEGER;

ALTER TABLE users DROP CONSTRAINT users_role_check;

ALTER TABLE users ADD CONSTRAINT ck_user_roles CHECK (role IN ('platform_admin','institution_admin','placement_officer','hod','faculty','campus_staff','student'));

ALTER TABLE "campus_authorities" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE "campus_authorities" FROM PUBLIC;

DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN EXECUTE 'REVOKE ALL ON TABLE campus_authorities FROM anon'; END IF; IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN EXECUTE 'REVOKE ALL ON TABLE campus_authorities FROM authenticated'; END IF; END $$;

ALTER TABLE "campus_imports" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE "campus_imports" FROM PUBLIC;

DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN EXECUTE 'REVOKE ALL ON TABLE campus_imports FROM anon'; END IF; IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN EXECUTE 'REVOKE ALL ON TABLE campus_imports FROM authenticated'; END IF; END $$;

ALTER TABLE "teaching_slots" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE "teaching_slots" FROM PUBLIC;

DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN EXECUTE 'REVOKE ALL ON TABLE teaching_slots FROM anon'; END IF; IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN EXECUTE 'REVOKE ALL ON TABLE teaching_slots FROM authenticated'; END IF; END $$;

ALTER TABLE "campus_posts" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE "campus_posts" FROM PUBLIC;

DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN EXECUTE 'REVOKE ALL ON TABLE campus_posts FROM anon'; END IF; IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN EXECUTE 'REVOKE ALL ON TABLE campus_posts FROM authenticated'; END IF; END $$;

ALTER TABLE "campus_receipts" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE "campus_receipts" FROM PUBLIC;

DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN EXECUTE 'REVOKE ALL ON TABLE campus_receipts FROM anon'; END IF; IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN EXECUTE 'REVOKE ALL ON TABLE campus_receipts FROM authenticated'; END IF; END $$;

UPDATE alembic_version SET version_num='d7e25ded6e9f' WHERE alembic_version.version_num = 'dc91572ca3aa';

COMMIT;

