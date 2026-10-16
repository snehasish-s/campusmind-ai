"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import {
  CheckCircle2,
  Sparkles,
  ArrowUpRight,
  BookOpen,
  Clock,
  Send,
  ShieldCheck,
} from "lucide-react";
import { toast } from "sonner";
import { api, send, type Drive, type User } from "@/lib/api";
import { Button } from "../ui/button";
import { Badge, Empty, Failure, PageHeading, Skeleton } from "../ui/common";

type Evidence = {
  id: string;
  skill: string;
  quote?: string;
  evidence_type: string;
  status: string;
  note?: string;
  score?: number;
  provider: string;
  ambiguous?: boolean;
  attempt_id?: string;
};
type Gap = {
  role: string;
  alignment_score: number | null;
  score_explanation: string;
  skills: {
    skill: string;
    state: string;
    recommendation: string;
    priority: string;
    evidence: Evidence[];
  }[];
  eligibility?: {
    status: string;
    checks: {
      rule: string;
      expected: unknown;
      actual: unknown;
      passes: boolean | null;
    }[];
  };
};
type Task = {
  id: string;
  title: string;
  status: string;
  hours: number;
  skill: string;
  objective: string;
  practice: string;
  prerequisites: string[];
  resource: { title: string; url: string };
  preserved_from?: string;
};
type Plan = {
  id: string;
  role: string;
  version: number;
  status: string;
  explanation: string;
  hours_budget: number;
  estimated_hours?: number;
  completed: number;
  total: number;
  tasks: Task[];
};
type Workflow = {
  id: string;
  status: string;
  provider: string;
  error?: string;
  result?: { answer?: string };
};
type Resource = {
  skill: string;
  title: string;
  url: string;
  prerequisites: string[];
  cost: string;
};

