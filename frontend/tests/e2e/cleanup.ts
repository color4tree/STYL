import { rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

export default function cleanup() {
  const data = process.env.STYL_E2E_DATA_DIR;
  if (data && path.dirname(data) === tmpdir() && path.basename(data).startsWith("styl-e2e-")) {
    rmSync(data, { recursive: true, force: true, maxRetries: 5 });
  }
}
