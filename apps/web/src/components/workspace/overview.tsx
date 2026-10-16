"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { motion, useReducedMotion } from "motion/react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import {
  Users,
  BriefcaseBusiness,
  FileCheck2,
  Upload,
  ArrowRight,
  CheckCircle2,
  Sparkles,
  Network,
  Building2,
  CalendarDays,
  FolderLock,
} from "lucide-react";
import {
  api,
  type User,
  type Metrics,
  type Drive,
  type Student,
} from "@/lib/api";
import { date } from "@/lib/utils";
import { Button } from "../ui/button";
import {
  Badge,
  CardHeading,
  Empty,
  Failure,
  PageHeading,
  Skeleton,
} from "../ui/common";

export function Overview({ user, mode }: { user: User; mode: string }) {
  const reduced = useReducedMotion(),
    student = user.role === "student",
    college = mode === "collegeops";
  const data = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api<Metrics>("/dashboard"),
  });
  const drives = useQuery({
    queryKey: ["drives"],
    queryFn: () => api<Drive[]>("/drives"),
  });
  const profile = useQuery({
    queryKey: ["profile"],
    queryFn: () => api<Student>("/profile"),
    enabled: student,
  });
  if (data.isLoading) return <Skeleton rows={5} />;
  if (data.error)
    return <Failure error={data.error} retry={() => void data.refetch()} />;
  if (!data.data) return null;
  const m = data.data,
    activePct = m.students ? Math.round((m.active / m.students) * 100) : 0,
    resumePct = m.students ? Math.round((m.resumes / m.students) * 100) : 0;
  const metrics = student
    ? [
        [
          "Available drives",
          m.drives,
          BriefcaseBusiness,
          "Published by your institution",
        ],
        [
          "My applications",
          m.applications,
          Users,
          "Your registered opportunities",
        ],
        [
          "Resume versions",
          m.resumes,
          FileCheck2,
          "Securely stored in your vault",
        ],
        ["Account status", "Active", CheckCircle2, "Your journey has started"],
      ]
    : college
      ? [
          ["Total students", m.students, Users, "Across your institution"],
          [
            "Departments",
            m.departments.length,
            Building2,
            "Configured academic branches",
          ],
          ["Faculty & staff", m.staff, Users, "Institution team members"],
          [
            "Evidence documents",
            m.documents,
            FolderLock,
            "Stored in the institution vault",
          ],
        ]
      : [
          ["Total students", m.students, Users, "Students in your registry"],
          [
            "Active recruitment drives",
            m.drives,
            BriefcaseBusiness,
            "Published opportunities",
          ],
          [
            "Resume completion",
            `${resumePct}%`,
            FileCheck2,
            `${m.resumes} students have a resume`,
          ],
          [
            "Student activation",
            `${activePct}%`,
            CheckCircle2,
            `${m.active} accounts activated`,
          ],
        ];
  const title =
    mode === "analytics"
      ? "Placement performance"
      : college
        ? "Your institution, in perspective."
        : student
          ? `Hello, ${user.full_name.split(" ")[0]}.`
          : "Your campus, in perspective.";
  return (
    <>
      <PageHeading
        eyebrow={
          college
            ? "COLLEGEOPS OVERVIEW"
            : student
              ? "YOUR PLACEMENT JOURNEY"
              : "PLACEMENTOS OVERVIEW"
        }
        title={title}
        description={
          student
            ? "Small steps today. More possibilities tomorrow."
            : college
              ? "People, records and evidence, connected in one workspace."
              : "A clear view of your students, opportunities and what needs attention."
        }
      >
        {!student && user.role !== "hod" ? (
          <>
            <Button variant="outline" asChild>
              <Link href="/app/reports">
                <FileCheck2 size={15} />
                View reports
              </Link>
            </Button>
            <Button asChild>
              <Link href={college ? "/app/documents" : "/app/imports"}>
                <Upload size={15} />
                {college ? "Add evidence" : "Import students"}
              </Link>
            </Button>
          </>
        ) : student ? (
          <Button asChild>
            <Link href="/app/profile">
              Complete my profile <ArrowRight size={15} />
            </Link>
          </Button>
        ) : null}
      </PageHeading>
      <div className="metric-grid">
        {metrics.map(([label, value, Icon, note], i) => {
          const I = Icon as typeof Users;
          return (
            <motion.article
              key={label as string}
              className="card metric"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.06, duration: 0.3 }}
            >
              <div className="metric-top">
                <span>{label as string}</span>
                <I size={17} />
              </div>
              <div className="metric-value">
                {typeof value === "number"
                  ? value.toLocaleString("en-IN")
                  : String(value ?? 0)}
              </div>
              <div className="metric-foot">
                <CheckCircle2 size={12} />
                {note as string}
              </div>
            </motion.article>
          );
        })}
      </div>
      {student && (
        <div className="welcome-banner">
          <div>
            <div className="eyebrow">YOUR NEXT STEP</div>
            <h2>
              {m.resumes
                ? "Your profile is taking shape."
                : "A good resume opens the conversation."}
            </h2>
            <p>
              {m.resumes
                ? "Explore upcoming recruitment drives and check the eligibility criteria for your next opportunity."
                : "Upload your resume to make it available to your authorized placement team."}
            </p>
          </div>
          <Network className="banner-symbol" />
          <Button asChild>
            <Link href={m.resumes ? "/app/drives" : "/app/resumes"}>
              {m.resumes ? "Explore drives" : "Upload my resume"}
              <ArrowRight size={15} />
            </Link>
          </Button>
        </div>
      )}
      {!student ? (
        <div className="chart-layout">
          <motion.section
            className="card"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
          >
            <CardHeading
              title="Your student community"
              description="Registered and activated students by department"
            />
            {m.departments.length ? (
              <>
                <div
                  className="chart-legend"
                  style={{ padding: "0 24px 15px" }}
                >
                  <span>
                    <i />
                    Registered
                  </span>
                  <span>
                    <i className="teal" />
                    Activated
                  </span>
                </div>
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={m.departments}
                      barGap={5}
                      margin={{ left: -24, right: 5, top: 5 }}
                    >
                      <CartesianGrid
                        strokeDasharray="3 4"
                        vertical={false}
                        stroke="var(--border)"
                      />
                      <XAxis
                        dataKey="name"
                        axisLine={false}
                        tickLine={false}
                        tick={{ fontSize: 10, fill: "#64748b" }}
                        dy={8}
                      />
                      <YAxis
                        allowDecimals={false}
                        axisLine={false}
                        tickLine={false}
                        tick={{ fontSize: 9, fill: "#64748b" }}
                      />
                      <Tooltip
                        contentStyle={{
                          background: "var(--card)",
                          border: "1px solid var(--border)",
                          borderRadius: 8,
                          fontSize: 11,
                        }}
                        cursor={{ fill: "#64748b08" }}
                      />
                      <Bar
                        dataKey="students"
                        name="Registered"
                        fill="#2563eb"
                        radius={[4, 4, 0, 0]}
                        maxBarSize={23}
                        isAnimationActive={!reduced}
                      />
                      <Bar
                        dataKey="active"
                        name="Activated"
                        fill="#14b8a6"
                        radius={[4, 4, 0, 0]}
                        maxBarSize={23}
                        isAnimationActive={!reduced}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </>
            ) : (
              <Empty
                title="No departments yet"
                description="Create departments before importing students."
              />
            )}
          </motion.section>
          <section className="card">
            <CardHeading
              title="Onboarding at a glance"
              description="Turn invitations into prepared student profiles"
            />
            <div className="card-pad" style={{ paddingTop: 8 }}>
              {[
                [
                  "Account activation",
                  activePct,
                  `${m.active} of ${m.students}`,
                  false,
                ],
                [
                  "Resume uploaded",
                  resumePct,
                  `${m.resumes} of ${m.students}`,
                  true,
                ],
              ].map(([label, pct, note, teal]) => (
                <div className="progress-row" key={label as string}>
                  <div className="progress-label">
                    <span>{label as string}</span>
                    <strong>{pct as number}%</strong>
                  </div>
                  <div className="progress-track">
                    <motion.div
                      className={`progress-fill ${teal ? "teal" : ""}`}
                      initial={{ scaleX: 0 }}
                      animate={{ scaleX: Number(pct) / 100 }}
                      transition={{ duration: 0.7, delay: 0.3 }}
                      style={{ width: "100%" }}
                    />
                  </div>
                  <p className="hint">{note as string} students</p>
                </div>
              ))}
              <div className="insight-note">
                <Sparkles />
                <span>
                  {m.students === 0
                    ? "Start by importing your synthetic student CSV. These metrics will update from your institution’s records."
                    : `${m.students! - m.active} students are yet to activate their account. Review invitation delivery in the student registry.`}
                </span>
              </div>
              <Link
                className="text-link"
                style={{ marginTop: 18 }}
                href="/app/students"
              >
                Open student registry <ArrowRight size={14} />
              </Link>
            </div>
          </section>
        </div>
      ) : (
        <div className="grid-2" style={{ marginBottom: 22 }}>
          <section className="card card-pad">
            <div className="between">
              <h2>My academic snapshot</h2>
              <Badge tone="blue">Self-reported</Badge>
            </div>
            {profile.data ? (
              <div
                className="summary-grid"
                style={{ gridTemplateColumns: "repeat(3,1fr)" }}
              >
                <div className="summary-cell">
                  <strong>{profile.data.cgpa}</strong>
                  <span>CGPA / 10</span>
                </div>
                <div className="summary-cell">
                  <strong>{profile.data.department}</strong>
                  <span>Department</span>
                </div>
                <div className="summary-cell">
                  <strong>{profile.data.graduation_year}</strong>
                  <span>Graduating batch</span>
                </div>
              </div>
            ) : (
              <Skeleton rows={1} />
            )}
            <Link className="text-link" href="/app/profile">
              Review my profile <ArrowRight size={14} />
            </Link>
          </section>
          <section className="card card-pad">
            <div className="between">
              <h2>Your preparation workspace</h2>
              <Badge tone="green">Connected</Badge>
            </div>
            <p className="small" style={{ marginBlock: 18 }}>
              Review resume evidence, choose a preparation target, and use
              approved mock assessments to demonstrate learning.
            </p>
            <Link className="text-link" href="/app/roadmap">
              Open my roadmap <ArrowRight size={14} />
            </Link>
          </section>
        </div>
      )}
      <div className="chart-layout">
        <section className="card">
          <CardHeading
            title={college ? "Institutional records" : "Upcoming opportunities"}
            description={
              college
                ? "A foundation for evidence and quality workflows"
                : "Recruitment drives in your institution"
            }
            href={college ? "/app/documents" : "/app/drives"}
          />
          {college ? (
            <div className="card-pad">
              <div className="insight-note">
                <FolderLock />
                <span>
                  {m.documents} documents stored. Evidence extraction,
                  requirement mapping and human review are available in
                  CollegeOps.
                </span>
              </div>
              <Button asChild variant="outline" style={{ marginTop: 20 }}>
                <Link href="/app/documents">
                  Open evidence vault <ArrowRight size={14} />
                </Link>
              </Button>
            </div>
          ) : drives.error ? (
            <Failure error={drives.error} />
          ) : drives.isLoading ? (
            <div className="card-pad">
              <Skeleton rows={2} />
            </div>
          ) : !drives.data?.length ? (
            <Empty
              title="The next opportunity starts here"
              description="Your institution’s published recruitment drives will appear here."
            />
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Company & role</th>
                    <th>Drive date</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {drives.data.slice(0, 4).map((d) => (
                    <tr key={d.id}>
                      <td>
                        <Link href="/app/drives">
                          <strong>{d.company_name}</strong>
                          <div className="sub">{d.position}</div>
                        </Link>
                      </td>
                      <td>{date(d.drive_date)}</td>
                      <td>
                        <Badge
                          tone={d.status === "published" ? "green" : "neutral"}
                        >
                          {d.status}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
        <section className="card">
          <CardHeading
            title={student ? "Your checklist" : "Recent activity"}
            description={
              student
                ? "A few useful steps to get started"
                : "Updates from your institution workspace"
            }
          />
          <div className="card-pad" style={{ paddingTop: 8 }}>
            {student ? (
              [
                ["Review your profile", "profile", Users],
                ["Keep your resume up to date", "resumes", FileCheck2],
                ["Explore recruitment drives", "drives", BriefcaseBusiness],
              ].map(([t, url, Icon]) => {
                const I = Icon as typeof Users;
                return (
                  <Link
                    key={t as string}
                    className="activity-row"
                    href={`/app/${url}`}
                  >
                    <div className="activity-icon">
                      <I size={14} />
                    </div>
                    <div>
                      <strong>{t as string}</strong>
                      <p>
                        Open workspace{" "}
                        <ArrowRight size={10} style={{ display: "inline" }} />
                      </p>
                    </div>
                  </Link>
                );
              })
            ) : m.activity.length ? (
              m.activity.map((a) => (
                <div className="activity-row" key={a.id}>
                  <div className="activity-icon">
                    {a.kind === "drive" ? (
                      <BriefcaseBusiness size={13} />
                    ) : (
                      <CalendarDays size={13} />
                    )}
                  </div>
                  <div>
                    <strong>{a.title}</strong>
                    <p>{date(a.created_at)}</p>
                  </div>
                </div>
              ))
            ) : (
              <p className="small">
                Institution activity will appear as you import students and
                publish drives.
              </p>
            )}
          </div>
        </section>
      </div>
    </>
  );
}
