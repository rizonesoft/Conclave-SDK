import {build} from 'esbuild';
const base={bundle:true,platform:'node',format:'esm',banner:{js:"import { createRequire } from 'node:module'; const require = createRequire(import.meta.url);"}};
await build({...base,entryPoints:['src/server.js'],outfile:'dist/server.mjs'});
await build({...base,entryPoints:['scripts/probe.mjs'],outfile:'dist/probe.mjs'});