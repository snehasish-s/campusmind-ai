import { test, expect, type Page } from "@playwright/test";
import { signIn } from "./auth";
import path from "node:path";

async function login(page: Page, id = "ADMIN") {
  await signIn(page, id);
  await expect(page).toHaveURL(
    ["STUDENT", "TEACHER", "JUNIOR"].includes(id) ? /\/app\/campus$/ : /\/app$/,
  );
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
}
async function navigate(page: Page, name: string, mobile: boolean) {
  if (mobile)
    await page
      .getByRole("button", { name: "Open navigation", exact: true })
      .click();
  const nav = page.getByRole("navigation", { name: "Workspace navigation" });
  if (
    (await nav.getByRole("link", { name, exact: true }).count()) === 0 &&
    (await nav
      .getByRole("link", { name: "Open PlacementOS", exact: true })
      .count())
  ) {
    await nav
      .getByRole("link", { name: "Open PlacementOS", exact: true })
      .click();
    if (mobile)
      await page
        .getByRole("button", { name: "Open navigation", exact: true })
        .click();
  }
  await page
    .getByRole("navigation", { name: "Workspace navigation" })
    .getByRole("link", { name, exact: true })
    .click();
}

test("public site, responsive navigation, real metrics and student search", async ({
  page,
  isMobile,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", {
      name: "A connected campus. A clearer future.",
    }),
  ).toBeVisible();
  await expect(page.locator(".hero-art")).toHaveCSS("opacity", "1");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: testInfo.outputPath("landing.png"),
    fullPage: true,
  });
  await login(page);
  await expect(page.locator(".metric-value").first()).toContainText(/\d+/);
  await expect(page.locator(".metric").last()).toHaveCSS("opacity", "1");
  await expect(
    page.getByRole("heading", { name: "Your student community" }),
  ).toBeVisible();
  await expect(page.locator(".chart-layout > section").first()).toHaveCSS(
    "opacity",
    "1",
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: testInfo.outputPath("dashboard.png"),
    fullPage: true,
  });
  await navigate(page, "Student registry", isMobile);
  await page.getByLabel("Search student registry").fill("SYN00003");
  await expect(
    page.getByText("Synthetic Student 003", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "View", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", { name: "Close dialog" }).click();
  await page.getByRole("button", { name: "Use dark theme" }).click();
  await expect(page.locator(".dark")).toBeVisible();
  expect(errors).toEqual([]);
});

test("student edits profile, uploads resume and browses a published drive", async ({
  page,
  isMobile,
}, testInfo) => {
  await login(page, "STUDENT");
  await navigate(page, "My profile", isMobile);
  await page
    .getByLabel("About you")
    .fill("Synthetic browser-tested academic profile.");
  await page.getByRole("button", { name: "Save profile" }).click();
  await expect(page.getByText("Your profile has been updated.")).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("About you")).toHaveValue(
    "Synthetic browser-tested academic profile.",
  );
  await navigate(page, "My resume", isMobile);
  await page
    .getByLabel("Choose resume")
    .setInputFiles(path.resolve("../../data/browser-resume.docx"));
  await page.getByRole("button", { name: "Upload new version" }).click();
  await expect(
    page.getByText("Resume uploaded. A new version has been saved."),
  ).toBeVisible();
  await expect(page.getByText("Text extracted").first()).toBeVisible();
  await navigate(page, "Recruitment drives", isMobile);
  await expect(
    page.getByText("Northstar Labs (Synthetic)", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "View details" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  const register = page.getByRole("button", { name: "Register for drive" });
  if (await register.isVisible()) {
    await register.click();
    await expect(page.getByText("Application registered.")).toBeVisible();
  }
  await page.screenshot({
    path: testInfo.outputPath("student-drives.png"),
    fullPage: true,
  });
});

test("CSV mapping, validation and confirmation use real API records", async ({
  page,
  isMobile,
}) => {
  await login(page, "PLACEMENT");
  await navigate(page, "Bulk student import", isMobile);
  const suffix = isMobile ? "MOBILE" : "DESKTOP";
  const csv = `roll_no,full_name,email,department,graduation_year,cgpa,active_backlogs,phone\nBROWSER${suffix},Synthetic ${suffix},browser${suffix.toLowerCase()}@example.com,CSE,2027,8,0,\n`;
  await page.getByLabel("Choose student CSV").setInputFiles({
    name: `browser-${suffix}.csv`,
    mimeType: "text/csv",
    buffer: Buffer.from(csv),
  });
  await expect(
    page.getByRole("heading", { name: "Map your columns" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Validate & preview" }).click();
  await expect(
    page.getByRole("button", { name: "Confirm import" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Confirm import" }).click();
  await expect(page.getByText("Import complete", { exact: true })).toBeVisible({
    timeout: 30000,
  });
});
