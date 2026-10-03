/* Chapter navigation and reading progress, confined to published stories. */
(() => {
  'use strict';
  if (!document.body.classList.contains('issue-story')) return;
  const main = document.querySelector('main');
  if (!main) return;
  const names = {report:'The question',finding:'The question',atlas:'The interactive atlas',degrees:'Attention and degree',islands:'Islands and isolates',experiment:'Remove a hero',methods:'Data and methods',paradox:'Friends and hubs',shuffle:'The shuffle test',growth:'Growing a network',blackout:'The removal experiment',pathfinder:'Paths through the network','b-side':'The grunge B-side','week3-method':'Data and methods',weights:'Weighted communities',backbone:'The breaking point',method:'Data and methods'};
  const chapters = [...main.querySelectorAll(':scope > section[id], :scope > article[id]')].filter(node => node.querySelector('h2'));
  if (!chapters.length) return;
  const create = (tag, text, cls) => {const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;};
  const rail = create('nav',undefined,'journal-rail'); rail.setAttribute('aria-label','Reading guide');
  const inner = create('div',undefined,'shell journal-rail-inner');
  const currentIssue = document.querySelector('.issue-nav [aria-current="page"]');
  const issueLabel = currentIssue?.textContent.replace(/\s+/g,' ').trim().match(/Week\s+(\d+)/)?.[1] || '';
  inner.append(create('span',`ISSUE ${issueLabel.padStart(2,'0')}`,'journal-rail-label'));
  const select = create('select');select.setAttribute('aria-label','Jump to a chapter');
  chapters.forEach((chapter,index)=>{const option=create('option',`${String(index+1).padStart(2,'0')} / ${names[chapter.id] || chapter.querySelector('h2').innerText.replace(/\s+/g,' ').trim()}`);option.value=chapter.id;select.append(option);});
  select.addEventListener('change',()=>{const node=document.getElementById(select.value);node?.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});if(node)history.replaceState(null,'',`#${encodeURIComponent(node.id)}`);});
  inner.append(select);
  const archive=create('a','All issues ↗');archive.href=`${document.body.dataset.root || '../'}index.html#journal`;inner.append(archive);
  const progress=create('div',undefined,'journal-progress');
  const track=create('span',undefined,'journal-progress-track');const fill=create('i');track.setAttribute('aria-hidden','true');track.append(fill);
  const percent=create('span','0%','journal-progress-percent');progress.append(track,percent);progress.setAttribute('aria-label','Reading progress');inner.append(progress);
  rail.append(inner);main.before(rail);document.documentElement.classList.add('journal-reader');
  let scheduled=false;
  function update(){scheduled=false;const top=main.getBoundingClientRect().top+scrollY;const total=Math.max(1,main.offsetHeight-innerHeight);const value=Math.max(0,Math.min(100,(scrollY-top)/total*100));fill.style.width=`${value}%`;percent.textContent=`${Math.round(value)}%`;let active=chapters[0];for(const chapter of chapters){if(chapter.getBoundingClientRect().top<130)active=chapter;}if(document.activeElement!==select)select.value=active.id;}
  function schedule(){if(scheduled)return;scheduled=true;requestAnimationFrame(update);}
  addEventListener('scroll',schedule,{passive:true});addEventListener('resize',schedule);update();
})();
