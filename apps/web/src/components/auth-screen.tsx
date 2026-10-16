"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowLeft, ArrowRight, ShieldCheck } from "lucide-react";
import { Brand } from "./brand";
import { Button } from "./ui/button";
import { Pending } from "./ui/common";
import { send, type User } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";

const schema = z.object({
  institution: z.string().min(1, "Enter your institution code"),
  identifier: z.string().min(1, "Enter your roll number or email"),
  password: z.string().min(1, "Enter your password"),
});
export function AuthScreen({ activate = false }: { activate?: boolean }) {
  const router = useRouter(),
    client = useQueryClient();
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [reset, setReset] = useState(false);
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [consent, setConsent] = useState(false);
  const [pending, setPending] = useState(false);
  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors, isSubmitting },
  } = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { institution: "demo", identifier: "", password: "" },
  });
  useEffect(() => {
    if (!activate) return;
    const frame = requestAnimationFrame(() => {
      const value =
        new URLSearchParams(window.location.hash.slice(1)).get("token") || "";
      setToken(value);
      window.history.replaceState(null, "", window.location.pathname);
    });
    return () => cancelAnimationFrame(frame);
  }, [activate]);
  async function login(values: z.infer<typeof schema>) {
    setError("");
    try {
      const user = await send<User>("/auth/login", values);
      client.clear();
      client.setQueryData(["me"], user);
      router.push(
        ["student", "faculty", "campus_staff"].includes(user.role)
          ? "/app/campus"
          : "/app",
      );
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function activation(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setPending(true);
    try {
      const result = await send<{ institution: string; roll_no: string }>(
        "/auth/activate",
        { token, password, consent },
      );
      setSuccess(
        `Your account is ready. Sign in with institution ${result.institution} and login ID ${result.roll_no}.`,
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPending(false);
    }
  }
  async function requestReset() {
    setError("");
    setPending(true);
    try {
      const result = await send<{ message: string }>("/auth/password-reset", {
        institution: getValues("institution"),
        identifier: getValues("identifier"),
      });
      setSuccess(result.message);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPending(false);
    }
  }
  return (
    <div className="auth-page">
      <aside className="auth-story">
        <Link href="/">
          <Brand />
        </Link>
        <div>
          <div className="eyebrow" style={{ color: "#5eead4" }}>
            ONE CAMPUS. EVERY POSSIBILITY.
          </div>
          <h1>
            Better connected.
            <br />
            Better prepared.
            <br />
            <span>Ready for what’s next.</span>
          </h1>
          <p>
            Your institution’s people, records and career opportunities, brought
            into one thoughtful workspace.
          </p>
          <div className="story-grid">
            <article>
              <strong>CollegeOps</strong>
              <p>Clarity for your institution.</p>
            </article>
            <article>
              <strong>PlacementOS</strong>
              <p>Possibility for every student.</p>
            </article>
          </div>
        </div>
        <small>Local demonstration · Synthetic data only</small>
      </aside>
      <main className="auth-form-wrap">
        <div className="auth-form">
          <Link className="auth-back" href="/">
            <ArrowLeft size={14} />
            Back to CampusMind
          </Link>
          <div className="icon-tile">
            <ShieldCheck size={24} />
          </div>
          <h2>
            {activate
              ? "Your next chapter starts here."
              : reset
                ? "Reset your password"
                : "Welcome back."}
          </h2>
          <p>
            {activate
              ? "Choose a secure password to activate your account or complete your password reset."
              : reset
                ? "Enter your institution and login ID. We’ll send instructions to your registered email."
                : "Sign in to your institution’s workspace."}
          </p>
          {error && (
            <div role="alert" className="error-panel">
              {error}
            </div>
          )}
          {success ? (
            <div className="stack">
              <div className="insight-note">{success}</div>
              <Button asChild>
                <Link href="/login">
                  Continue to sign in <ArrowRight size={15} />
                </Link>
              </Button>
            </div>
          ) : activate ? (
            <form onSubmit={activation}>
              <div className="field">
                <label htmlFor="new-password">New password</label>
                <input
                  id="new-password"
                  type="password"
                  minLength={12}
                  maxLength={128}
                  required
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <p className="hint">
                  Use at least 12 characters. A memorable passphrase works well.
                </p>
              </div>
              <div className="field">
                <label htmlFor="confirm-password">Confirm password</label>
                <input
                  id="confirm-password"
                  type="password"
                  required
                  autoComplete="new-password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                />
              </div>
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={consent}
                  onChange={(e) => setConsent(e.target.checked)}
                  required
                />
                <span>
                  I understand my institution uses my profile and resume for
                  placement coordination. I can contact my administrator to
                  request access, correction or deletion.
                </span>
              </label>
              <Button disabled={pending || !token}>
                {pending ? (
                  <Pending />
                ) : (
                  <>
                    Set password <ArrowRight size={15} />
                  </>
                )}
              </Button>
              {!token && (
                <p className="field-error">
                  Open the complete single-use link from your invitation email.
                </p>
              )}
            </form>
          ) : (
            <form
              onSubmit={
                reset
                  ? (e) => {
                      e.preventDefault();
                      void requestReset();
                    }
                  : handleSubmit(login)
              }
            >
              <div className="field">
                <label htmlFor="institution">Institution code</label>
                <input
                  id="institution"
                  autoComplete="organization"
                  {...register("institution")}
                />
                {errors.institution && (
                  <p className="field-error">{errors.institution.message}</p>
                )}
              </div>
              <div className="field">
                <label htmlFor="identifier">Roll number or staff email</label>
                <input
                  id="identifier"
                  autoComplete="username"
                  placeholder="e.g. SYN202700001"
                  {...register("identifier")}
                />
                {errors.identifier && (
                  <p className="field-error">{errors.identifier.message}</p>
                )}
              </div>
              {!reset && (
                <div className="field">
                  <div className="between">
                    <label htmlFor="password">Password</label>
                    <button
                      type="button"
                      className="text-link"
                      onClick={() => setReset(true)}
                    >
                      Forgot password?
                    </button>
                  </div>
                  <input
                    id="password"
                    type="password"
                    autoComplete="current-password"
                    {...register("password")}
                  />
                  {errors.password && (
                    <p className="field-error">{errors.password.message}</p>
                  )}
                </div>
              )}
              <Button disabled={isSubmitting || pending}>
                {isSubmitting || pending ? (
                  <Pending label="Please wait…" />
                ) : (
                  <>
                    {reset ? "Send reset instructions" : "Sign in securely"}
                    <ArrowRight size={16} />
                  </>
                )}
              </Button>
              {reset && (
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setReset(false)}
                >
                  Back to sign in
                </Button>
              )}
              <p className="auth-note">
                {reset
                  ? "Reset links expire after one hour and can only be used once."
                  : "Students: use your invitation email to activate your account first. Demo staff credentials are generated locally during setup; there is no shared default password."}
              </p>
            </form>
          )}
        </div>
      </main>
    </div>
  );
}
