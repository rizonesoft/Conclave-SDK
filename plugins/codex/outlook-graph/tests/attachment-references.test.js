import test from "node:test";
import assert from "node:assert/strict";
import { attachmentReferences, normalizeContentId } from "../src/attachment-references.js";
import { htmlRegion } from "../src/html-body.js";

const asset = (id, contentId, options = {}) => ({ id, contentId, contentIdKnown: true, isInline: true, ...options });
const region = (authored, quoted, head = "", wrapper = "") => htmlRegion(
  `<html><head>${head}</head><body ${wrapper}>${authored}<hr><div id="divRplyFwdMsg">Quote</div>${quoted}</body></html>`);

test("CID matching decodes URLs and brackets while preserving case and raw metadata", () => {
  assert.equal(normalizeContentId("CID:%3CExample%40test%3E"), "Example@test");
  assert.equal(normalizeContentId("<Example@test>"), "Example@test");
  for (const invalid of [null, "", "bad value", "%zz", "<bad", "line\nfeed"])
    assert.equal(normalizeContentId(invalid), null);
  const raw = asset("a", "<Example@test>");
  const result = attachmentReferences(region("", '<img src="cid:Example%40test">'), [raw]);
  assert.equal(result.protectedReferencesComplete, true);
  assert.equal(result.inventory[0].contentId, "<Example@test>");
  assert.deepEqual(result.inventory[0].roles, ["quoted"]);
  assert.equal(attachmentReferences(region("", '<img src="cid:example%40test">'), [raw]).protectedReferencesComplete, false);
});

test("authored, quoted and preserved document references include URL attributes and CSS", () => {
  const result = attachmentReferences(region(
    '<img src="cid:portrait"><p>cid:plain-text-is-not-a-reference</p>',
    '<table background="cid:shared"><tr><td style="background:url(\'cid:css\')"></td></tr></table>' +
      '<img srcset="cid:retina 2x, cid:small 1x"><a href="cid:linked">File</a><img src="cid:shared">',
    '<style>.x { background-image:url("cid:head") }</style>',
    'background="cid:shared"'),
  ["portrait", "shared", "css", "retina", "small", "linked", "head"].map((id) => asset(id, id)));
  assert.equal(result.protectedReferencesComplete, true);
  assert.equal(result.references.length, 7);
  assert.deepEqual(result.inventory.find((a) => a.id === "shared").roles, ["document", "quoted"]);
  assert.deepEqual(result.inventory.find((a) => a.id === "portrait").roles, ["authored"]);
  assert.deepEqual(result.inventory.find((a) => a.id === "head").roles, ["document"]);
});

test("omitted IDs are unknown; known unused IDs, non-inline items and duplicate IDs remain distinct", () => {
  const result = attachmentReferences(region("", '<img src="cid:duplicate"><img src="cid:not-inline"><img src="cid:missing">'), [
    asset("unknown", null, { contentIdKnown: false }), asset("unused", "unused"),
    asset("file", "not-inline", { isInline: false }), asset("a", "duplicate"), asset("b", "duplicate"),
    asset("invalid", "bad id"),
  ]);
  assert.deepEqual(result.inventory.map((a) => a.classification), ["unknown-content-id", "unreferenced", "non-inline",
    "ambiguous-content-id", "ambiguous-content-id", "invalid-content-id"]);
  assert.deepEqual(result.references.map((r) => r.resolution).sort(), ["ambiguous", "missing", "not-inline"]);
  assert.equal(result.protectedReferencesComplete, false);
});

test("invalid protected CID references block; missing authored images are diagnostic only", () => {
  assert.equal(attachmentReferences(region('<img src="cid:missing">', ""), []).protectedReferencesComplete, true);
  const invalid = attachmentReferences(region("", '<img src="cid:%zz">'), []);
  assert.equal(invalid.references[0].resolution, "invalid-reference");
  assert.equal(invalid.protectedReferencesComplete, false);
});
