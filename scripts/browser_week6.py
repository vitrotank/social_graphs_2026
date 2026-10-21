#!/usr/bin/env python3
"""Check the built Week 6 story and retained Vector Drift in installed Chrome.

Run after ``python scripts/build.py --output _site``. Uses only the standard
library and writes screenshots and its check report to ignored ``.preview/``.
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
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', help='Path to an installed Chrome/Chromium executable')
    args = parser.parse_args()
    browser = args.browser or shutil.which('chromium') or shutil.which('google-chrome')
    if not browser:
        browser = next((str(path) for path in (
            Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe'),
            Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'),
        ) if path.is_file()), None)
    if not browser:
        raise SystemExit('Install Chrome/Chromium or pass --browser. No browser was downloaded.')
    public = ROOT / '_site'
    if not (public / 'week6/index.html').is_file():
        raise SystemExit('Run python scripts/build.py --output _site first.')

    preview = ROOT / '.preview'
    preview.mkdir(exist_ok=True)
    checks = {}
    client = process = server = None
    log = None
    report = preview / 'week6-browser-checks.json'
    try:
        QuietHandler.errors = []
        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(public)))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{server.server_port}/'
        opener = build_opener(ProxyHandler({}))
        with opener.open(base + 'week6/index.html', timeout=5) as response:
            if response.status != 200:
                raise RuntimeError('The local Week 6 preview did not return HTTP 200.')
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            debug_port = probe.getsockname()[1]
        log = (preview / 'week6-browser.log').open('w', encoding='utf-8')
        process = subprocess.Popen([
            browser, '--headless=new', '--disable-gpu', '--disable-background-networking',
            '--no-first-run', '--no-default-browser-check', '--disable-component-update',
            '--disable-sync', f'--remote-debugging-port={debug_port}',
            f'--user-data-dir={preview / "week6-browser-profile"}', 'about:blank',
        ], stdout=log, stderr=log, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError('Browser exited during startup; see .preview/week6-browser.log.')
            try:
                with opener.open(f'http://127.0.0.1:{debug_port}/json/list', timeout=1) as response:
                    targets = json.load(response)
                client = CDP(next(target['webSocketDebuggerUrl'] for target in targets if target['type'] == 'page'))
                break
            except (OSError, StopIteration):
                time.sleep(.1)
        if client is None:
            raise RuntimeError('Browser did not start; see .preview/week6-browser.log.')
        client.call('Runtime.enable')
        client.call('Page.enable')
        client.call('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-reduced-motion', 'value': 'reduce'}]})

        def navigate(url, ready="document.readyState === 'complete'"):
            client.call('Page.navigate', {'url': url})
            for _ in range(100):
                try:
                    if client.js(ready):
                        return
                except RuntimeError as error:
                    if not any(message in str(error) for message in (
                        'Inspected target navigated or closed', 'Execution context was destroyed',
                        'Cannot find context with specified id',
                    )):
                        raise
                time.sleep(.1)
            raise AssertionError(f'Page did not become ready: {url}')

        def screenshot(name):
            result = client.call('Page.captureScreenshot', {'format': 'png'})
            (preview / name).write_bytes(base64.b64decode(result['data']))

        def check(name, expression):
            checks[name] = client.js(expression)
            if not checks[name]:
                screenshot('week6-browser-failure.png')
                raise AssertionError(f'Browser check failed: {name}')

        def viewport(width):
            client.call('Emulation.setDeviceMetricsOverride', {
                'width': width, 'height': 1000 if width > 500 else 844,
                'deviceScaleFactor': 1, 'mobile': width < 500,
            })

        story_ready = "document.readyState==='complete' && !!window.WEEK6_DATA && document.querySelector('#w6-character')?.options.length===WEEK6_DATA.rows.length && !document.querySelector('#lookalikes').hidden"
        viewport(1440)
        navigate(base + 'week6/index.html', story_ready)
        check('All 303 articles are available', 'WEEK6_DATA.rows.length===303 && document.querySelector("#w6-character").options.length===303')
        check('Figure and inspected cases are rendered', "(()=>{const f=document.querySelector('.w6-audit-figure img');return f?.complete&&f.naturalWidth>0&&WEEK6_DATA.cases.length>0&&WEEK6_DATA.cases.every(c=>{const e=document.getElementById('w6-case-'+c.id);return e&&e.textContent.includes(c.title)&&c.sources.every(s=>e.textContent.includes(s.text)&&[...e.querySelectorAll('a[href]')].some(a=>a.href===s.url))})})()")
        check('Each article selection displays its measured neighbors and cosine', "WEEK6_DATA.rows.every(row=>{const s=document.querySelector('#w6-character');s.value=row.node;s.dispatchEvent(new Event('change'));return s.selectedOptions[0].textContent.includes(row.name)&&document.querySelector('#w6-comparison').textContent.startsWith(row.name+':')&&['before','after'].every(condition=>{const c=document.querySelector('#w6-neighbors [data-condition='+condition+']'),r=row[condition];return c.querySelector('h3 a').textContent===r.name&&c.querySelector('h3 a').href===r.url&&c.querySelector('.w6-score').textContent.includes('Cosine '+r.similarity.toFixed(3))})})")
        client.js("const s=document.querySelector('#w6-character');s.value='Storm_(Marvel_Comics)';s.dispatchEvent(new Event('change'))")
        check('Storm contribution is attributed and measured', "(()=>{const r=WEEK6_DATA.rows.find(r=>r.node==='Storm_(Marvel_Comics)'),item=document.querySelector('#w6-neighbors [data-condition=before] .w6-terms li');return r.before.terms[0].term==='storm'&&(100*r.before.terms[0].share).toFixed(1)==='86.9'&&item.querySelector('.w6-term').textContent==='storm'&&item.querySelector('.w6-term-share').textContent==='86.9%'})()")

        for width in (1440, 390, 320):
            viewport(width)
            check(f'Story at {width}px has no horizontal overflow', 'document.documentElement.scrollWidth<=innerWidth+1')
            check(f'Story at {width}px has no broken images', '[...document.images].every(i=>i.complete&&i.naturalWidth>0)')
            client.js("document.querySelector('#name-audit').scrollIntoView({block:'start',behavior:'instant'})")
            screenshot(f'week6-audit-{width}.png')

        viewport(1440)
        navigate((public / 'week6/index.html').as_uri(), story_ready)
        check('Offline file viewing loads the data bundle and explorer', "location.protocol==='file:'&&document.querySelector('#w6-character').options.length===303&&document.querySelectorAll('#w6-neighbors article').length===2")
        client.call('Emulation.setScriptExecutionDisabled', {'value': True})
        navigate(base + 'week6/index.html')
        check('Without JavaScript the figure and inspected cases remain', "(()=>{const f=document.querySelector('.w6-audit-figure img');return f?.complete&&f.naturalWidth>0&&document.querySelectorAll('.w6-cases article').length>0&&document.querySelector('.w6-cases').textContent.includes('Storm')&&document.querySelector('#lookalikes').hidden})()")
        client.call('Emulation.setScriptExecutionDisabled', {'value': False})

        navigate(base + 'play/vector-voyage.html', "document.readyState==='complete'&&document.querySelectorAll('#vv-mission-tabs button').length===5&&document.querySelectorAll('.vv-chip').length===18")
        check('Preserved game loads all missions and palette terms', 'CROSSTALK_VECTOR_GAME.characters.length===28&&CROSSTALK_VECTOR_GAME.missions.length===5&&CROSSTALK_VECTOR_GAME.palette.reduce((n,c)=>n+c.words.length,0)===18')
        client.js("document.querySelector('.vv-chip').click()")
        check('Game applies a word step', "document.querySelector('#vv-move-count').textContent==='1'")
        client.js("document.querySelector('#vv-undo-btn').click()")
        check('Game undo restores the start', "document.querySelector('#vv-move-count').textContent==='0'")
        client.js("document.querySelector('#vv-view-2d').click()")
        check('Game keeps its 2D view control', "document.querySelector('#vv-view-2d').getAttribute('aria-pressed')==='true'")
        errors = [event for event in client.events if event.get('method') == 'Runtime.exceptionThrown']
        checks['No uncaught browser exceptions'] = not errors
        checks['No failed local resource requests'] = not QuietHandler.errors
        if errors or QuietHandler.errors:
            raise AssertionError('Browser exceptions or failed resources; see week6-browser-checks.json.')
        print(f'{len(checks)} Week 6 browser checks passed; screenshots in .preview/.')
    finally:
        errors = [event for event in client.events if event.get('method') == 'Runtime.exceptionThrown'] if client else []
        report.write_text(json.dumps({'checks': checks, 'errors': errors, 'http_errors': QuietHandler.errors}, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
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


if __name__ == '__main__':
    main()
