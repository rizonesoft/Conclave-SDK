---
name: frontend-design
description: >-
  Use when designing, building, or reshaping web UI components, pages, dashboards, or applications. Enforces a project's design contract first, distinctive typography and aesthetic restraint without AI-slop defaults, and visual verification in Chrome DevTools.
---

# Frontend Design

Approach every UI task like a principal design engineer responsible for giving the product an unmistakable, cohesive identity rather than generic generated layouts.

## Project design contract first

Check the workspace for `DESIGN.md` or files under `design/` before making visual choices. When the project defines palette, typography, tokens, spacing, or component rules, follow that contract strictly. When it leaves axes open or no design system exists, design deliberately for the subject matter below.

## Ground decisions in the subject

Identify the concrete audience, domain vernacular, and primary job of the interface before writing code. A financial operations console, a veterinary clinic portal, and a consumer hardware manual demand completely different density, surface contrast, and typographic voice. Use realistic domain copy throughout rather than empty placeholder strings.

## Anti-slop calibration

Avoid default AI-generated visual clichés unless explicitly requested by the brief or `DESIGN.md`:

- Avoid overused system-default or identical rounded-card SaaS grids where every widget wears the same `rgba(0,0,0,.1)` drop shadow and pastel gradient wash.
- Avoid gratuitous tracked-out ALL-CAPS eyebrows above every heading, middle-dot meta chains (`A · B · C`), labeled em-dash fragments, monospace micro-badges on non-code prose, and trailing arrows appended to every CTA.
- Choose typography intentionally: pick one expressive display/body family (or two clearly contrasting families) with clean hierarchy, keep body line lengths under 80 characters, and do not style single isolated words in headlines with different colors or italics as fake emphasis.
- Use visual structure honestly: borders, dividers, and numbered markers (`01`, `02`, `03`) belong only where hierarchy or real sequential order exists.
- Keep motion purposeful and disciplined: prefer responsive state transitions that clarify what changed over gratuitous scroll fade-ins on every section.

## Two-pass design plan before coding

Before editing layout or stylesheet code for a new view or major redesign, draft a brief token plan:

1. **Palette (4 to 6 named hex values)**: primary canvas, surface, primary ink, muted ink, accent, semantic status.
2. **Typography**: chosen font families, scale ratios, line heights, and weight roles.
3. **Layout & Alignment**: rough ASCII wireframe and clear alignment discipline (left-aligned prose, tabular figures for metrics).
4. **Distinctive Focal Element**: choose one memorable focal point and strip decorative noise everywhere else.

Review your plan against the brief: if any piece feels like a generic template you would reach for on any unrelated prompt, revise that piece before writing HTML/CSS/TSX.

## Copy and accessibility discipline

- Write active, concrete UI labels matching the user's mental model ("Save notification rules", not "Submit webhook config"), keeping verbs consistent from trigger button to confirmation toast.
- Make empty and error states actionable in clear sentences without vague apologies.
- Maintain responsive breakpoints down to narrow mobile viewports, WCAG AA color contrast, visible keyboard `:focus-visible` outlines, semantic HTML landmarks, and `prefers-reduced-motion` support.
- Avoid em dashes and en dashes in UI copy and labels.

## Visual verification loop

Never treat frontend code edits as finished from code inspection alone:

1. Build or serve the interface and open it in a real browser (using Chrome DevTools MCP, Playwright, or screenshot capture when available).
2. Inspect desktop and mobile viewports for overflow, clipped labels, broken wrapping, weak contrast, and spacing alignment.
3. Run accessibility checks (keyboard tab order, focus rings, semantic roles) when Chrome DevTools MCP (`chrome-devtools` or `a11y-debugging`) is active, fix defects in component styles, and verify again with a fresh capture.
