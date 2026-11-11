// Extract the largest embedded PNG byte-for-byte from the official website ICO.
import fs from 'node:fs';
const ico=fs.readFileSync(new URL('../assets/domains-official.ico',import.meta.url));
const frames=[];
for(let i=0;i<ico.readUInt16LE(4);i++){const o=6+16*i;frames.push({size:(ico[o]||256)*(ico[o+1]||256),length:ico.readUInt32LE(o+8),offset:ico.readUInt32LE(o+12)});}
const frame=frames.sort((a,b)=>b.size-a.size)[0];
const png=ico.subarray(frame.offset,frame.offset+frame.length);
if(png.subarray(0,8).toString('hex')!=='89504e470d0a1a0a')throw new Error('Largest favicon frame is not PNG');
fs.writeFileSync(new URL('../assets/icon.png',import.meta.url),png);
