#!/usr/bin/env python3
"""Records a play-through video of a room in a real browser (tests only).

    tools/playthrough.py record URL --out DIR [--limit 5400]
    tools/playthrough.py cut ROOM_ID DIR [--captions FILE] [--video OUT.mp4]
                                [--ff-after 40] [--ff-speed 8]

`record` opens URL (the web client with ?room=<id>&deskbot=1&tour=1, the play
bot at a watching pace) in headless Chrome, clicks when the game asks for
pointer lock, and saves every frame Chrome draws (DevTools screencast, JPEG)
to DIR/frames with its time, and the game's console with times to
DIR/timeline.jsonl. `cut` turns that into a 30 fps H.264 video with each
solution step captioned while it plays: the step as room.yaml writes it, and
the line for that step from the captions file if there is one (YAML: step
index -> text), in a band under the picture so they cover neither the game's
own subtitles nor its HUD. A step that takes longer than --ff-after seconds
(the bot hunting for a spot to reach something from) plays at --ff-speed
from 10 s in to 8 s before it is done, marked on screen: the long hunt is
the finding, not something to sit through. Video only; the screencast
carries no sound.
tools/playthrough.sh wraps both with a private platform.
"""
import argparse, asyncio, base64, json, os, re, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


async def record(url: str, out: str, limit: float) -> int:
    from playwright.async_api import async_playwright
    frames = os.path.join(out, "frames")
    os.makedirs(frames, exist_ok=True)
    timeline = open(os.path.join(out, "timeline.jsonl"), "w")
    index = open(os.path.join(out, "frames.jsonl"), "w")
    logs: list[str] = []
    n = 0
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome", headless=True, args=["--use-angle=gl", "--ignore-gpu-blocklist",
            "--autoplay-policy=no-user-gesture-required"])
        page = await b.new_page(viewport={"width": 1280, "height": 720})
        cdp = await page.context.new_cdp_session(page)

        def on_console(m) -> None:
            logs.append(m.text)
            timeline.write(json.dumps({"t": time.time(), "line": m.text}) + "\n")
            timeline.flush()
            if "BOT: step " in m.text or "-FAIL" in m.text or "won=" in m.text:
                print(m.text, flush=True)
        page.on("console", on_console)

        async def on_frame(ev: dict) -> None:
            nonlocal n
            n += 1
            name = "%06d.jpg" % n
            with open(os.path.join(frames, name), "wb") as f:
                f.write(base64.b64decode(ev["data"]))
            index.write(json.dumps({"f": name, "t": ev["metadata"].get("timestamp", time.time())}) + "\n")
            try:
                await cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})
            except Exception:
                pass
        cdp.on("Page.screencastFrame", lambda ev: asyncio.ensure_future(on_frame(ev)))
        await page.goto(url)
        await cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 88, "maxWidth": 1280, "maxHeight": 720})
        t0 = time.time()
        seen = 0
        while time.time() - t0 < limit and not any(": done," in l for l in logs):
            await page.wait_for_timeout(250)
            new, seen = logs[seen:], len(logs)
            if any("DESKBOT: CLICK" in l for l in new):
                await page.mouse.click(640, 360)
        await page.wait_for_timeout(1000)
        await cdp.send("Page.stopScreencast")
        await b.close()
    timeline.close()
    index.close()
    print("playthrough: %d frames in %.0f s -> %s" % (n, time.time() - t0, out))
    done = [l for l in logs if ": done," in l]
    return 0 if done and "done, 0 problems" in done[-1] else 2


def describe(step: dict) -> str:
    last = lambda p: str(p).split("/")[-1]
    act = step.get("act")
    if act == "examine":
        return "Examine %s" % last(step["node"])
    if act == "pick_up":
        return "Pick up %s" % step["item"]
    if act == "use_on":
        return "Use %s on %s" % (step["item"], step["target"])
    if act == "input_code":
        return "Enter %s on %s" % (step["value"], step["lock"])
    if act == "interact":
        verb = step.get("verb", "use")
        if verb == "set":
            return "Set %s to %s" % (step["node"], step["value"])
        return "%s %s" % (verb.capitalize(), step["node"])
    return "%s %s" % (act, step)


