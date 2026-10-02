import { existsSync, lstatSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { tmpdir } from "node:os";
import path from "node:path";
import { setTimeout as delay } from "node:timers/promises";

function running(pid: number): boolean {
  try { process.kill(pid, 0); return true; }
  catch (error) {
    if (error instanceof Error && "code" in error && error.code === "ESRCH") return false;
    throw error;
  }
}

export default async function cleanup() {
  const data = process.env.STYL_E2E_DATA_DIR;
  const token = process.env.STYL_E2E_TOKEN;
  if (!data || !token || path.dirname(data) !== tmpdir() || !path.basename(data).startsWith("styl-e2e-")) {
    throw new Error("Refusing cleanup outside the isolated test fixture.");
  }
  if (!existsSync(data)) return;
  if (lstatSync(data).isSymbolicLink()) throw new Error("Refusing cleanup of a linked fixture directory.");
  const ownerFile = path.join(data, "api-process.json");
  if (existsSync(ownerFile)) {
    const owner: unknown = JSON.parse(readFileSync(ownerFile, "utf8"));
    if (typeof owner !== "object" || owner === null || !("pid" in owner) || !Number.isSafeInteger(owner.pid)
        || typeof owner.pid !== "number" || owner.pid <= 0 || !("directory" in owner) || owner.directory !== data
        || !("ownerHash" in owner) || owner.ownerHash !== createHash("sha256").update(token).digest("hex")) {
      throw new Error("Test API ownership does not match; no process or data was touched.");
    }
    if (running(owner.pid)) {
      const response = await fetch("http://127.0.0.1:8102/api/admin/verify", {
        headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(5000),
      });
      if (!response.ok) throw new Error("Cannot verify isolated API ownership before shutdown.");
      writeFileSync(path.join(data, "stop.request"), "", { flag: "wx" });
      process.kill(owner.pid, "SIGTERM");
      const deadline = Date.now() + 10000;
      while (running(owner.pid) && Date.now() < deadline) await delay(50);
      if (running(owner.pid)) throw new Error("Test API is still running; private fixture retained for review.");
    }
  }
  // Stop the owned writer before deleting SQLite files; global teardown precedes webServer shutdown.
  rmSync(data, { recursive: true, force: true, maxRetries: 5 });
}
