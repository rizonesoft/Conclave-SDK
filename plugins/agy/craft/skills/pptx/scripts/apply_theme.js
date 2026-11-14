// Give a deck pptxgenjs wrote its own theme colors and theme name. pptxgenjs sets the theme's
// two fonts (pres.theme) but hard-codes Office's palette, so scheme colors resolve to Office
// blue and orange until the deck's colors are written into ppt/theme/theme1.xml.
//
//   const { applyTheme } = require("<this skill's directory>/scripts/apply_theme.js");
//   await pres.writeFile({ fileName: "deck.pptx" });
//   await applyTheme("deck.pptx", {
//     name: "Northwind",
//     colors: { dk1, lt1, dk2, lt2, accent1, accent2, accent3, accent4, accent5, accent6, hlink, folHlink },
//   });   // extra keys (headFontFace, ...) are ignored, and the twelve colors may sit beside name instead
//
//   node scripts/apply_theme.js deck.pptx theme.json [out.pptx]     # the same, from a shell
//
// Colors are six hex digits, no "#". The deck is rewritten in place unless a third argument
// names another file. It throws, changing nothing, if a color anywhere in the deck is not six
// hex digits, which is what a scheme color passed to a hex-only option turns into.
//
// As the step that rewrites the deck after pres.writeFile(), it also handles two faults pptxgenjs writes
// that make PowerPoint offer to repair the deck: it mends <c:crossesAt val="autoZero"/>, and it
// throws on a line dash that is not a dash style.
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const MAX_ARCHIVE_ENTRIES = 10000;
const MAX_MEMBER_BYTES = 128 * 1024 * 1024;
const MAX_ARCHIVE_BYTES = 512 * 1024 * 1024;
const MAX_TMP_ATTEMPTS = 8;

function addAncestorPaths(startDir, out, seen) {
	if (!startDir) return;
	let current = path.resolve(startDir);
	while (true) {
		const nm = path.join(current, "node_modules");
		if (!seen.has(nm)) {
			seen.add(nm);
			out.push(nm);
		}
		if (!seen.has(current)) {
			seen.add(current);
			out.push(current);
		}
		const parent = path.dirname(current);
		if (parent === current) break;
		current = parent;
	}
}

function collectSearchPaths(extraPaths = []) {
	const paths = [];
	const seen = new Set();
	const pushRaw = (p) => {
		if (!p || seen.has(p)) return;
		seen.add(p);
		paths.push(p);
	};

	const extras = Array.isArray(extraPaths) ? extraPaths : [extraPaths];
	for (const p of extras) {
		if (typeof p === "string" && p.trim()) addAncestorPaths(p, paths, seen);
	}

	// Walk caller chain so requiring this helper from a globally deployed plugin still
	// resolves packages installed beside the caller script.
	const visitedMods = new Set();
	let mod = module.parent;
	while (mod && !visitedMods.has(mod)) {
		visitedMods.add(mod);
		if (mod.filename) addAncestorPaths(path.dirname(mod.filename), paths, seen);
		if (Array.isArray(mod.paths)) mod.paths.forEach(pushRaw);
		mod = mod.parent;
	}

	if (require.main && require.main.filename) {
		addAncestorPaths(path.dirname(require.main.filename), paths, seen);
		if (Array.isArray(require.main.paths)) require.main.paths.forEach(pushRaw);
	}

	if (process.argv[1]) {
		addAncestorPaths(path.dirname(path.resolve(process.argv[1])), paths, seen);
	}

	for (const cachedKey of Object.keys(require.cache || {})) {
		if (/[\\/]node_modules[\\/]pptxgenjs([\\/]|$)/i.test(cachedKey) || path.basename(cachedKey).toLowerCase().startsWith("pptxgen")) {
			addAncestorPaths(path.dirname(cachedKey), paths, seen);
			const cachedMod = require.cache[cachedKey];
			if (cachedMod && Array.isArray(cachedMod.paths)) cachedMod.paths.forEach(pushRaw);
		}
	}

	if (process.env.NODE_PATH) {
		for (const entry of process.env.NODE_PATH.split(path.delimiter)) {
			if (entry && entry.trim()) addAncestorPaths(entry.trim(), paths, seen);
		}
	}

	addAncestorPaths(process.cwd(), paths, seen);
	addAncestorPaths(__dirname, paths, seen);
	if (Array.isArray(module.paths)) module.paths.forEach(pushRaw);

	return paths;
}

