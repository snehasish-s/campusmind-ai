"use client";
import Link from "next/link";
import { motion } from "motion/react";
import {
  ArrowRight,
  ArrowUpRight,
  Building2,
  GraduationCap,
  Check,
  ShieldCheck,
  LockKeyhole,
  Database,
  MailCheck,
  Laptop,
  FileCheck2,
  CircleCheck,
} from "lucide-react";
import { Brand } from "@/components/brand";
import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <div className="landing">
      <header className="landing-nav">
        <Link href="/" aria-label="CampusMind home">
          <Brand />
        </Link>
        <nav aria-label="Main navigation">
          <a href="#products">Our products</a>
          <a href="#workflow">How it works</a>
          <a href="#security">Security</a>
        </nav>
        <div className="landing-nav-actions">
          <Link href="/login">Sign in</Link>
          <Button asChild>
            <Link href="/login">
              Explore the workspace <ArrowUpRight size={15} />
            </Link>
          </Button>
        </div>
      </header>
      <main>
        <section className="hero">
          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <div className="hero-label">
              <span className="status-dot" /> BUILT FOR THE NEXT CHAPTER OF
              HIGHER EDUCATION
            </div>
            <h1>
              A connected campus.
              <br />A <span>clearer future.</span>
            </h1>
            <p>
              Bring your institution’s operations and student career journeys
              together. Less administrative friction. More room for potential.
            </p>
            <div className="hero-actions">
              <Button asChild>
                <Link href="/login">
                  Enter your workspace <ArrowRight size={16} />
                </Link>
              </Button>
              <Button variant="outline" asChild>
                <a href="#products">Discover CampusMind</a>
              </Button>
            </div>
            <div className="hero-foot">
              <span>
                <Check />
                Locally runnable
              </span>
              <span>
                <Check />
                Open-source foundation
              </span>
              <span>
                <Check />
                Your institution’s data
              </span>
            </div>
          </motion.div>
          <motion.div
            className="hero-art"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.6, delay: 0.15 }}
          >
            <svg
              className="network-svg"
              viewBox="0 0 180 120"
              aria-hidden="true"
            >
              <g stroke="#cbd5e1" fill="none">
                <path d="M15 65L55 30L100 55L150 20M55 30L70 100L100 55L160 95" />
                <path d="M15 65L70 100L160 95" />
              </g>
              {[
                [15, 65],
                [55, 30],
                [100, 55],
                [150, 20],
                [70, 100],
                [160, 95],
              ].map(([x, y], i) => (
                <circle
                  key={i}
                  cx={x}
                  cy={y}
                  r={i === 2 ? 7 : 4}
                  fill={i === 2 ? "#2563eb" : "#0d9488"}
                  className="network-dot"
                  style={{ animationDelay: `${i * 0.2}s` }}
                />
              ))}
            </svg>
            <div
              className="product-preview"
              aria-label="Illustrative dashboard preview, not live institution metrics"
            >
              <div className="preview-sidebar">
                <b>◈ CampusMind</b>
                {[
                  "Overview",
                  "Student registry",
                  "Recruitment drives",
                  "Resume vault",
                  "Departments",
                  "Analytics",
                  "Settings",
                ].map((x) => (
                  <div key={x}>{x}</div>
                ))}
              </div>
              <div className="preview-main">
                <div className="preview-top">
                  <span>PlacementOS / Overview</span>
                  <span>Demo workspace</span>
                </div>
                <h3>Your campus, in perspective.</h3>
                <p>One workspace for every next step.</p>
                <div className="preview-metrics">
                  {[
                    ["STUDENTS", "1,000"],
                    ["DEPARTMENTS", "5"],
                    ["WORKSPACE", "01"],
                  ].map(([k, v]) => (
                    <div key={k}>
                      {k}
                      <strong>{v}</strong>
                    </div>
                  ))}
                </div>
                <div className="preview-chart">
                  <h4>One connected student community</h4>
                  <div className="preview-bars">
                    {[48, 32, 56, 42, 38, 27, 62, 49, 45, 34].map((h, i) => (
                      <span key={i} style={{ height: h }} />
                    ))}
                  </div>
                </div>
              </div>
            </div>
            <div className="floating-note">
              <CircleCheck />
              <div>
                <strong>Every journey starts connected</strong>
                <span>Invite. Activate. Prepare. Progress.</span>
              </div>
            </div>
            <div className="preview-caption">
              Illustrative product preview · synthetic data
            </div>
          </motion.div>
        </section>
        <div className="value-strip">
          <span>
            <Building2 />
            Designed for institutions
          </span>
          <span>
            <GraduationCap />
            Centered on students
          </span>
          <span>
            <ShieldCheck />
            Tenant-isolated by design
          </span>
          <span>
            <Laptop />
            No paid API required
          </span>
        </div>
        <section className="section" id="products">
          <div className="section-header">
            <div className="eyebrow">TWO PRODUCTS. ONE SHARED PURPOSE.</div>
            <h2>
              Everything connected.
              <br />
              Everyone moving forward.
            </h2>
            <p>
              From departmental records to a student’s first opportunity, give
              your institution a shared foundation for better work.
            </p>
          </div>
          <div className="product-panels">
            <article className="product-panel">
              <div className="between">
                <div className="icon-tile teal">
                  <Building2 />
                </div>
                <span className="badge badge-green">
                  INSTITUTION OPERATIONS
                </span>
              </div>
              <h3>CampusMind CollegeOps</h3>
              <p>
                A structured home for institutional records, departments and
                academic evidence. Build clarity into your everyday operations.
              </p>
              <div className="feature-list">
                {[
                  "Department and staff management",
                  "Academic document and evidence vault",
                  "Institutional activity and access controls",
                ].map((t) => (
                  <span key={t}>
                    <Check />
                    {t}
                  </span>
                ))}
              </div>
              <p className="hint" style={{ marginTop: 22 }}>
                Accreditation intelligence and review workflows arrive in Phase
                2.
              </p>
            </article>
            <article className="product-panel placement">
              <div className="between">
                <div className="icon-tile">
                  <GraduationCap />
                </div>
                <span className="badge badge-blue">STUDENT CAREERS</span>
              </div>
              <h3>CampusMind PlacementOS</h3>
              <p>
                Connect your placement team and students, from secure onboarding
                to the next recruitment opportunity.
              </p>
              <div className="feature-list">
                {[
                  "Bulk student onboarding and secure invitations",
                  "Student profiles and versioned resumes",
                  "Recruitment drives and application tracking",
                ].map((t) => (
                  <span key={t}>
                    <Check />
                    {t}
                  </span>
                ))}
              </div>
              <p className="hint" style={{ marginTop: 22 }}>
                Evidence-backed preparation, adaptive roadmaps and approved mock
                assessments.
              </p>
            </article>
          </div>
        </section>
        <section className="workflow-section" id="workflow">
          <div className="section">
            <div className="section-header">
              <div className="eyebrow">A THOUGHTFUL START</div>
              <h2>
                From a spreadsheet
                <br />
                to a connected institution.
              </h2>
              <p>
                A guided workflow that respects your team’s time and your
                students’ privacy.
              </p>
            </div>
            <div className="workflow-grid">
              {[
                [
                  "01",
                  "Configure your campus",
                  "Set up your institution, departments and authorized staff.",
                ],
                [
                  "02",
                  "Bring your students in",
                  "Map and validate a CSV. Review every issue before importing.",
                ],
                [
                  "03",
                  "Activate securely",
                  "Students receive a single-use invitation and choose their own password.",
                ],
                [
                  "04",
                  "Open new possibilities",
                  "Build profiles, upload resumes and discover recruitment drives.",
                ],
              ].map(([n, t, d]) => (
                <article key={n}>
                  <b>{n} /</b>
                  <h3>{t}</h3>
                  <p>{d}</p>
                </article>
              ))}
            </div>
          </div>
        </section>
        <section className="section security-section" id="security">
          <div className="section-header">
            <div className="eyebrow">TRUST IS PART OF THE FOUNDATION</div>
            <h2>
              Your campus data.
              <br />
              Handled with care.
            </h2>
            <p>
              Clear access boundaries and secure account workflows, built into
              the foundation. Development uses entirely synthetic student
              records.
            </p>
          </div>
          <div className="security-grid">
            {[
              [
                LockKeyhole,
                "Role-based access",
                "Permissions enforced in the API, with institution-specific data boundaries.",
              ],
              [
                MailCheck,
                "Secure activation",
                "Single-use invitations. Individually chosen, securely hashed passwords.",
              ],
              [
                Database,
                "Local-first storage",
                "Run the application and store documents on your own infrastructure.",
              ],
              [
                FileCheck2,
                "Accountability built in",
                "Audited privileged actions, protected uploads and clear privacy notices.",
              ],
            ].map(([Icon, t, d]) => {
              const I = Icon as typeof ShieldCheck;
              return (
                <article key={t as string}>
                  <I size={24} />
                  <h3>{t as string}</h3>
                  <p>{d as string}</p>
                </article>
              );
            })}
          </div>
        </section>
        <section className="cta-band">
          <div>
            <div className="eyebrow">THE NEXT CHAPTER STARTS HERE</div>
            <h2>Make room for your campus’s potential.</h2>
            <p>
              Explore the locally hosted demonstration with your configured
              institution account.
            </p>
          </div>
          <Button asChild>
            <Link href="/login">
              Open CampusMind <ArrowRight size={16} />
            </Link>
          </Button>
        </section>
      </main>
      <footer className="landing-footer">
        <div>
          <Brand />
          <p>Institutional clarity. Student possibility.</p>
        </div>
        <div>
          Built for engineering institutions in Odisha and beyond.
          <br />
          Local-first institutional software · Synthetic demonstration.
        </div>
      </footer>
    </div>
  );
}
