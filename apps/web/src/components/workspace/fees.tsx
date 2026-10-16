"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CreditCard,
  Download,
  FileText,
  IndianRupee,
  Receipt,
  ShieldCheck,
} from "lucide-react";
import { api, send, type User } from "@/lib/api";
import { Button } from "../ui/button";
import { Badge, Empty, Failure, PageHeading, Skeleton } from "../ui/common";
import { useAction } from "./intelligence";
import { campusDate } from "./campus-life";

type Invoice = {
  id: string;
  reference: string;
  title: string;
  category: string;
  term: string;
  student: string;
  roll_no: string;
  amount_paise: number;
  status: string;
  due_at: string;
  overdue: boolean;
  payments: {
    id: string;
    provider: string;
    status: string;
    receipt_number: string | null;
    settled_at: string | null;
  }[];
};
type Ledger = {
  invoices: Invoice[];
  provider: string;
  test_mode: boolean;
  configured: boolean;
  totals: {
    billed_paise: number;
    collected_paise: number;
    outstanding_paise: number;
    demo_paid_paise: number;
  };
};
type Order = {
  id: string;
  provider: string;
  order_id: string;
  amount: number;
  currency: string;
  key_id: string;
  status: string;
  test_mode: boolean;
};
type ProviderResult = {
  razorpay_payment_id: string;
  razorpay_order_id: string;
  razorpay_signature: string;
};
type CheckoutOptions = {
  key: string;
  amount: number;
  currency: string;
  name: string;
  description: string;
  order_id: string;
  handler: (response: ProviderResult) => void;
  modal: { ondismiss: () => void };
  theme: { color: string };
};
declare global {
  interface Window {
    Razorpay?: new (options: CheckoutOptions) => {
      open: () => void;
      on: (event: string, handler: () => void) => void;
    };
  }
}

