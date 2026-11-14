"""
Excel Formula Recalculation Script
Recalculates all formulas in an Excel file using LibreOffice
"""

import html
import io
import json
import os
import posixpath
import re
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as _stdlib_et
import xml.parsers.expat as _expat
import zipfile
from pathlib import Path

from office.helpers import (
    MAX_ARCHIVE_BYTES,
    open_zip_member,
    read_zip_member,
    validate_archive,
)
from office.soffice import get_soffice_env, run_soffice

MACRO_FILENAME = "Module1.xba"
SOFFICE_MISSING = "soffice not found on PATH; LibreOffice is required to recalculate"

MAX_LOCATIONS = 100

EXTERNAL_REF_RE = re.compile(r"""(?<![\w"\[])'?\[\d+\][^!"\[\]]*'?!""")

RECALCULATE_MACRO = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE script:module PUBLIC "-//OpenOffice.org//DTD OfficeDocument 1.0//EN" "module.dtd">
<script:module xmlns:script="http://openoffice.org/2000/script" script:name="Module1" script:language="StarBasic">
    Sub RecalculateAndSave()
      ThisComponent.calculateAll()
      ThisComponent.store()
      ThisComponent.close(True)
    End Sub
</script:module>"""


def _stamp(path):
    st = os.stat(path)
    return st.st_mtime_ns, st.st_size


def setup_libreoffice_macro(profile_dir: Path, timeout=30):
    url = profile_dir.as_uri()
    try:
        run_soffice(
            ["--headless", "--terminate_after_init", f"-env:UserInstallation={url}"],
            capture_output=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return None, SOFFICE_MISSING
    except subprocess.TimeoutExpired:
        return None, "LibreOffice timed out creating its profile; formulas were NOT recalculated"

    macro_dir = profile_dir / "user" / "basic" / "Standard"
    if not macro_dir.exists():
        return None, "LibreOffice did not create a usable profile; formulas were NOT recalculated"

    try:
        (macro_dir / MACRO_FILENAME).write_text(RECALCULATE_MACRO)
    except OSError as e:
        return None, f"Could not install the recalculation macro: {e}"

    return url, None


EXCEL_ERRORS = ["#VALUE!", "#DIV/0!", "#REF!", "#NAME?", "#NULL!", "#NUM!", "#N/A"]
EXCEL_ERROR_SET = frozenset(EXCEL_ERRORS)
MAX_XML_PART_BYTES = 128 * 1024 * 1024
MAX_MERGE_CHECKS = 1_000_000
MAX_MERGED_CELLS = 1_000_000
MAX_XML_DEPTH = 256
MAX_SUBTREE_ELEMENTS = 10_000

_TRANSITIONAL_MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_STRICT_MAIN_NS = "{http://purl.oclc.org/ooxml/spreadsheetml/main}"
_TRANSITIONAL_REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_STRICT_REL_NS = "{http://purl.oclc.org/ooxml/officeDocument/relationships}"
_MAIN_NS = _TRANSITIONAL_MAIN_NS
_REL_NS = _TRANSITIONAL_REL_NS
_CELL_REF_RE = re.compile(r"([A-Z]+)([0-9]+)")


def _local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _resolve_rel_target(target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(f"xl/{target}")


def _make_dtd_guard():
    parser = _expat.ParserCreate()

    def _forbid(*_args):
        raise ValueError("XML DTD and entity declarations are forbidden")

    parser.StartDoctypeDeclHandler = _forbid
    parser.EntityDeclHandler = _forbid
    parser.UnparsedEntityDeclHandler = _forbid
    parser.ExternalEntityRefHandler = _forbid
    return parser


class _NoDtdStream:
    def __init__(self, stream):
        self._stream = stream
        self._guard = _make_dtd_guard()
        self._finished = False

    def read(self, size=-1):
        chunk = self._stream.read(size)
        if chunk:
            self._guard.Parse(chunk, False)
        elif size != 0 and not self._finished:
            self._finished = True
            self._guard.Parse(b"", True)
        return chunk


def _safe_fromstring(data: bytes):
    try:
        from defusedxml.ElementTree import fromstring
    except ImportError:
        _make_dtd_guard().Parse(data, True)
        return _stdlib_et.fromstring(data)
    return fromstring(data)


def _safe_iterparse(source, keep_subtrees=frozenset(("c", "si"))):
    try:
        from defusedxml.ElementTree import iterparse
        raw_iter = iterparse(source, events=("start", "end"))
    except ImportError:
        raw_iter = _stdlib_et.iterparse(_NoDtdStream(source), events=("start", "end"))

    stack = []
    retain_depth = 0
    subtree_nodes = 0
    for event, node in raw_iter:
        if event == "start":
            stack.append(node)
            if len(stack) > MAX_XML_DEPTH:
                raise ValueError(f"XML nesting depth exceeds limit {MAX_XML_DEPTH}")
            if retain_depth > 0 or _local_tag(node.tag) in keep_subtrees:
                retain_depth += 1
                subtree_nodes += 1
                if subtree_nodes > MAX_SUBTREE_ELEMENTS:
                    raise ValueError(f"XML element subtree exceeds limit {MAX_SUBTREE_ELEMENTS}")
            continue
        yield (event, node)
        stack.pop()
        if retain_depth > 0:
            retain_depth -= 1
            if retain_depth == 0:
                subtree_nodes = 0
                node.clear()
                if stack:
                    del stack[-1][:]
        else:
            node.clear()
            if stack:
                del stack[-1][:]


def _workbook_namespaces(workbook):
    if workbook.tag == f"{_STRICT_MAIN_NS}workbook":
        return _STRICT_MAIN_NS, _STRICT_REL_NS
    if workbook.tag == f"{_TRANSITIONAL_MAIN_NS}workbook":
        return _TRANSITIONAL_MAIN_NS, _TRANSITIONAL_REL_NS
    raise ValueError("not a supported OOXML workbook")


def _exact_error(text):
    if not isinstance(text, str):
        return None
    cleaned = text.strip()
    return cleaned if cleaned in EXCEL_ERROR_SET else None


def _read_archive_part(
    archive: zipfile.ZipFile,
    name: str,
    max_bytes: int = MAX_XML_PART_BYTES,
    budget: list[int] | None = None,
) -> bytes:
    return read_zip_member(
        archive,
        name,
        budget=budget,
        max_member_bytes=max_bytes,
        max_bytes=MAX_ARCHIVE_BYTES,
    )


def _rich_text(node, main_ns=_MAIN_NS):
    runs = node.findall(f"{main_ns}t") + node.findall(f"{main_ns}r/{main_ns}t")
    return "".join(t.text or "" for t in runs)


def _row_major(coordinate):
    cleaned = coordinate.replace("$", "").strip().upper()
    match = _CELL_REF_RE.fullmatch(cleaned)
    if match is None:
        raise ValueError(f"invalid cell coordinate: {coordinate!r}")
    column, row = match.groups()
    number = 0
    for letter in column:
        number = number * 26 + ord(letter) - ord("A") + 1
    return int(row), number


def _parse_merge_ref(ref_str: str, merge_budget: list[int] | None) -> tuple[int, int, int, int]:
    cleaned = html.unescape(ref_str).strip()
    first, sep, last = cleaned.partition(":")
    if not sep:
        last = first
    r1, c1 = _row_major(first)
    r2, c2 = _row_major(last)
    top, bottom = min(r1, r2), max(r1, r2)
    left, right = min(c1, c2), max(c1, c2)
    area = (bottom - top + 1) * (right - left + 1)
    if area > MAX_MERGED_CELLS:
        raise ValueError(f"merged cell count exceeds limit {MAX_MERGED_CELLS}")
    if merge_budget is not None:
        merge_budget[0] += area
        if merge_budget[0] > MAX_MERGED_CELLS:
            raise ValueError(f"merged cell count exceeds limit {MAX_MERGED_CELLS}")
    return top, left, bottom, right


def _merged_ranges(sheet_xml, merge_budget=None):
    ranges = []
    budget = merge_budget if merge_budget is not None else [0]
    stream = io.BytesIO(sheet_xml) if isinstance(sheet_xml, (bytes, bytearray)) else sheet_xml
    for _, node in _safe_iterparse(stream, keep_subtrees=frozenset()):
        if _local_tag(node.tag) == "mergeCell":
            ref = node.get("ref")
            if ref:
                ranges.append(_parse_merge_ref(ref, budget))
    return ranges


def _hidden_by_a_merge(merged, row, column):
    return any(
        top <= row <= bottom and left <= column <= right and (row, column) != (top, left)
        for top, left, bottom, right in merged
    )


def _worksheet_parts(
    archive: zipfile.ZipFile,
    names: list[str],
    budget: list[int],
    rels_root=None,
) -> list[str]:
    name_set = set(names)
    parts = [n for n in names if "/worksheets/" in n.lower() and n.lower().endswith(".xml")]
    seen = set(parts)
    if rels_root is None and "xl/_rels/workbook.xml.rels" in name_set:
        rels_root = _safe_fromstring(_read_archive_part(archive, "xl/_rels/workbook.xml.rels", budget=budget))
    if rels_root is not None:
        for rel in rels_root:
            rel_type = rel.get("Type") or ""
            target = rel.get("Target") or ""
            if rel_type.endswith("/worksheet") and target:
                part_name = _resolve_rel_target(target)
                if part_name in name_set and part_name not in seen:
                    seen.add(part_name)
                    parts.append(part_name)
    return parts


def _validate_workbook_archive(archive: zipfile.ZipFile) -> None:
    validate_archive(archive)
    names = archive.namelist()
    budget = [0]
    merge_budget = [0]
    for part_name in _worksheet_parts(archive, names, budget):
        with open_zip_member(
            archive,
            part_name,
            budget=budget,
            max_member_bytes=MAX_XML_PART_BYTES,
            max_bytes=MAX_ARCHIVE_BYTES,
        ) as part:
            _merged_ranges(part, merge_budget=merge_budget)


_UNQUOTED_EXT_RE = re.compile(r"\[\d+\][^!\[\]\"']*!")
_QUOTED_EXT_RE = re.compile(r"^\[\d+\]")


def _scan_formula_tokens(expr: str):
    """Yield ('ext', None, None, False) for external refs or ('name', ident_cf, qual_sheet_cf, is_call)."""
    s = expr.lstrip()
    if s.startswith("="):
        s = s[1:]
    n = len(s)
    i = 0
    qual_sheet = None
    while i < n:
        ch = s[i]
        if ch == '"':
            qual_sheet = None
            i += 1
            while i < n:
                if s[i] == '"':
                    if i + 1 < n and s[i + 1] == '"':
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            continue
        if ch == "'":
            i += 1
            buf = []
            while i < n:
                if s[i] == "'":
                    if i + 1 < n and s[i + 1] == "'":
                        buf.append("'")
                        i += 2
                        continue
                    i += 1
                    break
                buf.append(s[i])
                i += 1
            quoted = "".join(buf)
            if i < n and s[i] == "!":
                i += 1
                if _QUOTED_EXT_RE.match(quoted):
                    yield ("ext", None, None, False)
                    qual_sheet = None
                else:
                    qual_sheet = quoted.casefold()
            else:
                qual_sheet = None
            continue
        if ch == "[":
            match = _UNQUOTED_EXT_RE.match(s, i)
            if match:
                yield ("ext", None, None, False)
                i = match.end()
                qual_sheet = None
                continue
            depth = 1
            i += 1
            while i < n and depth > 0:
                if s[i] == "[":
                    depth += 1
                elif s[i] == "]":
                    depth -= 1
                i += 1
            qual_sheet = None
            continue
        if ch.isalpha() or ch in ("_", "\\"):
            start = i
            i += 1
            while i < n and (s[i].isalnum() or s[i] in ("_", ".", "?", "\\")):
                i += 1
            ident = s[start:i]
            if start > 0 and s[start - 1] == "$":
                qual_sheet = None
                continue
            if i < n and s[i] == "!":
                qual_sheet = ident.casefold()
                i += 1
                continue
            if i < n and s[i] == ":" and qual_sheet is None:
                end_3d = i + 1
                while end_3d < n and (s[end_3d].isalnum() or s[end_3d] in ("_", ".", "?", "\\")):
                    end_3d += 1
                if end_3d > i + 1 and end_3d < n and s[end_3d] == "!":
                    qual_sheet = None
                    i = end_3d + 1
                    continue
            is_call = i < n and s[i] == "("
            yield ("name", ident.casefold(), qual_sheet, is_call)
            qual_sheet = None
            continue
        if not ch.isspace():
            qual_sheet = None
        i += 1


def _resolve_def_key(ident_cf, qual_sheet_cf, current_scope, defs, sheet_idx_by_name):
    if qual_sheet_cf is not None:
        target_scope = sheet_idx_by_name.get(qual_sheet_cf)
        if target_scope is None:
            return None
        if (ident_cf, target_scope) in defs:
            return (ident_cf, target_scope)
        return (ident_cf, None) if (ident_cf, None) in defs else None
    if current_scope is not None and (ident_cf, current_scope) in defs:
        return (ident_cf, current_scope)
    return (ident_cf, None) if (ident_cf, None) in defs else None


def _expr_reaches_external(expr, current_scope, external_defs, defs, lambda_defs, sheet_idx_by_name) -> bool:
    for kind, ident_cf, qual_sheet_cf, is_call in _scan_formula_tokens(expr):
        if kind == "ext":
            return True
        key = _resolve_def_key(ident_cf, qual_sheet_cf, current_scope, defs, sheet_idx_by_name)
        if key is None:
            continue
        if is_call and key not in lambda_defs:
            continue
        if key in external_defs:
            return True
    return False


def _existing_cells(ws):
    if not hasattr(ws, "iter_rows"):  
        return []
    return [ws._cells[key] for key in sorted(ws._cells)]


def external_links_at_risk(filename):
    try:
        with zipfile.ZipFile(filename) as archive:
            validate_archive(archive)
            names = archive.namelist()
            budget = [0]
            merge_budget = [0]
            rels_root = None
            if "xl/_rels/workbook.xml.rels" in names:
                rels_root = _safe_fromstring(
                    _read_archive_part(archive, "xl/_rels/workbook.xml.rels", budget=budget)
                )
            has_external = any(n.lower().startswith("xl/externallinks/") for n in names) or (
                rels_root is not None
                and any((rel.get("Type") or "").endswith("/externalLink") for rel in rels_root)
            )
            if not has_external:
                for part_name in _worksheet_parts(archive, names, budget, rels_root=rels_root):
                    with open_zip_member(
                        archive,
                        part_name,
                        budget=budget,
                        max_member_bytes=MAX_XML_PART_BYTES,
                        max_bytes=MAX_ARCHIVE_BYTES,
                    ) as part:
                        _merged_ranges(part, merge_budget=merge_budget)
                return []

            workbook = _safe_fromstring(_read_archive_part(archive, "xl/workbook.xml", budget=budget))
            main_ns, rel_ns = _workbook_namespaces(workbook)
            if rels_root is None:
                rels_root = _safe_fromstring(
                    _read_archive_part(archive, "xl/_rels/workbook.xml.rels", budget=budget)
                )
            rel_map = {
                rel.get("Id"): (rel.get("Target"), rel.get("Type") or "")
                for rel in rels_root
            }

            sheets_el = workbook.find(f"{main_ns}sheets")
            sheets_list = list(sheets_el) if sheets_el is not None else []
            sheet_idx_by_name = {
                (sh.get("name") or "").casefold(): idx
                for idx, sh in enumerate(sheets_list)
                if sh.get("name")
            }

            defined_el = workbook.find(f"{main_ns}definedNames")
            defs = {}
            for dn in (defined_el if defined_el is not None else ()):
                raw_name = (dn.get("name") or "").strip()
                if not raw_name:
                    continue
                raw_scope = dn.get("localSheetId")
                scope = int(raw_scope) if raw_scope is not None else None
                defs[(raw_name.casefold(), scope)] = dn.text or ""

            lambda_defs = {
                key
                for key, text in defs.items()
                if any(
                    kind == "name" and ident == "lambda" and is_call
                    for kind, ident, _, is_call in _scan_formula_tokens(text)
                )
            }
            while True:
                added_lambdas = {
                    key
                    for key, text in defs.items()
                    if key not in lambda_defs
                    and any(
                        kind == "name"
                        and _resolve_def_key(ident, qual_sheet, key[1], defs, sheet_idx_by_name) in lambda_defs
                        for kind, ident, qual_sheet, _ in _scan_formula_tokens(text)
                    )
                }
                if not added_lambdas:
                    break
                lambda_defs |= added_lambdas

            external_defs = set()
            while True:
                added = {
                    key
                    for key, text in defs.items()
                    if key not in external_defs
                    and _expr_reaches_external(
                        text,
                        key[1],
                        external_defs,
                        defs,
                        lambda_defs,
                        sheet_idx_by_name,
                    )
                }
                if not added:
                    break
                external_defs |= added

            at_risk = []
            checked_parts = set()
            for sheet_idx, sheet in enumerate(sheets_list):
                rel_info = rel_map.get(sheet.get(f"{rel_ns}id"))
                if not rel_info:
                    continue
                target, rel_type = rel_info
                if not target:
                    continue
                part_name = _resolve_rel_target(target)
                is_ws = rel_type.endswith("/worksheet") if rel_type else ("/worksheets/" in part_name.lower())
                if not is_ws or part_name not in names:
                    continue
                checked_parts.add(part_name)
                sheet_name = sheet.get("name")
                shared_ext_si = set()
                pending_shared = {}
                with open_zip_member(
                    archive,
                    part_name,
                    budget=budget,
                    max_member_bytes=MAX_XML_PART_BYTES,
                    max_bytes=MAX_ARCHIVE_BYTES,
                ) as part:
                    for _, node in _safe_iterparse(part, keep_subtrees=frozenset(("c",))):
                        if _local_tag(node.tag) == "mergeCell":
                            ref = node.get("ref")
                            if ref:
                                _parse_merge_ref(ref, merge_budget)
                            continue
                        if node.tag != f"{main_ns}c":
                            continue
                        coord = node.get("r")
                        if coord is None:
                            raise ValueError("a cell without its address")
                        formula = node.find(f"{main_ns}f")
                        if formula is None or formula.get("t") == "dataTable":
                            continue
                        f_text = (formula.text or "").strip()
                        si = formula.get("si")
                        inline = node.find(f"{main_ns}is")
                        val_text = (
                            _rich_text(inline, main_ns)
                            if inline is not None
                            else (node.findtext(f"{main_ns}v") or "")
                        )
                        is_uncached = val_text == ""
                        reaches_out = False
                        if f_text:
                            reaches_out = _expr_reaches_external(
                                f_text,
                                sheet_idx,
                                external_defs,
                                defs,
                                lambda_defs,
                                sheet_idx_by_name,
                            )
                            if reaches_out and formula.get("t") == "shared" and si is not None:
                                shared_ext_si.add(si)
                                if si in pending_shared:
                                    for pending_coord in pending_shared.pop(si):
                                        at_risk.append(f"{sheet_name}!{pending_coord}")
                        elif formula.get("t") == "shared" and si is not None:
                            if si in shared_ext_si:
                                reaches_out = True
                            elif is_uncached:
                                pending_shared.setdefault(si, []).append(coord)
                        if reaches_out and is_uncached:
                            at_risk.append(f"{sheet_name}!{coord}")

            for part_name in _worksheet_parts(archive, names, budget, rels_root=rels_root):
                if part_name not in checked_parts:
                    with open_zip_member(
                        archive,
                        part_name,
                        budget=budget,
                        max_member_bytes=MAX_XML_PART_BYTES,
                        max_bytes=MAX_ARCHIVE_BYTES,
                    ) as part:
                        _merged_ranges(part, merge_budget=merge_budget)

            return at_risk
    except (zipfile.BadZipFile, OSError):
        return []


def recalc(filename, timeout=30, force=False):
    if not Path(filename).exists():
        return {"error": f"File {filename} does not exist"}

    abs_path = str(Path(filename).absolute())

    if not os.access(abs_path, os.W_OK):
        return {"error": f"{filename} is not writable; recalculation rewrites the file in place"}

    try:
        get_soffice_env()
    except Exception as e:  
        return {"error": f"Could not prepare the LibreOffice environment: {e}"}

    if not force:
        try:
            at_risk = external_links_at_risk(filename)
        except Exception as e:  
            return {"error": f"Could not inspect {filename} for external links: {e}"}
        if at_risk:
            shown = at_risk[:MAX_LOCATIONS]
            return {
                "error": (
                    "Refusing to recalculate: this workbook links to another workbook, and "
                    f"{len(at_risk)} linked cell(s) have lost their cached value (openpyxl strips "
                    "these on save). Recalculating would resolve them to #NAME? and delete the "
                    "external links for good. Copy those cells' values from the original file "
                    "before saving, or pass --force to accept the loss. Charts and conditional "
                    "formats can hold external references too, so this list may not be exhaustive."
                ),
                "external_link_cells": shown,
                "external_link_cells_truncated": max(0, len(at_risk) - len(shown)),
            }

    if force and zipfile.is_zipfile(abs_path):
        try:
            with zipfile.ZipFile(abs_path) as archive:
                _validate_workbook_archive(archive)
        except Exception as e:
            return {"error": f"Could not validate {filename}: {e}"}

    with tempfile.TemporaryDirectory(
        prefix="recalc-lo-profile-", ignore_cleanup_errors=True
    ) as profile_dir:
        return _recalc_with_profile(filename, abs_path, timeout, Path(profile_dir))


def _recalc_with_profile(filename, abs_path, timeout, profile_dir: Path):
    started = time.monotonic()
    profile_url, err = setup_libreoffice_macro(profile_dir, timeout=timeout)
    if err:
        return {"error": err}

    timeout = max(5, int(timeout - (time.monotonic() - started)))

    before = _stamp(abs_path)

    args = [
        f"-env:UserInstallation={profile_url}",
        "--headless",
        "--norestore",
        "vnd.sun.star.script:Standard.Module1.RecalculateAndSave?language=Basic&location=application",
        abs_path,
    ]

    timed_out = f"LibreOffice timed out after {timeout}s; formulas were NOT recalculated. Re-run with a longer timeout."

    try:
        result = run_soffice(args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"error": timed_out}
    except FileNotFoundError:
        return {"error": SOFFICE_MISSING}

    if result.returncode != 0:
        detail = (result.stderr or "").strip() or f"soffice exited {result.returncode}"
        return {"error": f"LibreOffice failed to recalculate: {detail}"}

    if _stamp(abs_path) == before:
        return {
            "error": (
                "LibreOffice exited cleanly but never rewrote the file, so nothing was "
                "recalculated. Check that no other LibreOffice instance is running, then retry."
            )
        }

    return _report(filename)


def _scan_xml(filename):
    error_details = {err: [] for err in EXCEL_ERRORS}
    formula_count = 0
    merge_checks = 0
    merge_budget = [0]

    with zipfile.ZipFile(filename) as archive:
        validate_archive(archive)
        names = archive.namelist()
        budget = [0]
        workbook = _safe_fromstring(_read_archive_part(archive, "xl/workbook.xml", budget=budget))
        main_ns, rel_ns = _workbook_namespaces(workbook)
        rels_root = _safe_fromstring(_read_archive_part(archive, "xl/_rels/workbook.xml.rels", budget=budget))
        rel_map = {
            rel.get("Id"): (rel.get("Target"), rel.get("Type") or "")
            for rel in rels_root
        }

        shared_equals = set()
        if "xl/sharedStrings.xml" in names:
            with open_zip_member(
                archive,
                "xl/sharedStrings.xml",
                budget=budget,
                max_member_bytes=MAX_XML_PART_BYTES,
                max_bytes=MAX_ARCHIVE_BYTES,
            ) as part:
                index = 0
                for _, node in _safe_iterparse(part, keep_subtrees=frozenset(("si",))):
                    if node.tag != f"{main_ns}si":
                        continue
                    text = _rich_text(node, main_ns).replace("x005F_", "")
                    if text.startswith("="):
                        shared_equals.add(index)
                    index += 1

        checked_parts = set()
        sheets_el = workbook.find(f"{main_ns}sheets")
        for sheet in (sheets_el if sheets_el is not None else ()):
            rel_info = rel_map.get(sheet.get(f"{rel_ns}id"))
            if not rel_info:
                continue
            target, rel_type = rel_info
            if not target:
                continue
            part_name = _resolve_rel_target(target)
            is_ws = rel_type.endswith("/worksheet") if rel_type else ("/worksheets/" in part_name.lower())
            if not is_ws or part_name not in names:
                continue
            checked_parts.add(part_name)
            found = []
            with open_zip_member(
                archive,
                part_name,
                budget=None,
                max_member_bytes=MAX_XML_PART_BYTES,
                max_bytes=MAX_ARCHIVE_BYTES,
            ) as part:
                merged = _merged_ranges(part, merge_budget=merge_budget)
            with open_zip_member(
                archive,
                part_name,
                budget=budget,
                max_member_bytes=MAX_XML_PART_BYTES,
                max_bytes=MAX_ARCHIVE_BYTES,
            ) as part:
                for _, node in _safe_iterparse(part, keep_subtrees=frozenset(("c",))):
                    if node.tag != f"{main_ns}c":
                        continue
                    if node.get("r") is None:
                        raise ValueError("a cell without its address")
                    formula = node.find(f"{main_ns}f")
                    is_formula = formula is not None and formula.get("t") != "dataTable"
                    err = None
                    cell_type = node.get("t", "n")
                    if cell_type == "s":
                        v_text = node.findtext(f"{main_ns}v")
                        if v_text is not None:
                            index = int(v_text)
                            is_formula = is_formula or (formula is None and index in shared_equals)
                    elif cell_type == "e":
                        err = _exact_error(node.findtext(f"{main_ns}v"))
                    elif cell_type not in ("n", "b", "d"):
                        inline = node.find(f"{main_ns}is")
                        text = node.findtext(f"{main_ns}v") if inline is None else _rich_text(inline, main_ns)
                        is_formula = is_formula or (formula is None and (text or "").startswith("="))
                    if not is_formula and not err:
                        continue
                    row, column = _row_major(node.get("r"))
                    merge_checks += len(merged)
                    if merge_checks > MAX_MERGE_CHECKS:
                        raise ValueError("too many merged ranges for this many cells")
                    if _hidden_by_a_merge(merged, row, column):
                        continue
                    formula_count += is_formula
                    if err:
                        found.append(((row, column), err, node.get("r")))
            for _, err, coordinate in sorted(found):
                error_details[err].append(f"{sheet.get('name')}!{coordinate}")

        for part_name in _worksheet_parts(archive, names, budget, rels_root=rels_root):
            if part_name not in checked_parts:
                with open_zip_member(
                    archive,
                    part_name,
                    budget=budget,
                    max_member_bytes=MAX_XML_PART_BYTES,
                    max_bytes=MAX_ARCHIVE_BYTES,
                ) as part:
                    _merged_ranges(part, merge_budget=merge_budget)

    return error_details, formula_count


def _scan_with_openpyxl(filename):
    from openpyxl import load_workbook
    from openpyxl.worksheet.formula import ArrayFormula

    if zipfile.is_zipfile(filename):
        with zipfile.ZipFile(filename) as archive:
            _validate_workbook_archive(archive)

    error_details = {err: [] for err in EXCEL_ERRORS}
    wb = load_workbook(filename, data_only=True)
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        for cell in _existing_cells(ws):
            if cell.data_type == "e" and isinstance(cell.value, str):
                err = _exact_error(cell.value)
                if err:
                    error_details[err].append(f"{sheet_name}!{cell.coordinate}")
    wb.close()

    wb_formulas = load_workbook(filename, data_only=False)
    formula_count = 0
    for sheet_name in wb_formulas.sheetnames:
        ws = wb_formulas[sheet_name]
        for cell in _existing_cells(ws):
            v = cell.value
            if isinstance(v, ArrayFormula):
                v = v.text
            if isinstance(v, str) and v.startswith("="):
                formula_count += 1
    wb_formulas.close()

    return error_details, formula_count


def _report(filename):
    try:
        try:
            error_details, formula_count = _scan_xml(filename)
        except ValueError:
            raise
        except Exception:
            error_details, formula_count = _scan_with_openpyxl(filename)
    except Exception as e:
        return {"error": str(e)}

    total_errors = sum(len(locations) for locations in error_details.values())
    result = {
        "status": "success" if total_errors == 0 else "errors_found",
        "total_errors": total_errors,
        "error_summary": {},
    }

    for err_type, locations in error_details.items():
        if locations:
            entry = {"count": len(locations), "locations": locations[:MAX_LOCATIONS]}
            if len(locations) > MAX_LOCATIONS:
                entry["locations_truncated"] = len(locations) - MAX_LOCATIONS
            result["error_summary"][err_type] = entry

    result["total_formulas"] = formula_count
    return result


def main():
    args = [a for a in sys.argv[1:] if a != "--force"]
    force = "--force" in sys.argv[1:]

    if not args:
        print("Usage: python recalc.py <excel_file> [timeout_seconds] [--force]")
        print("\nRecalculates all formulas in an Excel file using LibreOffice")
        print("\nReturns JSON with error details:")
        print("  - status: 'success' or 'errors_found'")
        print("  - total_errors: Total number of Excel errors found")
        print("  - total_formulas: Number of formulas in the file")
        print("  - error_summary: Breakdown by error type with locations")
        print("    - #VALUE!, #DIV/0!, #REF!, #NAME?, #NULL!, #NUM!, #N/A")
        print("\nOn any failure the JSON has an 'error' key and no 'status'.")
        print("--force recalculates even when it would destroy external links.")
        sys.exit(1)

    filename = args[0]
    try:
        timeout = int(args[1]) if len(args) > 1 else 30
    except ValueError:
        result = {"error": f"timeout must be an integer number of seconds, got {args[1]!r}"}
        print(json.dumps(result, indent=2))
        sys.exit(1)

    result = recalc(filename, timeout, force=force)
    print(json.dumps(result, indent=2))
    sys.exit(1 if "error" in result else 0)


if __name__ == "__main__":
    main()