def ass_time(s: float) -> str:
    s = max(0.0, s)
    return "%d:%02d:%05.2f" % (s // 3600, s % 3600 // 60, s % 60)


def ass_text(s: str) -> str:
    return s.replace("\\", "/").replace("{", "(").replace("}", ")").replace("\n", "\\N")


def cut(room: str, d: str, captions: str, video: str, ff_after: float = 40.0, ff_speed: float = 8.0) -> int:
    import yaml
    manifest = yaml.safe_load(open(os.path.join(ROOT, "game", "rooms", room, "room.yaml")))
    steps = manifest["solution"]
    why = yaml.safe_load(open(captions)) if captions else {}
    why = {int(k): str(v) for k, v in (why or {}).items()}
    frames = [json.loads(l) for l in open(os.path.join(d, "frames.jsonl"))]
    frames.sort(key=lambda f: f["t"])
    t1 = frames[-1]["t"]
    # Start when the room pack has arrived (skip the download screen).
    t0 = frames[0]["t"]
    for l in open(os.path.join(d, "timeline.jsonl")):
        e = json.loads(l)
        if e["line"].startswith("room pack:"):
            t0 = e["t"]
            break
    frames = [f for f in frames if f["t"] >= t0 - 0.5] or frames[-1:]
    begins, done = [], {}
    for l in open(os.path.join(d, "timeline.jsonl")):
        e = json.loads(l)
        m = re.search(r"BOT: step (\d+) begin", e["line"])
        if m:
            begins.append((int(m.group(1)), e["t"] - t0))
        m = re.search(r"BOT: step (\d+) \S+ .*(ok \(at|\(looked\))", e["line"])
        if m:
            done[int(m.group(1))] = e["t"] - t0
        if "BOT: won=" in e["line"]:
            begins.append((-1, e["t"] - t0))
    # Fast-forward windows (recording time from t0).
    ff = []
    for k, (i, t) in enumerate(begins):
        if i >= 0 and k + 1 < len(begins) and begins[k + 1][1] - t > ff_after and i in done:
            a, b = t + 10.0, done[i] - 8.0
            if b - a > 10.0:
                ff.append((a, b))
    def vt(t: float) -> float:
        """Recording time to video time."""
        return t - sum(max(0.0, min(t, b) - a) for a, b in ff) * (1.0 - 1.0 / ff_speed)
    # The frames, each held until the next arrives (the screencast only sends
    # a frame when the page changes).
    with open(os.path.join(d, "frames.txt"), "w") as f:
        for a, b in zip(frames, frames[1:] + [{"t": t1 + 0.5}]):
            dur = vt(b["t"] - t0) - vt(a["t"] - t0)
            f.write("file 'frames/%s'\nduration %.4f\n" % (a["f"], max(dur, 0.001)))
        f.write("file 'frames/%s'\n" % frames[-1]["f"])
    events = []
    for a, b in ff:
        events.append("Dialogue: 1,%s,%s,FF,,0,0,0,,FAST-FORWARD x%d: the bot is hunting for a spot to reach it from (%.0f s real)"
                      % (ass_time(vt(a)), ass_time(vt(b)), ff_speed, b - a))
    for k, (i, t) in enumerate(begins):
        if i < 0:
            continue
        end = begins[k + 1][1] if k + 1 < len(begins) else t1 - t0
        top = "Step %d of %d: %s" % (i + 1, len(steps), describe(steps[i]))
        line = "Dialogue: 0,%s,%s,Cap,,0,0,0,,{\\b1}%s{\\b0}" % (ass_time(vt(t)), ass_time(vt(end)), ass_text(top))
        if i in why:
            line += "\\N" + ass_text(why[i])
        events.append(line)
    with open(os.path.join(d, "captions.ass"), "w") as f:
        f.write("[Script Info]\nScriptType: v4.00+\nPlayResX: 1280\nPlayResY: 816\nWrapStyle: 0\n\n"
                "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
                "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
                "Alignment, MarginL, MarginR, MarginV, Encoding\n"
                "Style: Cap,DejaVu Sans,20,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,8,40,40,728,1\n"
                "Style: FF,DejaVu Sans,22,&H0000D8FF,&H0000D8FF,&H60000000,&H60000000,1,0,0,0,100,100,0,0,3,6,0,8,40,40,330,1\n\n"
                "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        f.write("\n".join(events) + "\n")
    cmd = ["ffmpeg", "-hide_banner", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", "frames.txt",
           "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:816:(ow-iw)/2:0:color=0x141210,fps=30,ass=captions.ass",
           "-c:v", "libx264", "-preset", "medium", "-crf", "25", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
           os.path.abspath(video)]
    r = subprocess.run(cmd, cwd=d)
    if r.returncode == 0:
        print("playthrough: %s (%.0f min, %d fast-forwards)" % (video, vt(t1 - t0) / 60, len(ff)))
    return r.returncode


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record"); r.add_argument("url"); r.add_argument("--out", required=True)
    r.add_argument("--limit", type=float, default=5400)
    c = sub.add_parser("cut"); c.add_argument("room"); c.add_argument("dir")
    c.add_argument("--captions", default=""); c.add_argument("--video", default="")
    c.add_argument("--ff-after", type=float, default=40.0); c.add_argument("--ff-speed", type=float, default=8.0)
    a = ap.parse_args()
    if a.cmd == "record":
        sys.exit(asyncio.run(record(a.url, a.out, a.limit)))
    sys.exit(cut(a.room, a.dir, a.captions, a.video or os.path.join(a.dir, "playthrough.mp4"), a.ff_after, a.ff_speed))
