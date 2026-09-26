import { spawn, execFileSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const repository = path.dirname(root);
const data = process.env.STYL_E2E_DATA_DIR;
if (!data || !path.basename(data).startsWith("styl-e2e-") || !process.env.STYL_E2E_TOKEN) {
  throw new Error("Run through the Playwright config, which creates isolated test data.");
}
mkdirSync(data, { recursive: true });
const python = process.env.STYL_TEST_PYTHON ?? path.join(repository, ".venv", process.platform === "win32" ? "Scripts\\python.exe" : "bin/python");
if (!existsSync(python)) throw new Error("Set STYL_TEST_PYTHON to an interpreter with backend requirements installed.");
const ffmpeg = execFileSync(python, ["-c", "from imageio_ffmpeg import get_ffmpeg_exe; print(get_ffmpeg_exe())"], { encoding: "utf8" }).trim();
execFileSync(ffmpeg, [
  "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
  "-f", "lavfi", "-i", "testsrc2=size=160x96:rate=24",
  "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
  "-t", "4", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", path.join(data, "clip.mov"),
]);
const child = spawn(python, ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8102"], {
  cwd: path.join(repository, "backend"), stdio: "inherit",
  env: {
    ...process.env, STYL_DATA_DIR: data, STYL_ADMIN_TOKEN: process.env.STYL_E2E_TOKEN,
    STYL_ALLOWED_ORIGINS: "http://127.0.0.1:3102", STYL_SMTP_HOST: "",
    STYL_SMTP_USERNAME: "", STYL_SMTP_PASSWORD: "",
  },
});
child.on("error", (error) => { console.error(error); process.exitCode = 1; });
child.on("exit", (code) => {
  rmSync(data, { recursive: true, force: true });
  process.exit(code ?? 0);
});
for (const signal of ["SIGTERM", "SIGINT"]) process.on(signal, () => child.kill(signal));
