#!/usr/bin/env python3
"""Exercise the built Week 7 story with an installed Chrome or Chromium.

Run after ``python scripts/build.py --output _site``. Uses only the standard
library. Screenshots and the check report go to ignored ``.preview/``.
"""
from __future__ import annotations

import argparse
import base64
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time
from urllib.request import build_opener, ProxyHandler

from browser_smoke import CDP, QuietHandler

ROOT = Path(__file__).resolve().parents[1]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", help="Path to an installed Chrome/Chromium executable")
    args = parser.parse_args()
    browser = args.browser or shutil.which("chromium") or shutil.which("google-chrome")
    if not browser:
        browser = next((str(path) for path in (
            Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        ) if path.is_file()), None)
    if not browser:
        raise SystemExit("Install Chrome/Chromium or pass --browser. No browser was downloaded.")
    public = ROOT / "_site"
    if not (public / "week7/index.html").is_file():
        raise SystemExit("Run python scripts/build.py --output _site first.")

    preview = ROOT / ".preview"
    preview.mkdir(exist_ok=True)
    checks = {}
    client = process = server = None
    log = None
    report = preview / "week7-browser-checks.json"
    try:
        QuietHandler.errors = []
        server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(public)))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_port}/"
        opener = build_opener(ProxyHandler({}))
        with opener.open(base + "week7/index.html", timeout=5) as response:
            if response.status != 200:
                raise RuntimeError("The local Week 7 preview did not return HTTP 200.")
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            debug_port = probe.getsockname()[1]
        log = (preview / "week7-browser.log").open("w", encoding="utf-8")
        process = subprocess.Popen([
            browser, "--headless=new", "--disable-gpu", "--disable-background-networking",
            "--no-first-run", "--no-default-browser-check", "--disable-component-update",
            "--disable-sync", f"--remote-debugging-port={debug_port}",
            f"--user-data-dir={preview / 'week7-browser-profile'}", "about:blank",
        ], stdout=log, stderr=log, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError("Browser exited during startup; see .preview/week7-browser.log.")
            try:
                with opener.open(f"http://127.0.0.1:{debug_port}/json/list", timeout=1) as response:
                    targets = json.load(response)
                client = CDP(next(target["webSocketDebuggerUrl"] for target in targets if target["type"] == "page"))
                break
            except (OSError, StopIteration):
                time.sleep(.1)
        if client is None:
            raise RuntimeError("Browser did not start; see .preview/week7-browser.log.")
        client.call("Runtime.enable")
        client.call("Page.enable")
        client.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]})

        def navigate(url, ready="document.readyState === 'complete'"):
            client.call("Page.navigate", {"url": url})
            for _ in range(100):
                try:
                    if client.js(ready):
                        return
                except RuntimeError as error:
                    if not any(message in str(error) for message in (
                        "Inspected target navigated or closed", "Execution context was destroyed",
                        "Cannot find context with specified id",
                    )):
                        raise
                time.sleep(.1)
            raise AssertionError(f"Page did not become ready: {url}")

        def screenshot(name):
            result = client.call("Page.captureScreenshot", {"format": "png"})
            (preview / name).write_bytes(base64.b64decode(result["data"]))

        def check(name, expression):
            checks[name] = client.js(expression)
            if not checks[name]:
                screenshot("week7-browser-failure.png")
                raise AssertionError(f"Browser check failed: {name}")

        def viewport(width):
            client.call("Emulation.setDeviceMetricsOverride", {
                "width": width, "height": 1000 if width > 500 else 844,
                "deviceScaleFactor": 1, "mobile": width < 500,
            })
            expected = 'week7-distance-mobile.svg' if width <= 620 else 'week7-distance.svg'
            for _ in range(50):
                if client.js("(()=>{const i=document.querySelector('.w7-main-figure img');return !i||(i.complete&&i.naturalWidth>0&&i.currentSrc.endsWith(" + json.dumps(expected) + "))})()"):
                    break
                time.sleep(.05)

        viewport(1440)
        navigate(base, "document.readyState==='complete'&&!!document.querySelector('#latest-title')")
        check("Homepage leads with Week 7", "document.querySelector('.latest-spread a[href]').getAttribute('href')==='week7/index.html'")

        story_ready = "document.readyState==='complete'&&!!window.WEEK7_DATA&&!document.querySelector('#w7-explorer').hidden&&document.querySelectorAll('#w7-results button[data-source]').length>0"
        navigate(base + "week7/index.html", story_ready)
        check("All 303 nearest-neighbor choices are available", "WEEK7_DATA.nearest.length===303&&document.querySelectorAll('#w7-results button[data-source]').length===303")
        check("Static figure and inspected source evidence load", "(()=>{const f=document.querySelector('.w7-main-figure img');return f?.complete&&f.naturalWidth>0&&WEEK7_DATA.cases.length>0&&WEEK7_DATA.cases.every(c=>[...document.querySelectorAll('.w7-case')].some(e=>e.textContent.includes(c.title)&&c.sources.every(s=>e.textContent.includes(s.text)&&[...e.querySelectorAll('a[href]')].some(a=>a.href===s.url))))})()")

        for category in ("1", "2", "3", "4+", "disconnected"):
            client.js(f"(()=>{{const s=document.querySelector('#w7-distance');s.value={json.dumps(category)};s.dispatchEvent(new Event('change'))}})()")
            check(f"Distance filter {category} uses measured choices", f"(()=>{{const selected={json.dumps(category)},expected=WEEK7_DATA.nearest.filter(r=>selected==='disconnected'?r.distance===null:selected==='4+'?r.distance>=4:r.distance===Number(selected));return document.querySelectorAll('#w7-results button[data-source]').length===expected.length&&[...document.querySelectorAll('#w7-results button[data-source]')].every(b=>expected.some(r=>r.source===b.dataset.source))&&document.querySelector('#w7-count').textContent.includes(String(expected.length))}})()")
        client.js("(()=>{const s=document.querySelector('#w7-distance');s.value='all';s.dispatchEvent(new Event('change'));const q=document.querySelector('#w7-search');q.value=WEEK7_DATA.nearest[0].source_name;q.dispatchEvent(new Event('input'))})()")
        check("Search finds either member of a displayed pair", "(()=>{const q=document.querySelector('#w7-search').value.toLocaleLowerCase(),expected=WEEK7_DATA.nearest.filter(r=>(r.source_name+' '+r.target_name).toLocaleLowerCase().includes(q));return expected.length>0&&document.querySelectorAll('#w7-results button[data-source]').length===expected.length})()")
        client.js("(()=>{const q=document.querySelector('#w7-search');q.value='zzznomatchingmarvelarticlezzz';q.dispatchEvent(new Event('input'))})()")
        check("An empty search result has a readable count", "document.querySelectorAll('#w7-results button[data-source]').length===0&&document.querySelector('#w7-count').textContent.includes('0')")
        client.js("(()=>{const q=document.querySelector('#w7-search');q.value='';q.dispatchEvent(new Event('input'))})()")
        check("Every choice opens its own score and frozen excerpts", "WEEK7_DATA.nearest.every(row=>{const b=[...document.querySelectorAll('#w7-results button[data-source]')].find(b=>b.dataset.source===row.source);b.click();const e=document.querySelector('#w7-detail'),t=e.textContent;return e.dataset.pairSource===row.source&&e.dataset.pairTarget===row.target&&t.includes(row.source_name)&&t.includes(row.target_name)&&t.includes(row.similarity.toFixed(3))&&row.sources.every(s=>t.includes(s.text)&&[...e.querySelectorAll('a[href]')].some(a=>a.href===s.url))&&row.terms.every(x=>t.includes(x.term))})")
        check("Every route and term share matches its measured data", "WEEK7_DATA.nearest.every(row=>{[...document.querySelectorAll('#w7-results button[data-source]')].find(b=>b.dataset.source===row.source).click();const e=document.querySelector('#w7-detail'),links=[...e.querySelectorAll('.w7-path a')],terms=[...e.querySelectorAll('.w7-terms li')];return e.querySelector('.w7-detail-distance').textContent===(row.distance===null?'No path':row.distance+' '+(row.distance===1?'step':'steps'))&&links.length===row.path.length&&links.every((a,i)=>a.href===WEEK7_DATA.characters.find(c=>c.node===row.path[i]).url)&&terms.length===row.terms.length&&terms.every((li,i)=>li.textContent.includes(row.terms[i].term)&&li.querySelector('span').textContent===(row.terms[i].share*100).toFixed(1)+'%')})")
        check("Disconnected choices explicitly explain the missing route", "(()=>{const r=WEEK7_DATA.nearest.find(r=>r.distance===null),b=[...document.querySelectorAll('#w7-results button[data-source]')].find(b=>b.dataset.source===r.source);b.click();return /disconnected|no (?:hyperlink )?(?:path|route)/i.test(document.querySelector('#w7-detail').textContent)})()")
        client.js("document.querySelector('#w7-results button[data-source]').focus()")
        for kind in ("keyDown", "keyUp"):
            event = {"type": kind, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13}
            if kind == "keyDown":
                event.update(text="\r", unmodifiedText="\r")
            client.call("Input.dispatchKeyEvent", event)
        check("A focused choice opens through the keyboard", "(()=>{const b=document.querySelector('#w7-results button[data-source]');return document.activeElement===b&&b.getAttribute('aria-pressed')==='true'&&document.querySelector('#w7-detail').dataset.pairSource===b.dataset.source})()")

        for width in (1440, 390, 320):
            viewport(width)
            check(f"Story at {width}px has no horizontal overflow", "document.documentElement.scrollWidth<=innerWidth+1")
            check(f"Story at {width}px has no broken images", "[...document.images].every(i=>i.complete&&i.naturalWidth>0)")
            expected = 'week7-distance-mobile.svg' if width <= 620 else 'week7-distance.svg'
            check(f"Figure at {width}px chooses a readable layout", "document.querySelector('.w7-main-figure img').currentSrc.endsWith(" + json.dumps(expected) + ")")
            client.js("document.querySelector('.w7-main-figure').scrollIntoView({block:'start',behavior:'instant'})")
            screenshot(f"week7-figure-{width}.png")
            client.js("document.querySelector('#w7-explorer').scrollIntoView({block:'start',behavior:'instant'})")
            screenshot(f"week7-explorer-{width}.png")

        viewport(1440)
        navigate((public / "week7/index.html").as_uri(), story_ready)
        check("Offline file viewing loads all choices", "location.protocol==='file:'&&WEEK7_DATA.nearest.length===303&&document.querySelectorAll('#w7-results button[data-source]').length===303")
        client.call("Emulation.setScriptExecutionDisabled", {"value": True})
        navigate(base + "week7/index.html")
        check("Without JavaScript the figure and frozen evidence remain readable", "(()=>{const f=document.querySelector('.w7-main-figure img');return f?.complete&&f.naturalWidth>0&&document.querySelectorAll('.w7-case').length>=2&&document.querySelector('#evidence').textContent.includes('Backhand')&&document.querySelector('#w7-explorer').hidden})()")
        client.call("Emulation.setScriptExecutionDisabled", {"value": False})

        errors = [event for event in client.events if event.get("method") == "Runtime.exceptionThrown"]
        checks["No uncaught browser exceptions"] = not errors
        checks["No failed local resource requests"] = not QuietHandler.errors
        if errors or QuietHandler.errors:
            raise AssertionError("Browser exceptions or failed resources; see week7-browser-checks.json.")
        print(f"{len(checks)} Week 7 browser checks passed; screenshots in .preview/.")
    finally:
        errors = [event for event in client.events if event.get("method") == "Runtime.exceptionThrown"] if client else []
        report.write_text(json.dumps({"checks": checks, "errors": errors, "http_errors": QuietHandler.errors}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if client:
            client.sock.close()
        if process:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if log:
            log.close()
        if server:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
