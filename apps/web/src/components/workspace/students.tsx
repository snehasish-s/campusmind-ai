"use client";
import { useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Search,
  Upload,
  ArrowDownUp,
  ChevronLeft,
  ChevronRight,
  Mail,
  Link2,
  Copy,
  FileText,
} from "lucide-react";
import { toast } from "sonner";
import { api, send, type Student, type User } from "@/lib/api";
import { Button } from "../ui/button";
import { MatchingPanel } from "./intelligence";
import { Dialog } from "../ui/dialog";
import { Badge, Empty, Failure, PageHeading, Skeleton } from "../ui/common";

export function StudentsPage({ user }: { user: User }) {
  const params = useSearchParams(),
    client = useQueryClient();
  const [search, setSearch] = useState(params.get("q") || ""),
    [department, setDepartment] = useState(""),
    [page, setPage] = useState(1),
    [order, setOrder] = useState("asc"),
    [selected, setSelected] = useState<Student | null>(null),
    [invitation, setInvitation] = useState(""),
    [pending, setPending] = useState(false);
  const query = useQuery({
    queryKey: ["students", search, department, page, order],
    queryFn: () =>
      api<{ items: Student[]; total: number }>(
        `/students?q=${encodeURIComponent(search)}&department=${department}&page=${page}&order=${order}`,
      ),
  });
  const departments = useQuery({
    queryKey: ["departments"],
    queryFn: () =>
      api<{ id: string; code: string; name: string }[]>("/departments"),
  });
  const resumes = useQuery({
    queryKey: ["student-resumes", selected?.id],
    queryFn: () =>
      api<{ id: string; filename: string; version: number }[]>(
        `/resumes?student_id=${selected!.id}`,
      ),
    enabled: !!selected,
  });
  const passport = useQuery({
    queryKey: ["student-passport", selected?.id],
    queryFn: () =>
      api<{
        evidence: {
          id: string;
          skill: string;
          evidence_type: string;
          status: string;
          score?: number;
          quote?: string;
        }[];
      }>(`/campus/passport?student_id=${selected!.id}`),
    enabled: !!selected,
  });
  async function invite(action: string) {
    if (!selected) return;
    setPending(true);
    try {
      const response = await send<{
        activation_url?: string;
        delivery_status?: string;
      }>(
        action === "reset"
          ? `/auth/password-reset/${selected.id}/distribute`
          : `/auth/invitations/${selected.id}/${action}`,
      );
      if (response.activation_url) setInvitation(response.activation_url);
      else
        toast.success(
          action === "revoke"
            ? "Invitation revoked"
            : `Invitation delivery: ${response.delivery_status}`,
        );
      await client.invalidateQueries({ queryKey: ["students"] });
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setPending(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="STUDENT OPERATIONS"
        title="Your student community"
        description="Find a student, review their profile and keep onboarding moving."
      >
        {user.role !== "hod" && (
          <Button asChild>
            <Link href="/app/imports">
              <Upload size={15} />
              Import students
            </Link>
          </Button>
        )}
      </PageHeading>
      <section className="card">
        <div className="table-toolbar">
          <div className="search-field">
            <Search />
            <input
              aria-label="Search student registry"
              placeholder="Search name, roll number or email…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
          </div>
          <select
            aria-label="Filter by department"
            value={department}
            onChange={(e) => {
              setDepartment(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All departments</option>
            {departments.data?.map((d) => (
              <option key={d.id} value={d.code}>
                {d.code}
              </option>
            ))}
          </select>
          <Button
            variant="outline"
            onClick={() => setOrder(order === "asc" ? "desc" : "asc")}
          >
            <ArrowDownUp size={14} />
            Name {order === "asc" ? "A–Z" : "Z–A"}
          </Button>
        </div>
        {query.isLoading ? (
          <div className="card-pad">
            <Skeleton />
          </div>
        ) : query.error ? (
          <Failure error={query.error} retry={() => void query.refetch()} />
        ) : !query.data?.items.length ? (
          <Empty
            title="No students found"
            description="Import your synthetic student CSV or adjust the filters."
          />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Student</th>
                  <th>Roll number</th>
                  <th>Department</th>
                  <th>CGPA</th>
                  <th>Account</th>
                  <th>Resume</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((s) => (
                  <tr key={s.id}>
                    <td>
                      <div className="row">
                        <div className="avatar">
                          {s.full_name
                            .split(" ")
                            .slice(0, 2)
                            .map((x) => x[0])
                            .join("")}
                        </div>
                        <div>
                          <strong>{s.full_name}</strong>
                          <div className="sub">{s.email}</div>
                        </div>
                      </div>
                    </td>
                    <td>{s.roll_no}</td>
                    <td>
                      <Badge tone="blue">{s.department}</Badge>
                    </td>
                    <td>{s.cgpa.toFixed(2)}</td>
                    <td>
                      <Badge tone={s.active ? "green" : "amber"}>
                        {s.active ? "Active" : "Invited"}
                      </Badge>
                    </td>
                    <td>
                      {s.resume_count ? (
                        <Badge tone="green">Uploaded</Badge>
                      ) : (
                        <span className="muted">Not uploaded</span>
                      )}
                    </td>
                    <td>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setSelected(s);
                          setInvitation("");
                        }}
                      >
                        View <ChevronRight size={13} />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="pagination">
          <span>
            {query.data?.total.toLocaleString() || 0} students · Page {page}
          </span>
          <div className="row">
            <Button
              variant="outline"
              size="sm"
              aria-label="Previous page"
              disabled={page === 1}
              onClick={() => setPage(page - 1)}
            >
              <ChevronLeft size={14} />
            </Button>
            <Button
              variant="outline"
              size="sm"
              aria-label="Next page"
              disabled={page * 20 >= (query.data?.total || 0)}
              onClick={() => setPage(page + 1)}
            >
              <ChevronRight size={14} />
            </Button>
          </div>
        </div>
      </section>
      <Dialog
        open={!!selected}
        onOpenChange={(open) => {
          if (!open) {
            setSelected(null);
            setInvitation("");
          }
        }}
        title={selected?.full_name || "Student details"}
        description={
          selected
            ? `${selected.roll_no} · ${selected.department} · Class of ${selected.graduation_year}`
            : undefined
        }
      >
        {selected && (
          <>
            <div className="summary-grid">
              <div className="summary-cell">
                <strong>{selected.cgpa}</strong>
                <span>CGPA</span>
              </div>
              <div className="summary-cell">
                <strong>{selected.active_backlogs}</strong>
                <span>Backlogs</span>
              </div>
              <div className="summary-cell">
                <strong>{selected.resume_count}</strong>
                <span>Resume versions</span>
              </div>
              <div className="summary-cell">
                <Badge tone={selected.active ? "green" : "amber"}>
                  {selected.active ? "Active" : "Pending"}
                </Badge>
                <p className="hint">Account</p>
              </div>
            </div>
            <div className="grid-2 small">
              <div>
                <label>Email</label>
                {selected.email}
              </div>
              <div>
                <label>Phone</label>
                {selected.phone || "Not provided"}
              </div>
            </div>
            {selected.bio && (
              <p className="small" style={{ marginTop: 18 }}>
                {selected.bio}
              </p>
            )}
            <div className="divider" />
            <h3>Resume history</h3>
            {resumes.data?.length ? (
              resumes.data.map((r) => (
                <div className="list-item" key={r.id}>
                  <span className="small">
                    {r.filename} · v{r.version}
                  </span>
                  <Button variant="outline" size="sm" asChild>
                    <a href={`/api/resumes/${r.id}/download`}>
                      <FileText size={13} />
                      Download
                    </a>
                  </Button>
                </div>
              ))
            ) : (
              <p className="hint">No resume uploaded yet.</p>
            )}
            <MatchingPanel studentId={selected.id} />
            <div className="divider" />
            <h3>Academic & placement evidence passport</h3>
            {passport.isPending && <Skeleton rows={2} />}
            {passport.error && <Failure error={passport.error} />}
            {passport.data?.evidence.map((e) => (
              <div className="passport-evidence" key={e.id}>
                <strong>{e.skill}</strong>{" "}
                <Badge>{e.evidence_type.replaceAll("_", " ")}</Badge>{" "}
                <Badge>{e.status}</Badge>
                {e.score !== undefined && <p>Recorded score: {e.score}%</p>}
                {e.quote && <p className="hint">{e.quote}</p>}
              </div>
            ))}
            {passport.data?.evidence.length === 0 && (
              <p className="hint">No skill evidence recorded yet.</p>
            )}
            {selected.active &&
              ["institution_admin", "platform_admin"].includes(user.role) && (
                <div className="card card-pad" style={{ marginTop: 18 }}>
                  <h3>Secure account recovery</h3>
                  <p className="hint">
                    Verify the student’s identity before issuing a short-lived
                    reset link. The student chooses the replacement password.
                  </p>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={pending}
                    onClick={() => void invite("reset")}
                  >
                    Issue one-time password reset
                  </Button>
                  {invitation && (
                    <>
                      <label className="field" style={{ marginTop: 15 }}>
                        One-time password reset link
                        <input readOnly value={invitation} />
                      </label>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          void navigator.clipboard
                            .writeText(invitation)
                            .then(() => toast.success("Reset link copied"))
                        }
                      >
                        Copy reset link
                      </Button>
                    </>
                  )}
                </div>
              )}
            {!selected.active && user.role !== "hod" && (
              <>
                <div className="divider" />
                <h3>Account invitation</h3>
                <p className="hint">
                  Latest delivery:{" "}
                  {selected.invitation_status.replaceAll("_", " ")}. Resending
                  invalidates older links.
                </p>
                <div
                  className="row"
                  style={{ flexWrap: "wrap", marginTop: 15 }}
                >
                  <Button
                    size="sm"
                    disabled={pending}
                    onClick={() => void invite("resend")}
                  >
                    <Mail size={13} />
                    Resend email
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={pending}
                    onClick={() => void invite("distribute")}
                  >
                    <Link2 size={13} />
                    One-time distribution
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={pending}
                    onClick={() => void invite("revoke")}
                  >
                    Revoke
                  </Button>
                </div>
                {invitation && (
                  <div
                    className="insight-note"
                    style={{ marginTop: 15, display: "block" }}
                  >
                    <strong>Shown only now · This action is audited</strong>
                    <p>
                      Deliver this link directly to the verified student through
                      an institution-approved channel. Do not share it in a
                      group or spreadsheet.
                    </p>
                    <input
                      aria-label="One-time activation link"
                      readOnly
                      value={invitation}
                      style={{ marginBlock: 10, fontSize: 10 }}
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        void navigator.clipboard
                          .writeText(invitation)
                          .then(() => toast.success("Invitation link copied"))
                      }
                    >
                      <Copy size={13} />
                      Copy link
                    </Button>
                  </div>
                )}
              </>
            )}
          </>
        )}
      </Dialog>
    </>
  );
}
