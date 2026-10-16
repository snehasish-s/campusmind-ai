# Campus Hub: academic communication and deterministic routing

Open `/app/campus` or choose **Campus Hub** in the sidebar. `/app/timetable` shows schedules. Updates refresh every 15 seconds while the hub is open; timetable refreshes every 30 seconds. This is polling, not WebSockets or push delivery when the app is closed.

## Setup once, distribute automatically

1. Create departments. Use **Bulk student import** to onboard students securely. Its existing CSV fields still work; optional `section,academic_year,semester` columns now populate academic routing. Graduation year is the expected completion year, not current study year. Students cannot change routing fields themselves.
2. In **Staff & roles**, invite teachers with the **Subject teacher** role. Invite principals, deans and directors with **Campus office**. Each staff member activates their own account; there are no shared credentials. Existing HOD and placement roles continue to work.
3. Open **Campus Hub → Campus administration**. Download the cohort and timetable templates. Cohort imports update existing students; they do not create accounts or reset passwords.
4. Import a CSV or XLSX using exact template headers. Preview errors and records, then confirm. Every row must be valid: errors prevent the entire import from applying. Reconfirming the same import is idempotent.
5. Assign a publishing office (principal, dean, director, department, placement or teacher). Department/teacher grants require a department. A faculty account automatically has teacher publishing access for its assigned department; revoking an extra grant returns it to that baseline. Removing its teaching slots removes subject publishing permission. Campus-office accounts require a grant.
6. Publishers compose an update, optionally choose a timetable slot to populate the subject and cohort, check the recipient count and publish. Distribution and in-app notifications are automatic after publication. No administrator needs to individually forward each message.

## CSV examples (synthetic)

Cohorts:
```csv
roll_no,department,graduation_year,academic_year,semester,section
SYN20270001,CSE,2027,4,7,A
```

Timetable:
```csv
department,graduation_year,academic_year,semester,section,subject,teacher_roll_no,weekday,starts,ends,room,valid_from,valid_until
CSE,2027,4,7,A,Database Systems,TEACHER001,0,09:00,10:00,CSE101,2026-10-01,2026-12-31
```

Use existing department codes and staff login IDs. Monday is `0`, Sunday is `6`. Dates must be ISO `YYYY-MM-DD`; times must be plain text `HH:MM`. XLSX must have one worksheet and plain values, including time/date cells; formulas, legacy XLS and macro-enabled files are unsupported. Limit: 8 MB upload, 32 MB expanded workbook, 20,000 records, 100 columns. Do not upload a visual merged-cell timetable: use the normalized template. Ambiguous spreadsheet layouts are rejected rather than guessed by an LLM.

## Distribution rules

All queries are institution-scoped. Audience filters combine with AND: department, graduation year, academic year, semester, section and optional individual registration number. Blank fields broaden the audience. Unknown cohort fields never match a specified cohort. Institution-wide leadership announcements match all student accounts, including accounts awaiting activation; the feed becomes available after activation.

Teachers can publish only to an exact cohort and subject assigned to them by a currently valid timetable. Assignments by non-admin publishers also require that teaching assignment. Principals/deans/directors use an administrator-assigned publishing designation; their role is not inferred from a message. Campus-office and faculty accounts cannot access placement analytics, student registry or private resumes. HOD scope remains departmental. Existing administrator and placement roles retain their existing privileges; granting a new publishing office does not revoke those base privileges.

Documents use the existing private local/Supabase storage adapter. PDF, DOCX and TXT content is checked and limited to 8 MB. Every attachment download rechecks current institution and audience membership. Notices can be withdrawn; withdrawn attachments stop being downloadable by students. Posts are plain text, not rendered HTML.

Students see matching historical and new updates for their current cohort; this is not a permanent snapshot of their previous section. Read acknowledgement is an explicit student action. Delivery summaries count original recipient records and acknowledgements; they do not prove a device displayed an update. Newly reassigned students can see matching older posts and acknowledge them.

## Timetable replacement and history

A confirmed timetable replaces the **whole schedule for each exact cohort included in that file**. Include every desired slot for those cohorts. Other cohorts remain unchanged. Prior slots remain inactive in the database. Preview and confirmation reject teacher, room and cohort overlaps. Confirmation rechecks conflicts and serializes institutional replacement with a PostgreSQL row lock. Dates indicate validity; students can inspect active-version schedules including upcoming or expired dates. Teacher authorization requires validity today.

Academic cohort imports are administrative records, not student-editable profile fields. Existing onboarding CSV updates without cohort columns preserve a student's existing section/year/semester. Cohort updates and timetable updates create targeted notifications. Existing drive, assessment and roadmap notifications remain operational.

## API

- `GET /api/campus/context`, `/posts`, `/timetable`
- `POST /api/campus/posts/preview` — count matching accounts
- `POST /api/campus/posts` — multipart `payload` JSON and optional `file`
- `GET /api/campus/posts/{id}/attachment`
- `POST /api/campus/posts/{id}/acknowledge`
- `GET /api/campus/posts/{id}/delivery`
- `DELETE /api/campus/posts/{id}` — audited withdrawal
- `GET/PUT /api/campus/authorities`, `DELETE /api/campus/authorities/{id}` — admin only
- `GET /api/campus/template/{cohorts|timetable}`
- `POST /api/campus/imports/preview` — multipart `kind` + `file`
- `POST /api/campus/imports/{id}/confirm`, `GET /api/campus/imports`

All mutations use existing session and CSRF protections. PostgreSQL migration also restricts Supabase public Data API access to the new tables. Run migrations before restarting the API. Student erasure removes receipts, cohort import rows and individually targeted post content/attachments; shared class notices are institutional records and require their own retention policy.

## Practical boundaries

Routing is automatic after authorized setup/publication. The system does not invent official notices, discover teachers without a roster, infer semester promotions from dates or autonomously grant publishing authority. These trusted inputs are necessary to prevent incorrect distribution. Assignment submissions, marking and scheduled reminders are implemented in the [campus life extension](CAMPUS_LIFE_AND_FEES.md). Attendance and background Web Push remain future work. No LLM or paid service is required for campus communication.

## Workspace separation and PlacementOS admission

Campus Hub is an independent workspace. It has its own sidebar and breadcrumb, with campus updates, timetable and student profile access. Students, faculty and campus office staff land on `/app/campus` after login. The old student `/app` entry redirects there.

An **Open PlacementOS** link appears in Campus Hub only for eligible students and authorized placement/administrative staff. PlacementOS opens at `/app/placement` and has its own preparation, resume, drive and assessment navigation. A Campus Hub link returns to college communication. Campus Hub remains available to students in every year.

For the current four-year B.Tech programme, students need an institution-managed `academic_year` of **3 or 4** for PlacementOS. First year, second year, missing year and other values do not qualify. Batch/graduation dates, self-edited profile information and semester guesses do not grant access. The administrator updates this field through onboarding CSV or the cohort import. A missing year shows an explanatory message instead of guessing.

The backend enforces the same rule on placement routes, including resume, drive, assessment, skills, roadmap, analytics and workflow APIs. Campus routes, own profile, notifications, authentication and own privacy export/deletion request remain available. Permissions are re-evaluated on every request, so cohort changes take effect without waiting for logout. This product-admission rule is separate from each company's objective recruitment eligibility rules.

Institutions offering degrees with a different programme duration will need a configurable final-year policy before enabling PlacementOS for those programmes; this release applies the requested B.Tech third/fourth-year policy.
