// Runs before `astro build` on Vercel. Rebuilds site/public/data with the
// Python `matchstats` CLI. If anything fails, the committed data is kept and
// the build goes on, so a bad download never takes the site down.
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { delimiter, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const siteDir = resolve(fileURLToPath(import.meta.url), "..", "..");
const srcDir = resolve(siteDir, "..", "src");
const depsDir = resolve(siteDir, ".pydeps");
const outDir = resolve(siteDir, "public", "data");
const cacheDir = resolve(siteDir, ".raw-cache");

function run(cmd, args, env = {}) {
  const r = spawnSync(cmd, args, { stdio: "inherit", env: { ...process.env, ...env } });
  return r.status === 0;
}

function keepCommittedData(reason) {
  console.warn(`[refresh-data] ${reason}. Keeping the committed data in site/public/data.`);
  process.exit(0);
}

if (!existsSync(srcDir)) {
  keepCommittedData(
    "../src is not available (enable 'Include files outside the root directory' in Vercel)",
  );
}

const python = ["python3", "python"].find((p) => run(p, ["--version"]));
if (!python) keepCommittedData("Python is not available in this build");

if (!run(python, ["-m", "pip", "install", "--quiet", "--target", depsDir, "numpy>=2", "scipy>=1.14"])) {
  keepCommittedData("could not install numpy/scipy");
}

const pythonPath = [srcDir, depsDir].join(delimiter);
if (!run(python, ["-m", "matchstats.cli", "build", "--out", outDir, "--cache", cacheDir], { PYTHONPATH: pythonPath })) {
  keepCommittedData("matchstats build failed");
}

console.log("[refresh-data] data refreshed");
