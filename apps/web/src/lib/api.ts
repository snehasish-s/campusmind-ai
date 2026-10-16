export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const csrf =
    typeof document !== "undefined"
      ? document.cookie
          .split("; ")
          .find((c) => c.startsWith("cm_csrf="))
          ?.split("=")[1]
      : "";
  const response = await fetch(`/api${path}`, {
    ...options,
    credentials: "same-origin",
    cache: "no-store",
    headers: {
      ...(options.body && !(options.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...(csrf ? { "X-CSRF-Token": decodeURIComponent(csrf) } : {}),
      ...options.headers,
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new ApiError(
      typeof payload.detail === "string"
        ? payload.detail
        : "The request could not be completed. Please try again.",
      response.status,
    );
  }
  return response.json();
}
export const send = <T>(path: string, body?: unknown, method = "POST") =>
  api<T>(path, { method, ...(body ? { body: JSON.stringify(body) } : {}) });
export type User = {
  id: string;
  full_name: string;
  email: string;
  roll_no: string;
  role: string;
  department_id: string | null;
  placement_access: {
    allowed: boolean;
    academic_year: number | null;
    reason: string;
  };
  institution: {
    id: string;
    slug: string;
    name: string;
    city: string;
    privacy_notice: string;
  };
};
export type Student = {
  id: string;
  full_name: string;
  email: string;
  roll_no: string;
  active: boolean;
  department: string;
  graduation_year: number;
  cgpa: number;
  active_backlogs: number;
  phone: string;
  bio: string;
  projects: { title: string; description: string }[];
  internships: { title: string; description: string }[];
  resume_count: number;
  invitation_status: string;
};
export type Drive = {
  id: string;
  company_name: string;
  position: string;
  description: string;
  employment_type: string;
  location: string;
  ctc: string;
  required_skills: string[];
  min_cgpa: number;
  max_backlogs: number;
  eligible_branches: string[];
  graduation_year: number;
  deadline: string;
  drive_date: string;
  selection_rounds: string[];
  additional_requirements: string;
  status: string;
  applications: number;
  eligible: boolean | null;
  applied: boolean;
};
export type Metrics = {
  students: number | null;
  active: number;
  resumes: number;
  staff: number;
  drives: number;
  applications: number;
  offers: number;
  documents: number;
  departments: { name: string; students: number; active: number }[];
  activity: { id: string; title: string; kind: string; created_at: string }[];
};
export type ImportJob = {
  recoverable?: boolean;
  id: string;
  filename: string;
  policy: string;
  status: string;
  total: number;
  processed: number;
  created: number;
  updated: number;
  skipped: number;
  errors: number;
  failure: string | null;
  created_at: string;
  preview?: Record<string, string | number>[];
  row_errors?: { row: number; message: string }[];
  actions?: Record<string, number>;
};
