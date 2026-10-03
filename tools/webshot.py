#!/usr/bin/env python3
"""Screenshots of the browser build in headless Chrome (M5, ADR-0023).

    tools/webshot.py URL OUTDIR [--at 30,45] [--size 1280x720] [--swiftshader]

Starts Chrome with remote debugging, opens URL, saves OUTDIR/shot_<sec>.png at
each time in --at (seconds after load starts) and OUTDIR/console.log with the
page's console. Uses the real GPU unless --swiftshader.
"""
import argparse, base64, json, os, subprocess, tempfile, time, urllib.request
import websocket

ap = argparse.ArgumentParser()
ap.add_argument("url"); ap.add_argument("outdir")
ap.add_argument("--at", default="30"); ap.add_argument("--size", default="1280x720")
ap.add_argument("--swiftshader", action="store_true")
ap.add_argument("--chrome", default=os.environ.get("CHROME", "google-chrome"))
a = ap.parse_args()
os.makedirs(a.outdir, exist_ok=True)
w, h = a.size.split("x")
port = 9300 + os.getpid() % 500
gpu = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] if a.swiftshader else ["--use-angle=gl", "--ignore-gpu-blocklist"]  # the integrated GPU (Radeon 680M here)
prof = tempfile.mkdtemp(prefix="webshot-")
chrome = subprocess.Popen([a.chrome, "--headless=new", "--no-first-run", f"--user-data-dir={prof}",
    f"--remote-debugging-port={port}", f"--window-size={w},{h}", "--autoplay-policy=no-user-gesture-required",
    *gpu, "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(100):
        try:
            tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json"))
            page = next(t for t in tabs if t["type"] == "page"); break
        except Exception:
            time.sleep(0.1)
    ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=60, suppress_origin=True)
    n = [0]
    def call(method, **params):
        n[0] += 1; ws.send(json.dumps({"id": n[0], "method": method, "params": params}))
        while True:
            m = json.loads(ws.recv())
            if m.get("method") == "Runtime.consoleAPICalled":
                log.write(" ".join(str(x.get("value", x.get("description", ""))) for x in m["params"]["args"]) + "\n")
            if m.get("id") == n[0]:
                return m.get("result", {})
    log = open(os.path.join(a.outdir, "console.log"), "w")
    call("Runtime.enable")
    call("Emulation.setDeviceMetricsOverride", width=int(w), height=int(h), deviceScaleFactor=1, mobile=False)
    call("Page.navigate", url=a.url)
    start = time.time()
    for t in sorted(float(x) for x in a.at.split(",")):
        while time.time() - start < t:
            ws.settimeout(0.2)
            try:
                m = json.loads(ws.recv())
                if m.get("method") == "Runtime.consoleAPICalled":
                    log.write(" ".join(str(x.get("value", x.get("description", ""))) for x in m["params"]["args"]) + "\n")
            except websocket.WebSocketTimeoutException:
                pass
        ws.settimeout(60)
        img = call("Page.captureScreenshot", format="png")["data"]
        p = os.path.join(a.outdir, f"shot_{int(t)}.png")
        open(p, "wb").write(base64.b64decode(img)); print("shot", p)
    gl = call("Runtime.evaluate", expression="(()=>{const c=document.createElement('canvas').getContext('webgl2');const d=c&&c.getExtension('WEBGL_debug_renderer_info');return d?c.getParameter(d.UNMASKED_RENDERER_WEBGL):'no webgl2'})()")
    print("webgl:", gl.get("result", {}).get("value"))
    log.close()
finally:
    chrome.terminate(); chrome.wait()
