"use client";
import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Megaphone,
  CalendarDays,
  Download,
  CheckCheck,
  Users,
  FileSpreadsheet,
  ShieldCheck,
} from "lucide-react";
import { api, send, type User } from "@/lib/api";
import { Button } from "../ui/button";
import { Badge, PageHeading, Failure, Skeleton } from "../ui/common";
import { useAction } from "./intelligence";

type Department = { id: string; code: string; name: string };
type Audience = {
  department_id?: string | null;
  graduation_year?: number | null;
  academic_year?: number | null;
  semester?: number | null;
  section?: string;
  student_id?: string | null;
  student_roll_no?: string;
};
type Post = {
  id: string;
  title: string;
  message: string;
  office: string;
  kind: string;
  subject: string;
  author: string;
  created_at: string;
  due_at: string | null;
  filename: string | null;
  read_at: string | null;
  withdrawn: boolean;
  can_manage: boolean;
  audience: Audience;
};
type Slot = {
  id: string;
  subject: string;
  teacher: string;
  weekday: number;
  starts: string;
  ends: string;
  room: string;
  valid_from: string;
  valid_until: string;
  section: string;
  semester: number;
  academic_year: number;
  graduation_year: number;
  department_id: string;
};
type Preview = {
  id: string;
  kind: string;
  valid_rows: number;
  errors: { row: number; error: string }[];
  preview: Record<string, unknown>[];
  confirmed: boolean;
};
const days = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

