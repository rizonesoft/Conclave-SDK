// Diagnostic classification only. No role ever authorizes attachment removal.
// Raw metadata remains in the inventory used by the strict preservation guard.
export function normalizeContentId(value) {
  if (typeof value !== "string" || !value.trim()) return null;
  let result = value.trim().replace(/^cid:/i, "");
  try { result = decodeURIComponent(result); } catch { return null; }
  if (result.startsWith("<") && result.endsWith(">")) result = result.slice(1, -1);
  return result && result.length <= 2048 && !/[\s<>\x00-\x1f\x7f]/u.test(result) ? result : null;
}

function descendants(roots) {
  const result = new Set(), pending = [...roots];
  while (pending.length) {
    const node = pending.pop();
    result.add(node);
    pending.push(...(node.childNodes || []));
  }
  return result;
}

export function attachmentReferences(region, attachments) {
  const authored = descendants(region.authoredNodes), quoted = descendants(region.quoteNodes);
  const references = new Map();
  const record = (url, role) => {
    if (!/^cid:/i.test(url.trim())) return;
    const contentId = normalizeContentId(url), mapKey = contentId ?? "invalid:" + url;
    if (!references.has(mapKey)) references.set(mapKey, { contentId, rawReferences: new Set(), roles: new Set() });
    const ref = references.get(mapKey);
    ref.rawReferences.add(url);
    ref.roles.add(role);
  };
  const css = (value, role) => {
    // Match URL tokens, not normal text or CSS string literals outside url().
    for (const match of value.matchAll(/url\(\s*(?:"([^"]*)"|'([^']*)'|([^\s)]*))\s*\)/gi))
      record(match[1] ?? match[2] ?? match[3], role);
  };
  for (const node of region.nodes) {
    const role = authored.has(node) ? "authored" : quoted.has(node) ? "quoted" : "document";
    for (const attribute of node.attrs || []) {
      if (["src", "href", "background", "poster", "data"].includes(attribute.name)) record(attribute.value, role);
      if (attribute.name === "srcset")
        for (const candidate of attribute.value.split(",")) record(candidate.trim().split(/\s+/)[0], role);
      if (attribute.name === "style") css(attribute.value, role);
    }
    if (node.tagName === "style") css((node.childNodes || []).map((n) => n.value || "").join(""), role);
  }
  const inventory = attachments.map((attachment) => {
    const known = attachment.contentIdKnown === true;
    const normalizedContentId = known ? normalizeContentId(attachment.contentId) : null;
    const roles = [...(references.get(normalizedContentId)?.roles || [])].sort();
    const duplicates = normalizedContentId && attachments.filter((a) => a.contentIdKnown === true &&
      normalizeContentId(a.contentId) === normalizedContentId).length > 1;
    const classification = !attachment.isInline ? "non-inline" : !known ? "unknown-content-id" :
      attachment.contentId && !normalizedContentId ? "invalid-content-id" : duplicates ? "ambiguous-content-id" :
      roles.length ? "referenced" : "unreferenced";
    return { ...attachment, normalizedContentId, roles, classification };
  });
  const coverage = [...references.values()].map((ref) => {
    const matches = inventory.filter((a) => ref.contentId && a.normalizedContentId === ref.contentId);
    return { contentId: ref.contentId, rawReferences: [...ref.rawReferences].sort(), roles: [...ref.roles].sort(),
      attachmentIds: matches.map((a) => a.id).sort(),
      resolution: !ref.contentId ? "invalid-reference" : !matches.length ? "missing" :
        matches.length > 1 ? "ambiguous" : !matches[0].isInline ? "not-inline" : "resolved" };
  }).sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b)));
  return { inventory, references: coverage,
    protectedReferencesComplete: coverage.every((r) => !r.roles.some((role) => role !== "authored") || r.resolution === "resolved"),
    scope: "CID URLs in HTML URL attributes, srcset and CSS url(); metadata only, not rendered pixels or attachment bytes" };
}

export function attachmentDifferences(baseline, proposed, observed) {
  const metadata = ({ normalizedContentId, roles, classification, ...raw }) => raw;
  const before = new Map(baseline.inventory.map((a) => [a.id, a]));
  const after = new Map(observed.inventory.map((a) => [a.id, a]));
  const planned = new Map(proposed.inventory.map((a) => [a.id, a]));
  return {
    removed: baseline.inventory.filter((a) => !after.has(a.id)).map((a) => ({ before: a, proposed: planned.get(a.id) })),
    added: observed.inventory.filter((a) => !before.has(a.id)),
    changed: observed.inventory.filter((a) => before.has(a.id) && JSON.stringify(metadata(before.get(a.id))) !== JSON.stringify(metadata(a)))
      .map((a) => ({ before: before.get(a.id), proposed: planned.get(a.id), observed: a })),
  };
}
