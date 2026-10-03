/* A frozen graph, three lenses. Every mark and count comes from week4.json. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const data = window.CROSSTALK_WEEK4;
  const graph = data?.explorer;
  const stage = $('w4-map-stage');
  const canvas = $('w4-map');
  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  if (!stage || !canvas) return;
  if (!graph?.nodes?.length || !graph?.edges?.length) {
    stage.dataset.state = 'error';
    const message = 'The philosopher atlas could not load. Reload the page, or download the analysis JSON from the methods section.';
    if ($('w4-search-status')) $('w4-search-status').textContent = message;
    if ($('w4-dossier')) $('w4-dossier').replaceChildren(element('p', message));
    return;
  }
  const context = canvas.getContext('2d');
  if (!context) {
    stage.dataset.state = 'error';
    $('w4-search-status').textContent = 'This browser cannot draw the atlas. The findings and downloadable analysis remain available below.';
    return;
  }
  const colors = ['#e78b56', '#79b7aa', '#ac96d2', '#e0bc67', '#76a5d4', '#ce8c9e', '#b6be83', '#9ab6bb', '#f1e3bb'];
  const color = community => colors[((Number(community) || 0) % colors.length + colors.length) % colors.length];
  const fmt = number => Number(number).toLocaleString('en');
  const percent = fraction => `${(100 * fraction).toFixed(1)}%`;
  const nodes = graph.nodes;
  const byId = new Map(nodes.map((node, index) => [node.id, {...node, index}]));
  const roster = [...byId.values()];
  const edges = graph.edges.map(edge => ({...edge, a: byId.get(edge.source), b: byId.get(edge.target)}))
    .filter(edge => edge.a && edge.b);
  const neighbors = new Map(roster.map(node => [node.id, []]));
  edges.forEach(edge => { neighbors.get(edge.a.id).push(edge); neighbors.get(edge.b.id).push(edge); });
  const comparison = graph.weighted_comparison;
  const backbone = graph.backbone;
  const communityMap = new Map((graph.communities || []).map(row => [Number(row.id), row]));
  const weightedMap = new Map((graph.weighted_communities || []).map(row => [Number(row.id), row]));
  const display = id => byId.get(id)?.label || String(id).replaceAll('_', ' ');
  const communityLabel = (id, weighted = false) => (weighted ? weightedMap : communityMap).get(Number(id))?.label || `Community ${Number(id) + 1}`;
  const communityShort = (id, weighted = false) => communityLabel(id, weighted).split(' · ')[0];
  const state = {lens: 'unweighted', alpha: Number($('w4-alpha')?.value || 0.2), community: 'all', selected: 'Aristotle', neighborhood: false,
    scale: 1, x: 0, y: 0, width: 0, height: 0, hover: null};
  if (!byId.has(state.selected)) state.selected = roster[0].id;
  let visibleNodes = [];
  let visibleEdges = [];
  let eligibleEdges = edges;
  let visibleIds = new Set();
  let retainedIds = new Set();
  let scheduled = false;
  let dragging = null;
  const pointers = new Map();
  let pinch = null;
  let chartCursor;
  let chartLabel;
  const communityOf = node => state.lens === 'weighted' ? node.weighted_community : node.community;
  const keepEdge = (edge, alpha = state.alpha) => alpha >= 1 || edge.alpha < alpha;
  const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function fit() {
    const padding = state.width < 600 ? 24 : 38;
    state.scale = Math.min((state.width - padding * 2) / 1000, (state.height - padding * 2) / 760);
    state.x = (state.width - 1000 * state.scale) / 2;
    state.y = (state.height - 760 * state.scale) / 2;
    requestDraw();
  }
  function resize() {
    const bounds = stage.getBoundingClientRect();
    const width = Math.max(1, bounds.width);
    const height = Math.max(1, bounds.height);
    const previousWidth = state.width;
    const previousHeight = state.height;
    const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
    state.width = width; state.height = height;
    canvas.width = Math.round(width * pixelRatio);
    canvas.height = Math.round(height * pixelRatio);
    canvas.style.width = `${width}px`; canvas.style.height = `${height}px`;
    context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    if (!previousWidth) fit();
    else { state.x += (width - previousWidth) / 2; state.y += (height - previousHeight) / 2; requestDraw(); }
    drawHero();
  }
  function requestDraw() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => { scheduled = false; draw(); });
  }
  const point = node => ({x: state.x + node.x * state.scale, y: state.y + node.y * state.scale});
  const radius = node => Math.min(8, 1.5 + Math.sqrt(node.strength || 1) * 0.28) * Math.max(0.82, Math.min(1.55, state.scale));
  function line(edge) {
    context.moveTo(state.x + edge.a.x * state.scale, state.y + edge.a.y * state.scale);
    context.lineTo(state.x + edge.b.x * state.scale, state.y + edge.b.y * state.scale);
  }
  function draw() {
    context.clearRect(0, 0, state.width, state.height);
    context.fillStyle = '#182a2b'; context.fillRect(0, 0, state.width, state.height);
    const selected = byId.get(state.selected);
    const focusId = state.hover || state.selected;
    context.beginPath();
    visibleEdges.forEach(edge => line(edge));
    context.strokeStyle = state.neighborhood ? 'rgba(163,191,185,.25)' : 'rgba(162,190,184,.10)';
    context.lineWidth = 0.55; context.stroke();
    if (state.lens === 'weighted') {
      context.beginPath();
      visibleEdges.filter(edge => edge.weight > 1).forEach(edge => line(edge));
      context.strokeStyle = 'rgba(232,217,170,.16)'; context.lineWidth = 1.35; context.stroke();
      context.beginPath();
      visibleEdges.filter(edge => edge.weight >= 5).forEach(edge => line(edge));
      context.strokeStyle = 'rgba(232,217,170,.23)'; context.lineWidth = 2; context.stroke();
    }
    // A highlighted connection takes the neighbour's community colour.
    const focusEdges = visibleEdges.filter(edge => edge.a.id === focusId || edge.b.id === focusId);
    focusEdges.forEach(edge => {
      const other = edge.a.id === focusId ? edge.b : edge.a;
      context.beginPath(); line(edge);
      context.strokeStyle = color(communityOf(other));
      context.globalAlpha = state.hover ? 0.7 : 0.53;
      context.lineWidth = state.lens === 'weighted' ? Math.min(4, 0.8 + Math.log2(edge.weight + 1) * 0.55) : 1;
      context.stroke();
    });
    context.globalAlpha = 1;
    const connected = new Set(focusEdges.flatMap(edge => [edge.a.id, edge.b.id]));
    visibleNodes.forEach(node => {
      const pos = point(node);
      if (pos.x < -12 || pos.x > state.width + 12 || pos.y < -12 || pos.y > state.height + 12) return;
      context.beginPath(); context.arc(pos.x, pos.y, radius(node), 0, Math.PI * 2);
      context.fillStyle = color(communityOf(node));
      context.globalAlpha = state.hover && !connected.has(node.id) ? 0.35 : (node.degree > 15 ? 0.91 : 0.72);
      context.fill();
    });
    context.globalAlpha = 1;
    if (selected) {
      const pos = point(selected);
      context.beginPath(); context.arc(pos.x, pos.y, radius(selected) + 5, 0, Math.PI * 2);
      context.strokeStyle = '#fff6df'; context.lineWidth = 1.5; context.stroke();
      if (!visibleIds.has(selected.id)) {
        context.beginPath(); context.arc(pos.x, pos.y, radius(selected), 0, Math.PI * 2);
        context.strokeStyle = color(communityOf(selected)); context.stroke();
      }
    }
    const labelCandidates = visibleNodes.filter(node => node.id !== focusId)
      .sort((a, b) => b.strength - a.strength).slice(0, state.width < 600 ? 4 : 10);
    const focusNode = byId.get(focusId);
    if (focusNode) labelCandidates.unshift(focusNode);
    if (selected && selected.id !== focusId) labelCandidates.push(selected);
    const labelBounds = [];
    labelCandidates.forEach(node => {
      const pos = point(node);
      const isFocus = node.id === focusId || node.id === state.selected;
      context.font = `${isFocus ? '600 ' : ''}${isFocus ? 12 : 10}px system-ui, sans-serif`;
      const width = context.measureText(node.label).width;
      const x = Math.min(state.width - width - 12, Math.max(9, pos.x + radius(node) + 8));
      const y = Math.min(state.height - 12, Math.max(18, pos.y - 5));
      const box = {x: x - 4, y: y - 13, w: width + 8, h: 19};
      if (!isFocus && labelBounds.some(other => box.x < other.x + other.w && box.x + box.w > other.x && box.y < other.y + other.h && box.y + box.h > other.y)) return;
      labelBounds.push(box);
      context.fillStyle = 'rgba(24,42,43,.87)'; context.fillRect(box.x, box.y, box.w, box.h);
      context.fillStyle = isFocus ? '#fff1d3' : '#c4d2cb'; context.fillText(node.label, x, y);
    });
    if (!visibleNodes.length) {
      context.fillStyle = '#e7e1d1'; context.font = '14px system-ui, sans-serif'; context.textAlign = 'center';
      context.fillText('No connected philosophers in this view.', state.width / 2, state.height / 2);
      context.textAlign = 'start';
    }
  }

  function updateView() {
    eligibleEdges = state.lens === 'backbone' ? edges.filter(edge => keepEdge(edge)) : edges;
    retainedIds = new Set(eligibleEdges.flatMap(edge => [edge.a.id, edge.b.id]));
    let allowed = new Set(roster.filter(node => (state.lens !== 'backbone' || retainedIds.has(node.id)) &&
      (state.community === 'all' || String(communityOf(node)) === state.community)).map(node => node.id));
    if (state.neighborhood) {
      const neighborhood = new Set([state.selected]);
      eligibleEdges.forEach(edge => {
        if (edge.a.id === state.selected) neighborhood.add(edge.b.id);
        if (edge.b.id === state.selected) neighborhood.add(edge.a.id);
      });
      allowed = new Set([...allowed].filter(id => neighborhood.has(id)));
    }
    visibleIds = allowed;
    visibleNodes = roster.filter(node => allowed.has(node.id));
    visibleEdges = eligibleEdges.filter(edge => allowed.has(edge.a.id) && allowed.has(edge.b.id));
    $('w4-visible-nodes').textContent = fmt(visibleNodes.length);
    $('w4-visible-edges').textContent = fmt(visibleEdges.length);
    stage.dataset.lens = state.lens; stage.dataset.selectedId = state.selected;
    stage.dataset.visibleNodes = String(visibleNodes.length); stage.dataset.visibleEdges = String(visibleEdges.length);
    stage.dataset.neighborhood = String(state.neighborhood); stage.dataset.alpha = String(state.alpha);
    const notes = {
      unweighted: 'Unweighted communities · size: link strength',
      weighted: 'Weighted communities · same positions',
      backbone: `Backbone α = ${state.alpha.toFixed(2)} · attached nodes counted`
    };
    $('w4-lens-note').textContent = notes[state.lens];
    document.querySelectorAll('[data-w4-lens]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.w4Lens === state.lens)));
    document.querySelectorAll('[data-w4-focus]').forEach(button => button.setAttribute('aria-pressed', String(normalize(button.dataset.w4Focus) === normalize(display(state.selected)))));
    $('w4-neighbors')?.setAttribute('aria-pressed', String(state.neighborhood));
    renderDossier(); requestDraw();
  }
  function populateCommunities() {
    const select = $('w4-community');
    if (!select) return;
    const rows = state.lens === 'weighted' ? graph.weighted_communities : graph.communities;
    const all = element('option', 'All communities'); all.value = 'all';
    select.replaceChildren(all, ...(rows || []).map(row => {
      const option = element('option', `${row.label} (${fmt(row.size)})`); option.value = String(row.id); return option;
    }));
    if (![...select.options].some(option => option.value === state.community)) state.community = 'all';
    select.value = state.community;
  }
  function renderDossier() {
    const target = $('w4-dossier');
    if (!target) return;
    const node = byId.get(state.selected);
    const all = neighbors.get(node.id);
    const current = eligibleEdges.filter(edge => edge.a.id === node.id || edge.b.id === node.id);
    const groups = new Map();
    current.forEach(edge => {
      const other = edge.a.id === node.id ? edge.b : edge.a;
      const group = communityOf(other); groups.set(group, (groups.get(group) || 0) + 1);
    });
    const kick = element('p', 'SELECTED PHILOSOPHER', 'eyebrow');
    const heading = element('h3', node.label);
    const facts = element('dl', undefined, 'w4-dossier-facts');
    [['Neighbours', fmt(node.degree)], ['Link strength', fmt(node.strength)], ['In this lens', `${fmt(current.length)} links`]].forEach(([key, value]) => {
      const pair = element('div'); pair.append(element('dt', key), element('dd', value)); facts.append(pair);
    });
    const membership = element('p', undefined, 'w4-membership');
    membership.append(element('span', 'UNWEIGHTED'), element('strong', communityLabel(node.community)),
      element('span', 'WEIGHTED'), element('strong', communityLabel(node.weighted_community, true)));
    const groupList = element('div', undefined, 'w4-neighbor-groups');
    [...groups].sort((a, b) => b[1] - a[1]).slice(0, 5).forEach(([id, count]) => {
      const row = element('div', undefined, 'w4-neighbor-group');
      const swatch = element('i'); swatch.style.background = color(id); swatch.setAttribute('aria-hidden', 'true');
      row.append(swatch, element('span', communityShort(id, state.lens === 'weighted')), element('b', fmt(count))); groupList.append(row);
    });
    const caption = element('p', current.length ? `${node.label}'s neighbours span ${groups.size} communities in this lens.` : `No links involving ${node.label} survive α = ${state.alpha.toFixed(2)}.`, 'w4-dossier-caption');
    const connected = element('div', undefined, 'w4-dossier-neighbors');
    const ordered = [...current].sort((a, b) => b.weight - a.weight || (b.a.id === node.id ? b.b.degree : b.a.degree) - (a.a.id === node.id ? a.b.degree : a.a.degree)).slice(0, 5);
    ordered.forEach(edge => {
      const other = edge.a.id === node.id ? edge.b : edge.a;
      const button = element('button', `${other.label}${state.lens === 'weighted' ? ` · w ${edge.weight}` : ''}`);
      button.type = 'button'; button.dataset.w4Neighbor = other.id;
      button.addEventListener('click', () => selectNode(other.id)); connected.append(button);
    });
    const link = element('a', 'Read the Wikipedia article ↗', 'w4-wiki-link');
    link.href = `https://en.wikipedia.org/wiki/${encodeURIComponent(node.id)}`; link.target = '_blank'; link.rel = 'noopener noreferrer';
    target.replaceChildren(kick, heading, facts, membership, caption, groupList, connected, link);
    target.dataset.selectedId = node.id;
    target.dataset.degree = String(all.length);
  }
  function selectNode(id, center = true) {
    if (!byId.has(id)) return;
    state.selected = id;
    const selected = byId.get(id);
    if (state.community !== 'all' && String(communityOf(selected)) !== state.community) { state.community = 'all'; if ($('w4-community')) $('w4-community').value = 'all'; }
    if ($('w4-search')) $('w4-search').value = selected.label;
    if ($('w4-search-status')) $('w4-search-status').textContent = `${selected.label} selected. ${fmt(selected.degree)} neighbours in the full graph.`;
    if (center) {
      const pos = point(selected);
      if (pos.x < 50 || pos.x > state.width - 50 || pos.y < 50 || pos.y > state.height - 50) {
        state.x = state.width / 2 - selected.x * state.scale; state.y = state.height / 2 - selected.y * state.scale;
      }
    }
    updateView();
  }
  const normalize = value => String(value).trim().toLocaleLowerCase().replaceAll('_', ' ').replace(/\s+/g, ' ');
  const names = [...roster].sort((a, b) => a.label.localeCompare(b.label));
  $('w4-names')?.replaceChildren(...names.map(node => { const option = element('option'); option.value = node.label; return option; }));
  $('w4-search-form')?.addEventListener('submit', event => {
    event.preventDefault();
    const query = normalize($('w4-search').value);
    const exact = roster.find(node => normalize(node.label) === query || normalize(node.id) === query);
    const matches = query ? roster.filter(node => normalize(node.label).includes(query)) : [];
    const result = exact || (matches.length === 1 ? matches[0] : null);
    if (result) selectNode(result.id);
    else $('w4-search-status').textContent = matches.length > 1 ? `${fmt(matches.length)} names match. Choose a full name from the suggestions.` : 'No philosopher found. Try a full name from the suggestions.';
  });
  document.querySelectorAll('[data-w4-focus]').forEach(button => button.addEventListener('click', () => {
    const node = roster.find(row => normalize(row.label) === normalize(button.dataset.w4Focus));
    if (node) selectNode(node.id);
  }));
  document.querySelectorAll('[data-w4-lens]').forEach(button => button.addEventListener('click', () => {
    state.lens = button.dataset.w4Lens; state.community = 'all'; populateCommunities(); updateView();
  }));
  $('w4-community')?.addEventListener('change', event => { state.community = event.target.value; updateView(); });
  $('w4-neighbors')?.addEventListener('click', () => { state.neighborhood = !state.neighborhood; updateView(); });
  function zoom(factor, x = state.width / 2, y = state.height / 2) {
    const minimum = Math.min(state.width / 1000, state.height / 760) * 0.5;
    const next = Math.max(minimum, Math.min(5, state.scale * factor));
    const ratio = next / state.scale;
    state.x = x - (x - state.x) * ratio; state.y = y - (y - state.y) * ratio; state.scale = next; requestDraw();
  }
  $('w4-zoom-in')?.addEventListener('click', () => zoom(1.3));
  $('w4-zoom-out')?.addEventListener('click', () => zoom(1 / 1.3));
  $('w4-reset')?.addEventListener('click', () => { state.community = 'all'; state.neighborhood = false; populateCommunities(); fit(); updateView(); });
  canvas.tabIndex = 0;
  canvas.style.touchAction = 'pan-y';
  canvas.addEventListener('keydown', event => {
    let handled = true;
    if (event.key === '+' || event.key === '=') zoom(1.25);
    else if (event.key === '-') zoom(0.8);
    else if (event.key === 'ArrowLeft') state.x += 36;
    else if (event.key === 'ArrowRight') state.x -= 36;
    else if (event.key === 'ArrowUp') state.y += 36;
    else if (event.key === 'ArrowDown') state.y -= 36;
    else if (event.key === 'Escape' || event.key === '0') fit();
    else handled = false;
    if (handled) { event.preventDefault(); requestDraw(); }
  });
  function localPoint(event) { const bounds = canvas.getBoundingClientRect(); return {x: event.clientX - bounds.left, y: event.clientY - bounds.top}; }
  canvas.addEventListener('wheel', event => {
    if (document.activeElement !== canvas && !event.ctrlKey && !event.metaKey) return;
    event.preventDefault(); const pos = localPoint(event); zoom(Math.exp(-event.deltaY * 0.002), pos.x, pos.y);
  }, {passive: false});
  function nearest(pos) {
    let found = null; let distance = 12 * 12;
    const candidates = visibleIds.has(state.selected) ? visibleNodes : [...visibleNodes, byId.get(state.selected)];
    candidates.forEach(node => {
      const screen = point(node); const d = (screen.x - pos.x) ** 2 + (screen.y - pos.y) ** 2;
      if (d < Math.max(distance, (radius(node) + 5) ** 2) && (!found || d < distance)) { found = node; distance = d; }
    });
    return found;
  }
  function tooltip(node, pos) {
    const target = $('w4-map-tooltip');
    if (!target) return;
    target.hidden = !node;
    if (!node) return;
    target.textContent = `${node.label} · ${fmt(node.degree)} neighbours`;
    target.style.left = `${Math.max(8, Math.min(state.width - 250, pos.x + 14))}px`;
    target.style.top = `${Math.max(8, Math.min(state.height - 55, pos.y - 38))}px`;
  }
  canvas.addEventListener('pointerdown', event => {
    const pos = localPoint(event);
    pointers.set(event.pointerId, pos);
    if (event.pointerType === 'mouse') {
      canvas.focus({preventScroll: true}); canvas.setPointerCapture(event.pointerId);
      dragging = {id: event.pointerId, x: pos.x, y: pos.y, startX: pos.x, startY: pos.y, moved: false};
    } else {
      // Vertical one-finger movement remains page scrolling. A tap still selects.
      dragging = {id: event.pointerId, x: pos.x, y: pos.y, startX: pos.x, startY: pos.y, moved: false, touch: true};
    }
    if (pointers.size === 2) {
      const pair = [...pointers.values()];
      pinch = {distance: Math.hypot(pair[0].x - pair[1].x, pair[0].y - pair[1].y)};
    }
  });
  canvas.addEventListener('pointermove', event => {
    const pos = localPoint(event);
    if (pointers.has(event.pointerId)) pointers.set(event.pointerId, pos);
    if (pinch && pointers.size === 2) {
      const pair = [...pointers.values()]; const distance = Math.hypot(pair[0].x - pair[1].x, pair[0].y - pair[1].y);
      if (pinch.distance > 0) zoom(distance / pinch.distance, (pair[0].x + pair[1].x) / 2, (pair[0].y + pair[1].y) / 2);
      pinch.distance = distance; if (dragging) dragging.moved = true; return;
    }
    if (dragging?.id === event.pointerId) {
      const dx = pos.x - dragging.startX; const dy = pos.y - dragging.startY;
      if (Math.hypot(dx, dy) > 6) dragging.moved = true;
      if (!dragging.touch || Math.abs(dx) > Math.abs(dy) * 1.35) {
        if (dragging.touch && dragging.moved && !canvas.hasPointerCapture(event.pointerId)) canvas.setPointerCapture(event.pointerId);
        state.x += pos.x - dragging.x; state.y += dragging.touch ? 0 : pos.y - dragging.y; requestDraw();
      }
      dragging.x = pos.x; dragging.y = pos.y; return;
    }
    if (event.pointerType === 'touch') return;
    const node = nearest(pos); const next = node?.id || null;
    if (next !== state.hover) { state.hover = next; requestDraw(); }
    canvas.style.cursor = node ? 'pointer' : 'grab'; tooltip(node, pos);
  });
  function pointerEnd(event) {
    if (dragging?.id === event.pointerId && !dragging.moved && !pinch) {
      const pos = localPoint(event); const node = nearest(pos);
      if (node) selectNode(node.id, false);
    }
    pointers.delete(event.pointerId); if (pointers.size < 2) pinch = null;
    if (dragging?.id === event.pointerId) dragging = null;
  }
  canvas.addEventListener('pointerup', pointerEnd);
  canvas.addEventListener('pointercancel', event => { pointers.delete(event.pointerId); dragging = null; pinch = null; });
  canvas.addEventListener('pointerleave', () => { state.hover = null; tooltip(null); requestDraw(); });

  const svgNS = 'http://www.w3.org/2000/svg';
  function svg(tag, attributes = {}, text) {
    const node = document.createElementNS(svgNS, tag);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function configureSvg(target, width, height, label) {
    target.setAttribute('viewBox', `0 0 ${width} ${height}`); target.setAttribute('role', 'img'); target.setAttribute('aria-label', label);
    target.replaceChildren(svg('title', {}, label));
  }
  function renderFlow() {
    const target = $('w4-flow');
    if (!target || !comparison?.matrix?.length) return;
    configureSvg(target, 1080, 540, 'Community overlap: every ribbon counts philosophers shared between an unweighted and a weighted community.');
    target.dataset.state = 'ready';
    const top = 6;
    const leftRows = [...graph.communities].sort((a, b) => b.size - a.size).slice(0, top);
    const rightRows = [...graph.weighted_communities].sort((a, b) => b.size - a.size).slice(0, top);
    const leftSet = new Set(leftRows.map(row => Number(row.id)));
    const rightSet = new Set(rightRows.map(row => Number(row.id)));
    const leftId = id => leftSet.has(Number(id)) ? String(id) : 'other';
    const rightId = id => rightSet.has(Number(id)) ? String(id) : 'other';
    const matrix = new Map();
    comparison.matrix.forEach(row => { const key = `${leftId(row.from)}|${rightId(row.to)}`; matrix.set(key, (matrix.get(key) || 0) + row.count); });
    function columns(rows) {
      const result = rows.map(row => ({id: String(row.id), label: row.label, size: row.size}));
      const remainder = roster.length - result.reduce((sum, row) => sum + row.size, 0);
      if (remainder) result.push({id: 'other', label: 'Other communities', size: remainder});
      return result;
    }
    const left = columns(leftRows); const right = columns(rightRows);
    const gap = 13; const height = 438; const scale = (height - gap * (Math.max(left.length, right.length) - 1)) / roster.length;
    const position = rows => { let y = 58; return new Map(rows.map(row => { const result = {...row, y, height: row.size * scale, cursor: y}; y += result.height + gap; return [row.id, result]; })); };
    const leftPos = position(left); const rightPos = position(right);
    const flows = svg('g', {'aria-hidden': 'true'});
    left.forEach(a => right.forEach(b => {
      const count = matrix.get(`${a.id}|${b.id}`) || 0;
      if (!count) return;
      const l = leftPos.get(a.id); const r = rightPos.get(b.id); const h = count * scale; const ly = l.cursor; const ry = r.cursor;
      l.cursor += h; r.cursor += h;
      const path = svg('path', {d: `M 290 ${ly} C 475 ${ly}, 605 ${ry}, 790 ${ry} L 790 ${ry + h} C 605 ${ry + h}, 475 ${ly + h}, 290 ${ly + h} Z`,
        fill: a.id === 'other' ? '#a6aca1' : color(a.id), opacity: .32, 'data-w4-overlap': count});
      path.append(svg('title', {}, `${a.label} → ${b.label}: ${fmt(count)} philosophers`)); flows.append(path);
    }));
    target.append(flows);
    const labels = svg('g', {'font-family': 'system-ui, sans-serif', fill: '#273a34'});
    labels.append(svg('text', {x: 272, y: 25, 'text-anchor': 'end', 'font-size': 12, 'font-weight': 700}, 'UNWEIGHTED'),
      svg('text', {x: 810, y: 25, 'font-size': 12, 'font-weight': 700}, 'WEIGHTED'));
    function drawColumn(positions, isRight) {
      positions.forEach(row => {
        const x = isRight ? 790 : 278;
        const mark = svg('rect', {x, y: row.y, width: 12, height: row.height, rx: 2, fill: row.id === 'other' ? '#a6aca1' : color(row.id)});
        mark.append(svg('title', {}, `${row.label}: ${fmt(row.size)} philosophers`)); labels.append(mark);
        const textX = isRight ? 814 : 263;
        const text = svg('text', {x: textX, y: row.y + row.height / 2 - 1, 'text-anchor': isRight ? 'start' : 'end', 'font-size': 16, 'font-weight': 600});
        const name = row.label.split(' · ')[0];
        text.append(svg('tspan', {x: textX}, name.length > 25 ? `${name.slice(0, 22)}…` : name), svg('tspan', {x: textX, dy: 19, 'font-size': 15, 'font-weight': 400, fill: '#657268'}, `${fmt(row.size)} philosophers`));
        text.append(svg('title', {}, row.label)); labels.append(text);
      });
    }
    drawColumn(leftPos, false); drawColumn(rightPos, true); target.append(labels);
  }
  function renderComparison() {
    if (!comparison) return;
    if ($('w4-nmi')) $('w4-nmi').textContent = comparison.nmi.toFixed(3);
    if ($('w4-movers-count')) $('w4-movers-count').textContent = fmt(comparison.mover_count);
    if ($('w4-weighted-count')) $('w4-weighted-count').textContent = fmt(comparison.community_count);
    if ($('w4-weight-note')) $('w4-weight-note').textContent = `Weights count repeated article links, summed in both directions (range 1–${comparison.maximum_weight}). They do not measure intellectual influence or historical agreement. Weighted communities are matched to unweighted communities by maximum overlap before counting movers; NMI compares the full partitions.`;
    $('w4-movers')?.replaceChildren(...comparison.movers.slice(0, 4).map(row => {
      const item = element('li'); const button = element('button', undefined, 'w4-mover'); button.type = 'button'; button.dataset.w4Mover = row.id;
      button.append(element('strong', row.label || display(row.id)), element('span', `${communityShort(row.from)} → ${communityShort(row.to, true)}`));
      button.addEventListener('click', () => {
        state.lens = 'weighted'; state.community = 'all'; populateCommunities(); selectNode(row.id);
        stage.scrollIntoView({behavior: reducedMotion() ? 'instant' : 'smooth', block: 'center'});
      }); item.append(button); return item;
    }));
    renderFlow();
  }
  function componentSummary(alpha) {
    const kept = edges.filter(edge => keepEdge(edge, alpha));
    const parents = roster.map((_, index) => index); const sizes = roster.map(() => 1);
    function find(index) { while (parents[index] !== index) { parents[index] = parents[parents[index]]; index = parents[index]; } return index; }
    let components = roster.length; let giant = 0; const active = new Set();
    kept.forEach(edge => {
      active.add(edge.a.id); active.add(edge.b.id); giant = Math.max(giant, 1);
      let a = find(edge.a.index); let b = find(edge.b.index);
      if (a === b) return;
      if (sizes[a] < sizes[b]) [a, b] = [b, a]; parents[b] = a; sizes[a] += sizes[b]; giant = Math.max(giant, sizes[a]); components--;
    });
    return {alpha, edges: kept.length, giant_nodes: giant, components, nodes: active.size, giant_fraction: giant / roster.length};
  }
  function renderBackboneChart() {
    const target = $('w4-backbone-chart');
    if (!target || !backbone?.curve?.length) return;
    configureSvg(target, 900, 300, 'Size of the largest connected component as the disparity threshold increases. The cursor marks the current alpha.');
    const x = alpha => 70 + alpha * 790; const y = count => 246 - count / roster.length * 201;
    const rows = backbone.curve;
    [0, .25, .5, .75, 1].forEach(fraction => {
      target.append(svg('line', {x1: 70, x2: 860, y1: y(fraction * roster.length), y2: y(fraction * roster.length), stroke: '#d5d8c8', 'stroke-width': 1}),
        svg('text', {x: 55, y: y(fraction * roster.length) + 4, 'text-anchor': 'end', fill: '#677368', 'font-size': 11, 'font-family': 'system-ui, sans-serif'}, `${fraction * 100}%`),
        svg('text', {x: x(fraction), y: 271, 'text-anchor': 'middle', fill: '#677368', 'font-size': 11, 'font-family': 'system-ui, sans-serif'}, fraction.toFixed(2)));
    });
    target.append(svg('text', {x: 70, y: 22, fill: '#273a34', 'font-size': 12, 'font-family': 'system-ui, sans-serif', 'font-weight': 600}, 'PHILOSOPHERS IN THE GIANT COMPONENT'),
      svg('text', {x: 860, y: 291, 'text-anchor': 'end', fill: '#677368', 'font-size': 11, 'font-family': 'system-ui, sans-serif'}, 'α · more permissive →'));
    const points = rows.map(row => `${x(row.alpha)},${y(row.giant_nodes)}`);
    target.append(svg('path', {d: `M ${x(rows[0].alpha)},246 L ${points.join(' L ')} L ${x(rows[rows.length - 1].alpha)},246 Z`, fill: '#79b7aa', opacity: .2}),
      svg('polyline', {points: points.join(' '), fill: 'none', stroke: '#386f60', 'stroke-width': 3, 'stroke-linejoin': 'round'}));
    const half = backbone.breakpoint?.half_giant;
    if (half) {
      const marker = svg('g');
      marker.append(svg('line', {x1: x(half.alpha), x2: x(half.alpha), y1: 43, y2: 246, stroke: '#9da598', 'stroke-width': 1, 'stroke-dasharray': '2 5'}),
        svg('circle', {cx: x(half.alpha), cy: y(half.giant_after_tightening), r: 4, fill: '#273a34'}),
        svg('text', {x: x(half.alpha) + 9, y: y(half.giant_after_tightening) + 24, fill: '#58685b', 'font-size': 10, 'font-family': 'system-ui, sans-serif'}, `Half-giant break: ${half.alpha.toFixed(3)}`));
      marker.append(svg('title', {}, `Tightening alpha through ${half.alpha.toFixed(6)} reduces the giant from ${fmt(half.giant_before_tightening)} to ${fmt(half.giant_after_tightening)} philosophers.`));
      target.append(marker);
    }
    chartCursor = svg('g', {'aria-hidden': 'true'});
    chartCursor.append(svg('line', {x1: 0, x2: 0, y1: 34, y2: 247, stroke: '#cc6d3e', 'stroke-width': 1.5, 'stroke-dasharray': '4 5'}), svg('circle', {cx: 0, cy: 0, r: 5, fill: '#cc6d3e', stroke: '#faf5e7', 'stroke-width': 2}));
    target.append(chartCursor);
    chartLabel = svg('text', {y: 40, fill: '#a94f2b', 'font-size': 12, 'font-weight': 600, 'font-family': 'system-ui, sans-serif'});
    target.append(chartLabel);
    target.dataset.state = 'ready';
  }
  function renderPlates() {
    const target = $('w4-backbone-plates');
    if (!target) return;
    target.replaceChildren(...[0.05, 0.2, 0.5].map(alpha => {
      const summary = backbone?.presets?.find(row => Math.abs(row.alpha - alpha) < 0.00001) || componentSummary(alpha);
      const kept = edges.filter(edge => keepEdge(edge, alpha));
      const active = new Set(kept.flatMap(edge => [edge.a.id, edge.b.id]));
      const card = element('figure', undefined, 'w4-backbone-plate'); card.dataset.alpha = String(alpha);
      const picture = svg('svg', {viewBox: '-35 -25 1070 820', role: 'img', 'aria-label': `Backbone at alpha ${alpha.toFixed(2)}: ${fmt(summary.edges)} lines and ${fmt(summary.giant_nodes)} philosophers in the largest component.`});
      picture.append(svg('title', {}, `α = ${alpha.toFixed(2)} · identical positions across all three maps`), svg('rect', {x: -35, y: -25, width: 1070, height: 820, fill: '#182a2b'}));
      const path = kept.map(edge => `M${edge.a.x.toFixed(1)},${edge.a.y.toFixed(1)}L${edge.b.x.toFixed(1)},${edge.b.y.toFixed(1)}`).join('');
      picture.append(svg('path', {d: path, fill: 'none', stroke: '#90afa4', 'stroke-opacity': .26, 'stroke-width': 1.1}));
      const inactive = roster.filter(node => !active.has(node.id)).map(node => `M${(node.x - 1.6).toFixed(1)},${node.y.toFixed(1)}a1.6,1.6 0 1,0 3.2,0a1.6,1.6 0 1,0 -3.2,0`).join('');
      picture.append(svg('path', {d: inactive, fill: '#9ab6bb', opacity: .18}));
      const groups = new Map();
      roster.filter(node => active.has(node.id)).forEach(node => {
        const r = Math.min(7, 1.8 + Math.sqrt(node.strength) * .25);
        const d = `M${(node.x - r).toFixed(1)},${node.y.toFixed(1)}a${r.toFixed(1)},${r.toFixed(1)} 0 1,0 ${(r * 2).toFixed(1)},0a${r.toFixed(1)},${r.toFixed(1)} 0 1,0 ${(-r * 2).toFixed(1)},0`;
        groups.set(node.community, (groups.get(node.community) || '') + d);
      });
      groups.forEach((d, community) => picture.append(svg('path', {d, fill: color(community), opacity: .8})));
      const caption = element('figcaption'); caption.append(element('strong', `α = ${alpha.toFixed(2)}`), element('span', `${fmt(summary.edges)} lines · giant: ${fmt(summary.giant_nodes)}`));
      const button = element('button', 'Explore this threshold'); button.type = 'button'; button.dataset.w4Alpha = String(alpha); button.addEventListener('click', () => setAlpha(alpha, true)); caption.append(button);
      card.append(picture, caption); return card;
    }));
  }
  function setAlpha(value, activate = false) {
    state.alpha = Math.max(.01, Math.min(1, Number(value)));
    if ($('w4-alpha')) $('w4-alpha').value = state.alpha;
    if ($('w4-alpha-value')) { $('w4-alpha-value').value = `α = ${state.alpha.toFixed(2)}`; $('w4-alpha-value').textContent = `α = ${state.alpha.toFixed(2)}`; }
    const summary = backbone?.curve?.find(row => Math.abs(row.alpha - state.alpha) < .000001) || componentSummary(state.alpha);
    $('w4-backbone-edges').textContent = fmt(summary.edges);
    $('w4-backbone-giant').textContent = fmt(summary.giant_nodes);
    $('w4-backbone-components').textContent = fmt(summary.components);
    $('w4-backbone-chart')?.setAttribute('aria-label', `Largest component at alpha ${state.alpha.toFixed(2)}: ${fmt(summary.giant_nodes)} of ${fmt(roster.length)} philosophers. Components include isolates.`);
    if (chartCursor) {
      const x = 70 + state.alpha * 790;
      chartCursor.setAttribute('transform', `translate(${x},0)`);
      chartCursor.querySelector('circle').setAttribute('cy', 246 - summary.giant_nodes / roster.length * 201);
      chartLabel.setAttribute('x', Math.min(770, x + 10)); chartLabel.textContent = `α ${state.alpha.toFixed(2)}`;
    }
    document.querySelectorAll('[data-w4-alpha]').forEach(button => button.setAttribute('aria-pressed', String(Math.abs(Number(button.dataset.w4Alpha) - state.alpha) < .000001)));
    if (activate) { state.lens = 'backbone'; state.community = 'all'; populateCommunities(); }
    if (state.lens === 'backbone' || activate) updateView();
  }
  $('w4-alpha')?.addEventListener('input', event => setAlpha(event.target.value, true));
  document.querySelectorAll('[data-w4-alpha]').forEach(button => button.addEventListener('click', () => setAlpha(button.dataset.w4Alpha, true)));

  function drawHero() {
    const target = $('w4-hero-map');
    if (!target) return;
    const bounds = target.getBoundingClientRect();
    if (!bounds.width || !bounds.height) return;
    const ctx = target.getContext('2d'); if (!ctx) return;
    const ratio = Math.min(window.devicePixelRatio || 1, 2); target.width = bounds.width * ratio; target.height = bounds.height * ratio;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    const scale = Math.min(bounds.width / 1080, bounds.height / 800);
    const x = (bounds.width - 1000 * scale) / 2; const y = (bounds.height - 760 * scale) / 2;
    ctx.clearRect(0, 0, bounds.width, bounds.height);
    ctx.strokeStyle = 'rgba(107,139,127,.20)'; ctx.lineWidth = .6; ctx.beginPath();
    edges.filter(edge => keepEdge(edge, .5)).forEach(edge => { ctx.moveTo(x + edge.a.x * scale, y + edge.a.y * scale); ctx.lineTo(x + edge.b.x * scale, y + edge.b.y * scale); }); ctx.stroke();
    roster.forEach(node => { ctx.beginPath(); ctx.arc(x + node.x * scale, y + node.y * scale, Math.max(.8, (1.5 + Math.sqrt(node.strength) * .22) * scale), 0, Math.PI * 2); ctx.fillStyle = color(node.community); ctx.globalAlpha = .83; ctx.fill(); });
    ctx.globalAlpha = 1;
    const labelOffsets = {Aristotle: [18, -34], Plato: [-70, -6], Immanuel_Kant: [12, 24], Friedrich_Nietzsche: [22, -24]};
    ['Aristotle', 'Plato', 'Immanuel_Kant', 'Friedrich_Nietzsche'].forEach(id => {
      const node = byId.get(id); if (!node) return;
      const px = x + node.x * scale; const py = y + node.y * scale;
      ctx.font = '11px system-ui, sans-serif'; const width = ctx.measureText(node.label).width;
      const [dx, dy] = labelOffsets[id];
      const lx = Math.max(10, Math.min(bounds.width - width - 18, px + dx));
      const ly = Math.max(20, Math.min(bounds.height - 10, py + dy));
      ctx.strokeStyle = 'rgba(237,227,191,.6)'; ctx.lineWidth = .7;
      ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(lx + width / 2, ly - 4); ctx.stroke();
      ctx.fillStyle = 'rgba(250,247,235,.92)'; ctx.fillRect(lx - 4, ly - 13, width + 8, 18);
      ctx.fillStyle = '#26382f'; ctx.fillText(node.label, lx, ly);
    });
    target.dataset.state = 'ready';
  }
  stage.dataset.state = 'ready';
  populateCommunities(); renderComparison(); renderBackboneChart(); renderPlates(); setAlpha(state.alpha); updateView(); resize();
  if ('ResizeObserver' in window) {
    const observer = new ResizeObserver(resize); observer.observe(stage);
    if ($('w4-hero-map')) observer.observe($('w4-hero-map'));
  } else window.addEventListener('resize', resize);
})();
