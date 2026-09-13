#!/usr/bin/env python3
"""Exercise the built site in headless Chrome, with only Python's stdlib.

Run after build.py --output _site. Screenshots and checks go in .preview/.
Chrome/Chromium must already be installed; no dependencies are downloaded.
"""
from __future__ import annotations
import argparse
import base64
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import threading
import time
from urllib.parse import urlsplit
from urllib.request import build_opener, ProxyHandler

ROOT = Path(__file__).resolve().parents[1]


class CDP:
    def __init__(self, url):
        target = urlsplit(url)
        self.sock = socket.create_connection((target.hostname, target.port), timeout=15)
        self.sock.settimeout(20)
        key = base64.b64encode(os.urandom(16)).decode()
        request = f"GET {target.path} HTTP/1.1\r\nHost: {target.netloc}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        self.sock.sendall(request.encode())
        header = b""
        while not header.endswith(b"\r\n\r\n"):
            header += self.sock.recv(1)
        if b" 101 " not in header:
            raise RuntimeError(header.decode())
        self.serial = 0
        self.events = []

    def read(self, count):
        result = bytearray()
        while len(result) < count:
            data = self.sock.recv(count - len(result))
            if not data:
                raise EOFError("Chrome closed the debugging connection")
            result.extend(data)
        return bytes(result)

    def receive(self):
        full = bytearray()
        while True:
            first, second = self.read(2)
            length = second & 127
            if length == 126:
                length = struct.unpack("!H", self.read(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self.read(8))[0]
            mask = self.read(4) if second & 128 else None
            data = self.read(length)
            if mask:
                data = bytes(value ^ mask[i % 4] for i, value in enumerate(data))
            if first & 15 == 8:
                raise EOFError("WebSocket closed")
            full.extend(data)
            if first & 128:
                return json.loads(full)

    def call(self, method, params=None):
        self.serial += 1
        data = json.dumps({"id": self.serial, "method": method, "params": params or {}}).encode()
        mask = os.urandom(4)
        size = len(data)
        header = bytes((129, 128 | size)) if size < 126 else bytes((129, 254)) + struct.pack("!H", size) if size < 65536 else bytes((129, 255)) + struct.pack("!Q", size)
        self.sock.sendall(header + mask + bytes(value ^ mask[i % 4] for i, value in enumerate(data)))
        while True:
            result = self.receive()
            if result.get("id") == self.serial:
                if "error" in result:
                    raise RuntimeError(result["error"])
                return result.get("result", {})
            self.events.append(result)

    def js(self, expression):
        result = self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
        if "exceptionDetails" in result:
            raise RuntimeError(result["exceptionDetails"])
        return result.get("result", {}).get("value")


class QuietHandler(SimpleHTTPRequestHandler):
    errors = []

    def handle(self):
        try:
            super().handle()
        except (ConnectionResetError, BrokenPipeError):
            # Navigating away or closing the test browser can drop a keepalive.
            pass

    def log_message(self, *_args):
        pass

    def send_error(self, code, *args, **kwargs):
        self.errors.append((self.path, code))
        super().send_error(code, *args, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", help="Path to Chrome or Chromium executable")
    args = parser.parse_args()
    browser = args.browser or shutil.which("chromium") or shutil.which("google-chrome")
    if not browser:
        for candidate in (r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"):
            if Path(candidate).is_file():
                browser = candidate
                break
    if not browser:
        raise SystemExit("Install Chrome/Chromium or pass --browser. No browser was downloaded.")
    if not (ROOT / "_site/index.html").exists():
        raise SystemExit("Run python scripts/build.py --output _site first.")
    preview = ROOT / ".preview"
    preview.mkdir(exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT / "_site")))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        debug_port = probe.getsockname()[1]
    flags = [browser, "--headless=new", "--disable-gpu", "--disable-background-networking", "--no-first-run", "--no-default-browser-check", "--disable-component-update", "--disable-sync", f"--remote-debugging-port={debug_port}", f"--user-data-dir={preview / 'browser-profile'}", "about:blank"]
    log = (preview / "browser.log").open("w", encoding="utf-8")
    process = subprocess.Popen(flags, stdout=log, stderr=log, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    client = None
    try:
        opener = build_opener(ProxyHandler({}))
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError("Headless browser exited during startup. See .preview/browser.log.")
            try:
                with opener.open(f"http://127.0.0.1:{debug_port}/json/list", timeout=1) as response:
                    targets = json.load(response)
                client = CDP(next(t["webSocketDebuggerUrl"] for t in targets if t["type"] == "page"))
                break
            except (OSError, StopIteration):
                time.sleep(.1)
        if client is None:
            raise RuntimeError("Headless browser did not start. See .preview/browser.log.")
        client.call("Runtime.enable")
        client.call("Page.enable")
        client.call("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 1050, "deviceScaleFactor": 1, "mobile": False})
        base_url = f"http://127.0.0.1:{server.server_port}/"

        def navigate(url, ready="document.readyState === 'complete'"):
            client.call("Page.navigate", {"url": url})
            for _ in range(100):
                if client.js(ready):
                    return
                time.sleep(.1)
            raise AssertionError(f"Page did not become ready: {url}")

        def screenshot(name, full=False):
            params = {"format": "png"}
            if full:
                params.update({"captureBeyondViewport": True, "clip": {"x": 0, "y": 0, "width": client.js("document.documentElement.clientWidth"), "height": min(client.js("document.documentElement.scrollHeight"), 14000), "scale": 1}})
            shot = client.call("Page.captureScreenshot", params)
            (preview / name).write_bytes(base64.b64decode(shot["data"]))

        navigate(base_url)
        checks = {}
        def check(name, expression):
            result = client.js(expression)
            checks[name] = result
            if not result:
                raise AssertionError(f"Browser check failed: {name}")
        check("homepage is Crosstalk", "document.title.includes('CROSSTALK') && !!document.querySelector('.home-page')")
        check("eight week slots, only published week linked", "document.querySelectorAll('.week-entry').length === 8 && document.querySelectorAll('a.week-entry').length === 1")
        check("home stays lightweight", "!window.CROSSTALK_DATA && !document.querySelector('#network-atlas')")
        check("group names rendered", "document.body.textContent.includes('Christos Diamantis') && document.body.textContent.includes('s253102') && document.body.textContent.includes('Dávid Weiner') && document.body.textContent.includes('s253347')")
        screenshot("homepage.png", full=True)
        for width in (390, 360, 768):
            client.call("Emulation.setDeviceMetricsOverride", {"width":width,"height":844,"deviceScaleFactor":1,"mobile":True})
            check(f"home {width}px no horizontal overflow", "document.documentElement.scrollWidth <= document.documentElement.clientWidth")
            if width == 390:
                screenshot("homepage-mobile.png", full=True)
        client.call("Emulation.setDeviceMetricsOverride", {"width":1440,"height":1050,"deviceScaleFactor":1,"mobile":False})
        client.js("document.querySelector('a.week-entry').click()")
        for _ in range(100):
            if client.js("document.readyState==='complete' && !!document.querySelector('#network-atlas [data-node]')"):
                break
            time.sleep(.1)
        check("home opens the separate Week 1 report", "location.pathname.endsWith('/week1/index.html')")
        check("303 real nodes rendered", "document.querySelectorAll('#network-atlas [data-node]').length === 303")
        check("initial giant", "document.querySelector('#remaining-giant').textContent === '277'")
        check("desktop no horizontal overflow", "document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        shot = client.call("Page.captureScreenshot", {"format": "png"})
        (preview / "desktop.png").write_bytes(base64.b64decode(shot["data"]))
        client.js("document.querySelector('#character-search').value='Baymax'; document.querySelector('#search-form').requestSubmit()")
        check("isolate search", "document.querySelector('#dossier h3').textContent === 'Baymax' && document.querySelector('#dossier').textContent.includes('ISOLATED')")
        client.js("document.querySelector('#atlas').scrollIntoView({behavior:'instant'}); document.querySelector('#character-search').value='Spider-Man'; document.querySelector('#search-form').requestSubmit()")
        dot = client.js("(()=>{const e=document.querySelector('[data-node=Baymax] circle:last-child');const p=new DOMPoint(Number(e.getAttribute('cx')),Number(e.getAttribute('cy'))).matrixTransform(e.getScreenCTM());return {x:p.x,y:p.y}})()")
        client.call("Input.dispatchMouseEvent", {"type":"mousePressed","x":dot["x"],"y":dot["y"],"button":"left","clickCount":1})
        client.call("Input.dispatchMouseEvent", {"type":"mouseReleased","x":dot["x"],"y":dot["y"],"button":"left","clickCount":1})
        check("clicking a graph node opens its dossier", "document.querySelector('#dossier h3').textContent === 'Baymax'")
        client.js("document.querySelector('#character-search').value='Spider-Man (Marvel Mangaverse)'; document.querySelector('#search-form').requestSubmit()")
        check("disambiguated character search", "document.querySelector('#dossier h3').textContent === 'Spider-Man (Marvel Mangaverse)'")
        client.js("document.querySelector('#character-search').value='not-a-real-hero'; document.querySelector('#search-form').requestSubmit()")
        check("no-match feedback", "document.querySelector('#search-status').textContent.includes('No character found') && !document.querySelector('#search-status').classList.contains('sr-only')")
        client.js("document.querySelector('#character-search').value='Spider-Man'; document.querySelector('#search-form').requestSubmit(); document.querySelector('[data-direction=out]').click()")
        check("outgoing direction", "document.querySelector('#dossier').textContent.includes('LINKED FROM HERE / 9')")
        client.js("document.querySelector('[data-direction=in]').click()")
        check("incoming direction", "document.querySelector('#dossier').textContent.includes('LINKING HERE / 106')")
        client.js("document.querySelector('[data-scale=log]').click()")
        check("log distribution zeros explained", "document.querySelector('#distribution-caption').textContent.includes('58 pages') && document.querySelector('#distribution-caption').textContent.includes('20 with')")
        client.js("document.querySelector('[data-ranking=out]').click()")
        check("outgoing ranking", "document.querySelector('#rankings .rank-name').textContent === 'Betsy Braddock'")
        client.js("document.querySelector('#remove-spider').click()")
        check("Spider-Man removal", "document.querySelector('#remaining-giant').textContent === '271' && document.querySelector('#removal-detail').textContent.includes('302 surviving')")
        check("Python and browser experiments agree", "CROSSTALK_DATA.summary.hub_removal.steps.filter(s=>s.removed<=40).every(s=>{const r=document.querySelector('#removal-count');r.value=s.removed;r.dispatchEvent(new Event('input'));return Number(document.querySelector('#remaining-giant').textContent)===s.targeted_largest_component})")
        check("nested report figure download resolves", "document.querySelector('#download-chart').href === new URL('../assets/figures/degree-loglog.svg',location.href).href")
        client.js("document.querySelector('#zoom-in').click()")
        check("map zoom", "document.querySelector('#network-atlas').getAttribute('viewBox') !== '0 0 900 700'")
        client.js("document.querySelector('#zoom-reset').click();document.querySelector('[data-direction=all]').click();document.querySelector('#atlas').scrollIntoView({behavior:'instant'})")
        shot = client.call("Page.captureScreenshot", {"format": "png"})
        (preview / "atlas.png").write_bytes(base64.b64decode(shot["data"]))
        for width in (390, 360, 768):
            client.call("Emulation.setDeviceMetricsOverride", {"width":width,"height":844,"deviceScaleFactor":1,"mobile":True})
            client.js("window.scrollTo({top:0,behavior:'instant'})")
            check(f"report {width}px no horizontal overflow", "document.documentElement.scrollWidth <= document.documentElement.clientWidth")
            if width == 390:
                shot = client.call("Page.captureScreenshot", {"format":"png","captureBeyondViewport":True,"clip":{"x":0,"y":0,"width":390,"height":min(client.js('document.documentElement.scrollHeight'),18000),"scale":1}})
                (preview / "mobile.png").write_bytes(base64.b64decode(shot["data"]))
        client.call("Emulation.setDeviceMetricsOverride", {"width":1440,"height":1050,"deviceScaleFactor":1,"mobile":False})
        game_ready = "document.readyState==='complete' && document.querySelectorAll('#cw-wires .cw-wire').length>0"
        navigate(base_url + "play/index.html", game_ready)
        client.js("localStorage.removeItem('crosstalk-crossed-wires-v1')")
        navigate(base_url + "play/index.html", game_ready)
        check("game offers twelve real puzzles", "document.querySelector('#cw-select').options.length===12 && CROSSTALK_PUZZLES.puzzles.length===12")
        check("game starts with missing arrows", "document.querySelectorAll('.cw-wire-assigned').length===0")
        screenshot("game.png", full=True)
        client.js("document.querySelector('#cw-check').click()")
        check("game explains incomplete board", "document.querySelector('#cw-status').textContent.includes('need') && !document.querySelector('.cw-is-solved')")
        client.js("document.querySelector('.cw-wire').click()")
        check("wire can be connected", "document.querySelectorAll('.cw-wire-assigned').length===1 && document.querySelector('.cw-wire-direction').textContent==='→'")
        client.js("document.querySelector('.cw-wire').click()")
        check("wire can be reversed", "document.querySelector('.cw-wire-direction').textContent==='←'")
        client.js("document.querySelector('#cw-reset').click();document.querySelector('#cw-hint').click()")
        check("hint restores one real arrow", "document.querySelectorAll('.cw-wire-assigned').length===1 && document.querySelector('#cw-status').textContent.includes('Hint:')")
        client.js("document.querySelector('#cw-reset').click()")
        check("reset clears arrows", "document.querySelectorAll('.cw-wire-assigned').length===0")
        client.js("CROSSTALK_PUZZLES.puzzles[0].edges.forEach((e,i)=>{const b=document.querySelector(`[data-edge='${i}']`);b.click();if(e.source===e.a)b.click()});document.querySelector('#cw-check').click()")
        check("incorrect complete board is rejected", "document.querySelector('#cw-status').textContent.includes('crossed connection') && !document.querySelector('.cw-is-solved')")
        solve_all = """CROSSTALK_PUZZLES.puzzles.every((p,index)=>{
            const picker=document.querySelector('#cw-select');picker.value=index;picker.dispatchEvent(new Event('change'));
            p.edges.forEach((edge,i)=>{const b=document.querySelector(`[data-edge='${i}']`);b.click();if(edge.source!==edge.a)b.click()});
            document.querySelector('#cw-check').click();
            return !!document.querySelector('.cw-is-solved') && document.querySelectorAll('.cw-socket-matched').length===p.nodes.length;
        })"""
        check("all twelve puzzles solve with their real directions", solve_all)
        check("game celebrates completion", "document.querySelector('#cw-progress').textContent==='12 / 12 connected' && document.querySelector('#cw-status').textContent.includes('All twelve')")
        client.js("document.querySelector('#cw-next').click()")
        check("last board loops back for replay", "document.querySelector('#cw-select').value==='0' && !document.querySelector('.cw-is-solved')")
        navigate(base_url + "play/index.html", game_ready)
        check("completed boards survive reload", "document.querySelector('#cw-progress').textContent==='12 / 12 connected'")
        client.js("document.querySelector('#cw-select').value=11;document.querySelector('#cw-select').dispatchEvent(new Event('change'))")
        for width in (390, 360, 768):
            client.call("Emulation.setDeviceMetricsOverride", {"width":width,"height":844,"deviceScaleFactor":1,"mobile":True})
            check(f"game {width}px no horizontal overflow", "document.documentElement.scrollWidth <= document.documentElement.clientWidth")
            if width == 390:
                screenshot("game-mobile.png", full=True)
        blocker=client.call("Page.addScriptToEvaluateOnNewDocument", {"source":"Object.defineProperty(window,'localStorage',{get(){throw new Error('Storage unavailable for test')}})"})
        navigate(base_url + "play/index.html", game_ready)
        client.js("document.querySelector('#cw-hint').click()")
        check("game works when storage is unavailable", "document.querySelectorAll('.cw-wire-assigned').length===1")
        client.call("Page.removeScriptToEvaluateOnNewDocument", {"identifier":blocker["identifier"]})
        navigate(base_url + "#atlas", "location.pathname.endsWith('/week1/index.html') && !!document.querySelector('#network-atlas [data-node]')")
        check("old report bookmarks still work", "location.hash==='#atlas'")
        # All pages also work when opened from disk.
        navigate((ROOT / "index.html").as_uri())
        check("offline home works", "location.protocol === 'file:' && !!document.querySelector('.home-page')")
        navigate((ROOT / "week1/index.html").as_uri(), "document.readyState === 'complete' && !!document.querySelector('#network-atlas [data-node]')")
        check("offline report works", "location.protocol === 'file:' && document.querySelectorAll('#network-atlas [data-node]').length === 303")
        navigate((ROOT / "play/index.html").as_uri(), game_ready)
        check("offline game works", "location.protocol==='file:' && document.querySelector('#cw-select').options.length===12")
        failures = [event for event in client.events if event.get("method") == "Runtime.exceptionThrown"]
        if failures or QuietHandler.errors:
            raise AssertionError({"javascript_errors":failures,"http_errors":QuietHandler.errors})
        checks["no JavaScript exceptions or missing resources"] = True
        (preview / "checks.json").write_text(json.dumps(checks,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(checks,indent=2))
    finally:
        if client:
            client.sock.close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        log.close()
        server.shutdown()


if __name__ == "__main__":
    main()
