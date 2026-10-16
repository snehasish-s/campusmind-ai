"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import {
  ArrowUpRight,
  CalendarDays,
  CheckCircle2,
  Clock3,
  FileCheck2,
  Fingerprint,
  Link2,
  ShieldCheck,
  Workflow,
} from "lucide-react";
import { api, send, type User } from "@/lib/api";
import { Button } from "../ui/button";
import { Badge, Empty, Failure, PageHeading, Skeleton } from "../ui/common";
import { useAction } from "./intelligence";

export const campusDate = (value: string | null | undefined) =>
  value
    ? new Date(
        /(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : value + "Z",
      ).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })
    : "No deadline";

type DailyItem = {
  id: string;
  title: string;
  kind: string;
  due_at: string | null;
  href: string;
  reason: string;
  priority: number;
};
type ScheduleSlot = {
  id: string;
  subject: string;
  weekday: number;
  starts: string;
  ends: string;
  room: string;
  valid_from: string;
  valid_until: string;
};
type Day = {
  items: DailyItem[];
  conflicts: { kind: string; message: string }[];
  timetable: ScheduleSlot[];
  generated_at: string;
};

export function TodayPage({ user }: { user: User }) {
  const query = useQuery({
    queryKey: ["campus-today"],
    queryFn: () => api<Day>("/campus/today"),
    refetchInterval: 30000,
  });
  const [filter, setFilter] = useState("all"),
    [saved, setSaved] = useState(false);
  const { busy, act } = useAction();
  return (
    <>
      <PageHeading
        eyebrow="CAMPUS HUB · YOUR DAY"
        title={`Good to see you, ${user.full_name.split(" ")[0]}.`}
        description="Classes, deadlines and opportunities, together. Your institution sends official updates directly to this workspace."
      >
        <Button variant="outline" asChild>
          <Link href="/app/campus">
            Official noticeboard <ArrowUpRight size={16} />
          </Link>
        </Button>
      </PageHeading>
      <div className="daily-banner">
        <div>
          <Badge tone="green">Automatically organized</Badge>
          <h2>Your next step, with a reason.</h2>
          <p>
            Urgent deadlines come first, followed by today’s classes and
            upcoming work. Every recommendation explains why it appears.
          </p>
        </div>
        <CalendarDays size={60} aria-hidden="true" />
      </div>
      {query.error && (
        <Failure error={query.error} retry={() => void query.refetch()} />
      )}
      {query.isPending && <Skeleton rows={5} />}
      {query.data && (
        <>
          <div className="metric-grid campus-metrics">
            {[
              [
                "Pending actions",
                query.data.items.filter((i) => i.kind !== "class").length,
              ],
              [
                "Classes today",
                query.data.items.filter((i) => i.kind === "class").length,
              ],
              ["Workload alerts", query.data.conflicts.length],
            ].map(([label, value]) => (
              <div className="card card-pad" key={label}>
                <p>{label}</p>
                <h2>{value}</h2>
              </div>
            ))}
          </div>
          {query.data.conflicts.map((c, i) => (
            <div className="campus-alert" key={i}>
              <Clock3 size={19} />
              <p>{c.message}</p>
            </div>
          ))}
          <div className="campus-two-col">
            <section className="card card-pad">
              <div className="row spread">
                <h2>Your action list</h2>
                <select
                  aria-label="Filter daily actions"
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                >
                  {[
                    "all",
                    "assignment",
                    "class",
                    "notice",
                    "fee",
                    "drive",
                    "roadmap",
                    "learning",
                    "assessment",
                  ].map((f) => (
                    <option value={f} key={f}>
                      {f === "all" ? "All actions" : f}
                    </option>
                  ))}
                </select>
              </div>
              {query.data.items
                .filter((i) => filter === "all" || i.kind === filter)
                .map((item, index) => (
                  <motion.article
                    key={item.id}
                    className="daily-action"
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: Math.min(index * 0.03, 0.3) }}
                  >
                    <div className={`action-dot priority-${item.priority}`} />
                    <div>
                      <div className="row">
                        <Badge>{item.kind}</Badge>
                        <span className="hint">{campusDate(item.due_at)}</span>
                      </div>
                      <h3>{item.title}</h3>
                      <p className="hint">{item.reason}</p>
                    </div>
                    <Button variant="ghost" size="icon" asChild>
                      <Link href={item.href} aria-label={`Open ${item.title}`}>
                        <ArrowUpRight size={18} />
                      </Link>
                    </Button>
                  </motion.article>
                ))}
              {!query.data.items.length && (
                <Empty
                  title="You’re up to date"
                  description="Your next classes, notices and tasks will appear here as your college publishes them."
                />
              )}
            </section>
            <aside className="campus-stack">
              <section className="card card-pad">
                <ShieldCheck className="text-teal" />
                <h2>Built around your cohort</h2>
                <p className="hint">
                  Your branch, year, semester and section determine academic
                  updates. Fee invoices stay attached to your account after a
                  section change.
                </p>
                <Button variant="outline" asChild>
                  <Link href="/app/passport">Open my skill passport</Link>
                </Button>
              </section>
              <section className="card card-pad">
                <h2>Keep your timetable offline</h2>
                <p className="hint">
                  Optional: save a timetable snapshot on this device. Avoid
                  shared computers. Notices and payments always require a
                  connection. Sign out to remove the saved schedule.
                </p>
                <Button
                  disabled={!query.data || saved}
                  variant="outline"
                  onClick={() => {
                    localStorage.setItem(
                      "cm-offline-timetable",
                      JSON.stringify({
                        timetable: query.data!.timetable,
                        saved_at: new Date().toISOString(),
                      }),
                    );
                    setSaved(true);
                  }}
                >
                  {saved ? "Snapshot saved" : "Save timetable on this device"}
                </Button>
                <Link className="text-link" href="/offline">
                  Open offline timetable
                </Link>
              </section>
              <section className="card card-pad">
                <h2>Desktop reminders</h2>
                <p className="hint">
                  Receive browser alerts for new in-app notifications while
                  CampusMind is open. Your browser may require permission.
                </p>
                <Button
                  disabled={busy}
                  variant="outline"
                  onClick={() =>
                    void act(async () => {
                      if (!("Notification" in window))
                        throw new Error(
                          "This browser does not support desktop notifications.",
                        );
                      if (
                        (await Notification.requestPermission()) !== "granted"
                      )
                        throw new Error(
                          "Notification permission was not granted.",
                        );
                      localStorage.setItem("cm-notifications", "enabled");
                    }, "Browser alerts enabled")
                  }
                >
                  Enable browser alerts
                </Button>
              </section>
            </aside>
          </div>
        </>
      )}
    </>
  );
}

