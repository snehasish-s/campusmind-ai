import { randomBytes } from "node:crypto";
import { execFileSync } from "node:child_process";
import path from "node:path";
export default function setup() {
  process.env.CM_E2E_PASSWORD = randomBytes(24).toString("base64url");
  process.env.CM_E2E_INSTITUTION = `browser-${Date.now()}`;
  const root = path.resolve("../..");
  const python =
    process.env.CM_PYTHON ||
    path.join(
      root,
      process.platform === "win32"
        ? ".venv/Scripts/python.exe"
        : ".venv/bin/python",
    );
  execFileSync(python, ["scripts/browser_seed.py"], {
    cwd: root,
    env: process.env,
    stdio: "pipe",
  });
}
