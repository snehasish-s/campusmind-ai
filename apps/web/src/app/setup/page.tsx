"use client";
import { useState } from "react";
import Link from "next/link";
import { send } from "@/lib/api";
import { Brand } from "@/components/brand";
import { Button } from "@/components/ui/button";
export default function SetupPage() {
  const [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <main style={{ maxWidth: 640, margin: "60px auto", padding: 24 }}>
      <Brand />
      <section className="card card-pad" style={{ marginTop: 30 }}>
        <h1>Set up your institution</h1>
        <p style={{ marginBlock: 18 }}>
          For the first institution on a new installation. Your setup token
          comes from the private hosting environment. This form closes
          automatically after setup.
        </p>
        <form
          className="form-stack"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            const f = new FormData(e.currentTarget);
            try {
              const result = await send<{ message: string }>(
                "/setup",
                Object.fromEntries(f),
              );
              setMessage(result.message);
            } catch (error) {
              setMessage((error as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          {[
            ["token", "Private setup token", "password"],
            ["institution_name", "Institution name", "text"],
            [
              "slug",
              "Institution code · lowercase letters, numbers and hyphens",
              "text",
            ],
            ["admin_name", "Administrator name", "text"],
            ["admin_email", "Administrator email", "email"],
            [
              "password",
              "Choose a password · at least 12 characters",
              "password",
            ],
          ].map(([name, label, type]) => (
            <label className="field" key={name}>
              {label}
              <input
                name={name}
                type={type}
                required
                minLength={
                  name === "password" ? 12 : name === "token" ? 32 : undefined
                }
                autoComplete={name === "password" ? "new-password" : "off"}
              />
            </label>
          ))}
          <Button disabled={busy}>
            {busy ? "Creating institution…" : "Create institution"}
          </Button>
        </form>
        {message && (
          <p role="status" style={{ marginTop: 20 }}>
            {message}
          </p>
        )}
        <Link className="text-link" href="/login" style={{ marginTop: 20 }}>
          Continue to sign in
        </Link>
      </section>
    </main>
  );
}
