/* Issue 03 figures use a compact analysis bundle, independent of the games. */
(() => {
  'use strict';
  const data = window.CROSSTALK_WEEK3_FIGURE;
  const byId = id => document.getElementById(id);
  const explorer = byId('w3-story-explorer');
  if (!explorer || !data?.removal) return;
  const removal = data.removal;
  const total = removal.denominator;
  const complete = Number.isInteger(total) && total > 0
    && [removal.degree, removal.betweenness, removal.random].every(rows => Array.isArray(rows) && rows.length === total + 1)
    && removal.random.every(row => Number.isFinite(row.mean));
  if (!complete) return; // The published SVG remains readable if the data fails.

  const namespace = 'http://www.w3.org/2000/svg';
  const colors = {degree:'#2849c7', betweenness:'#c74929', random:'#607478'};
  const svg = byId('w3-story-removal-svg');
  const chart = byId('w3-story-chart');
  const slider = byId('w3-story-removal');
  const count = byId('w3-story-count');
  const reset = byId('w3-story-reset');
  const presets = [...document.querySelectorAll('[data-w3-budget]')];
  let budget = Math.min(30, total);
  let inspection = budget;
  let geometry;
  let cursor;
  const dots = {};
  const bandAvailable = removal.random.every(row => Number.isFinite(row.p05) && Number.isFinite(row.p95));
  const clamp = value => Math.max(0, Math.min(total, Math.round(value)));
  const percent = value => `${(100 * value / total).toFixed(1)}%`;
  const rounded = value => Number(value.toFixed(1)).toLocaleString('en-US', {maximumFractionDigits:1});
  function svgNode(tag, attributes = {}, content) {
    const element = document.createElementNS(namespace, tag);
    Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
    if (content !== undefined) element.textContent = content;
    return element;
  }
  function textLabel(x, y, content, attributes = {}) {
    return svgNode('text', {x, y, fill:'#535c61', 'font-family':'ui-monospace, monospace', 'font-size':11, ...attributes}, content);
  }
  function trajectory(values, x, y) {
    return values.map((value, index) => `${index ? 'L' : 'M'}${x(index).toFixed(2)},${y(value).toFixed(2)}`).join(' ');
  }
  function renderPlot() {
    const width = Math.max(280, chart.clientWidth || 860);
    const height = Math.max(280, Math.min(440, width * .54));
    const margin = {left:42, right:20, top:35, bottom:47};
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const x = removed => margin.left + plotWidth * removed / total;
    const y = size => margin.top + plotHeight * (1 - size / total);
    geometry = {width, height, x, y, margin, plotWidth, plotHeight};
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.replaceChildren();
    svg.append(svgNode('rect', {x:margin.left, y:margin.top, width:plotWidth, height:plotHeight, fill:'#fffdf7'}));
    const yTicks = width < 430 ? [0,100,200,300] : [0,50,100,150,200,250,300];
    yTicks.filter(value => value <= total).forEach(value => {
      svg.append(svgNode('line', {x1:margin.left, x2:width - margin.right, y1:y(value), y2:y(value), stroke:'#d5d0c5', 'stroke-width':1, 'stroke-dasharray':value ? '3 5' : 'none'}));
      svg.append(textLabel(margin.left - 10, y(value) + 4, value, {'text-anchor':'end'}));
    });
    const xTicks = width < 430 ? [0,100,200,total] : [0,60,120,180,240,total];
    [...new Set(xTicks.filter(value => value <= total))].forEach(value => {
      svg.append(svgNode('line', {x1:x(value), x2:x(value), y1:y(0), y2:y(0) + 5, stroke:'#a1a7a8'}));
      svg.append(textLabel(x(value), y(0) + 21, value, {'text-anchor':'middle'}));
    });
    svg.append(textLabel(margin.left + plotWidth / 2, height - 3, 'PAGES REMOVED', {'text-anchor':'middle', 'font-size':10, 'letter-spacing':'.05em'}));
    if (bandAvailable) {
      const upper = removal.random.map((row, index) => [x(index), y(row.p95)]);
      const lower = removal.random.map((row, index) => [x(index), y(row.p05)]).reverse();
      svg.append(svgNode('path', {d:[...upper, ...lower].map(([px,py], index) => `${index ? 'L' : 'M'}${px.toFixed(2)},${py.toFixed(2)}`).join(' ') + 'Z', fill:'#607478', 'fill-opacity':'.16'}));
    }
    ['random','betweenness','degree'].forEach(key => {
      const values = key === 'random' ? removal.random.map(row => row.mean) : removal[key];
      svg.append(svgNode('path', {d:trajectory(values, x, y), fill:'none', stroke:colors[key], 'stroke-width':key === 'random' ? 2 : 2.7, 'stroke-linejoin':'round', 'stroke-linecap':'round', ...(key === 'random' ? {'stroke-dasharray':'6 5'} : {})}));
    });
    cursor = svgNode('g');
    cursor.append(svgNode('line', {y1:margin.top, y2:y(0), stroke:'#172a48', 'stroke-width':1, 'stroke-dasharray':'3 4'}));
    cursor.append(svgNode('rect', {x:-20, y:4, width:40, height:24, rx:3, fill:'#172a48'}));
    cursor.append(textLabel(0,21,inspection, {'text-anchor':'middle', fill:'#f6f1e7', 'font-size':12}));
    svg.append(cursor);
    ['random','betweenness','degree'].forEach(key => {
      dots[key] = svgNode('circle', {r:4.5, fill:colors[key], stroke:'#fffdf7', 'stroke-width':2});
      svg.append(dots[key]);
    });
    updateValues(inspection);
  }
  function updateValues(removed, announce = false) {
    inspection = clamp(removed);
    const random = removal.random[inspection];
    const values = {degree:removal.degree[inspection], betweenness:removal.betweenness[inspection], random:random.mean};
    Object.entries(values).forEach(([key, value]) => {
      byId(`w3-story-${key}`).textContent = key === 'random' ? value.toFixed(1) : value;
      byId(`w3-story-${key}-share`).textContent = `${percent(value)} of the original roster`;
      if (geometry && dots[key]) {
        dots[key].setAttribute('cx', geometry.x(inspection));
        dots[key].setAttribute('cy', geometry.y(value));
      }
    });
    byId('w3-story-band').textContent = `${removal.trials}-trial mean${bandAvailable ? ` · 5–95% band: ${rounded(random.p05)}–${rounded(random.p95)} pages` : ''}`;
    const preview = inspection !== budget;
    byId('w3-story-inspection').textContent = preview
      ? `Inspecting ${inspection} removals · budget is ${budget}.`
      : `Reading ${inspection} ${inspection === 1 ? 'removal' : 'removals'}.`;
    reset.hidden = !preview;
    chart.setAttribute('aria-valuenow', inspection);
    const description = `${inspection} pages removed. Degree first: ${values.degree} pages in the largest group. Betweenness first: ${values.betweenness}. Random failure: ${random.mean.toFixed(1)} on average.`;
    chart.setAttribute('aria-valuetext', description);
    let takeaway;
    if (inspection === 0) {
      takeaway = `${values.degree} of ${total} pages start in the mainland. The other ${total - values.degree} already belong to smaller components or stand alone.`;
    } else if (inspection === total) {
      takeaway = 'Every page has disappeared. All three trajectories end at zero.';
    } else {
      const better = values.degree <= values.betweenness ? 'degree' : 'betweenness';
      const gap = random.mean - values[better];
      const targeted = values.degree === values.betweenness ? 'both targeted orders leave' : `${better} targeting leaves`;
      takeaway = gap >= 0
        ? `At ${inspection} ${inspection === 1 ? 'removal' : 'removals'}, ${targeted} ${rounded(gap)} fewer pages in the largest connected group than random failure, on average.`
        : `At ${inspection} ${inspection === 1 ? 'removal' : 'removals'}, ${targeted} ${rounded(-gap)} more pages in the largest connected group than random failure, on average.`;
    }
    byId('w3-story-takeaway').textContent = takeaway;
    if (cursor && geometry) {
      cursor.setAttribute('transform', `translate(${geometry.x(inspection)},0)`);
      cursor.lastChild.textContent = inspection;
    }
    if (announce) byId('w3-story-announcement').textContent = description;
  }
  function setBudget(value, announce = false) {
    budget = clamp(value);
    slider.value = budget;
    count.replaceChildren(document.createTextNode(`${budget} `));
    const denominator = document.createElement('small');
    denominator.textContent = `/ ${total}`;
    count.append(denominator);
    presets.forEach(button => button.setAttribute('aria-pressed', Number(button.dataset.w3Budget) === budget ? 'true' : 'false'));
    updateValues(budget, announce);
  }
  slider.max = total;
  chart.setAttribute('aria-valuemax', total);
  slider.addEventListener('input', () => setBudget(Number(slider.value)));
  slider.addEventListener('change', () => setBudget(Number(slider.value), true));
  presets.forEach(button => button.addEventListener('click', () => setBudget(Number(button.dataset.w3Budget), true)));
  reset.addEventListener('click', () => { updateValues(budget, true); chart.focus(); });
  function positionFromEvent(event) {
    const bounds = chart.getBoundingClientRect();
    const localX = (event.clientX - bounds.left) * geometry.width / bounds.width;
    return clamp((localX - geometry.margin.left) / geometry.plotWidth * total);
  }
  const tapTolerance = 10;
  let touchGesture = null;
  function movedBeyondTap(event, gesture) {
    return Math.hypot(event.clientX - gesture.x, event.clientY - gesture.y) > tapTolerance;
  }
  chart.addEventListener('pointermove', event => {
    if (event.pointerType === 'touch') {
      if (touchGesture?.id === event.pointerId && movedBeyondTap(event, touchGesture)) touchGesture.moved = true;
      return;
    }
    updateValues(positionFromEvent(event));
  });
  chart.addEventListener('pointerleave', () => updateValues(budget));
  chart.addEventListener('pointerdown', event => {
    // Leave vertical scrolling to the browser; only a completed tap sets a budget.
    if (event.pointerType === 'touch') {
      if (!event.isPrimary || touchGesture) {
        touchGesture = null;
        return;
      }
      touchGesture = {id:event.pointerId, x:event.clientX, y:event.clientY, moved:false};
      return;
    }
    setBudget(positionFromEvent(event), true);
    chart.focus();
  });
  chart.addEventListener('pointerup', event => {
    if (event.pointerType !== 'touch' || touchGesture?.id !== event.pointerId) return;
    const gesture = touchGesture;
    touchGesture = null;
    if (!gesture.moved && !movedBeyondTap(event, gesture)) setBudget(positionFromEvent(event), true);
  });
  chart.addEventListener('pointercancel', event => {
    if (touchGesture?.id === event.pointerId) touchGesture = null;
  });
  chart.addEventListener('keydown', event => {
    let next;
    const step = event.shiftKey ? 10 : 1;
    if (event.key === 'ArrowRight' || event.key === 'ArrowUp') next = inspection + step;
    else if (event.key === 'ArrowLeft' || event.key === 'ArrowDown') next = inspection - step;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = total;
    else if (event.key === 'Escape') {
      event.preventDefault();
      updateValues(budget, true);
      return;
    } else return;
    event.preventDefault();
    setBudget(next, true);
  });
  explorer.hidden = false;
  byId('w3-story-static').hidden = true;
  setBudget(budget);
  renderPlot();
  if ('ResizeObserver' in window) new ResizeObserver(() => renderPlot()).observe(chart);
  else window.addEventListener('resize', renderPlot);

  // A compact slope chart makes the rank gap visible without loading graph data.
  if (!Array.isArray(data.ranking) || !data.ranking.length) return;
  const ranks = data.ranking;
  const rankSvg = byId('w3-story-rank-chart');
  const rankNames = byId('w3-story-rank-names');
  const rankMax = Math.max(8, ...ranks.map(row => row.degree_rank), ...ranks.map(row => row.betweenness_rank));
  let selected = ranks.find(row => row.id === 'Black_Widow_(Natasha_Romanova)') || ranks[0];
  const shortName = row => row.name.replace(/\s*\([^)]*\)\s*/g, '').trim();
  function renderRanks() {
    rankSvg.replaceChildren(svgNode('title', {id:'w3-story-rank-title'}, 'Degree rank compared with betweenness rank'),
      svgNode('desc', {id:'w3-story-rank-desc'}, ranks.map(row => `${row.name}: degree rank ${row.degree_rank}, betweenness rank ${row.betweenness_rank}.`).join(' ')));
    const y = rank => 48 + (rank - 1) * 212 / (rankMax - 1);
    rankSvg.append(textLabel(79,22,'DEGREE', {'text-anchor':'middle', 'font-size':12}),
      textLabel(361,22,'BETWEENNESS', {'text-anchor':'middle', 'font-size':12}));
    [1,5,10,15,20,rankMax].filter((rank,index,array) => rank <= rankMax && array.indexOf(rank) === index).forEach(rank => {
      rankSvg.append(svgNode('line', {x1:79,x2:361,y1:y(rank),y2:y(rank),stroke:'#d5d0c5','stroke-dasharray':'2 5'}));
      rankSvg.append(textLabel(43,y(rank)+4,`#${rank}`, {'text-anchor':'end'}));
    });
    rankSvg.append(svgNode('line', {x1:79,x2:79,y1:y(1),y2:y(rankMax),stroke:'#d5d0c5'}),
      svgNode('line', {x1:361,x2:361,y1:y(1),y2:y(rankMax),stroke:'#d5d0c5'}));
    [...ranks.filter(row => row.id !== selected.id), selected].forEach(row => {
      const active = row.id === selected.id;
      const color = active ? (row.id === 'Black_Widow_(Natasha_Romanova)' ? colors.betweenness : colors.degree) : '#bbc2c8';
      rankSvg.append(svgNode('line', {x1:79,x2:361,y1:y(row.degree_rank),y2:y(row.betweenness_rank),stroke:color,'stroke-width':active ? 3.5 : 1.5}));
      [79,361].forEach((x,index) => rankSvg.append(svgNode('circle', {cx:x,cy:y(index ? row.betweenness_rank : row.degree_rank),r:active ? 6 : 4,fill:color,stroke:'#fffdf7','stroke-width':1.5})));
      if (active) {
        rankSvg.append(textLabel(93,y(row.degree_rank)-9,`#${row.degree_rank}`, {fill:color,'font-size':15,'font-weight':700}));
        rankSvg.append(textLabel(347,y(row.betweenness_rank)-9,`#${row.betweenness_rank}`, {fill:color,'font-size':15,'font-weight':700,'text-anchor':'end'}));
      }
    });
    rankSvg.append(textLabel(220,297,'LOWER NUMBER = HIGHER RANK', {'text-anchor':'middle','font-size':10}));
    const difference = selected.degree_rank - selected.betweenness_rank;
    byId('w3-story-rank-readout').textContent = `${shortName(selected)}: degree #${selected.degree_rank} → betweenness #${selected.betweenness_rank}. ${difference > 0 ? `${difference} places higher on shortest routes.` : difference < 0 ? `${-difference} places lower on shortest routes.` : 'The same position, two different measures.'}`;
    rankNames.querySelectorAll('button').forEach(button => button.setAttribute('aria-pressed', button.dataset.character === selected.id ? 'true' : 'false'));
  }
  ranks.forEach(row => {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = shortName(row);
    button.dataset.character = row.id;
    button.setAttribute('aria-label', `${row.name}, degree rank ${row.degree_rank}, betweenness rank ${row.betweenness_rank}`);
    button.addEventListener('click', () => { selected = row; renderRanks(); });
    rankNames.append(button);
  });
  renderRanks();
  byId('w3-story-ranks').hidden = false;
})();
