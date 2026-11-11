import { Resvg } from '@resvg/resvg-js';
import { readFileSync, writeFileSync } from 'node:fs';
const source = new URL('../assets/icon.svg', import.meta.url);
const output = new URL('../assets/icon.png', import.meta.url);
writeFileSync(output, new Resvg(readFileSync(source), { fitTo: { mode: 'width', value: 512 } }).render().asPng());
