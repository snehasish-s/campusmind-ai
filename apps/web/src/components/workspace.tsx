"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import {
  LayoutDashboard,
  Users,
  Upload,
  BriefcaseBusiness,
  FileText,
  Building2,
  Bell,
  Settings,
  ShieldCheck,
  BarChart3,
  ChevronRight,
  PanelLeftClose,
  PanelLeftOpen,
  Menu,
  LogOut,
  Search,
  Sun,
  Moon,
  BookOpen,
  Route,
  ListChecks,
  MessagesSquare,
  Trophy,
  Layers,
  ClipboardCheck,
  GraduationCap,
  FolderLock,
  FileBarChart2,
  ScrollText,
  UserRound,
  Compass,
} from "lucide-react";
import { api, ApiError, send, type User } from "@/lib/api";
import { Brand } from "./brand";
import { Button } from "./ui/button";
import { Badge, Failure, Skeleton } from "./ui/common";
import { Overview } from "./workspace/overview";
import { StudentsPage } from "./workspace/students";
import { ImportsPage } from "./workspace/imports";
import { DrivesPage } from "./workspace/drives";
import { ProfilePage, ResumesPage } from "./workspace/profile";
import {
  AdminPage,
  NotificationsPage,
  ApplicationsPage,
} from "./workspace/operations";
import {
  SkillsPage,
  RoadmapPage,
  ResourcesPage,
  CoachPage,
  AssessmentsPage,
  WorkflowJobs,
} from "./workspace/intelligence";
import { AnalyticsPage, EvidencePage } from "./workspace/insights";
import { TasksPage } from "./workspace/governance";
import { toast } from "sonner";
import { CampusHub } from "./workspace/campus";

const campusLinks = [
  ["campus", "Campus Hub", MessagesSquare],
  ["timetable", "My timetable", BookOpen],
] as const;
const staffLinks = [
  ["placement", "Overview", LayoutDashboard],
  ["students", "Student registry", Users],
  ["imports", "Bulk student import", Upload],
  ["resumes", "Resume management", FileText],
  ["companies", "Company directory", Building2],
  ["drives", "Recruitment drives", BriefcaseBusiness],
  ["applications", "Applications", ListChecks],
  ["assessments", "Assessments", ClipboardCheck],
  ["analytics", "Placement analytics", BarChart3],
  ["reports", "Reports", FileBarChart2],
] as const;
const studentLinks = [
  ["placement", "My dashboard", LayoutDashboard],
  ["profile", "My profile", UserRound],
  ["resumes", "My resume", FileText],
  ["skills", "My skills", Layers],
  ["roadmap", "My career roadmap", Route],
  ["drives", "Recruitment drives", BriefcaseBusiness],
  ["mock-tests", "Mock tests", ClipboardCheck],
  ["interview", "Interview preparation", MessagesSquare],
  ["resources", "Learning resources", BookOpen],
  ["progress", "Progress & achievements", Trophy],
] as const;
const collegeLinks = [
  ["collegeops", "Institutional overview", Building2],
  ["documents", "Academic evidence vault", FolderLock],
  ["departments", "Departments", Layers],
  ["accreditation", "Accreditation readiness", ShieldCheck],
  ["evidence-reports", "Evidence reports", FileBarChart2],
  ["tasks", "Institutional tasks", ListChecks],
  ["review", "Review & approval", ClipboardCheck],
] as const;
const adminLinks = [
  ["departments", "Departments", Layers],
  ["staff", "Staff & roles", Users],
  ["collegeops", "CollegeOps", Building2],
  ["documents", "Institution documents", FolderLock],
  ["audit", "Audit activity", ScrollText],
] as const;

