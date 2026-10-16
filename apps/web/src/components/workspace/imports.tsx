"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import {
  UploadCloud,
  Download,
  ArrowRight,
  CheckCircle2,
  ShieldCheck,
  FileSpreadsheet,
  RefreshCw,
} from "lucide-react";
import { toast } from "sonner";
import { api, send, type ImportJob } from "@/lib/api";
import { date } from "@/lib/utils";
import { Button } from "../ui/button";
import {
  Badge,
  CardHeading,
  Empty,
  Failure,
  PageHeading,
  Pending,
} from "../ui/common";

const columns = [
  "roll_no",
  "full_name",
  "email",
  "department",
  "graduation_year",
  "cgpa",
  "active_backlogs",
  "phone",
  "section",
  "academic_year",
  "semester",
];
const optionalColumns = ["phone", "section", "academic_year", "semester"];
export function ImportsPage() {
  const client = useQueryClient();
  const [file, setFile] = useState<File | null>(null),
    [headers, setHeaders] = useState<string[]>([]),
    [mapping, setMapping] = useState<Record<string, string>>({}),
    [policy, setPolicy] = useState("skip"),
    [job, setJob] = useState<ImportJob | null>(null),
    [pending, setPending] = useState(false),
    [error, setError] = useState<Error | null>(null);
  const history = useQuery({
    queryKey: ["imports"],
    queryFn: () => api<ImportJob[]>("/imports"),
  });
  const progress = useQuery({
    queryKey: ["import", job?.id],
    queryFn: () => api<ImportJob>(`/imports/${job!.id}`),
    enabled: !!job,
    refetchInterval: (q) =>
      ["queued", "running"].includes(q.state.data?.status || "") ? 1000 : false,
  });
  const current = progress.data || job,
    step = current ? (current.status === "preview" ? 2 : 3) : 1;
  async function choose(chosen: File | undefined) {
    setJob(null);
    setError(null);
    if (!chosen) return;
    setFile(chosen);
    if (chosen.size > 8 * 1024 * 1024) {
      setError(new Error("CSV exceeds 8 MB."));
      return;
    }
    const first = (await chosen.text())
      .replace(/^\uFEFF/, "")
      .split(/\r?\n/)[0];
    const values = (first.match(/("(?:[^"]|"")*"|[^,]*)(,|$)/g) || [])
      .filter(Boolean)
      .map((s) =>
        s.replace(/,$/, "").replace(/^"|"$/g, "").replaceAll('""', '"'),
      )
      .filter(Boolean);
    setHeaders(values);
    setMapping(
      Object.fromEntries(columns.map((c) => [c, values.includes(c) ? c : ""])),
    );
  }
  async function preview() {
    if (!file) return;
    setPending(true);
    setError(null);
    const body = new FormData();
    body.append("file", file);
    body.append("policy", policy);
    body.append("mapping", JSON.stringify(mapping));
    try {
      const result = await api<ImportJob>("/imports/preview", {
        method: "POST",
        body,
      });
      client.setQueryData(["import", result.id], result);
      setJob(result);
      await history.refetch();
    } catch (e) {
      setError(e as Error);
    } finally {
      setPending(false);
    }
  }
  async function confirm() {
    if (!current) return;
    setPending(true);
    setError(null);
    try {
      const result = await send<ImportJob>(`/imports/${current.id}/confirm`);
      client.setQueryData(["import", result.id], result);
      setJob(result);
      await history.refetch();
      await client.invalidateQueries({ queryKey: ["dashboard"] });
      await client.invalidateQueries({ queryKey: ["students"] });
      toast.success(
        result.status === "completed"
          ? "Student import complete"
          : "Import queued. You can safely leave this page.",
      );
    } catch (e) {
      setError(e as Error);
    } finally {
      setPending(false);
    }
  }
  const percent = current
    ? current.status === "completed"
      ? 100
      : Math.round(
          (current.processed / Math.max(1, current.total - current.errors)) *
            100,
        )
    : 0;
  return (
    <>
      <PageHeading
        eyebrow="SECURE BULK ONBOARDING"
        title="A thoughtful start for every student"
        description="Import up to 20,000 students, validate the details, then send secure invitations."
      >
        <Button variant="outline" asChild>
          <a href="/api/imports/template">
            <Download size={15} />
            Download CSV template
          </a>
        </Button>
      </PageHeading>
      <div className="stepper">
        {["Upload & map columns", "Review validation", "Import & invite"].map(
          (s, i) => (
            <div className={`step ${step >= i + 1 ? "active" : ""}`} key={s}>
              <b>{step > i + 1 ? <CheckCircle2 size={13} /> : i + 1}</b>
              <span>{s}</span>
            </div>
          ),
        )}
      </div>
      {error && (
        <div style={{ marginBottom: 20 }}>
          <Failure error={error} />
        </div>
      )}
      <div className="card card-pad">
        {!current ? (
          <>
            <div className="upload-zone">
              <UploadCloud size={34} />
              <h3>Bring your student registry into CampusMind</h3>
              <p className="small">
                UTF-8 CSV · Up to 8 MB · Synthetic records for demonstration
              </p>
              <input
                type="file"
                aria-label="Choose student CSV"
                accept=".csv,text/csv"
                onChange={(e) => void choose(e.target.files?.[0])}
              />
            </div>
            {file && headers.length > 0 && (
              <>
                <div className="card-heading" style={{ paddingInline: 0 }}>
                  <div>
                    <h2>Map your columns</h2>
                    <p>Match each required field to a column in {file.name}.</p>
                  </div>
                  <Badge tone="blue">{headers.length} columns detected</Badge>
                </div>
                <div className="form-grid">
                  {columns.map((c) => (
                    <div className="field" key={c}>
                      <label htmlFor={`map-${c}`}>
                        {c.replaceAll("_", " ")}{" "}
                        {!optionalColumns.includes(c) && "*"}
                      </label>
                      <select
                        id={`map-${c}`}
                        value={mapping[c] || ""}
                        onChange={(e) =>
                          setMapping({ ...mapping, [c]: e.target.value })
                        }
                      >
                        <option value="">
                          {optionalColumns.includes(c)
                            ? "Not provided"
                            : "Select CSV column"}
                        </option>
                        {headers.map((h) => (
                          <option key={h}>{h}</option>
                        ))}
                      </select>
                    </div>
                  ))}
                </div>
                <div className="field">
                  <label htmlFor="duplicate-policy">
                    When a student already exists
                  </label>
                  <select
                    id="duplicate-policy"
                    value={policy}
                    onChange={(e) => setPolicy(e.target.value)}
                  >
                    <option value="skip">Skip existing accounts</option>
                    <option value="update">
                      Update matching student profiles
                    </option>
                  </select>
                  <p className="hint">
                    Updates require matching roll number and email. Existing
                    passwords and account activation remain unchanged.
                  </p>
                </div>
                <Button
                  disabled={
                    pending ||
                    columns
                      .filter((c) => !optionalColumns.includes(c))
                      .some((c) => !mapping[c])
                  }
                  onClick={() => void preview()}
                >
                  {pending ? (
                    <Pending label="Validating rows…" />
                  ) : (
                    <>
                      Validate & preview <ArrowRight size={15} />
                    </>
                  )}
                </Button>
              </>
            )}
          </>
        ) : (
          <>
            <div className="between">
              <div className="row">
                <div className="icon-tile">
                  <FileSpreadsheet size={23} />
                </div>
                <div>
                  <h2>{current.filename}</h2>
                  <p className="hint">
                    Duplicate policy: {current.policy} · Institution determined
                    by your signed-in account
                  </p>
                </div>
              </div>
              <Badge
                tone={
                  current.status === "completed"
                    ? "green"
                    : current.status === "failed"
                      ? "red"
                      : "blue"
                }
              >
                {current.status}
              </Badge>
            </div>
            <div className="summary-grid">
              {(current.status === "preview"
                ? [
                    ["Total rows", current.total],
                    ["Ready to process", current.total - current.errors],
                    [
                      "Existing duplicates",
                      job?.actions?.skip || job?.actions?.update || 0,
                    ],
                    ["Validation errors", current.errors],
                  ]
                : [
                    ["Created", current.created],
                    ["Updated", current.updated],
                    ["Skipped", current.skipped],
                    ["Errors", current.errors],
                  ]
              ).map(([label, value]) => (
                <div className="summary-cell" key={label}>
                  <strong>{Number(value).toLocaleString()}</strong>
                  <span>{label}</span>
                </div>
              ))}
            </div>
            {current.status !== "preview" && (
              <div className="progress-row">
                <div className="progress-label">
                  <span>
                    {current.status === "completed"
                      ? "Import complete"
                      : current.status === "failed"
                        ? "Import interrupted"
                        : "Creating accounts and delivering invitations…"}
                  </span>
                  <strong>{Math.min(100, percent)}%</strong>
                </div>
                <div
                  className="progress-track"
                  role="progressbar"
                  aria-valuenow={Math.min(100, percent)}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label="Import progress"
                >
                  <motion.div
                    className="progress-fill teal"
                    animate={{ width: `${Math.min(100, percent)}%` }}
                    transition={{ duration: 0.4 }}
                  />
                </div>
                {current.failure && (
                  <p className="field-error">{current.failure}</p>
                )}
              </div>
            )}
            {current.preview?.length && current.status === "preview" ? (
              <>
                <h3 style={{ marginBottom: 12 }}>
                  Preview · first {current.preview.length} valid rows
                </h3>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Row</th>
                        <th>Student</th>
                        <th>Email</th>
                        <th>Branch</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {current.preview.map((r) => (
                        <tr key={r._row}>
                          <td>{r._row}</td>
                          <td>
                            <strong>{r.full_name}</strong>
                            <div className="sub">{r.roll_no}</div>
                          </td>
                          <td>{r.email}</td>
                          <td>{r.department}</td>
                          <td>
                            <Badge
                              tone={r._action === "create" ? "green" : "amber"}
                            >
                              {r._action}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : null}
            {current.row_errors && current.row_errors.length > 0 && (
              <div style={{ marginTop: 20 }}>
                <h3>Validation issues</h3>
                {current.row_errors.slice(0, 10).map((e, i) => (
                  <p className="field-error" key={i}>
                    Row {e.row}: {e.message}
                  </p>
                ))}
              </div>
            )}
            <div className="dialog-actions">
              {current.errors > 0 && (
                <Button variant="outline" asChild>
                  <a href={`/api/imports/${current.id}/errors.csv`}>
                    <Download size={14} />
                    Error report
                  </a>
                </Button>
              )}
              {["preview", "failed"].includes(current.status) && (
                <Button
                  onClick={() => void confirm()}
                  disabled={pending || current.total === current.errors}
                >
                  {pending ? (
                    <Pending />
                  ) : (
                    <>
                      {current.status === "failed"
                        ? "Retry import"
                        : "Confirm import"}
                      <ArrowRight size={14} />
                    </>
                  )}
                </Button>
              )}
              {current.recoverable && (
                <Button
                  variant="outline"
                  disabled={pending}
                  onClick={async () => {
                    setPending(true);
                    try {
                      const result = await send<ImportJob>(
                        `/imports/${current.id}/recover`,
                      );
                      client.setQueryData(["import", result.id], result);
                      setJob(result);
                      await history.refetch();
                      toast.success(
                        "Expired job recovered. Retry the import to resume.",
                      );
                    } catch (error) {
                      setError(error as Error);
                    } finally {
                      setPending(false);
                    }
                  }}
                >
                  Recover interrupted processing
                </Button>
              )}
              {!["running", "queued"].includes(current.status) && (
                <Button
                  variant="outline"
                  onClick={() => {
                    setJob(null);
                    setFile(null);
                    setHeaders([]);
                  }}
                >
                  Start another import
                </Button>
              )}
            </div>
          </>
        )}
      </div>
      <div className="insight-note" style={{ marginBlock: 20 }}>
        <ShieldCheck />
        <span>
          No shared passwords. Every new account receives a short-lived,
          single-use invitation. If email delivery fails, an authorized officer
          can issue an audited one-time link from the student registry.
          Re-uploading an identical file with the same mapping and policy
          returns the existing job.
        </span>
      </div>
      <section className="card">
        <CardHeading
          title="Import history"
          description="Your institution’s recent onboarding operations"
        />
        <div style={{ padding: "0 20px 12px" }}>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void history.refetch()}
          >
            <RefreshCw size={12} />
            Refresh history
          </Button>
        </div>
        {history.error ? (
          <Failure error={history.error} />
        ) : history.data?.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>File</th>
                  <th>Imported</th>
                  <th>Rows</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {history.data.map((j) => (
                  <tr key={j.id}>
                    <td>
                      <strong>{j.filename}</strong>
                    </td>
                    <td>{date(j.created_at)}</td>
                    <td>{j.total.toLocaleString()}</td>
                    <td>
                      <Badge
                        tone={j.status === "completed" ? "green" : "neutral"}
                      >
                        {j.status}
                      </Badge>
                    </td>
                    <td>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          client.removeQueries({ queryKey: ["import", j.id] });
                          setJob(j);
                        }}
                      >
                        Inspect <ArrowRight size={12} />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            title="Your first import starts here"
            description="Completed and in-progress imports will appear in this history."
          />
        )}
      </section>
    </>
  );
}
