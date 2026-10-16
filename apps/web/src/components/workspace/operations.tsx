"use client";
import { PrivacyActions } from "./governance";
import { useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Bell,
  Download,
  Save,
  ShieldCheck,
  FileText,
  Building2,
  Users,
  ArrowRight,
  LockKeyhole,
  Mail,
  Pencil,
} from "lucide-react";
import { toast } from "sonner";
import { api, send, type User } from "@/lib/api";
import { date } from "@/lib/utils";
import { Button } from "../ui/button";
import { Dialog } from "../ui/dialog";
import {
  Badge,
  Empty,
  Failure,
  PageHeading,
  Pending,
  Skeleton,
} from "../ui/common";

type RecordRow = {
  id: string;
  code?: string;
  name?: string;
  full_name?: string;
  email?: string;
  role?: string;
  department_id?: string;
  active?: boolean;
  sector?: string;
  website?: string;
  title?: string;
  category?: string;
  status?: string;
  filename?: string;
  size_bytes?: number;
  created_at?: string;
  action?: string;
  actor?: string;
  target_id?: string;
};
const titles: Record<string, [string, string]> = {
  departments: [
    "Departments",
    "Give every academic branch a clear place in your institution.",
  ],
  staff: [
    "People & permissions",
    "Invite your institution’s team with clearly defined responsibilities.",
  ],
  companies: [
    "Company directory",
    "A shared directory of employers for your placement team.",
  ],
  documents: [
    "Academic evidence vault",
    "Store institutional documents with controlled access.",
  ],
  audit: [
    "An accountable workspace",
    "Review privileged actions within your institution.",
  ],
  reports: [
    "Reports, grounded in your records",
    "Export recruitment activity from your institution’s database.",
  ],
};

