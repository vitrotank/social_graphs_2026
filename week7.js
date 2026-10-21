/* Frozen nearest-neighbor evidence. No network requests are needed. */
(() => {
  'use strict';
  const data = window.WEEK7_DATA;
  const explorer = document.querySelector('#w7-explorer');
  if (!data?.nearest?.length || !explorer) return;
  const search = document.querySelector('#w7-search');
  const filter = document.querySelector('#w7-distance');
  const results = document.querySelector('#w7-results');
  const count = document.querySelector('#w7-count');
  const detail = document.querySelector('#w7-detail');
  const characters = new Map(data.characters.map(character => [character.node, character]));
  const rows = [...data.nearest].sort((a, b) => a.source_name.localeCompare(b.source_name, 'en') || a.source.localeCompare(b.source, 'en'));
  let selected = null;
  const el = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  const link = (name, url) => {
    const node = el('a', name);
    node.href = url;
    return node;
  };
  const routeLabel = distance => distance === null ? 'No path' : `${distance} ${distance === 1 ? 'step' : 'steps'}`;
  const group = row => row.distance === null ? 'disconnected' : row.distance >= 4 ? '4+' : String(row.distance);

  function sourceCard(source) {
    const card = el('article', undefined, 'w7-source');
    const heading = el('h4');
    heading.append(link(source.name, source.url));
    card.append(heading, el('blockquote', source.text));
    card.append(el('p', `Frozen text · character offsets [${source.start.toLocaleString('en')}, ${source.end.toLocaleString('en')})`, 'w7-offset'));
    const context = el('details');
    context.append(el('summary', 'Read the surrounding text'));
    const paragraph = el('p');
    paragraph.append(el('span', source.before, 'w7-context-fade'), el('strong', source.text), el('span', source.after, 'w7-context-fade'));
    context.append(paragraph);
    card.append(link('Wikipedia article & history ↗', source.url), context);
    return card;
  }

  function show(row) {
    selected = row.source;
    detail.replaceChildren();
    detail.dataset.pairSource = row.source;
    detail.dataset.pairTarget = row.target;
    const heading = el('h3');
    heading.append(link(row.source_name, row.source_url), document.createTextNode(' → '), link(row.target_name, row.target_url));
    const metrics = el('div', undefined, 'w7-case-metrics');
    metrics.append(el('span', `Cosine ${row.similarity.toFixed(3)}`, 'w7-detail-score'), el('span', routeLabel(row.distance), 'w7-detail-distance'));
    const path = el('p', undefined, 'w7-path');
    if (row.distance === null) {
      path.textContent = 'No path between these pages within the frozen 303-page roster.';
    } else {
      path.append(document.createTextNode('One shortest undirected route: '));
      row.path.forEach((entry, index) => {
        const node = typeof entry === 'string' ? characters.get(entry) : entry;
        if (index) path.append(el('span', '→', 'w7-arrow'));
        path.append(link(node.name, node.url));
      });
    }
    const terms = el('ul', undefined, 'w7-terms');
    for (const term of row.terms) {
      const item = el('li', term.term);
      item.append(el('span', `${(term.share * 100).toFixed(1)}%`));
      terms.append(item);
    }
    const passages = el('div', undefined, 'w7-source-grid');
    row.sources.forEach(source => passages.append(sourceCard(source)));
    detail.append(heading, metrics, path, el('p', 'Largest shared-term contributions · percent of this pair’s cosine', 'w7-term-note'), terms, passages);
    results.querySelectorAll('[data-source]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.source === selected)));
  }

  function render() {
    const query = search.value.trim().toLocaleLowerCase('en');
    const visible = rows.filter(row => (filter.value === 'all' || filter.value === group(row)) && (!query || `${row.source_name} ${row.target_name}`.toLocaleLowerCase('en').includes(query)));
    results.replaceChildren();
    count.textContent = `${visible.length} of ${rows.length} choices`;
    const fragment = document.createDocumentFragment();
    for (const row of visible) {
      const tr = el('tr');
      const focal = el('th');
      focal.scope = 'row';
      const button = el('button', undefined, 'w7-neighbor-choice');
      button.type = 'button';
      button.dataset.source = row.source;
      button.setAttribute('aria-pressed', String(row.source === selected));
      button.setAttribute('aria-controls', 'w7-detail');
      button.setAttribute('aria-label', `Inspect ${row.source_name} and ${row.target_name}`);
      button.append(el('span', row.source_name), el('span', `→ ${row.target_name}`, 'w7-neighbor-target'));
      button.addEventListener('click', () => show(row));
      focal.append(button);
      tr.append(focal, el('td', row.similarity.toFixed(3)), el('td', routeLabel(row.distance)));
      fragment.append(tr);
    }
    if (!visible.length) {
      const tr = el('tr');
      const empty = el('td', 'No matching page choices. Try another name or distance.', 'w7-empty');
      empty.colSpan = 3;
      tr.append(empty);
      fragment.append(tr);
      detail.replaceChildren();
      detail.hidden = true;
      selected = null;
      delete detail.dataset.pairSource;
      delete detail.dataset.pairTarget;
    } else {
      detail.hidden = false;
      show(visible.find(row => row.source === selected) || visible[0]);
    }
    results.append(fragment);
    results.querySelectorAll('[data-source]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.source === selected)));
  }

  search.addEventListener('input', render);
  filter.addEventListener('change', render);
  render();
  explorer.hidden = false;
})();
