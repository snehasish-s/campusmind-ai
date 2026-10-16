"use client";
import { useQuery } from "@tanstack/react-query";
import { api, send } from "@/lib/api";
import { Button } from "../ui/button";
import { Badge, Failure } from "../ui/common";
import { useAction } from "./intelligence";
type ReviewAttempt = {
  id: string;
  title: string;
  status: string;
  score: number | null;
  manual_review_pending: boolean;
  examiner_total_score?: number;
  questions: {
    id: string;
    prompt: string;
    kind: string;
    points: number;
    explanation: string;
  }[];
  answers: Record<string, number[] | string>;
  manual_reviews?: Record<string, { points: number; feedback: string }>;
};
export function ExaminerReview({ studentId }: { studentId: string }) {
  const { busy, act } = useAction();
  const attempts = useQuery({
    queryKey: ["student-attempts", studentId],
    queryFn: () => api<ReviewAttempt[]>(`/attempts?student_id=${studentId}`),
  });
  return (
    <details style={{ marginTop: 20 }}>
      <summary>Assessment history & examiner review</summary>
      {attempts.error && <Failure error={attempts.error} />}{" "}
      {attempts.data
        ?.filter((a) => a.status === "submitted")
        .map((a) => (
          <article
            className="card card-pad"
            style={{ marginTop: 18 }}
            key={a.id}
          >
            <h3>{a.title}</h3>
            <p className="hint">
              Objective score: {a.score ?? "No objective questions"}
              {a.examiner_total_score != null
                ? ` · Examiner-reviewed total: ${a.examiner_total_score}%`
                : ""}
            </p>
            <Badge tone={a.manual_review_pending ? "amber" : "green"}>
              {a.manual_review_pending
                ? "Written answers need review"
                : "Review complete"}
            </Badge>
            {a.questions
              .filter((q) => !["single", "multiple"].includes(q.kind))
              .map((q) => (
                <form
                  key={q.id}
                  className="form-stack"
                  style={{ marginTop: 20 }}
                  onSubmit={(e) => {
                    e.preventDefault();
                    const f = new FormData(e.currentTarget);
                    void act(
                      () =>
                        send(
                          `/attempts/${a.id}/manual-review`,
                          {
                            question_id: q.id,
                            points: Number(f.get("points")),
                            feedback: f.get("feedback"),
                          },
                          "PUT",
                        ),
                      "Examiner review saved",
                    );
                  }}
                >
                  <strong>{q.prompt}</strong>
                  <p style={{ whiteSpace: "pre-wrap" }}>
                    {String(a.answers[q.id] || "No response")}
                  </p>
                  <p className="hint">
                    Rubric:{" "}
                    {q.explanation || "Use your approved marking policy."}
                  </p>
                  <label className="field">
                    Marks · out of {q.points}
                    <input
                      type="number"
                      name="points"
                      min={0}
                      max={q.points}
                      step="0.5"
                      defaultValue={a.manual_reviews?.[q.id]?.points || 0}
                      required
                    />
                  </label>
                  <label className="field">
                    Examiner feedback
                    <textarea
                      name="feedback"
                      required
                      minLength={5}
                      defaultValue={a.manual_reviews?.[q.id]?.feedback || ""}
                    />
                  </label>
                  <Button disabled={busy}>Save examiner review</Button>
                </form>
              ))}
          </article>
        ))}
    </details>
  );
}
