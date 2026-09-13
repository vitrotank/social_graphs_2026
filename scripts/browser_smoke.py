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
        client.call("Page.navigate", {"url": f"http://127.0.0.1:{server.server_port}/"})
        for _ in range(100):
            if client.js("document.readyState === 'complete' && !!document.querySelector('#network-atlas [data-node]')"):
                break
            time.sleep(.1)
        checks = {}
        def check(name, expression):
            result = client.js(expression)
            checks[name] = result
            if not result:
                raise AssertionError(f"Browser check failed: {name}")
        check("303 real nodes rendered", "document.querySelectorAll('#network-atlas [data-node]').length === 303")
        check("group names rendered", "document.body.textContent.includes('Christos Diamantis (s253102)') && document.body.textContent.includes('Dávid Weiner (s253347)')")
        check("initial giant", "document.querySelector('#remaining-giant').textContent === '277'")
        check("desktop no horizontal overflow", "document.documentElement.scrollWidth <= innerWidth")
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
        check("Python and browser experiments agree", "EARTH303_DATA.summary.hub_removal.steps.filter(s=>s.removed<=40).every(s=>{const r=document.querySelector('#removal-count');r.value=s.removed;r.dispatchEvent(new Event('input'));return Number(document.querySelector('#remaining-giant').textContent)===s.targeted_largest_component})")
        client.js("document.querySelector('#zoom-in').click()")
        check("map zoom", "document.querySelector('#network-atlas').getAttribute('viewBox') !== '0 0 900 700'")
        client.js("document.querySelector('#zoom-reset').click();document.querySelector('[data-direction=all]').click();document.querySelector('#atlas').scrollIntoView({behavior:'instant'})")
        shot = client.call("Page.captureScreenshot", {"format": "png"})
        (preview / "atlas.png").write_bytes(base64.b64decode(shot["data"]))
        for width in (390, 360, 768):
            client.call("Emulation.setDeviceMetricsOverride", {"width":width,"height":844,"deviceScaleFactor":1,"mobile":True})
            client.js("window.scrollTo({top:0,behavior:'instant'})")
            check(f"{width}px no horizontal overflow", "document.documentElement.scrollWidth <= innerWidth")
            if width == 390:
                shot = client.call("Page.captureScreenshot", {"format":"png","captureBeyondViewport":True,"clip":{"x":0,"y":0,"width":390,"height":min(client.js('document.documentElement.scrollHeight'),18000),"scale":1}})
                (preview / "mobile.png").write_bytes(base64.b64decode(shot["data"]))
        client.call("Page.navigate", {"url":(ROOT / "index.html").as_uri()})
        for _ in range(100):
            if client.js("document.readyState === 'complete' && !!document.querySelector('#network-atlas [data-node]')"):
                break
            time.sleep(.1)
        check("offline double-click site works", "location.protocol === 'file:' && document.querySelectorAll('#network-atlas [data-node]').length === 303")
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
