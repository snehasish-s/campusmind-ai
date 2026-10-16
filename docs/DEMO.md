# Final-year project demonstration

Use fictional records only. Start with README's installation and seed steps. Passwords are chosen locally or generated uniquely; no shared demo credential is embedded in source. For a short presentation, import a small preview first, then demonstrate the full `data/synthetic-students.csv` operation.

## A — Bulk onboarding

1. Sign in as institution `demo`, ID `PLACEMENT`, with the unique seed password.
2. Open Bulk student import, download the template, and choose the 1,000-row generated CSV.
3. Show column mapping, normalized preview, duplicates/error summary and confirmation.
4. Show completed import counters and Student registry. Accounts remain inactive until students choose passwords.
5. In Mailpit, open a synthetic student's invitation. Without Mailpit, issue **One-time distribution** from the registry; explain that the link is one-time, short-lived and audited.
6. Activate the student, acknowledge the privacy notice, choose a password, sign in with the roll number and edit the profile.
7. Upload a synthetic PDF/DOCX resume. Example text: `Projects: Campus library API using Python and SQL. Skills: Python, SQL, Git.`

## B — Skill intelligence

1. Open My skills and Analyze latest resume.
2. Show provider provenance: default exact keyword extraction is labelled deterministic, not an LLM.
3. Show the source quote and review/confirm/challenge controls. Confirming a claim does not prove proficiency.
4. As an officer, open Assessments and its studio. The seed bank starts as drafts. Review options, answer keys and explanations, approve two SQL questions, select them and publish a timed assessment.
5. As the student, start the assessment, save answers and submit. Before submission, the API does not expose the answer key.
6. Show the objective score, topic feedback and assessment evidence. Written/code responses require an examiner and never run on the server.

## C — New .NET recruitment drive

1. As the officer, create a draft for **Fictional Coastline Systems**, position **.NET Developer**.
2. Use explicit synthetic description: `Required: C#, .NET and SQL Server. Develop and maintain backend services. Eligible CSE students graduating in 2027, minimum CGPA 6, no active backlogs.` Enter the same actual academic conditions in the form.
3. Set a future registration deadline and a drive date five days away. Save a draft.
4. Open details, Analyze job description, review required/preferred skills, remove unsupported entries and confirm actual company conditions. Mark unresolved conditions for human review rather than inventing a restriction.
5. Approve requirements, reopen details and move Reviewed → Published → Open. Students receive in-app information. Close and Complete are later permitted lifecycle actions.
6. As the student, browse the drive. Inspect objective criteria separately from preparation alignment. Register if eligible or submit a correction request; the officer records an explained decision.
7. In My career roadmap, select the .NET drive and propose a plan. The five-day plan uses realistic revision/practice with a bounded study budget and explicitly defers material it cannot fit.

## D — Adaptive preparation

1. Accept a Python/SQL baseline plan and mark a task completed before proposing the .NET plan.
2. Complete the SQL assessment; inspect stored answers, exact objective scoring and topic results.
3. Return to the roadmap. A new proposal explains its assessment/drive trigger. Completed tasks are preserved.
4. Accept the update. The old active plan becomes archived. Show archived versions without deleting progress.

## E — Officer intelligence

1. Open Placement analytics. Filter by department, batch, company/drive, assessment, topic or dates.
2. Show actual participation, mean/median scores, distributions, topic performance, application outcomes and evidence coverage.
3. Open the student drill-down. Inspect claimed versus demonstrated skills, progress, assessment history, source-backed matching and coaching reasons.
4. Demonstrate examiner marking on a written response. Explain that objective and examiner total scores remain separate.
5. Export the authorized cohort CSV. A second synthetic institution must not access the first institution's student, file, workflow, attempt or evidence IDs; automated negative tests demonstrate this boundary.

## F — CollegeOps

1. Sign in as an administrator; optionally invite a department coordinator and assign the department.
2. Upload a fictional UTF-8 text evidence file: `CSE faculty development report. A database workshop was conducted for twelve fictional faculty members in September.`
3. Tag the department, choose expiry/version metadata and show chunk/index status. Re-uploading identical content returns the duplicate record.
4. Review and approve the source as the administrator. Before approval, it is excluded from evidence answers.
5. Define an institution-specific Faculty development requirement and map the document.
6. Ask `What evidence supports the faculty database workshop?` Show the exact excerpt, document/version and PDF page if a PDF source supplies one.
7. Export the draft requirement report. Emphasize that source availability is not official accreditation certification. Assign a follow-up task, have the coordinator submit it and the administrator approve it.

## Research and deployment closing

Show `docs/evaluation-results.json`, its sample sizes and the actual test record. Explain the difference between deterministic baseline results, in-process vector-adapter tests and optional real-model experiments. Do not claim production accuracy, successful placement probability or unrun cloud/model benchmarks.

Finish with `.env.hosted.example`: credentials are inserted privately into Supabase/Render configuration. The local prototype stays usable at ₹0 even if hosted quotas or account requirements prevent deployment.
