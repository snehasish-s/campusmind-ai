# Database and workflow diagrams

Every domain table below is institution-owned through an indexed `institution_id`, except the institution root and hashed global rate-limit buckets. Repeated tenant relationships are omitted from the diagrams for legibility. Payload records include a schema version and are validated at their service/API boundaries. Foreign keys, per-institution account uniqueness, per-student resume version uniqueness and controlled skill-name uniqueness are enforced in the database.

## Identity and onboarding

```mermaid
erDiagram
  Institutions ||--o{ Departments : contains
  Institutions ||--o{ Users : owns
  Departments ||--o{ Users : assigns
  Users ||--o| StudentProfiles : has
  Users ||--o| StaffRoles : has
  Users ||--o{ AuthSessions : authenticates
  Users ||--o{ Invitations : activates_or_resets
  Users ||--o{ ImportJobs : initiates
  ImportJobs ||--o{ ImportErrors : records
  Users ||--o{ Resumes : versions
  Users ||--o{ Notifications : receives
  Users ||--o{ ActivityEvents : performs
  Users ||--o{ AuditLogs : privileged_actor
  Users {
    uuid id PK
    uuid institution_id FK
    uuid department_id FK
    string roll_no "unique within institution"
    string email "unique within institution"
    string role
    string password_hash
    boolean active
  }
  Invitations {
    uuid id PK
    uuid user_id FK
    string token_hash "unique; never raw token"
    datetime expires_at
    datetime used_at
    datetime revoked_at
  }
  ImportJobs {
    uuid id PK
    string fingerprint "unique within institution"
    string status
    int processed
    datetime lease_expires_at
    string lease_token
  }
```

## Placement, assessments and preparation

```mermaid
erDiagram
  Companies ||--o{ RecruitmentDrives : recruits
  RecruitmentDrives ||--o| DriveReviews : approves
  RecruitmentDrives ||--o{ DriveApplications : receives
  RecruitmentDrives ||--o{ EligibilityAppeals : reviewed_corrections
  Users ||--o{ DriveApplications : submits
  Users ||--o{ EligibilityAppeals : requests
  Resumes ||--o{ ResumeAnalysis : supports
  Users ||--o{ SkillEvidence : claims_or_demonstrates
  Skills ||--o{ SkillEvidence : normalizes
  Users ||--o| CareerGoals : defines
  StudentAssessments ||--o{ TestAttempts : delivers
  StudentAssessments o|--o{ TestQuestions : optional_legacy_parent
  Users ||--o{ TestAttempts : takes
  Users ||--o{ LearningRoadmaps : versions
  LearningRoadmaps ||--o{ LearningTasks : contains
  Users ||--o{ Conversations : owns
  StudentAssessments {
    uuid id PK
    string title
    json payload "approved question IDs and duration"
  }
  TestQuestions {
    uuid id PK
    uuid assessment_id FK "nullable; independent question bank"
    json payload "type, options, key, rubric, human approval"
  }
  TestAttempts {
    uuid id PK
    uuid assessment_id FK
    uuid user_id FK
    json payload "private snapshot, deadline, answers, score, reviews"
  }
  LearningRoadmaps {
    uuid id PK
    uuid user_id FK
    json payload "version, previous ID, trigger, proposal status"
  }
  LearningTasks {
    uuid id PK
    uuid roadmap_id FK
    json payload "objective, hours, resources, status, preserved source"
  }
```

## Institutional evidence and reliability

```mermaid
erDiagram
  Users ||--o{ InstitutionalDocuments : uploads_or_owns
  Departments o|--o{ InstitutionalDocuments : tags
  InstitutionalDocuments o|--o{ InstitutionalDocuments : parent_version
  InstitutionalDocuments ||--o{ DocumentChunks : indexes
  InstitutionalDocuments ||--o{ EvidenceFindings : supports
  EvidenceRequirements ||--o{ EvidenceFindings : maps
  Users ||--o{ InstitutionalTasks : assigned
  Departments o|--o{ InstitutionalTasks : scopes
  Users ||--o{ DataRequests : requests
  InstitutionalDocuments {
    uuid id PK
    uuid parent_id FK
    uuid department_id FK
    uuid owner_id FK
    string content_hash
    int version
    string status
    datetime expires_at
    json metadata_json
  }
  DocumentChunks {
    uuid id PK
    uuid document_id FK
    int chunk_index "unique within document"
    int page "nullable"
    string content_hash
    string vector_status
  }
  AIWorkflowRuns {
    uuid id PK
    string status
    string provider
    json payload "actor, kind, target, provenance, retry, result"
  }
  RateLimitBuckets {
    string key PK "hashed limiter identity"
    int count
    datetime expires_at
  }
```

LangGraph checkpoint tables are managed by its installed checkpointer library, separately from domain migrations. They use a private PostgreSQL schema or a local SQLite file; neither has a browser-facing read endpoint.

## Bounded agent execution

```mermaid
flowchart TD
  U[Authenticated action] --> V[Validate input, role, tenant and target]
  V --> J[Persist queued workflow run]
  J --> Q{Execution mode}
  Q -->|local distributed| R[Single RQ AI queue]
  Q -->|lightweight fallback| S[Synchronous execution]
  R --> A
  S --> A
  A[LangGraph: reauthorize current actor] --> B[Analyze using allowlisted business queries]
  B --> C{Optional model available?}
  C -->|yes| L[Bounded LangChain / Ollama structured call]
  C -->|no or invalid| F[Labelled deterministic fallback]
  L --> O[Validate schema, source quotes and source IDs]
  F --> O
  O --> P[Persist evidence, draft, recommendation or source answer]
  P --> H{Important action?}
  H -->|roadmap or official question/drive| I[Human review and explicit acceptance]
  H -->|read-only result| D[Authorized result]
  I --> D
  A -. checkpoint .-> CP[(Private graph checkpoints)]
  B -. checkpoint .-> CP
  P -. checkpoint .-> CP
```

## Evidence retrieval

```mermaid
flowchart LR
  F[Validated upload] --> T[Text extraction with available page metadata]
  T --> C[Overlapping versioned chunks]
  C --> K[Keyword index in authorized DB records]
  C --> E[Optional cached local embeddings]
  E --> Q[Qdrant tenant and document filters]
  K --> R[Retrieval and optional RRF fusion]
  Q --> R
  R --> A[Revalidate tenant, department, approval, expiry and version]
  A --> S[Optional local model selects allowed source IDs]
  S --> O[Exact source excerpts with document/version/page citations]
  A --> N[Insufficient evidence when no supporting source exists]
```


## Academic distribution
```mermaid
flowchart LR
  A[Admin cohort sheet] --> B[Validated student branch / section / semester]
  C[Admin timetable sheet] --> D[Versioned teaching slots]
  D --> E[Teacher subject permission]
  F[Admin assigned leadership office] --> G[Authorized publication]
  E --> G
  G --> H[Deterministic audience matching]
  B --> H
  H --> I[Private student feed and notifications]
  I --> J[Explicit read acknowledgement]
```