export function Workspace() {
  const pathname = usePathname(),
    router = useRouter(),
    client = useQueryClient();
  const section = pathname.split("/")[2] || "";
  const [collapsed, setCollapsed] = useState(false),
    [mobile, setMobile] = useState(false),
    [dark, setDark] = useState(false),
    [search, setSearch] = useState("");
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api<User>("/auth/me"),
    retry: false,
    refetchInterval: 60000,
  });
  useEffect(() => {
    if (me.error instanceof ApiError && me.error.status === 401)
      router.replace("/login");
  }, [me.error, router]);
  useEffect(() => {
    const frame = requestAnimationFrame(() =>
      setDark(localStorage.getItem("cm-theme") === "dark"),
    );
    return () => cancelAnimationFrame(frame);
  }, []);
  const user = me.data;
  useEffect(() => {
    if (
      user &&
      section === "" &&
      ["student", "faculty", "campus_staff"].includes(user.role)
    )
      router.replace("/app/campus");
  }, [user, section, router]);
  if (!user)
    return (
      <main className="workspace" style={{ maxWidth: 900, paddingTop: 80 }}>
        <Brand />
        <div style={{ marginTop: 35 }}>
          {me.error &&
          !(me.error instanceof ApiError && me.error.status === 401) ? (
            <Failure error={me.error} retry={() => void me.refetch()} />
          ) : (
            <Skeleton rows={5} />
          )}
        </div>
      </main>
    );
  const student = user.role === "student",
    admin = ["institution_admin", "platform_admin"].includes(user.role),
    college = [
      "collegeops",
      "documents",
      "accreditation",
      "evidence-reports",
      "tasks",
      "review",
    ].includes(section);
  const campus =
    ["campus", "timetable"].includes(section) ||
    (["student", "faculty", "campus_staff"].includes(user.role) &&
      ["", "profile", "notifications", "settings"].includes(section));
  const canPlacement = user.placement_access.allowed;
  const moduleName = campus
    ? "Campus Hub"
    : college
      ? "CollegeOps"
      : admin && section === ""
        ? "Institution administration"
        : "PlacementOS";
  const links = campus
    ? student
      ? [...campusLinks, ["profile", "My profile", UserRound] as const]
      : campusLinks
    : student
      ? studentLinks
      : college
        ? collegeLinks
        : user.role === "hod"
          ? staffLinks.filter(
              ([id]) =>
                !["imports", "companies", "assessments", "reports"].includes(
                  id,
                ),
            )
          : staffLinks;
  const title =
    [
      ...campusLinks,
      ...staffLinks,
      ...studentLinks,
      ...adminLinks,
      ...collegeLinks,
      ["notifications", "Notifications"],
      ["settings", "Settings"],
    ].find(([id]) => id === section)?.[1] || "Workspace";
  async function logout() {
    try {
      await send("/auth/logout");
      client.clear();
      router.push("/login");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }
  function navigate() {
    setMobile(false);
  }
  function toggleTheme() {
    const next = !dark;
    setDark(next);
    localStorage.setItem("cm-theme", next ? "dark" : "light");
  }
  const nav = (items: readonly (readonly [string, string, typeof Users])[]) =>
    items.map(([id, label, Icon]) => (
      <Link
        key={id}
        href={`/app${id ? "/" + id : ""}`}
        title={label}
        aria-current={section === id ? "page" : undefined}
        onClick={navigate}
        className={`nav-link ${section === id ? "active" : ""}`}
      >
        <Icon size={17} />
        <span>{label}</span>
      </Link>
    ));
  return (
    <div
      className={`${collapsed ? "collapsed " : ""}${mobile ? "mobile-open " : ""}${dark ? "dark" : ""}`}
      style={{ background: "var(--bg)", minHeight: "100vh" }}
    >
      <a className="sr-only focus:not-sr-only" href="#workspace-content">
        Skip to content
      </a>
      <button
        className="mobile-backdrop"
        aria-label="Close navigation"
        onClick={() => setMobile(false)}
      />
      <aside className="sidebar">
        <Link href="/" aria-label="CampusMind home">
          <Brand />
        </Link>
        <div className="institution-switch">
          <div
            className="icon-tile"
            style={{
              width: 28,
              height: 28,
              background: "#24334b",
              color: "#a5b4fc",
            }}
          >
            <Building2 size={16} />
          </div>
          <div>
            <strong>{user.institution.name}</strong>
            <small>Institution workspace</small>
          </div>
        </div>
        <div className="nav-label">{moduleName}</div>
        <nav aria-label="Workspace navigation">
          {nav(links)}
          <div className="nav-divider" />
          <div className="nav-label">Your workspaces</div>
          {!campus && (
            <Link href="/app/campus" onClick={navigate} className="nav-link">
              <MessagesSquare size={17} />
              <span>Campus Hub</span>
            </Link>
          )}
          {campus && canPlacement && (
            <Link href="/app/placement" onClick={navigate} className="nav-link">
              <BriefcaseBusiness size={17} />
              <span>Open PlacementOS</span>
            </Link>
          )}
          {campus && student && !canPlacement && (
            <p
              className="hint"
              style={{ padding: "8px 16px", color: "#b9c8de" }}
            >
              PlacementOS opens in third year and final year.{" "}
              {user.placement_access.academic_year === null
                ? "Ask your institution to assign your academic year."
                : "Your campus updates remain available here."}
            </p>
          )}
          {campus && admin && (
            <Link href="/app/placement" onClick={navigate} className="nav-link">
              <Building2 size={17} />
              <span>Institution administration</span>
            </Link>
          )}
          {(admin || user.role === "hod") && !college && (
            <>
              <div className="nav-divider" />
              <div className="nav-label">Institution</div>
              {nav(
                admin
                  ? adminLinks
                  : adminLinks.filter(([id]) =>
                      ["collegeops", "documents"].includes(id),
                    ),
              )}
            </>
          )}
          {college && (
            <>
              <div className="nav-divider" />
              <Link
                href="/app/placement"
                onClick={navigate}
                className="nav-link"
              >
                <GraduationCap />
                <span>Back to PlacementOS</span>
              </Link>
            </>
          )}
          <div className="nav-divider" />
          {nav([
            ["notifications", "Notifications", Bell],
            ...(!["faculty", "campus_staff"].includes(user.role)
              ? [
                  [
                    "settings",
                    student ? "Account settings" : "Settings",
                    Settings,
                  ] as const,
                ]
              : []),
          ])}
        </nav>
        <div className="sidebar-footer">
          <div className="local-label">
            <span className="status-dot" />
            Connected campus workspace
          </div>
          <div className="user-info">
            <div className="avatar">
              {user.full_name
                .split(" ")
                .slice(0, 2)
                .map((x) => x[0])
                .join("")}
            </div>
            <div>
              <strong>{user.full_name}</strong>
              <p>{user.role.replaceAll("_", " ")}</p>
            </div>
          </div>
        </div>
      </aside>
      <div className="app-main">
        <header className="topbar">
          <div className="row">
            <Button
              className="collapse-toggle"
              variant="ghost"
              size="icon"
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              onClick={() => setCollapsed(!collapsed)}
            >
              {collapsed ? (
                <PanelLeftOpen size={18} />
              ) : (
                <PanelLeftClose size={18} />
              )}
            </Button>
            <Button
              className="mobile-toggle"
              variant="ghost"
              size="icon"
              aria-label="Open navigation"
              onClick={() => setMobile(true)}
            >
              <Menu size={20} />
            </Button>
            <div className="breadcrumbs">
              <span>{moduleName}</span>
              <ChevronRight size={12} />
              <strong>{title}</strong>
            </div>
          </div>
          <div className="top-actions">
            {!campus && (admin || user.role === "hod") && (
              <form
                className="top-search"
                onSubmit={(e) => {
                  e.preventDefault();
                  router.push(`/app/students?q=${encodeURIComponent(search)}`);
                }}
              >
                <Search size={14} />
                <input
                  aria-label="Search students"
                  placeholder="Find a student…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </form>
            )}
            <Badge tone="green">Local edition</Badge>
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleTheme}
              aria-label={dark ? "Use light theme" : "Use dark theme"}
            >
              {dark ? <Sun size={17} /> : <Moon size={17} />}
            </Button>
            <Button variant="ghost" size="icon" asChild>
              <Link href="/app/notifications" aria-label="Notifications">
                <Bell size={18} />
              </Link>
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={logout}
              aria-label="Sign out"
            >
              <LogOut size={17} />
            </Button>
          </div>
        </header>
        <main className="workspace" id="workspace-content">
          <AnimatePresence mode="wait">
            <motion.div
              key={pathname}
              initial={{ opacity: 0, y: 7 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
            >
              <Page section={section} user={user} />
            </motion.div>
          </AnimatePresence>
          {!campus && canPlacement && <WorkflowJobs />}
          <footer className="workspace-footer">
            <span>CampusMind AI · A connected campus, a clearer future.</span>
            <span>Synthetic demonstration</span>
          </footer>
        </main>
      </div>
    </div>
  );
}

function Page({ section, user }: { section: string; user: User }) {
  const admin = ["institution_admin", "platform_admin"].includes(user.role),
    student = user.role === "student";
  if (
    ["campus", "timetable"].includes(section) ||
    (["faculty", "campus_staff"].includes(user.role) && section === "")
  )
    return <CampusHub user={user} timetableOnly={section === "timetable"} />;
  const campusPages = [
    "",
    "campus",
    "timetable",
    "profile",
    "notifications",
    "settings",
  ];
  if (
    student &&
    !user.placement_access.allowed &&
    !campusPages.includes(section)
  )
    return (
      <div className="card card-pad">
        <h1>PlacementOS opens in third year</h1>
        <p style={{ marginBlock: 16 }}>
          Placement preparation is available to third-year and final-year
          students. Your academic year is managed by your institution.
        </p>
        <Button asChild>
          <Link href="/app/campus">Return to Campus Hub</Link>
        </Button>
      </div>
    );
  if (section === "" && student) return <CampusHub user={user} />;
  if (section === "placement") return <Overview user={user} mode="" />;
  if (section === "") return <Overview user={user} mode={section} />;
  if (["analytics", "progress"].includes(section))
    return <AnalyticsPage user={user} />;
  if (
    [
      "collegeops",
      "documents",
      "accreditation",
      "evidence-reports",
      "review",
    ].includes(section) &&
    ["institution_admin", "platform_admin", "hod"].includes(user.role)
  )
    return <EvidencePage user={user} section={section} />;
  if (section === "students" && !student) return <StudentsPage user={user} />;
  if (
    section === "imports" &&
    ["placement_officer", "institution_admin", "platform_admin"].includes(
      user.role,
    )
  )
    return <ImportsPage />;
  if (section === "drives") return <DrivesPage user={user} />;
  if (section === "profile" && student) return <ProfilePage />;
  if (section === "resumes") return <ResumesPage user={user} />;
  if (section === "notifications") return <NotificationsPage />;
  if (section === "applications") return <ApplicationsPage user={user} />;
  if (
    [
      "departments",
      "staff",
      "companies",
      "documents",
      "audit",
      "settings",
      "reports",
    ].includes(section)
  )
    return <AdminPage section={section} user={user} />;
  if (
    section === "tasks" &&
    ["institution_admin", "platform_admin", "hod"].includes(user.role)
  )
    return <TasksPage user={user} />;
  if (section === "skills" && student) return <SkillsPage />;
  if (section === "roadmap" && student) return <RoadmapPage />;
  if (section === "resources" && student) return <ResourcesPage />;
  if (section === "interview" && student) return <CoachPage />;
  if (["assessments", "mock-tests"].includes(section))
    return <AssessmentsPage user={user} />;
  return (
    <div className="card card-pad">
      <Compass />
      <h1 style={{ marginTop: 20 }}>This page isn’t available</h1>
      <p style={{ marginBlock: 15 }}>
        Choose a page from your workspace navigation.
      </p>
      <Button asChild>
        <Link href="/app">Back to overview</Link>
      </Button>
      {admin && (
        <p className="hint">
          Institution pages are available from the sidebar.
        </p>
      )}
    </div>
  );
}