// jszip comes with pptxgenjs but is not always installed where a bare require("jszip") finds
// it, so resolve pptxgenjs from caller, entry, cached, NODE_PATH, cwd, and plugin paths,
// then load jszip from beside pptxgenjs or from those same roots. Never searches beside deckPath.
function loadJSZip(extraPaths = []) {
	const searchPaths = collectSearchPaths(extraPaths);
	const jszipPaths = [];
	const jszipSeen = new Set();

	try {
		const pptxPath = require.resolve("pptxgenjs", { paths: searchPaths });
		addAncestorPaths(path.dirname(pptxPath), jszipPaths, jszipSeen);
		jszipSeen.add(pptxPath);
		jszipPaths.push(pptxPath);
	} catch {
		// Fall through to check whether jszip itself is directly resolvable on searchPaths.
	}

	for (const p of searchPaths) {
		if (!jszipSeen.has(p)) {
			jszipSeen.add(p);
			jszipPaths.push(p);
		}
	}

	try {
		return require(require.resolve("jszip", { paths: jszipPaths }));
	} catch {
		throw new Error(`pptxgenjs and the jszip that comes with it cannot be found from ${__filename} or caller/cwd search paths. Install pptxgenjs in your project directory or pass searchPaths/jszip options (or set NODE_PATH). Nothing was changed.`);
	}
}

function atomicWriteBuffer(targetPath, data, fsMod = fs) {
	const buf = Buffer.isBuffer(data) ? data : Buffer.from(data);
	const resolvedTarget = path.resolve(targetPath);
	const dir = path.dirname(resolvedTarget);
	const base = path.basename(resolvedTarget);

	if (typeof fsMod.mkdirSync === "function") {
		fsMod.mkdirSync(dir, { recursive: true });
	}

	let existingMode = null;
	if (typeof fsMod.statSync === "function") {
		try {
			existingMode = fsMod.statSync(resolvedTarget).mode & 0o777;
		} catch (err) {
			if (!err || err.code !== "ENOENT") throw err;
		}
	}

	const constants = fsMod.constants || fs.constants;
	const flags = constants.O_CREAT | constants.O_EXCL | constants.O_WRONLY;
	const openMode = existingMode !== null ? existingMode : 0o666;

	let tmpPath = null;
	let fd = null;
	for (let attempt = 0; attempt < MAX_TMP_ATTEMPTS; attempt++) {
		const suffix = crypto.randomBytes(6).toString("hex");
		const candidate = path.join(dir, `.${base}.${process.pid}.${suffix}.tmp`);
		try {
			fd = fsMod.openSync(candidate, flags, openMode);
			tmpPath = candidate;
			break;
		} catch (err) {
			if (err && err.code === "EEXIST" && attempt + 1 < MAX_TMP_ATTEMPTS) continue;
			throw err;
		}
	}

	let tmpUnlinked = false;
	try {
		let offset = 0;
		while (offset < buf.length) {
			const written = fsMod.writeSync(fd, buf, offset, buf.length - offset);
			if (!Number.isInteger(written) || written <= 0) {
				throw new Error(`Short write to temporary file ${tmpPath}. Nothing was changed.`);
			}
			offset += written;
		}
		if (typeof fsMod.fsyncSync === "function") {
			fsMod.fsyncSync(fd);
		}
		fsMod.closeSync(fd);
		fd = null;

		if (existingMode !== null && typeof fsMod.chmodSync === "function") {
			fsMod.chmodSync(tmpPath, existingMode);
		}
		fsMod.renameSync(tmpPath, resolvedTarget);
		tmpUnlinked = true;
	} finally {
		// Best-effort rollback cleanup so the primary write error is not masked.
		if (fd !== null) {
			try { fsMod.closeSync(fd); } catch {}
		}
		if (tmpPath && !tmpUnlinked) {
			try { fsMod.unlinkSync(tmpPath); } catch {}
		}
	}
}