type Rubric = { label: string; maximum: number };
type Submission = {
  id: string;
  user_id: string;
  student: string;
  roll_no: string;
  version: number;
  content: string;
  filename: string | null;
  status: string;
  late: boolean;
  rubric: Rubric[];
  skills: string[];
  marks: number[];
  score: number | null;
  feedback: string;
  created_at: string;
  reviewed_at: string | null;
};
type Assignment = {
  id: string;
  title: string;
  message: string;
  subject: string;
  due_at: string | null;
  filename: string | null;
  can_manage: boolean;
  rubric: Rubric[];
  skills: string[];
  allow_late: boolean;
  submissions: Submission[];
};

export function AssignmentsPage({ user }: { user: User }) {
  const query = useQuery({
    queryKey: ["campus-assignments"],
    queryFn: () =>
      api<{ assignments: Assignment[]; taxonomy: string[] }>(
        "/campus/assignments",
      ),
    refetchInterval: 30000,
  });
  const [search, setSearch] = useState("");
  const student = user.role === "student";
  return (
    <>
      <PageHeading
        eyebrow="CAMPUS HUB · ACADEMIC WORK"
        title={student ? "Assignments & feedback" : "Review academic work"}
        description="Submit work, receive rubric-based feedback and build evidence of what you have demonstrated."
      >
        <Button variant="outline" asChild>
          <Link href="/app/campus">
            {student ? "View announcements" : "Publish an assignment"}
          </Link>
        </Button>
      </PageHeading>
      <input
        className="campus-search"
        aria-label="Search assignments"
        placeholder="Search title or subject"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      {query.isPending && <Skeleton />}
      {query.error && (
        <Failure error={query.error} retry={() => void query.refetch()} />
      )}
      <div className="campus-stack">
        {query.data?.assignments
          .filter((a) =>
            `${a.title} ${a.subject}`
              .toLowerCase()
              .includes(search.toLowerCase()),
          )
          .map((a) => (
            <AssignmentCard
              key={a.id}
              item={a}
              student={student}
              taxonomy={query.data.taxonomy}
            />
          ))}
      </div>
      {query.data && !query.data.assignments.length && (
        <Empty
          title="No assignments yet"
          description="Teachers publish assignments to exact teaching cohorts. Work and feedback appear here automatically."
        />
      )}
    </>
  );
}

