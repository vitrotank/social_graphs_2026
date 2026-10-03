/* The measured tail is recomputed from the frozen roster. Guides are sketches. */
(() => {
  'use strict';
  const nodes=window.CROSSTALK_DATA?.network?.nodes;
  const plot=document.getElementById('w2-ccdf-plot');
  if(!nodes || !plot)return;
  const $=id=>document.getElementById(id), NS='http://www.w3.org/2000/svg';
  const positive=nodes.filter(node=>node.in_degree>0), degrees=[...new Set(positive.map(node=>node.in_degree))].sort((a,b)=>a-b);
  const count=k=>positive.filter(node=>node.in_degree>=k).length;
  const state={k:10,slope:1.35,references:true,view:'models'};
  const svg=(tag,attrs={},text)=>{const el=document.createElementNS(NS,tag);Object.entries(attrs).forEach(([key,value])=>el.setAttribute(key,String(value)));if(text!==undefined)el.textContent=text;return el;};
  const el=(tag,text)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;return node;};
  const x=k=>76+Math.log10(Math.max(1,k))/Math.log10(120)*844;
  const y=p=>374-(Math.log10(Math.max(.003,Math.min(1,p)))-Math.log10(.003))/(0-Math.log10(.003))*336;
  let cursor;
  function readout(k){
    state.k=Math.max(1,Math.min(106,Math.round(k)));$('w2-tail-k').value=state.k;$('w2-tail-value').textContent=`k ≥ ${state.k}`;
    const total=count(state.k),percent=100*total/positive.length;
    const title=el('strong',`${total}`),text=el('p');text.append(el('span',`of ${positive.length} pages with incoming links`),el('br'),el('span',`${percent.toFixed(1)}% receive at least ${state.k} links`));
    $('w2-tail-readout').replaceChildren(title,text);$('w2-tail-readout').dataset.count=String(total);$('w2-tail-readout').dataset.threshold=String(state.k);
    const hubList=[...positive].filter(node=>node.in_degree>=state.k).sort((a,b)=>b.in_degree-a.in_degree||a.id.localeCompare(b.id)).slice(0,4);
    $('w2-tail-links').replaceChildren(el('span','FOLLOW THE PAGES IN THIS TAIL'),...hubList.map(node=>{const link=el('a',`${node.label} · ${node.in_degree} ↗`);link.href=`${document.body.dataset.root}week1/index.html?character=${encodeURIComponent(node.id)}#atlas`;return link;}));
    if(cursor){cursor.replaceChildren(svg('line',{x1:x(state.k),x2:x(state.k),y1:38,y2:374,stroke:'#b95836','stroke-width':1.3,'stroke-dasharray':'4 5'}),svg('circle',{cx:x(state.k),cy:y(total/positive.length),r:7,fill:'#dc512f',stroke:'#fffdf7','stroke-width':3}));}
  }
  function poisson(k){let term=Math.exp(-5.88),sum=term;for(let i=1;i<k;i++){term*=5.88/i;sum+=term;}return Math.max(0,1-sum);}
  function render(){
    plot.replaceChildren(svg('title',{},'How many Marvel pages receive at least k incoming links?'),svg('desc',{},`Counts use ${positive.length} positive-degree pages. ${state.references ? `The blue guide${state.view==='models' ? ' and green Poisson reference' : ''} are chosen illustrations, not fitted models.` : 'Only measured observations are shown.'} Focus a measured dot to inspect its count.`));
    const grid=svg('g',{'font-family':'Arial, sans-serif','font-size':17,fill:'#677164'});
    [1,2,5,10,20,50,100].forEach(k=>grid.append(svg('line',{x1:x(k),x2:x(k),y1:38,y2:374,stroke:'#d9dccd','stroke-width':1}),svg('text',{x:x(k),y:403,'text-anchor':'middle'},k)));
    [.005,.01,.02,.05,.1,.2,.5,1].forEach(p=>grid.append(svg('line',{x1:76,x2:920,y1:y(p),y2:y(p),stroke:'#d9dccd','stroke-width':1}),svg('text',{x:63,y:y(p)+5,'text-anchor':'end'},`${100*p}%`)));
    grid.append(svg('text',{x:498,y:443,'text-anchor':'middle','font-size':15,'letter-spacing':1},'INCOMING LINKS · k'),svg('text',{x:76,y:20,'font-size':15,'letter-spacing':.5},'PAGES WITH AT LEAST k LINKS / POSITIVE-DEGREE PAGES'));plot.append(grid);
    if(state.view==='fit'){plot.append(svg('rect',{x:x(2),y:38,width:x(35)-x(2),height:336,fill:'#e6b89a',opacity:.18}));}
    if(state.references){
      const reference=svg('g',{'aria-hidden':'true'}),power=[];
      for(let k=1;k<=120;k++){const p=state.view==='fit' ? 0.83*(k/2)**(-state.slope) : Math.min(1,(2/k)**state.slope);if(p>=.003)power.push(`${x(k)},${y(p)}`);}
      reference.append(svg('polyline',{points:power.join(' '),fill:'none',stroke:'#2849c7','stroke-width':2.5,'stroke-dasharray':state.view==='fit'?'6 5':'none'}));
      if(state.view==='models'){const points=[];for(let k=1;k<=25;k++){const p=poisson(k);if(p>=.003)points.push(`${x(k)},${y(p)}`);}reference.append(svg('polyline',{points:points.join(' '),fill:'none',stroke:'#486452','stroke-width':2.5,'stroke-dasharray':'5 5'}));}
      plot.append(reference);
    }
    let path=`M${x(1)},${y(1)}`;
    for(let k=2;k<=106;k++)path+=`H${x(k)}V${y(count(k)/positive.length)}`;
    plot.append(svg('path',{d:path,fill:'none',stroke:'#dc512f','stroke-width':2.5}));
    const marks=svg('g');degrees.forEach(k=>{const n=count(k);const point=svg('circle',{cx:x(k),cy:y(n/positive.length),r:4.5,fill:'#dc512f',stroke:'#fffdf7','stroke-width':1.5,tabindex:0,role:'button','aria-label':`At least ${k} incoming links: ${n} of ${positive.length} pages`,class:'w2-measured-point','data-degree':k});point.append(svg('title',{},`${n} pages receive at least ${k} links`));point.addEventListener('pointerenter',()=>readout(k));point.addEventListener('focus',()=>readout(k));point.addEventListener('click',()=>readout(k));point.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();readout(k);}});marks.append(point);});plot.append(marks);
    cursor=svg('g',{'aria-hidden':'true'});plot.append(cursor);readout(state.k);
    const caption = `Orange steps and dots show measured counts among ${positive.length} pages with incoming links. `;
    $('ccdf-switch-caption').textContent = caption + (state.references
      ? `The chosen blue guide has slope −${state.slope.toFixed(2)} on these log axes${state.view==='fit' ? '; the shaded range is 2–35 links' : '; the green reference uses Poisson mean 5.88'}. These are illustrations, not fitted models. The download preserves the original static reference.`
      : 'Only the observations are shown. The download preserves the original static reference, including its illustrative curves.');
    document.querySelector('[data-w2-legend="guide"]').hidden = !state.references;
    document.querySelector('[data-w2-legend="poisson"]').hidden = !state.references || state.view!=='models';
    $('ccdf-download-link').textContent = 'Download static reference ↓';
    plot.dataset.state='ready';plot.dataset.view=state.view;
  }
  $('w2-tail-k').addEventListener('input',event=>readout(Number(event.target.value)));
  $('w2-guide-slope').addEventListener('input',event=>{state.slope=Number(event.target.value);$('w2-guide-value').textContent=state.slope.toFixed(2);render();});
  $('w2-show-reference').addEventListener('change',event=>{state.references=event.target.checked;render();});
  $('w2-tail-reset').addEventListener('click',()=>{state.k=10;state.slope=1.35;state.references=true;$('w2-guide-slope').value=1.35;$('w2-guide-value').textContent='1.35';$('w2-show-reference').checked=true;render();});
  document.querySelectorAll('[data-ccdf-view]').forEach(button=>button.addEventListener('click',()=>{state.view=button.dataset.ccdfView;render();}));
  $('w2-ccdf-fallback').hidden=true;$('w2-ccdf-live').hidden=false;render();
})();
