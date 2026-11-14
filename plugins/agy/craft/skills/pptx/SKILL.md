---
name: pptx
description: "Use this skill any time a .pptx or .potx file is involved in any way: as input, output, or both. This includes: creating slide decks, pitch decks, or presentations as PowerPoint (.pptx) files; reading, parsing, or extracting text from any .pptx or .potx file (even if the extracted content will be used elsewhere, like in an email, summary, or new deck); editing, modifying, or updating existing presentations; combining or splitting slide files; working with templates (.potx), layouts, speaker notes, or comments."
license: Complete terms in LICENSE.txt
---

# PPTX creation, editing, and analysis

This skill covers producing `.pptx` files and reading, editing, templating, or converting existing `.pptx` and `.potx` files.

A `.pptx` is a ZIP archive of XML files. Choose your approach by task:

| Task | Approach |
|---|---|
| **Create** a new deck | Write a `pptxgenjs` script (see gotchas below) and build it as a [structured deck](#structured-decks) unless the user asks for a quick throwaway |
| **Edit** an existing deck, or build from a template | unzip -> edit `ppt/slides/slideN.xml` -> zip |
| **Read** content | `python scripts/slide_text.py deck.pptx` (one block per slide under `<!-- Slide number: N -->` markers); visual grid: `python scripts/thumbnail.py deck.pptx` |

## Scripts

Paths are relative to this skill's directory. Everything else is plain Python, `node`, or shell.

| Script | What it does |
|---|---|
| `scripts/slide_text.py deck.pptx` | Every slide's title, text, tables, chart data (scatter and bubble charts: series names only), picture alt text and speaker notes, as markdown. Reads `.potx` too |
| `scripts/thumbnail.py deck.pptx [prefix]` | Labeled grid of every slide, for picking template layouts. `.pptx` only. Pass `prefix`; it defaults to `thumbnails`, which overwrites the grids of any other deck done in the same directory |
| `scripts/add_slide.py unpacked/ slide2.xml [--after slideN.xml]` | Duplicate a slide (or a `slideLayoutN.xml`) with all the package bookkeeping. Also takes a `.pptx` directly with `-o out.pptx` |
| `scripts/clean.py unpacked/` | Delete slides, media, and rels no longer referenced. Run **after** `<p:sldIdLst>` is final |
| `scripts/apply_theme.js` | Node module: `const { applyTheme } = require("<this skill's directory>/scripts/apply_theme.js")`. `await applyTheme("deck.pptx", THEME)` after `pres.writeFile()` writes `THEME`'s colors and name (escaped for XML) into the deck's theme, for [structured decks](#structured-decks). Also a CLI: `node scripts/apply_theme.js deck.pptx theme.json` |
| `scripts/office/validate.py deck.pptx [--original src.pptx]` | Schema, relationship, content-type, chart and slide checks; each failure names its fix. Pass `--original` for any template-derived deck so it baselines schema checks against the template and does not confuse template XSD errors with yours |
| `scripts/office/soffice.py --headless --convert-to pdf deck.pptx` | LibreOffice wrapper; prevents headless `soffice` hangs and profile lock collisions |

## Creating with pptxgenjs: gotchas

Write the script and `require('pptxgenjs')` directly first. Only if that require fails, install `pptxgenjs` in the project directory or a scratch workspace in `R:\scratch`. The model knows the API; these are the footguns:

- **Set `pres.layout` before adding slides.** The default canvas is `LAYOUT_16x9` = **10" × 5.625"**, not 13.3" wide. Coordinates past the edge are written, not clamped: the shape just isn't on the slide. (`LAYOUT_WIDE` is 13.3" × 7.5".)
- **Hex colors: never `#`, never 8 digits.** `color: "FF0000"`. Both `"#FF0000"` and alpha baked into the hex (`"00000020"`) **corrupt the file**. For translucency: `transparency: 0-100` on fills and images, `opacity: 0.0-1.0` on shadows: each is silently ignored on the other.
- **pptxgenjs mutates option objects in place** (converts values to EMU on first use). Never share one `shadow`/options object across two `add*` calls: build a fresh object each time.
- **Shadow `offset` must be ≥ 0**: a negative offset corrupts the file. To cast a shadow upward, use `angle: 270` with a positive offset.
- **`letterSpacing` is silently ignored**: the real option is `charSpacing`.
- **Lists:** `bullet: true` on each item, never a literal `•` (renders double bullets). Set `breakLine: true` on every array item except the last. Space bulleted paragraphs with `paraSpaceAfter`, not `lineSpacing` (huge gaps).
- **One `new pptxgen()` per output file**: never reuse an instance.
- **`rectRadius` only works on `ROUNDED_RECTANGLE`**, not `RECTANGLE`.
- **Gradient fills aren't supported**: use a gradient image as the background instead.
- **Every `addText` call without a `placeholder` needs `isTextBox: true`**: without it the shape lacks `txBox="1"`, so screen readers announce the text as a "graphic" instead of a text box. No visual change.
- **Text boxes have built-in internal padding**: set `margin: 0` whenever text must align with a shape, line, or icon at the same x.
- **Speaker notes go in `slide.addNotes("...")`** (plain text, once per slide), never in a text box on the slide.
- **Keep charts native.** Use `addChart()` for everything PowerPoint can chart (pass an array of `{type, data, options}` for combos). For PowerPoint-native features the library doesn't expose (trendlines, error bars), compute the extra series yourself or post-process the generated OOXML: do not fall back to a rendered image. Only chart types PowerPoint has no native form for (Sankey, network, chord) go in as images.
- **Default charts render bare**: no title, no data labels, dated palette. Set `showTitle` + `title`, `showValue: true` + `dataLabelPosition`, `chartColors: [...]` from your palette, and quiet the frame (`catAxisLabelColor`/`valAxisLabelColor`, `valGridLine: { color, size }`, `catGridLine: { style: "none" }`, `showLegend: false` for a single series).
- **On a stacked bar or column chart, `dataLabelPosition` must be `ctr`, `inEnd`, or `inBase`.** `outEnd` **corrupts the file**.
- **A combo series using `secondaryValAxis`/`secondaryCatAxis` needs both `valAxes` and `catAxes` on the chart options, two entries each.** Without them pptxgenjs writes axis *ids* it never declares, and PowerPoint **discards that chart** and reports the file as corrupt. Supplying only `valAxes` is not enough.
- **After `writeFile()`, run `python scripts/office/validate.py deck.pptx`.** It reports many of the chart and slide-XML faults PowerPoint refuses or repairs, the two above among them, and names the fix for each. Fix them in your generator, not by hand-editing the packed XML.
- **Never reorder the children of `<p:presentation>`.** pptxgenjs writes `<p:notesMasterIdLst>` right after `<p:sldIdLst>` and points both masters at one theme part. PowerPoint reads that happily: move the element and the same deck becomes unopenable.
- **Icons:** render `react-icons` to SVG (`ReactDOMServer.renderToStaticMarkup`), rasterize with `sharp` at >= 256px, and insert via `addImage({ data: "image/png;base64," + buf.toString("base64") })` with the required `image/png;base64,` prefix (install `react-icons`, `react`, `react-dom`, and `sharp` in the project or scratch workspace if a require fails).
- **`defineSlideMaster()` creates a slide *layout*, not a master**: one `slideLayoutN.xml` per call, under a single master you cannot change. Call them layouts when talking to the user.
- **`pres.company` and a `defineSlideMaster()` `title` are written into the XML unescaped**: an `&` in either (`"Harrow & Sons"`) leaves `docProps/app.xml` or the layout unparseable, and `validate.py` fails. Write `&amp;` there, and in the matching `masterName`. `title`, `subject`, `author`, section titles, `objectName`, notes and slide text are escaped for you.

### Structured decks

A deck built on a theme, layouts, placeholders and sections can be restyled in one place and edited in PowerPoint without fighting it. Build every new deck this way unless the user asks for a quick throwaway.

1. **Theme first:** `const THEME = { name, headFontFace, bodyFontFace, colors: { dk1, lt1, dk2, lt2, accent1 … accent6, hlink, folHlink } }`, colors in hex. `pres.theme` takes the two fonts and nothing else. Name no font after that: titles get the heading font, other text the body font: except on chart text, which is hard-coded Arial: give its `*FontFace` options `"+mn-lt"` (theme body font; `"+mj-lt"` is the heading font).
2. **`const C = pres.SchemeColor` for every color**: `C.text1`/`C.text2` are `dk1`/`dk2`, `C.background1`/`C.background2` are `lt1`/`lt2`. These take hex only, read from `THEME`: `valGridLine.color`, `catGridLine.color`, `shadow.color`, and on a one-series bar chart `invertedColors` or more than one `chartColors`. A scheme color there is written as `<a:srgbClr val="bg2"/>` without complaint, and being hex, these will not follow a later change of theme.
3. **Sections:** `pres.addSection({ title })` just before that section's first slide, then `sectionTitle` on every `addSlide`. A slide without one: or, when sections are all declared up front, a table's auto-paged continuation slides: lands in a stray "Default-N" section.
4. **One layout per slide frame** (`defineSlideMaster()`): title, section divider, title only, chart + commentary, table; dark and light variants if the design alternates. Text regions are named placeholders carrying position, size, weight and `color`: chart, image and table placeholders need a `color` too, or prompt text and arrays of runs come out hard-coded `000000`. Footer text, logo and `slideNumber` go on the layout, never on a slide.
5. **Fill by name:** `addSlide({ masterName, sectionTitle })`, then `addText("…", { placeholder: "title" })` with no position, size or color: the placeholder's own options win, and anything it doesn't set (italic, `align`, `fontFace`) still applies; style one run with `[{ text, options }]`. A misspelt `placeholder` or `masterName` fails silently (a stray text box at 0,0; the blank layout). Only `title`, `body` and `chart` placeholders fill by name alone: `addImage({ placeholder })` takes the placeholder's x and y but not its size (a 1" × 1" picture): pass `w`/`h` too. `addTable({ placeholder })` takes its x and y only: always pass `w`; when it auto-pages it ignores the placeholder and runs off the slide, so also pass `x`, `y` and `autoPageSlideStartY` (same as `y`, or continuation pages are laid out from the top margin), give the layout a `margin` whose bottom clears the footer, and fill the continuation slides' titles through `slide.newAutoPagedSlides`.
6. **A layout is the frame, not the "layout" Design Ideas means.** Cards, icons, stat callouts and images are still composed slide by slide on top of it, in scheme colors, each with an `objectName`: every Design Idea applies, and most content slides sit on the title-only layout.
7. **Write, then apply the theme:** `await pres.writeFile({ fileName: "deck.pptx" })`, then `await applyTheme("deck.pptx", THEME)`. pptxgenjs cannot write theme colors: until this runs, scheme colors resolve to Office's stock palette. It throws, changing nothing, on a scheme color in a hex-only option: fix what it names and rebuild.

## Editing existing decks and templates

Pick layouts first: `python scripts/thumbnail.py template.pptx template-thumbs` writes a labeled grid of every slide and prints the file(s) it created: `template-thumbs.jpg`, split into `template-thumbs-N.jpg` past 12 slides. **Always pass that second argument, named after the deck.** It defaults to `thumbnails`, so two decks thumbnailed in one directory silently overwrite each other's grids: the first deck's are simply gone (template analysis only: visual QA needs the full-resolution renders from [Converting to Images](#converting-to-images); it only accepts `.pptx`, so copy a `.potx` to a `.pptx` name first). Use it with `slide_text.py` to map each content section onto a template slide, and vary the layouts: don't put every section on the same title-and-bullets slide.

```bash
python3 -c "import sys,zipfile; zipfile.ZipFile(sys.argv[1]).extractall('unpacked')" deck.pptx
python scripts/add_slide.py unpacked/ slide2.xml --after slide2.xml   # duplicate a slide (or slideLayoutN.xml); prints the new slide's path
# reorder / delete slides = edit <p:sldIdLst> in ppt/presentation.xml
python scripts/clean.py unpacked/                                     # after deletions: removes orphaned slides, media, rels
# edit slide content in ppt/slides/slideN.xml
(cd unpacked && rm -f ../out.pptx && zip -XrD ../out.pptx .)          # zip from INSIDE the dir; rm first or deleted parts survive
python scripts/office/validate.py out.pptx --original deck.pptx
```

- **Do all structural work: add, delete, reorder: before editing any slide's content.** `add_slide.py` copies a slide file verbatim, so duplicating after you edit clones the edited content; and `clean.py` deletes any slide missing from `<p:sldIdLst>`, including one you just wrote.
- **Never copy a slide file by hand**: `add_slide.py` does every registration a new slide needs and reports what it made (`Created ppt/slides/slide17.xml from slide2.xml`). It also works directly on a file: `add_slide.py deck.pptx slide2.xml -o out.pptx`: **pass `-o`, or it rewrites the input deck in place.** A duplicated slide still *references* its source's chart/SmartArt/embedded-object parts rather than cloning them, so editing one slide's chart changes the other's.
- **If you use `python-pptx`**, three things it won't do: duplicate a slide (its only entry point is `add_slide(layout)`), preserve formatting through `text_frame.text = "..."` (that collapses the paragraph to a single unstyled run: assign `run.text` instead), or read the SVG/EMF most template art uses (`add_picture` raises `UnidentifiedImageError`).
- Legacy `.ppt` must be converted first: `python scripts/office/soffice.py --headless --convert-to pptx file.ppt`. `.potx` templates unpack and pack identically: keep the `.potx` extension on the output.
- To reuse a template icon or image, duplicate a slide or layout that already contains it.

When filling in a template:

- If you script an XML transform, parse with `defusedxml.minidom`: round-tripping OOXML through `xml.etree.ElementTree` rewrites namespace prefixes and corrupts the deck.
- **Template slots ≠ source items.** If the template shows 4 team members and you have 3, delete the 4th member's entire group (image + text boxes), not just its text: then check for orphaned visuals in QA.
- One `<a:p>` per list item: never concatenate items into a single paragraph. Copy the sibling `<a:pPr>` to preserve spacing, and put `b="1"` on the `<a:rPr>` of titles, section headers, and inline labels (`Status:`, `Owner:`).
- Let bullets inherit from the layout; only add `<a:buChar>`, `<a:buAutoNum>` (numbered), or `<a:buNone>` to override: never a literal `•` in the text.
- Text with leading or trailing spaces needs `xml:space="preserve"` on its `<a:t>`.

## Deck content and flow

- **One message per slide.** A deck goes theme by theme, message by message.
- **A common structure is the pyramid:** the main message up front, an executive summary that previews the sections, the sections themselves, then a conclusion, usually with next steps that act on the findings.
- **Match the structure to the size of the deck.** A short deck might not need an introduction and a conclusion; a long deck might need dividers between topics.
- **Build toward what the deck is for:** a decision, consensus, a celebration, resolving a disagreement, or opening a discussion.
- **Build for how it will be used.** A live deck gets narration and possibly discussion; a pre-read has to carry the whole narrative itself. An executive audience in a live meeting needs few words and highly visual slides. Detailed, word-heavy slides are sometimes right for subject-matter experts or for a deck read offline. Analytical reports lean on charts and tables.
- **Size a live deck to the talk:** about 1.5 to 2 minutes per slide, with time left for questions if there will be any.

## Design Ideas

Read [references/design-ideas.md](./references/design-ideas.md) when designing a new deck for curated color palettes, slide layout patterns, Office-safe typography pairing, and visual mistakes to avoid (never put accent stripes or title underlines, keep 0.5" margins, use 14-16pt body and 36-44pt titles, and keep Office-safe fonts so LibreOffice QA text fit matches PowerPoint).

## QA (Required)

Your first render usually has a few real issues: overlaps, overflow, misalignment. Find and fix those, re-render only the slides you changed, and stop.

### Content QA (required)

```bash
python scripts/slide_text.py output.pptx
```

Check for missing content, typos, wrong order.

**When using templates, check for leftover placeholder text:**

```bash
python scripts/slide_text.py output.pptx | grep -iE "\bx{3,}\b|lorem|ipsum|\bTODO|\[insert|this.*(page|slide).*layout"
```

If grep returns results, fix them before declaring success.

### File QA (required)

```bash
python scripts/office/validate.py output.pptx                      # built from scratch
python scripts/office/validate.py output.pptx --original src.pptx  # built from a template
```

**If the deck came from a template, always pass `--original`.** A template may itself
contain parts the XSD rejects, so a bare run can report failures you never caused: and
a genuine regression can hide among them. `--original` baselines
the schema and slide checks against the template, suppressing errors it already had.
The structural checks: relationships, content types, charts: ignore `--original` and
report template-inherited problems either way, so read those on their own merits.

pptxgenjs emits chart XML PowerPoint refuses to open, and every other tool
accepts: python-pptx opens those decks, LibreOffice renders them, the XSD
passes them. Every failure names its fix. Fix it in the generator and rebuild.

**A pass is not proof of a valid file:** `validate.py` does not catch everything PowerPoint repairs (a chart element repeated past its limit passes); when you delete an animated shape from a template slide, delete the slide's `<p:timing>` element too (its animations go with it), or PowerPoint offers to repair the deck.

### Visual QA (required)

Convert the slides to images (see [Converting to Images](#converting-to-images)) and inspect every one. After staring at the generating code you tend to see what you expect rather than what rendered, so look at the images fresh (a subagent works well for this if you have one). User-visible defects to look for:

- **Text overflow or text cut off at a box or slide boundary: check this first.** It is the most common defect and always user-visible. (For a font the previewer renders unreliably per Typography, the preview is approximate: trust the ~10% slack you left, not its apparent fit.)
- Overlapping elements (text through shapes, lines through words, stacked elements)
- Source citations or footers colliding with content above
- Elements too close (< 0.3" gaps) or cards/sections nearly touching
- Uneven gaps (large empty area in one place, cramped in another)
- Insufficient margin from slide edges (< 0.5")
- Columns or similar elements not aligned consistently
- Low-contrast text (e.g., light gray text on cream-colored background)
- Template decoration mispositioned after text replacement: e.g., a title underline positioned for one line, but the replaced title wrapped to two
- Low-contrast icons (e.g., dark icons on dark backgrounds without a contrasting circle)
- Text boxes too narrow causing excessive wrapping
- Titles at different heights, or chart labels that look different from chart to chart, across slides of the same type: compare slides with each other, not only each slide with itself
- A word or number broken across two lines: a word split mid-word, or a figure separated from its unit ("26" on one line, "M" on the next)
- Leftover placeholder content

## Converting to Images

Convert presentations to individual slide images for visual inspection:

```bash
python scripts/office/soffice.py --headless --convert-to pdf output.pptx
rm -f slide-*.jpg
pdftoppm -jpeg -r 150 output.pdf slide
ls -1 "$PWD"/slide-*.jpg
```

**Pass the absolute paths printed above directly to `read_file` to visually inspect the images.** The `rm` clears stale images from prior runs. `pdftoppm` zero-pads based on page count: `slide-1.jpg` for decks under 10 pages, `slide-01.jpg` for 10-99, `slide-001.jpg` for 100+.

**After fixes, rerun all four commands above**, because the PDF must be regenerated from the edited `.pptx` before `pdftoppm` can reflect your changes.

## Dependencies

`pptxgenjs` (npm; install locally only if `require('pptxgenjs')` fails) | `python-pptx`, `Pillow`, `defusedxml`, `lxml` (pip: `slide_text`, `thumbnail`, `clean`, `validate`) | LibreOffice (`soffice` via `scripts/office/soffice.py`) | `pdftoppm` (Poppler)
