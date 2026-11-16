// Copies the mobile web app (server/app/web, the single source) into www/ for the Android build.
import { cpSync, rmSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const src = join(here, "..", "server", "app", "web");
const out = join(here, "www");
rmSync(out, { recursive: true, force: true });
mkdirSync(out);
cpSync(src, out, { recursive: true, filter: (p) => !p.endsWith("sw.js") }); // pages are inside the APK: no service worker
console.log("copied", src, "->", out);
