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
import sys
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
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", help="Path to Chrome or Chromium executable")
    parser.add_argument("--grunge-only", action="store_true", help="Run just the B-side and provider-control checks")
    parser.add_argument("--week4-only", action="store_true", help="Run just the philosopher atlas, comparison, and backbone checks")
    parser.add_argument("--editorial-only", action="store_true", help="Run just the homepage, network cabinet, and Week 1–3 editorial figure checks")
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
                try:
                    if client.js(ready):
                        return
                except RuntimeError as error:
                    # The legacy homepage bookmarks redirect to Week 1. CDP
                    # can briefly evaluate against the departing document.
                    if not any(message in str(error) for message in (
                        "Inspected target navigated or closed",
                        "Execution context was destroyed",
                        "Cannot find context with specified id",
                    )):
                        raise
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
                print("Failure details:", client.js("JSON.stringify({width:innerWidth,scroll:document.documentElement.scrollWidth,focus:document.activeElement.outerHTML.slice(0,350),rank:document.querySelector('#w3-story-rank-readout')?.textContent,rankChoice:document.querySelector('#w3-story-rank-names [aria-pressed=true]')?.dataset.character,offenders:Array.from(document.querySelectorAll('body *')).filter(e=>e.getBoundingClientRect().right>document.documentElement.clientWidth+1).slice(0,12).map(e=>({tag:e.tagName,cls:String(e.className),text:e.textContent.slice(0,90)}))})"), flush=True)
                screenshot("failure.png", full=True)
                raise AssertionError(f"Browser check failed: {name}")
        def next_frame():
            client.js("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")

        def press_key(key, code, virtual_key):
            keydown = {"type":"keyDown" if key == "Enter" else "rawKeyDown","key":key,"code":code,"windowsVirtualKeyCode":virtual_key,"nativeVirtualKeyCode":virtual_key}
            if key == "Enter":
                keydown.update({"text":"\r","unmodifiedText":"\r"})
            client.call("Input.dispatchKeyEvent", keydown)
            client.call("Input.dispatchKeyEvent", {"type":"keyUp","key":key,"code":code,"windowsVirtualKeyCode":virtual_key,"nativeVirtualKeyCode":virtual_key})
            next_frame()

        def check_editorial():
            """Exercise real figure data, pointer/keyboard controls, and disk use."""
            ready = {
                "index.html": "document.readyState==='complete' && !!document.querySelector('#latest-title')",
                "explore/index.html": "document.readyState==='complete' && document.querySelectorAll('#cover-nodes [data-node]').length>0",
                "week1/index.html": "document.readyState==='complete' && document.querySelectorAll('#degree-scatter [data-degree-character]').length===303",
                "week2/index.html": "document.readyState==='complete' && document.querySelector('#w2-ccdf-plot')?.dataset.state==='ready'",
                "week3/index.html": "document.readyState==='complete' && document.querySelector('#w3-story-explorer')?.hidden===false && document.querySelectorAll('#w3-story-rank-names button').length===8",
            }
            client.call("Emulation.setEmulatedMedia", {"features":[{"name":"prefers-reduced-motion","value":"reduce"}]})
            client.call("Emulation.setDeviceMetricsOverride", {"width":1440,"height":1050,"deviceScaleFactor":1,"mobile":False})

            # Capture every redesigned figure before assertions, so visual review
            # remains available if a later interaction reveals a regression.
            figures = (("index.html","editorial-home",None),
                       ("explore/index.html","editorial-cabinet",".cover-observatory"),
                       ("week1/index.html","editorial-week1",".degree-portrait"),
                       ("week2/index.html","editorial-week2",".week2-ccdf-panel"),
                       ("week3/index.html","editorial-week3","#w3-story-figure"))
            for route, name, target in figures:
                navigate(base_url + route, ready[route])
                next_frame()
                screenshot(name + ".png", full=True)
                if target:
                    # The plot's figure is the useful viewport, rather than the
                    # headline at the top of a long story.
                    if route.startswith("week2/"):
                        client.js("document.querySelector('#w2-ccdf-plot').closest('figure').scrollIntoView({block:'start',behavior:'instant'})")
                    else:
                        client.js(f"document.querySelector({json.dumps(target)}).scrollIntoView({{block:'start',behavior:'instant'}})")
                    next_frame()
                    screenshot(name + ("-scatter.png" if route.startswith("week1/") else "-plot.png" if route.startswith("week2/") else "-map.png" if route.startswith("explore/") else "-curve.png"))
                else:
                    screenshot(name + "-hero.png")
                    client.call("Emulation.setDeviceMetricsOverride", {"width":390,"height":844,"deviceScaleFactor":1,"mobile":True})
                    client.js("window.scrollTo({top:0,behavior:'instant'})")
                    next_frame()
                    screenshot(name + "-mobile.png", full=True)
                    client.call("Emulation.setDeviceMetricsOverride", {"width":1440,"height":1050,"deviceScaleFactor":1,"mobile":False})

            navigate(base_url, ready["index.html"])
            check("homepage gives the latest story a direct entry", "!!document.querySelector('.latest-spread a[href]') && !!document.querySelector('.latest-plate svg') && !document.querySelector('#cover-map') && !window.CROSSTALK_COVER")
            check("reading rail is confined to stories on the homepage", "!document.querySelector('.journal-rail') && !document.documentElement.classList.contains('journal-reader')")
            navigate(base_url + "explore/index.html", ready["explore/index.html"])
            check("network cabinet defaults to the real philosopher preview", "document.querySelector('[data-cover-world=philosophers]').getAttribute('aria-pressed')==='true' && document.querySelector('#cover-total-nodes').textContent==='1,374' && document.querySelector('#cover-total-edges').textContent==='9,139' && document.querySelectorAll('#cover-nodes [data-node]').length===CROSSTALK_COVER.philosophers.nodes.length && document.querySelectorAll('#cover-edges line').length===CROSSTALK_COVER.philosophers.edges.length")
            check("network cabinet uses a compact exhibit without the full graph payload", "!window.CROSSTALK_DATA && !window.CROSSTALK_WEEK4 && CROSSTALK_COVER.philosophers.nodes.length<200 && CROSSTALK_COVER.philosophers.edges.length<=500 && document.querySelector('#cover-person').options.length===CROSSTALK_COVER.philosophers.nodes.length+1 && document.querySelector('#cover-sample-note').textContent.includes('Selected')")
            client.js("document.querySelector('#cover-groups button:not([data-group=all])').click()")
            check("cabinet community focus preserves cross-group links and dims the rest", "document.querySelector('#cover-groups button[aria-pressed=true]').dataset.group!=='all' && document.querySelectorAll('#cover-nodes .is-muted').length>0 && document.querySelectorAll('#cover-edges .is-active').length>0 && document.querySelectorAll('#cover-edges .is-muted').length>0 && document.querySelector('#cover-person-note').textContent.includes('stay visible')")
            client.js("document.querySelector('#cover-person').value='Aristotle';document.querySelector('#cover-person').dispatchEvent(new Event('change'))")
            check("cabinet named picker follows Aristotle's real links", "document.querySelector('#cover-person-note h3').textContent==='Aristotle' && document.querySelector('#cover-person-note').textContent.includes('300 neighbors') && document.querySelector('#cover-nodes [data-node=Aristotle]').getAttribute('aria-pressed')==='true' && document.querySelectorAll('#cover-edges .is-active').length===CROSSTALK_COVER.philosophers.edges.filter(e=>e.source==='Aristotle'||e.target==='Aristotle').length")
            client.js("document.querySelector('#cover-nodes [tabindex=\"0\"]').focus()")
            press_key("ArrowRight", "ArrowRight", 39)
            client.js("window.__editorialCoverFocus=document.activeElement.dataset.node")
            check("cabinet map arrow key moves to another named dot", "!!window.__editorialCoverFocus && window.__editorialCoverFocus!=='Aristotle' && document.activeElement.closest('#cover-nodes')!==null")
            press_key("Enter", "Enter", 13)
            check("cabinet map Enter selects the focused dot", "document.querySelector('#cover-person').value===window.__editorialCoverFocus && document.querySelector('#cover-nodes [aria-pressed=true]').dataset.node===window.__editorialCoverFocus")
            press_key("Escape", "Escape", 27)
            check("cabinet map Escape restores the preview", "document.querySelector('#cover-person').value==='' && document.querySelector('#cover-groups [data-group=all]').getAttribute('aria-pressed')==='true' && !document.querySelector('#cover-nodes .is-muted')")
            client.js("document.querySelector('[data-cover-world=marvel]').click()")
            check("cabinet Marvel lens shows the real roster totals and selected pairs", "document.querySelector('[data-cover-world=marvel]').getAttribute('aria-pressed')==='true' && document.querySelector('#cover-total-nodes').textContent==='303' && document.querySelector('#cover-total-edges').textContent==='1,784' && document.querySelectorAll('#cover-nodes [data-node]').length===CROSSTALK_COVER.marvel.nodes.length && document.querySelectorAll('#cover-edges line').length===CROSSTALK_COVER.marvel.edges.length && document.querySelector('#cover-open').href.endsWith('/week1/index.html#atlas')")
            client.js("document.querySelector('#cover-person').value='Baymax';document.querySelector('#cover-person').dispatchEvent(new Event('change'))")
            check("cabinet preview includes an actual isolate", "document.querySelector('#cover-person-note h3').textContent==='Baymax' && document.querySelector('#cover-person-note').textContent.includes('0 neighbors') && !document.querySelector('#cover-edges .is-active')")

            navigate(base_url + "week1/index.html", ready["week1/index.html"])
            check("Week 1 scatter represents all 303 real character pages", "document.querySelectorAll('#degree-scatter [data-degree-character]').length===303 && document.querySelector('#degree-character').options.length===303 && Array.from(document.querySelectorAll('#degree-scatter [data-degree-character]')).every(e=>{const n=CROSSTALK_DATA.network.nodes.find(n=>n.id===e.dataset.degreeCharacter);return n&&Number(e.dataset.inDegree)===n.in_degree&&Number(e.dataset.outDegree)===n.out_degree})")
            client.js("document.querySelector('[data-degree-view=local]').click()")
            check("Week 1 close-up accurately reports its 279 included pages", "document.querySelectorAll('#degree-scatter [data-degree-character]').length===279 && document.querySelector('#degree-scatter svg').dataset.degreeScope==='local' && document.querySelector('#degree-scatter-caption').textContent.includes('279 of 303')")
            client.js("document.querySelector('[data-degree-scale=sqrt]').click()")
            check("Week 1 square-root axes retain original counts", "document.querySelector('#degree-scatter svg').dataset.axisScale==='sqrt' && document.querySelector('[data-degree-scale=sqrt]').getAttribute('aria-pressed')==='true' && document.querySelectorAll('#degree-scatter [data-degree-character]').length===279 && document.querySelector('#degree-scatter-caption').textContent.includes('tick labels remain original link counts')")
            client.js("document.querySelector('#degree-character').value='Baymax';document.querySelector('#degree-character').dispatchEvent(new Event('change'))")
            check("Week 1 named selector explains Baymax and overlapping isolates", "document.querySelector('#degree-character-readout h4').textContent==='Baymax' && document.querySelector('#degree-character-readout').textContent.includes('isolated page') && document.querySelector('#degree-character-readout').textContent.includes('17 pages') && document.querySelector('#degree-scatter [data-degree-character=Baymax]').getAttribute('aria-pressed')==='true'")
            client.js("document.querySelector('#degree-scatter').scrollIntoView({block:'center',behavior:'instant'})")
            next_frame()
            point = client.js("(()=>{const e=document.querySelector('#degree-scatter [data-degree-character=Baymax] .portrait-dot');const p=new DOMPoint(Number(e.getAttribute('cx')),Number(e.getAttribute('cy'))).matrixTransform(e.getScreenCTM());return{x:p.x,y:p.y}})()")
            client.call("Input.dispatchMouseEvent", {"type":"mousePressed",**point,"button":"left","clickCount":1})
            client.call("Input.dispatchMouseEvent", {"type":"mouseReleased",**point,"button":"left","clickCount":1})
            check("clicking Baymax's scatter dot opens the atlas dossier", "document.querySelector('#dossier h3').textContent==='Baymax' && document.querySelector('#dossier').textContent.includes('ISOLATED')")
            client.js("document.querySelector('#network-atlas [data-node=Baymax]').focus()")
            press_key("Enter", "Enter", 13)
            check("Week 1 atlas Enter preserves focus after rebuilding its dots", "document.activeElement.dataset.node==='Baymax' && document.activeElement.closest('#network-atlas')!==null && document.activeElement.classList.contains('selected')")
            client.js("document.querySelector('[data-degree-view=all]').click();document.querySelector('#degree-character').value='Spider-Man';document.querySelector('#degree-character').dispatchEvent(new Event('change'));document.querySelector('#degree-scatter [data-degree-character=Spider-Man]').focus()")
            press_key("ArrowDown", "ArrowDown", 40)
            client.js("window.__editorialDegreeFocus=document.activeElement.dataset.degreeCharacter")
            check("Week 1 scatter arrow key reaches a different real page", "!!window.__editorialDegreeFocus && window.__editorialDegreeFocus!=='Spider-Man' && document.querySelector('#degree-character').value===window.__editorialDegreeFocus")
            press_key("Enter", "Enter", 13)
            check("Week 1 scatter Enter opens that page's real dossier", "document.querySelector('#network-atlas .selected').dataset.node===window.__editorialDegreeFocus && document.querySelector('#dossier h3').textContent===document.querySelector('#degree-character-readout h4').textContent")
            check("Week 1 scatter Enter transfers focus to its selected atlas dot", "document.activeElement.dataset.node===window.__editorialDegreeFocus && document.activeElement.closest('#network-atlas')!==null && document.activeElement.classList.contains('selected')")
            client.js("document.querySelector('[data-degree-point=in-106]').focus()")
            check("Week 1 distribution point reports the exact Spider-Man tail", "document.querySelector('#degree-readout').textContent.includes('1 page') && document.querySelector('#degree-readout').textContent.includes('Spider-Man') && document.querySelector('#degree-readout').textContent.includes('106 LINKS')")
            client.js("document.querySelector('[data-degree-series=in]').click()")
            check("Week 1 distribution can show outgoing counts alone", "!document.querySelector('[data-degree-point^=in-]') && !!document.querySelector('[data-degree-point^=out-]') && document.querySelector('[data-degree-series=in]').getAttribute('aria-pressed')==='false'")
            client.js("document.querySelector('[data-degree-series=in]').click();document.querySelector('[data-degree-series=out]').click()")
            check("Week 1 distribution can show incoming counts alone", "!!document.querySelector('[data-degree-point^=in-]') && !document.querySelector('[data-degree-point^=out-]') && document.querySelector('[data-degree-series=out]').getAttribute('aria-pressed')==='false'")

            navigate(base_url + "week2/index.html", ready["week2/index.html"])
            client.js("document.querySelector('#w2-tail-k').value=106;document.querySelector('#w2-tail-k').dispatchEvent(new Event('input'))")
            check("Week 2 threshold 106 identifies one measured page", "document.querySelector('#w2-tail-readout').dataset.threshold==='106' && document.querySelector('#w2-tail-readout').dataset.count==='1' && document.querySelector('#w2-tail-readout').textContent.includes('245 pages') && document.querySelectorAll('#w2-tail-links a').length===1 && document.querySelector('#w2-tail-links a').textContent.includes('Spider-Man')")
            client.js("document.querySelector('#w2-tail-k').value=1;document.querySelector('#w2-tail-k').dispatchEvent(new Event('input'))")
            check("Week 2 threshold one retains all 245 positive-degree pages", "document.querySelector('#w2-tail-readout').dataset.threshold==='1' && document.querySelector('#w2-tail-readout').dataset.count==='245' && document.querySelector('#w2-tail-readout').textContent.includes('100.0%')")
            client.js("window.__editorialMeasured=JSON.stringify(Array.from(document.querySelectorAll('#w2-ccdf-plot .w2-measured-point'),e=>[e.dataset.degree,e.getAttribute('cx'),e.getAttribute('cy')]));window.__editorialGuide=document.querySelector('#w2-ccdf-plot polyline').getAttribute('points');document.querySelector('#w2-guide-slope').value=2.2;document.querySelector('#w2-guide-slope').dispatchEvent(new Event('input'))")
            check("Week 2 changing the illustrative guide preserves measured points", "JSON.stringify(Array.from(document.querySelectorAll('#w2-ccdf-plot .w2-measured-point'),e=>[e.dataset.degree,e.getAttribute('cx'),e.getAttribute('cy')]))===window.__editorialMeasured && document.querySelector('#w2-ccdf-plot polyline').getAttribute('points')!==window.__editorialGuide && document.querySelector('#w2-guide-value').textContent==='2.20'")
            check("Week 2 caption follows the chosen slope and distinguishes its static download", "document.querySelector('#ccdf-switch-caption').textContent.includes('2.20') && document.querySelector('#ccdf-switch-caption').textContent.includes('not fitted models') && document.querySelector('#ccdf-download-link').textContent.includes('Download static reference')")
            client.js("document.querySelector('#w2-show-reference').click()")
            check("Week 2 reference switch leaves the observations visible", "document.querySelector('#w2-show-reference').checked===false && document.querySelectorAll('#w2-ccdf-plot polyline').length===0 && document.querySelectorAll('#w2-ccdf-plot .w2-measured-point').length>0 && JSON.stringify(Array.from(document.querySelectorAll('#w2-ccdf-plot .w2-measured-point'),e=>[e.dataset.degree,e.getAttribute('cx'),e.getAttribute('cy')]))===window.__editorialMeasured")
            check("Week 2 hidden references also disappear from its caption and legend", "document.querySelector('#ccdf-switch-caption').textContent.includes('Only the observations are shown') && document.querySelector('[data-w2-legend=guide]').hidden && document.querySelector('[data-w2-legend=poisson]').hidden && document.querySelector('#ccdf-download-link').textContent.includes('Download static reference')")
            client.js("document.querySelector('[data-ccdf-view=fit]').click()")
            check("Week 2 tail view updates the live plot and downloadable fallback", "document.querySelector('#w2-ccdf-plot').dataset.view==='fit' && document.querySelector('#ccdf-switch-img').getAttribute('src').endsWith('ccdf-fit.svg') && document.querySelector('#ccdf-download-link').href.endsWith('/assets/figures/ccdf-fit.svg') && document.querySelector('[data-ccdf-view=fit]').getAttribute('aria-pressed')==='true'")
            client.js("document.querySelector('#w2-ccdf-plot .w2-measured-point[data-degree=\"106\"]').focus()")
            press_key("Enter", "Enter", 13)
            check("Week 2 measured points are keyboard inspectable", "document.querySelector('#w2-tail-readout').dataset.threshold==='106' && document.querySelector('#w2-tail-readout').dataset.count==='1'")
            check("Week 2 tail links name a real character in the Week 1 atlas", "(()=>{const u=new URL(document.querySelector('#w2-tail-links a').href);return u.pathname.endsWith('/week1/index.html')&&u.searchParams.get('character')==='Spider-Man'&&u.hash==='#atlas'})()")
            navigate(client.js("document.querySelector('#w2-tail-links a').href"), ready["week1/index.html"])
            check("Week 2 character link opens Spider-Man's dossier", "document.querySelector('#dossier h3').textContent==='Spider-Man' && location.hash==='#atlas'")

            navigate(base_url + "week3/index.html", ready["week3/index.html"])
            check("Week 3 story retains its downloadable static figure and separate game", "!!document.querySelector('#w3-story-static img[src$=\"week3-removal.svg\"]') && document.querySelector('#w3-story-static').hidden && !document.querySelector('#w3-disconnect, #w3-route-form, script[src$=\"week3.js\"]') && !window.CROSSTALK_WEEK3 && !window.CROSSTALK_DATA && CROSSTALK_WEEK3_FIGURE.removal.trials===200")
            check("Week 3 reproduces every exact removal count from its compact bundle", "CROSSTALK_WEEK3_FIGURE.removal.degree.every((degree,k)=>{const s=document.querySelector('#w3-story-removal');s.value=k;s.dispatchEvent(new Event('input'));return Number(document.querySelector('#w3-story-degree').textContent)===degree && Number(document.querySelector('#w3-story-betweenness').textContent)===CROSSTALK_WEEK3_FIGURE.removal.betweenness[k] && document.querySelector('#w3-story-random').textContent===CROSSTALK_WEEK3_FIGURE.removal.random[k].mean.toFixed(1)})")
            client.js("document.querySelector('[data-w3-budget=\"150\"]').click()")
            check("Week 3 150-page preset compares targeted collapse with random survival", "document.querySelector('#w3-story-removal').value==='150' && document.querySelector('#w3-story-degree').textContent==='9' && document.querySelector('#w3-story-betweenness').textContent==='9' && document.querySelector('#w3-story-random').textContent==='128.0' && document.querySelector('#w3-story-band').textContent.includes('119–137')")
            client.js("document.querySelector('[data-w3-budget=\"30\"]').click()")
            check("Week 3 30-page preset shows exact values and the random percentile band", "document.querySelector('#w3-story-degree').textContent==='222' && document.querySelector('#w3-story-betweenness').textContent==='225' && document.querySelector('#w3-story-random').textContent==='247.6' && document.querySelector('#w3-story-band').textContent.includes('244–252') && !!document.querySelector('#w3-story-removal-svg path[fill-opacity]') && document.querySelector('[data-w3-budget=\"30\"]').getAttribute('aria-pressed')==='true'")
            client.js("document.querySelector('#w3-story-chart').focus()")
            press_key("ArrowRight", "ArrowRight", 39)
            check("Week 3 chart arrow key advances its removal budget and accessible value", "document.querySelector('#w3-story-removal').value==='31' && document.querySelector('#w3-story-chart').getAttribute('aria-valuenow')==='31' && Number(document.querySelector('#w3-story-degree').textContent)===CROSSTALK_WEEK3_FIGURE.removal.degree[31]")
            press_key("Home", "Home", 36)
            check("Week 3 chart Home returns to the original mainland", "document.querySelector('#w3-story-removal').value==='0' && document.querySelector('#w3-story-degree').textContent==='277'")
            press_key("End", "End", 35)
            check("Week 3 chart End leaves zero pages in all three trajectories", "document.querySelector('#w3-story-removal').value==='303' && ['degree','betweenness','random'].every(k=>Number(document.querySelector('#w3-story-'+k).textContent)===0)")
            client.js("document.querySelector('[data-w3-budget=\"30\"]').click();document.querySelector('#w3-story-chart').scrollIntoView({block:'center',behavior:'instant'})")
            next_frame()
            hover = client.js("(()=>{const s=document.querySelector('#w3-story-removal-svg'),v=s.viewBox.baseVal,p=new DOMPoint(42+(v.width-62)*150/303,100).matrixTransform(s.getScreenCTM());return{x:p.x,y:p.y}})()")
            client.call("Input.dispatchMouseEvent", {"type":"mouseMoved",**hover})
            next_frame()
            check("Week 3 pointer inspection leaves the chosen slider budget intact", "document.querySelector('#w3-story-removal').value==='30' && document.querySelector('#w3-story-chart').getAttribute('aria-valuenow')==='150' && document.querySelector('#w3-story-inspection').textContent.includes('budget is 30') && document.querySelector('#w3-story-degree').textContent==='9' && !document.querySelector('#w3-story-reset').hidden")
            client.js("document.querySelector('#w3-story-reset').click()")
            check("Week 3 return button clears the transient inspection", "document.querySelector('#w3-story-chart').getAttribute('aria-valuenow')==='30' && document.querySelector('#w3-story-degree').textContent==='222' && document.querySelector('#w3-story-reset').hidden")
            client.call("Input.dispatchMouseEvent", {"type":"mouseMoved",**hover})
            client.js("document.querySelector('#w3-story-chart').focus()")
            press_key("Escape", "Escape", 27)
            check("Week 3 Escape restores the pinned budget after inspection", "document.querySelector('#w3-story-chart').getAttribute('aria-valuenow')==='30' && document.querySelector('#w3-story-degree').textContent==='222'")
            check("Week 3 rank diagram begins with Black Widow's measured rise", "document.querySelectorAll('#w3-story-rank-names button').length===8 && document.querySelector('#w3-story-rank-readout').textContent.includes('#23') && document.querySelector('#w3-story-rank-readout').textContent.includes('#8') && document.querySelector('#w3-story-rank-readout').textContent.includes('15 places higher')")
            client.js("document.querySelector('#w3-story-rank-names [data-character=\"Hercules_(Marvel_Comics)\"]').click()")
            check("Week 3 rank selection exposes Hercules's measured rank gap", "document.querySelector('#w3-story-rank-readout').textContent.includes('#20') && document.querySelector('#w3-story-rank-readout').textContent.includes('#7') && document.querySelector('#w3-story-rank-readout').textContent.includes('13 places higher')")
            client.js("document.querySelector('#w3-story-rank-names [data-character=Spider-Man]').focus()")
            press_key("Enter", "Enter", 13)
            check("Week 3 rank diagram accepts keyboard selection", "document.querySelector('#w3-story-rank-names [data-character=Spider-Man]').getAttribute('aria-pressed')==='true' && document.querySelector('#w3-story-rank-readout').textContent.includes('same position')")

            # Native touch input must distinguish reading gestures from taps.
            # A canceled vertical pan must never commit its starting position.
            client.call("Emulation.setDeviceMetricsOverride", {"width":390,"height":844,"deviceScaleFactor":1,"mobile":True})
            client.call("Emulation.setTouchEmulationEnabled", {"enabled":True,"maxTouchPoints":1})
            client.js("document.querySelector('[data-w3-budget=\"30\"]').click();document.querySelector('#w3-story-chart').scrollIntoView({block:'center',behavior:'instant'})")
            next_frame()
            touch_start = client.js("(()=>{const s=document.querySelector('#w3-story-removal-svg'),v=s.viewBox.baseVal,p=new DOMPoint(42+(v.width-62)*150/303,220).matrixTransform(s.getScreenCTM());window.__editorialSwipeScroll=scrollY;return{x:p.x,y:p.y}})()")
            client.call("Input.dispatchTouchEvent", {"type":"touchStart","touchPoints":[{**touch_start,"radiusX":1,"radiusY":1,"force":1,"id":1}]})
            next_frame()
            check("Week 3 touch contact waits for release before changing the budget", "document.querySelector('#w3-story-removal').value==='30' && document.querySelector('#w3-story-degree').textContent==='222'")
            for distance in (20,40,70,100,120):
                client.call("Input.dispatchTouchEvent", {"type":"touchMove","touchPoints":[{"x":touch_start["x"],"y":touch_start["y"]-distance,"radiusX":1,"radiusY":1,"force":1,"id":1}]})
                next_frame()
            # Hold before lifting to avoid inertial scrolling into the next tap.
            time.sleep(.2)
            client.call("Input.dispatchTouchEvent", {"type":"touchEnd","touchPoints":[]})
            next_frame()
            check("Week 3 vertical touch swipe scrolls the story without committing a removal", "scrollY>window.__editorialSwipeScroll+20 && document.querySelector('#w3-story-removal').value==='30' && document.querySelector('#w3-story-degree').textContent==='222'")
            client.js("document.querySelector('#w3-story-chart').scrollIntoView({block:'center',behavior:'instant'})")
            next_frame()
            tap = client.js("(()=>{const s=document.querySelector('#w3-story-removal-svg'),v=s.viewBox.baseVal,p=new DOMPoint(42+(v.width-62)*150/303,100).matrixTransform(s.getScreenCTM());return{x:p.x,y:p.y}})()")
            client.call("Input.dispatchTouchEvent", {"type":"touchStart","touchPoints":[{**tap,"radiusX":1,"radiusY":1,"force":1,"id":2}]})
            next_frame()
            client.call("Input.dispatchTouchEvent", {"type":"touchEnd","touchPoints":[]})
            next_frame()
            check("Week 3 completed touch tap commits its exact 150-page budget", "document.querySelector('#w3-story-removal').value==='150' && document.querySelector('#w3-story-degree').textContent==='9' && document.querySelector('#w3-story-betweenness').textContent==='9' && document.querySelector('#w3-story-random').textContent==='128.0'")
            client.call("Emulation.setTouchEmulationEnabled", {"enabled":False})
            client.call("Emulation.setDeviceMetricsOverride", {"width":1440,"height":1050,"deviceScaleFactor":1,"mobile":False})

            # Chapter controls and layout need checks on every story, since each
            # page combines its own figures with the shared reading guide.
            for route, chapter in (("week1/index.html","degrees"),("week2/index.html","paradox"),("week3/index.html","blackout")):
                navigate(base_url + route, ready[route])
                check(f"{route} has one story-only reading rail", "document.body.classList.contains('issue-story') && document.querySelectorAll('.journal-rail').length===1 && document.querySelector('.journal-rail select').options.length>=4")
                client.js(f"const chapterSelect=document.querySelector('.journal-rail select');chapterSelect.value={json.dumps(chapter)};chapterSelect.dispatchEvent(new Event('change'))")
                next_frame()
                check(f"{route} chapter selector navigates to {chapter}", f"location.hash==={json.dumps('#'+chapter)} && scrollY>0")
            for route in ready:
                navigate(base_url + route, ready[route])
                for width in (360,390,768):
                    client.call("Emulation.setDeviceMetricsOverride", {"width":width,"height":844,"deviceScaleFactor":1,"mobile":True})
                    next_frame()
                    check(f"editorial {route} at {width}px has no horizontal overflow", "document.documentElement.scrollWidth<=document.documentElement.clientWidth")
                    check(f"editorial {route} at {width}px keeps its primary figure within the viewport", "(()=>{const e=document.querySelector('.latest-plate,#cover-map,#degree-scatter,#w2-ccdf-live,#w3-story-explorer'),r=e.getBoundingClientRect();return r.left>=-1&&r.right<=document.documentElement.clientWidth+1})()")
                    if width == 390 and route == "week1/index.html":
                        check("Week 1 mobile plots preserve readable 680px graphics within scrollable regions", "['distribution-chart','degree-scatter'].every(id=>{const e=document.getElementById(id);return e.scrollWidth>e.clientWidth && parseFloat(getComputedStyle(e.querySelector('svg')).width)>=680 && getComputedStyle(e).overflowX==='auto'})")
                        check("Week 1 mobile plots visibly explain sideways scrolling", "['distribution-scroll-hint','degree-scatter-scroll-hint'].every(id=>{const hint=document.getElementById(id);return hint.getClientRects().length>0 && hint.textContent.includes('Scroll sideways')})")
                    if width == 390 and route != "index.html":
                        client.js("window.scrollTo({top:0,behavior:'instant'})")
                        next_frame()
                        screenshot("editorial-" + route.split('/')[0] + "-mobile.png", full=True)
                        if route.startswith("week2/"):
                            client.js("document.querySelector('#w2-ccdf-plot').closest('figure').scrollIntoView({block:'start',behavior:'instant'})")
                        else:
                            figure = ".degree-portrait" if route.startswith("week1/") else ".cover-observatory" if route.startswith("explore/") else "#w3-story-figure"
                            client.js(f"document.querySelector({json.dumps(figure)}).scrollIntoView({{block:'start',behavior:'instant'}})")
                        next_frame()
                        screenshot("editorial-" + route.split('/')[0] + "-mobile-figure.png")
                client.call("Emulation.setDeviceMetricsOverride", {"width":1440,"height":1050,"deviceScaleFactor":1,"mobile":False})

            navigate((ROOT / "_site/index.html").as_uri(), ready["index.html"])
            check("offline editorial home keeps the reading room and cabinet link", "location.protocol==='file:' && !!document.querySelector('.latest-spread') && !!document.querySelector('a[href=\"explore/index.html\"]') && !window.CROSSTALK_COVER")
            navigate((ROOT / "_site/explore/index.html").as_uri(), ready["explore/index.html"])
            client.js("document.querySelector('[data-cover-world=marvel]').click();document.querySelector('#cover-person').value='Baymax';document.querySelector('#cover-person').dispatchEvent(new Event('change'))")
            check("offline network cabinet switches real networks and follows a name", "location.protocol==='file:' && !window.CROSSTALK_DATA && document.querySelector('#cover-person-note h3').textContent==='Baymax' && document.querySelector('#cover-total-nodes').textContent==='303' && document.querySelector('#cover-open').href.endsWith('/week1/index.html#atlas')")
            navigate((ROOT / "_site/week1/index.html").as_uri(), ready["week1/index.html"])
            client.js("document.querySelector('[data-degree-view=local]').click();document.querySelector('[data-degree-scale=sqrt]').click();document.querySelector('#degree-character').value='Baymax';document.querySelector('#degree-character').dispatchEvent(new Event('change'))")
            check("offline Week 1 scatter keeps the real close-up and isolate readout", "location.protocol==='file:' && document.querySelectorAll('#degree-scatter [data-degree-character]').length===279 && document.querySelector('#degree-scatter svg').dataset.axisScale==='sqrt' && document.querySelector('#degree-character-readout').textContent.includes('17 pages')")
            navigate((ROOT / "_site/week2/index.html").as_uri(), ready["week2/index.html"])
            client.js("document.querySelector('#w2-tail-k').value=106;document.querySelector('#w2-tail-k').dispatchEvent(new Event('input'));document.querySelector('#w2-guide-slope').value=1.7;document.querySelector('#w2-guide-slope').dispatchEvent(new Event('input'))")
            check("offline Week 2 tail and guide controls retain exact observations", "location.protocol==='file:' && document.querySelector('#w2-tail-readout').dataset.count==='1' && document.querySelector('#w2-tail-readout').dataset.threshold==='106' && document.querySelector('#w2-guide-value').textContent==='1.70' && document.querySelector('#w2-tail-links a').protocol==='file:'")
            navigate((ROOT / "_site/week3/index.html").as_uri(), ready["week3/index.html"])
            client.js("document.querySelector('[data-w3-budget=\"150\"]').click();document.querySelector('#w3-story-rank-names [data-character=\"Hercules_(Marvel_Comics)\"]').click()")
            check("offline Week 3 removal and ranking figures work without game data", "location.protocol==='file:' && !window.CROSSTALK_WEEK3 && !window.CROSSTALK_DATA && document.querySelector('#w3-story-degree').textContent==='9' && document.querySelector('#w3-story-random').textContent==='128.0' && document.querySelector('#w3-story-rank-readout').textContent.includes('13 places higher')")
            client.call("Emulation.setEmulatedMedia", {"features":[]})

        if args.editorial_only:
            check_editorial()
            failures = [event for event in client.events if event.get("method") == "Runtime.exceptionThrown"]
            if failures or QuietHandler.errors:
                raise AssertionError({"javascript_errors":failures,"http_errors":QuietHandler.errors})
            checks["no editorial JavaScript exceptions or missing resources"] = True
            (preview / "editorial-checks.json").write_text(json.dumps(checks,indent=2)+"\n",encoding="utf-8")
            print(json.dumps(checks,indent=2))
            return

        def check_week4():
            ready = "document.readyState==='complete' && document.querySelector('#w4-map-stage')?.dataset.state==='ready' && document.querySelector('#w4-hero-map')?.dataset.state==='ready'"
            navigate(base_url + "week4/index.html", ready)
            next_frame()
            # Keep initial visuals available even if a later interaction fails.
            screenshot("week4.png", full=True)
            screenshot("week4-hero.png")
            check("Week 4 loads the complete real core and edge roster", "CROSSTALK_WEEK4.explorer.nodes.length===1374 && CROSSTALK_WEEK4.explorer.edges.length===9139 && document.querySelector('#w4-map-stage').dataset.visibleNodes==='1374' && document.querySelector('#w4-map-stage').dataset.visibleEdges==='9139'")
            check("philosopher suggestions and named directory are complete", "document.querySelector('#w4-names').options.length===1374 && document.querySelector('#w4-community').options.length===10 && Array.from(document.querySelector('#w4-community').options).slice(1).every(o=>o.textContent.includes('('))")
            check("Aristotle opens with 300 real neighbours", "document.querySelector('#w4-dossier').dataset.selectedId==='Aristotle' && document.querySelector('#w4-dossier').dataset.degree==='300' && document.querySelector('#w4-dossier').textContent.includes('521')")
            check("community ribbons account for every philosopher", "Array.from(document.querySelectorAll('#w4-flow [data-w4-overlap]')).reduce((sum,e)=>sum+Number(e.dataset.w4Overlap),0)===1374")
            client.js("document.querySelector('#w4-neighbors').click()")
            check("Aristotle neighbourhood contains him and all 300 neighbours", "document.querySelector('#w4-neighbors').getAttribute('aria-pressed')==='true' && document.querySelector('#w4-map-stage').dataset.visibleNodes==='301'")
            client.js("document.querySelector('#w4-reset').click();document.querySelector('[data-w4-lens=weighted]').click()")
            check("weighted lens switches communities and preserves full ties", "document.querySelector('[data-w4-lens=weighted]').getAttribute('aria-pressed')==='true' && document.querySelector('#w4-map-stage').dataset.lens==='weighted' && document.querySelector('#w4-map-stage').dataset.visibleEdges==='9139' && document.querySelector('#w4-community').options.length===9")
            check("weighted comparison reports NMI and 383 matched movers", "document.querySelector('#w4-nmi').textContent==='0.622' && document.querySelector('#w4-movers-count').textContent==='383' && document.querySelector('#w4-weighted-count').textContent==='8'")
            client.js("document.querySelector('#w4-search').value='a philosopher who is not in this roster';document.querySelector('#w4-search-form').requestSubmit()")
            check("invalid search explains failure and preserves selection", "document.querySelector('#w4-search-status').textContent.includes('No philosopher found') && document.querySelector('#w4-dossier').dataset.selectedId==='Aristotle'")
            client.js("document.querySelector('#w4-search').value='  plato  ';document.querySelector('#w4-search-form').requestSubmit()")
            check("search normalizes names and selects a real philosopher", "document.querySelector('#w4-dossier').dataset.selectedId==='Plato' && document.querySelector('#w4-search-status').textContent.includes('Plato selected') && document.querySelector('#w4-dossier .w4-wiki-link').href==='https://en.wikipedia.org/wiki/Plato'")
            client.js("document.querySelector('#w4-search').value='John';document.querySelector('#w4-search-form').requestSubmit()")
            check("ambiguous search requests a complete name", "document.querySelector('#w4-search-status').textContent.includes('names match') && document.querySelector('#w4-dossier').dataset.selectedId==='Plato'")
            client.js("document.querySelector('[data-w4-lens=unweighted]').click();const directory=document.querySelector('#w4-community');directory.value='0';directory.dispatchEvent(new Event('change'))")
            check("directory filters to its 268-member community", "document.querySelector('#w4-map-stage').dataset.visibleNodes==='268' && document.querySelector('#w4-community').value==='0'")
            client.js("document.querySelector('#w4-reset').click();document.querySelector('[data-w4-focus=Aristotle]').click()")
            check("Fit map clears the directory and neighbourhood filters", "document.querySelector('#w4-community').value==='all' && document.querySelector('#w4-map-stage').dataset.visibleNodes==='1374' && document.querySelector('#w4-neighbors').getAttribute('aria-pressed')==='false'")
            client.js("document.querySelector('#w4-map').scrollIntoView({block:'center',behavior:'instant'});document.querySelector('#w4-map').focus()")
            next_frame()
            client.js("window.__w4FitImage=document.querySelector('#w4-map').toDataURL()")
            press_key("+", "Equal", 187)
            check("canvas plus key visibly zooms the actual map", "document.querySelector('#w4-map').toDataURL()!==window.__w4FitImage")
            client.js("window.__w4ZoomedImage=document.querySelector('#w4-map').toDataURL()")
            press_key("-", "Minus", 189)
            check("canvas minus key visibly zooms back out", "document.querySelector('#w4-map').toDataURL()!==window.__w4ZoomedImage")
            press_key("0", "Digit0", 48)
            check("canvas zero key restores the fitted map", "document.querySelector('#w4-map').toDataURL()===window.__w4FitImage")
            press_key("ArrowLeft", "ArrowLeft", 37)
            check("canvas arrow key visibly pans the map", "document.querySelector('#w4-map').toDataURL()!==window.__w4FitImage")
            press_key("Escape", "Escape", 27)
            check("canvas Escape key restores the map", "document.querySelector('#w4-map').toDataURL()===window.__w4FitImage")
            # Pointer input selects a drawn node, rather than calling its handler.
            pointer=client.js("""(() => {const c=document.querySelector('#w4-map'),r=c.getBoundingClientRect(),n=CROSSTALK_WEEK4.explorer.nodes.find(n=>n.id==='Plato'),padding=r.width<600?24:38,scale=Math.min((r.width-padding*2)/1000,(r.height-padding*2)/760);return{x:r.x+(r.width-1000*scale)/2+n.x*scale,y:r.y+(r.height-760*scale)/2+n.y*scale}})()""")
            client.call("Input.dispatchMouseEvent", {"type":"mousePressed",**pointer,"button":"left","clickCount":1})
            client.call("Input.dispatchMouseEvent", {"type":"mouseReleased",**pointer,"button":"left","clickCount":1})
            check("clicking Plato's drawn dot selects his dossier", "document.querySelector('#w4-dossier').dataset.selectedId==='Plato'")
            for alpha, edges, attached, giant, components in ((.05,292,348,116,1096),(.2,1540,950,816,478),(.5,5641,1284,1270,98)):
                client.js(f"document.querySelector('.w4-alpha-presets [data-w4-alpha=\"{alpha}\"]').click()")
                check(f"backbone alpha {alpha:.2f} matches the published graph counts", f"Number(document.querySelector('#w4-backbone-edges').textContent.replaceAll(',',''))==={edges} && Number(document.querySelector('#w4-backbone-giant').textContent.replaceAll(',',''))==={giant} && Number(document.querySelector('#w4-backbone-components').textContent.replaceAll(',',''))==={components} && document.querySelector('#w4-map-stage').dataset.visibleNodes==='{attached}' && document.querySelector('#w4-map-stage').dataset.visibleEdges==='{edges}' && document.querySelector('#w4-map-stage').dataset.lens==='backbone'")
                check(f"backbone alpha {alpha:.2f} updates curve and accessible readout", f"document.querySelector('#w4-alpha').value==='{alpha}' && document.querySelector('#w4-backbone-chart').getAttribute('aria-label').includes('alpha {alpha:.2f}') && document.querySelector('#w4-backbone-chart g[aria-hidden=true]').getAttribute('transform')==='translate({70+alpha*790:g},0)'")
            client.js("document.querySelector('#w4-alpha').value='.1';document.querySelector('#w4-alpha').dispatchEvent(new Event('input',{bubbles:true}))")
            check("dragging the significance dial updates the connected giant", "document.querySelector('#w4-backbone-giant').textContent==='419' && document.querySelector('#w4-visible-edges').textContent==='649'")
            check("three backbone plates show distinct measured giants", "document.querySelectorAll('.w4-backbone-plate').length===3 && document.querySelector('.w4-backbone-plate[data-alpha=\"0.05\"]').textContent.includes('116') && document.querySelector('.w4-backbone-plate[data-alpha=\"0.2\"]').textContent.includes('816') && document.querySelector('.w4-backbone-plate[data-alpha=\"0.5\"]').textContent.includes('1,270')")
            client.js("document.querySelector('.w4-alpha-presets [data-w4-alpha=\"0.2\"]').click();document.querySelector('[data-w4-lens=unweighted]').click();document.querySelector('[data-w4-focus=Aristotle]').click();document.querySelector('#w4-reset').click();window.scrollTo(0,0)")
            next_frame()
            check("Week 4 desktop has no horizontal overflow", "document.documentElement.scrollWidth<=document.documentElement.clientWidth")
            screenshot("week4.png", full=True)
            screenshot("week4-hero.png")
            client.js("document.querySelector('#atlas').scrollIntoView({block:'start',behavior:'instant'})")
            next_frame()
            screenshot("week4-atlas.png")
            for width in (390,360,768):
                client.call("Emulation.setDeviceMetricsOverride", {"width":width,"height":844,"deviceScaleFactor":1,"mobile":True})
                next_frame()
                check(f"Week 4 {width}px has no horizontal overflow", "document.documentElement.scrollWidth<=document.documentElement.clientWidth")
                check(f"Week 4 {width}px canvas fits its stage", "Math.abs(document.querySelector('#w4-map').getBoundingClientRect().width-document.querySelector('#w4-map-stage').getBoundingClientRect().width)<1")
                if width==390:
                    client.js("document.querySelector('#w4-reset').click();window.scrollTo(0,0)")
                    next_frame()
                    screenshot("week4-mobile.png", full=True)
            client.call("Emulation.setDeviceMetricsOverride", {"width":1440,"height":1050,"deviceScaleFactor":1,"mobile":False})
            navigate((ROOT / "_site/week4/index.html").as_uri(), ready)
            check("offline Week 4 loads its local graph without fetch", "location.protocol==='file:' && document.querySelector('#w4-map-stage').dataset.visibleNodes==='1374' && document.querySelector('#w4-nmi').textContent==='0.622'")
            client.js("document.querySelector('.w4-alpha-presets [data-w4-alpha=\"0.05\"]').click()")
            check("offline backbone controls still compute the real giant", "document.querySelector('#w4-backbone-giant').textContent==='116' && document.querySelector('#w4-map-stage').dataset.visibleEdges==='292'")

        if args.week4_only:
            check_week4()
            failures=[event for event in client.events if event.get("method")=="Runtime.exceptionThrown"]
            if failures or QuietHandler.errors:
                raise AssertionError({"javascript_errors":failures,"http_errors":QuietHandler.errors})
            checks["no Week 4 JavaScript exceptions or missing resources"]=True
            (preview / "week4-checks.json").write_text(json.dumps(checks,indent=2)+"\n",encoding="utf-8")
            print(json.dumps(checks,indent=2))
            return

        def check_grunge():
            navigate(base_url + "grunge/index.html", "document.readyState==='complete' && document.querySelector('#grunge-from')?.options.length===15")
            check("B-side visibly links back to Week 3", "Array.from(document.querySelectorAll('main a[href]')).some(a=>new URL(a.href).pathname.endsWith('/week3/index.html') && a.getClientRects().length>0)")
            check("grunge sample has its own real data", "CROSSTALK_GRUNGE.nodes.length===15 && CROSSTALK_GRUNGE.edges.length===55 && document.querySelectorAll('#grunge-map circle').length===15")
            check("grunge initial chain spans three hops", "document.querySelectorAll('.grunge-chain li').length===4")
            client.js("document.querySelector('#grunge-from').value='Mark Arm';document.querySelector('#grunge-to').value='Dave Grohl';document.querySelector('#grunge-direction').value='directed';document.querySelector('#grunge-route-form').requestSubmit()")
            check("grunge explicitly handles no directed route", "document.querySelector('#grunge-route-result').textContent.includes('No observed route')")
            client.js("document.querySelector('#grunge-to').value='Mark Arm';document.querySelector('#grunge-route-form').requestSubmit()")
            check("grunge same-node route has zero hops", "document.querySelectorAll('.grunge-chain li').length===1 && document.querySelector('#grunge-route-result').textContent.includes('Zero hops')")
            check("radio waits for an interaction before loading YouTube", "!document.querySelector('#radio-player-wrap iframe') && !document.querySelector('script[src*=youtube]') && !document.querySelector('.grunge-radio.is-playing')")
            old_station=client.js("document.querySelector('#radio-external').href")
            client.js("document.querySelector('#radio-next').click()")
            check("radio station buttons change the listening link", "document.querySelector('#radio-external').href !== " + json.dumps(old_station))
            screenshot("grunge.png", full=True)
            for width in (390,360,768):
                client.call("Emulation.setDeviceMetricsOverride", {"width":width,"height":844,"deviceScaleFactor":1,"mobile":True})
                check(f"grunge {width}px no horizontal overflow", "document.documentElement.scrollWidth <= document.documentElement.clientWidth")
                if width==390: screenshot("grunge-mobile.png", full=True)
            # Simulate provider events to test controls deterministically without
            # claiming that an external video stream was played by this check.
            client.js("window.YT={Player:function(id,options){window.__radioEvents=options.events;const frame=document.createElement('iframe');document.getElementById(id).replaceWith(frame);this.getIframe=()=>frame;this.setVolume=()=>{};this.playVideo=()=>{window.__radioCommand='play'};this.pauseVideo=()=>{window.__radioCommand='pause'};this.loadVideoById=(id)=>{window.__radioCommand=id};this.cueVideoById=this.loadVideoById;window.__radioMock=this}};document.querySelector('#radio-play').click()")
            client.js("window.__radioEvents.onReady({target:window.__radioMock})")
            check("radio requests playback after provider ready", "window.__radioCommand===new URL(document.querySelector('#radio-external').href).searchParams.get('v') && !document.querySelector('.grunge-radio.is-playing')")
            client.js("window.__radioEvents.onStateChange({data:1})")
            check("radio shows playing only on provider playback event", "!!document.querySelector('.grunge-radio.is-playing') && document.querySelector('#radio-play').textContent.includes('Pause')")
            client.js("document.querySelector('#radio-play').click();window.__radioEvents.onStateChange({data:2})")
            check("radio pause works through provider", "window.__radioCommand==='pause' && !document.querySelector('.grunge-radio.is-playing')")
            client.js("window.__radioEvents.onError({data:150})")
            check("radio provides an external fallback on playback failure", "document.querySelector('#radio-status').textContent.includes('cannot play') && document.querySelector('#radio-external').href.startsWith('https://www.youtube.com/watch')")
            client.call("Emulation.setDeviceMetricsOverride", {"width":1440,"height":1050,"deviceScaleFactor":1,"mobile":False})

        if args.grunge_only:
            check_grunge()
            failures = [event for event in client.events if event.get("method") == "Runtime.exceptionThrown"]
            if failures or QuietHandler.errors:
                raise AssertionError({"javascript_errors":failures,"http_errors":QuietHandler.errors})
            (preview / "grunge-checks.json").write_text(json.dumps(checks,indent=2)+"\n",encoding="utf-8")
            print(json.dumps(checks,indent=2))
            return

        check_editorial()
        navigate(base_url)
        registry = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))
        published_weeks = sorted(week["number"] for week in registry["weeks"] if week["status"] == "published")
        check("homepage is Crosstalk", "document.title.includes('CROSSTALK') && !!document.querySelector('.home-page')")
        check("homepage exposes every registry week and published issue", f"document.querySelectorAll('.week-entry').length==={len(registry['weeks'])} && document.querySelectorAll('a.week-entry').length==={len(published_weeks)}")
        check("homepage leads with the latest published week", f"document.querySelector('.latest-spread a[href]').getAttribute('href')==='week{published_weeks[-1]}/index.html'")
        check("home stays lightweight", "!window.CROSSTALK_DATA && !document.querySelector('#network-atlas')")
        check("group names rendered", "document.body.textContent.includes('Christos Diamantis') && document.body.textContent.includes('s253102') && document.body.textContent.includes('Dávid Weiner') && document.body.textContent.includes('s253347')")
        check("clear direct week navigation", f"document.querySelectorAll('.issue-nav a').length==={len(published_weeks)+1} && !!document.querySelector('#games')")
        check("header no longer offers Open an issue", "!document.querySelector('header').textContent.toLowerCase().includes('open an issue')")
        check("homepage lists the separate Week 3 game", "!!document.querySelector('#games a[href=\"play/switchboard.html\"]')")
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
        game_url = base_url + "play/index.html"
        storage_key = "crosstalk-crossed-wires-v2"
        clock_script = None

        def freeze_clock(instant):
            """Control browser time without an application-only release bypass."""
            nonlocal clock_script
            if clock_script:
                client.call("Page.removeScriptToEvaluateOnNewDocument", {"identifier":clock_script})
            source = """(() => {
                const RealDate = Date;
                window.__cwTestNow = RealDate.parse(INSTANT);
                class FixedDate extends RealDate {
                    constructor(...args) { super(...(args.length ? args : [window.__cwTestNow])); }
                    static now() { return window.__cwTestNow; }
                }
                window.Date = FixedDate;
            })();""".replace("INSTANT", json.dumps(instant))
            clock_script = client.call("Page.addScriptToEvaluateOnNewDocument", {"source":source})["identifier"]

        def await_check(name, expression):
            for _ in range(40):
                if client.js(expression):
                    break
                time.sleep(.1)
            check(name, expression)

        assigned_count = "document.querySelectorAll('#cw-wires .cw-wire-assigned').length"
        first_direction = "document.querySelector('#cw-wires [data-edge=\"0\"]').dataset.direction"
        saved_state = f"JSON.parse(localStorage.getItem({json.dumps(storage_key)}))"
        solve_board = """(p => {
            document.querySelector('#cw-reset').click();
            p.edges.forEach((edge,i) => {
                const selector=`#cw-wires [data-edge='${i}']`;
                document.querySelector(selector).click();
                if(edge.source!==edge.a) document.querySelector(selector).click();
            });
            document.querySelector('#cw-check').click();
            return !!document.querySelector('.cw-is-solved') &&
                document.querySelectorAll('.cw-socket-matched').length===p.nodes.length;
        })"""

        freeze_clock("2026-09-13T15:00:00Z")
        navigate(game_url, game_ready)
        client.js(f"localStorage.removeItem({json.dumps(storage_key)});localStorage.removeItem('crosstalk-crossed-wires-v1')")
        navigate(game_url, game_ready)
        check("weekly shift is the default with future releases locked", "document.querySelector('#cw-weekly').getAttribute('aria-pressed')==='true' && document.querySelector('#cw-week-select').value==='shift-01' && Array.from(document.querySelector('#cw-week-select').options).filter(o=>!o.disabled).length===1")
        check("twelve practice boards and a year of weekly shifts", "document.querySelector('#cw-select').options.length===12 && CROSSTALK_PUZZLES.puzzles.length===12 && CROSSTALK_PUZZLES.weeks.length===52")
        check("weekly shift has three progressively unlocked rounds", "document.querySelectorAll('.cw-round').length===3 && !document.querySelector('.cw-round[data-round=\"0\"]').disabled && document.querySelector('.cw-round[data-round=\"1\"]').disabled && document.querySelector('.cw-round[data-round=\"2\"]').disabled")
        check("release countdown has an explicit timestamp", "!!document.querySelector('#cw-countdown').textContent.trim() && Date.parse(document.querySelector('#cw-release-time').dateTime)===Date.parse('2026-09-16T17:00:00Z')")
        check("game starts with missing arrows", assigned_count + "===0")
        screenshot("game.png", full=True)

        client.js("document.querySelector('#cw-check').click()")
        check("game explains an incomplete board", "document.querySelector('#cw-status').textContent.length>25 && !document.querySelector('.cw-is-solved')")
        client.js("document.querySelector('#cw-diagram').scrollIntoView({block:'center',behavior:'instant'})")
        wire_point = client.js("""(() => {
            const group=document.querySelector('#cw-diagram [data-wire="0"]');
            const line=group.querySelector('path,line');
            const local=line.getPointAtLength(line.getTotalLength()/2);
            const point=new DOMPoint(local.x,local.y).matrixTransform(line.getScreenCTM());
            return {x:point.x,y:point.y};
        })()""")
        client.call("Input.dispatchMouseEvent", {"type":"mousePressed",**wire_point,"button":"left","clickCount":1})
        client.call("Input.dispatchMouseEvent", {"type":"mouseReleased",**wire_point,"button":"left","clickCount":1})
        check("clicking the drawn wire sets its direction", assigned_count + "===1 && " + first_direction + "==='0'")
        client.js("document.querySelector('#cw-diagram [data-wire=\"0\"]').focus()")
        client.call("Input.dispatchKeyEvent", {"type":"rawKeyDown","key":"Enter","code":"Enter","windowsVirtualKeyCode":13,"nativeVirtualKeyCode":13})
        client.call("Input.dispatchKeyEvent", {"type":"keyUp","key":"Enter","code":"Enter","windowsVirtualKeyCode":13,"nativeVirtualKeyCode":13})
        check("drawn wires also respond to the keyboard", first_direction + "==='1'")
        client.js("document.querySelector('#cw-undo').click()")
        check("undo restores the preceding direction", first_direction + "==='0'")
        saved_directions = client.js("Array.from(document.querySelectorAll('#cw-wires .cw-wire'),b=>b.dataset.direction)")
        navigate(game_url, game_ready)
        check("partial board survives reload", "JSON.stringify(Array.from(document.querySelectorAll('#cw-wires .cw-wire'),b=>b.dataset.direction))===" + json.dumps(json.dumps(saved_directions, separators=(',', ':'))))
        client.js("document.querySelector('#cw-reset').click();document.querySelector('#cw-hint').click()")
        check("hint gives a real arrow and a deduction", assigned_count + "===1 && Number(document.querySelector('#cw-hints-used').textContent)===1 && document.querySelector('#cw-status').textContent.length>60")
        client.js("document.querySelector('#cw-reset').click()")
        check("reset clears arrows and the attempt counters", assigned_count + "===0 && Number(document.querySelector('#cw-moves').textContent)===0 && Number(document.querySelector('#cw-hints-used').textContent)===0")
        client.js("document.querySelector('#cw-week-select').value='shift-02';document.querySelector('#cw-week-select').dispatchEvent(new Event('change'))")
        check("a forced change cannot open a future shift", "document.querySelector('#cw-week-select').value==='shift-01' && " + assigned_count + "===0")

        # A complete shift exercises the progressive and blackout variants.
        for round_index in range(3):
            client.js(f"document.querySelector('.cw-round[data-round=\"{round_index}\"]').click()")
            check(f"weekly round {round_index + 1} solves using real edges", solve_board + f"(CROSSTALK_PUZZLES.weeks[0].puzzles[{round_index}])")
            check(f"weekly round {round_index + 1} earns a receipt", "!document.querySelector('#cw-receipt').hidden && document.querySelector('#cw-receipt-rating').textContent.trim().length>0")
            check(f"clean weekly round {round_index + 1} earns three stars", saved_state + f".boards[CROSSTALK_PUZZLES.weeks[0].puzzles[{round_index}].id].bestStars===3")
            if round_index < 2:
                check(f"solving round {round_index + 1} unlocks the next stage", f"!document.querySelector('.cw-round[data-round=\"{round_index + 1}\"]').disabled")
        check("weekly receipt offers a shareable result", "!document.querySelector('#cw-share').disabled")
        client.js("Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async text=>{window.__cwCopied=text}}});document.querySelector('#cw-share').click()")
        await_check("share copies the completed shift and score", "window.__cwCopied?.includes('Shift 01') && window.__cwCopied.includes('9/9 stars') && window.__cwCopied.includes('/play/index.html')")
        client.js("navigator.clipboard.writeText=async()=>{throw new Error('Clipboard unavailable for test')};document.querySelector('#cw-share').click()")
        await_check("share has a selectable fallback when clipboard is unavailable", "!document.querySelector('#cw-share-text').hidden && document.querySelector('#cw-share-text').value.includes('9/9 stars')")
        navigate(game_url, game_ready)
        check("weekly completion and selected round survive reload", saved_state + ".selection.round===2 && !!document.querySelector('.cw-is-solved') && CROSSTALK_PUZZLES.weeks[0].puzzles.every(p=>" + saved_state + ".boards[p.id].bestStars===3)")
        screenshot("game-solved.png", full=True)
        client.js("document.querySelector('#cw-reset').click()")
        check("replaying keeps the best weekly score", saved_state + ".boards[CROSSTALK_PUZZLES.weeks[0].puzzles[2].id].bestStars===3 && !document.querySelector('.cw-is-solved')")
        for width in (390, 360, 768):
            client.call("Emulation.setDeviceMetricsOverride", {"width":width,"height":844,"deviceScaleFactor":1,"mobile":True})
            check(f"weekly blackout board {width}px no horizontal overflow", "document.documentElement.scrollWidth <= document.documentElement.clientWidth")
            if width == 390:
                screenshot("game-mobile.png", full=True)
        client.call("Emulation.setDeviceMetricsOverride", {"width":1440,"height":1050,"deviceScaleFactor":1,"mobile":False})

        client.js("document.querySelector('#cw-practice').click();document.querySelector('#cw-select').value='0';document.querySelector('#cw-select').dispatchEvent(new Event('change'));document.querySelector('#cw-reset').click()")
        client.js("CROSSTALK_PUZZLES.puzzles[0].edges.forEach((e,i)=>{const s=`#cw-wires [data-edge='${i}']`;document.querySelector(s).click();if(e.source===e.a)document.querySelector(s).click()});document.querySelector('#cw-check').click()")
        check("incorrect complete board is rejected", "!document.querySelector('.cw-is-solved') && document.querySelector('#cw-receipt').hidden && document.querySelectorAll('.cw-socket-matched').length<CROSSTALK_PUZZLES.puzzles[0].nodes.length")
        solve_all = """CROSSTALK_PUZZLES.puzzles.every((p,index)=>{
            const picker=document.querySelector('#cw-select');picker.value=index;picker.dispatchEvent(new Event('change'));
            return SOLVER(p);
        })""".replace("SOLVER", solve_board)
        check("all twelve practice puzzles solve with their real directions", solve_all)
        check("all twelve practice completions are saved", "CROSSTALK_PUZZLES.puzzles.every(p=>" + saved_state + ".boards[p.id].bestStars>0)")
        navigate(game_url, game_ready)
        check("practice mode and completed board survive reload", "document.querySelector('#cw-practice').getAttribute('aria-pressed')==='true' && document.querySelector('#cw-select').value==='11' && !!document.querySelector('.cw-is-solved')")
        for width in (390, 360, 768):
            client.call("Emulation.setDeviceMetricsOverride", {"width":width,"height":844,"deviceScaleFactor":1,"mobile":True})
            check(f"practice board {width}px no horizontal overflow", "document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        client.call("Emulation.setDeviceMetricsOverride", {"width":1440,"height":1050,"deviceScaleFactor":1,"mobile":False})

        freeze_clock("2026-09-09T16:59:59Z")
        client.js(f"localStorage.removeItem({json.dumps(storage_key)})")
        navigate(game_url, "document.readyState==='complete' && document.querySelector('#cw-week-select')?.options.length===52")
        check("before the season starts every weekly shift is sealed", "Array.from(document.querySelector('#cw-week-select').options).every(o=>o.disabled) && document.querySelectorAll('#cw-wires .cw-wire').length===0 && document.querySelector('#cw-check').disabled")
        client.js("document.querySelector('#cw-practice').click()")
        check("practice is available before the first weekly release", "document.querySelectorAll('#cw-wires .cw-wire').length>0 && !document.querySelector('#cw-check').disabled")
        client.js("document.querySelector('#cw-weekly').click();window.__cwTestNow=Date.parse('2026-09-09T17:00:00Z')")
        await_check("first release creates the board on an already open page", "document.querySelector('#cw-week-select').value==='shift-01' && document.querySelectorAll('#cw-wires .cw-wire').length>0 && !document.querySelector('#cw-check').disabled")

        # Explicit UTC expectations catch a fixed-offset schedule across DST.
        release_cases = (
            ("2026-09-16T16:59:59Z", "shift-02", False),
            ("2026-09-16T17:00:00Z", "shift-02", True),
            ("2026-10-28T17:59:59Z", "shift-08", False),
            ("2026-10-28T18:00:00Z", "shift-08", True),
            ("2027-03-31T16:59:59Z", "shift-30", False),
            ("2027-03-31T17:00:00Z", "shift-30", True),
        )
        for instant, shift_id, unlocked in release_cases:
            freeze_clock(instant)
            navigate(game_url, game_ready)
            check(f"{shift_id} {'unlocked' if unlocked else 'locked'} at {instant}", f"document.querySelector('#cw-week-select option[value=\"{shift_id}\"]').disabled==={str(not unlocked).lower()}")
        freeze_clock("2027-09-01T17:00:00Z")
        navigate(game_url, game_ready)
        check("the completed season keeps all 52 shifts open", "Array.from(document.querySelector('#cw-week-select').options).every(o=>!o.disabled) && document.querySelector('#cw-countdown').textContent==='Season complete' && !document.querySelector('#cw-release-time').hasAttribute('datetime') && !/NaN|undefined/.test(document.querySelector('#cw-release-time').textContent)")
        client.call("Emulation.setTimezoneOverride", {"timezoneId":"America/Los_Angeles"})
        freeze_clock("2026-10-28T18:00:00Z")
        navigate(game_url, game_ready)
        check("release availability is independent of a visitor's timezone", "!document.querySelector('#cw-week-select option[value=\"shift-08\"]').disabled && document.querySelector('#cw-week-select option[value=\"shift-09\"]').disabled")
        client.call("Emulation.setTimezoneOverride", {"timezoneId":"Europe/Copenhagen"})
        freeze_clock("2026-09-16T16:59:59Z")
        navigate(game_url, game_ready)
        client.js("window.__cwTestNow=Date.parse('2026-09-16T17:00:00Z')")
        await_check("an open page unlocks the Wednesday release automatically", "!document.querySelector('#cw-week-select option[value=\"shift-02\"]').disabled")

        freeze_clock("2026-09-13T15:00:00Z")
        client.js(f"localStorage.removeItem({json.dumps(storage_key)});localStorage.setItem('crosstalk-crossed-wires-v1',JSON.stringify(['line-01']))")
        navigate(game_url, game_ready)
        check("previous game completions migrate into practice", saved_state + ".boards['line-01'].bestStars>0")
        blocker=client.call("Page.addScriptToEvaluateOnNewDocument", {"source":"Object.defineProperty(window,'localStorage',{get(){throw new Error('Storage unavailable for test')}})"})
        navigate(game_url, game_ready)
        client.js("document.querySelector('#cw-hint').click()")
        check("game works when storage is unavailable", assigned_count + "===1")
        client.call("Page.removeScriptToEvaluateOnNewDocument", {"identifier":blocker["identifier"]})
        client.call("Page.removeScriptToEvaluateOnNewDocument", {"identifier":clock_script})
        navigate(base_url + "#atlas", "location.pathname.endsWith('/week1/index.html') && !!document.querySelector('#network-atlas [data-node]')")
        check("old report bookmarks still work", "location.hash==='#atlas'")
        # The later issues keep their story controls separate from the game.
        navigate(base_url + "week2/index.html")
        check("Week 2 has chapter navigation", "document.querySelector('.journal-rail select').options.length>=4")
        client.js("document.querySelector('[data-ccdf-view=fit]').click()")
        check("Week 2 figure switch works", "document.querySelector('#ccdf-switch-img').getAttribute('src').includes('ccdf-fit.svg')")
        screenshot("week2.png", full=True)
        navigate(base_url + "play/cerebro.html", "document.readyState==='complete' && document.querySelector('#tab-paradox-mode') !== null")
        client.js("document.querySelector('#tab-paradox-mode').click()")
        check("Popularity Trap switches modes", "document.querySelector('#tab-paradox-mode').getAttribute('aria-selected')==='true'")
        client.js("document.querySelector('#tab-duel-mode').click()")
        screenshot("popularity-trap.png", full=True)
        for route in ("week2/index.html", "play/cerebro.html"):
            navigate(base_url + route)
            for width in (390, 360, 768):
                client.call("Emulation.setDeviceMetricsOverride", {"width":width,"height":844,"deviceScaleFactor":1,"mobile":True})
                check(f"{route} {width}px no horizontal overflow", "document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        client.call("Emulation.setDeviceMetricsOverride", {"width":1440,"height":1050,"deviceScaleFactor":1,"mobile":False})
        navigate(base_url + "week3/index.html")
        check("Week 3 keeps story chapters and the static removal figure", "!!document.querySelector('#blackout img[src$=\"week3-removal.svg\"]') && !!document.querySelector('#pathfinder') && document.querySelector('.journal-rail select').options.length>=4")
        check("Week 3 story is separate from game controls and data", "!document.querySelector('#w3-disconnect, #w3-route-form, #w3-removal-count, script[src$=\"week3.js\"]') && !window.CROSSTALK_WEEK3")
        check("Week 3 visibly links to its game", "Array.from(document.querySelectorAll('main a[href]')).some(a=>new URL(a.href).pathname.endsWith('/play/switchboard.html') && a.getClientRects().length>0)")
        check("Week 3 visibly links to the B-side", "Array.from(document.querySelectorAll('main a[href]')).some(a=>new URL(a.href).pathname.endsWith('/grunge/index.html') && a.getClientRects().length>0)")
        check("Week 3 story desktop has no horizontal overflow", "document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        screenshot("week3.png", full=True)
        for width in (390,360,768):
            client.call("Emulation.setDeviceMetricsOverride", {"width":width,"height":844,"deviceScaleFactor":1,"mobile":True})
            check(f"Week 3 story {width}px no horizontal overflow", "document.documentElement.scrollWidth <= document.documentElement.clientWidth")
            if width == 390:
                screenshot("week3-mobile.png", full=True)
        navigate(base_url + "week4/index.html")
        check("Week 4 article and Louvain link", "document.title.includes('The schools hiding in the links') && !!document.querySelector('a[href$=\"play/louvain.html\"]')")
        check("Week 4 article desktop has no horizontal overflow", "document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        navigate(base_url + "play/louvain.html", "document.readyState==='complete' && !!document.querySelector('#w4-canvas circle')")
        check("Louvain explorable has controls", "!!document.querySelector('#w4-step') && !!document.querySelector('#w4-aggregate') && !!document.querySelector('#w4-canvas circle')")
        client.call("Emulation.setDeviceMetricsOverride", {"width":1440,"height":1050,"deviceScaleFactor":1,"mobile":False})
        switchboard_ready = "document.readyState==='complete' && !!document.querySelector('#w3-disconnect') && !document.querySelector('#w3-disconnect').disabled"
        navigate(base_url + "play/switchboard.html", switchboard_ready)
        check("Switchboard visibly links back to Week 3", "Array.from(document.querySelectorAll('main a[href]')).some(a=>new URL(a.href).pathname.endsWith('/week3/index.html') && a.getClientRects().length>0)")
        check("Switchboard has every character", "document.querySelector('#w3-remove-character').options.length===303 && document.querySelector('#w3-directory').options.length===303")
        client.js("document.querySelector('#w3-disconnect').click()")
        check("Black Widow detaches three survivors", "document.querySelector('.w3-giant-number').textContent.startsWith('273 ') && document.querySelectorAll('.w3-detached-list li').length===3")
        client.js("document.querySelector('#w3-remove-character').value='Spider-Man'; document.querySelector('#w3-disconnect').click()")
        check("Spider-Man removal matches analysis", "document.querySelector('.w3-giant-number').textContent.startsWith('271 ') && document.querySelectorAll('.w3-detached-list li').length===5")
        client.js("document.querySelector('#w3-reconnect').click()")
        check("restoring the network resets damage", "document.querySelector('.w3-giant-number').textContent.startsWith('277 ') && !document.querySelector('.w3-detached-list')")
        check("directed longest route has four real hops", "document.querySelectorAll('.w3-route-chain li').length===5 && document.querySelector('#w3-route-result').textContent.includes('4 hops')")
        client.js("document.querySelector('#w3-isolate-preset').click()")
        check("route finder explains isolates", "document.querySelector('#w3-route-result').textContent.includes('isolate') && !document.querySelector('.w3-route-chain')")
        client.js("document.querySelector('#w3-route-character').value='not a character'; document.querySelector('#w3-route-form').requestSubmit()")
        check("route finder handles invalid names", "document.querySelector('#w3-route-character').getAttribute('aria-invalid')==='true'")
        client.js("document.querySelector('[data-route-id=\"Spider-Man\"]').click()")
        check("calling Spider-Man from himself is zero hops", "document.querySelectorAll('.w3-route-chain li').length===1 && !document.querySelector('#w3-route-character').hasAttribute('aria-invalid')")
        client.js("document.querySelector('#w3-route-mode').value='undirected'; document.querySelector('#w3-route-mode').dispatchEvent(new Event('change')); document.querySelector('[data-route-id]').click()")
        check("undirected longest route has three hops", "document.querySelectorAll('.w3-route-chain li').length===4")
        client.js("document.querySelector('#w3-removal-count').value=303; document.querySelector('#w3-removal-count').dispatchEvent(new Event('input'))")
        check("all removals leave zero pages in every curve", "Array.from(document.querySelectorAll('.w3-order-result strong')).every(e=>Number(e.textContent)===0)")
        client.js("document.querySelector('#w3-removal-count').value=30; document.querySelector('#w3-removal-count').dispatchEvent(new Event('input'))")
        check("Switchboard desktop has no horizontal overflow", "document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        screenshot("switchboard.png", full=True)
        for width in (390,360,768):
            client.call("Emulation.setDeviceMetricsOverride", {"width":width,"height":844,"deviceScaleFactor":1,"mobile":True})
            check(f"Switchboard {width}px no horizontal overflow", "document.documentElement.scrollWidth <= document.documentElement.clientWidth")
            if width == 390:
                screenshot("switchboard-mobile.png", full=True)
        client.call("Emulation.setDeviceMetricsOverride", {"width":1440,"height":1050,"deviceScaleFactor":1,"mobile":False})
        check_grunge()
        # All pages also work when opened from disk.
        navigate((ROOT / "index.html").as_uri())
        check("offline home works", "location.protocol === 'file:' && !!document.querySelector('.home-page')")
        navigate((ROOT / "week1/index.html").as_uri(), "document.readyState === 'complete' && !!document.querySelector('#network-atlas [data-node]')")
        check("offline report works", "location.protocol === 'file:' && document.querySelectorAll('#network-atlas [data-node]').length === 303")
        navigate((ROOT / "play/index.html").as_uri(), game_ready)
        check("offline game works", "location.protocol==='file:' && document.querySelector('#cw-select').options.length===12")
        navigate((ROOT / "play/switchboard.html").as_uri(), switchboard_ready)
        client.js("document.querySelector('#w3-remove-character').value='Spider-Man';document.querySelector('#w3-disconnect').click()")
        check("offline Switchboard works", "location.protocol==='file:' && document.querySelector('#w3-remove-character').options.length===303 && document.querySelector('.w3-giant-number').textContent.startsWith('271 ') && document.querySelectorAll('.w3-route-chain li').length===5")
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
