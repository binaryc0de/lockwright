#!/usr/bin/env python3
"""Texture size budget for the browser build (M5, ADR-0024).

Sets Godot texture import options so the exported game stays small enough to
load in a browser and light on GPU memory (integrated GPUs):
  - every 3D texture is VRAM compressed (S3TC/BPTC; normal maps as RGTC)
  - non-colour maps (normal, ORM/ARM, AO, roughness, metal): at most 1024 px
  - tiling CC0 surface colour maps (third_party materials): at most 1024 px
  - prop colour maps: at most 1024 px, except props whose textures carry text
    players read (TEXT_PROPS keep their full size)
  - printables (rooms/*/assets/docs, read up close as text): left lossless
Godot's editor would switch 3D textures to VRAM compression after seeing them
used in 3D; our headless workflow never does, so this sets it explicitly.
Run it after adding assets (tools/test.sh checks nothing is over budget):
    tools/texture_budget.py [--check]
"""
import os, re, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "game")
LIMIT = 1024
NON_COLOUR = re.compile(r"(?i)(normal|_nor_|_nor\.|orm|_arm_|_arm\.|ambientocclusion|roughness|metal)")
NORMAL = re.compile(r"(?i)(normal|_nor_|_nor\.)")
# Props whose colour textures carry labels, numbers or screens players read.
TEXT_PROPS = ("patch_panel_8", "exit_keypad_6", "keypad_4", "intercom_panel", "wall_clock_countdown",
              "laptop_open", "ups_tower", "server_rack_42u", "filing_cabinet_keypad", "monitor_24")
PROP_DIRS = ("assets/core/props/", "assets/core/third_party/polyhaven/")
SURFACE_DIRS = ("assets/core/third_party/ambientcg/", "assets/core/third_party/polyhaven/concrete_floor_painted/",
                "assets/core/third_party/polyhaven/painted_plaster_wall/")


# Room-specific props and CC0 downloads (ADR-0030) follow the core rules.
ROOM_PROP = re.compile(r"^rooms/[a-z0-9_]+/assets/(props|third_party)/")


def is_doc(rel: str) -> bool:
    return "/assets/docs/" in rel


# Room-specific assets download with the room's pack in the browser, on top
# of the client: props and CC0 model textures are capped at 512 px (seen from
# a metre or two), tiling room surfaces at 1024; text-bearing colour maps
# keep their size (ADR-0034).
ROOM_LIMIT = 512
# Room-prop colour maps that carry lettering players read (dials, numerals,
# signs); everything else of a room prop is capped.
ROOM_TEXT_MAPS = ("automaton_songbird_T_automaton_songbird_enamel_base_color",
                  "chime_bars_5_T_chime_bars_5_wood_base_color",
                  "longcase_clock_T_longcase_clock_dial_plaque_base_color",
                  "mantel_clock_drawer_T_mantel_clock_drawer_base_color",
                  "pegboard_tools_T_pegboard_tools_wood_paint_base_color",
                  # R5, the undercroft (ADR-0037): marks, numerals, letters, inscription
                  "gate_ring_lock_T_gate_ring_lock_brass_base_color",
                  "gate_ring_lock_T_gate_ring_lock_iron_base_color",
                  "great_dial_T_great_dial_paint_base_color",
                  "tomb_chest_T_tomb_chest_base_color",
                  "maren_bench_T_maren_bench_metal_base_color",
                  "vault_door_T_vault_door_brass_base_color")
ROOM_SURFACE = re.compile(r"^rooms/[a-z0-9_]+/assets/third_party/polyhaven/[^/]+/[^/]+$")


def wanted(rel: str) -> int:
    name = os.path.basename(rel)
    if ROOM_PROP.match(rel):
        if ROOM_SURFACE.match(rel):
            return LIMIT
        if name.startswith(ROOM_TEXT_MAPS):
            return 0
        return ROOM_LIMIT
    if NON_COLOUR.search(name):
        return LIMIT
    if rel.startswith(SURFACE_DIRS):
        return LIMIT
    if (rel.startswith(PROP_DIRS) or ROOM_PROP.match(rel)) and not name.startswith(TEXT_PROPS):
        return LIMIT
    return 0


def main() -> int:
    check = "--check" in sys.argv
    bad, changed = [], 0
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in (".godot", "addons", "tests", "reports", "ui")]
        for f in files:
            if not f.endswith((".png.import", ".jpg.import", ".webp.import")):
                continue
            path = os.path.join(dirpath, f)
            rel = os.path.relpath(path, ROOT).replace(os.sep, "/")[: -len(".import")]
            want = wanted(rel)
            text = open(path).read()
            if 'importer="texture"' not in text:
                continue
            new = text
            if want:
                m = re.search(r"^process/size_limit=(\d+)$", new, re.M)
                cur = int(m.group(1)) if m else 0
                if not cur or cur > want:
                    new = new.replace(m.group(0), f"process/size_limit={want}") if m else new.rstrip("\n") + f"\nprocess/size_limit={want}\n"
            if not is_doc(rel):
                new = re.sub(r"^compress/mode=\d+$", "compress/mode=2", new, flags=re.M)
                if NORMAL.search(os.path.basename(rel)):
                    new = re.sub(r"^compress/normal_map=\d+$", "compress/normal_map=1", new, flags=re.M)
            if new == text:
                continue
            if check:
                bad.append(rel)
                continue
            open(path, "w").write(new)
            changed += 1
    if check:
        for r in bad:
            print(f"over budget: {r} (run tools/texture_budget.py)")
        return 1 if bad else 0
    print(f"texture budget: {changed} import file(s) updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
