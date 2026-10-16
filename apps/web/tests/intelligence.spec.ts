import { test, expect, type Page } from "@playwright/test";
import path from "node:path";

async function login(page: Page, id = "ADMIN") {
  await page.goto("/login");
  await page
    .getByLabel("Institution code", { exact: true })
    .fill(process.env.CM_E2E_INSTITUTION!);
  await page.getByLabel("Roll number or staff email").fill(id);
  await page
    .getByLabel("Password", { exact: true })
    .fill(process.env.CM_E2E_PASSWORD!);
  await page.getByRole("button", { name: "Sign in securely" }).click();
  await expect(page).toHaveURL(
    ["STUDENT", "TEACHER", "JUNIOR"].includes(id) ? /\/app\/campus$/ : /\/app$/,
  );
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

test("approved assessment, skill review, adaptive roadmap and officer analytics", async ({
  page,
  isMobile,
}, testInfo) => {
  test.setTimeout(120000);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await login(page, "PLACEMENT");
  await navigate(page, "Assessments", isMobile);
  const studio = page
    .locator("details")
    .filter({
      has: page.locator("summary", {
        hasText: "Question bank & assessment studio",
      }),
    })
    .first();
  await studio.locator("summary").first().click();
  await studio
    .getByRole("button", { name: "Suggest draft practice questions" })
    .click();
  await expect(
    page.getByText(
      "Draft suggestions saved. Review every answer and explanation before approving.",
    ),
  ).toBeVisible();
  for (let i = 0; i < 2; i++) {
    await studio
      .getByRole("button", { name: "Approve question", exact: true })
      .first()
      .click();
    await expect(
      studio.getByRole("button", { name: "Approve question", exact: true }),
    ).toHaveCount(1 - i);
  }
  const checks = studio.locator(
    '.evidence-list input[type="checkbox"]:enabled',
  );
  for (let i = 0; i < (await checks.count()); i++) await checks.nth(i).check();
  const title = `SQL foundations · ${testInfo.project.name}`;
  await studio.getByLabel("Assessment title", { exact: true }).fill(title);
  await studio
    .getByRole("button", { name: /Publish \d+ selected questions/ })
    .click();
  await expect(
    page.getByText("Assessment published", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await login(page, "STUDENT");
  await navigate(page, "My resume", isMobile);
  await page
    .getByLabel("Choose resume")
    .setInputFiles(path.resolve("../../data/browser-resume.docx"));
  await page.getByRole("button", { name: "Upload new version" }).click();
  await expect(
    page.getByText("Resume uploaded. A new version has been saved."),
  ).toBeVisible();
  await navigate(page, "My skills", isMobile);
  await page.getByRole("button", { name: "Analyze latest resume" }).click();
  await expect(
    page.getByText("Resume analysis saved for your review"),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Python", exact: true }).first(),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Confirm claim", exact: true })
    .first()
    .click();
  await navigate(page, "My career roadmap", isMobile);
  await page
    .getByRole("button", { name: "Propose roadmap", exact: true })
    .click();
  await expect(
    page.getByText("Your roadmap proposal is ready", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Accept this plan", exact: true })
    .first()
    .click();
  await expect(
    page.getByText("Roadmap accepted; completed work preserved", {
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Mark complete", exact: true })
    .and(page.locator(":enabled"))
    .first()
    .click();
  await expect(page.getByText("Progress saved", { exact: true })).toBeVisible();
  await navigate(page, "Mock tests", isMobile);
  const assessment = page
    .locator("article")
    .filter({ has: page.getByRole("heading", { name: title, exact: true }) });
  await assessment.getByRole("button", { name: "Start or resume" }).click();
  const questions = page.locator("fieldset.assessment-question");
  await expect(questions.first()).toBeVisible();
  for (let i = 0; i < (await questions.count()); i++) {
    const question = questions.nth(i);
    const where = question.getByLabel("WHERE", { exact: true });
    if (await where.count()) await where.check();
    else await question.getByLabel("LEFT JOIN", { exact: true }).check();
  }
  await page.getByRole("button", { name: "Save answers", exact: true }).click();
  await expect(page.getByText("Answers saved", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Submit assessment", exact: true })
    .click();
  await expect(
    page.getByText("Objective score: 100", { exact: true }),
  ).toBeVisible();
  await navigate(page, "My career roadmap", isMobile);
  await expect(
    page.getByText(/Triggered by assessment completed/).first(),
  ).toBeVisible();
  await expect(
    page.getByText("Completed work preserved", { exact: true }).first(),
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("adaptive-roadmap.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBeTruthy();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await login(page, "PLACEMENT");
  await navigate(page, "Placement analytics", isMobile);
  await page
    .getByRole("button", { name: "Synthetic Student", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Synthetic Student · preparation detail",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Evidence coverage matrix" }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("CollegeOps upload, human approval, requirement mapping and cited retrieval", async ({
  page,
  isMobile,
}, testInfo) => {
  await login(page);
  await navigate(page, "CollegeOps", isMobile);
  await page
    .locator("summary", { hasText: "Upload evidence or a new version" })
    .click();
  const title = `Synthetic faculty workshop · ${testInfo.project.name}`;
  await page.getByLabel("Document title", { exact: true }).fill(title);
  await page
    .getByLabel("PDF, DOCX or UTF-8 TXT · up to 8 MB", { exact: true })
    .setInputFiles({
      name: `workshop-${testInfo.project.name}.txt`,
      mimeType: "text/plain",
      buffer: Buffer.from(
        `Synthetic ${testInfo.project.name} faculty database workshop report. The fictional CSE department conducted database development training.`,
      ),
    });
  await page
    .getByRole("button", { name: "Upload & index", exact: true })
    .click();
  await expect(
    page.getByText("Evidence uploaded and indexed", { exact: true }),
  ).toBeVisible();
  const row = page.locator("article.evidence-row").filter({
    has: page.getByRole("link", { name: `${title} · v1`, exact: true }),
  });
  await row
    .getByRole("button", { name: "Approve source", exact: true })
    .click();
  await expect(
    page.getByText("Evidence approved", { exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Evidence question", { exact: true })
    .fill("faculty database workshop");
  await page
    .getByRole("button", { name: "Find evidence", exact: true })
    .click();
  await expect(
    page.locator("a.source-chip").filter({ hasText: title }).first(),
  ).toBeVisible();
  await page
    .locator("summary", { hasText: "Define a requirement & map evidence" })
    .click();
  await page
    .getByLabel("Requirement title", { exact: true })
    .fill(`Faculty development · ${testInfo.project.name}`);
  await page
    .getByLabel("Institution-specific description", { exact: true })
    .fill(
      "Synthetic institution-defined requirement to retain faculty workshop evidence.",
    );
  await page.getByLabel(title, { exact: true }).check();
  await page
    .getByRole("button", { name: "Save requirement mapping", exact: true })
    .click();
  await expect(
    page.getByText("Requirement saved", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("evidence available", { exact: true }).first(),
  ).toBeVisible();
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page
      .getByRole("link", { name: "Export draft report", exact: true })
      .click(),
  ]);
  expect(download.suggestedFilename()).toBe("draft-evidence-report.csv");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: testInfo.outputPath("collegeops-evidence.png"),
    fullPage: true,
  });
});
