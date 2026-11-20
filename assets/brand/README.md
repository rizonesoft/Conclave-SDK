# Brand assets

The Conclave-SDK mark is the Conclave Agent OS mark in green: the same dark tile, a ring of seven nodes around a bright core, with spokes and a glow. The owner chose it on 2026-11-12 over the earlier cyan hexagon.

| File | Use |
| ---- | --- |
| `conclave-sdk-icon.svg` | The icon. The source for every size above 64 pixels. |
| `conclave-sdk-icon-small.svg` | A heavier drawing for 64 pixels and below, where thin lines close up. |
| `conclave-sdk-icon-512.png`, `conclave-sdk-icon-192.png` | Renders of the icon. |
| `conclave-sdk.ico` | Windows icon with 16 to 256 pixel frames; the base of the campaign launchers' icons. |
| `social-preview.svg`, `social-preview.png` | The 1280 by 640 image for the repository's social preview. |

## Colours

| Name | Value | Where |
| ---- | ----- | ----- |
| Tile, top | `#10221a` | Background gradient start |
| Tile, bottom | `#050c09` | Background gradient end, node centres |
| Tile edge | `#1d4532` | The inner border of the tile |
| Green | `#1ee08a` | Ring, spokes, nodes, glow |
| Core | `#9ef5c8` | The bright core |
| White | `#ffffff` | The centre of the core |

## Launcher icons

`pwsh scripts/start-run.ps1 -InstallShortcut` writes "Conclave-SDK Claude campaign" and "Conclave-SDK Gemini campaign" to the desktop, in the shape Office's and Isotone's campaign launchers have: the mark with the runner's badge in the bottom right (Claude Code's orange spark, Antigravity's blue Carbon sparkle). Their icons are rendered on the machine into `%LOCALAPPDATA%\Conclave-SDK` by `kits/launchers/templates/scripts/campaign-icon.py badge` (the launchers kit's renderer) and are never committed.

## Rendering

The SVG files are the source. Each was drawn once at 1024 pixels in headless Chrome, and the PNG and ICO files were made from those renders by the launchers kit's `campaign-icon.py` (`kits/launchers/templates/scripts/`; area resizing, standard library only): `campaign-icon.py frames <large.png> <small.png> conclave-sdk.ico` takes the small drawing up to 64 pixels. They are committed so that nothing in the repository needs an image library. Render them again only when an SVG changes.
