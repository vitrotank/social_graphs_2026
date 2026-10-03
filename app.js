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
  const linkedCharacter=new URLSearchParams(location.search).get("character");
  let selected = byId.has(linkedCharacter)?linkedCharacter:byId.has("Spider-Man") ? "Spider-Man" : nodes[0].id, direction = "all";
  let distributionScale = "linear", degreeScale = "linear", degreeView = "all", degreeFocus = selected;
  const degreeSeries = new Set(["in", "out"]);
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
      const [cx,cy]=point(n), active=n.id===selected, neighbour=adjacent.has(n.id), g=svg("g",{"data-node":n.id,class:`atlas-node${active?" selected":""}`,cursor:"pointer",tabindex:active?0:-1,role:"button","aria-label":`${nameOf(n)}: ${n.in_degree} incoming and ${n.out_degree} outgoing links`});
      g.append(svg("title",{},`${nameOf(n)}: ${n.in_degree} incoming, ${n.out_degree} outgoing`),svg("circle",{cx,cy,r:Math.max(radius(n)+3,7),fill:"transparent"}));
      if(active) g.append(svg("circle",{cx,cy,r:radius(n)+7,fill:"none",stroke:"#ef7954","stroke-opacity":.5}));
      g.append(svg("circle",{cx,cy,r:radius(n),fill:active?"#ef7954":neighbour?"#99d5c6":"#77938d",opacity:active||neighbour?1:.52,stroke:"#142a2b","stroke-width":.8}));
      g.addEventListener("keydown",event=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();select(n.id,false,true);}}); dots.append(g);
    });
    atlas.append(dots);
    const labels=svg("g",{"aria-hidden":"true","pointer-events":"none"});
    const occupied=[];
    [...new Set([selected,...ranked.slice(0,5).map(n=>n.id)])].forEach(id=>{
      const n=byId.get(id),[x,y]=point(n),left=x>650,text=nameOf(n),font=id===selected?16:13,width=text.length*font*.62;
      const tx=x+(left?-1:1)*(radius(n)+10),start=left?tx-width:tx;
      let ty=y+5;
      for(let step=0;step<6;step++){
        if(!occupied.some(box=>start<box.x+box.w&&start+width>box.x&&ty-font<box.y+box.h&&ty>box.y))break;
        ty=y+5+(step%2===0?-1:1)*(Math.floor(step/2)+1)*18;
      }
      occupied.push({x:start,y:ty-font,w:width,h:font+5});
      labels.append(svg("text",{x:tx,y:ty,fill:id===selected?"#ffbc94":"#d3dfd8","font-family":"monospace","font-size":font,"font-weight":id===selected?600:400,"text-anchor":left?"end":"start",stroke:"#142a2b","stroke-width":4,"paint-order":"stroke","stroke-linejoin":"round",class:id===selected?"atlas-selected-label":"atlas-hub-label"},text));
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
    adjacent.slice(0,7).forEach(n=>{const button=element("button",{class:"neighbour-button",type:"button"},`${nameOf(n)} ↗`);button.addEventListener("click",event=>select(n.id,false,event.detail===0));list.append(button);});
    if(!adjacent.length)list.append(element("p",{class:"chart-note"},"Nothing in this direction. The silence is part of the data."));
    dossier.append(list);
    if(adjacent.length>7)dossier.append(element("p",{class:"chart-note"},`Showing 7 of ${adjacent.length}, ranked by in-degree.`));
    if(n.url && /^https:\/\/en\.wikipedia\.org\//.test(n.url))dossier.append(element("a",{class:"text-link",href:n.url,target:"_blank",rel:"noopener noreferrer"},"Read the Wikipedia page ↗"));
  }
  function select(id,scroll=false,focusAtlas=false) {
    if(!byId.has(id))return;
    selected=id;$("#character-search").value=nameOf(byId.get(id));
    $("#search-status").textContent=`Showing ${nameOf(byId.get(id))}.`;
    $("#search-status").classList.add("sr-only"); renderAtlas();renderDossier();
    focusDegree(id);
    if(scroll)scrollAtlas();
    if(focusAtlas){
      const activeNode=[...atlas.querySelectorAll("[data-node]")].find(node=>node.dataset.node===id);
      activeNode?.focus({preventScroll:true});
    }
  }
  $("#search-form").addEventListener("submit",event=>{
    event.preventDefault();const term=$("#character-search").value.trim().toLowerCase();
    const match=nodes.find(n=>n.id.toLowerCase()===term)||nodes.find(n=>nameOf(n).toLowerCase()===term)||ranked.find(n=>term&&(n.label.toLowerCase()===term||nameOf(n).toLowerCase().includes(term)));
    if(match){resetZoom();select(match.id);}else{$("#search-status").classList.remove("sr-only");$("#search-status").textContent="No character found. Try Spider-Man, Baymax, or a name from the suggestions.";}
  });
  document.querySelectorAll("[data-direction]").forEach(b=>b.addEventListener("click",()=>{direction=b.dataset.direction;activate("[data-direction]",b);renderAtlas();renderDossier();}));
  document.querySelectorAll(".inspect-character").forEach(b=>b.addEventListener("click",event=>{resetZoom();select(b.dataset.character,true,event.detail===0);}));
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
    distributionScale=scale;
    $("#degree-readout").replaceChildren(element("span",{class:"readout-label"},"EVERY DOT IS A COUNT"),element("p",{},"Hover or focus a point to see its exact degree, page count and share of the complete roster."));
    const log=scale==="log",ins=distribution("in_degree"),outs=distribution("out_degree");
    const plot=svg("svg",{viewBox:"0 0 680 410",role:"group","aria-labelledby":"plot-title plot-desc"});
    plot.append(svg("title",{id:"plot-title"},`${log?"Log–log":"Linear"} in-degree and out-degree distributions`),svg("desc",{id:"plot-desc"},"X axis: exact number of links. Y axis: fraction of all 303 pages. Orange circles show incoming links; blue diamonds show outgoing links. Hover or focus a point for an exact count and example pages."));
    const m={l:68,r:30,t:28,b:65},w=680-m.l-m.r,h=410-m.t-m.b;
    const maxY=Math.ceil(Math.max(...ins.map(d=>d.probability),...outs.map(d=>d.probability))*10)/10,maxX=Math.ceil(Math.max(...ins.map(d=>d.degree),...outs.map(d=>d.degree))/20)*20;
    const x=k=>m.l+(log?Math.log10(k)/Math.log10(maxX):k/maxX)*w;
    const y=p=>m.t+h*(log?(Math.log10(maxY)-Math.log10(p))/(Math.log10(maxY)-Math.log10(1/nodes.length)):1-p/maxY);
    const xt=log?[1,2,5,10,20,50,100]:Array.from({length:maxX/20+1},(_,i)=>i*20),yt=log?[.005,.01,.02,.05,.1,.2,.3].filter(t=>t>=1/nodes.length&&t<=maxY):Array.from({length:5},(_,i)=>maxY*i/4);
    yt.forEach(t=>{const py=y(t);plot.append(svg("line",{x1:m.l,x2:680-m.r,y1:py,y2:py,stroke:"#ccd0c3","stroke-dasharray":"3 5"}),svg("text",{x:m.l-12,y:py+4,"text-anchor":"end",fill:"#62716a","font-family":"monospace","font-size":13},`${+(t*100).toFixed(1)}%`));});
    xt.forEach(t=>{const px=x(t);plot.append(svg("line",{x1:px,x2:px,y1:m.t+h,y2:m.t+h+6,stroke:"#89998f"}),svg("text",{x:px,y:m.t+h+25,"text-anchor":"middle",fill:"#62716a","font-family":"monospace","font-size":13},String(t)));});
    plot.append(svg("path",{d:`M${m.l} ${m.t} V${m.t+h} H${680-m.r}`,fill:"none",stroke:"#88998e"}));
    [[ins,"#d65936","Incoming","in"],[outs,"#3158a4","Outgoing","out"]].forEach(([data,color,label,kind])=>{
      if(!degreeSeries.has(kind))return;
      const values=data.filter(d=>!log||d.degree>0);
      values.forEach(d=>{
        const px=x(d.degree),py=y(d.probability),description=`${label}: ${d.degree} links; ${d.count} pages; ${(d.probability*100).toFixed(2)}% of all ${nodes.length} pages`;
        const dot=svg("g",{class:`degree-point degree-point-${kind}`,"data-degree-point":`${kind}-${d.degree}`,"data-degree":d.degree,"data-degree-kind":kind,role:"button",tabindex:0,"aria-label":description});
        dot.append(svg("title",{},description),svg("circle",{cx:px,cy:py,r:9,fill:"transparent",class:"degree-point-target"}));
        dot.append(kind==="in"?svg("circle",{cx:px,cy:py,r:4.3,fill:color,class:"degree-mark"}):svg("path",{d:`M${px} ${py-5} L${px+5} ${py} L${px} ${py+5} L${px-5} ${py} Z`,fill:color,class:"degree-mark"}));
        const inspect=()=>{
          plot.querySelectorAll(".degree-point.is-focused").forEach(e=>e.classList.remove("is-focused"));dot.classList.add("is-focused");
          const readout=$("#degree-readout"),examples=rankedBy(`${kind}_degree`).filter(n=>n[`${kind}_degree`]===d.degree).slice(0,3);
          readout.replaceChildren(element("span",{class:"readout-label"},`${label.toUpperCase()} / ${d.degree} LINKS`),element("p",{},`${d.count} ${d.count===1?"page":"pages"} · ${(d.probability*100).toFixed(2)}% of the complete roster`));
          const examplesList=element("div",{class:"degree-examples"});examples.forEach(n=>{const b=element("button",{type:"button",class:"text-link","data-degree-example":n.id},`${nameOf(n)} ↗`);b.addEventListener("click",event=>{resetZoom();select(n.id,true,event.detail===0);});examplesList.append(b);});readout.append(examplesList);
        };
        dot.addEventListener("pointerenter",inspect);dot.addEventListener("focus",inspect);dot.addEventListener("click",inspect);dot.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();inspect();}});plot.append(dot);
      });
    });
    plot.append(svg("text",{x:m.l+w/2,y:395,"text-anchor":"middle",fill:"#40594f","font-family":"monospace","font-size":13},log?"NUMBER OF LINKS · LOG SCALE":"NUMBER OF LINKS"),svg("text",{x:18,y:m.t+h/2,transform:`rotate(-90 18 ${m.t+h/2})`,"text-anchor":"middle",fill:"#40594f","font-family":"monospace","font-size":13},log?"FRACTION OF PAGES · LOG SCALE":"FRACTION OF PAGES"));
    $("#distribution-chart").replaceChildren(plot);
    const zi=ins.find(d=>d.degree===0)?.count||0,zo=outs.find(d=>d.degree===0)?.count||0,isolates=nodes.filter(n=>!n.in_degree&&!n.out_degree).length;
    $("#distribution-caption").textContent=log?`True log–log axes. Omitted at degree zero: ${zi} pages with no incoming links; ${zo} with no outgoing links. Of these, ${isolates} have neither. No degree shift or fitted power law.`:`Each point shows the fraction of all ${nodes.length} pages with exactly that degree. Linear axes include degree zero. Hover or focus a point for its count and example pages.`;
    $("#download-chart").href=`${root}assets/figures/degree-${log?"loglog":"linear"}.svg`;
  }
  document.querySelectorAll("[data-scale]").forEach(b=>b.addEventListener("click",()=>{activate("[data-scale]",b);renderDistribution(b.dataset.scale);}));
  document.querySelectorAll("[data-degree-series]").forEach(b=>b.addEventListener("click",()=>{
    const kind=b.dataset.degreeSeries;
    if(degreeSeries.has(kind)){
      if(degreeSeries.size===1)return;
      degreeSeries.delete(kind);
    }else degreeSeries.add(kind);
    document.querySelectorAll("[data-degree-series]").forEach(button=>{const active=degreeSeries.has(button.dataset.degreeSeries);button.classList.toggle("active",active);button.setAttribute("aria-pressed",String(active));});
    $("#degree-readout").replaceChildren(element("span",{class:"readout-label"},"EVERY DOT IS A COUNT"),element("p",{},"Hover or focus a visible point to see its exact count and example pages."));
    renderDistribution(distributionScale);
  }));

  function inspectDegree(id){
    const n=byId.get(id);if(!n)return;
    degreeFocus=id;
    $("#degree-character").value=id;
    const difference=n.in_degree-n.out_degree,overlap=nodes.filter(other=>other.in_degree===n.in_degree&&other.out_degree===n.out_degree).length;
    const readout=$("#degree-character-readout");
    readout.replaceChildren(element("h4",{},nameOf(n)));
    const metrics=element("dl",{class:"degree-counts"});
    [["Incoming",n.in_degree],["Outgoing",n.out_degree]].forEach(([label,count])=>{const row=element("div");row.append(element("dt",{},label),element("dd",{},String(count)));metrics.append(row);});
    const message=difference>0?`Receives ${difference} more links than it sends.`:difference<0?`Sends ${-difference} more links than it receives.`:"Receives and sends the same number of links.";
    readout.append(metrics,element("p",{},n.in_degree+n.out_degree===0?"An isolated page: zero incoming and zero outgoing links.":message));
    if(overlap>1)readout.append(element("p",{class:"degree-overlap"},`${overlap} pages share these exact coordinates. Choose a name below to inspect each one.`));
    $("#degree-open-character").setAttribute("aria-label",`Open ${nameOf(n)} on the switchboard`);
    $("#degree-scatter").querySelectorAll("[data-degree-character]").forEach(dot=>{
      const focused=dot.dataset.degreeCharacter===id;dot.classList.toggle("is-focused",focused);dot.setAttribute("tabindex",focused?"0":"-1");
      dot.setAttribute("aria-pressed",String(focused));
      if(focused&&document.activeElement!==dot&&dot.parentNode.lastElementChild!==dot)dot.parentNode.append(dot);
    });
    const plot=$("#degree-scatter svg"),focusDot=[...plot.querySelectorAll("[data-degree-character]")].find(dot=>dot.dataset.degreeCharacter===id);
    plot.querySelectorAll(".portrait-label-focused").forEach(label=>label.remove());
    if(focusDot){
      const mark=focusDot.querySelector(".portrait-dot"),px=Number(mark.getAttribute("cx")),py=Number(mark.getAttribute("cy")),fullName=nameOf(n),text=fullName.length>47?`${fullName.slice(0,44)}…`:fullName,left=px+text.length*7.3+16>751;
      plot.append(svg("text",{x:px+(left?-12:12),y:py<44?py+20:py-12,"text-anchor":left?"end":"start",class:"portrait-label portrait-label-focused","aria-hidden":"true"},text));
    }
    document.querySelectorAll("[data-degree-spotlight]").forEach(button=>button.setAttribute("aria-pressed",String(button.dataset.degreeSpotlight===id)));
  }

  function focusDegree(id){
    if(!byId.has(id))return;
    const n=byId.get(id);
    if(degreeView==="local"&&(n.in_degree>20||n.out_degree>20)){
      degreeView="all";activate("[data-degree-view]",document.querySelector('[data-degree-view="all"]'));
    }
    degreeFocus=id;renderDegreeScatter();
    const plotArea=$("#degree-scatter"),mark=plotArea.querySelector(".portrait-point.is-focused .portrait-dot");
    if(mark&&plotArea.scrollWidth>plotArea.clientWidth){
      const area=plotArea.getBoundingClientRect(),point=mark.getBoundingClientRect();
      if(point.left<area.left||point.right>area.right)plotArea.scrollLeft+=point.left-area.left-(plotArea.clientWidth-point.width)/2;
    }
  }

  function renderDegreeScatter(){
    if(!$("#degree-scatter"))return;
    const shown=nodes.filter(n=>degreeView!=="local"||(n.in_degree<=20&&n.out_degree<=20)),squareRoot=degreeScale==="sqrt";
    const m={l:64,r:29,t:28,b:60},width=780,height=470,w=width-m.l-m.r,h=height-m.t-m.b;
    const maxX=degreeView==="local"?20:Math.ceil(Math.max(...nodes.map(n=>n.out_degree))/10)*10,maxY=degreeView==="local"?20:Math.ceil(Math.max(...nodes.map(n=>n.in_degree))/20)*20;
    const position=(value,max)=>squareRoot?Math.sqrt(value/max):value/max;
    const x=value=>m.l+position(value,maxX)*w,y=value=>m.t+h-position(value,maxY)*h;
    const plot=svg("svg",{viewBox:`0 0 ${width} ${height}`,role:"group","aria-labelledby":"scatter-title scatter-desc","data-axis-scale":degreeScale,"data-degree-scope":degreeView});
    plot.append(svg("title",{id:"scatter-title"},"Every Marvel page: incoming versus outgoing links"),svg("desc",{id:"scatter-desc"},`${shown.length} pages. Horizontal axis: outgoing links. Vertical axis: incoming links. ${squareRoot?"Both axes use square roots; tick labels show the original counts and zero remains visible.":"Both axes are linear."} Click a page to inspect its map. Arrow keys navigate the dots; Enter opens the focused page. Identical degrees share a point; the named selector reaches every page.`));
    const xticks=Array.from({length:maxX/5+1},(_,i)=>i*5),yticks=Array.from({length:maxY/(maxY===20?5:20)+1},(_,i)=>i*(maxY===20?5:20));
    xticks.forEach(value=>plot.append(svg("line",{x1:x(value),x2:x(value),y1:m.t,y2:m.t+h,class:"portrait-grid"}),svg("text",{x:x(value),y:m.t+h+25,"text-anchor":"middle",class:"portrait-tick"},String(value))));
    yticks.forEach(value=>plot.append(svg("line",{x1:m.l,x2:m.l+w,y1:y(value),y2:y(value),class:"portrait-grid"}),svg("text",{x:m.l-12,y:y(value)+4,"text-anchor":"end",class:"portrait-tick"},String(value))));
    const diagonal=Array.from({length:41},(_,i)=>Math.min(maxX,maxY)*i/40).map(value=>`${x(value)},${y(value)}`).join(" ");
    plot.append(svg("polyline",{points:diagonal,fill:"none",class:"portrait-diagonal"}),svg("path",{d:`M${m.l} ${m.t} V${m.t+h} H${m.l+w}`,fill:"none",class:"portrait-axis"}));
    const marks=svg("g",{class:"portrait-marks"});
    [...shown].sort((a,b)=>Number(a.id===degreeFocus)-Number(b.id===degreeFocus)).forEach(n=>{
      const px=x(n.out_degree),py=y(n.in_degree),color=n.in_degree>n.out_degree?"#3158a4":n.in_degree<n.out_degree?"#d65936":"#697e76";
      const dot=svg("g",{"data-degree-character":n.id,"data-in-degree":n.in_degree,"data-out-degree":n.out_degree,class:"portrait-point",role:"button",tabindex:n.id===degreeFocus?0:-1,"aria-label":`${nameOf(n)}: ${n.in_degree} incoming and ${n.out_degree} outgoing links. Open its dossier.`,"aria-pressed":String(n.id===degreeFocus)});
      dot.append(svg("title",{},`${nameOf(n)} · ${n.in_degree} incoming · ${n.out_degree} outgoing`),svg("circle",{cx:px,cy:py,r:9,fill:"transparent"}),svg("circle",{cx:px,cy:py,r:8,fill:"none",class:"portrait-focus-ring"}),svg("circle",{cx:px,cy:py,r:4.2,fill:color,"fill-opacity":.75,stroke:"#fbf9f3","stroke-width":.7,class:"portrait-dot"}));
      dot.addEventListener("pointerenter",()=>inspectDegree(n.id));dot.addEventListener("focus",()=>inspectDegree(n.id));
      dot.addEventListener("click",event=>{resetZoom();select(n.id,true,event.detail===0);});
      dot.addEventListener("keydown",event=>{
        if(event.key==="Enter"||event.key===" "){event.preventDefault();resetZoom();select(n.id,true,true);return;}
        if(!["ArrowLeft","ArrowRight","ArrowUp","ArrowDown"].includes(event.key))return;
        event.preventDefault();
        const horizontal=event.key==="ArrowLeft"||event.key==="ArrowRight",sign=event.key==="ArrowLeft"||event.key==="ArrowUp"?-1:1;
        const candidates=shown.map(other=>{const dx=x(other.out_degree)-px,dy=y(other.in_degree)-py,axis=horizontal?dx:dy,cross=horizontal?dy:dx;return {other,axis,score:Math.hypot(dx,dy)*(1+Math.abs(cross)/Math.max(Math.abs(axis),1)*2)};}).filter(other=>other.axis*sign>.1).sort((a,b)=>a.score-b.score||a.other.id.localeCompare(b.other.id));
        if(candidates.length){const next=[...marks.querySelectorAll("[data-degree-character]")].find(e=>e.dataset.degreeCharacter===candidates[0].other.id);next?.focus();}
      });
      marks.append(dot);
    });
    plot.append(marks);
    const notable=[...new Set([degreeFocus,ranked[0].id,rankedBy("out_degree")[0].id])].map(id=>byId.get(id)).filter(n=>shown.includes(n)),labelBoxes=[];
    notable.forEach(n=>{
      const px=x(n.out_degree),py=y(n.in_degree),text=nameOf(n),labelWidth=text.length*7.3,left=px+labelWidth+16>width-m.r,tx=px+(left?-12:12),start=left?tx-labelWidth:tx;
      let ty=py-11;
      if(ty<m.t+12)ty=py+20;
      while(labelBoxes.some(box=>start<box.x+box.w&&start+labelWidth>box.x&&ty-14<box.y+box.h&&ty>box.y))ty+=18;
      labelBoxes.push({x:start,y:ty-14,w:labelWidth,h:17});
      plot.append(svg("text",{x:tx,y:ty,"text-anchor":left?"end":"start",class:`portrait-label${n.id===degreeFocus?" portrait-label-focused":""}`,"aria-hidden":"true"},text));
    });
    plot.append(svg("text",{x:m.l+w/2,y:height-10,"text-anchor":"middle",class:"portrait-axis-label"},"OUTGOING LINKS →"),svg("text",{x:17,y:m.t+h/2,transform:`rotate(-90 17 ${m.t+h/2})`,"text-anchor":"middle",class:"portrait-axis-label"},"INCOMING LINKS →"));
    $("#degree-scatter").replaceChildren(plot);
    $("#degree-scatter-caption").textContent=`${degreeView==="local"?`Close-up: ${shown.length} of ${nodes.length} pages have at most 20 incoming and 20 outgoing links; ${nodes.length-shown.length} pages fall outside this view.`:`All ${nodes.length} pages.`} ${squareRoot?"Square-root axes spread the crowded low-degree region without moving zero; tick labels remain original link counts.":"Linear axes show original link counts."} Identical degrees overlap; use the selector to reach every page.`;
    if(!shown.some(n=>n.id===degreeFocus))degreeFocus=shown.find(n=>n.id==="Baymax")?.id||shown[0].id;
    inspectDegree(degreeFocus);
  }

  const characterSelect=$("#degree-character");
  [...nodes].sort((a,b)=>nameOf(a).localeCompare(nameOf(b))).forEach(n=>characterSelect.append(element("option",{value:n.id},nameOf(n))));
  characterSelect.addEventListener("change",()=>focusDegree(characterSelect.value));
  $("#degree-open-character").addEventListener("click",event=>{resetZoom();select(degreeFocus,true,event.detail===0);});
  [[ranked[0],"Most incoming"],[rankedBy("out_degree")[0],"Most outgoing"],[byId.get("Baymax")||nodes.find(n=>!n.in_degree&&!n.out_degree),"Zero links"]].forEach(([n,label])=>{
    if(!n)return;
    const button=element("button",{type:"button","data-degree-spotlight":n.id,"aria-pressed":String(n.id===degreeFocus)},`${label}: ${nameOf(n)}`);
    button.addEventListener("click",()=>focusDegree(n.id));$("#degree-spotlights").append(button);
  });
  document.querySelectorAll("[data-degree-scale]").forEach(button=>button.addEventListener("click",()=>{degreeScale=button.dataset.degreeScale;activate("[data-degree-scale]",button);renderDegreeScatter();}));
  document.querySelectorAll("[data-degree-view]").forEach(button=>button.addEventListener("click",()=>{degreeView=button.dataset.degreeView;activate("[data-degree-view]",button);renderDegreeScatter();}));

  function renderRanking(kind){const top=rankedBy(`${kind}_degree`).slice(0,5),list=element("ol",{class:"rank-list"});top.forEach((n,i)=>{const li=element("li"),b=element("button",{class:"rank-button",type:"button"});b.append(element("span",{class:"rank-number"},String(i+1).padStart(2,"0")),element("span",{class:"rank-name"},nameOf(n)),element("strong",{},String(n[`${kind}_degree`])),element("i",{class:"rank-bar",style:`width:${n[`${kind}_degree`]/top[0][`${kind}_degree`]*100}%`}));b.addEventListener("click",event=>{resetZoom();select(n.id,true,event.detail===0);});li.append(b);list.append(li);});$("#rankings").replaceChildren(list);}
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
  select(selected);renderDistribution("linear");renderRanking("in");removeHubs();
})();
