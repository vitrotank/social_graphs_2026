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
    parser.add_argument("--grunge-only", action="store_true", help="Run just the B-side and provider-control checks")
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
                print("Failure details:", client.js("JSON.stringify({width:innerWidth,scroll:document.documentElement.scrollWidth,offenders:Array.from(document.querySelectorAll('body *')).filter(e=>e.getBoundingClientRect().right>document.documentElement.clientWidth+1).slice(0,12).map(e=>({tag:e.tagName,cls:String(e.className),text:e.textContent.slice(0,90)}))})"), flush=True)
                screenshot("failure.png", full=True)
                raise AssertionError(f"Browser check failed: {name}")
        def check_grunge():
            navigate(base_url + "grunge/index.html", "document.readyState==='complete' && document.querySelector('#grunge-from')?.options.length===15")
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

        check("homepage is Crosstalk", "document.title.includes('CROSSTALK') && !!document.querySelector('.home-page')")
        check("eight week slots, three published issues", "document.querySelectorAll('.week-entry').length === 8 && document.querySelectorAll('a.week-entry').length === 3")
        check("home stays lightweight", "!window.CROSSTALK_DATA && !document.querySelector('#network-atlas')")
        check("group names rendered", "document.body.textContent.includes('Christos Diamantis') && document.body.textContent.includes('s253102') && document.body.textContent.includes('Dávid Weiner') && document.body.textContent.includes('s253347')")
        check("clear direct week navigation", "document.querySelectorAll('.issue-nav a').length===4 && !!document.querySelector('#games')")
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
        check("Week 2 has chapter navigation", "document.querySelectorAll('.issue-directory a').length >= 6")
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
        navigate(base_url + "week3/index.html", "document.readyState==='complete' && !document.querySelector('#w3-disconnect')?.disabled")
        check("Week 3 has every character", "document.querySelector('#w3-remove-character').options.length===303 && document.querySelector('#w3-directory').options.length===303")
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
        screenshot("week3.png", full=True)
        for width in (390,360,768):
            client.call("Emulation.setDeviceMetricsOverride", {"width":width,"height":844,"deviceScaleFactor":1,"mobile":True})
            check(f"Week 3 {width}px no horizontal overflow", "document.documentElement.scrollWidth <= document.documentElement.clientWidth")
            if width == 390:
                screenshot("week3-mobile.png", full=True)
        client.call("Emulation.setDeviceMetricsOverride", {"width":1440,"height":1050,"deviceScaleFactor":1,"mobile":False})
        check_grunge()
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
