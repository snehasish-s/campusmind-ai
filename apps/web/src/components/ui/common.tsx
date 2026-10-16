"use client";
import { AlertCircle, ArrowRight, Inbox, LoaderCircle } from "lucide-react";
import { Button } from "./button";
import { cn } from "@/lib/utils";
import Link from "next/link";
export function Badge({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: string;
}) {
  return <span className={cn("badge", `badge-${tone}`)}>{children}</span>;
}
export function Empty({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Inbox size={26} />
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
      {children}
    </div>
  );
}
export function Failure({
  error,
  retry,
}: {
  error: Error;
  retry?: () => void;
}) {
  return (
    <div role="alert" className="error-panel">
      <AlertCircle size={22} />
      <div>
        <strong>We couldn’t load this information</strong>
        <p>{error.message}</p>
        {retry && (
          <Button onClick={retry} variant="outline" size="sm">
            Try again
          </Button>
        )}
      </div>
    </div>
  );
}
export function Skeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div aria-label="Loading" className="skeleton-list">
      {Array.from({ length: rows }, (_, i) => (
        <div className="skeleton" key={i} />
      ))}
    </div>
  );
}
export function Pending({ label = "Saving…" }: { label?: string }) {
  return (
    <>
      <LoaderCircle size={16} className="spin" />
      {label}
    </>
  );
}
export function PageHeading({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className="heading-actions">{children}</div>
    </div>
  );
}
export function CardHeading({
  title,
  description,
  href,
}: {
  title: string;
  description?: string;
  href?: string;
}) {
  return (
    <div className="card-heading">
      <div>
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </div>
      {href && (
        <Link className="text-link" href={href}>
          View all <ArrowRight size={15} />
        </Link>
      )}
    </div>
  );
}
