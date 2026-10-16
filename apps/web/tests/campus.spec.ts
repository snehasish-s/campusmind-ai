import { test, expect, type Page } from "@playwright/test";
import { signIn } from "./auth";
async function login(page: Page, id: string) {
  await signIn(page, id);
  await expect(page).toHaveURL(
    ["STUDENT", "TEACHER", "JUNIOR"].includes(id) ? /\/app\/campus$/ : /\/app$/,
  );
  await page.goto("/app/campus");
  await expect(
    page.getByRole("heading", {
      name: "The right update, for the right student.",
    }),
  ).toBeVisible();
}

test("campus cohort routing, timetable import, teacher assignment and student acknowledgement", async ({
  page,
}, testInfo) => {
  const section = testInfo.project.name === "desktop" ? "A" : "B";
  const weekday = section === "A" ? 0 : 1;
  await login(page, "ADMIN");
  await page
    .getByText("Campus administration · routing & publishing permissions", {
      exact: true,
    })
    .click();
  await page
    .getByRole("combobox", { name: "Import type", exact: true })
    .selectOption("cohorts");
  await page.getByLabel("CSV / XLSX", { exact: true }).setInputFiles({
    name: "cohorts.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      `roll_no,department,graduation_year,academic_year,semester,section\nSTUDENT,CSE,2027,4,7,${section}\n`,
    ),
  });
  await page.getByRole("button", { name: "Validate & preview" }).click();
  await expect(
    page.getByText("1 valid rows · 0 errors", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Confirm import", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Imported", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("combobox", { name: "Import type", exact: true })
    .selectOption("timetable");
  const today = new Date(),
    until = new Date(today.getTime() + 60 * 86400000);
  const csv = `department,graduation_year,academic_year,semester,section,subject,teacher_roll_no,weekday,starts,ends,room,valid_from,valid_until\nCSE,2027,4,7,${section},Database Systems,TEACHER,${weekday},09:00,10:00,R101,${today.toISOString().slice(0, 10)},${until.toISOString().slice(0, 10)}\n`;
  await page.getByLabel("CSV / XLSX", { exact: true }).setInputFiles({
    name: "timetable.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(csv),
  });
  await page.getByRole("button", { name: "Validate & preview" }).click();
  await expect(
    page.getByText("1 valid rows · 0 errors", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Confirm import", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Imported", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await login(page, "TEACHER");
  await page.getByText("Publish an update · teacher", { exact: true }).click();
  const select = page.getByRole("combobox", {
    name: "Fill audience from timetable",
  });
  const option = await select
    .locator("option")
    .filter({ hasText: `Database Systems · ${section} ·` })
    .getAttribute("value");
  await select.selectOption(option!);
  const title = `SQL joins practice ${section}`;
  await page.getByLabel("Title", { exact: true }).fill(title);
  await page
    .getByLabel("Message", { exact: true })
    .fill("Write INNER JOIN and LEFT JOIN queries for the synthetic tables.");
  await page.getByLabel("Private document (up to 8 MB)").setInputFiles({
    name: "assignment.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("Synthetic assignment: explain an INNER JOIN."),
  });
  await page.getByRole("button", { name: "Check recipients" }).click();
  await expect(
    page.getByText("1 matching student accounts", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Publish update", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: title, exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await login(page, "STUDENT");
  const article = page
    .locator("article")
    .filter({ has: page.getByRole("heading", { name: title, exact: true }) });
  await expect(article).toBeVisible();
  await expect(
    page.getByRole("cell", { name: "Database Systems", exact: true }),
  ).toBeVisible();
  await article
    .getByRole("button", { name: "I have read this", exact: true })
    .click();
  await expect(
    article.getByRole("button", { name: "Acknowledged", exact: true }),
  ).toBeDisabled();
  const download = page.waitForEvent("download");
  await article.getByRole("link", { name: "assignment.txt" }).click();
  expect((await download).suggestedFilename()).toBe("assignment.txt");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: testInfo.outputPath("campus-hub.png"),
    fullPage: true,
  });
});

test("Campus Hub is independent and PlacementOS is restricted to senior students", async ({
  page,
  isMobile,
}) => {
  await login(page, "JUNIOR");
  await expect(page.locator(".breadcrumbs")).toContainText("Campus Hub");
  if (isMobile)
    await page
      .getByRole("button", { name: "Open navigation", exact: true })
      .click();
  const nav = page.getByRole("navigation", { name: "Workspace navigation" });
  await expect(
    nav.getByRole("link", { name: "Campus Hub", exact: true }),
  ).toBeVisible();
  await expect(
    nav.getByRole("link", { name: "Open PlacementOS", exact: true }),
  ).toHaveCount(0);
  await expect(
    nav.getByRole("link", { name: "Recruitment drives", exact: true }),
  ).toHaveCount(0);
  expect((await page.request.get("/api/drives")).status()).toBe(403);
  expect((await page.request.get("/api/campus/posts")).status()).toBe(200);
  await page.goto("/app/drives");
  await expect(
    page.getByRole("heading", {
      name: "PlacementOS opens in third year",
      exact: true,
    }),
  ).toBeVisible();
  await page.goto("/app");
  await expect(page).toHaveURL(/\/app\/campus$/);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await login(page, "STUDENT");
  if (isMobile)
    await page
      .getByRole("button", { name: "Open navigation", exact: true })
      .click();
  await nav
    .getByRole("link", { name: "Open PlacementOS", exact: true })
    .click();
  await expect(page).toHaveURL(/\/app\/placement$/);
  await expect(page.locator(".breadcrumbs")).toContainText("PlacementOS");
  if (isMobile)
    await page
      .getByRole("button", { name: "Open navigation", exact: true })
      .click();
  await expect(
    nav.getByRole("link", { name: "Recruitment drives", exact: true }),
  ).toBeVisible();
  await nav.getByRole("link", { name: "Campus Hub", exact: true }).click();
  await expect(page.locator(".breadcrumbs")).toContainText("Campus Hub");
});
