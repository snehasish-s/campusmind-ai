"use client";
import { useState } from "react";
import { useReducedMotion } from "motion/react";
import { useQuery } from "@tanstack/react-query";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  LineChart,
  Line,
} from "recharts";
import {
  Search,
  FileCheck2,
  Upload,
  Download,
  ShieldCheck,
} from "lucide-react";
import { api, send, type User, type Drive } from "@/lib/api";
import { Button } from "../ui/button";
import { Badge, Empty, Failure, PageHeading, Skeleton } from "../ui/common";
import { MatchingPanel, useAction } from "./intelligence";
import { ExaminerReview } from "./examiner";

type Performance = {
  id: string;
  name: string;
  roll_no: string;
  active: boolean;
  resume: boolean;
  attempts: number;
  average: number | null;
  completed_tasks: number;
  total_tasks: number;
  applications: number;
  offers: number;
  support_reasons: string[];
  skills: { skill: string; evidence_type: string }[];
  trend: { date: string; score: number | null; title: string }[];
};
type Analytics = {
  total: number;
  activated: number;
  resume_rate: number;
  participation_rate: number;
  average: number | null;
  median: number | null;
  students: Performance[];
  topics: { topic: string; average: number }[];
  funnel: { status: string; count: number }[];
  distribution: { band: string; count: number }[];
  drive_eligibility: { id: string; position: string; eligible: number }[];
  method: string;
};
export function AnalyticsPage({ user }: { user: User }) {
  const reduced = useReducedMotion();
  const [search, setSearch] = useState(""),
    [department, setDepartment] = useState(""),
    [batch, setBatch] = useState(""),
    [drive, setDrive] = useState(""),
    [topic, setTopic] = useState(""),
    [assessment, setAssessment] = useState(""),
    [from, setFrom] = useState(""),
    [to, setTo] = useState(""),
    [selected, setSelected] = useState<string>();
  const [company, setCompany] = useState("");
  const params = new URLSearchParams({
    q: search,
    department,
    drive,
    topic,
    assessment,
    company,
  });
  if (batch) params.set("batch", batch);
  if (from) params.set("date_from", from + "T00:00:00");
  if (to) params.set("date_to", to + "T23:59:59");
  const data = useQuery({
    queryKey: ["analytics", params.toString()],
    queryFn: () => api<Analytics>(`/analytics?${params}`),
  });
  const departments = useQuery({
    queryKey: ["departments"],
    queryFn: () => api<{ id: string; name: string }[]>("/departments"),
    enabled: user.role !== "student",
  });
  const companies = useQuery({
    queryKey: ["companies"],
    queryFn: () => api<{ id: string; name: string }[]>("/companies"),
    enabled: user.role !== "student",
  });
  const drives = useQuery({
    queryKey: ["drives"],
    queryFn: () => api<Drive[]>("/drives"),
  });
  const assessments = useQuery({
    queryKey: ["assessments"],
    queryFn: () => api<{ id: string; title: string }[]>("/assessments"),
  });
  const selectedRow = data.data?.students.find((s) => s.id === selected);
  const [page, setPage] = useState(0);
  const pages = Math.max(1, Math.ceil((data.data?.students.length || 0) / 20));
  const currentPage = Math.min(page, pages - 1);
  const visibleStudents =
    data.data?.students.slice(currentPage * 20, (currentPage + 1) * 20) || [];
  return (
    <>
      <PageHeading
        eyebrow="MEASURED PROGRESS"
        title={
          user.role === "student"
            ? "See your preparation take shape."
            : "A clearer view of student preparation."
        }
        description="Every metric comes from stored records. Missing evidence prompts support, not a judgment of ability."
      >
        {user.role !== "student" && (
          <Button asChild variant="outline">
            <a href={`/api/analytics/export.csv?${params}`}>
              <Download size={16} />
              Export authorized cohort
            </a>
          </Button>
        )}
      </PageHeading>
      <div className="card filter-grid">
        <label className="field">
          Student search
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Name or roll number"
          />
        </label>
        {user.role !== "student" && (
          <label className="field">
            Department
            <select
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
            >
              <option value="">All departments</option>
              {departments.data?.map((d) => (
                <option value={d.id} key={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="field">
          Batch
          <input
            type="number"
            value={batch}
            onChange={(e) => setBatch(e.target.value)}
            placeholder="All batches"
          />
        </label>
        {user.role !== "student" && (
          <label className="field">
            Company
            <select
              value={company}
              onChange={(e) => setCompany(e.target.value)}
            >
              <option value="">All companies</option>
              {companies.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="field">
          Drive
          <select value={drive} onChange={(e) => setDrive(e.target.value)}>
            <option value="">All drives</option>
            {drives.data?.map((d) => (
              <option value={d.id} key={d.id}>
                {d.company_name} · {d.position}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Assessment
          <select
            value={assessment}
            onChange={(e) => setAssessment(e.target.value)}
          >
            <option value="">All assessments</option>
            {assessments.data?.map((a) => (
              <option value={a.id} key={a.id}>
                {a.title}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Topic
          <input
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. SQL"
          />
        </label>
        <label className="field">
          From
          <input
            type="date"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
        </label>
        <label className="field">
          Through
          <input
            type="date"
            value={to}
            onChange={(e) => setTo(e.target.value)}
          />
        </label>
      </div>
      <div className="between" style={{ marginBlock: 18 }}>
        <span className="hint">
          {data.data?.total || 0} students · Page {currentPage + 1} of {pages}
        </span>
        <div className="row">
          <Button
            size="sm"
            variant="outline"
            disabled={!currentPage}
            onClick={() => setPage(currentPage - 1)}
          >
            Previous students
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={currentPage >= pages - 1}
            onClick={() => setPage(currentPage + 1)}
          >
            Next students
          </Button>
        </div>
      </div>
      {data.error ? (
        <Failure error={data.error} />
      ) : !data.data ? (
        <Skeleton />
      ) : (
        <>
          <div className="grid-3" style={{ marginBlock: 24 }}>
            {[
              ["Registered students", data.data.total],
              ["Activated accounts", data.data.activated],
              ["Resume completion", `${data.data.resume_rate}%`],
              ["Assessment participation", `${data.data.participation_rate}%`],
              [
                "Mean objective score",
                data.data.average === null
                  ? "No scores"
                  : `${data.data.average}%`,
              ],
              [
                "Median objective score",
                data.data.median === null
                  ? "No scores"
                  : `${data.data.median}%`,
              ],
            ].map(([label, value]) => (
              <article className="card card-pad" key={label}>
                <p>{label}</p>
                <strong className="alignment-number">{value}</strong>
              </article>
            ))}
          </div>
          <div className="grid-2">
            <Chart
              title="Topic performance"
              data={data.data.topics}
              name="topic"
              value="average"
            />
            <Chart
              title="Current application outcomes"
              data={data.data.funnel}
              name="status"
              value="count"
            />
            <Chart
              title="Objective score distribution"
              data={data.data.distribution}
              name="band"
              value="count"
            />
            <Chart
              title="Students meeting academic criteria"
              data={data.data.drive_eligibility}
              name="position"
              value="eligible"
            />
          </div>
          <section className="card card-pad" style={{ marginTop: 24 }}>
            <h2>Student performance & coaching</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Student</th>
                    <th>Assessment average</th>
                    <th>Learning tasks</th>
                    <th>Applications</th>
                    <th>Coaching context</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleStudents.map((s) => (
                    <tr key={s.id}>
                      <td>
                        <button
                          className="text-link"
                          onClick={() => setSelected(s.id)}
                        >
                          {s.name}
                        </button>
                        <p className="hint">{s.roll_no}</p>
                      </td>
                      <td>
                        {s.average === null ? "No score" : `${s.average}%`}
                        <p className="hint">{s.attempts} attempts</p>
                      </td>
                      <td>
                        {s.completed_tasks}/{s.total_tasks}
                      </td>
                      <td>
                        {s.applications} · {s.offers} offers
                      </td>
                      <td>
                        {s.support_reasons.join(" · ") ||
                          "Continue regular practice"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <section className="card card-pad" style={{ marginTop: 24 }}>
            <h2>Evidence coverage matrix</h2>
            <p className="hint">
              Green = approved assessment evidence; amber = claim. Empty cells
              mean no stored evidence.
            </p>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Student</th>
                    {[
                      ...new Set(
                        data.data.students.flatMap((s) =>
                          s.skills.map((e) => e.skill),
                        ),
                      ),
                    ].map((s) => (
                      <th key={s}>{s}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {visibleStudents.map((s) => (
                    <tr key={s.id}>
                      <td>{s.name}</td>
                      {[
                        ...new Set(
                          data.data!.students.flatMap((s) =>
                            s.skills.map((e) => e.skill),
                          ),
                        ),
                      ].map((skill) => {
                        const evidence = s.skills.filter(
                          (e) => e.skill === skill,
                        );
                        return (
                          <td key={skill}>
                            <Badge
                              tone={
                                evidence.some((e) =>
                                  [
                                    "assessment_verified",
                                    "faculty_verified",
                                  ].includes(e.evidence_type),
                                )
                                  ? "green"
                                  : evidence.length
                                    ? "amber"
                                    : "neutral"
                              }
                            >
                              {evidence.some((e) =>
                                [
                                  "assessment_verified",
                                  "faculty_verified",
                                ].includes(e.evidence_type),
                              )
                                ? "Demonstrated"
                                : evidence.length
                                  ? "Claim"
                                  : "—"}
                            </Badge>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          {selectedRow && (
            <section className="card card-pad" style={{ marginTop: 24 }}>
              <h2>{selectedRow.name} · preparation detail</h2>
              <div style={{ height: 240 }}>
                <ResponsiveContainer>
                  <LineChart data={selectedRow.trend}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="title" />
                    <YAxis domain={[0, 100]} />
                    <Tooltip />
                    <Line
                      dataKey="score"
                      stroke="#2563eb"
                      connectNulls={false}
                      isAnimationActive={!reduced}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <MatchingPanel
                studentId={selectedRow.id}
                driveId={drive || undefined}
              />
              {[
                "institution_admin",
                "platform_admin",
                "placement_officer",
              ].includes(user.role) && (
                <ExaminerReview studentId={selectedRow.id} />
              )}
            </section>
          )}
          <p className="hint">{data.data.method}</p>
        </>
      )}
    </>
  );
}

function Chart({
  title,
  data,
  name,
  value,
}: {
  title: string;
  data: object[];
  name: string;
  value: string;
}) {
  const reduced = useReducedMotion();
  return (
    <section className="card card-pad">
      <h2>{title}</h2>
      {data.length ? (
        <div style={{ height: 260, marginTop: 20 }}>
          <ResponsiveContainer>
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey={name} fontSize={11} />
              <YAxis fontSize={11} />
              <Tooltip />
              <Bar
                dataKey={value}
                fill="#2563eb"
                radius={[5, 5, 0, 0]}
                animationDuration={500}
                isAnimationActive={!reduced}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <Empty
          title="No recorded results yet"
          description="This chart appears after relevant activity is recorded."
        />
      )}
    </section>
  );
}

type EvidenceDoc = {
  id: string;
  title: string;
  filename: string;
  category: string;
  status: string;
  version: number;
  index_status?: string;
  chunks?: number;
  expired: boolean;
  review_note?: string;
};
type Requirement = {
  id: string;
  title: string;
  description: string;
  status: string;
  finding: string;
  sources: EvidenceDoc[];
};
type Answer = {
  answer: string;
  provider: string;
  retrieval_method: string;
  sources: {
    id: string;
    document_id: string;
    title: string;
    quote: string;
    page: number | null;
    version: number;
  }[];
};
export function EvidencePage({
  user,
  section,
}: {
  user: User;
  section: string;
}) {
  const docs = useQuery({
    queryKey: ["evidence-documents"],
    queryFn: () => api<EvidenceDoc[]>("/evidence/documents"),
  });
  const requirements = useQuery({
    queryKey: ["requirements"],
    queryFn: () => api<Requirement[]>("/evidence/requirements"),
  });
  const departments = useQuery({
    queryKey: ["departments"],
    queryFn: () => api<{ id: string; name: string }[]>("/departments"),
  });
  const [search, setSearch] = useState(""),
    [answer, setAnswer] = useState<Answer | null>(null),
    [mapped, setMapped] = useState<string[]>([]);
  const { busy, act } = useAction();
  const admin = ["institution_admin", "platform_admin"].includes(user.role);
  const staff = useQuery({
    queryKey: ["staff"],
    queryFn: () => api<{ id: string; full_name: string }[]>("/staff"),
    enabled: admin,
  });
  const [requirementId, setRequirementId] = useState("");
  const [requirementTitle, setRequirementTitle] = useState("");
  const [requirementDescription, setRequirementDescription] = useState("");
  return (
    <>
      <PageHeading
        eyebrow="COLLEGEOPS · EVIDENCE WORKSPACE"
        title={
          section === "review"
            ? "Review with the source in view."
            : "Institutional knowledge, with evidence."
        }
        description="Upload and version documents, map institution-defined requirements, and ask questions of approved evidence. This is preparation assistance, not compliance certification."
      >
        <Button asChild variant="outline">
          <a href="/api/evidence/report.csv">
            <Download size={16} />
            Export draft report
          </a>
        </Button>
      </PageHeading>
      <div className="grid-3">
        {[
          ["Evidence documents", docs.data?.length || 0],
          [
            "Approved evidence",
            docs.data?.filter((d) => d.status === "approved" && !d.expired)
              .length || 0,
          ],
          [
            "Requirements needing review",
            requirements.data?.filter((r) => r.status !== "evidence_available")
              .length || 0,
          ],
        ].map(([title, value]) => (
          <article className="card card-pad" key={title}>
            <p>{title}</p>
            <strong className="alignment-number">{value}</strong>
          </article>
        ))}
      </div>
      <details className="card card-pad" style={{ marginTop: 24 }}>
        <summary>
          <Upload size={16} /> Upload evidence or a new version
        </summary>
        <form
          className="form-grid"
          style={{ marginTop: 20 }}
          onSubmit={(e) => {
            e.preventDefault();
            const form = new FormData(e.currentTarget);
            void act(
              () => api("/evidence/documents", { method: "POST", body: form }),
              "Evidence uploaded and indexed",
            );
          }}
        >
          <label className="field">
            Document title
            <input name="title" required minLength={2} maxLength={200} />
          </label>
          <label className="field">
            Category
            <input
              name="category"
              defaultValue="Department activity"
              required
            />
          </label>
          <label className="field">
            Department
            <select name="department_id">
              <option value="">Institution-wide / my department</option>
              {departments.data?.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Version of
            <select name="parent_id">
              <option value="">New document</option>
              {docs.data?.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.title} · v{d.version}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Evidence owner
            <select name="owner_id">
              <option value={user.id}>{user.full_name} · me</option>
              {staff.data
                ?.filter((s) => s.id !== user.id)
                .map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.full_name}
                  </option>
                ))}
            </select>
          </label>
          <label className="field">
            Expiry date · optional
            <input type="date" name="expires_at" />
          </label>
          <label className="field">
            PDF, DOCX or UTF-8 TXT · up to 8 MB
            <input type="file" name="file" accept=".pdf,.docx,.txt" required />
          </label>
          <Button disabled={busy}>
            {busy ? "Processing evidence…" : "Upload & index"}
          </Button>
        </form>
      </details>
      <section className="card card-pad" style={{ marginTop: 24 }}>
        <div className="between">
          <h2>Evidence vault</h2>
          <div className="search-field">
            <Search size={16} />
            <input
              aria-label="Search evidence"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search documents…"
            />
          </div>
        </div>
        {docs.error ? (
          <Failure error={docs.error} />
        ) : (
          <div className="evidence-list">
            {docs.data
              ?.filter((d) =>
                `${d.title} ${d.category}`
                  .toLowerCase()
                  .includes(search.toLowerCase()),
              )
              .map((d) => (
                <article className="evidence-row" key={d.id}>
                  <div>
                    <a
                      className="text-link"
                      href={`/api/documents/${d.id}/download`}
                    >
                      {d.title} · v{d.version}
                    </a>
                    <p className="hint">
                      {d.category} · {d.chunks || 0} chunks ·{" "}
                      {d.index_status || "Not indexed"}
                    </p>
                    {d.review_note && (
                      <p className="hint">Review: {d.review_note}</p>
                    )}
                  </div>
                  <div className="row" style={{ flexWrap: "wrap" }}>
                    <Badge
                      tone={
                        d.expired
                          ? "amber"
                          : d.status === "approved"
                            ? "green"
                            : "neutral"
                      }
                    >
                      {d.expired ? "Expired" : d.status}
                    </Badge>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={busy}
                      onClick={() =>
                        act(
                          () => send(`/evidence/documents/${d.id}/reindex`),
                          "Document reindexed",
                        )
                      }
                    >
                      Reindex
                    </Button>
                    {admin && d.status !== "approved" && (
                      <Button
                        size="sm"
                        disabled={busy}
                        onClick={() =>
                          act(
                            () =>
                              send(
                                `/evidence/documents/${d.id}/review`,
                                {
                                  status: "approved",
                                  note: "Reviewed source document and approved its use for institutional evidence retrieval.",
                                },
                                "PUT",
                              ),
                            "Evidence approved",
                          )
                        }
                      >
                        Approve source
                      </Button>
                    )}
                    {admin && (
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={busy}
                        onClick={() => {
                          if (
                            window.confirm(
                              `Delete ${d.title} and its private file? Remove newer versions first.`,
                            )
                          )
                            void act(
                              () =>
                                api(`/evidence/documents/${d.id}`, {
                                  method: "DELETE",
                                }),
                              "Evidence deleted",
                            );
                        }}
                      >
                        Delete
                      </Button>
                    )}
                  </div>
                </article>
              ))}
          </div>
        )}
      </section>
      <section className="card card-pad" style={{ marginTop: 24 }}>
        <div className="row">
          <ShieldCheck color="#0d9488" />
          <h2>Ask the approved evidence</h2>
        </div>
        <form
          className="row"
          style={{ marginTop: 20 }}
          onSubmit={async (e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            const result = (await act(
              () =>
                send<Answer>("/evidence/ask", { question: f.get("question") }),
              "Source search complete",
            )) as Answer | undefined;
            if (result) setAnswer(result);
          }}
        >
          <input
            name="question"
            required
            minLength={3}
            maxLength={2000}
            placeholder="What evidence supports our faculty development activity?"
            aria-label="Evidence question"
          />
          <Button disabled={busy}>Find evidence</Button>
        </form>
        {answer && (
          <div style={{ marginTop: 20 }}>
            <Badge>{answer.provider.replaceAll("_", " ")}</Badge>
            <p className="hint">Retrieval: {answer.retrieval_method}</p>
            <p style={{ whiteSpace: "pre-wrap" }}>{answer.answer}</p>
            {answer.sources.map((s, i) => (
              <a
                className="source-chip"
                key={s.id}
                href={`/api/documents/${s.document_id}/download`}
              >
                [{i + 1}] {s.title} · v{s.version}
                {s.page ? ` · page ${s.page}` : " · page unavailable"}
              </a>
            ))}
          </div>
        )}
      </section>
      <section className="card card-pad" style={{ marginTop: 24 }}>
        <h2>Configured requirements & draft findings</h2>
        <p className="hint">
          Your institution defines requirements. Evidence availability does not
          certify adequacy or compliance.
        </p>
        {requirements.data?.map((r) => (
          <article className="evidence-row" key={r.id}>
            <div>
              <h3>{r.title}</h3>
              <p>{r.description}</p>
              <p className="hint">{r.finding}</p>
              <div className="chips">
                {r.sources.map((s) => (
                  <a
                    key={s.id}
                    href={`/api/documents/${s.id}/download`}
                    className="text-link"
                  >
                    {s.title} · v{s.version}
                  </a>
                ))}
              </div>
            </div>
            <Badge tone={r.status === "evidence_available" ? "green" : "amber"}>
              {r.status.replaceAll("_", " ")}
            </Badge>
          </article>
        ))}
        <details style={{ marginTop: 20 }}>
          <summary>
            <FileCheck2 size={16} /> Define a requirement & map evidence
          </summary>
          <form
            className="form-stack"
            style={{ marginTop: 18 }}
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              void act(
                () =>
                  send(
                    requirementId
                      ? `/evidence/requirements/${requirementId}`
                      : "/evidence/requirements",
                    {
                      title: f.get("title"),
                      description: f.get("description"),
                      document_ids: mapped,
                    },
                    requirementId ? "PUT" : "POST",
                  ),
                "Requirement saved",
              );
            }}
          >
            <label className="field">
              Create or update
              <select
                value={requirementId}
                onChange={(e) => {
                  setRequirementId(e.target.value);
                  const r = requirements.data?.find(
                    (r) => r.id === e.target.value,
                  );
                  setRequirementTitle(r?.title || "");
                  setRequirementDescription(r?.description || "");
                  setMapped(r?.sources.map((s) => s.id) || []);
                }}
              >
                <option value="">New requirement</option>
                {requirements.data?.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.title}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              Requirement title
              <input
                name="title"
                required
                minLength={3}
                value={requirementTitle}
                onChange={(e) => setRequirementTitle(e.target.value)}
              />
            </label>
            <label className="field">
              Institution-specific description
              <textarea
                name="description"
                required
                minLength={3}
                value={requirementDescription}
                onChange={(e) => setRequirementDescription(e.target.value)}
              />
            </label>
            <fieldset>
              <legend>Supporting documents</legend>
              {docs.data?.map((d) => (
                <label className="answer-option" key={d.id}>
                  <input
                    type="checkbox"
                    checked={mapped.includes(d.id)}
                    onChange={(e) =>
                      setMapped(
                        e.target.checked
                          ? [...mapped, d.id]
                          : mapped.filter((id) => id !== d.id),
                      )
                    }
                  />
                  {d.title}
                </label>
              ))}
            </fieldset>
            <Button disabled={busy}>Save requirement mapping</Button>
          </form>
        </details>
      </section>
    </>
  );
}

export function DriveIntelligence({
  drive,
  user,
}: {
  drive: Drive;
  user: User;
}) {
  const { busy, act } = useAction();
  const [review, setReview] = useState<{
    extracted: {
      skills: { skill: string; priority: string; quote: string }[];
      ambiguities: string[];
    };
    review: object;
  } | null>(null);
  const [matrix, setMatrix] = useState<
    { skill: string; priority: string; quote: string }[]
  >([]);
  const [unresolved, setUnresolved] = useState("");
  if (user.role === "student")
    return (
      <>
        <MatchingPanel driveId={drive.id} />
        <form
          className="form-stack"
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            void act(
              () =>
                send(`/drives/${drive.id}/appeal`, {
                  explanation: f.get("explanation"),
                }),
              "Correction request submitted for officer review",
            );
          }}
        >
          <label className="field">
            Request an eligibility correction
            <textarea
              name="explanation"
              minLength={10}
              maxLength={2000}
              required
              placeholder="Explain the academic data or condition needing review."
            />
          </label>
          <Button variant="outline" disabled={busy}>
            Submit correction request
          </Button>
        </form>
      </>
    );
  if (
    !["institution_admin", "platform_admin", "placement_officer"].includes(
      user.role,
    )
  )
    return null;
  const next: Record<string, string> = {
    reviewed: "published",
    published: "open",
    open: "closed",
    closed: "completed",
  };
  return (
    <section className="card card-pad">
      <h3>Requirement review & lifecycle</h3>
      <p className="hint">
        DRAFT → REVIEWED → PUBLISHED → OPEN → CLOSED → COMPLETED. Published
        officer-authored forms also record explicit human approval.
      </p>
      {["draft", "reviewed"].includes(drive.status) && (
        <Button
          variant="outline"
          disabled={busy}
          onClick={async () => {
            const r = (await act(
              () => api(`/drives/${drive.id}/review`),
              "Extracted requirements ready for review",
            )) as typeof review;
            if (r) {
              setReview(r);
              setMatrix(
                r.extracted.skills.map((s) => ({
                  ...s,
                  priority: s.priority,
                })),
              );
            }
          }}
        >
          Analyze job description
        </Button>
      )}
      {review && (
        <form
          style={{ marginTop: 16 }}
          onSubmit={(e) => {
            e.preventDefault();
            void act(
              () =>
                send(`/drives/${drive.id}/review`, {
                  approved_skills: matrix,
                  unresolved_conditions: unresolved
                    .split("\n")
                    .map((s) => s.trim())
                    .filter(Boolean),
                  confirm_explicit_conditions: true,
                }),
              "Drive reviewed. Reopen the drive to publish.",
            );
          }}
        >
          {matrix.map((s, i) => (
            <div className="evidence-row" key={s.skill}>
              <div>
                <strong>{s.skill}</strong>
                <p className="hint">{s.quote}</p>
              </div>
              <select
                aria-label={`${s.skill} requirement priority`}
                value={s.priority}
                onChange={(e) =>
                  setMatrix(
                    matrix.map((item, index) =>
                      index === i
                        ? { ...item, priority: e.target.value }
                        : item,
                    ),
                  )
                }
              >
                <option value="unclear">Choose a priority after review</option>
                <option value="required">Required</option>
                <option value="preferred">Preferred</option>
              </select>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() =>
                  setMatrix(matrix.filter((_, index) => index !== i))
                }
              >
                Remove
              </Button>
            </div>
          ))}
          <label className="field">
            Conditions needing human clarification
            <textarea
              value={unresolved}
              onChange={(e) => setUnresolved(e.target.value)}
              placeholder="One unresolved company condition per line. Eligibility stays open for human review."
              maxLength={3000}
            />
          </label>
          <label className="answer-option">
            <input type="checkbox" required />I verified the skills and academic
            conditions against actual company requirements.
          </label>
          <Button
            disabled={busy || matrix.some((s) => s.priority === "unclear")}
          >
            Approve requirements
          </Button>
        </form>
      )}
      {next[drive.status] && (
        <Button
          style={{ marginTop: 16 }}
          disabled={busy}
          onClick={() =>
            act(
              () =>
                send(
                  `/drives/${drive.id}/transition?status=${next[drive.status]}`,
                ),
              "Drive status updated; reopen to see the next step",
            )
          }
        >
          Move to {next[drive.status]}
        </Button>
      )}
    </section>
  );
}

export function AppealsPage() {
  const appeals = useQuery({
    queryKey: ["appeals"],
    queryFn: () =>
      api<
        { id: string; student: string; status: string; explanation: string }[]
      >("/eligibility-appeals"),
  });
  const { busy, act } = useAction();
  return (
    <details className="card card-pad" style={{ marginTop: 24 }}>
      <summary>Eligibility correction requests</summary>
      {appeals.data?.map((a) => (
        <form
          key={a.id}
          className="form-stack"
          style={{ marginTop: 20 }}
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            void act(
              () =>
                send(
                  `/eligibility-appeals/${a.id}`,
                  { status: f.get("status"), decision: f.get("decision") },
                  "PUT",
                ),
              "Decision recorded",
            );
          }}
        >
          <h3>
            {a.student} · {a.status}
          </h3>
          <p>{a.explanation}</p>
          <label className="field">
            Decision
            <select name="status">
              <option value="approved">Approve eligibility correction</option>
              <option value="declined">Decline with explanation</option>
            </select>
          </label>
          <label className="field">
            Evidence and reason
            <textarea name="decision" required minLength={10} />
          </label>
          <Button disabled={busy}>Record human review</Button>
        </form>
      ))}
      {!appeals.data?.length && (
        <p className="hint">No requests currently recorded.</p>
      )}
    </details>
  );
}