function AssignmentCard({
  item: a,
  student,
  taxonomy,
}: {
  item: Assignment;
  student: boolean;
  taxonomy: string[];
}) {
  const { busy, act } = useAction();
  const [rubric, setRubric] = useState(a.rubric),
    [skills, setSkills] = useState(a.skills);
  const latest = a.submissions.filter(
    (s) =>
      !a.submissions.some(
        (other) => other.user_id === s.user_id && other.version > s.version,
      ),
  );
  return (
    <section className="card card-pad">
      <div className="row spread">
        <div className="row">
          <Badge tone="blue">{a.subject || "Academic work"}</Badge>
          <Badge>
            {student && latest.length
              ? latest[0].status
              : `${latest.length} submissions`}
          </Badge>
        </div>
        <span className="hint">Due {campusDate(a.due_at)}</span>
      </div>
      <h2 style={{ marginBlock: 12 }}>{a.title}</h2>
      <p className="preserve-text">{a.message}</p>
      {a.filename && (
        <Button asChild variant="outline" size="sm">
          <a href={`/api/campus/posts/${a.id}/attachment`}>
            Download assignment
          </a>
        </Button>
      )}
      <p className="hint">
        Rubric: {a.rubric.map((c) => `${c.label} ${c.maximum}`).join(" · ")} ·
        Total 100 marks{a.allow_late ? " · Late work allowed" : ""}
      </p>
      {!!a.skills.length && (
        <p className="hint">
          Mapped skills: {a.skills.join(", ")}. Faculty may verify evidence
          after review.
        </p>
      )}
      {a.can_manage && (
        <details className="campus-details">
          <summary>Configure rubric and skill evidence</summary>
          <form
            className="campus-stack"
            onSubmit={(e) => {
              e.preventDefault();
              const data = new FormData(e.currentTarget);
              void act(
                () =>
                  send(
                    `/campus/assignments/${a.id}/policy`,
                    {
                      rubric,
                      skills,
                      allow_late: data.get("allow_late") === "on",
                    },
                    "PUT",
                  ),
                "Assignment policy saved",
              );
            }}
          >
            <p className="hint">
              Set this before the first submission. Criteria must add up to 100;
              later edits are locked for fair grading.
            </p>
            {rubric.map((c, i) => (
              <div className="row" key={i}>
                <input
                  aria-label={`Criterion ${i + 1}`}
                  required
                  value={c.label}
                  onChange={(e) =>
                    setRubric((r) =>
                      r.map((x, j) =>
                        j === i ? { ...x, label: e.target.value } : x,
                      ),
                    )
                  }
                />
                <input
                  type="number"
                  min={1}
                  max={100}
                  required
                  aria-label={`Maximum marks ${i + 1}`}
                  value={c.maximum}
                  onChange={(e) =>
                    setRubric((r) =>
                      r.map((x, j) =>
                        j === i ? { ...x, maximum: +e.target.value } : x,
                      ),
                    )
                  }
                />
                <Button
                  type="button"
                  variant="ghost"
                  disabled={rubric.length === 1}
                  onClick={() => setRubric((r) => r.filter((_, j) => j !== i))}
                >
                  Remove
                </Button>
              </div>
            ))}
            <Button
              type="button"
              variant="outline"
              disabled={rubric.length >= 10}
              onClick={() =>
                setRubric((r) => [
                  ...r,
                  { label: "New criterion", maximum: 10 },
                ])
              }
            >
              Add criterion
            </Button>
            <div className="campus-chip-grid">
              {taxonomy.map((s) => (
                <label key={s}>
                  <input
                    type="checkbox"
                    checked={skills.includes(s)}
                    onChange={(e) =>
                      setSkills((v) =>
                        e.target.checked ? [...v, s] : v.filter((x) => x !== s),
                      )
                    }
                  />{" "}
                  {s}
                </label>
              ))}
            </div>
            <label>
              <input
                type="checkbox"
                name="allow_late"
                defaultChecked={a.allow_late}
              />{" "}
              Allow late submissions
            </label>
            <Button disabled={busy || !!a.submissions.length}>
              Save rubric
            </Button>
          </form>
        </details>
      )}
      {student && (
        <form
          className="campus-stack campus-details"
          onSubmit={(e) => {
            e.preventDefault();
            const form = e.currentTarget,
              data = new FormData(form);
            if (!(data.get("file") as File)?.size) data.delete("file");
            void act(async () => {
              await api(`/campus/assignments/${a.id}/submit`, {
                method: "POST",
                body: data,
              });
              form.reset();
            }, "Work submitted; previous versions are preserved");
          }}
        >
          <label className="field">
            Your response
            <textarea
              name="content"
              rows={4}
              maxLength={20000}
              placeholder="Explain your work or write your answer. Code text is reviewed by a teacher and is never executed."
            />
          </label>
          <label className="field">
            Attach work · PDF, DOCX or TXT · up to 8 MB
            <input name="file" type="file" accept=".pdf,.docx,.txt" />
          </label>
          <Button disabled={busy}>
            <FileCheck2 size={17} />
            {a.submissions.length
              ? "Submit a new version"
              : "Submit assignment"}
          </Button>
        </form>
      )}
      {a.submissions.map((s) => (
        <details
          className="campus-details"
          key={s.id}
          open={student && s.id === latest[0]?.id}
        >
          <summary>
            {s.student} · {s.roll_no} · v{s.version} · {s.status}
            {s.score !== null ? ` · ${s.score}/100` : ""}
            {s.late ? " · late" : ""}
          </summary>
          <p className="hint">Submitted {campusDate(s.created_at)}</p>
          <p className="preserve-text">{s.content}</p>
          {s.filename && (
            <Button variant="outline" asChild size="sm">
              <a
                href={`/api/campus/assignments/submissions/${s.id}/attachment`}
              >
                {s.filename}
              </a>
            </Button>
          )}
          {s.feedback && (
            <div className="campus-feedback">
              <strong>Faculty feedback</strong>
              <p className="preserve-text">{s.feedback}</p>
              {s.rubric.map((r, i) => (
                <p key={r.label}>
                  {r.label}: {s.marks[i] ?? "Pending"} / {r.maximum}
                </p>
              ))}
            </div>
          )}
          {a.can_manage && latest.some((x) => x.id === s.id) && (
            <form
              className="campus-stack"
              onSubmit={(e) => {
                e.preventDefault();
                const data = new FormData(e.currentTarget);
                void act(
                  () =>
                    send(
                      `/campus/assignments/submissions/${s.id}/review`,
                      {
                        marks: s.rubric.map((_, i) =>
                          Number(data.get(`mark_${i}`)),
                        ),
                        feedback: data.get("feedback"),
                        decision: data.get("decision"),
                        verify_skills: data.get("verify") === "on",
                      },
                      "PUT",
                    ),
                  "Review recorded and student notified",
                );
              }}
            >
              <div className="form-grid">
                {s.rubric.map((r, i) => (
                  <label className="field" key={r.label}>
                    {r.label} / {r.maximum}
                    <input
                      name={`mark_${i}`}
                      aria-label={`${r.label} marks for ${s.roll_no}`}
                      type="number"
                      min={0}
                      max={r.maximum}
                      required
                      defaultValue={s.marks[i] ?? 0}
                    />
                  </label>
                ))}
              </div>
              <label className="field">
                Feedback
                <textarea
                  name="feedback"
                  minLength={5}
                  maxLength={5000}
                  required
                  defaultValue={s.feedback}
                />
              </label>
              <label className="field">
                Decision
                <select name="decision">
                  <option value="graded">Grade submission</option>
                  <option value="returned">Return for revision</option>
                </select>
              </label>
              <label>
                <input
                  type="checkbox"
                  name="verify"
                  disabled={!s.skills.length}
                />{" "}
                Verify mapped skills from this work (requires ≥60/100)
              </label>
              <Button disabled={busy}>Save review & notify student</Button>
            </form>
          )}
        </details>
      ))}
    </section>
  );
}

