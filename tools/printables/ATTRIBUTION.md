# Printable provenance

All templates, emblem/pictogram geometry, signature strokes, original handwriting
alphabet, rasterizer and wear overlays were authored for escapebox. Request text
comes from the owner/orchestrator's `assets/requests/printables/` files. No downloaded
photographs, textures, SVGs or font files are used. No font binaries are copied into
the repository or delivered PNGs.

Printed lettering uses only **Inter**, already bundled with Blender 5.2.2,
as expressly allowed by the printable request. Author: **The Inter Project
Authors**, copyright 2020. Source: https://rsms.me/inter/ and
https://github.com/rsms/inter . License: **SIL Open Font License 1.1**.
Installed input: `5.2/datafiles/fonts/Inter.woff2` relative to Blender's binary.
This attribution/license was verified from the installed distribution's
`license/license.md`, Fonts section, and `license/spdx/OFL-1.1.txt`.
The renderer uses this local input; it never fetches either source URL.
The owner's express bundled-font allowance covers this OFL font, while the
CC0/CC-BY restriction continues to apply to any third-party art assets.

The CPU renderer uses Python's standard library and NumPy already bundled with
Blender. These are rendering tools and are not shipped as asset inputs.
