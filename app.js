/* Crosstalk explores data computed by scripts/analyze.py. No external libraries. */
(() => {
  "use strict";
  if (!window.CROSSTALK_DATA || !document.querySelector("#network-atlas")) return;
  const root = document.body.dataset.root || "";
  const { nodes, edges } = window.CROSSTALK_DATA.network;
  const byId = new Map(nodes.map(n => [n.id, n]));
  const incoming = new Map(nodes.map(n => [n.id, new Set()]));
  const outgoing = new Map(nodes.map(n => [n.id, new Set()]));
  edges.forEach(({source, target}) => { outgoing.get(source).add(target); incoming.get(target).add(source); });
  const componentSize = new Map();
  nodes.forEach(n => componentSize.set(n.component, (componentSize.get(n.component) || 0) + 1));
  const rankedBy = key => [...nodes].sort((a,b) => b[key]-a[key] || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  const ranked = rankedBy("in_degree");
  const $ = selector => document.querySelector(selector);
  const labelCounts = new Map();
  nodes.forEach(n => labelCounts.set(n.label, (labelCounts.get(n.label) || 0) + 1));
  const nameOf = n => labelCounts.get(n.label) > 1 ? n.name : n.label || n.name || n.id.replaceAll("_", " ");
  function element(tag, attrs = {}, text = null, ns = null) {
    const e = ns ? document.createElementNS(ns, tag) : document.createElement(tag);
    Object.entries(attrs).forEach(([key,value]) => e.setAttribute(key,value));
    if (text !== null) e.textContent = text;
    return e;
  }
  const svg = (tag, attrs = {}, text = null) => element(tag, attrs, text, "http://www.w3.org/2000/svg");
  const activate = (selector, button) => document.querySelectorAll(selector).forEach(b => {
    b.classList.toggle("active", b === button); b.setAttribute("aria-pressed", String(b === button));
  });
  const scrollAtlas = () => $("#atlas").scrollIntoView({behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"});
  let selected = byId.has("Spider-Man") ? "Spider-Man" : nodes[0].id, direction = "all";
  const atlas = $("#network-atlas");
  const point = n => [38+n.x*824, 38+n.y*624];
  const radius = n => 2.3+Math.sqrt(n.in_degree)*.84;
  const neighbours = () => new Set(direction === "in" ? incoming.get(selected) : direction === "out" ? outgoing.get(selected) : [...incoming.get(selected), ...outgoing.get(selected)]);

  function renderAtlas() {
    atlas.replaceChildren(svg("title", {id:"atlas-svg-title"}, `Marvel network: ${nameOf(byId.get(selected))}`), svg("desc", {id:"atlas-svg-desc"}, "Search for a character to explore its links. Orange is the selected page; teal circles are its neighbours. Arrows run from the linking page to the linked page."));
    const defs = svg("defs");
    ["in","out"].forEach(kind => {
      const marker = svg("marker", {id:`arrow-${kind}`,markerWidth:5,markerHeight:5,refX:4,refY:2.5,orient:"auto",markerUnits:"userSpaceOnUse"});
      marker.append(svg("path", {d:"M0 0 L5 2.5 L0 5 Z",fill:kind === "in" ? "#f2a078" : "#83d0ca"})); defs.append(marker);
    });
    atlas.append(defs);
    const background = svg("g", {"aria-hidden":"true"}), foreground = svg("g", {"aria-hidden":"true"});
    edges.forEach(e => {
      const a=byId.get(e.source), b=byId.get(e.target), [x1,y1]=point(a), [x2,y2]=point(b);
      const isIn=e.target===selected, isOut=e.source===selected;
      if (!((direction!=="out" && isIn)||(direction!=="in" && isOut))) {
        background.append(svg("line", {x1,y1,x2,y2,stroke:"#91b5ad","stroke-opacity":.095,"stroke-width":.65})); return;
      }
      const length=Math.hypot(x2-x1,y2-y1)||1, tx=x2-(x2-x1)/length*(radius(b)+4), ty=y2-(y2-y1)/length*(radius(b)+4);
      const curve=outgoing.get(e.target).has(e.source)?6:0, cx=(x1+tx)/2-(y2-y1)/length*curve, cy=(y1+ty)/2+(x2-x1)/length*curve;
      foreground.append(svg("path", {d:`M${x1},${y1} Q${cx},${cy} ${tx},${ty}`,fill:"none",stroke:isIn?"#f2a078":"#83d0ca","stroke-width":1.05,"stroke-opacity":.72,"marker-end":`url(#arrow-${isIn?"in":"out"})`}));
    });
    atlas.append(background,foreground);
    const adjacent=neighbours(), dots=svg("g");
    [...nodes].sort((a,b)=>Number(a.id===selected)-Number(b.id===selected)).forEach(n=>{
      const [cx,cy]=point(n), active=n.id===selected, neighbour=adjacent.has(n.id), g=svg("g",{"data-node":n.id,class:"atlas-node",cursor:"pointer"});
      g.append(svg("title",{},`${nameOf(n)}: ${n.in_degree} incoming, ${n.out_degree} outgoing`),svg("circle",{cx,cy,r:Math.max(radius(n)+3,7),fill:"transparent"}));
      if(active) g.append(svg("circle",{cx,cy,r:radius(n)+7,fill:"none",stroke:"#ef7954","stroke-opacity":.5}));
      g.append(svg("circle",{cx,cy,r:radius(n),fill:active?"#ef7954":neighbour?"#99d5c6":"#77938d",opacity:active||neighbour?1:.52,stroke:"#142a2b","stroke-width":.8})); dots.append(g);
    });
    atlas.append(dots);
    const labels=svg("g",{"aria-hidden":"true","pointer-events":"none"});
    [...new Set([selected,...ranked.slice(0,4).map(n=>n.id)])].forEach(id=>{
      const n=byId.get(id),[x,y]=point(n),left=x>690;
      labels.append(svg("text",{x:x+(left?-1:1)*(radius(n)+9),y:y+4,fill:id===selected?"#ffbc94":"#b5c7be","font-family":"monospace","font-size":11,"text-anchor":left?"end":"start",stroke:"#142a2b","stroke-width":3,"paint-order":"stroke"},nameOf(n)));
    });
    atlas.append(labels);
  }

  function renderDossier() {
    const n=byId.get(selected), dossier=$("#dossier"), isolated=n.in_degree+n.out_degree===0;
    dossier.replaceChildren(element("p",{class:"eyebrow"},"CHARACTER DOSSIER"),element("h3",{},nameOf(n)));
    dossier.append(element("p",{class:"dossier-tag"}, isolated?"ISOLATED · NO RECORDED LINKS":n.component===ranked[0].component?"IN THE GIANT COMPONENT":`ISLAND · ${componentSize.get(n.component)} PAGES`));
    const metrics=element("div",{class:"metric-row"});
    [[n.in_degree,"INCOMING"],[n.out_degree,"OUTGOING"]].forEach(([value,label])=>{const item=element("div",{class:"metric"});item.append(element("strong",{},String(value)),element("span",{},label));metrics.append(item);});
    dossier.append(metrics,element("p",{class:"dossier-description"},isolated?"A real page in the roster. No incoming or outgoing links within this snapshot. Its absence from the edge list is exactly why we loaded the roster first.":`This page shares a weakly connected component with ${componentSize.get(n.component)-1} other pages. Follow a neighbour to keep exploring.`));
    const adjacent=[...neighbours()].map(id=>byId.get(id)).sort((a,b)=>b.in_degree-a.in_degree||a.id.localeCompare(b.id));
    dossier.append(element("p",{class:"eyebrow"},`${direction==="in"?"LINKING HERE":direction==="out"?"LINKED FROM HERE":"NEIGHBOURS"} / ${adjacent.length}`));
    const list=element("div",{class:"neighbour-list"});
    adjacent.slice(0,7).forEach(n=>{const button=element("button",{class:"neighbour-button",type:"button"},`${nameOf(n)} ↗`);button.addEventListener("click",()=>select(n.id));list.append(button);});
    if(!adjacent.length)list.append(element("p",{class:"chart-note"},"Nothing in this direction. The silence is part of the data."));
    dossier.append(list);
    if(adjacent.length>7)dossier.append(element("p",{class:"chart-note"},`Showing 7 of ${adjacent.length}, ranked by in-degree.`));
    if(n.url && /^https:\/\/en\.wikipedia\.org\//.test(n.url))dossier.append(element("a",{class:"text-link",href:n.url,target:"_blank",rel:"noopener noreferrer"},"Read the Wikipedia page ↗"));
  }
  function select(id,scroll=false) {
    if(!byId.has(id))return;
    selected=id;$("#character-search").value=nameOf(byId.get(id));
    $("#search-status").textContent=`Showing ${nameOf(byId.get(id))}.`;
    $("#search-status").classList.add("sr-only"); renderAtlas();renderDossier();if(scroll)scrollAtlas();
  }
  $("#search-form").addEventListener("submit",event=>{
    event.preventDefault();const term=$("#character-search").value.trim().toLowerCase();
    const match=nodes.find(n=>n.id.toLowerCase()===term)||nodes.find(n=>nameOf(n).toLowerCase()===term)||ranked.find(n=>term&&(n.label.toLowerCase()===term||nameOf(n).toLowerCase().includes(term)));
    if(match){resetZoom();select(match.id);}else{$("#search-status").classList.remove("sr-only");$("#search-status").textContent="No character found. Try Spider-Man, Baymax, or a name from the suggestions.";}
  });
  document.querySelectorAll("[data-direction]").forEach(b=>b.addEventListener("click",()=>{direction=b.dataset.direction;activate("[data-direction]",b);renderAtlas();renderDossier();}));
  document.querySelectorAll(".inspect-character").forEach(b=>b.addEventListener("click",()=>{resetZoom();select(b.dataset.character,true);}));
  let view={x:0,y:0,w:900,h:700},drag=null,dragged=false;
  const updateView=()=>atlas.setAttribute("viewBox",`${view.x} ${view.y} ${view.w} ${view.h}`);
  function resetZoom(){view={x:0,y:0,w:900,h:700};updateView();}
  function zoom(factor){const w=Math.max(225,Math.min(1350,view.w*factor)),h=w*700/900;view={x:view.x+(view.w-w)/2,y:view.y+(view.h-h)/2,w,h};updateView();}
  $("#zoom-in").addEventListener("click",()=>zoom(.75));$("#zoom-out").addEventListener("click",()=>zoom(1.3333));$("#zoom-reset").addEventListener("click",resetZoom);
  atlas.addEventListener("pointerdown",e=>{if(e.pointerType==="touch")return;drag={x:e.clientX,y:e.clientY,vx:view.x,vy:view.y};dragged=false;atlas.setPointerCapture(e.pointerId);});
  atlas.addEventListener("pointermove",e=>{if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(Math.abs(dx)+Math.abs(dy)>5)dragged=true;if(dragged){const r=atlas.getBoundingClientRect();view.x=drag.vx-dx*view.w/r.width;view.y=drag.vy-dy*view.h/r.height;updateView();}});
  atlas.addEventListener("pointerup",e=>{if(!dragged){const hit=document.elementFromPoint(e.clientX,e.clientY)?.closest("[data-node]");if(hit)select(hit.dataset.node);}drag=null;if(atlas.hasPointerCapture(e.pointerId))atlas.releasePointerCapture(e.pointerId);dragged=false;});
  atlas.addEventListener("pointercancel",()=>{drag=null;dragged=false;});

  function distribution(key){const counts=new Map();nodes.forEach(n=>counts.set(n[key],(counts.get(n[key])||0)+1));return [...counts].sort((a,b)=>a[0]-b[0]).map(([degree,count])=>({degree,count,probability:count/nodes.length}));}
  function renderDistribution(scale){
    const log=scale==="log",ins=distribution("in_degree"),outs=distribution("out_degree");
    const plot=svg("svg",{viewBox:"0 0 680 410",role:"img","aria-labelledby":"plot-title plot-desc"});
    plot.append(svg("title",{id:"plot-title"},`${log?"Log–log":"Linear"} in-degree and out-degree distributions`),svg("desc",{id:"plot-desc"},"X axis: number of links. Y axis: fraction of pages. Orange points show incoming links, teal points show outgoing links. Exact values are available in the downloaded summary JSON."));
    const m={l:68,r:30,t:28,b:65},w=680-m.l-m.r,h=410-m.t-m.b;
    const maxY=Math.ceil(Math.max(...ins.map(d=>d.probability),...outs.map(d=>d.probability))*10)/10,maxX=Math.ceil(Math.max(...ins.map(d=>d.degree),...outs.map(d=>d.degree))/20)*20;
    const x=k=>m.l+(log?Math.log10(k)/Math.log10(maxX):k/maxX)*w;
    const y=p=>m.t+h*(log?(Math.log10(maxY)-Math.log10(p))/(Math.log10(maxY)-Math.log10(1/nodes.length)):1-p/maxY);
    const xt=log?[1,2,5,10,20,50,100]:Array.from({length:maxX/20+1},(_,i)=>i*20),yt=log?[.005,.01,.02,.05,.1,.2,.3].filter(t=>t>=1/nodes.length&&t<=maxY):Array.from({length:5},(_,i)=>maxY*i/4);
    yt.forEach(t=>{const py=y(t);plot.append(svg("line",{x1:m.l,x2:680-m.r,y1:py,y2:py,stroke:"#ccd0c3","stroke-dasharray":"3 5"}),svg("text",{x:m.l-12,y:py+4,"text-anchor":"end",fill:"#62716a","font-family":"monospace","font-size":11},`${+(t*100).toFixed(1)}%`));});
    xt.forEach(t=>{const px=x(t);plot.append(svg("line",{x1:px,x2:px,y1:m.t+h,y2:m.t+h+6,stroke:"#89998f"}),svg("text",{x:px,y:m.t+h+25,"text-anchor":"middle",fill:"#62716a","font-family":"monospace","font-size":11},String(t)));});
    plot.append(svg("path",{d:`M${m.l} ${m.t} V${m.t+h} H${680-m.r}`,fill:"none",stroke:"#88998e"}));
    [[ins,"#dc512f","Incoming"],[outs,"#2849c7","Outgoing"]].forEach(([data,color,label])=>data.filter(d=>!log||d.degree>0).forEach(d=>{const dot=svg("circle",{cx:x(d.degree),cy:y(d.probability),r:log?4.2:3.5,fill:color,"fill-opacity":.78,stroke:"#f6f1e7","stroke-width":.7});dot.append(svg("title",{},`${label}: ${d.degree} links · ${d.count} pages · ${(d.probability*100).toFixed(2)}%`));plot.append(dot);}));
    plot.append(svg("text",{x:m.l+w/2,y:395,"text-anchor":"middle",fill:"#40594f","font-family":"monospace","font-size":11},log?"NUMBER OF LINKS · LOG SCALE":"NUMBER OF LINKS"),svg("text",{x:18,y:m.t+h/2,transform:`rotate(-90 18 ${m.t+h/2})`,"text-anchor":"middle",fill:"#40594f","font-family":"monospace","font-size":11},log?"FRACTION OF PAGES · LOG SCALE":"FRACTION OF PAGES"));
    $("#distribution-chart").replaceChildren(plot);
    const zi=ins.find(d=>d.degree===0)?.count||0,zo=outs.find(d=>d.degree===0)?.count||0,isolates=nodes.filter(n=>!n.in_degree&&!n.out_degree).length;
    $("#distribution-caption").textContent=log?`True log–log axes. Omitted at degree zero: ${zi} pages with no incoming links; ${zo} with no outgoing links. Of these, ${isolates} have neither. No degree shift or fitted power law.`:`Each point shows the fraction of the ${nodes.length} pages with exactly that degree. Linear axes include degree zero. Hover a point for its count.`;
    $("#download-chart").href=`${root}assets/figures/degree-${log?"loglog":"linear"}.svg`;
  }
  document.querySelectorAll("[data-scale]").forEach(b=>b.addEventListener("click",()=>{activate("[data-scale]",b);renderDistribution(b.dataset.scale);}));
  function renderRanking(kind){const top=rankedBy(`${kind}_degree`).slice(0,5),list=element("ol",{class:"rank-list"});top.forEach((n,i)=>{const li=element("li"),b=element("button",{class:"rank-button",type:"button"});b.append(element("span",{class:"rank-number"},String(i+1).padStart(2,"0")),element("span",{class:"rank-name"},nameOf(n)),element("strong",{},String(n[`${kind}_degree`])),element("i",{class:"rank-bar",style:`width:${n[`${kind}_degree`]/top[0][`${kind}_degree`]*100}%`}));b.addEventListener("click",()=>{resetZoom();select(n.id,true);});li.append(b);list.append(li);});$("#rankings").replaceChildren(list);}
  document.querySelectorAll("[data-ranking]").forEach(b=>b.addEventListener("click",()=>{activate("[data-ranking]",b);renderRanking(b.dataset.ranking);}));
  function removeHubs(){
    const count=Number($("#removal-count").value),removed=new Set(ranked.slice(0,count).map(n=>n.id)),seen=new Set(removed);let largest=0;
    nodes.forEach(n=>{if(seen.has(n.id))return;const stack=[n.id];seen.add(n.id);let size=0;while(stack.length){const id=stack.pop();size++;for(const other of [...incoming.get(id),...outgoing.get(id)])if(!seen.has(other)){seen.add(other);stack.push(other);}}largest=Math.max(largest,size);});
    const remaining=nodes.length-count,share=remaining?largest/remaining*100:0;
    $("#removal-label").textContent=count;$("#remaining-giant").textContent=largest;$("#giant-bar").style.width=`${share}%`;
    $("#removal-detail").textContent=`${largest} of ${remaining} surviving pages · ${share.toFixed(1)}%`;
    $("#removed-names").textContent=count?`Removed: ${ranked.slice(0,Math.min(count,3)).map(nameOf).join(", ")}${count>3?` + ${count-3} more`:""}. ${remaining-largest} surviving pages sit outside the largest component.`:"Slide to begin the experiment. Ranking stays fixed at the original in-degree.";
  }
  $("#removal-count").addEventListener("input",removeHubs);
  $("#remove-spider").addEventListener("click",()=>{$("#removal-count").value=1;removeHubs();});
  renderAtlas();renderDossier();renderDistribution("linear");renderRanking("in");removeHubs();
})();