export function useAction() {
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  async function act(work: () => Promise<unknown>, message = "Saved") {
    setBusy(true);
    try {
      const result = await work();
      await client.invalidateQueries();
      toast.success(message);
      return result;
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return { busy, act };
}

export function WorkflowJobs() {
  const client = useQueryClient();
  const { busy, act } = useAction();
  const query = useQuery({
    queryKey: ["workflow-jobs"],
    queryFn: () =>
      api<
        {
          id: string;
          kind: string;
          status: string;
          provider: string;
          latency_ms?: number;
          error?: string;
          recoverable: boolean;
        }[]
      >("/workflows"),
    refetchInterval: (q) =>
      q.state.data?.some((r) => ["queued", "running"].includes(r.status))
        ? 2000
        : false,
  });
  const signature = query.data?.map((r) => `${r.id}:${r.status}`).join("|");
  useEffect(() => {
    if (signature)
      void client.invalidateQueries({
        predicate: (q) => q.queryKey[0] !== "workflow-jobs",
      });
  }, [signature, client]);
  if (!query.data?.length) return null;
  return (
    <details className="card card-pad" style={{ marginTop: 24 }}>
      <summary>Processing history & provider provenance</summary>
      {query.data.slice(0, 6).map((r) => (
        <div className="evidence-row" key={r.id}>
          <div>
            <strong>{r.kind.replaceAll("_", " ")}</strong>
            <p className="hint">
              {r.provider} {r.latency_ms != null ? `· ${r.latency_ms} ms` : ""}
            </p>
            {r.error && <p className="hint">{r.error}</p>}
          </div>
          <Badge
            tone={
              r.status === "completed"
                ? "green"
                : r.status === "failed"
                  ? "amber"
                  : "blue"
            }
          >
            {r.status}
          </Badge>
          {r.recoverable && (
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() =>
                act(() => send(`/workflows/${r.id}/retry`), "Workflow retried")
              }
            >
              Retry safely
            </Button>
          )}
        </div>
      ))}
    </details>
  );
}

async function runWorkflow(body: object) {
  let run = await send<Workflow>("/workflows", body);
  // Poll only this authorized job. Heavy local work runs on the single AI queue.
  for (let i = 0; i < 90 && ["queued", "running"].includes(run.status); i++) {
    await new Promise((resolve) => setTimeout(resolve, 2000));
    run = await api<Workflow>(`/workflows/${run.id}`);
  }
  if (run.status !== "completed")
    throw new Error(
      run.error ||
        "Processing is still queued. Return shortly and refresh your records.",
    );
  return run;
}

export function SkillsPage() {
  const evidence = useQuery({
    queryKey: ["skills"],
    queryFn: () => api<Evidence[]>("/skills"),
  });
  const resumes = useQuery({
    queryKey: ["resumes"],
    queryFn: () =>
      api<{ id: string; filename: string; version: number }[]>("/resumes"),
  });
  const { busy, act } = useAction();
  const [note, setNote] = useState("");
  return (
    <>
      <PageHeading
        eyebrow="EVIDENCE, BEFORE ASSUMPTIONS"
        title="Make your skills visible."
        description="Review resume claims, challenge incorrect extraction, and build evidence through approved assessments."
      >
        <Button
          disabled={busy || !resumes.data?.length}
          onClick={() =>
            act(
              () =>
                runWorkflow({
                  kind: "resume",
                  target_id: resumes.data?.[0].id,
                }),
              "Resume analysis saved for your review",
            )
          }
        >
          <Sparkles size={16} />
          {busy ? "Analyzing evidence…" : "Analyze latest resume"}
        </Button>
      </PageHeading>
      <div className="notice">
        <ShieldCheck size={20} />
        <div>
          <strong>A mention is not proof of proficiency.</strong>
          <p>
            Confirming a resume claim does not make it assessment-verified.
            Exact keyword extraction is used when the optional local model is
            unavailable.
          </p>
        </div>
      </div>
      <div className="card card-pad" style={{ marginBlock: 20 }}>
        <label className="field">
          Review note or correction
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Explain an ambiguity before choosing Challenge below"
            maxLength={2000}
          />
        </label>
      </div>
      {evidence.isLoading ? (
        <Skeleton />
      ) : evidence.error ? (
        <Failure error={evidence.error} />
      ) : !evidence.data?.length ? (
        <Empty
          title="Your evidence starts here"
          description="Upload a resume, then analyze it. Your extracted claims will appear here for review."
        >
          <Button asChild>
            <Link href="/app/resumes">Upload a resume</Link>
          </Button>
        </Empty>
      ) : (
        <div className="grid-3">
          {evidence.data.map((e) => (
            <motion.article
              whileHover={{ y: -3 }}
              className="card card-pad"
              key={e.id}
            >
              <div className="between">
                <h2>{e.skill}</h2>
                <Badge
                  tone={
                    ["assessment_verified", "faculty_verified"].includes(
                      e.evidence_type,
                    )
                      ? "green"
                      : "amber"
                  }
                >
                  {e.evidence_type.replaceAll("_", " ")}
                </Badge>
              </div>
              <p style={{ marginBlock: 16, whiteSpace: "pre-wrap" }}>
                {e.quote || `Approved assessment result: ${e.score}%`}
              </p>
              <Badge>{e.status}</Badge>
              <p className="hint">Source: {e.provider}</p>
              {e.evidence_type === "resume_claim" && (
                <p className="hint">
                  Mention indicator:{" "}
                  {e.ambiguous
                    ? "ambiguous or negated wording; clarification needed"
                    : "exact skill-name match; proficiency unverified"}
                  .
                </p>
              )}
              {e.note && <p>{e.note}</p>}
              {!["assessment_verified", "faculty_verified"].includes(
                e.evidence_type,
              ) && (
                <div
                  className="row"
                  style={{ flexWrap: "wrap", marginTop: 16 }}
                >
                  {["confirmed", "challenged", "rejected"].map((status) => (
                    <Button
                      key={status}
                      size="sm"
                      variant={status === "confirmed" ? "default" : "outline"}
                      disabled={busy}
                      onClick={() =>
                        act(() =>
                          send(
                            `/skills/${e.id}/review`,
                            { status, note },
                            "PUT",
                          ),
                        )
                      }
                    >
                      {status === "confirmed"
                        ? "Confirm claim"
                        : status === "challenged"
                          ? "Challenge"
                          : "Reject"}
                    </Button>
                  ))}
                </div>
              )}
            </motion.article>
          ))}
        </div>
      )}
    </>
  );
}

export function MatchingPanel({
  driveId,
  studentId,
}: {
  driveId?: string;
  studentId?: string;
}) {
  const query = new URLSearchParams();
  if (driveId) query.set("drive_id", driveId);
  if (studentId) query.set("student_id", studentId);
  const gap = useQuery({
    queryKey: ["matching", driveId, studentId],
    queryFn: () => api<Gap>(`/matching?${query}`),
  });
  if (gap.isLoading) return <Skeleton />;
  if (gap.error) return <Failure error={gap.error} />;
  if (!gap.data) return null;
  const data = gap.data;
  return (
    <div className="card card-pad">
      <div className="between">
        <div>
          <div className="eyebrow">PREPARATION ALIGNMENT</div>
          <h2>{data.role}</h2>
        </div>
        <strong className="alignment-number">
          {data.alignment_score ?? "—"}
          <small>/100</small>
        </strong>
      </div>
      <p className="hint">{data.score_explanation}</p>
      <div className="evidence-list">
        {data.skills.map((s) => (
          <div className="evidence-row" key={s.skill}>
            <div>
              <strong>{s.skill}</strong>
              <p className="hint">{s.recommendation}</p>
              {!!s.evidence.length && (
                <details>
                  <summary className="hint">
                    Inspect supporting evidence
                  </summary>
                  {s.evidence.map((e) => (
                    <p className="hint" key={e.id}>
                      {e.quote ||
                        `Assessment result: ${e.score}% · attempt ${e.attempt_id}`}{" "}
                      · {e.evidence_type.replaceAll("_", " ")} · {e.status}
                    </p>
                  ))}
                </details>
              )}
            </div>
            <Badge tone={s.state === "demonstrated" ? "green" : "amber"}>
              {s.state.replaceAll("_", " ")}
            </Badge>
          </div>
        ))}
      </div>
      {data.eligibility && (
        <>
          <h3 style={{ marginTop: 20 }}>
            Objective eligibility:{" "}
            {data.eligibility.status.replaceAll("_", " ")}
          </h3>
          {data.eligibility.checks.map((c) => (
            <p className="hint" key={c.rule}>
              {c.passes === true ? "✓" : c.passes === false ? "×" : "?"}{" "}
              {c.rule}: expected {JSON.stringify(c.expected)}, profile{" "}
              {JSON.stringify(c.actual)}
            </p>
          ))}
        </>
      )}
    </div>
  );
}

export function RoadmapPage() {
  const plans = useQuery({
    queryKey: ["roadmaps"],
    queryFn: () => api<Plan[]>("/roadmaps"),
  });
  const drives = useQuery({
    queryKey: ["drives"],
    queryFn: () => api<Drive[]>("/drives"),
  });
  const [drive, setDrive] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  const { busy, act } = useAction();
  return (
    <>
      <PageHeading
        eyebrow="YOUR NEXT STEP, WITH CONTEXT"
        title="A plan that grows with you."
        description="Updates are proposals. Completed lessons stay recorded, and you decide when to accept a new plan."
      >
        <select
          aria-label="Roadmap target drive"
          value={drive}
          onChange={(e) => setDrive(e.target.value)}
        >
          <option value="">My career goal</option>
          {drives.data?.map((d) => (
            <option key={d.id} value={d.id}>
              {d.company_name} · {d.position}
            </option>
          ))}
        </select>
        <Button
          disabled={busy}
          onClick={() =>
            act(
              () => runWorkflow({ kind: "learning", target_id: drive || null }),
              "Your roadmap proposal is ready",
            )
          }
        >
          {busy ? "Preparing…" : "Propose roadmap"}
        </Button>
      </PageHeading>
      <MatchingPanel driveId={drive || undefined} />
      <GoalForm />
      {!!plans.data?.some((p) => p.status === "archived") && (
        <Button
          variant="ghost"
          style={{ marginTop: 16 }}
          onClick={() => setShowArchived(!showArchived)}
        >
          {showArchived ? "Hide archived versions" : "Show archived versions"}
        </Button>
      )}
      {plans.error ? (
        <Failure error={plans.error} />
      ) : plans.isLoading ? (
        <Skeleton />
      ) : !plans.data?.length ? (
        <Empty
          title="Give your preparation a direction"
          description="Choose a recruitment drive or set a career goal, then propose a roadmap."
        />
      ) : (
        plans.data
          .filter((p) => p.status !== "archived" || showArchived)
          .map((p) => (
            <section
              className="card card-pad"
              key={p.id}
              style={{ marginTop: 24 }}
            >
              <div className="between">
                <div>
                  <Badge tone={p.status === "active" ? "green" : "blue"}>
                    Version {p.version} · {p.status}
                  </Badge>
                  <h2 style={{ marginTop: 12 }}>{p.role}</h2>
                </div>
                {p.status === "proposed" && (
                  <Button
                    disabled={busy}
                    onClick={() =>
                      act(
                        () => send(`/roadmaps/${p.id}/accept`),
                        "Roadmap accepted; completed work preserved",
                      )
                    }
                  >
                    Accept this plan
                  </Button>
                )}
              </div>
              <p style={{ marginBlock: 16 }}>{p.explanation}</p>
              <div className="progress-track">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{
                    width: `${p.total ? (100 * p.completed) / p.total : 0}%`,
                  }}
                />
              </div>
              <p className="hint">
                {p.completed} of {p.total} tasks completed ·{" "}
                {p.estimated_hours ??
                  p.tasks
                    .filter((t) => t.status !== "completed")
                    .reduce((sum, t) => sum + t.hours, 0)}{" "}
                hours planned · up to {p.hours_budget} hours available
              </p>
              <div className="timeline">
                {p.tasks.map((t) => (
                  <article className="timeline-task" key={t.id}>
                    <div
                      className={`timeline-dot ${t.status === "completed" ? "done" : ""}`}
                    >
                      <CheckCircle2 size={18} />
                    </div>
                    <div>
                      <h3>{t.title}</h3>
                      <p>{t.objective}</p>
                      <p className="hint">
                        <Clock size={12} /> {t.hours} hours · Prerequisites:{" "}
                        {t.prerequisites.join(", ") || "None"}
                      </p>
                      <p className="hint">{t.practice}</p>
                      <a
                        className="text-link"
                        href={t.resource.url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {t.resource.title}
                        <ArrowUpRight size={14} />
                      </a>
                      {t.preserved_from && (
                        <Badge tone="green">Completed work preserved</Badge>
                      )}
                    </div>
                    <Button
                      disabled={
                        busy ||
                        t.status === "completed" ||
                        p.status !== "active"
                      }
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        act(
                          () => send(`/learning-tasks/${t.id}/complete`),
                          "Progress saved",
                        )
                      }
                    >
                      {t.status === "completed" ? "Completed" : "Mark complete"}
                    </Button>
                  </article>
                ))}
              </div>
            </section>
          ))
      )}
    </>
  );
}