type Evidence = {
  id: string;
  skill: string;
  evidence_type: string;
  status: string;
  quote?: string;
  provider?: string;
  score?: number;
  created_at: string;
  reviewer_id?: string;
  note?: string;
};
type Passport = {
  student: string;
  roll_no: string;
  method: string;
  evidence: Evidence[];
  counts: Record<string, number>;
};
type Share = {
  id: string;
  expires_at: string;
  revoked_at: string | null;
  count: number;
};
export function PassportPage() {
  const query = useQuery({
    queryKey: ["campus-passport"],
    queryFn: () => api<Passport>("/campus/passport"),
  });
  const shares = useQuery({
    queryKey: ["passport-shares"],
    queryFn: () => api<Share[]>("/campus/passport/shares"),
  });
  const accesses = useQuery({
    queryKey: ["privacy-activity"],
    queryFn: () =>
      api<{ id: string; action: string; actor: string; at: string }[]>(
        "/campus/privacy/activity",
      ),
  });
  const [selected, setSelected] = useState<string[]>([]),
    [shareUrl, setShareUrl] = useState("");
  const { busy, act } = useAction();
  return (
    <>
      <PageHeading
        eyebrow="CAMPUS HUB · SKILL EVIDENCE"
        title="My evidence passport"
        description="A transparent record of your claims and demonstrated work. You decide which evidence to share."
      />
      {query.isPending && <Skeleton />}
      {query.error && (
        <Failure error={query.error} retry={() => void query.refetch()} />
      )}
      {query.data && (
        <>
          <div className="metric-grid campus-metrics">
            {Object.entries(query.data.counts).map(([kind, count]) => (
              <div className="card card-pad" key={kind}>
                <ShieldCheck size={22} />
                <h2>{count}</h2>
                <p>{kind.replaceAll("_", " ")}</p>
              </div>
            ))}
          </div>
          <p className="hint">{query.data.method}</p>
          <section className="card card-pad">
            <h2>
              <Fingerprint size={20} /> Evidence trail
            </h2>
            {query.data.evidence.map((e) => (
              <article className="passport-evidence" key={e.id}>
                <label className="row">
                  <input
                    aria-label={`Share ${e.skill} evidence`}
                    type="checkbox"
                    disabled={["rejected", "challenged", "superseded"].includes(
                      e.status,
                    )}
                    checked={selected.includes(e.id)}
                    onChange={(event) =>
                      setSelected((v) =>
                        event.target.checked
                          ? [...v, e.id]
                          : v.filter((id) => id !== e.id),
                      )
                    }
                  />
                  <strong>{e.skill}</strong>
                  <Badge
                    tone={
                      e.evidence_type.includes("verified") ? "green" : "neutral"
                    }
                  >
                    {e.evidence_type.replaceAll("_", " ")}
                  </Badge>
                  <Badge>{e.status}</Badge>
                </label>
                {e.quote && <p className="preserve-text">{e.quote}</p>}
                <p className="hint">
                  {e.score !== undefined
                    ? `Recorded score: ${e.score}% · `
                    : ""}
                  {e.provider || "Recorded source"} · {campusDate(e.created_at)}
                </p>
              </article>
            ))}
            {!query.data.evidence.length && (
              <Empty
                title="Your evidence starts with your work"
                description="Complete an approved assessment or submit a skill-mapped assignment for faculty review. PlacementOS students can also analyze their resume."
              />
            )}
          </section>
          <section className="card card-pad" style={{ marginTop: 20 }}>
            <h2>Share selected evidence</h2>
            <p className="hint">
              The link reveals your name, selected skills, evidence types,
              recorded scores and dates. It excludes resume text, assignment
              content, contact details and registration number. Anyone holding
              the link can view it until expiry or revocation.
            </p>
            <form
              className="campus-stack"
              onSubmit={(e) => {
                e.preventDefault();
                const data = new FormData(e.currentTarget);
                void act(async () => {
                  const result = await send<{ token: string }>(
                    "/campus/passport/shares",
                    {
                      evidence_ids: selected,
                      hours: Number(data.get("hours")),
                      consent: data.get("consent") === "on",
                    },
                  );
                  setShareUrl(
                    `${window.location.origin}/share/${result.token}`,
                  );
                }, "Share link created");
              }}
            >
              <label className="field">
                Expires after
                <select name="hours">
                  <option value="24">24 hours</option>
                  <option value="72">3 days</option>
                  <option value="168">7 days</option>
                </select>
              </label>
              <label>
                <input type="checkbox" required name="consent" /> I consent to
                sharing my selected evidence and name.
              </label>
              <Button disabled={busy || !selected.length}>
                <Link2 size={16} />
                Create share link ({selected.length} selected)
              </Button>
            </form>
            {shareUrl && (
              <label className="field">
                Copy this link now; the token is shown only once
                <input
                  aria-label="Passport share URL"
                  readOnly
                  value={shareUrl}
                  onFocus={(e) => e.target.select()}
                />
              </label>
            )}
            {shares.error && <Failure error={shares.error} />}
            {shares.data?.map((s) => (
              <div className="row spread passport-evidence" key={s.id}>
                <p>
                  {s.count} evidence records · expires{" "}
                  {campusDate(s.expires_at)}
                  {s.revoked_at ? " · revoked" : ""}
                </p>
                <Button
                  variant="outline"
                  disabled={busy || !!s.revoked_at}
                  onClick={() =>
                    void act(
                      () =>
                        send(
                          `/campus/passport/shares/${s.id}`,
                          undefined,
                          "DELETE",
                        ),
                      "Share revoked",
                    )
                  }
                >
                  Revoke link
                </Button>
              </div>
            ))}
          </section>
        </>
      )}
      <section className="card card-pad" style={{ marginTop: 20 }}>
        <h2>Your privacy activity</h2>
        <p className="hint">
          Recent recorded profile, resume and passport accesses. Institution
          audit records support investigation and correction requests.
        </p>
        {accesses.error && <Failure error={accesses.error} />}
        {accesses.data?.map((e) => (
          <div className="passport-evidence" key={e.id}>
            <strong>
              {e.action.replaceAll(".", " ").replaceAll("_", " ")}
            </strong>
            <p className="hint">
              {e.actor} · {campusDate(e.at)}
            </p>
          </div>
        ))}
        {accesses.data?.length === 0 && <p>No access events recorded yet.</p>}
        <Button variant="outline" asChild>
          <a
            href="/api/privacy/export"
            download="campusmind-personal-export.json"
          >
            Export my data
          </a>
        </Button>
      </section>
    </>
  );
}

