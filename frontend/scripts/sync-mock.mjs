// Copy the saved API responses into public/mock so the dashboard works with the API stopped.
import { cpSync, existsSync, rmSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const from = resolve(here, "../../data/demo/api_snapshots");
const to = resolve(here, "../public/mock");
if (!existsSync(from)) {
  console.warn("mock:sync: no snapshots at", from, "(run `python -m sol_ml.snapshots` in ml/)");
} else {
  rmSync(to, { recursive: true, force: true });
  cpSync(from, to, { recursive: true });
  console.log("mock:sync: copied snapshots to public/mock");
}