export function AdminPage({ section, user }: { section: string; user: User }) {
  if (section === "settings") return <SettingsPage user={user} />;
  if (section === "reports") return <ReportsPage />;
  return <Registry section={section} user={user} />;
}
function Registry({ section, user }: { section: string; user: User }) {
  const client = useQueryClient(),
    [open, setOpen] = useState(false),
    [pending, setPending] = useState(false),
    [error, setError] = useState(""),
    [access, setAccess] = useState<RecordRow | null>(null),
    [edit, setEdit] = useState<RecordRow | null>(null);
  const admin = ["institution_admin", "platform_admin"].includes(user.role),
    canCreate =
      section === "companies"
        ? ["institution_admin", "platform_admin", "placement_officer"].includes(
            user.role,
          )
        : section === "documents"
          ? admin || user.role === "hod"
          : admin;
  const allowed =
    section === "departments" ||
    (section === "companies" && user.role !== "student") ||
    (section === "documents" && (admin || user.role === "hod")) ||
    (["staff", "audit"].includes(section) && admin);
  const query = useQuery({
    queryKey: [section],
    queryFn: () => api<RecordRow[]>(`/${section}`),
    enabled: allowed,
  });
  const departments = useQuery({
    queryKey: ["departments"],
    queryFn: () => api<RecordRow[]>("/departments"),
    enabled: section === "staff",
  });
  const [title, description] = titles[section] || [
    "Workspace",
    "Institution records",
  ];
  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      if (section === "documents") {
        await api("/documents", { method: "POST", body: form });
      } else {
        const values: Record<string, unknown> = Object.fromEntries(form);
        if (section === "staff" && !values.department_id)
          values.department_id = null;
        await send(
          edit ? `/${section}/${edit.id}` : `/${section}`,
          values,
          edit ? "PUT" : "POST",
        );
      }
      await client.invalidateQueries({ queryKey: [section] });
      await client.invalidateQueries({ queryKey: ["dashboard"] });
      setOpen(false);
      toast.success(
        section === "staff"
          ? "Staff invitation created. Check Mailpit for delivery."
          : "Record saved.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPending(false);
    }
  }
  async function resend(id: string) {
    try {
      const result = await send<{ delivery_status: string }>(
        `/auth/invitations/${id}/resend`,
      );
      toast.success(`Invitation delivery: ${result.delivery_status}`);
    } catch (e) {
      toast.error((e as Error).message);
    }
  }
  async function saveAccess(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!access) return;
    setPending(true);
    const values = Object.fromEntries(new FormData(event.currentTarget));
    try {
      await send(
        `/staff/${access.id}/access`,
        { role: values.role, department_id: values.department_id || null },
        "PUT",
      );
      await client.invalidateQueries({ queryKey: ["staff"] });
      setAccess(null);
      toast.success("Staff access updated. Existing sessions have been ended.");
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setPending(false);
    }
  }
  if (!allowed)
    return (
      <Empty
        title="This workspace is restricted"
        description="Your role does not have access to this institution page."
      />
    );
  return (
    <>
      <PageHeading
        eyebrow={
          section === "documents" ? "COLLEGEOPS" : "INSTITUTION WORKSPACE"
        }
        title={title}
        description={description}
      >
        {canCreate && section !== "audit" && (
          <Button
            onClick={() => {
              setEdit(null);
              setError("");
              setOpen(true);
            }}
          >
            <Plus size={15} />
            {section === "documents"
              ? "Upload document"
              : section === "staff"
                ? "Invite staff"
                : section === "companies"
                  ? "Add company"
                  : "Add department"}
          </Button>
        )}
      </PageHeading>
      {section === "documents" && (
        <div className="phase-banner">
          <ShieldCheck size={16} />
          Secure document storage is available now. Evidence analysis,
          accreditation mapping and approvals will arrive in Phase 2.
        </div>
      )}
      {query.isLoading ? (
        <Skeleton />
      ) : query.error ? (
        <Failure error={query.error} retry={() => void query.refetch()} />
      ) : !query.data?.length ? (
        <section className="card">
          <Empty
            title={
              section === "audit"
                ? "No activity recorded yet"
                : "A clear place to start"
            }
            description={
              section === "documents"
                ? "Upload your first institutional PDF or DOCX. Files are visible to authorized administrators and department coordinators."
                : `Your institution’s ${section} will appear here.`
            }
          />
        </section>
      ) : section === "departments" || section === "companies" ? (
        <div className="grid-3">
          {query.data.map((r) => (
            <article className="card card-pad" key={r.id}>
              <div className="between">
                <div className="icon-tile">
                  {section === "departments" ? (
                    <Building2 size={23} />
                  ) : (
                    <Users size={23} />
                  )}
                </div>
                <Badge tone="blue">{r.code || r.sector}</Badge>
              </div>
              <h2 style={{ marginTop: 20 }}>{r.name}</h2>
              <p className="small" style={{ marginTop: 10 }}>
                {section === "departments"
                  ? "Academic department"
                  : r.website || "Institution company directory"}
              </p>
              {section === "departments" && admin && (
                <Button
                  variant="ghost"
                  size="sm"
                  style={{ marginTop: 18 }}
                  onClick={() => {
                    setEdit(r);
                    setError("");
                    setOpen(true);
                  }}
                >
                  <Pencil size={13} />
                  Edit department
                </Button>
              )}
            </article>
          ))}
        </div>
      ) : (
        <section className="card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  {(section === "staff"
                    ? ["Staff member", "Role", "Account", "Actions"]
                    : section === "documents"
                      ? [
                          "Document",
                          "Category",
                          "Uploaded",
                          "Status",
                          "Actions",
                        ]
                      : ["Action", "Actor", "Date", "Record reference"]
                  ).map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {query.data.map((r) => (
                  <tr key={r.id}>
                    {section === "staff" ? (
                      <>
                        <td>
                          <strong>{r.full_name}</strong>
                          <div className="sub">{r.email}</div>
                        </td>
                        <td>
                          <Badge tone="blue">
                            {r.role?.replaceAll("_", " ")}
                          </Badge>
                        </td>
                        <td>
                          <Badge tone={r.active ? "green" : "amber"}>
                            {r.active ? "Active" : "Invitation pending"}
                          </Badge>
                        </td>
                        <td>
                          {r.id !== user.id && r.role !== "platform_admin" && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setAccess(r)}
                            >
                              <Pencil size={12} />
                              Manage role
                            </Button>
                          )}
                          {!r.active && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => void resend(r.id)}
                            >
                              <Mail size={12} />
                              Resend invitation
                            </Button>
                          )}
                        </td>
                      </>
                    ) : section === "documents" ? (
                      <>
                        <td>
                          <strong>{r.title}</strong>
                          <div className="sub">
                            {r.filename} ·{" "}
                            {Math.ceil((r.size_bytes || 0) / 1024)} KB
                          </div>
                        </td>
                        <td>{r.category}</td>
                        <td>{date(r.created_at!)}</td>
                        <td>
                          <Badge>{r.status}</Badge>
                        </td>
                        <td>
                          <Button size="sm" variant="outline" asChild>
                            <a href={`/api/documents/${r.id}/download`}>
                              <Download size={13} />
                              Download
                            </a>
                          </Button>
                        </td>
                      </>
                    ) : (
                      <>
                        <td>
                          <strong>{r.action}</strong>
                        </td>
                        <td>{r.actor}</td>
                        <td>{date(r.created_at!)}</td>
                        <td className="muted">
                          {r.target_id?.slice(0, 12) || "—"}
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      <Dialog
        open={!!access}
        onOpenChange={(value) => {
          if (!value) setAccess(null);
        }}
        title="Manage staff access"
        description="Role changes end the staff member’s existing sessions."
      >
        {access && (
          <form onSubmit={saveAccess}>
            <div className="field">
              <label htmlFor="access-role">Role for {access.full_name}</label>
              <select id="access-role" name="role" defaultValue={access.role}>
                <option value="institution_admin">
                  Institution administrator
                </option>
                <option value="placement_officer">Placement officer</option>
                <option value="hod">HOD / Department coordinator</option>
                <option value="faculty">Subject teacher</option>
                <option value="campus_staff">
                  Campus office (principal / dean / director)
                </option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="access-department">
                Department (required for HOD)
              </label>
              <select
                id="access-department"
                name="department_id"
                defaultValue={access.department_id || ""}
              >
                <option value="">Institution-wide</option>
                {departments.data?.map((d) => (
                  <option value={d.id} key={d.id}>
                    {d.code}
                  </option>
                ))}
              </select>
            </div>
            <div className="dialog-actions">
              <Button disabled={pending}>
                {pending ? <Pending /> : "Save access"}
              </Button>
            </div>
          </form>
        )}
      </Dialog>
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title={
          edit
            ? "Edit department"
            : section === "documents"
              ? "Upload institutional evidence"
              : section === "staff"
                ? "Invite a staff member"
                : section === "companies"
                  ? "Add a company"
                  : "Add a department"
        }
        description={
          section === "staff"
            ? "Staff receive secure activation instructions and choose their own password."
            : "Records belong to your current institution."
        }
      >
        <form onSubmit={save}>
          {error && (
            <p
              role="alert"
              className="field-error"
              style={{ marginBottom: 15 }}
            >
              {error}
            </p>
          )}
          {section === "departments" ? (
            <>
              <Field
                name="code"
                label="Department code"
                value={edit?.code}
                placeholder="CSE"
              />
              <Field
                name="name"
                label="Department name"
                value={edit?.name}
                placeholder="Computer Science & Engineering"
              />
            </>
          ) : section === "companies" ? (
            <>
              <Field name="name" label="Company name" />
              <Field name="sector" label="Sector" value="Technology" />
              <Field
                name="website"
                label="Website (optional)"
                type="url"
                required={false}
              />
            </>
          ) : section === "staff" ? (
            <>
              <Field name="full_name" label="Full name" />
              <Field name="email" label="Institutional email" type="email" />
              <Field name="roll_no" label="Staff login ID" />
              <div className="field">
                <label htmlFor="staff-role">Role</label>
                <select name="role" id="staff-role">
                  <option value="placement_officer">Placement officer</option>
                  <option value="hod">HOD / Department coordinator</option>
                  <option value="faculty">Subject teacher</option>
                  <option value="campus_staff">
                    Campus office (principal / dean / director)
                  </option>
                  <option value="institution_admin">
                    Institution administrator
                  </option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="staff-department">
                  Department (required for HOD)
                </label>
                <select name="department_id" id="staff-department">
                  <option value="">Institution-wide</option>
                  {departments.data?.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.code} · {d.name}
                    </option>
                  ))}
                </select>
              </div>
            </>
          ) : (
            <>
              <Field name="title" label="Document title" />
              <div className="field">
                <label htmlFor="doc-category">Category</label>
                <select id="doc-category" name="category">
                  <option>Academic records</option>
                  <option>Department evidence</option>
                  <option>Institution policy</option>
                  <option>Accreditation evidence</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="institution-file">
                  PDF or DOCX · up to 8 MB
                </label>
                <input
                  id="institution-file"
                  name="file"
                  type="file"
                  accept=".pdf,.docx"
                  required
                />
              </div>
            </>
          )}
          <div className="dialog-actions">
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
            >
              Cancel
            </Button>
            <Button disabled={pending}>
              {pending ? (
                <Pending />
              ) : section === "staff" ? (
                "Send invitation"
              ) : (
                "Save record"
              )}
            </Button>
          </div>
        </form>
      </Dialog>
    </>
  );
}
function Field({
  name,
  label,
  type = "text",
  required = true,
  value,
  placeholder,
}: {
  name: string;
  label: string;
  type?: string;
  required?: boolean;
  value?: string;
  placeholder?: string;
}) {
  return (
    <div className="field">
      <label htmlFor={`field-${name}`}>{label}</label>
      <input
        id={`field-${name}`}
        name={name}
        type={type}
        required={required}
        defaultValue={value}
        placeholder={placeholder}
      />
    </div>
  );
}
function SettingsPage({ user }: { user: User }) {
  const client = useQueryClient(),
    [pending, setPending] = useState(false),
    [error, setError] = useState("");
  const admin = ["institution_admin", "platform_admin"].includes(user.role);
  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setPending(true);
    setError("");
    try {
      await send(
        "/institution",
        Object.fromEntries(new FormData(e.currentTarget)),
        "PUT",
      );
      await client.invalidateQueries({ queryKey: ["me"] });
      toast.success("Institution settings saved.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPending(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="WORKSPACE SETTINGS"
        title={
          admin
            ? "Make this workspace your institution’s."
            : "Your account & privacy"
        }
        description="Clear identity, secure access and transparent data use."
      />
      <div className="grid-2">
        <section className="card card-pad">
          <h2>{admin ? "Institution details" : "Account details"}</h2>
          {admin ? (
            <form onSubmit={save} style={{ marginTop: 22 }}>
              <Field
                name="name"
                label="Institution name"
                value={user.institution.name}
              />
              <Field name="city" label="City" value={user.institution.city} />
              <div className="field">
                <label htmlFor="privacy-notice">
                  Institution privacy notice
                </label>
                <textarea
                  name="privacy_notice"
                  id="privacy-notice"
                  defaultValue={user.institution.privacy_notice}
                  required
                  minLength={20}
                />
              </div>
              {error && <p className="field-error">{error}</p>}
              <Button disabled={pending}>
                {pending ? (
                  <Pending />
                ) : (
                  <>
                    <Save size={14} />
                    Save settings
                  </>
                )}
              </Button>
            </form>
          ) : (
            <div className="stack" style={{ marginTop: 22 }}>
              <div>
                <label>Full name</label>
                <p>{user.full_name}</p>
              </div>
              <div>
                <label>Login ID</label>
                <p>{user.roll_no}</p>
              </div>
              <div>
                <label>Institution</label>
                <p>{user.institution.name}</p>
              </div>
              <div>
                <label>Email</label>
                <p>{user.email}</p>
              </div>
            </div>
          )}
        </section>
        <div className="stack">
          <section className="card card-pad">
            <div className="row">
              <div className="icon-tile teal">
                <LockKeyhole size={22} />
              </div>
              <h2>Account security</h2>
            </div>
            <p className="small" style={{ marginBlock: 18 }}>
              Passwords are protected with Argon2id. Sessions expire
              automatically. Use the sign-in page’s password reset to choose a
              new password; it also ends existing sessions.
            </p>
            <Button variant="outline" asChild>
              <Link href="/login">
                Open sign-in & password reset <ArrowRight size={14} />
              </Link>
            </Button>
          </section>
          <section className="card card-pad">
            <h2>Privacy & data requests</h2>
            <PrivacyActions user={user} />
            <p className="small" style={{ marginTop: 15 }}>
              {user.institution.privacy_notice}
            </p>
            <p className="hint" style={{ marginTop: 15 }}>
              Use your data export or submit a deletion request for
              administrator review.
            </p>
          </section>
        </div>
      </div>
    </>
  );
}
function ReportsPage() {
  return (
    <>
      <PageHeading
        eyebrow="PLACEMENT REPORTS"
        title="Useful records. Clear decisions."
        description="Export current recruitment records for your institution’s review."
      />
      <div className="grid-2">
        <section className="card card-pad">
          <div className="icon-tile">
            <FileText size={25} />
          </div>
          <h2 style={{ marginTop: 20 }}>Recruitment activity report</h2>
          <p className="small" style={{ marginBlock: 15 }}>
            A CSV of recruitment drives, their current status, applications and
            recorded offers. Values come from the institution database.
          </p>
          <Button asChild>
            <a href="/api/reports/placement.csv">
              <Download size={14} />
              Download CSV report
            </a>
          </Button>
        </section>
        <section className="card card-pad">
          <Badge tone="amber">Phase 2</Badge>
          <h2 style={{ marginTop: 20 }}>Institutional intelligence reports</h2>
          <p className="small" style={{ marginBlock: 15 }}>
            Evidence-backed analysis, skill-gap reports and cohort preparation
            insights will become available after the Phase 2 intelligence
            pipeline is connected.
          </p>
          <Link href="/app/analytics" className="text-link">
            View current placement metrics <ArrowRight size={14} />
          </Link>
        </section>
      </div>
    </>
  );
}

export function NotificationsPage() {
  const query = useQuery({
    queryKey: ["notifications"],
    queryFn: () =>
      api<{ id: string; title: string; message: string; created_at: string }[]>(
        "/notifications",
      ),
  });
  return (
    <>
      <PageHeading
        eyebrow="NOTIFICATION CENTER"
        title="Stay in the loop."
        description="Recruitment announcements and updates from your institution."
      />
      {query.isLoading ? (
        <Skeleton />
      ) : query.error ? (
        <Failure error={query.error} />
      ) : (
        <section className="card">
          {query.data?.length ? (
            query.data.map((n) => (
              <article className="list-item" key={n.id}>
                <div className="row">
                  <div className="icon-tile">
                    <Bell size={21} />
                  </div>
                  <div>
                    <h3>{n.title}</h3>
                    <p>{n.message}</p>
                    <p className="hint">{date(n.created_at)}</p>
                  </div>
                </div>
              </article>
            ))
          ) : (
            <Empty
              title="You’re all caught up"
              description="New recruitment drives and institution announcements will appear here."
            />
          )}
        </section>
      )}
    </>
  );
}

export function ApplicationsPage({ user }: { user: User }) {
  const client = useQueryClient();
  const manager = [
    "institution_admin",
    "platform_admin",
    "placement_officer",
  ].includes(user.role);
  const query = useQuery({
    queryKey: ["applications"],
    queryFn: () =>
      api<
        {
          id: string;
          student: string;
          position: string;
          company: string;
          status: string;
          created_at: string;
        }[]
      >("/applications"),
  });
  async function update(id: string, status: string) {
    try {
      await send(`/applications/${id}?status=${status}`, undefined, "PATCH");
      await client.invalidateQueries({ queryKey: ["applications"] });
      await client.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success("Application status updated.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="RECRUITMENT TRACKING"
        title="Every application, in view."
        description="Track student registrations and the next step in each opportunity."
      />
      {query.isLoading ? (
        <Skeleton />
      ) : query.error ? (
        <Failure error={query.error} />
      ) : (
        <section className="card">
          {query.data?.length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Student</th>
                    <th>Company & position</th>
                    <th>Registered</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {query.data.map((a) => (
                    <tr key={a.id}>
                      <td>
                        <strong>{a.student}</strong>
                      </td>
                      <td>
                        {a.company}
                        <div className="sub">{a.position}</div>
                      </td>
                      <td>{date(a.created_at)}</td>
                      <td>
                        {manager ? (
                          <select
                            aria-label={`Status for ${a.student}`}
                            value={a.status}
                            onChange={(e) => void update(a.id, e.target.value)}
                          >
                            {[
                              "registered",
                              "shortlisted",
                              "interview",
                              "offered",
                              "rejected",
                            ].map((s) => (
                              <option key={s}>{s}</option>
                            ))}
                          </select>
                        ) : (
                          <Badge
                            tone={a.status === "offered" ? "green" : "blue"}
                          >
                            {a.status}
                          </Badge>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty
              title="No applications yet"
              description="Student registrations for recruitment drives will appear here."
            />
          )}
        </section>
      )}
    </>
  );
}
