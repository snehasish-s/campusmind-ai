"use client";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BriefcaseBusiness,
  Plus,
  MapPin,
  IndianRupee,
  CalendarDays,
  ArrowRight,
  Search,
  Pencil,
  XCircle,
  CheckCircle2,
} from "lucide-react";
import { DriveIntelligence, AppealsPage } from "./insights";
import { toast } from "sonner";
import { api, send, type Drive, type User } from "@/lib/api";
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

export function DrivesPage({ user }: { user: User }) {
  const client = useQueryClient(),
    manager = [
      "institution_admin",
      "platform_admin",
      "placement_officer",
    ].includes(user.role),
    student = user.role === "student";
  const [editing, setEditing] = useState<Drive | null | undefined>(undefined),
    [selected, setSelected] = useState<Drive | null>(null),
    [search, setSearch] = useState(""),
    [filter, setFilter] = useState("all"),
    [pending, setPending] = useState(false);
  const query = useQuery({
    queryKey: ["drives"],
    queryFn: () => api<Drive[]>("/drives"),
  });
  async function action(drive: Drive, command: string) {
    setPending(true);
    try {
      await send(`/drives/${drive.id}/${command}`);
      await client.invalidateQueries({ queryKey: ["drives"] });
      await client.invalidateQueries({ queryKey: ["dashboard"] });
      await client.invalidateQueries({ queryKey: ["applications"] });
      toast.success(
        command === "apply" ? "Application registered." : "Drive closed.",
      );
      setSelected(null);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setPending(false);
    }
  }
  const items = query.data?.filter(
    (d) =>
      (filter === "all" ||
        (filter === "eligible" ? d.eligible : d.status === filter)) &&
      `${d.company_name} ${d.position}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  return (
    <>
      <PageHeading
        eyebrow="RECRUITMENT WORKSPACE"
        title={
          student
            ? "Find your next opportunity."
            : "Opportunities, thoughtfully managed."
        }
        description={
          student
            ? "Explore drives from your institution and check where your profile fits."
            : "Create, publish and coordinate your institution’s recruitment drives."
        }
      >
        {manager && (
          <Button onClick={() => setEditing(null)}>
            <Plus size={16} />
            Create recruitment drive
          </Button>
        )}
      </PageHeading>
      <div className="table-toolbar card" style={{ marginBottom: 22 }}>
        <div className="search-field">
          <Search />
          <input
            aria-label="Search recruitment drives"
            placeholder="Search company or position…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          aria-label="Filter recruitment drives"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          <option value="all">All drives</option>
          <option value="published">Published</option>
          <option value="open">Open for registration</option>
          <option value="closed">Closed</option>
          {student ? (
            <option value="eligible">Matching my profile</option>
          ) : (
            <option value="draft">Drafts</option>
          )}
        </select>
        <span className="muted small">{items?.length || 0} opportunities</span>
      </div>
      {query.isLoading ? (
        <Skeleton />
      ) : query.error ? (
        <Failure error={query.error} />
      ) : !items?.length ? (
        <div className="card">
          <Empty
            title="Your next opportunity is on its way"
            description={
              manager
                ? "Create a recruitment drive to get started. Drafts remain private until you publish them."
                : "Published drives from your institution will appear here. Try adjusting your filters."
            }
          />
        </div>
      ) : (
        <div className="grid-3">
          {items.map((d) => (
            <article className="card drive-card" key={d.id}>
              <div className="between">
                <div className="company-logo">{d.company_name[0]}</div>
                <Badge
                  tone={
                    d.status === "published"
                      ? "green"
                      : d.status === "draft"
                        ? "amber"
                        : "neutral"
                  }
                >
                  {d.status}
                </Badge>
              </div>
              <div>
                <p className="small" style={{ marginBottom: 5 }}>
                  {d.company_name}
                </p>
                <h3>{d.position}</h3>
              </div>
              <p className="description">{d.description}</p>
              <div className="drive-meta">
                <span>
                  <MapPin size={13} />
                  {d.location}
                </span>
                <span>
                  <IndianRupee size={13} />
                  {d.ctc}
                </span>
                <span>
                  <CalendarDays size={13} />
                  {date(d.drive_date)}
                </span>
                <span>
                  <BriefcaseBusiness size={13} />
                  {d.employment_type}
                </span>
              </div>
              <div className="chips">
                {d.required_skills.slice(0, 4).map((s) => (
                  <Badge key={s}>{s}</Badge>
                ))}
              </div>
              <div className="drive-footer">
                <span className="small muted">
                  {student
                    ? d.applied
                      ? "Registered"
                      : d.eligible
                        ? "Profile matches"
                        : "Check eligibility"
                    : `${d.applications} applications`}
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setSelected(d);
                    if (student)
                      void send(`/drives/${d.id}/view`).catch(() => undefined);
                  }}
                >
                  View details <ArrowRight size={13} />
                </Button>
              </div>
            </article>
          ))}
        </div>
      )}
      {manager && <AppealsPage />}
      <Dialog
        open={!!selected}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
        title={selected?.position || "Recruitment drive"}
        description={selected?.company_name}
      >
        {selected && (
          <div className="stack">
            <div className="row">
              <Badge
                tone={selected.status === "published" ? "green" : "neutral"}
              >
                {selected.status}
              </Badge>
              <Badge tone="blue">{selected.employment_type}</Badge>
            </div>
            <p className="small" style={{ whiteSpace: "pre-wrap" }}>
              {selected.description}
            </p>
            <div className="grid-2 small">
              <div>
                <label>Compensation</label>
                {selected.ctc}
              </div>
              <div>
                <label>Location</label>
                {selected.location}
              </div>
              <div>
                <label>Registration closes</label>
                {date(selected.deadline)}
              </div>
              <div>
                <label>Drive date</label>
                {date(selected.drive_date)}
              </div>
              <div>
                <label>Minimum CGPA / maximum backlogs</label>
                {selected.min_cgpa} / {selected.max_backlogs}
              </div>
              <div>
                <label>Eligible graduation batch</label>
                {selected.graduation_year}
              </div>
            </div>
            <div>
              <label>Eligible branches</label>
              <p className="small">
                {selected.eligible_branches.join(", ") || "All departments"}
              </p>
            </div>
            <div>
              <label>Required skills</label>
              <div className="chips">
                {selected.required_skills.map((s) => (
                  <Badge key={s}>{s}</Badge>
                ))}
              </div>
            </div>
            <div>
              <label>Selection rounds</label>
              <p className="small">
                {selected.selection_rounds.join(" → ") || "To be announced"}
              </p>
            </div>
            {selected.additional_requirements && (
              <div>
                <label>Additional requirements</label>
                <p className="small">{selected.additional_requirements}</p>
              </div>
            )}
            {student && (
              <div className="insight-note">
                <CheckCircle2 />
                <span>
                  {selected.applied
                    ? "You have registered for this drive."
                    : selected.eligible
                      ? "Your academic profile matches the stated criteria. Confirm your profile is current before registering."
                      : "Your academic profile does not currently match every eligibility criterion for this drive."}
                </span>
              </div>
            )}
            <DriveIntelligence drive={selected} user={user} />
            <div className="dialog-actions">
              {manager ? (
                <>
                  <Button
                    variant="outline"
                    disabled={["closed", "completed"].includes(selected.status)}
                    onClick={() => {
                      setEditing(selected);
                      setSelected(null);
                    }}
                  >
                    <Pencil size={14} />
                    Edit drive
                  </Button>
                  {["published", "open"].includes(selected.status) && (
                    <Button
                      variant="danger"
                      disabled={pending}
                      onClick={() => void action(selected, "close")}
                    >
                      <XCircle size={14} />
                      Close registration
                    </Button>
                  )}
                </>
              ) : student ? (
                <Button
                  disabled={
                    pending ||
                    selected.applied ||
                    !selected.eligible ||
                    !["published", "open"].includes(selected.status) ||
                    new Date(selected.deadline + "Z") <= new Date()
                  }
                  onClick={() => void action(selected, "apply")}
                >
                  {pending ? (
                    <Pending />
                  ) : selected.applied ? (
                    "Already registered"
                  ) : (
                    <>
                      Register for drive <ArrowRight size={14} />
                    </>
                  )}
                </Button>
              ) : null}
            </div>
          </div>
        )}
      </Dialog>
      <Dialog
        open={editing !== undefined}
        onOpenChange={(open) => {
          if (!open) setEditing(undefined);
        }}
        title={
          editing ? "Edit recruitment drive" : "Create a recruitment drive"
        }
        description="Drafts are visible only to authorized institution staff."
      >
        {editing !== undefined && (
          <DriveForm
            key={editing?.id || "new"}
            drive={editing}
            onDone={() => setEditing(undefined)}
          />
        )}
      </Dialog>
    </>
  );
}

type DriveValues = {
  company_name: string;
  position: string;
  description: string;
  employment_type: string;
  location: string;
  ctc: string;
  required_skills: string;
  min_cgpa: number;
  max_backlogs: number;
  eligible_branches: string;
  graduation_year: number;
  deadline: string;
  drive_date: string;
  selection_rounds: string;
  additional_requirements: string;
  status: string;
};
function DriveForm({
  drive,
  onDone,
}: {
  drive: Drive | null;
  onDone: () => void;
}) {
  const client = useQueryClient(),
    [error, setError] = useState("");
  function localDate(value: string) {
    const d = new Date(value + "Z");
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
      .toISOString()
      .slice(0, 16);
  }
  const {
    register,
    handleSubmit,
    formState: { isSubmitting },
  } = useForm<DriveValues>({
    defaultValues: drive
      ? {
          ...drive,
          status: drive.status === "published" ? "published" : "draft",
          required_skills: drive.required_skills.join(", "),
          eligible_branches: drive.eligible_branches.join(", "),
          selection_rounds: drive.selection_rounds.join(", "),
          deadline: localDate(drive.deadline),
          drive_date: localDate(drive.drive_date),
        }
      : {
          company_name: "",
          position: "",
          description: "",
          employment_type: "Full-time",
          location: "",
          ctc: "",
          required_skills: "",
          min_cgpa: 6,
          max_backlogs: 0,
          eligible_branches: "",
          graduation_year: 2027,
          deadline: "",
          drive_date: "",
          selection_rounds: "Aptitude, Technical interview, HR conversation",
          additional_requirements: "",
          status: "draft",
        },
  });
  async function save(values: DriveValues) {
    setError("");
    try {
      const split = (s: string) =>
        s
          .split(",")
          .map((x) => x.trim())
          .filter(Boolean);
      await send(
        drive ? `/drives/${drive.id}` : "/drives",
        {
          ...values,
          required_skills: split(values.required_skills),
          eligible_branches: split(values.eligible_branches).map((x) =>
            x.toUpperCase(),
          ),
          selection_rounds: split(values.selection_rounds),
          deadline: new Date(values.deadline).toISOString(),
          drive_date: new Date(values.drive_date).toISOString(),
        },
        drive ? "PUT" : "POST",
      );
      await client.invalidateQueries({ queryKey: ["drives"] });
      await client.invalidateQueries({ queryKey: ["dashboard"] });
      await client.invalidateQueries({ queryKey: ["companies"] });
      toast.success("Recruitment drive saved.");
      onDone();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <form onSubmit={handleSubmit(save)}>
      {error && (
        <p role="alert" className="field-error" style={{ marginBottom: 15 }}>
          {error}
        </p>
      )}
      <div className="form-grid">
        {[
          ["company_name", "Company name", "text"],
          ["position", "Position", "text"],
          ["location", "Location", "text"],
          ["ctc", "CTC / compensation information", "text"],
          ["min_cgpa", "Minimum CGPA", "number"],
          ["max_backlogs", "Maximum permitted backlogs", "number"],
          ["graduation_year", "Graduation batch", "number"],
          ["eligible_branches", "Eligible branches (comma separated)", "text"],
          ["deadline", "Registration deadline (local time)", "datetime-local"],
          ["drive_date", "Drive date (local time)", "datetime-local"],
        ].map(([key, label, type]) => (
          <div className="field" key={key}>
            <label htmlFor={`drive-${key}`}>{label}</label>
            <input
              id={`drive-${key}`}
              type={type}
              required={key !== "eligible_branches"}
              step={key === "min_cgpa" ? ".01" : undefined}
              {...register(key as keyof DriveValues, {
                valueAsNumber: type === "number",
              })}
            />
          </div>
        ))}
        <div className="field">
          <label htmlFor="employment-type">Employment type</label>
          <select id="employment-type" {...register("employment_type")}>
            <option>Full-time</option>
            <option>Internship</option>
            <option>Internship + PPO</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="drive-status">Status</label>
          <select id="drive-status" {...register("status")}>
            <option value="draft">Draft</option>
            <option value="published">Published</option>
          </select>
        </div>
        <div className="field full">
          <label htmlFor="drive-description">Job description</label>
          <textarea
            id="drive-description"
            minLength={20}
            required
            {...register("description")}
          />
        </div>
        <div className="field full">
          <label htmlFor="drive-skills">
            Required skills (comma separated)
          </label>
          <input id="drive-skills" {...register("required_skills")} />
        </div>
        <div className="field full">
          <label htmlFor="drive-rounds">
            Selection rounds (comma separated)
          </label>
          <input id="drive-rounds" {...register("selection_rounds")} />
        </div>
        <div className="field full">
          <label htmlFor="drive-requirements">Additional requirements</label>
          <textarea
            id="drive-requirements"
            {...register("additional_requirements")}
          />
        </div>
      </div>
      <label className="answer-option" style={{ marginTop: 18 }}>
        <input type="checkbox" required />I have checked the skills and academic
        criteria against the company’s actual requirements. Publishing records
        my approval.
      </label>
      <div className="dialog-actions">
        <Button type="button" variant="outline" onClick={onDone}>
          Cancel
        </Button>
        <Button disabled={isSubmitting}>
          {isSubmitting ? <Pending /> : "Save drive"}
        </Button>
      </div>
    </form>
  );
}
