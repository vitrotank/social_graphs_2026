/* Exact counts and attributed passages from the frozen Week 5 corpus. */
(() => {
  'use strict';
  const data = window.WEEK5_DATA;
  if (!data) return;
  const $ = id => document.getElementById(id);
  const plot = $('w5-plot'), slider = $('w5-threshold'), select = $('w5-pair-select');
  if (!plot || !slider || !select) return;
  const NS='http://www.w3.org/2000/svg', format=n=>n.toLocaleString('en-US');
  const compact=window.matchMedia('(max-width: 620px)');
  let threshold=20, selected=data.examples.story.id, category='all';
  const unique=new Map(data.pairs.map(p=>[p.id,p]));
  unique.set(data.examples.editorial.id,data.examples.editorial);
  const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
  const svg=(tag,attrs,text)=>{const e=document.createElementNS(NS,tag);Object.entries(attrs||{}).forEach(([k,v])=>e.setAttribute(k,v));if(text!==undefined)e.textContent=text;return e;};
  const X=n=>(compact.matches?56:82)+(n-8)/52*(compact.matches?344:810);
  const Y=n=>(compact.matches?300:335)-Math.log10(Math.max(1,n))/5*(compact.matches?245:270);
  const path=key=>data.thresholds.map((r,i)=>`${i?'L':'M'}${X(r.length).toFixed(2)},${Y(r[key]).toFixed(2)}`).join(' ');
  function draw(){
    const row=data.thresholds.find(r=>r.length===threshold), compare=$('w5-without-lead').checked;
    const small=compact.matches, left=small?56:82, right=small?400:914, baseline=small?300:335;
    plot.setAttribute('viewBox',small?'0 0 450 380':'0 0 960 420');
    plot.replaceChildren(svg('title',{id:'w5-plot-title'},'Longer phrases reveal a much smaller overlap'),svg('desc',{id:'w5-plot-desc'},`All 303 articles; 45,753 possible unordered pairs. At eight words 40,570 pairs match; at twenty 71; at forty 13; at sixty 8. Vertical scale is logarithmic: equal distances multiply counts by ten. Selected ${threshold} words: ${format(row.pairs)} pairs.${compare?` Without first paragraphs: ${format(row.without_lead_pairs)}.`:''}`));
    for(const count of [1,10,100,1000,10000,100000]){
      const y=Y(count);
      const label=small&&count>=1000?`${count/1000}k`:format(count);
      plot.append(svg('line',{x1:left,x2:right,y1:y,y2:y,class:'w5-grid'}),svg('text',{x:left-13,y:y+4,'text-anchor':'end',class:'w5-axis'},label));
    }
    plot.append(svg('text',{x:left,y:28,class:'w5-axis-heading'},small?'ARTICLE PAIRS / LOG SCALE':'MATCHING ARTICLE PAIRS / LOG SCALE'));
    for(const length of small?[8,20,40,60]:[8,20,30,40,50,60]){
      plot.append(svg('line',{x1:X(length),x2:X(length),y1:baseline,y2:baseline+7,class:'w5-tick'}),svg('text',{x:X(length),y:baseline+28,'text-anchor':'middle',class:'w5-axis'},length));
    }
    plot.append(svg('text',{x:small?228:500,y:small?365:400,'text-anchor':'middle',class:'w5-axis-heading'},small?'MINIMUM WORDS SHARED':'MINIMUM CONSECUTIVE WORDS SHARED'));
    plot.append(svg('path',{d:path('pairs')+` L${X(60)},${baseline} L${left},${baseline} Z`,class:'w5-curve-area'}),svg('path',{d:path('pairs'),class:'w5-curve'}));
    if(compare) plot.append(svg('path',{d:path('without_lead_pairs'),class:'w5-comparison-curve'}));
    for(const length of [8,20,40]){
      const r=data.thresholds.find(r=>r.length===length), x=X(length), y=Y(r.pairs);
      plot.append(svg('circle',{cx:x,cy:y,r:5,class:'w5-anchor'}));
      const dx=length===8?18:12, dy=length===8?-13:-19;
      plot.append(svg('text',{x:x+dx,y:y+dy,class:'w5-value-label'},format(r.pairs)),svg('text',{x:x+dx,y:y+dy+17,class:'w5-annotation'},`${length} words`));
    }
    plot.append(svg('line',{x1:X(threshold),x2:X(threshold),y1:52,y2:baseline,class:'w5-cursor'}),svg('circle',{cx:X(threshold),cy:Y(row.pairs),r:9,class:'w5-selected-point'}));
    $('w5-threshold-value').textContent=`${threshold} words`;
    $('w5-pair-count').textContent=format(row.pairs);
    $('w5-article-count').textContent=row.articles;
    $('w5-pair-percent').textContent=`${row.percent.toFixed(row.percent<1?2:1)}%`;
    $('w5-comparison-note').textContent=compare?`Without each article’s first paragraph: ${format(row.without_lead_pairs)} pairs at ${threshold} words. The solid curve and evidence directory use full articles.`:'Equal vertical steps multiply the count by ten. Every count is measured on the complete frozen corpus.';
    $('w5-comparison-legend').hidden=!compare;
    document.querySelectorAll('[data-w5-threshold]').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.w5Threshold)===threshold)));
  }
  function evidence(pair){
    selected=pair.id;select.value=selected;
    const panel=$('w5-evidence-panel');panel.replaceChildren();
    const head=node('div',undefined,'w5-passage-head');
    head.append(node('span',pair.category,'w5-category-label'),node('strong',`${pair.length} consecutive normalized words`));
    panel.append(head);
    const columns=node('div',undefined,'w5-source-columns');
    pair.sources.forEach((source,index)=>{
      const card=node('article',undefined,'w5-source');
      card.append(node('p',`SOURCE ${String(index+1).padStart(2,'0')} / ${source.section}`,'eyebrow'),node('h3',source.name));
      const quote=node('blockquote'),mark=node('mark',source.excerpt);quote.append(mark);card.append(quote);
      const details=node('details',undefined,'w5-full-passage');details.append(node('summary','Read the complete match in context'));
      const context=node('p');context.append(node('span',`…${source.before} `,'w5-context'),node('mark',source.text),node('span',` ${source.after}…`,'w5-context'));details.append(context);
      details.append(node('p',`Frozen paragraph ${source.paragraph}; characters ${format(source.start)}–${format(source.end)} (Python offsets).`,'w5-source-offset'));
      card.append(details);
      const a=node('a','Wikipedia article & history ↗');a.href=source.url;card.append(a);columns.append(card);
    });
    panel.append(columns);
    panel.append(node('p',pair.linked===undefined?'An introductory formula shared across distinct pages.':pair.linked?'These two pages also share a hyperlink in the frozen Week 1 network.':'No hyperlink joins these two pages inside the frozen Week 1 roster.','w5-network-note'));
    document.querySelectorAll('[data-w5-example]').forEach(b=>b.setAttribute('aria-pressed',String(data.examples[b.dataset.w5Example]?.id===selected)));
  }
  function updateDirectory(){
    const linked=$('w5-linked')?.checked;
    let choices=data.pairs.filter(p=>p.length>=Math.max(20,threshold)&&(category==='all'||p.category===category)&&(!linked||p.linked));
    if(threshold<=data.examples.editorial.length&&(category==='all'||category===data.examples.editorial.category)&&!linked)choices=[data.examples.editorial,...choices];
    select.replaceChildren();
    choices.forEach(p=>{const o=node('option',`${p.sources[0].name} × ${p.sources[1].name} · ${p.length} words`);o.value=p.id;select.append(o);});
    select.disabled=choices.length===0;
    $('w5-evidence-count').textContent=`${choices.length} passage comparisons in this view. The directory covers all 71 pairs with a longest match of at least 20 words, plus one short formula example. It is not the complete eight-word network.`;
    if(!choices.length){$('w5-evidence-panel').replaceChildren(node('p','No inspected pair meets these filters. Choose another category or shorten the phrase length.','w5-empty'));return;}
    evidence(choices.find(p=>p.id===selected)||choices[0]);
  }
  function setThreshold(value){threshold=Math.max(8,Math.min(60,Math.round(value)));slider.value=threshold;draw();updateDirectory();}
  slider.addEventListener('input',()=>setThreshold(Number(slider.value)));
  document.querySelectorAll('[data-w5-threshold]').forEach(b=>b.addEventListener('click',()=>{if(Number(b.dataset.w5Threshold)===8)selected=data.examples.editorial.id;setThreshold(Number(b.dataset.w5Threshold));}));
  $('w5-without-lead').addEventListener('change',draw);
  select.addEventListener('change',()=>evidence(unique.get(select.value)));
  const categories=$('w5-category');
  [...new Set(data.pairs.map(p=>p.category))].sort().forEach(c=>{const o=node('option',c);o.value=c;categories.append(o);});
  categories.addEventListener('change',()=>{category=categories.value;updateDirectory();});
  $('w5-linked')?.addEventListener('change',updateDirectory);
  document.querySelectorAll('[data-w5-example]').forEach(b=>b.addEventListener('click',()=>{
    const pair=data.examples[b.dataset.w5Example];if(!pair)return;
    category='all';categories.value='all';if($('w5-linked'))$('w5-linked').checked=false;
    selected=pair.id;setThreshold(pair.id===data.examples.editorial.id?8:20);
  }));
  plot.addEventListener('click',event=>{const box=plot.getBoundingClientRect();setThreshold(8+((event.clientX-box.left)/box.width*(compact.matches?450:960)-(compact.matches?56:82))/(compact.matches?344:810)*52);});
  compact.addEventListener('change',draw);
  draw();updateDirectory();plot.dataset.ready='true';
})();
