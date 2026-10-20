// Empties out/ before tsc compiles into it: tsc never deletes the output of a source file that was removed, so a
// deleted test would otherwise keep running from its stale .js. out/ is generated and holds no links; this runs in
// standalone Node, whose rmSync removes a link without following it (unlike VS Code's runtime, D02 T01 §20).
import { rmSync } from "node:fs";

rmSync(new URL("./out/", import.meta.url), { recursive: true, force: true });
