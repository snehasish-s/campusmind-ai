import { test, expect, type Page, type Cookie } from "@playwright/test";

// Reuse still-valid test sessions in memory. Explicit logout invalidates them;
// every reuse is verified server-side. Production rate limits stay unchanged.
const sessions = new Map<string, Cookie[]>();
export async function signIn(page: Page, identifier: string) {
  // Unmount the previous workspace before switching cookies; its polling must
  // not observe an intermediate unauthenticated cookie jar and redirect us.
  await page.goto("/login");
  const institution = `${process.env.CM_E2E_INSTITUTION}-${test.info().project.name}`;
  const key = `${institution}:${identifier}`;
  const destination = ["STUDENT", "TEACHER", "JUNIOR"].includes(identifier)
    ? "/app/campus"
    : "/app";
  const cached = sessions.get(key);
  if (cached) {
    await page.context().clearCookies();
    await page.context().addCookies(cached);
    const response = await page.request.get("/api/auth/me");
    if (response.ok() && (await response.json()).roll_no === identifier) {
      await page.goto(destination);
      await expect(page).toHaveURL(new RegExp(`${destination.replaceAll("/", "\\/")}$`));
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      return;
    }
  }
  await page.context().clearCookies();
  await page.goto("/login");
  await page.getByLabel("Institution code", { exact: true }).fill(institution);
  await page.getByLabel("Roll number or staff email").fill(identifier);
  await page
    .getByLabel("Password", { exact: true })
    .fill(process.env.CM_E2E_PASSWORD!);
  await page.getByRole("button", { name: "Sign in securely" }).click();
  await expect(page).toHaveURL(
    new RegExp(`${destination.replaceAll("/", "\\/")}$`),
  );
  sessions.set(
    key,
    (await page.context().cookies()).filter((c) =>
      ["cm_session", "cm_csrf"].includes(c.name),
    ),
  );
}