async function readXmlBounded(entry, name, budget) {
	const declaredSize = entry && entry._data && entry._data.uncompressedSize;
	if (typeof declaredSize === "number" && (declaredSize < 0 || declaredSize > MAX_MEMBER_BYTES)) {
		throw new Error(`${shown(name)} exceeds member size budget (${MAX_MEMBER_BYTES} bytes). Nothing was changed.`);
	}

	let buf;
	if (entry && typeof entry.nodeStream === "function") {
		buf = await new Promise((resolve, reject) => {
			const chunks = [];
			let memberBytes = 0;
			let settled = false;
			const stream = entry.nodeStream();
			const fail = (err) => {
				if (settled) return;
				settled = true;
				if (typeof stream.destroy === "function") stream.destroy();
				reject(err);
			};
			stream.on("data", (chunk) => {
				if (settled) return;
				const b = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
				memberBytes += b.length;
				if (memberBytes > MAX_MEMBER_BYTES) {
					fail(new Error(`${shown(name)} exceeds member size budget (${MAX_MEMBER_BYTES} bytes). Nothing was changed.`));
					return;
				}
				if (budget.total + memberBytes > MAX_ARCHIVE_BYTES) {
					fail(new Error(`Archive unpacked XML exceeds size budget (${MAX_ARCHIVE_BYTES} bytes). Nothing was changed.`));
					return;
				}
				chunks.push(b);
			});
			stream.on("error", fail);
			stream.on("end", () => {
				if (settled) return;
				settled = true;
				resolve(Buffer.concat(chunks, memberBytes));
			});
		});
		budget.total += buf.length;
		return buf.toString("utf8");
	}

	if (entry && typeof entry.async === "function") {
		try {
			const raw = await entry.async("nodebuffer");
			buf = Buffer.isBuffer(raw) ? raw : Buffer.from(raw);
		} catch {
			buf = Buffer.from(await entry.async("string"), "utf8");
		}
		if (buf.length > MAX_MEMBER_BYTES) {
			throw new Error(`${shown(name)} exceeds member size budget (${MAX_MEMBER_BYTES} bytes). Nothing was changed.`);
		}
		budget.total += buf.length;
		if (budget.total > MAX_ARCHIVE_BYTES) {
			throw new Error(`Archive unpacked XML exceeds size budget (${MAX_ARCHIVE_BYTES} bytes). Nothing was changed.`);
		}
		return buf.toString("utf8");
	}

	throw new Error(`${shown(name)} cannot be read from ZIP entry. Nothing was changed.`);
}

const SLOTS = ["dk1", "lt1", "dk2", "lt2", "accent1", "accent2", "accent3", "accent4", "accent5", "accent6", "hlink", "folHlink"];
// A name or value from the deck, for an error a model reads: quoted, cut, and with nothing unprintable left raw.
const shown = (s) => JSON.stringify(String(s).slice(0, 80)).replace(/[\p{C}\u2028\u2029]/gu, (c) => "\\u{" + c.codePointAt(0).toString(16) + "}");
const DASHES = ["solid", "dot", "dash", "lgDash", "dashDot", "lgDashDot", "lgDashDotDot", "sysDash", "sysDot", "sysDashDot", "sysDashDotDot"];