type AutomationPolicy = {
  enabled: boolean;
  assignments: boolean;
  fees: boolean;
  evidence: boolean;
};
export function AutomationsPage() {
  const query = useQuery({
    queryKey: ["campus-automations"],
    queryFn: () =>
      api<{
        policy: AutomationPolicy;
        last_run_at: string | null;
        last_result: { delivered?: number };
        deliveries: {
          id: string;
          title: string;
          source: string;
          created_at: string;
        }[];
      }>("/campus/automations"),
    refetchInterval: 30000,
  });
  const { busy, act } = useAction();
  return (
    <>
      <PageHeading
        eyebrow="CAMPUS HUB · AUTOMATION"
        title="Routine updates, delivered automatically."
        description="Configure once. The system routes official notices immediately and checks deadlines while the service is running."
      />
      {query.isPending && <Skeleton />}
      {query.error && (
        <Failure error={query.error} retry={() => void query.refetch()} />
      )}
      {query.data && (
        <div className="campus-two-col">
          <section className="card card-pad">
            <Workflow size={26} />
            <h2>Campus rules</h2>
            <form
              key={JSON.stringify(query.data.policy)}
              className="campus-stack"
              onSubmit={(e) => {
                e.preventDefault();
                const form = new FormData(e.currentTarget);
                void act(
                  () =>
                    send(
                      "/campus/automations",
                      Object.fromEntries(
                        ["enabled", "assignments", "fees", "evidence"].map(
                          (k) => [k, form.get(k) === "on"],
                        ),
                      ),
                      "PUT",
                    ),
                  "Automation settings saved",
                );
              }}
            >
              {(
                [
                  ["enabled", "Enable scheduled reminders"],
                  [
                    "assignments",
                    "Assignment reminder · within 24 hours · only if work is not submitted",
                  ],
                  ["fees", "Fee reminder · 7 days, 3 days, 1 day and overdue"],
                  [
                    "evidence",
                    "Evidence renewal · 7 days before expiry and once expired",
                  ],
                ] as const
              ).map(([key, label]) => (
                <label className="automation-rule" key={key}>
                  <input
                    type="checkbox"
                    name={key}
                    defaultChecked={query.data!.policy[key]}
                  />
                  <span>{label}</span>
                </label>
              ))}
              <Button disabled={busy}>Save automation settings</Button>
            </form>
            <p className="hint">
              One notification per recipient and reminder stage prevents
              duplicate alerts. Timetable and cohort changes already trigger
              targeted updates.
            </p>
            <p className="hint">
              Free hosting sleeps when idle. Missed deadline checks catch up
              when the service wakes or a student opens Today. Continuous,
              exact-time delivery needs an always-running worker.
            </p>
            <Button
              variant="outline"
              disabled={busy}
              onClick={() =>
                void act(
                  () => send("/campus/automations/run"),
                  "Reminder sweep finished",
                )
              }
            >
              Run a reminder sweep
            </Button>
            <p className="hint">
              Last run: {campusDate(query.data.last_run_at)} ·{" "}
              {query.data.last_result.delivered ?? 0} new reminders
            </p>
          </section>
          <section className="card card-pad">
            <h2>Delivery activity</h2>
            {query.data.deliveries.map((d) => (
              <div className="passport-evidence" key={d.id}>
                <Badge>{d.source}</Badge>
                <h3>{d.title}</h3>
                <p className="hint">{campusDate(d.created_at)}</p>
              </div>
            ))}
            {!query.data.deliveries.length && (
              <Empty
                title="No automated reminders yet"
                description="Reminders appear here when a configured deadline rule matches. Official notice delivery continues through Campus Hub."
              />
            )}
          </section>
        </div>
      )}
    </>
  );
}

