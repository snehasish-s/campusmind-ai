import { cpSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const target = join(root, ".next", "standalone");
if (!existsSync(join(target, "server.js"))) {
  throw new Error("Build CampusMind first with npm run build.");
}
mkdirSync(join(target, ".next"), { recursive: true });
cpSync(join(root, ".next", "static"), join(target, ".next", "static"), {
  recursive: true,
});
if (existsSync(join(root, "public")))
  cpSync(join(root, "public"), join(target, "public"), { recursive: true });
const server = spawn(process.execPath, [join(target, "server.js")], {
  cwd: root,
  stdio: "inherit",
  env: {
    ...process.env,
    HOSTNAME: process.env.CM_HOSTNAME || "0.0.0.0",
    PORT: process.env.PORT || "3000",
  },
});
for (const signal of ["SIGINT", "SIGTERM"])
  process.on(signal, () => server.kill(signal));
server.on("exit", (code) => process.exit(code ?? 1));