function GoalForm() {
  const { busy, act } = useAction();
  return (
    <details className="card card-pad" style={{ marginTop: 20 }}>
      <summary>Set or update my career goal</summary>
      <form
        className="form-grid"
        style={{ marginTop: 20 }}
        onSubmit={(e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          void act(
            () =>
              send(
                "/career-goal",
                {
                  role: f.get("role"),
                  skills: String(f.get("skills"))
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean),
                  hours_per_week: Number(f.get("hours")),
                },
                "PUT",
              ),
            "Career goal saved",
          );
        }}
      >
        <label className="field">
          Target role
          <input name="role" required defaultValue="Backend developer" />
        </label>
        <label className="field">
          Skills from the resource catalog
          <input name="skills" required defaultValue="Python, SQL" />
        </label>
        <label className="field">
          Hours per week
          <input
            name="hours"
            type="number"
            min="1"
            max="40"
            defaultValue="6"
            required
          />
        </label>
        <Button disabled={busy}>Save career goal</Button>
      </form>
    </details>
  );
}

export function ResourcesPage() {
  const data = useQuery({
    queryKey: ["resources"],
    queryFn: () => api<Resource[]>("/resources"),
  });
  const [search, setSearch] = useState("");
  return (
    <>
      <PageHeading
        eyebrow="A CURATED STARTING POINT"
        title="Good learning should be accessible."
        description="Official documentation and free learning materials, organized by skill. Optional certificates may cost extra."
      />
      <input
        aria-label="Search resources"
        placeholder="Search a skill…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        style={{ marginBottom: 20 }}
      />
      {data.error ? (
        <Failure error={data.error} />
      ) : (
        <div className="grid-3">
          {data.data
            ?.filter((r) =>
              r.skill.toLowerCase().includes(search.toLowerCase()),
            )
            .map((r) => (
              <article className="card card-pad" key={r.skill}>
                <BookOpen color="#0d9488" />
                <h2 style={{ marginBlock: 15 }}>{r.skill}</h2>
                <p>{r.title}</p>
                <p className="hint">
                  Prerequisites: {r.prerequisites.join(", ") || "Start here"}
                </p>
                <a
                  className="text-link"
                  href={r.url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open free resource <ArrowUpRight size={16} />
                </a>
              </article>
            ))}
        </div>
      )}
    </>
  );
}

type Message = { role: string; content: string; provider?: string };
export function CoachPage() {
  const history = useQuery({
    queryKey: ["conversations"],
    queryFn: () =>
      api<{ id: string; title: string; messages: Message[] }[]>(
        "/coach/conversations",
      ),
  });
  const [selected, setSelected] = useState<string>();
  const [messages, setMessages] = useState<Message[] | null>(null);
  const [text, setText] = useState("");
  const { busy, act } = useAction();
  const current =
    messages || history.data?.find((c) => c.id === selected)?.messages || [];
  return (
    <>
      <PageHeading
        eyebrow="YOUR CAREER COMPANION"
        title="Prepare with a clearer picture."
        description="Record-based guidance uses only your own evidence and results. It never changes a profile, grade, or roadmap on your behalf."
      />
      <div className="coach-layout">
        <aside className="card card-pad">
          <Button
            variant="outline"
            onClick={() => {
              setSelected(undefined);
              setMessages([]);
            }}
          >
            New conversation
          </Button>
          {history.data?.map((c) => (
            <button
              className="conversation-link"
              key={c.id}
              onClick={() => {
                setSelected(c.id);
                setMessages(null);
              }}
            >
              {c.title}
            </button>
          ))}
          <p className="hint">
            The latest 40 messages are retained per conversation.
          </p>
        </aside>
        <section className="card card-pad">
          <div className="chat-history" aria-live="polite">
            {!current.length && (
              <Empty
                title="What would you like to work on?"
                description="Ask what to study this week, why your roadmap changed, or what to revisit after your latest assessment."
              />
            )}
            {current.map((m, i) => (
              <article className={`chat-message ${m.role}`} key={i}>
                <strong>
                  {m.role === "user" ? "You" : "CampusMind coach"}
                </strong>
                <p style={{ whiteSpace: "pre-wrap" }}>{m.content}</p>
                {m.provider && <Badge>{m.provider.replaceAll("_", " ")}</Badge>}
              </article>
            ))}
          </div>
          <form
            className="row"
            onSubmit={async (e) => {
              e.preventDefault();
              const result = (await act(
                () =>
                  send<{ id: string; messages: Message[] }>("/coach/chat", {
                    message: text,
                    conversation_id: selected,
                  }),
                "Response ready",
              )) as { id: string; messages: Message[] } | undefined;
              if (result) {
                setSelected(result.id);
                setMessages(result.messages);
                setText("");
              }
            }}
          >
            <input
              aria-label="Message career coach"
              required
              minLength={2}
              maxLength={2000}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="What should I practice this week?"
            />
            <Button disabled={busy}>
              <Send size={16} />
              {busy ? "Reading…" : "Send"}
            </Button>
          </form>
        </section>
      </div>
      <InterviewPractice />
    </>
  );
}

function InterviewPractice() {
  const [feedback, setFeedback] = useState("");
  const { busy, act } = useAction();
  return (
    <details className="card card-pad" style={{ marginTop: 24 }}>
      <summary>Practice an interview response</summary>
      <form
        className="form-stack"
        style={{ marginTop: 18 }}
        onSubmit={async (e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          const r = (await act(
            () =>
              runWorkflow({
                kind: "interview",
                question: f.get("question"),
                answer: f.get("answer"),
              }),
            "Advisory feedback ready",
          )) as Workflow | undefined;
          if (r)
            setFeedback(
              `${r.result?.answer}\n\nSource: ${r.provider}. Advisory only; no grade assigned.`,
            );
        }}
      >
        <label className="field">
          Practice question
          <input
            name="question"
            defaultValue="Describe a project where you used SQL. How did you validate your queries?"
            required
          />
        </label>
        <label className="field">
          Your response
          <textarea name="answer" required maxLength={8000} rows={5} />
        </label>
        <Button disabled={busy}>Get practice feedback</Button>
      </form>
      {feedback && (
        <p style={{ whiteSpace: "pre-wrap", marginTop: 20 }}>{feedback}</p>
      )}
    </details>
  );
}

type Question = {
  id: string;
  prompt: string;
  kind: string;
  topic: string;
  options: string[];
  correct?: number[];
  explanation?: string;
  status?: string;
};
type Attempt = {
  id: string;
  title: string;
  status: string;
  expires_at: string;
  server_time: string;
  questions: Question[];
  answers: Record<string, string | number[]>;
  score?: number | null;
  topics?: Record<string, { score: number }>;
  score_basis?: string;
  manual_review_pending?: boolean;
  examiner_total_score?: number | null;
  manual_reviews?: Record<string, { feedback: string; points: number }>;
};
export function AssessmentsPage({ user }: { user: User }) {
  const student = user.role === "student";
  const { busy, act } = useAction();
  const [active, setActive] = useState<Attempt | null>(null);
  const list = useQuery({
    queryKey: ["assessments"],
    queryFn: () =>
      api<
        {
          id: string;
          title: string;
          duration_minutes: number;
          question_count: number;
        }[]
      >("/assessments"),
  });
  const history = useQuery({
    queryKey: ["attempts"],
    queryFn: () => api<Attempt[]>("/attempts"),
    enabled: student,
  });
  return (
    <>
      <PageHeading
        eyebrow="PRACTICE WITH EVIDENCE"
        title={
          student
            ? "Understand what you know."
            : "Assessments with accountable marking."
        }
        description="Approved questions, timed sessions, and persisted results. Free-text and code exercises require human review; submitted code is never executed."
      />
      {!student && <QuestionStudio />}
      {active ? (
        <TestPlayer
          key={active.id}
          attempt={active}
          close={() => setActive(null)}
        />
      ) : (
        <>
          <div className="grid-3">
            {list.data?.map((a) => (
              <article className="card card-pad" key={a.id}>
                <Badge tone="blue">Approved question bank</Badge>
                <h2 style={{ marginBlock: 16 }}>{a.title}</h2>
                <p>
                  {a.question_count} questions · {a.duration_minutes} minutes
                </p>
                {student && (
                  <Button
                    style={{ marginTop: 20 }}
                    disabled={busy}
                    onClick={async () => {
                      const r = (await act(
                        () => send<Attempt>(`/assessments/${a.id}/start`),
                        "Attempt ready",
                      )) as Attempt | undefined;
                      if (r) setActive(r);
                    }}
                  >
                    Start or resume
                  </Button>
                )}
              </article>
            ))}
          </div>
          {!list.data?.length && (
            <Empty
              title="No assessments published yet"
              description={
                student
                  ? "Your placement team will publish approved practice sets here."
                  : "Create questions below, approve them, then publish a timed assessment."
              }
            />
          )}{" "}
          {student && (
            <section style={{ marginTop: 28 }}>
              <h2>Your attempt history</h2>
              {history.data?.map((a) => (
                <button
                  className="card attempt-history"
                  key={a.id}
                  onClick={() => setActive(a)}
                >
                  <span>
                    <strong>{a.title}</strong>
                    <small>{a.status.replaceAll("_", " ")}</small>
                  </span>
                  <Badge tone={a.status === "submitted" ? "green" : "amber"}>
                    {a.score != null
                      ? `${a.score}% objective`
                      : a.status === "active"
                        ? "Resume"
                        : "Manual review"}
                  </Badge>
                </button>
              ))}
            </section>
          )}
        </>
      )}
      {list.error && <Failure error={list.error} />}
    </>
  );
}

function TestPlayer({
  attempt,
  close,
}: {
  attempt: Attempt;
  close: () => void;
}) {
  const [data, setData] = useState(attempt),
    [answers, setAnswers] = useState(attempt.answers),
    [seconds, setSeconds] = useState(0);
  const { busy, act } = useAction();
  const active = data.status === "active";
  useEffect(() => {
    const offset = new Date(data.server_time + "Z").getTime() - Date.now();
    const update = () =>
      setSeconds(
        Math.max(
          0,
          Math.ceil(
            (new Date(data.expires_at + "Z").getTime() - Date.now() - offset) /
              1000,
          ),
        ),
      );
    update();
    const timer = setInterval(update, 1000);
    return () => clearInterval(timer);
  }, [data.server_time, data.expires_at]);
  async function save(submit = false) {
    const r = (await act(
      () =>
        send<Attempt>(
          `/attempts/${data.id}/answers?submit=${submit}`,
          { answers },
          "PUT",
        ),
      submit ? "Assessment submitted" : "Answers saved",
    )) as Attempt | undefined;
    if (r) {
      setData(r);
      setAnswers(r.answers);
    }
  }
  return (
    <section className="card card-pad">
      <div className="between">
        <h2>{data.title}</h2>
        <Badge tone="blue">
          {active
            ? `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")} remaining`
            : `Objective score: ${data.score ?? "Pending review"}`}
        </Badge>
      </div>
      <p className="hint">
        Save answers regularly. After expiry, the server grades only answers
        received before the deadline.
      </p>
      {data.questions.map((q, index) => (
        <fieldset className="assessment-question" key={q.id}>
          <legend>
            {index + 1}. {q.prompt}
          </legend>
          <Badge>{q.topic}</Badge>
          {["single", "multiple"].includes(q.kind) ? (
            q.options.map((option, i) => (
              <label className="answer-option" key={i}>
                <input
                  type={q.kind === "single" ? "radio" : "checkbox"}
                  name={q.id}
                  disabled={!active || !seconds}
                  checked={
                    Array.isArray(answers[q.id]) &&
                    (answers[q.id] as number[]).includes(i)
                  }
                  onChange={(e) => {
                    const prior = Array.isArray(answers[q.id])
                      ? (answers[q.id] as number[])
                      : [];
                    setAnswers({
                      ...answers,
                      [q.id]:
                        q.kind === "single"
                          ? [i]
                          : e.target.checked
                            ? [...prior, i]
                            : prior.filter((v) => v !== i),
                    });
                  }}
                />
                {option}
              </label>
            ))
          ) : (
            <textarea
              aria-label={`Answer question ${index + 1}`}
              disabled={!active || !seconds}
              rows={5}
              maxLength={12000}
              value={
                typeof answers[q.id] === "string"
                  ? (answers[q.id] as string)
                  : ""
              }
              onChange={(e) =>
                setAnswers({ ...answers, [q.id]: e.target.value })
              }
            />
          )}{" "}
          {!active && (
            <div className="notice" style={{ marginTop: 15 }}>
              <p>
                {q.correct
                  ? `Correct: ${q.correct.map((i) => q.options[i]).join("; ")}. `
                  : "Examiner review required. "}
                {q.explanation}
              </p>
            </div>
          )}
        </fieldset>
      ))}
      {!active && <p className="hint">{data.score_basis}</p>}
      {!active && data.examiner_total_score != null && (
        <p>Examiner-reviewed total: {data.examiner_total_score}%</p>
      )}
      {!active && data.manual_reviews && (
        <div>
          {Object.entries(data.manual_reviews).map(([id, review]) => (
            <p className="hint" key={id}>
              Examiner feedback: {review.feedback} · {review.points} points
            </p>
          ))}
        </div>
      )}
      <div className="row">
        {active && (
          <>
            <Button variant="outline" disabled={busy} onClick={() => save()}>
              Save answers
            </Button>
            <Button disabled={busy} onClick={() => save(true)}>
              {seconds ? "Submit assessment" : "Finalize expired attempt"}
            </Button>
          </>
        )}
        <Button variant="ghost" onClick={close}>
          Back to assessments
        </Button>
      </div>
    </section>
  );
}

function QuestionStudio() {
  const bank = useQuery({
    queryKey: ["questions"],
    queryFn: () => api<Question[]>("/questions"),
  });
  const { busy, act } = useAction();
  const [selected, setSelected] = useState<string[]>([]);
  return (
    <details className="card card-pad" style={{ marginBottom: 24 }}>
      <summary>Question bank & assessment studio</summary>
      <form
        className="row"
        style={{ marginTop: 20 }}
        onSubmit={(e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          void act(
            () =>
              runWorkflow({
                kind: "assessment_draft",
                topic: f.get("topic"),
                count: 2,
              }),
            "Draft suggestions saved. Review every answer and explanation before approving.",
          );
        }}
      >
        <label className="field">
          Draft question topic
          <select name="topic">
            <option>SQL</option>
            <option>Python</option>
            <option>C#</option>
            <option>DSA</option>
            <option>Aptitude</option>
          </select>
        </label>
        <Button variant="outline" disabled={busy}>
          Suggest draft practice questions
        </Button>
        <p className="hint">
          Uses a curated synthetic catalog unless the optional local model is
          enabled.
        </p>
      </form>
      <form
        className="form-grid"
        style={{ marginTop: 20 }}
        onSubmit={async (e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          await act(
            () =>
              send("/questions", {
                prompt: f.get("prompt"),
                topic: f.get("topic"),
                kind: f.get("kind"),
                options: String(f.get("options")).split("\n").filter(Boolean),
                correct: String(f.get("correct"))
                  .split(",")
                  .filter(Boolean)
                  .map((v) => Number(v) - 1),
                explanation: f.get("explanation"),
                points: 1,
              }),
            "Question saved as draft",
          );
        }}
      >
        <label className="field">
          Question
          <textarea name="prompt" required minLength={5} />
        </label>
        <label className="field">
          Topic
          <input name="topic" defaultValue="SQL" required />
        </label>
        <label className="field">
          Type
          <select name="kind">
            <option value="single">Single-choice MCQ</option>
            <option value="multiple">Multiple-choice MCQ</option>
            <option value="short">Short answer</option>
            <option value="code">Code writing · manual review</option>
            <option value="interview">Interview response</option>
          </select>
        </label>
        <label className="field">
          Options · one per line
          <textarea
            name="options"
            placeholder="Leave empty for written responses"
          />
        </label>
        <label className="field">
          Correct option numbers · comma separated
          <input
            name="correct"
            placeholder="1 or 1,3; empty for written responses"
          />
        </label>
        <label className="field">
          Feedback / examiner rubric
          <textarea name="explanation" />
        </label>
        <Button disabled={busy}>Create draft question</Button>
      </form>
      <div className="evidence-list">
        {bank.data?.map((q) => (
          <div className="evidence-row" key={q.id}>
            <label className="row">
              <input
                type="checkbox"
                disabled={q.status !== "approved"}
                checked={selected.includes(q.id)}
                onChange={(e) =>
                  setSelected(
                    e.target.checked
                      ? [...selected, q.id]
                      : selected.filter((id) => id !== q.id),
                  )
                }
              />
              <span>
                {q.prompt}
                <small className="muted"> · {q.topic}</small>
                <details style={{ marginTop: 12 }}>
                  <summary>Review answer key & explanation</summary>
                  <p className="hint">
                    {q.options.map((o, i) => `${i + 1}. ${o}`).join(" · ")}
                  </p>
                  <p className="hint">
                    Correct options:{" "}
                    {q.correct?.map((i) => i + 1).join(", ") || "Manual review"}
                  </p>
                  <p className="hint">
                    {q.explanation ||
                      "Add an examiner rubric before official use."}
                  </p>
                </details>
              </span>
            </label>
            {q.status !== "approved" ? (
              <Button
                size="sm"
                disabled={busy}
                onClick={() =>
                  act(
                    () => send(`/questions/${q.id}/approve`),
                    "Question approved after human review",
                  )
                }
              >
                Approve question
              </Button>
            ) : (
              <Badge tone="green">Approved</Badge>
            )}
          </div>
        ))}
      </div>
      <form
        className="form-grid"
        style={{ marginTop: 20 }}
        onSubmit={(e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          void act(
            () =>
              send("/assessments", {
                title: f.get("title"),
                duration_minutes: Number(f.get("minutes")),
                question_ids: selected,
                randomize: true,
              }),
            "Assessment published",
          );
        }}
      >
        <label className="field">
          Assessment title
          <input name="title" required minLength={3} />
        </label>
        <label className="field">
          Time limit · minutes
          <input
            name="minutes"
            type="number"
            min={1}
            max={180}
            defaultValue={20}
          />
        </label>
        <Button disabled={busy || !selected.length}>
          Publish {selected.length} selected questions
        </Button>
      </form>
    </details>
  );
}
