"use client";
import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Badge, Failure, Skeleton } from "@/components/ui/common";
export default function SharedPassport({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = use(params);
  const query = useQuery({
    queryKey: ["shared-passport", token],
    queryFn: () =>
      api<{
        student: string;
        expires_at: string;
        evidence: {
          skill: string;
          evidence_type: string;
          status: string;
          score: number | null;
          provider: string;
          created_at: string;
        }[];
      }>(`/campus/passport/shared/${encodeURIComponent(token)}`),
    retry: false,
  });
  return (
    <main className="offline-page">
      <div className="eyebrow">CAMPUSMIND · CONSENTED EVIDENCE SHARE</div>
      <h1>Student skill passport</h1>
      <p>
        This expiring link contains evidence selected by the student. It
        describes demonstrated tasks and recorded claims; it does not guarantee
        proficiency or hiring outcomes.
      </p>
      {query.isPending && <Skeleton />}
      {query.error && <Failure error={query.error} />}
      {query.data && (
        <>
          <h2>{query.data.student}</h2>
          <p className="hint">
            Expires {new Date(query.data.expires_at + "Z").toLocaleString()}
          </p>
          {query.data.evidence.map((e, i) => (
            <section className="card card-pad" key={i}>
              <h3>{e.skill}</h3>
              <Badge>{e.evidence_type.replaceAll("_", " ")}</Badge>
              <p>
                {e.score !== null
                  ? `Recorded score: ${e.score}%`
                  : "Unverified claim — no proficiency score"}
              </p>
              <p className="hint">
                {e.provider} · {e.status}
              </p>
            </section>
          ))}
        </>
      )}
    </main>
  );
}