const rupees = (paise: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(
    paise / 100,
  );

async function checkout(
  order: Order,
  institution: string,
  description: string,
) {
  if (!window.Razorpay)
    await new Promise<void>((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://checkout.razorpay.com/v1/checkout.js";
      script.onload = () => resolve();
      script.onerror = () => {
        script.remove();
        reject(
          new Error("Unable to load secure checkout. Check your connection."),
        );
      };
      document.head.appendChild(script);
    });
  await new Promise<void>((resolve, reject) => {
    if (!window.Razorpay)
      return reject(new Error("Secure checkout is unavailable."));
    const payment = new window.Razorpay({
      key: order.key_id,
      amount: order.amount,
      currency: order.currency,
      name: institution,
      description,
      order_id: order.order_id,
      handler: (result) => {
        void send(`/campus/fees/orders/${order.id}/verify`, result).then(
          () => resolve(),
          reject,
        );
      },
      modal: {
        ondismiss: () =>
          reject(
            new Error(
              "Checkout closed. The invoice remains unpaid until the provider confirms a captured payment.",
            ),
          ),
      },
      theme: { color: "#2563EB" },
    });
    payment.on("payment.failed", () =>
      reject(
        new Error(
          "Payment was not completed. Review your bank and invoice status before retrying.",
        ),
      ),
    );
    payment.open();
  });
}

export function FeesPage({ user }: { user: User }) {
  const student = user.role === "student";
  const query = useQuery({
    queryKey: ["campus-fees"],
    queryFn: () => api<Ledger>("/campus/fees"),
    refetchInterval: 30000,
  });
  const [search, setSearch] = useState(""),
    [status, setStatus] = useState("all"),
    [confirm, setConfirm] = useState<string | null>(null);
  const { busy, act } = useAction();
  const rows =
    query.data?.invoices.filter(
      (i) =>
        (status === "all" || i.status === status) &&
        `${i.student} ${i.roll_no} ${i.title} ${i.reference}`
          .toLowerCase()
          .includes(search.toLowerCase()),
    ) || [];
  async function pay(invoice: Invoice) {
    const result = await act(
      async () => {
        const key = `fee_${invoice.id.replaceAll("-", "")}`;
        const order = await send<Order>(`/campus/fees/${invoice.id}/orders`, {
          idempotency_key: key,
        });
        if (order.provider === "demo")
          await send(`/campus/fees/orders/${order.id}/demo-complete`);
        else await checkout(order, user.institution.name, invoice.title);
        return true;
      },
      query.data?.test_mode
        ? "Test payment recorded. No money was collected."
        : "Captured payment verified. Your receipt is ready.",
    );
    if (result) setConfirm(null);
  }
  return (
    <>
      <PageHeading
        eyebrow="CAMPUS HUB · FEES & RECEIPTS"
        title={
          student
            ? "Your fees, clearly accounted for."
            : "Institution fee ledger"
        }
        description={
          student
            ? "Review course, exam, hostel and other fee invoices. You initiate every payment and receive a receipt after verification."
            : "Issue fixed invoices to an exact cohort, monitor collections and export the ledger. Amounts are always set by authorized administrators."
        }
      >
        {!student && (
          <Button asChild variant="outline">
            <a href="/api/campus/fees/export">
              <Download size={16} />
              Export ledger
            </a>
          </Button>
        )}
      </PageHeading>
      {query.isPending && <Skeleton />}
      {query.error && (
        <Failure error={query.error} retry={() => void query.refetch()} />
      )}
      {query.data && (
        <>
          {query.data.test_mode && (
            <div className="campus-alert">
              <ShieldCheck size={22} />
              <p>
                <strong>
                  {query.data.provider === "demo"
                    ? "Local demonstration mode"
                    : "Razorpay test mode"}
                </strong>{" "}
                · No real money is collected. Test receipts are labelled TEST
                and test transactions are excluded from real collections.
              </p>
            </div>
          )}
          {!query.data.configured && (
            <div className="campus-alert">
              <p>
                The institution’s payment account needs configuration. Your
                invoices remain available; online checkout is disabled.
              </p>
            </div>
          )}
          <div className="metric-grid campus-metrics">
            {[
              ["Billed", query.data.totals.billed_paise],
              ["Collected · real payments", query.data.totals.collected_paise],
              ["Outstanding", query.data.totals.outstanding_paise],
              ["Test payments", query.data.totals.demo_paid_paise],
            ].map(([label, value]) => (
              <div className="card card-pad" key={String(label)}>
                <IndianRupee size={21} />
                <h2>{rupees(Number(value))}</h2>
                <p>{label}</p>
              </div>
            ))}
          </div>
          {!student && <FeeIssuer />}
          <section className="card card-pad">
            <div className="row spread">
              <h2>Invoices</h2>
              <div className="row">
                <input
                  aria-label="Search fee invoices"
                  placeholder="Search student, fee or reference"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
                <select
                  aria-label="Filter fee status"
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                >
                  {["all", "unpaid", "paid", "demo_paid", "void"].map((s) => (
                    <option value={s} key={s}>
                      {s.replaceAll("_", " ")}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            {!rows.length && (
              <Empty
                title="No matching invoices"
                description={
                  student
                    ? "Your institution will issue invoices here when fees are due."
                    : "Create a fee plan for a cohort to issue individual invoices and notify students automatically."
                }
              />
            )}
            {rows.map((i) => (
              <article className="fee-invoice" key={i.id}>
                <div className="row spread">
                  <div>
                    <h3>{i.title}</h3>
                    <p className="hint">
                      {i.reference} · {i.term} · {i.category}
                    </p>
                    {!student && (
                      <p>
                        {i.student} · {i.roll_no}
                      </p>
                    )}
                  </div>
                  <div>
                    <h2>{rupees(i.amount_paise)}</h2>
                    <Badge tone={i.status === "paid" ? "green" : "neutral"}>
                      {i.status.replaceAll("_", " ")}
                    </Badge>
                    {i.overdue && <Badge>Overdue</Badge>}
                  </div>
                </div>
                <p className="hint">Due {campusDate(i.due_at)}</p>
                <div className="row">
                  {student &&
                    !["paid", "void"].includes(i.status) &&
                    !(i.status === "demo_paid" && query.data.test_mode) && (
                      <Button
                        disabled={busy || !query.data.configured}
                        onClick={() =>
                          setConfirm(confirm === i.id ? null : i.id)
                        }
                      >
                        <CreditCard size={16} />
                        {query.data.test_mode
                          ? "Review test payment"
                          : "Review & pay"}
                      </Button>
                    )}
                  {i.payments
                    .filter((p) => p.receipt_number)
                    .map((p) => (
                      <Button key={p.id} variant="outline" asChild>
                        <a href={`/api/campus/fees/receipts/${p.id}`}>
                          <Receipt size={16} />
                          {p.receipt_number?.startsWith("TEST-")
                            ? "Download test receipt"
                            : "Download receipt"}
                        </a>
                      </Button>
                    ))}
                  {i.payments
                    .filter(
                      (p) =>
                        p.provider === "razorpay" && p.status === "created",
                    )
                    .map((p) => (
                      <Button
                        variant="outline"
                        key={p.id}
                        disabled={busy}
                        onClick={() =>
                          void act(async () => {
                            const result = await send<{ status: string }>(
                              `/campus/fees/orders/${p.id}/refresh`,
                            );
                            if (result.status !== "paid")
                              throw new Error(
                                "The gateway has not confirmed a captured payment yet. Check again later.",
                              );
                          }, "Payment verified and receipt updated")
                        }
                      >
                        Refresh payment status
                      </Button>
                    ))}
                </div>
                {confirm === i.id && (
                  <div className="campus-feedback">
                    <h3>
                      Confirm{" "}
                      {query.data.test_mode ? "test payment" : "payment"}
                    </h3>
                    <p>
                      {i.title} · {rupees(i.amount_paise)} ·{" "}
                      {user.institution.name}
                    </p>
                    <p className="hint">
                      {query.data.test_mode
                        ? "This demonstrates a payment and creates a TEST receipt. It does not settle a real institutional fee."
                        : "Continue to the payment provider. Your invoice is settled only after the server confirms the captured amount and currency."}
                    </p>
                    <div className="row">
                      <Button disabled={busy} onClick={() => void pay(i)}>
                        {busy
                          ? "Processing…"
                          : query.data.test_mode
                            ? "Confirm test payment"
                            : "Continue to secure checkout"}
                      </Button>
                      <Button
                        variant="ghost"
                        disabled={busy}
                        onClick={() => setConfirm(null)}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}
                {!student && (
                  <details className="campus-details">
                    <summary>Finance actions</summary>
                    {i.payments
                      .filter((p) => p.provider === "razorpay")
                      .map((p) => (
                        <form
                          key={p.id}
                          className="campus-stack"
                          onSubmit={(e) => {
                            e.preventDefault();
                            const form = new FormData(e.currentTarget);
                            void act(
                              () =>
                                send(`/campus/fees/orders/${p.id}/reconcile`, {
                                  payment_id: form.get("payment_id"),
                                }),
                              "Gateway payment reconciled",
                            );
                          }}
                        >
                          <p className="hint">
                            Order {p.id} · {p.status}. Use a payment ID from
                            your authorized merchant dashboard. Amount, order
                            receipt and capture status are checked server-side.
                          </p>
                          <label className="field">
                            Gateway payment ID
                            <input
                              name="payment_id"
                              required
                              pattern="pay_[A-Za-z0-9]+"
                            />
                          </label>
                          <Button disabled={busy} variant="outline">
                            Verify with gateway
                          </Button>
                        </form>
                      ))}
                    {i.status === "unpaid" && !i.payments.length && (
                      <form
                        className="campus-stack"
                        onSubmit={(e) => {
                          e.preventDefault();
                          const form = new FormData(e.currentTarget);
                          void act(
                            () =>
                              send(`/campus/fees/${i.id}/void`, {
                                reason: form.get("reason"),
                              }),
                            "Invoice voided with audit record",
                          );
                        }}
                      >
                        <label className="field">
                          Reason for voiding this invoice
                          <textarea
                            name="reason"
                            minLength={10}
                            maxLength={1000}
                            required
                          />
                        </label>
                        <Button disabled={busy} variant="outline">
                          Void unpaid invoice
                        </Button>
                      </form>
                    )}
                  </details>
                )}
              </article>
            ))}
          </section>
        </>
      )}
    </>
  );
}

function FeeIssuer() {
  const departments = useQuery({
    queryKey: ["departments"],
    queryFn: () => api<{ id: string; code: string }[]>("/departments"),
  });
  const { busy, act } = useAction();
  const [preview, setPreview] = useState<{
    students: number;
    total_paise: number;
  } | null>(null);
  function payload(form: HTMLFormElement) {
    const f = new FormData(form);
    return {
      reference: f.get("reference"),
      title: f.get("title"),
      category: f.get("category"),
      term: f.get("term"),
      amount_paise: Math.round(Number(f.get("amount")) * 100),
      due_at: new Date(String(f.get("due_at"))).toISOString(),
      audience: {
        department_id: f.get("department_id") || null,
        academic_year: Number(f.get("academic_year")) || null,
        semester: Number(f.get("semester")) || null,
        section: String(f.get("section") || "").toUpperCase(),
        graduation_year: Number(f.get("graduation_year")) || null,
        student_roll_no: String(f.get("student_roll_no") || ""),
      },
    };
  }
  return (
    <details className="card card-pad" style={{ marginBlock: 20 }}>
      <summary className="row">
        <FileText size={19} />
        <strong>Create fee plan & issue invoices</strong>
      </summary>
      <p className="hint">
        Use a unique reference for each term or instalment. Preview recipients
        before confirming. Issued amounts remain fixed and are never inferred by
        AI.
      </p>
      <form
        className="form-grid"
        onChange={() => setPreview(null)}
        onSubmit={(e) => {
          e.preventDefault();
          const form = e.currentTarget;
          if (!preview) return;
          void act(async () => {
            await send("/campus/fees/plans", payload(form));
            form.reset();
            setPreview(null);
          }, "Invoices issued and students notified");
        }}
      >
        <label className="field">
          Unique reference
          <input
            required
            name="reference"
            placeholder="CSE-SEM7-TUITION-2026"
            pattern="[a-zA-Z0-9_-]{3,80}"
          />
        </label>
        <label className="field">
          Fee title
          <input
            required
            name="title"
            minLength={3}
            maxLength={200}
            placeholder="Semester tuition · instalment 1"
          />
        </label>
        <label className="field">
          Category
          <select name="category">
            {["tuition", "exam", "hostel", "transport", "other"].map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label className="field">
          Term
          <input
            required
            name="term"
            minLength={2}
            maxLength={80}
            placeholder="2026–27 · Semester 7"
          />
        </label>
        <label className="field">
          Amount per student · INR
          <input
            required
            name="amount"
            type="number"
            step="0.01"
            min={1}
            max={1000000}
          />
        </label>
        <label className="field">
          Due date
          <input required name="due_at" type="datetime-local" />
        </label>
        <label className="field">
          Branch
          <select name="department_id">
            <option value="">All branches</option>
            {departments.data?.map((d) => (
              <option key={d.id} value={d.id}>
                {d.code}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Academic year
          <input
            type="number"
            name="academic_year"
            min={1}
            max={6}
            placeholder="All years"
          />
        </label>
        <label className="field">
          Semester
          <input
            type="number"
            name="semester"
            min={1}
            max={12}
            placeholder="All semesters"
          />
        </label>
        <label className="field">
          Section
          <input name="section" maxLength={30} placeholder="All sections" />
        </label>
        <label className="field">
          Graduation year
          <input name="graduation_year" type="number" min={2020} max={2100} />
        </label>
        <label className="field">
          Individual registration number
          <input name="student_roll_no" maxLength={80} placeholder="Optional" />
        </label>
        <div className="row" style={{ gridColumn: "1 / -1" }}>
          <Button
            type="button"
            variant="outline"
            disabled={busy}
            onClick={(e) => {
              const form = e.currentTarget.closest("form")!;
              if (!form.reportValidity()) return;
              void act(
                async () =>
                  setPreview(
                    await send("/campus/fees/plans/preview", payload(form)),
                  ),
                "Fee audience preview ready",
              );
            }}
          >
            Preview invoices
          </Button>
          <Button disabled={busy || !preview || preview.students === 0}>
            Confirm & issue invoices
          </Button>
          {preview && (
            <p>
              {preview.students} students · {rupees(preview.total_paise)} total
            </p>
          )}
        </div>
      </form>
    </details>
  );
}
