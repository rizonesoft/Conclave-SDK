import {Resvg} from '@resvg/resvg-js';
import {readFile,writeFile} from 'node:fs/promises';
await writeFile('assets/icon.png',new Resvg(await readFile('assets/icon.svg'),{fitTo:{mode:'width',value:180}}).render().asPng());
