#!/usr/bin/env python3
"""Render and exercise Marginalia in installed Chrome using the stdlib CDP client."""
from __future__ import annotations
import argparse, base64, json, os, socket, subprocess, time
from pathlib import Path
from urllib.request import build_opener, ProxyHandler
from browser_smoke import CDP

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:8000/')
    parser.add_argument('--quick',action='store_true')
    parser.add_argument('--references',action='store_true',help='Inspect both supplied reference sites and an internal story route')
    args=parser.parse_args()
    output=ROOT/'.preview'; output.mkdir(exist_ok=True)
    browser=next((p for p in [Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe'),Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')] if p.is_file()),None)
    if not browser: raise SystemExit('Chrome or Edge must be installed.')
    with socket.socket() as s:
        s.bind(('127.0.0.1',0)); port=s.getsockname()[1]
    log=(output/'inspection-browser.log').open('w',encoding='utf-8')
    process=subprocess.Popen([str(browser),'--headless=new','--disable-gpu','--no-first-run','--disable-background-networking',f'--remote-debugging-port={port}',f'--user-data-dir={output / "inspection-profile"}','about:blank'],stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    client=None
    checks={}
    try:
        opener=build_opener(ProxyHandler({}))
        for _ in range(120):
            try:
                with opener.open(f'http://127.0.0.1:{port}/json/list',timeout=1) as response: targets=json.load(response)
                client=CDP(next(t['webSocketDebuggerUrl'] for t in targets if t['type']=='page')); break
            except (OSError,StopIteration): time.sleep(.1)
        if client is None: raise RuntimeError('Browser did not start. See inspection-browser.log')
        client.call('Runtime.enable');client.call('Page.enable')
        client.call('Emulation.setEmulatedMedia',{'features':[{'name':'prefers-reduced-motion','value':'reduce'}]})
        def navigate(route):
            client.call('Page.navigate',{'url':route if route.startswith(('https://','http://','file:')) else args.url+route})
            for _ in range(100):
                try:
                    if client.js("document.readyState==='complete'"): break
                except RuntimeError: pass
                time.sleep(.1)
            time.sleep(.25)
        def shot(name,full=False):
            params={'format':'png'}
            if full: params.update({'captureBeyondViewport':True,'clip':{'x':0,'y':0,'width':client.js('innerWidth'),'height':min(client.js('document.documentElement.scrollHeight'),16000),'scale':1}})
            (output/name).write_bytes(base64.b64decode(client.call('Page.captureScreenshot',params)['data']))
        def check(name,expression):
            value=client.js(expression); checks[name]=value
            if not value:
                shot('inspection-failure.png',True)
                raise AssertionError(f'{name}: {value}')
        if args.references:
            report={}
            for key,url in [('movega','https://movega.github.io/02805-Social-graphs-and-interactions/index.html'),('oddvar','https://oddvar112.github.io/Social-Graphs-and-Interactions/index.html')]:
                report[key]={}
                for width,height,label in [(1440,1000,'desktop'),(390,844,'mobile')]:
                    client.call('Emulation.setDeviceMetricsOverride',{'width':width,'height':height,'deviceScaleFactor':1,'mobile':width<500})
                    navigate(url);time.sleep(2)
                    shot(f'reference-{key}-{label}.png',True);shot(f'reference-{key}-{label}-top.png')
                    report[key][label]=client.js("({title:document.title,url:location.href,text:document.body.innerText.slice(0,7500),links:[...document.querySelectorAll('a[href]')].map(a=>({text:a.textContent.trim(),href:a.href})).filter(a=>a.text),buttons:[...document.querySelectorAll('button')].map(b=>({text:b.textContent.trim(),aria:b.getAttribute('aria-label')}))})")
                client.call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1000,'deviceScaleFactor':1,'mobile':False})
                link=client.js("[...document.querySelectorAll('a[href]')].find(a=>/Week 5|Posts/i.test(a.textContent)&&a.href.startsWith(location.origin)&&!a.href.includes('#'))?.href")
                if link:
                    navigate(link);time.sleep(1);shot(f'reference-{key}-story.png',True)
                    report[key]['story']=client.js("({title:document.title,url:location.href,text:document.body.innerText.slice(0,2500),buttons:[...document.querySelectorAll('button')].map(b=>b.textContent.trim())})")
            (output/'reference-review.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
            print(json.dumps({k:{l:{'title':d['title'],'url':d['url'],'buttons':d['buttons']} for l,d in v.items()} for k,v in report.items()},ensure_ascii=True))
            return
        routes=['index.html','week1/index.html','week2/index.html','week3/index.html','week4/index.html','explore/index.html']
        if (ROOT/'week5/index.html').exists(): routes.insert(5,'week5/index.html')
        if not args.quick: routes+=['play/index.html','play/cerebro.html','play/switchboard.html','play/louvain.html','grunge/index.html']
        for width,height,label in [(1440,1000,'desktop'),(390,844,'mobile')]:
            client.call('Emulation.setDeviceMetricsOverride',{'width':width,'height':height,'deviceScaleFactor':1,'mobile':width<500})
            for route in routes:
                navigate(route)
                name=route.split('/')[0].replace('.html','home')
                shot(f'{name}-{label}.png',True)
                shot(f'{name}-{label}-top.png')
                check(f'{route} {width}px no overflow','document.documentElement.scrollWidth<=innerWidth+1')
                check(f'{route} {width}px header navigation',"document.querySelectorAll('.issue-nav a').length>=4")
                check(f'{route} {width}px no broken images',"[...document.images].every(i=>i.complete&&i.naturalWidth>0)")
        navigate('index.html')
        expected=[w['number'] for w in json.loads((ROOT/'site.json').read_text(encoding='utf-8'))['weeks'] if w['status']=='published']
        check('Homepage exposes every published week',str(expected)+".every(n=>document.querySelector('main a[href=\"week'+n+'/index.html\"]'))")
        navigate('explore/index.html')
        client.js("document.querySelector('[data-cover-world=marvel]').click()")
        check('Relocated cabinet resolves atlas links',"document.querySelector('#cover-open').href.endsWith('/week1/index.html#atlas') && document.querySelector('#cover-total-nodes').textContent==='303'")
        if (ROOT/'week5/index.html').exists():
            navigate('week5/index.html')
            check('Week 5 data available',"!!window.WEEK5_DATA && document.querySelector('#w5-plot').dataset.ready==='true'")
            check('Every one of the 53 thresholds uses computed counts',"WEEK5_DATA.thresholds.every(r=>{let s=document.querySelector('#w5-threshold');s.value=r.length;s.dispatchEvent(new Event('input'));return document.querySelector('#w5-pair-count').textContent===r.pairs.toLocaleString('en-US')&&Number(document.querySelector('#w5-article-count').textContent)===r.articles})")
            client.js("document.querySelector('[data-w5-threshold=\"8\"]').click();document.querySelector('#w5-without-lead').click()")
            check('Opening-paragraph sensitivity adds the exact comparison',"!!document.querySelector('.w5-comparison-curve')&&!document.querySelector('#w5-comparison-legend').hidden&&document.querySelector('#w5-comparison-note').textContent.includes('8,649')&&document.querySelector('#w5-pair-count').textContent==='40,570'")
            client.js("document.querySelector('[data-w5-example=editorial]').click()")
            check('Editorial example reveals the measured introductory formula',"document.querySelector('#w5-threshold').value==='8'&&document.querySelector('#w5-pair-select').value===WEEK5_DATA.examples.editorial.id&&document.querySelectorAll('.w5-source').length===2&&document.querySelector('.w5-source mark').textContent===WEEK5_DATA.examples.editorial.sources[0].excerpt")
            client.js("document.querySelector('[data-w5-example=references]').click()")
            check('Bibliography example reveals both attributed source passages',"document.querySelector('#w5-evidence-panel').textContent.includes('103 consecutive')&&[...document.querySelectorAll('.w5-source>a')].every((a,i)=>a.href===WEEK5_DATA.examples.references.sources[i].url)&&[...document.querySelectorAll('.w5-full-passage mark')].every((m,i)=>m.textContent===WEEK5_DATA.examples.references.sources[i].text)")
            client.js("document.querySelectorAll('.w5-full-passage summary').forEach(s=>s.click())")
            check('Evidence expands into complete text and frozen offsets',"[...document.querySelectorAll('.w5-full-passage')].every(d=>d.open)&&document.querySelectorAll('.w5-source-offset').length===2")
            client.js("document.querySelector('[data-w5-threshold=\"60\"]').click();let c=document.querySelector('#w5-category');c.value='Editorial formula';c.dispatchEvent(new Event('change'))")
            check('Empty evidence filters give a usable explanation',"document.querySelector('#w5-pair-select').disabled&&document.querySelector('.w5-empty').textContent.includes('No inspected pair')")
            client.js("document.querySelector('[data-w5-example=story]').click();document.querySelector('#w5-linked').click()")
            check('Link filter uses the real frozen Week 1 graph',"[...document.querySelector('#w5-pair-select').options].every(o=>WEEK5_DATA.pairs.find(p=>p.id===o.value).linked)")
            client.js("document.querySelector('[data-w5-threshold=\"40\"]').click();document.querySelector('#w5-threshold').focus()")
            for kind in ['rawKeyDown','keyUp']:client.call('Input.dispatchKeyEvent',{'type':kind,'key':'ArrowRight','code':'ArrowRight','windowsVirtualKeyCode':39})
            check('Keyboard changes phrase length and computed readout',"document.querySelector('#w5-threshold').value==='41'&&document.querySelector('#w5-pair-count').textContent==='13'")
            check('Reduced-motion preference is respected',"getComputedStyle(document.documentElement).scrollBehavior==='auto'")
            client.call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1000,'deviceScaleFactor':1,'mobile':False})
            client.js("document.querySelector('[data-w5-threshold=\"20\"]').click();document.querySelector('#sieve').scrollIntoView({block:'start',behavior:'instant'})")
            shot('week5-desktop-figure.png')
            client.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
            client.js("document.querySelector('#sieve').scrollIntoView({block:'start',behavior:'instant'})")
            shot('week5-mobile-figure.png')
            check('Phone controls have touch-size targets',"[...document.querySelectorAll('[data-w5-threshold]')].every(b=>b.getBoundingClientRect().height>=40)")
            client.js("document.querySelector('#evidence').scrollIntoView({block:'start',behavior:'instant'})")
            shot('week5-mobile-evidence.png')
            for width in [320,768]:
                client.call('Emulation.setDeviceMetricsOverride',{'width':width,'height':900,'deviceScaleFactor':1,'mobile':width<500})
                check(f'Week 5 {width}px containment',"document.documentElement.scrollWidth<=innerWidth+1")
            client.call('Emulation.setScriptExecutionDisabled',{'value':True})
            navigate('week5/index.html')
            check('No-JavaScript story and complete figure remain available',"!!document.querySelector('#w5-plot polyline')&&document.querySelector('#w5-evidence-panel').textContent.includes('Mayday Parker')&&document.querySelector('#w5-pair-count').textContent==='71'")
            client.call('Emulation.setScriptExecutionDisabled',{'value':False})
            navigate((ROOT/'week5/index.html').as_uri())
            check('Week 5 also works directly from disk',"location.protocol==='file:'&&document.querySelector('#w5-plot').dataset.ready==='true'&&document.querySelector('#w5-pair-select').options.length===71")
        errors=[e for e in client.events if e.get('method')=='Runtime.exceptionThrown']
        checks['No uncaught browser exceptions']=not errors
        (output/'inspection-checks.json').write_text(json.dumps({'checks':checks,'errors':errors},indent=2),encoding='utf-8')
        if errors: raise AssertionError(errors)
        print(f'{len(checks)} browser checks passed; screenshots in .preview/')
    finally:
        if client: client.sock.close()
        process.terminate()
        try: process.wait(timeout=8)
        except subprocess.TimeoutExpired: process.kill()
        log.close()

if __name__=='__main__': main()
