# Night Shift - game master notes

Never shown to players. Par 35-45 minutes for a team of 3. Four threads that converge on one meta code.

## Layout
- **Office** (6 m x 5 m): desk with monitor, laptop and an unlocked top drawer (north wall); whiteboard (north wall); filing cabinet with a 4-digit keypad, pinboard and fire inspection certificate (south wall); exit door, its override panel, the intercom and the UPS countdown clock (west wall).
- **Cage** (2.5 m x 5 m, east side), behind a wire-mesh wall and a maglocked cage door: server rack with patch panel P1 and the "RACK 062" stencil, UPS.

## Solution path
1. **find_uv** - Open the top desk drawer, pick up the UV torch under the papers.
2. **open_cabinet** - Select the UV torch near the whiteboard: four violet digits (per-session `cabinet_code`) appear next to "Filing cabinet code: UV pen". Enter them on the filing cabinet keypad and open the drawer: laminated network diagram + USB stick (flavour only in the prototype).
3. **hack_intranet** (parallel from minute one) - Sticky note on the monitor: user `mreyes`, "pw: same as the guest wifi one". Guest WiFi card on the pinboard, back side: `Kestrel#2019`. The laptop shows the intranet's connection card; log in from your own browser, open ticket `?id=1042`, try neighbouring ids, find the maglock vendor's facilities ticket with the override token (the flag), paste it into the laptop. The cage maglock releases.
4. **restore_power** - In the cage, patch P1 per the diagram: A->3, B->7, C->1, D->5 (cables tagged by letter and stripe count). The exit override panel powers up (status shows LOCKED).
5. **override_door** - Plate above the panel: "MAGLOCK OVERRIDE: SITE + RACK". Certificate: SITE 417. Rack stencil: RACK 062. Enter `417062`. Session won; the exit door opens.

## Common sticking points
- Not realising the UV torch must be *selected* in the inventory to reveal UV ink.
- Not flipping the WiFi card (the front says "Password: see back").
- Treating the intranet as a blind pentest: steer them to the sticky note and card first.
- Typing colours for the patch cables: the diagram lists letters, the cables carry letter tags.
