# Conclave Craft & Documents (`agy-craft`)

Antigravity design and document authoring bundle packaged for global deployment via `global/deploy.py --agent agy`.

## Contents

| Skill | Path | Focus |
| ----- | ---- | ----- |
| `frontend-design` | `skills/frontend-design/` | Anti-slop UI design plus browser visual verification |
| `docx` | `skills/docx/` | Word document creation, tracked edits, and OOXML checks |
| `xlsx` | `skills/xlsx/` | Spreadsheet modeling with live formulas and recalc checks |
| `pptx` | `skills/pptx/` | Structured slide decks, layouts, and OOXML validation |
| `pdf` | `skills/pdf/` | PDF text/table extraction, merging, and form filling |

## Runtime dependencies

Document and presentation helpers use local tools when invoked (`openpyxl`, `pandas`, `python-docx`, `pypdf`, `pdfplumber`, `pptxgenjs`, `sharp`, LibreOffice, Poppler). Import directly first; if a package is missing, install inside the project virtual environment or a temporary folder in `R:\scratch` rather than modifying global packages unnecessarily.

## Installation

```powershell
python global/deploy.py --agent agy
agy plugin validate plugins/agy/craft --strict
```
