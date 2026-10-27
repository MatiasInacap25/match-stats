// Copies contract/example/ into site/public/data/ so the site runs locally
// without the nightly job. Local development only: never commit public/data.
import { cp, rm } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const source = fileURLToPath(new URL("../../contract/example/", import.meta.url));
const target = fileURLToPath(new URL("../public/data/", import.meta.url));

await rm(target, { recursive: true, force: true });
await cp(source, target, { recursive: true });
console.log(`Copied example data to ${target}`);
