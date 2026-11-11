import { parse } from "parse5";
import { createHash } from "node:crypto";
import { GraphError } from "./client.js";

export const htmlHash = (value) => createHash("sha256").update(value).digest("hex");
const text = (node) => node.nodeName === "#text" ? node.value :
  node.tagName === "br" ? "\n" : (node.childNodes || []).map(text).join("");
const normalized = (value) => value.replace(/\s+/gu, " ").trim();
const attr = (node, name) => node.attrs?.find((a) => a.name === name)?.value;
const children = (node) => node.childNodes || [];
const walk = (node) => {
  const result = [], pending = [[node, 0]];
  while (pending.length) {
    const [current, depth] = pending.pop();
    if (depth > 256 || result.length >= 100000) throw new GraphError("Draft HTML exceeds safe structural bounds.");
    result.push(current);
    for (const child of [...children(current)].reverse()) pending.push([child, depth + 1]);
  }
  return result;
};
const meaningful = (node) => node.nodeName !== "#comment" &&
  (node.nodeName !== "#text" || normalized(node.value));
const escape = (value) => value.replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

export function renderParagraphs(paragraphs) {
  if (!Array.isArray(paragraphs) || !paragraphs.length || paragraphs.length > 100 ||
      paragraphs.some((p) => typeof p !== "string" || !p.trim() || p.length > 20000 ||
        /[\u0000-\u0008\u000b\u000c\u000e-\u001f]/u.test(p)) ||
      paragraphs.join("").length > 100000)
    throw new GraphError("Supply one to 100 nonempty plain-text paragraphs, within 100000 characters.");
  return paragraphs.map((p) => '<p style="font-family:Segoe UI,Arial,sans-serif;font-size:12pt;line-height:1.2;margin:0 0 8pt;color:#242424">' +
    escape(p.replace(/\r\n?/g, "\n")).replaceAll("\n", "<br>") + "</p>").join("\n") + "\n";
}

// Parse for source offsets, then splice the original string. Never serialize or
// sanitize the existing quote: its HTML, links, signatures and CID references
// are sent unchanged. Unsupported/ambiguous native layouts fail closed.
export function htmlRegion(html) {
  if (typeof html !== "string" || !html || html.length > 1000000)
    throw new GraphError("HTML body is missing or exceeds 1000000 characters.");
  const document = parse(html, { sourceCodeLocationInfo: true });
  const nodes = walk(document), body = nodes.find((n) => n.tagName === "body");
  const quotes = nodes.filter((n) => n.tagName === "div" &&
    attr(n, "id")?.toLowerCase() === "divrplyfwdmsg");
  if (quotes.length !== 1 || !body?.sourceCodeLocation?.startTag || !body.sourceCodeLocation.endTag)
    throw new GraphError("One unambiguous native divRplyFwdMsg quote and explicit body tags are required.");
  const quote = quotes[0], container = quote.parentNode;
  let parent = container;
  for (let depth = 0; parent !== body; depth++) {
    if (!parent || depth >= 8 || parent.tagName !== "div" ||
        children(parent.parentNode).filter(meaningful).length !== 1)
      throw new GraphError("Unsupported quote nesting; preserve the draft and inspect its HTML.");
    parent = parent.parentNode;
  }
  const location = container.sourceCodeLocation;
  if (!location?.startTag || !location.endTag || !quote.sourceCodeLocation?.startTag)
    throw new GraphError("Draft HTML boundaries are incomplete.");
  const siblings = children(container), quoteIndex = siblings.indexOf(quote);
  let boundaryIndex = quoteIndex;
  for (let i = quoteIndex - 1; i >= 0; i--) {
    if (!meaningful(siblings[i])) continue;
    if (siblings[i].tagName === "hr") boundaryIndex = i;
    break;
  }
  const start = location.startTag.endOffset;
  const end = siblings[boundaryIndex].sourceCodeLocation?.startOffset;
  if (!Number.isSafeInteger(end) || end < start || end >= location.endTag.startOffset)
    throw new GraphError("Draft HTML edit range is ambiguous.");
  return {
    html, start, end, nodes, authoredHtml: html.slice(start, end),
    authoredNodes: siblings.slice(0, boundaryIndex),
    quoteNodes: siblings.slice(boundaryIndex),
    replace: (authoredHtml) => html.slice(0, start) + authoredHtml + html.slice(end),
  };
}

function semantic(node) {
  if (node.nodeName === "#comment") return [];
  if (node.nodeName === "#text") return normalized(node.value) ? [normalized(node.value)] : [];
  const content = children(node).flatMap(semantic);
  if (["span", "font"].includes(node.tagName)) return content;
  const attributes = (node.attrs || []).filter((a) =>
    ["href", "src", "alt", "width", "height", "colspan", "rowspan"].includes(a.name))
    .map((a) => [a.name, a.value]).sort(([a], [b]) => a.localeCompare(b));
  const tag = ["p", "div"].includes(node.tagName) ? "block" :
    node.tagName === "b" ? "strong" : node.tagName === "i" ? "em" : node.tagName;
  if (tag === "block" && !content.length && !attributes.length) return [];
  return [{ tag, attributes, content }];
}

export const quoteFingerprint = (region) => htmlHash(JSON.stringify(region.quoteNodes.flatMap(semantic)));

export function verifyAuthored(region, paragraphs) {
  const nodes = region.authoredNodes.filter(meaningful);
  if (nodes.some((n) => walk(n).some((x) =>
      attr(x, "id")?.toLowerCase() === "signature" ||
      ["img", "script", "iframe", "object", "svg", "form", "style", "link"].includes(x.tagName) ||
      x.attrs?.some((a) => a.name.startsWith("on") ||
        (a.name === "href" && !/^(?:https?:|mailto:)/i.test(a.value)))))) return false;
  const actual = nodes.filter((n) => normalized(text(n)));
  if (actual.some((n) => !["p", "div"].includes(n.tagName))) return false;
  return JSON.stringify(actual.map((n) => normalized(text(n)))) ===
    JSON.stringify(paragraphs.map(normalized));
}
