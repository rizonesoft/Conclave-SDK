import { build } from "esbuild";
import { Resvg } from "@resvg/resvg-js";
import { readFile, writeFile } from "node:fs/promises";
for (const [input, output] of [
  ["src/server.js", "dist/server.mjs"],
  ["scripts/setup.mjs", "dist/setup.mjs"],
])
  await build({
    entryPoints: [input],
    outfile: output,
    bundle: true,
    platform: "node",
    format: "esm",
    banner: {
      js: "import { createRequire } from 'node:module'; const require = createRequire(import.meta.url);",
    },
  });
await writeFile(
  "assets/icon.png",
  new Resvg(await readFile("assets/icon.svg"), {
    fitTo: { mode: "width", value: 256 },
  })
    .render()
    .asPng(),
);