export function CampusHub({
  user,
  timetableOnly = false,
}: {
  user: User;
  timetableOnly?: boolean;
}) {
  const admin = ["institution_admin", "platform_admin"].includes(user.role),
    student = user.role === "student";
  const [filter, setFilter] = useState("all"),
    [query, setQuery] = useState("");
  const posts = useQuery({
    queryKey: ["campus-posts"],
    queryFn: () => api<Post[]>("/campus/posts"),
    refetchInterval: 15000,
  });
  const slots = useQuery({
    queryKey: ["campus-timetable"],
    queryFn: () => api<Slot[]>("/campus/timetable"),
    refetchInterval: 30000,
  });
  const context = useQuery({
    queryKey: ["campus-context"],
    queryFn: () =>
      api<{ office: string | null; cohort: Audience | null }>(
        "/campus/context",
      ),
  });
  const departments = useQuery({
    queryKey: ["departments"],
    queryFn: () => api<Department[]>("/departments"),
  });
  const { busy, act } = useAction();
  const [delivery, setDelivery] = useState<
    Record<string, { delivered: number; acknowledged: number }>
  >({});
  const filtered = (posts.data || []).filter(
    (p) =>
      (filter === "all" || p.kind === filter) &&
      `${p.title} ${p.message} ${p.subject} ${p.office}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  const list = slots.data || [];
  return (
    <>
      <PageHeading
        eyebrow="CAMPUS HUB · CONNECTED COLLEGE"
        title={
          timetableOnly
            ? "Your classes. One clear schedule."
            : "The right update, for the right student."
        }
        description="Official notices, subject assignments and academic schedules, automatically matched to your institution and cohort."
      />
      <div className="row" style={{ marginBottom: 20 }}>
        {student && (
          <Button asChild>
            <Link href="/app/today">Open my Today dashboard</Link>
          </Button>
        )}
        <Button variant="outline" asChild>
          <Link href="/app/assignments">Assignments & feedback</Link>
        </Button>
        {(student || admin) && (
          <Button variant="outline" asChild>
            <Link href="/app/fees">Fees & receipts</Link>
          </Button>
        )}
      </div>
      <div className="metric-grid" style={{ marginBottom: 24 }}>
        <div className="card card-pad">
          <Megaphone size={22} />
          <h2>{(posts.data || []).filter((p) => !p.withdrawn).length}</h2>
          <p>Relevant updates</p>
        </div>
        <div className="card card-pad">
          <CheckCheck size={22} />
          <h2>
            {student
              ? (posts.data || []).filter((p) => !p.read_at).length
              : "Automatic"}
          </h2>
          <p>
            {student ? "Awaiting acknowledgement" : "Branch & cohort routing"}
          </p>
        </div>
        <div className="card card-pad">
          <CalendarDays size={22} />
          <h2>{list.length}</h2>
          <p>Scheduled teaching slots</p>
        </div>
      </div>
      {student && context.data?.cohort && (
        <p className="hint" style={{ marginBottom: 20 }}>
          Graduation {context.data.cohort.graduation_year} · Year{" "}
          {context.data.cohort.academic_year || "not assigned"} · Semester{" "}
          {context.data.cohort.semester || "not assigned"} · Section{" "}
          {context.data.cohort.section || "not assigned"}. Your institution
          manages academic routing.
        </p>
      )}
      {admin && <CampusAdministration departments={departments.data || []} />}
      {!timetableOnly && context.data?.office && (
        <Composer
          departments={departments.data || []}
          slots={list}
          office={context.data.office}
        />
      )}
      {!timetableOnly && (
        <section className="card card-pad" style={{ marginBlock: 24 }}>
          <div
            style={{
              display: "flex",
              gap: 12,
              flexWrap: "wrap",
              alignItems: "center",
              marginBottom: 20,
            }}
          >
            <h2 style={{ marginRight: "auto" }}>Campus noticeboard</h2>
            <input
              aria-label="Search campus updates"
              placeholder="Search subject, office or update"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <select
              aria-label="Filter update type"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            >
              <option value="all">All updates</option>
              <option value="announcement">Announcements</option>
              <option value="assignment">Assignments</option>
              <option value="resource">Resources</option>
            </select>
          </div>
          {posts.isPending && <Skeleton rows={3} />}
          {posts.error && (
            <Failure error={posts.error} retry={() => void posts.refetch()} />
          )}
          {!posts.isPending && !filtered.length && (
            <p>
              No matching updates yet. New announcements appear automatically;
              this page checks every 15 seconds.
            </p>
          )}
          {filtered.map((p) => (
            <article
              key={p.id}
              style={{
                borderTop: "1px solid var(--border, #e2e8f0)",
                paddingBlock: 22,
              }}
            >
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <Badge>{p.office.replaceAll("_", " ")}</Badge>
                <Badge>{p.kind}</Badge>
                {p.withdrawn && <Badge>Withdrawn</Badge>}
                {p.subject && <Badge>{p.subject}</Badge>}
              </div>
              <h3 style={{ marginTop: 12 }}>{p.title}</h3>
              <p className="hint">
                {p.author} · {new Date(p.created_at + "Z").toLocaleString()}
              </p>
              <p style={{ whiteSpace: "pre-wrap", marginBlock: 14 }}>
                {p.message}
              </p>
              {student && (
                <p className="hint">
                  Why you see this: your institution and current academic cohort
                  match this update’s audience.
                  {p.audience.section ? ` Section ${p.audience.section}.` : ""}
                  {p.audience.semester
                    ? ` Semester ${p.audience.semester}.`
                    : ""}
                </p>
              )}
              {p.due_at && (
                <p>Due: {new Date(p.due_at + "Z").toLocaleString()}</p>
              )}
              <div
                style={{
                  display: "flex",
                  gap: 10,
                  flexWrap: "wrap",
                  marginTop: 12,
                }}
              >
                {p.filename && !p.withdrawn && (
                  <Button variant="outline" asChild>
                    <a href={`/api/campus/posts/${p.id}/attachment`}>
                      <Download size={15} />
                      {p.filename}
                    </a>
                  </Button>
                )}
                {student && (
                  <Button
                    disabled={busy || !!p.read_at}
                    variant="outline"
                    onClick={() =>
                      void act(
                        () => send(`/campus/posts/${p.id}/acknowledge`),
                        "Acknowledgement recorded",
                      )
                    }
                  >
                    {p.read_at ? "Acknowledged" : "I have read this"}
                  </Button>
                )}
                {p.can_manage && (
                  <>
                    <Button
                      variant="outline"
                      onClick={() =>
                        void act(async () => {
                          const d = await api<{
                            delivered: number;
                            acknowledged: number;
                          }>(`/campus/posts/${p.id}/delivery`);
                          setDelivery((v) => ({ ...v, [p.id]: d }));
                        }, "Delivery summary loaded")
                      }
                    >
                      Delivery summary
                    </Button>
                    {!p.withdrawn && (
                      <Button
                        variant="ghost"
                        disabled={busy}
                        onClick={() =>
                          void act(
                            () =>
                              send(
                                `/campus/posts/${p.id}`,
                                undefined,
                                "DELETE",
                              ),
                            "Update withdrawn",
                          )
                        }
                      >
                        Withdraw
                      </Button>
                    )}
                  </>
                )}
              </div>
              {delivery[p.id] && (
                <p className="hint" style={{ marginTop: 10 }}>
                  {delivery[p.id].delivered} original recipients ·{" "}
                  {delivery[p.id].acknowledged} acknowledged
                </p>
              )}
            </article>
          ))}
        </section>
      )}
      <section className="card card-pad" style={{ marginTop: 24 }}>
        <h2>
          <CalendarDays
            size={20}
            style={{ display: "inline", marginRight: 8 }}
          />
          {student ? "My timetable" : "Teaching timetable"}
        </h2>
        <p className="hint" style={{ marginBlock: 12 }}>
          Monday = 0 in imports. Times follow the institution’s local timetable.
          Validity dates are shown for each schedule.
        </p>
        {slots.error && (
          <Failure error={slots.error} retry={() => void slots.refetch()} />
        )}
        {slots.isPending && <Skeleton rows={3} />}
        {!slots.isPending && !list.length && (
          <p>
            No timetable assigned yet. Administrators can import a cohort and
            teaching schedule above.
          </p>
        )}
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", minWidth: 660 }}>
            <thead>
              <tr>
                {[
                  "Day / time",
                  "Subject",
                  "Teacher",
                  "Cohort",
                  "Room",
                  "Valid dates",
                ].map((h) => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {list.map((s) => (
                <tr key={s.id}>
                  <td>
                    {days[s.weekday]}
                    <br />
                    {s.starts}–{s.ends}
                  </td>
                  <td>{s.subject}</td>
                  <td>{s.teacher}</td>
                  <td>
                    {
                      departments.data?.find((d) => d.id === s.department_id)
                        ?.code
                    }{" "}
                    · {s.section}
                    <br />
                    Year {s.academic_year} · Sem {s.semester} ·{" "}
                    {s.graduation_year}
                  </td>
                  <td>{s.room || "—"}</td>
                  <td>
                    {s.valid_from}
                    <br />
                    {s.valid_until}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

function Composer({
  departments,
  slots,
  office,
}: {
  departments: Department[];
  slots: Slot[];
  office: string;
}) {
  const { busy, act } = useAction();
  const [count, setCount] = useState<number | null>(null);
  const [selected, setSelected] = useState("");
  const [translation, setTranslation] = useState("");
  const selectedSlot = slots.find((s) => s.id === selected);
  const exact = office === "teacher";
  function body(form: HTMLFormElement) {
    const f = new FormData(form);
    return {
      title: f.get("title"),
      message: f.get("message"),
      kind: f.get("kind"),
      subject: f.get("subject") || "",
      due_at: f.get("due_at")
        ? new Date(String(f.get("due_at"))).toISOString()
        : null,
      audience: {
        department_id: f.get("department_id") || null,
        graduation_year: Number(f.get("graduation_year")) || null,
        academic_year: Number(f.get("academic_year")) || null,
        semester: Number(f.get("semester")) || null,
        section: String(f.get("section") || "")
          .trim()
          .toUpperCase(),
        student_roll_no: f.get("student_roll_no") || "",
      },
    };
  }
  return (
    <details className="card card-pad" style={{ marginTop: 24 }}>
      <summary style={{ cursor: "pointer", fontWeight: 650 }}>
        <Megaphone size={17} style={{ display: "inline", marginRight: 8 }} />
        Publish an update · {office}
      </summary>
      <p className="hint" style={{ marginTop: 14 }}>
        Blank audience fields mean all matching students. Subject assignments
        require an exact cohort and a current teaching assignment. Student IDs
        target one account.
      </p>
      {slots.length > 0 && (
        <label className="field" style={{ marginTop: 14 }}>
          Fill audience from timetable
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
          >
            <option value="">Choose a teaching slot</option>
            {slots.map((s) => (
              <option value={s.id} key={s.id}>
                {s.subject} · {s.section} · Semester {s.semester} · {s.teacher}
              </option>
            ))}
          </select>
        </label>
      )}
      <form
        key={selected}
        className="form-grid"
        style={{ marginTop: 18 }}
        onChange={() => setCount(null)}
        onSubmit={(e) => {
          e.preventDefault();
          const form = e.currentTarget,
            f = new FormData(form);
          void act(async () => {
            const data = new FormData();
            data.set("payload", JSON.stringify(body(form)));
            const file = f.get("file") as File;
            if (file?.size) data.set("file", file);
            const result = await api<{ recipients: number }>("/campus/posts", {
              method: "POST",
              body: data,
            });
            setCount(result.recipients);
            form.reset();
          }, "Published to matching students");
        }}
      >
        <label className="field">
          Title
          <input name="title" required minLength={3} maxLength={200} />
        </label>
        <label className="field">
          Type
          <select
            name="kind"
            defaultValue={exact ? "assignment" : "announcement"}
          >
            <option value="announcement">Announcement</option>
            <option value="assignment">Subject assignment</option>
            <option value="resource">Learning resource</option>
          </select>
        </label>
        <div className="field" style={{ gridColumn: "1 / -1" }}>
          <label htmlFor="campus-message">Message</label>
          <textarea
            id="campus-message"
            name="message"
            required
            maxLength={15000}
            rows={4}
          />
          <Button
            type="button"
            variant="outline"
            disabled={busy}
            onClick={(e) => {
              const form = e.currentTarget.closest("form")!;
              const text = String(new FormData(form).get("message") || "");
              void act(async () => {
                const draft = await send<{
                  translation: string;
                  message?: string;
                }>("/campus/translation-draft", { text });
                setTranslation(draft.translation);
                if (!draft.translation)
                  throw new Error(
                    draft.message || "Enter a translation manually.",
                  );
              }, "Translation draft ready for staff review");
            }}
          >
            Draft Odia translation · local model
          </Button>
        </div>
        <div className="field" style={{ gridColumn: "1 / -1" }}>
          <label htmlFor="odia-draft">
            Odia draft · review names, dates and amounts before adding it to the
            message
          </label>
          <textarea
            id="odia-draft"
            lang="or"
            value={translation}
            onChange={(e) => setTranslation(e.target.value)}
            rows={3}
            placeholder="Optional: type an Odia translation or request a local-model draft."
          />
          <Button
            variant="outline"
            type="button"
            disabled={!translation.trim()}
            onClick={(e) => {
              const input = e.currentTarget
                .closest("form")
                ?.elements.namedItem("message") as HTMLTextAreaElement;
              input.value = `${input.value}\n\nଓଡ଼ିଆ ସୂଚନା\n${translation}`;
              setTranslation("");
              setCount(null);
            }}
          >
            Add reviewed translation to message
          </Button>
        </div>
        <label className="field">
          Branch
          <select
            name="department_id"
            defaultValue={selectedSlot?.department_id || ""}
          >
            <option value="">All departments</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.code}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Section
          <input
            name="section"
            maxLength={30}
            defaultValue={selectedSlot?.section}
          />
        </label>
        <label className="field">
          Graduation year
          <input
            name="graduation_year"
            type="number"
            min={2020}
            max={2100}
            defaultValue={selectedSlot?.graduation_year}
          />
        </label>
        <label className="field">
          Academic year
          <input
            name="academic_year"
            type="number"
            min={1}
            max={6}
            defaultValue={selectedSlot?.academic_year}
          />
        </label>
        <label className="field">
          Semester
          <input
            name="semester"
            type="number"
            min={1}
            max={12}
            defaultValue={selectedSlot?.semester}
          />
        </label>
        <label className="field">
          Subject
          <input
            name="subject"
            maxLength={100}
            defaultValue={selectedSlot?.subject}
          />
        </label>
        <label className="field">
          Individual registration / roll number (optional)
          <input name="student_roll_no" placeholder="Example: REG2026001" />
        </label>
        <label className="field">
          Deadline (optional)
          <input type="datetime-local" name="due_at" />
        </label>
        <label className="field">
          Private document (up to 8 MB)
          <input name="file" type="file" accept=".pdf,.docx,.txt" />
        </label>
        <div
          style={{
            gridColumn: "1 / -1",
            display: "flex",
            gap: 10,
            alignItems: "center",
            flexWrap: "wrap",
          }}
        >
          <Button
            type="button"
            variant="outline"
            disabled={busy}
            onClick={(e) => {
              const form = e.currentTarget.closest("form")!;
              void act(async () => {
                const r = await send<{ recipients: number }>(
                  "/campus/posts/preview",
                  body(form),
                );
                setCount(r.recipients);
              }, "Audience checked");
            }}
          >
            <Users size={16} />
            Check recipients
          </Button>
          <Button disabled={busy} type="submit">
            Publish update
          </Button>
          {count !== null && <span>{count} matching student accounts</span>}
        </div>
      </form>
    </details>
  );
}

function CampusAdministration({ departments }: { departments: Department[] }) {
  const { busy, act } = useAction();
  const [preview, setPreview] = useState<Preview | null>(null);
  const staff = useQuery({
    queryKey: ["staff"],
    queryFn: () =>
      api<{ id: string; full_name: string; role: string }[]>("/staff"),
  });
  const grants = useQuery({
    queryKey: ["campus-authorities"],
    queryFn: () =>
      api<
        {
          id: string;
          user_id: string;
          office: string;
          department_id: string | null;
        }[]
      >("/campus/authorities"),
  });
  const history = useQuery({
    queryKey: ["campus-imports"],
    queryFn: () =>
      api<
        {
          id: string;
          kind: string;
          rows: number;
          errors: number;
          confirmed_at: string | null;
        }[]
      >("/campus/imports"),
  });
  return (
    <details className="card card-pad" style={{ marginBlock: 24 }}>
      <summary style={{ cursor: "pointer", fontWeight: 650 }}>
        <ShieldCheck size={18} style={{ display: "inline", marginRight: 8 }} />
        Campus administration · routing & publishing permissions
      </summary>
      <h3 style={{ marginTop: 24 }}>
        1. Import student cohorts or teaching timetables
      </h3>
      <p className="hint" style={{ marginBlock: 12 }}>
        Use one CSV or XLSX sheet with template headers. Onboard students and
        invite staff first in Student Registry / Staff & roles. Timetable
        imports replace the full schedule only for cohorts included in the file;
        prior versions are retained. Dates: YYYY-MM-DD; times: HH:MM as text.
      </p>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <Button variant="outline" asChild>
          <a href="/api/campus/template/cohorts">
            <Download size={15} />
            Cohort template
          </a>
        </Button>
        <Button variant="outline" asChild>
          <a href="/api/campus/template/timetable">
            <Download size={15} />
            Timetable template
          </a>
        </Button>
      </div>
      <form
        className="form-grid"
        style={{ marginTop: 18 }}
        onSubmit={(e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          void act(
            async () =>
              setPreview(
                await api<Preview>("/campus/imports/preview", {
                  method: "POST",
                  body: f,
                }),
              ),
            "Sheet validated",
          );
        }}
      >
        <label className="field">
          Import type
          <select name="kind">
            <option value="cohorts">Student branch / section / semester</option>
            <option value="timetable">Teaching timetable</option>
          </select>
        </label>
        <label className="field">
          CSV / XLSX
          <input
            required
            name="file"
            type="file"
            accept=".csv,.xlsx"
            onChange={() => setPreview(null)}
          />
        </label>
        <Button disabled={busy}>
          <FileSpreadsheet size={16} />
          Validate & preview
        </Button>
      </form>
      {preview && (
        <div style={{ marginTop: 20 }}>
          <Badge>
            {preview.valid_rows} valid rows · {preview.errors.length} errors
          </Badge>
          <p style={{ marginBlock: 10 }}>
            No changes are applied until confirmation. Fix every row error
            before importing.
          </p>
          {preview.errors.slice(0, 30).map((r) => (
            <p key={r.row} role="alert">
              Row {r.row}: {r.error}
            </p>
          ))}
          <div style={{ overflowX: "auto", maxHeight: 240 }}>
            <table>
              <thead>
                <tr>
                  {Object.keys(preview.preview[0] || {})
                    .filter((k) => !k.endsWith("_id"))
                    .map((k) => (
                      <th key={k}>{k}</th>
                    ))}
                </tr>
              </thead>
              <tbody>
                {preview.preview.map((r, i) => (
                  <tr key={i}>
                    {Object.entries(r)
                      .filter(([k]) => !k.endsWith("_id"))
                      .map(([k, v]) => (
                        <td key={k}>{String(v)}</td>
                      ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Button
            style={{ marginTop: 12 }}
            disabled={
              busy ||
              !!preview.errors.length ||
              preview.confirmed ||
              !preview.valid_rows
            }
            onClick={() =>
              void act(async () => {
                await send(`/campus/imports/${preview.id}/confirm`);
                setPreview({ ...preview, confirmed: true });
              }, "Academic routing updated")
            }
          >
            {preview.confirmed ? "Imported" : "Confirm import"}
          </Button>
        </div>
      )}
      <h3 style={{ marginTop: 28 }}>2. Assign official publishing authority</h3>
      <p className="hint">
        Create subject teachers with the Subject teacher role. Create principal,
        dean and director accounts with Campus office role, then assign their
        publishing office here. This grants communication access without
        placement or student-record access.
      </p>
      <form
        className="form-grid"
        style={{ marginTop: 16 }}
        onSubmit={(e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          void act(
            () =>
              send(
                "/campus/authorities",
                {
                  user_id: f.get("user_id"),
                  office: f.get("office"),
                  department_id: f.get("department_id") || null,
                },
                "PUT",
              ),
            "Publishing authority assigned",
          );
        }}
      >
        <label className="field">
          Staff account
          <select name="user_id" required>
            <option value="">Select staff</option>
            {staff.data?.map((s) => (
              <option value={s.id} key={s.id}>
                {s.full_name} · {s.role}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Office
          <select name="office">
            {[
              "principal",
              "dean",
              "director",
              "department",
              "placement",
              "teacher",
            ].map((o) => (
              <option key={o}>{o}</option>
            ))}
          </select>
        </label>
        <label className="field">
          Department scope
          <select name="department_id">
            <option value="">Institution-wide (leadership only)</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.code}
              </option>
            ))}
          </select>
        </label>
        <Button disabled={busy}>Assign authority</Button>
      </form>
      {grants.data?.map((g) => (
        <div
          key={g.id}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            marginTop: 12,
          }}
        >
          <span>
            {staff.data?.find((s) => s.id === g.user_id)?.full_name} ·{" "}
            {g.office} ·{" "}
            {departments.find((d) => d.id === g.department_id)?.code ||
              "Institution"}
          </span>
          <Button
            variant="ghost"
            disabled={busy}
            onClick={() =>
              void act(
                () => send(`/campus/authorities/${g.id}`, undefined, "DELETE"),
                "Authority revoked",
              )
            }
          >
            Revoke grant
          </Button>
        </div>
      ))}
      <h3 style={{ marginTop: 28 }}>Import history</h3>
      {history.data?.slice(0, 10).map((j) => (
        <p key={j.id} className="hint" style={{ marginTop: 8 }}>
          {j.kind} · {j.rows} rows · {j.errors} errors ·{" "}
          {j.confirmed_at ? "Applied" : "Preview only"}
        </p>
      ))}
    </details>
  );
}