function themeXml(xml, theme) {
	if (!theme || !theme.name) throw new Error("theme.name is required. Nothing was changed.");
	// The name goes into XML attributes: drop control characters, escape & < > and the double quote.
	const name = String(theme.name).replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
	const colors = theme.colors || theme; // { name, colors: {...} }, or flat { name, dk1, ... }
	for (const k of SLOTS) {
		if (!/^[0-9A-Fa-f]{6}$/.test(String(colors[k]))) throw new Error(`theme.colors.${k} is ${JSON.stringify(colors[k])}; it must be six hex digits with no "#" (slots: ${SLOTS.join(" ")}). Nothing was changed.`);
	}
	const scheme = `<a:clrScheme name="${name}">` + SLOTS.map((k) => `<a:${k}><a:srgbClr val="${String(colors[k]).toUpperCase()}"/></a:${k}>`).join("") + "</a:clrScheme>";
	// Function replacements, so a "$" in the name is not read as a replacement pattern.
	// The theme, its color scheme and its font scheme each carry a name; none should still say Office.
	const out = xml
		.replace(/<a:clrScheme\b[\s\S]*?<\/a:clrScheme>/, () => scheme)
		.replace(/(<a:(?:theme|fontScheme)\b[^>]*?\bname=")[^"]*"/g, (_, head) => `${head}${name}"`);
	if (!out.includes(scheme)) throw new Error("ppt/theme/theme1.xml has no <a:clrScheme> to replace; this script expects the theme part pptxgenjs writes. Nothing was changed.");
	return out;
}

function readZip64MemberUncompressedSize(extraBuf, deckLabel) {
	let pos = 0;
	while (pos + 4 <= extraBuf.length) {
		const headerId = extraBuf.readUInt16LE(pos);
		const dataSize = extraBuf.readUInt16LE(pos + 2);
		pos += 4;
		if (pos + dataSize > extraBuf.length) break;
		if (headerId === 0x0001 && dataSize >= 8) {
			const val = extraBuf.readBigUInt64LE(pos);
			if (val > BigInt(MAX_MEMBER_BYTES)) {
				throw new Error(`${deckLabel} contains a member exceeding size budget (${MAX_MEMBER_BYTES} bytes). Nothing was changed.`);
			}
			return Number(val);
		}
		pos += dataSize;
	}
	throw new Error(`${deckLabel} has a malformed ZIP64 member size header. Nothing was changed.`);
}

function inspectZipBuffer(buf, deckLabel) {
	if (!Buffer.isBuffer(buf)) {
		throw new Error(`${deckLabel} is not a readable binary ZIP buffer. Nothing was changed.`);
	}
	if (buf.length > MAX_ARCHIVE_BYTES) {
		throw new Error(`${deckLabel} exceeds archive size budget (${MAX_ARCHIVE_BYTES} bytes). Nothing was changed.`);
	}
	if (buf.length < 22) {
		throw new Error(`${deckLabel} is not a valid ZIP archive. Nothing was changed.`);
	}

	let eocd = -1;
	const minEocd = Math.max(0, buf.length - 22 - 65535);
	for (let i = buf.length - 22; i >= minEocd; i--) {
		if (buf.readUInt32LE(i) === 0x06054b50 && i + 22 + buf.readUInt16LE(i + 20) === buf.length) {
			eocd = i;
			break;
		}
	}
	if (eocd < 0) {
		throw new Error(`${deckLabel} is missing a valid ZIP end-of-central-directory record. Nothing was changed.`);
	}

	const diskNum = buf.readUInt16LE(eocd + 4);
	const cdDisk = buf.readUInt16LE(eocd + 6);
	const diskEntries = buf.readUInt16LE(eocd + 8);
	let totalEntries = buf.readUInt16LE(eocd + 10);
	let cdSize = buf.readUInt32LE(eocd + 12);
	let cdOffset = buf.readUInt32LE(eocd + 16);
	let cdUpperBound = eocd;

	if (eocd >= 20 && buf.readUInt32LE(eocd - 20) === 0x07064b50) {
		const locDisk = buf.readUInt32LE(eocd - 16);
		const z64OffBig = buf.readBigUInt64LE(eocd - 12);
		const totalDisks = buf.readUInt32LE(eocd - 4);
		if (locDisk !== 0 || (totalDisks !== 1 && totalDisks !== 0)) {
			throw new Error(`${deckLabel} is an unsupported multi-disk ZIP64 archive. Nothing was changed.`);
		}
		if (z64OffBig > BigInt(eocd - 20 - 56)) {
			throw new Error(`${deckLabel} has an invalid ZIP64 central directory locator. Nothing was changed.`);
		}
		const z64Off = Number(z64OffBig);
		if (buf.readUInt32LE(z64Off) !== 0x06064b50) {
			throw new Error(`${deckLabel} has a malformed ZIP64 end-of-central-directory record. Nothing was changed.`);
		}
		const z64DiskNum = buf.readUInt32LE(z64Off + 16);
		const z64CdDisk = buf.readUInt32LE(z64Off + 20);
		const z64DiskEntries = buf.readBigUInt64LE(z64Off + 24);
		const z64TotalEntries = buf.readBigUInt64LE(z64Off + 32);
		const z64CdSize = buf.readBigUInt64LE(z64Off + 40);
		const z64CdOffset = buf.readBigUInt64LE(z64Off + 48);
		if (z64DiskNum !== 0 || z64CdDisk !== 0 || z64DiskEntries !== z64TotalEntries) {
			throw new Error(`${deckLabel} is an unsupported multi-disk ZIP64 archive. Nothing was changed.`);
		}
		if (z64TotalEntries > BigInt(MAX_ARCHIVE_ENTRIES)) {
			throw new Error(`${deckLabel} has ${z64TotalEntries.toString()} archive entries, exceeding limit ${MAX_ARCHIVE_ENTRIES}. Nothing was changed.`);
		}
		if (z64CdSize > BigInt(MAX_ARCHIVE_BYTES) || z64CdOffset + z64CdSize > BigInt(z64Off)) {
			throw new Error(`${deckLabel} has an out-of-bounds ZIP64 central directory. Nothing was changed.`);
		}
		totalEntries = Number(z64TotalEntries);
		cdSize = Number(z64CdSize);
		cdOffset = Number(z64CdOffset);
		cdUpperBound = z64Off;
	} else {
		if (
			diskNum !== 0 ||
			cdDisk !== 0 ||
			diskEntries !== totalEntries ||
			totalEntries === 0xffff ||
			cdSize === 0xffffffff ||
			cdOffset === 0xffffffff
		) {
			throw new Error(`${deckLabel} has an unsupported multi-disk or truncated ZIP directory. Nothing was changed.`);
		}
		if (totalEntries > MAX_ARCHIVE_ENTRIES) {
			throw new Error(`${deckLabel} has ${totalEntries} archive entries, exceeding limit ${MAX_ARCHIVE_ENTRIES}. Nothing was changed.`);
		}
	}

	if (cdOffset < 0 || cdSize < 0 || cdOffset + cdSize > cdUpperBound) {
		throw new Error(`${deckLabel} has an out-of-bounds ZIP central directory. Nothing was changed.`);
	}

	const cdEnd = cdOffset + cdSize;
	let ptr = cdOffset;
	let seenEntries = 0;
	let declaredTotal = 0;
	while (ptr < cdEnd) {
		if (ptr + 46 > cdEnd || buf.readUInt32LE(ptr) !== 0x02014b50) {
			throw new Error(`${deckLabel} has a malformed ZIP central directory entry. Nothing was changed.`);
		}
		seenEntries += 1;
		if (seenEntries > MAX_ARCHIVE_ENTRIES) {
			throw new Error(`${deckLabel} has more than ${MAX_ARCHIVE_ENTRIES} archive entries, exceeding limit ${MAX_ARCHIVE_ENTRIES}. Nothing was changed.`);
		}
		const uncompSize32 = buf.readUInt32LE(ptr + 24);
		const nameLen = buf.readUInt16LE(ptr + 28);
		const extraLen = buf.readUInt16LE(ptr + 30);
		const commentLen = buf.readUInt16LE(ptr + 32);
		const extAttr = buf.readUInt32LE(ptr + 38);
		const entryEnd = ptr + 46 + nameLen + extraLen + commentLen;
		if (entryEnd > cdEnd) {
			throw new Error(`${deckLabel} has a truncated ZIP central directory entry. Nothing was changed.`);
		}
		if (((extAttr >>> 16) & 0o170000) === 0o120000) {
			throw new Error(`${deckLabel} contains a symlink archive entry, which is not allowed. Nothing was changed.`);
		}
		const uncompSize = uncompSize32 === 0xffffffff
			? readZip64MemberUncompressedSize(buf.subarray(ptr + 46 + nameLen, ptr + 46 + nameLen + extraLen), deckLabel)
			: uncompSize32;
		if (uncompSize > MAX_MEMBER_BYTES) {
			throw new Error(`${deckLabel} contains a member exceeding size budget (${MAX_MEMBER_BYTES} bytes). Nothing was changed.`);
		}
		declaredTotal += uncompSize;
		if (declaredTotal > MAX_ARCHIVE_BYTES) {
			throw new Error(`${deckLabel} declared archive size exceeds budget (${MAX_ARCHIVE_BYTES} bytes). Nothing was changed.`);
		}
		ptr = entryEnd;
	}

	if (seenEntries !== totalEntries || ptr !== cdEnd) {
		throw new Error(`${deckLabel} central directory entry count does not match its header. Nothing was changed.`);
	}
}

async function applyTheme(deckPath, theme, outPathOrOptions = deckPath, maybeOptions = {}) {
	let outPath = deckPath;
	let options = maybeOptions || {};
	if (outPathOrOptions !== null && typeof outPathOrOptions === "object") {
		options = outPathOrOptions;
	} else if (outPathOrOptions) {
		outPath = outPathOrOptions;
	}

	const fsMod = options.fs || fs;
	const JSZip = options.jszip || loadJSZip(options.searchPaths);

	if (typeof fsMod.statSync === "function") {
		const deckSize = fsMod.statSync(deckPath).size;
		if (deckSize > MAX_ARCHIVE_BYTES) {
			throw new Error(`${deckPath} exceeds archive size budget (${MAX_ARCHIVE_BYTES} bytes). Nothing was changed.`);
		}
	}

	const rawDeck = fsMod.readFileSync(deckPath);
	inspectZipBuffer(rawDeck, deckPath);
	const zip = await JSZip.loadAsync(rawDeck);
	const entryNames = Object.keys(zip.files);
	if (entryNames.length > MAX_ARCHIVE_ENTRIES) {
		throw new Error(`${deckPath} has ${entryNames.length} archive entries, exceeding limit ${MAX_ARCHIVE_ENTRIES}. Nothing was changed.`);
	}

	const budget = { total: 0 };
	const part = "ppt/theme/theme1.xml"; // the one theme part pptxgenjs writes; the slide master and the notes master share it
	const themeEntry = zip.file(part);
	if (!themeEntry) throw new Error(`${deckPath} has no ${part}; this script is for decks pptxgenjs wrote. Nothing was changed.`);
	const updatedThemeXml = themeXml(await readXmlBounded(themeEntry, part, budget), theme);
	zip.file(part, updatedThemeXml);

	// A scheme color given to a hex-only option is written as <a:srgbClr val="bg2"/>, which is
	// not a color. pptxgenjs does not warn; stop here instead.
	for (const name of entryNames) {
		if (!name.endsWith(".xml") || (zip.files[name] && zip.files[name].dir)) continue;
		const xml = name === part ? updatedThemeXml : await readXmlBounded(zip.file(name), name, budget);
		const bad = xml.match(/<a:srgbClr val="((?![0-9A-Fa-f]{6}")[^"]*)"/);
		if (bad) throw new Error(`${shown(name)} has an <a:srgbClr> whose val is ${shown(bad[1])}, not six hex digits. Usually a scheme color was given to an option that takes hex only (valGridLine.color, catGridLine.color, shadow.color, or chartColors / invertedColors on a one-series bar chart). Pass the six-digit hex from your theme object there and rebuild. Nothing was changed.`);

		// pptxgenjs writes a dash option through unchecked, and an array as "solid,dash".
		const dash = [...xml.matchAll(/<a:prstDash val="([^"]*)"/g)].find((m) => !DASHES.includes(m[1].trim()));
		if (dash) throw new Error(`${shown(name)} has an <a:prstDash> whose val is ${shown(dash[1])}, which is not a dash style, and PowerPoint would offer to repair the deck. Give line.dashType, a chart's lineDash (one word for the whole chart, not an array), catAxisLineStyle or valAxisLineStyle one of: ${DASHES.join(" ")}. Then rebuild. Nothing was changed.`);

		// pptxgenjs writes valAxisCrossesAt: 0 as <c:crossesAt val="autoZero"/>. <c:crossesAt> takes
		// a number; the word belongs in <c:crosses>, where it means the same: cross at zero.
		if (xml.includes('<c:crossesAt val="autoZero"/>')) zip.file(name, xml.replaceAll('<c:crossesAt val="autoZero"/>', '<c:crosses val="autoZero"/>'));
	}
	// A ZIP entry for a folder ("ppt/slides/") is not a part, and pptxgenjs writes one per folder.
	// A cloud co-editing service reported issues editing decks that carry them. They are dropped
	// here for that reason, not to save space. (zip.remove() would take the folder's files too.)
	for (const name of Object.keys(zip.files)) if (zip.files[name].dir) delete zip.files[name];

	atomicWriteBuffer(outPath, await zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" }), fsMod);
}

module.exports = { applyTheme, atomicWriteBuffer, inspectZipBuffer, loadJSZip };

if (require.main === module) {
	const [deck, themeFile, out] = process.argv.slice(2);
	if (!deck || !themeFile) {
		console.error("usage: node apply_theme.js deck.pptx theme.json [out.pptx]");
		process.exit(2);
	}
	let theme;
	try {
		theme = JSON.parse(fs.readFileSync(themeFile, "utf8"));
	} catch (e) {
		console.error(`Error: cannot read ${themeFile} as JSON (${e.message}). Nothing was changed.`);
		process.exit(1);
	}
	applyTheme(deck, theme, out || deck).then(
		() => console.log(`Theme written to ${out || deck}`),
		(e) => { console.error(`Error: ${e.message}`); process.exit(1); }
	);
}
