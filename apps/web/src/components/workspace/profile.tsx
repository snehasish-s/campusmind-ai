"use client";
import { useState } from "react";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Trash2,
  Save,
  FileText,
  UploadCloud,
  Download,
  ShieldCheck,
  CheckCircle2,
} from "lucide-react";
import { toast } from "sonner";
import { api, send, type Student, type User } from "@/lib/api";
import { date } from "@/lib/utils";
import { Button } from "../ui/button";
import { Dialog } from "../ui/dialog";
import {
  Badge,
  CardHeading,
  Empty,
  Failure,
  PageHeading,
  Pending,
  Skeleton,
} from "../ui/common";

const experience = z.object({
  title: z.string().min(1, "Add a title").max(160),
  description: z.string().max(2000),
});
const profileSchema = z.object({
  full_name: z.string().min(2).max(150),
  graduation_year: z.number().int().min(2020).max(2100),
  cgpa: z.number().min(0).max(10),
  active_backlogs: z.number().int().min(0).max(50),
  phone: z.string().max(30),
  bio: z.string().max(2000),
  projects: z.array(experience).max(30),
  internships: z.array(experience).max(30),
});
type ProfileValues = z.infer<typeof profileSchema>;
export function ProfilePage() {
  const q = useQuery({
    queryKey: ["profile"],
    queryFn: () => api<Student>("/profile"),
  });
  return (
    <>
      <PageHeading
        eyebrow="MY PROFILE"
        title="A little more about you"
        description="Keep your academic details and experience current for your placement team."
      />
      {q.isLoading ? (
        <Skeleton />
      ) : q.error ? (
        <Failure error={q.error} />
      ) : q.data ? (
        <ProfileForm profile={q.data} />
      ) : null}
    </>
  );
}
function ProfileForm({ profile }: { profile: Student }) {
  const client = useQueryClient();
  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isSubmitting },
  } = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      full_name: profile.full_name,
      graduation_year: profile.graduation_year,
      cgpa: profile.cgpa,
      active_backlogs: profile.active_backlogs,
      phone: profile.phone,
      bio: profile.bio,
      projects: profile.projects,
      internships: profile.internships,
    },
  });
  const projects = useFieldArray({ control, name: "projects" }),
    internships = useFieldArray({ control, name: "internships" });
  async function save(values: ProfileValues) {
    try {
      await send("/profile", values, "PUT");
      await client.invalidateQueries({ queryKey: ["profile"] });
      await client.invalidateQueries({ queryKey: ["me"] });
      await client.invalidateQueries({ queryKey: ["drives"] });
      toast.success("Your profile has been updated.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }
  return (
    <form onSubmit={handleSubmit(save)} className="stack">
      <section className="card">
        <CardHeading
          title="Personal & academic details"
          description="Academic details are self-reported and should match your institutional records."
        />
        <div className="card-pad" style={{ paddingTop: 0 }}>
          <div className="form-grid">
            {[
              ["full_name", "Full name", "text"],
              ["phone", "Contact phone", "tel"],
              ["graduation_year", "Graduation year", "number"],
              ["cgpa", "Current CGPA", "number"],
              ["active_backlogs", "Active backlogs", "number"],
            ].map(([key, label, type]) => (
              <div className="field" key={key}>
                <label htmlFor={key}>{label}</label>
                <input
                  id={key}
                  type={type}
                  step={key === "cgpa" ? ".01" : undefined}
                  {...register(key as keyof ProfileValues, {
                    valueAsNumber: type === "number",
                  })}
                />
                {errors[key as keyof ProfileValues] && (
                  <p className="field-error">
                    {errors[key as keyof ProfileValues]?.message as string}
                  </p>
                )}
              </div>
            ))}
            <div className="field">
              <label>Institution identity</label>
              <input
                value={`${profile.roll_no} · ${profile.department}`}
                disabled
              />
              <p className="hint">
                Contact your institution to change your roll number, email or
                department.
              </p>
            </div>
            <div className="field full">
              <label htmlFor="bio">About you</label>
              <textarea
                id="bio"
                placeholder="What are you interested in building or learning?"
                {...register("bio")}
              />
            </div>
          </div>
        </div>
      </section>
      {(
        [
          ["projects", "Projects", projects],
          ["internships", "Internships", internships],
        ] as const
      ).map(([key, label, array]) => (
        <section className="card card-pad" key={key}>
          <div className="between">
            <h2>{label}</h2>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => array.append({ title: "", description: "" })}
            >
              <Plus size={14} />
              Add {key === "projects" ? "project" : "internship"}
            </Button>
          </div>
          {array.fields.length ? (
            array.fields.map((field, i) => (
              <div
                key={field.id}
                style={{
                  borderTop: "1px solid var(--border)",
                  marginTop: 20,
                  paddingTop: 20,
                }}
              >
                <div className="between">
                  <label htmlFor={`${key}-${i}`}>
                    {key === "projects"
                      ? "Project title"
                      : "Role & organization"}
                  </label>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label={`Remove ${label.toLowerCase()} ${i + 1}`}
                    onClick={() => array.remove(i)}
                  >
                    <Trash2 size={14} />
                  </Button>
                </div>
                <input id={`${key}-${i}`} {...register(`${key}.${i}.title`)} />
                <textarea
                  aria-label={`${label} description ${i + 1}`}
                  placeholder="Describe your contribution and what you learned."
                  style={{ marginTop: 10 }}
                  {...register(`${key}.${i}.description`)}
                />
                {errors[key]?.[i]?.title && (
                  <p className="field-error">Add a title before saving.</p>
                )}
              </div>
            ))
          ) : (
            <p className="small" style={{ marginTop: 18 }}>
              Add your {label.toLowerCase()} to help your placement team
              understand your experience.
            </p>
          )}
        </section>
      ))}
      <div className="between">
        <p className="hint">
          Your profile is visible to authorized institution staff.
        </p>
        <Button disabled={isSubmitting}>
          {isSubmitting ? (
            <Pending />
          ) : (
            <>
              <Save size={15} />
              Save profile
            </>
          )}
        </Button>
      </div>
    </form>
  );
}

type Resume = {
  id: string;
  filename: string;
  student_name: string;
  size_bytes: number;
  version: number;
  created_at: string;
  extraction_status: string;
};
export function ResumesPage({ user }: { user: User }) {
  const client = useQueryClient(),
    student = user.role === "student";
  const [file, setFile] = useState<File | null>(null),
    [pending, setPending] = useState(false),
    [text, setText] = useState<string | null>(null),
    [error, setError] = useState<Error | null>(null);
  const query = useQuery({
    queryKey: ["resumes"],
    queryFn: () => api<Resume[]>("/resumes"),
  });
  async function upload() {
    if (!file) return;
    setPending(true);
    setError(null);
    const body = new FormData();
    body.append("file", file);
    try {
      await api("/resumes", { method: "POST", body });
      setFile(null);
      await client.invalidateQueries({ queryKey: ["resumes"] });
      await client.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success("Resume uploaded. A new version has been saved.");
    } catch (e) {
      setError(e as Error);
    } finally {
      setPending(false);
    }
  }
  async function inspect(id: string) {
    try {
      const result = await api<{ text: string }>(`/resumes/${id}/text`);
      setText(
        result.text ||
          "No text could be extracted. Scanned documents will require OCR in Phase 2.",
      );
    } catch (e) {
      toast.error((e as Error).message);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow={student ? "MY RESUME" : "PLACEMENT OPERATIONS"}
        title={
          student ? "Your experience, well presented." : "The resume workspace"
        }
        description={
          student
            ? "Upload your latest resume. Every version stays in your private history."
            : "Review student resumes within your institution’s access boundaries."
        }
      />
      {error && (
        <div style={{ marginBottom: 20 }}>
          <Failure error={error} />
        </div>
      )}
      {student && (
        <section className="card card-pad" style={{ marginBottom: 22 }}>
          <div className="upload-zone">
            <UploadCloud size={32} />
            <h3>Make your next introduction count</h3>
            <p className="small">
              PDF or DOCX · Maximum 8 MB · Text extraction runs locally
            </p>
            <input
              type="file"
              accept=".pdf,.docx"
              aria-label="Choose resume"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
            <Button onClick={() => void upload()} disabled={!file || pending}>
              {pending ? (
                <Pending label="Uploading & extracting…" />
              ) : (
                <>
                  <UploadCloud size={15} />
                  Upload new version
                </>
              )}
            </Button>
          </div>
          <div className="insight-note" style={{ marginTop: 18 }}>
            <ShieldCheck />
            <span>
              Your original file and extracted text are stored separately. Only
              you and authorized staff in your institution can access them. AI
              skill analysis is planned for Phase 2.
            </span>
          </div>
        </section>
      )}
      <section className="card">
        <CardHeading
          title={student ? "Your version history" : "Recent resume uploads"}
          description="Up to 200 recent versions. Previous versions are retained when a new resume is uploaded."
        />
        {query.isLoading ? (
          <div className="card-pad">
            <Skeleton />
          </div>
        ) : query.error ? (
          <Failure error={query.error} />
        ) : query.data?.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{student ? "Document" : "Student & document"}</th>
                  <th>Version</th>
                  <th>Uploaded</th>
                  <th>Size</th>
                  <th>Extraction</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {query.data.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <div className="row">
                        <div className="icon-tile">
                          <FileText size={20} />
                        </div>
                        <div>
                          <strong>
                            {student ? r.filename : r.student_name}
                          </strong>
                          {!student && <div className="sub">{r.filename}</div>}
                        </div>
                      </div>
                    </td>
                    <td>v{r.version}</td>
                    <td>{date(r.created_at)}</td>
                    <td>{Math.ceil(r.size_bytes / 1024)} KB</td>
                    <td>
                      <Badge
                        tone={
                          r.extraction_status === "complete" ? "green" : "amber"
                        }
                      >
                        {r.extraction_status === "complete" ? (
                          <>
                            <CheckCircle2 size={10} />
                            Text extracted
                          </>
                        ) : (
                          "No text found"
                        )}
                      </Badge>
                    </td>
                    <td>
                      <div className="row">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => void inspect(r.id)}
                        >
                          View text
                        </Button>
                        <Button variant="outline" size="sm" asChild>
                          <a href={`/api/resumes/${r.id}/download`}>
                            <Download size={13} />
                            Download
                          </a>
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            title="A fresh page for your experience"
            description={
              student
                ? "Upload your first resume to begin your version history."
                : "Student resume uploads will appear here."
            }
          />
        )}
      </section>
      <Dialog
        open={text !== null}
        onOpenChange={(open) => {
          if (!open) setText(null);
        }}
        title="Extracted document text"
        description="Local text extraction only. This is not an AI assessment."
      >
        <pre
          style={{
            whiteSpace: "pre-wrap",
            fontFamily: "inherit",
            fontSize: 12,
            lineHeight: 1.8,
            maxHeight: "55vh",
            overflow: "auto",
          }}
        >
          {text}
        </pre>
      </Dialog>
    </>
  );
}
