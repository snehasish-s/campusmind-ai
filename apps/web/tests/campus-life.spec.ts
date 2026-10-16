import { test, expect, type Page } from "@playwright/test";
import { signIn } from "./auth";

async function login(page: Page, identifier: string) {
  await signIn(page, identifier);
  await expect(page).toHaveURL(
    identifier === "ADMIN" ? /\/app$/ : /\/app\/campus$/,
  );
}

async function csrf(page: Page) {
  return {
    "X-CSRF-Token": (await page.context().cookies()).find(
      (c) => c.name === "cm_csrf",
    )!.value,
  };
}

test("academic work, evidence passport, automation and fee payment journey", async ({
  page,
}, info) => {
  await login(page, "ADMIN");
  const department = (
    await (await page.request.get("/api/departments")).json()
  ).find((d: { code: string }) => d.code === "CSE");
  const section = info.project.name === "desktop" ? "LD" : "LM";
  const headers = await csrf(page);
  const preview = await page.request.post("/api/campus/imports/preview", {
    headers,
    multipart: {
      kind: "cohorts",
      file: {
        name: "life-cohort.csv",
        mimeType: "text/csv",
        buffer: Buffer.from(
          `roll_no,department,graduation_year,academic_year,semester,section\nSTUDENT,CSE,2027,4,7,${section}\n`,
        ),
      },
    },
  });
  expect(preview.ok()).toBeTruthy();
  const imported = await preview.json();
  expect(
    (
      await page.request.post(`/api/campus/imports/${imported.id}/confirm`, {
        headers,
      })
    ).ok(),
  ).toBeTruthy();
  const post = await page.request.post("/api/campus/posts", {
    headers,
    multipart: {
      payload: JSON.stringify({
        title: `SQL assignment ${section}`,
        message: "Explain a join and show the query result.",
        kind: "assignment",
        subject: "Database Systems",
        due_at: new Date(Date.now() + 20 * 3600000).toISOString(),
        audience: {
          department_id: department.id,
          graduation_year: 2027,
          academic_year: 4,
          semester: 7,
          section,
        },
      }),
    },
  });
  expect(post.ok()).toBeTruthy();
  const postId = (await post.json()).id;
  expect(
    (
      await page.request.put(`/api/campus/assignments/${postId}/policy`, {
        headers,
        data: {
          rubric: [
            { label: "Correctness", maximum: 60 },
            { label: "Explanation", maximum: 40 },
          ],
          skills: ["SQL"],
        },
      })
    ).ok(),
  ).toBeTruthy();
  await page.goto("/app/fees");
  await page
    .getByText("Create fee plan & issue invoices", { exact: true })
    .click();
  await page
    .getByLabel("Unique reference", { exact: true })
    .fill(`SYN-LIFE-${section}`);
  await page
    .getByLabel("Fee title", { exact: true })
    .fill(`Semester course fee ${section}`);
  await page.getByLabel("Term", { exact: true }).fill("2026–27 Semester 7");
  await page
    .getByLabel("Amount per student · INR", { exact: true })
    .fill("1250.50");
  const due = new Date(Date.now() + 2 * 86400000).toISOString().slice(0, 16);
  await page.getByLabel("Due date", { exact: true }).fill(due);
  await page
    .getByLabel("Individual registration number", { exact: true })
    .fill("STUDENT");
  await page
    .getByRole("button", { name: "Preview invoices", exact: true })
    .click();
  await expect(page.getByText(/1 students ·/)).toBeVisible();
  await page
    .getByRole("button", { name: "Confirm & issue invoices", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: `Semester course fee ${section}`,
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await login(page, "STUDENT");
  await page.goto("/app/today");
  await expect(
    page.getByRole("heading", { name: "Your action list" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: `SQL assignment ${section}`,
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Save timetable on this device", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Snapshot saved", exact: true }),
  ).toBeDisabled();
  await page.screenshot({ path: info.outputPath("today.png"), fullPage: true });
  await page.goto("/app/assignments");
  const assignment = page.locator("section").filter({
    has: page.getByRole("heading", {
      name: `SQL assignment ${section}`,
      exact: true,
    }),
  });
  await assignment
    .getByLabel("Your response", { exact: true })
    .fill(
      "SELECT s.name FROM students s INNER JOIN projects p ON p.student_id = s.id; This returns matching student and project rows.",
    );
  await assignment
    .getByRole("button", { name: "Submit assignment", exact: true })
    .click();
  await expect(
    assignment.getByText(/Synthetic Student · STUDENT · v1 · submitted/),
  ).toBeVisible();
  await page.goto("/app/fees");
  const invoice = page.locator("article").filter({
    has: page.getByRole("heading", {
      name: `Semester course fee ${section}`,
      exact: true,
    }),
  });
  await invoice
    .getByRole("button", { name: "Review test payment", exact: true })
    .click();
  await invoice
    .getByRole("button", { name: "Confirm test payment", exact: true })
    .click();
  await expect(
    invoice.getByRole("link", { name: "Download test receipt" }),
  ).toBeVisible();
  const download = page.waitForEvent("download");
  await invoice.getByRole("link", { name: "Download test receipt" }).click();
  expect((await download).suggestedFilename()).toMatch(/^TEST-.*\.txt$/);
  await page.screenshot({ path: info.outputPath("fees.png"), fullPage: true });
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await login(page, "ADMIN");
  await page.goto("/app/assignments");
  const review = page.locator("section").filter({
    has: page.getByRole("heading", {
      name: `SQL assignment ${section}`,
      exact: true,
    }),
  });
  await review
    .locator("summary")
    .filter({ hasText: "Synthetic Student · STUDENT · v1" })
    .click();
  await review
    .getByRole("spinbutton", {
      name: "Correctness marks for STUDENT",
      exact: true,
    })
    .fill("55");
  await review
    .getByRole("spinbutton", {
      name: "Explanation marks for STUDENT",
      exact: true,
    })
    .fill("35");
  await review
    .getByLabel("Feedback", { exact: true })
    .fill("Correct join and a clear explanation of matching keys.");
  await review
    .getByLabel("Verify mapped skills from this work", { exact: false })
    .check();
  await review
    .getByRole("button", { name: "Save review & notify student", exact: true })
    .click();
  await expect(review.getByText(/v1 · graded · 90\/100/)).toBeVisible();
  await page.goto("/app/automations");
  await page
    .getByRole("button", { name: "Run a reminder sweep", exact: true })
    .click();
  await expect(
    page.getByText("Reminder sweep finished", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await login(page, "STUDENT");
  await page.goto("/app/passport");
  await expect(
    page.getByText("faculty verified", { exact: true }).first(),
  ).toBeVisible();
  await page
    .getByRole("checkbox", { name: "Share SQL evidence", exact: true })
    .first()
    .check();
  await page
    .getByLabel("I consent to sharing my selected evidence and name.")
    .check();
  await page
    .getByRole("button", { name: "Create share link (1 selected)" })
    .click();
  const url = await page
    .getByRole("textbox", { name: "Passport share URL" })
    .inputValue();
  expect(url).toContain("/share/");
  await page.screenshot({
    path: info.outputPath("passport.png"),
    fullPage: true,
  });
  const guest = await page.context().browser()!.newContext();
  const shared = await guest.newPage();
  await shared.goto(url);
  await expect(
    shared.getByRole("heading", { name: "Synthetic Student", exact: true }),
  ).toBeVisible();
  await expect(
    shared.getByText("Recorded score: 90%", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Revoke link", exact: true })
    .first()
    .click();
  await shared.reload();
  await expect(
    shared.getByText("This share is invalid, revoked or expired."),
  ).toBeVisible();
  await guest.close();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth + 1,
  );
  expect(overflow).toBeFalsy();
});

test("junior student can use campus academics and an explicitly saved offline timetable", async ({
  page,
  context,
}, info) => {
  await login(page, "ADMIN");
  const headers = await csrf(page);
  const suffix = info.project.name === "desktop" ? "OD" : "OM";
  const cohorts = await page.request.post("/api/campus/imports/preview", {
    headers,
    multipart: {
      kind: "cohorts",
      file: {
        name: "junior-cohort.csv",
        mimeType: "text/csv",
        buffer: Buffer.from(
          `roll_no,department,graduation_year,academic_year,semester,section\nJUNIOR,CSE,2029,2,3,${suffix}\n`,
        ),
      },
    },
  });
  expect(cohorts.ok()).toBeTruthy();
  expect(
    (
      await page.request.post(
        `/api/campus/imports/${(await cohorts.json()).id}/confirm`,
        { headers },
      )
    ).ok(),
  ).toBeTruthy();
  const start = info.project.name === "desktop" ? "15:00" : "16:00";
  const end = info.project.name === "desktop" ? "16:00" : "17:00";
  const from = new Date().toISOString().slice(0, 10),
    until = new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10);
  const timetable = `department,graduation_year,academic_year,semester,section,subject,teacher_roll_no,weekday,starts,ends,room,valid_from,valid_until\nCSE,2029,2,3,${suffix},Offline Database Lab,TEACHER,4,${start},${end},Room-${suffix},${from},${until}\n`;
  const preview = await page.request.post("/api/campus/imports/preview", {
    headers,
    multipart: {
      kind: "timetable",
      file: {
        name: "junior-timetable.csv",
        mimeType: "text/csv",
        buffer: Buffer.from(timetable),
      },
    },
  });
  expect(preview.ok()).toBeTruthy();
  expect(
    (
      await page.request.post(
        `/api/campus/imports/${(await preview.json()).id}/confirm`,
        { headers },
      )
    ).ok(),
  ).toBeTruthy();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await login(page, "JUNIOR");
  await page.goto("/app/today");
  await page
    .getByRole("button", { name: "Save timetable on this device", exact: true })
    .click();
  await page.goto("/offline");
  await expect(
    page.getByRole("heading", { name: "Offline Database Lab", exact: true }),
  ).toBeVisible();
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });
  await context.setOffline(true);
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Your offline timetable", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Offline Database Lab", exact: true }),
  ).toBeVisible();
  await context.setOffline(false);
  await page.goto("/app/campus");
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/offline");
  await expect(
    page.getByText(/No timetable was saved on this device/),
  ).toBeVisible();
});
