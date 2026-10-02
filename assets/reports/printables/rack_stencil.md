# rack_stencil

Built the exact one-line clue **RACK 062** as white spray-enamel paint over a
transparent background. The 2048 x 683 RGBA sRGB texture is paint only; the
black blanking plate remains separate geometry. Original drawn, chamfered
stencil contours use genuine transparent bridges in R, A, 0 and 6. The 6 has a
diagonal upper ascender, an open upper-right gap and one lower counter, so it
does not resemble 8 or b. No font, downloaded artwork or third-party texture
was used.

Cap height is 444 px (65.0% of the image), approximately 91 mm on the requested
0.42 x 0.14 m plate. Lettering is horizontally centred with about 147 px side
margins. Original seeded wear adds subtle uneven spray coverage, fine pinholes,
short scuffs, a restrained overspray halo and two small gravity drips beneath
the letters. Drips avoid the digits; the gap between 0 and 6 remains clear.
Paint variation is in colour and alpha, without baked lighting or a plate
background. The source is deterministic and offline.

## Delivered files

- SVG source: `tools/printables/templates/rack_stencil.svg`, with the requested
  text filled into `<tspan id="rack_number">` from the request.
- Drawn lettering and wear: `tools/printables/rack_stencil.py`.
- Pipeline entry point: `tools/printables/build_printables.sh rack_stencil`.
- Output: `game/rooms/night_shift/assets/docs/rack_stencil.png` (2048 x 683 RGBA).
- Legibility preview: `assets/previews/printables/rack_stencil_25.png`
  (512 x 171, 111 px nominal cap height, composited over black for review).
- Metadata: `assets/meta/printables/rack_stencil.json`, including current source
  and request hashes, exact text, dimensions, seeds and artifact hashes.

Texture SHA-256:
`9da20987933da7188ae42f2458f1b86ad6a4dd13905b17a0330d13b6feed7ed3`.

Preview SHA-256:
`8df22cb0e811475bbf8787d494e6e961cc29f5ff3912c1f033808212266cbcac`.

## Inspection and verification actually run

Personally inspected the delivered RGBA texture, a full-size black-backed
review copy and the 25% preview. **RACK 062 is unambiguous** in the quarter-size
preview: the 0 and 6 are distinct, the 6 stays open at the upper right, and the
2 has a clear descending diagonal and bottom bar. Also read all seven glyphs
in an aggressive 128 x 43 review copy (about 28 px caps). Review copies live
only in ignored `assets/cache/printables/`.

On the Alienware development machine, 2026-10-02, the final build ran through
the existing shared flock with Blender **5.2.2 LTS**, factory startup, four
threads and disabled audio. All rasterization used bundled Python/NumPy on
CPU; no render engine, GPU context, network or package installation was used.

Commands run with Blender's bundled `python3.13 -B`:

```text
tools/printables/build_printables.sh rack_stencil
tools/printables/verify.py --record rack_stencil
tools/printables/build_printables.sh rack_stencil
tools/printables/verify.py --compare rack_stencil
tools/printables/verify.py
```

The first final build and selected record check passed. Independent PNG
decoding checked CRCs, sRGB/gamma chunks, actual dimensions, empty RGB in all
zero-alpha texels, transparent margins, sufficient opaque paint coverage,
the empty 0/6 gap, the open upper-right gap of the 6 and preview/output hashes.
The read-only default verifier also passed for all seven current printable
outputs, including the six existing ones. Python syntax and the current
source/request metadata hashes passed independent checks.

Both final builds completed with exit 0. The selected `--compare` check returned
exit 0 and reported:

```text
PASS reproducibility: all 1 outputs, 1 previews and 1 metadata records byte-identical
```

The PNG, quarter-size preview and metadata are byte-identical, with no timestamp
exception. The first checksum manifest is
`assets/cache/printables/rack_stencil_first_build.sha256.json`; the second build
log is `assets/cache/printables/rack_stencil_second_build.log`.

The first development attempt exposed faint overspray quantizing to zero alpha
with nonzero RGB. The final code clears those texels to zero RGBA before PNG
encoding; the successful build passes the independent transparency check.

## Scope and integration

No deviations from the request's content, dimensions or transparency. Shared
printable changes add stencil support, a black-backed review mode and optional
request selection in the verifier. Existing lettering, wear and document
render paths are retained. Only this asset was built or written; no other
asset files, runtime code, room scenes, room.yaml, shared Blender helpers or
request files were edited. No git commit was made.

Use the delivered paint texture on the black plate with alpha blending and
non-emissive paint. Physical plate roughness, lighting and any paint relief
remain material integration work. No 3D prop or additional PBR map was requested.
No in-engine screenshot or actual 2 m camera test is claimed; the 25% and
additional reduced preview checks establish texture legibility, while the
final lighting/distance check belongs to the room review. GLB-only
`tools/blender/build_assets.sh` and `tools/assetcheck` do not validate printables
(ADR-0014 and `assets/requests/printables/README.md`).
