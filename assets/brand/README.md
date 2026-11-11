# Brand assets

The Conclave-SDK mark belongs to the same family as the Conclave Agent OS icon: the same dark tile, cyan ring and bright core. The ring is drawn as a hexagon, a kit box seen corner-on, and its three large nodes are the three agents the kits serve: Claude Code, Codex and Antigravity.

| File | Use |
| ---- | --- |
| `conclave-sdk-icon.svg` | The icon. The source for every size from 128 pixels up. |
| `conclave-sdk-icon-small.svg` | A heavier drawing for 64 pixels and below, where thin lines close up. |
| `conclave-sdk-icon-512.png`, `conclave-sdk-icon-192.png` | Renders of the icon. |
| `conclave-sdk.ico` | Windows icon with 16 to 256 pixel frames, used by the desktop shortcut. |
| `social-preview.svg`, `social-preview.png` | The 1280 by 640 image for the repository's social preview. |

## Colours

| Name | Value | Where |
| ---- | ----- | ----- |
| Tile, top | `#111c2e` | Background gradient start |
| Tile, bottom | `#060a12` | Background gradient end, node centres |
| Tile edge | `#1e3554` | The inner border of the tile |
| Cyan | `#00beff` | Ring, spokes, nodes |
| Core | `#91edff` | The bright core |
| White | `#ffffff` | The centre of the core |

## Rendering

The SVG files are the source. The PNG and ICO files were rendered from them once, by drawing each SVG in a headless browser at 1024 pixels and resizing with a Lanczos filter. They are committed so that nothing in the repository needs an image library. Render them again only when an SVG changes, and use the small drawing for every ICO frame up to 64 pixels.
