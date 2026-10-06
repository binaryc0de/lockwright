#!/usr/bin/env python3
"""Plays a room in a real browser with the play bot (ADR-0038 addendum).

    tools/browserbot.py URL [--phone] [--limit 2400] [--out DIR] [--shots]

URL is the web client with ?room=<id>&deskbot=1 (keyboard and mouse; add
&deskdrag=1 to use items by dragging) or &touchbot=1 (with --phone: Chrome as
a Pixel 7 held sideways). Desktop play needs pointer lock, which a browser
only grants on a real click: when the game prints "DESKBOT: CLICK" this
clicks the page, as a player clicks to play. Exits 0 when the bot reports no
problems, 2 otherwise; the console goes to DIR/console.log. With --shots it
saves DIR/step-NNN.png after every solution step, to review a run by eye.
"""
import argparse, os, sys, time
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("SKIP: python playwright not installed"); sys.exit(0)

ap = argparse.ArgumentParser()
ap.add_argument("url"); ap.add_argument("--phone", action="store_true")
ap.add_argument("--limit", type=float, default=2400); ap.add_argument("--out", default="")
ap.add_argument("--shots", action="store_true")
a = ap.parse_args()
out = a.out or os.path.join(os.environ.get("TMPDIR", "/tmp"), "escapebox-browserbot")
os.makedirs(out, exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True, args=["--use-angle=gl", "--ignore-gpu-blocklist",
        # A player has always tapped or clicked to get here, which lets audio
        # start; without it every sound retries and a touch run crawls.
        "--autoplay-policy=no-user-gesture-required"])
    if a.phone:
        dev = dict(p.devices["Pixel 7 landscape"]); dev.pop("default_browser_type", None)
        page = b.new_context(**dev).new_page()
    else:
        page = b.new_page(viewport={"width": 1280, "height": 720})
    logs = []
    page.on("console", lambda m: logs.append(m.text))
    page.goto(a.url)
    seen, t0 = 0, time.time()
    w, h = page.viewport_size["width"], page.viewport_size["height"]
    while time.time() - t0 < a.limit and not any(": done," in l for l in logs):
        page.wait_for_timeout(250)
        new, seen = logs[seen:], len(logs)
        if any("DESKBOT: CLICK" in l for l in new):
            page.mouse.click(w / 2, h / 2)
        for l in new:  # progress as it happens (the full console is saved at the end)
            if "BOT: step " in l or "-FAIL" in l:
                print(l, flush=True)
        if a.shots:
            import re
            for l in new:
                m = re.search(r"BOT: step (\d+) ", l)
                if m:
                    page.screenshot(path=os.path.join(out, "step-%03d.png" % int(m.group(1))))
    page.screenshot(path=os.path.join(out, "end.png"))
    b.close()
open(os.path.join(out, "console.log"), "w").write("\n".join(logs))
for l in logs:
    if "won=" in l or ": done," in l:
        print(l)
done = [l for l in logs if ": done," in l]
if not done:
    print("browserbot: no result within %d s (log: %s)" % (a.limit, out)); sys.exit(2)
sys.exit(0 if "done, 0 problems" in done[-1] else 2)
