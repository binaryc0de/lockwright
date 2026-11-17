# Night Shift printables

Run `tools/printables/build_printables.sh` from any directory. Optional arguments
select request IDs, for example `tools/printables/build_printables.sh wifi_card_front_back`.
Requires the already-installed Blender 5.2.x and `flock`. The runner shares
`assets/cache/.blender-build.lock` with the prop pipeline, uses factory startup,
four threads, disabled audio, and Blender's bundled Python/NumPy. No network,
package installation, system fonts, GPU context, or render engine is used.

Each document has one SVG template with `<tspan id="...">` placeholders. WiFi
front/back groups live in one template and are selected by `data-page`. Text is
read from the exact backtick strings (or whiteboard fenced block) in its request.
Blender's bundled Inter supplies the printed sans outlines. Handwriting uses
only the original stroke alphabet in `lettering.py`. The renderer tessellates
printed outlines and rasterizes all geometry on CPU at 2x antialiasing. SVG
templates are a restricted rendering source, not browser-authoritative previews:
`data-lettering="stroke"` selects the authored stroke alphabet; `data-width`
caps line width; `font-size` is the actual cap height in final pixels.

`overlays/surface.py` produces original, seeded surface layers: paper fibres and
handling discoloration, light print banding, laminate glints and scratches,
adhesive shading and a curled sticky-note edge, dry marker pressure variation,
and restrained LCD scanline variation. No wear covers the critical credentials
or site ID. Physical paper/card textures remain opaque. The whiteboard is RGBA
with zero alpha throughout its reserved UV-code interior.

Outputs go to the exact request paths under
`game/rooms/night_shift/assets/docs/`; quarter-size previews go to
`assets/previews/printables/`; metadata goes to `assets/meta/printables/`.
PNG encoding includes sRGB/gamma chunks and excludes timestamps. Metadata records
source/request/output hashes, exact text, cap sizes and dimensions without a
wall-clock timestamp. The request dimensions take precedence over Section 7's
general long-edge minimum: WiFi is 1536x1024 and the sticky note is 1024x1024.
Whiteboard and laptop preview heights round to the nearest pixel (316 and 321).
The whiteboard's quarter-size preview is composited onto white enamel for
legibility; the delivered full texture retains its transparent background.
An opaque full-size review copy goes only into ignored `assets/cache/printables/`.

For independent file and repeat-build verification, use Blender's bundled
Python executable to run `tools/printables/verify.py --record` after a first build,
run the builder again, then run `tools/printables/verify.py --compare`. This verifies
PNG CRCs, actual pixel dimensions, sRGB chunks, opacity and UV-interior pixels,
as well as comparing every output, preview and metadata file byte for byte.

The build checks exact text coverage, critical strings, required opacity and
the transparent UV rectangle. Visual review and repeat-build evidence live in
`assets/reports/printables/`. This batch contains no 3D props, so
`tools/blender/build_assets.sh` and the GLB-only `tools/assetcheck` do not apply
(see `assets/requests/printables/README.md`). Roughness/emission, inspect-scale
lighting and texture assignment remain integration work for Claude; no runtime
or room scene is changed by the renderer.

`rack_stencil` adds original polygon stencil contours, transparent counter
bridges, seeded spray density, pinholes, fine scuffs and two short letter drips.
Its 2048x683 RGBA output contains paint only. The 512x171 preview is composited
over black for legibility; a full black-backed review copy lives only in ignored
`assets/cache/printables/rack_stencil_on_black.png`. No font is used for it.
Build it with `tools/printables/build_printables.sh rack_stencil`. Run
`tools/printables/verify.py --record rack_stencil` using bundled Python, rebuild,
then run `tools/printables/verify.py --compare rack_stencil` to compare only its
output, preview and metadata. Selected verification uses a separate per-request
checksum manifest and also checks the clear 0/6 gap and open top of the six.

`network_diagram_laminated` (2048x1448) and `work_order` (1448x2048)
are built with `tools/printables/build_printables.sh network_diagram_laminated work_order`.
Their SVG templates use the same CPU pipeline and seeded laminate/paper overlays.
The diagram includes cable lettering, white bands and port numerals; verification
counts the actual white pixel runs at full and quarter size (A=1, B=2, C=3, D=0)
and checks the A→3, B→7, C→1, D→5 mapping. The work order adds original plus
and apostrophe pen strokes and opt-in `data-wrap="words"` text layout. Wrapped
fields retain the exact request string in metadata, with individual lines and
baselines recorded; `data-leading` and `data-height` define field spacing and
prevent overflow. All ten work-order strings are checked, including the double
space in the order title and three spaces before `Window:`. Coffee residue,
pen ticks/signature and corner laminate reflections are original SVG geometry.
For a selected two-build check, run bundled Python on `verify.py --record
network_diagram_laminated work_order`, rebuild, then use the same IDs with
`--compare`. Existing templates and outputs are unchanged.

