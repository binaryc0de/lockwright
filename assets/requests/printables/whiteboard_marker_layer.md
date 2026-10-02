# whiteboard_marker_layer

**Status:** open · **Requested by:** Claude Code, 2026-10-02 · **Used in:** room night_shift, `Office/Whiteboard` (puzzle A2 context; the UV code itself stays in-engine)
**Output:** `game/rooms/night_shift/assets/docs/whiteboard_marker_layer.png`, 2048 x 1262 px RGBA, transparent background, covering the whole `whiteboard_wall` surface (1.564 x 0.964 m; pixel (0,0) = top-left of the surface as seen from the front).

Dry-wipe marker writing by a tired sysadmin, drawn as strokes by the script (no fonts), blue marker for the list, black for the box and arrow, slightly uneven line weight and a few marker-starved strokes. Content, in the left 55 % of the board, cap height about 45 mm:

```
MIGRATION - NIGHT 2
[x] backup core-sw
[x] move DNS
[ ] cutover 23:30
Filing cabinet code:
UV pen (audit rule!)  -->
```

The arrow at the end of the last line must point right toward an **empty** rectangle drawn in black marker, its interior kept fully transparent: x 58 % to 88 % of the width, y 52 % to 80 % of the height from the top. The UV-ink code is rendered in-engine inside that box. Add a faint hand-drawn network sketch (three boxes and lines, no text) in the top right, nothing else.
