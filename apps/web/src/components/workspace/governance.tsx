"use client";
import { useQuery } from "@tanstack/react-query";
import { api, send, type User } from "@/lib/api";
import { Button } from "../ui/button";
import { Badge, PageHeading, Failure } from "../ui/common";
import { useAction } from "./intelligence";

export function TasksPage({ user }: { user: User }) {
  const tasks = useQuery({
    queryKey: ["institutional-tasks"],
    queryFn: () =>
      api<
        {
          id: string;
          title: string;
          description: string;
          status: string;
          due_date: string;
          assigned_to: string;
        }[]
      >("/institutional-tasks"),
  });
  const admin = ["institution_admin", "platform_admin"].includes(user.role);
  const staff = useQuery({
    queryKey: ["staff"],
    queryFn: () =>
      api<{ id: string; full_name: string; role: string }[]>("/staff"),
    enabled: admin,
  });
  const { busy, act } = useAction();
  return (
    <>
      <PageHeading
        eyebrow="COLLEGEOPS · COORDINATION"
        title="Turn evidence gaps into action."
        description="Assign institutional work, record progress, and retain administrator approval."
      />
      <details className="card card-pad">
        <summary>Create an institutional task</summary>
        <form
          className="form-grid"
          style={{ marginTop: 20 }}
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            void act(
              () =>
                send("/institutional-tasks", {
                  title: f.get("title"),
                  description: f.get("description"),
                  due_date: f.get("due_date"),
                  assigned_to: f.get("assigned_to"),
                }),
              "Institutional task created",
            );
          }}
        >
          <label className="field">
            Title
            <input name="title" minLength={3} required />
          </label>
          <label className="field">
            Description
            <textarea name="description" />
          </label>
          <label className="field">
            Assigned coordinator
            <select name="assigned_to">
              <option value={user.id}>{user.full_name} · me</option>
              {staff.data
                ?.filter(
                  (s) =>
                    s.id !== user.id &&
                    ["institution_admin", "platform_admin", "hod"].includes(
                      s.role,
                    ),
                )
                .map((s) => (
                  <option value={s.id} key={s.id}>
                    {s.full_name}
                  </option>
                ))}
            </select>
          </label>
          <label className="field">
            Due date
            <input type="date" name="due_date" />
          </label>
          <Button disabled={busy}>Create task</Button>
        </form>
      </details>
      {tasks.error && <Failure error={tasks.error} />}
      <div className="grid-2" style={{ marginTop: 24 }}>
        {tasks.data?.map((t) => (
          <article className="card card-pad" key={t.id}>
            <Badge tone={t.status === "approved" ? "green" : "blue"}>
              {t.status.replaceAll("_", " ")}
            </Badge>
            <h2 style={{ marginTop: 16 }}>{t.title}</h2>
            <p style={{ marginBlock: 15 }}>{t.description}</p>
            <p className="hint">Due: {t.due_date || "Not specified"}</p>
            <div className="row" style={{ flexWrap: "wrap" }}>
              {(admin || t.assigned_to === user.id) &&
                [
                  "in_progress",
                  "submitted",
                  ...(admin ? ["approved"] : []),
                ].map((status) => (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busy || status === t.status}
                    key={status}
                    onClick={() =>
                      act(
                        () =>
                          send(
                            `/institutional-tasks/${t.id}?status=${status}`,
                            undefined,
                            "PUT",
                          ),
                        "Task status saved",
                      )
                    }
                  >
                    {status.replaceAll("_", " ")}
                  </Button>
                ))}
            </div>
          </article>
        ))}
      </div>
    </>
  );
}

export function PrivacyActions({ user }: { user: User }) {
  const admin = ["institution_admin", "platform_admin"].includes(user.role);
  const { busy, act } = useAction();
  const requests = useQuery({
    queryKey: ["privacy-requests"],
    queryFn: () =>
      api<{ id: string; name: string; status: string }[]>("/privacy/requests"),
    enabled: admin,
  });
  return (
    <div style={{ marginTop: 18 }}>
      {user.role === "student" && (
        <>
          <div className="row">
            <Button asChild variant="outline">
              <a href="/api/privacy/export" target="_blank" rel="noreferrer">
                Open my data export
              </a>
            </Button>
            <Button
              variant="outline"
              disabled={busy}
              onClick={() =>
                act(
                  () => send("/privacy/deletion-request"),
                  "Deletion request sent to your institution administrator",
                )
              }
            >
              Request account deletion
            </Button>
          </div>
          <p className="hint">
            Deletion requires institutional review. Your private records and
            files are erased after approval; a pseudonymous audit trail remains.
          </p>
        </>
      )}
      {admin && (
        <details>
          <summary>Review student deletion requests</summary>
          {requests.data?.map((r) => (
            <form
              key={r.id}
              style={{ marginTop: 16 }}
              onSubmit={(e) => {
                e.preventDefault();
                void act(
                  () =>
                    send(`/privacy/requests/${r.id}/erase`, {
                      confirm_erasure: true,
                    }),
                  "Student records erased",
                );
              }}
            >
              <strong>{r.name}</strong> <Badge>{r.status}</Badge>
              {r.status === "pending" && (
                <>
                  <label className="answer-option">
                    <input type="checkbox" required />I have authorized this
                    deletion and understand that private records, files, results
                    and progress will be erased.
                  </label>
                  <Button disabled={busy} variant="danger">
                    Approve & erase student records
                  </Button>
                </>
              )}
            </form>
          ))}
          <p className="hint">
            Backups and legally required records need a separate
            institution-approved retention process.
          </p>
        </details>
      )}
    </div>
  );
}
