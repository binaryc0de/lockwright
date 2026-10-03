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


def is_doc(rel: str) -> bool:
    return "/assets/docs/" in rel


def wanted(rel: str) -> int:
    name = os.path.basename(rel)
    if NON_COLOUR.search(name):
        return LIMIT
    if rel.startswith(SURFACE_DIRS):
        return LIMIT
    if rel.startswith(PROP_DIRS) and not name.startswith(TEXT_PROPS):
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