type EvidenceMap = {
  requirements: { id: string; title: string; documents: string[] }[];
  documents: {
    id: string;
    title: string;
    status: string;
    version: number;
    owner: string;
    expires_at: string | null;
  }[];
};
export function EvidenceMapPage() {
  const query = useQuery({
    queryKey: ["evidence-map"],
    queryFn: () => api<EvidenceMap>("/campus/evidence-map"),
  });
  return (
    <>
      <PageHeading
        eyebrow="COLLEGEOPS · EVIDENCE RELATIONSHIPS"
        title="See what supports each requirement."
        description="Trace a requirement to its documents, owner, review state and expiry. This view supports preparation and coordinator review."
      >
        <Button asChild variant="outline">
          <Link href="/app/documents">Manage evidence</Link>
        </Button>
      </PageHeading>
      {query.isPending && <Skeleton />}
      {query.error && (
        <Failure error={query.error} retry={() => void query.refetch()} />
      )}
      <div className="campus-stack">
        {query.data?.requirements.map((r) => (
          <section className="card card-pad" key={r.id}>
            <div className="row spread">
              <h2>{r.title}</h2>
              <Badge tone={r.documents.length ? "blue" : "neutral"}>
                {r.documents.length
                  ? `${r.documents.length} mapped documents`
                  : "Missing evidence"}
              </Badge>
            </div>
            <div className="evidence-map-grid">
              {r.documents.map((id) => {
                const d = query.data.documents.find((d) => d.id === id);
                return (
                  d && (
                    <div className="evidence-map-node" key={id}>
                      <CheckCircle2 size={20} />
                      <h3>{d.title}</h3>
                      <Badge>{d.status}</Badge>
                      <p className="hint">
                        v{d.version} · {d.owner}
                        <br />
                        {d.expires_at
                          ? `Expires ${campusDate(d.expires_at)}`
                          : "No expiry assigned"}
                      </p>
                      <Link href="/app/documents" className="text-link">
                        Inspect document <ArrowUpRight size={14} />
                      </Link>
                    </div>
                  )
                );
              })}
            </div>
            {!r.documents.length && (
              <p className="hint">
                No source is mapped within your authorized scope. Upload
                evidence and request a human review before using it in a report.
              </p>
            )}
          </section>
        ))}
      </div>
      {query.data && !query.data.requirements.length && (
        <Empty
          title="Configure evidence requirements"
          description="Create requirements in CollegeOps and map supporting documents to start building the relationship view."
        />
      )}
    </>
  );
}
