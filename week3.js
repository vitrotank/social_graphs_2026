/* Offline operator's desk. All numbers and routes come from the frozen analysis. */
(() => {
  'use strict';
  const data = window.CROSSTALK_WEEK3;
  const network = window.CROSSTALK_DATA?.network;
  if (!data || !network) {
    const target = document.getElementById('w3-route-result');
    if (target) target.textContent = 'The directory could not be loaded. Reload this page, or download the results JSON below to read the routes.';
    return;
  }
  const byId = new Map(network.nodes.map(node => [node.id, node]));
  const removals = new Map(data.single_removal.map(row => [row.id, row]));
  const edgeKeys = new Set(network.edges.map(edge => JSON.stringify([edge.source, edge.target])));
  const originalGiant = data.component_sizes[0];
  const names = [...network.nodes].sort((a, b) => a.name.localeCompare(b.name));
  const $ = id => document.getElementById(id);
  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  const display = id => byId.get(id)?.label || id.replaceAll('_', ' ');
  function pageLink(id) {
    const node = byId.get(id);
    const link = element('a', display(id));
    link.href = node.url;
    link.title = `${node.name} on Wikipedia`;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    return link;
  }
  const percent = value => `${(100 * value / data.nodes).toFixed(1)}%`;
  const noun = (count, singular, plural = `${singular}s`) => count === 1 ? singular : plural;

  // A deliberate disconnect button lets visitors inspect the selection first.
  const removeSelect = $('w3-remove-character');
  removeSelect.replaceChildren(...names.map(node => {
    const option = element('option', node.name);
    option.value = node.id;
    return option;
  }));
  removeSelect.value = 'Black_Widow_(Natasha_Romanova)';
  function removalResult(id = null) {
    const result = $('w3-removal-result');
    const row = id ? removals.get(id) : null;
    const size = row ? row.largest_component : originalGiant;
    const status = element('p', row ? `${display(id).toUpperCase()} DISCONNECTED` : 'ALL ORIGINAL LINES CONNECTED', 'w3-console-status');
    const count = element('p', `${size} `, 'w3-giant-number');
    count.append(element('span', `/ ${data.nodes} original pages`));
    const bar = element('div', undefined, 'w3-signal-track');
    bar.setAttribute('aria-hidden', 'true');
    const fill = element('i');
    fill.style.width = percent(size);
    bar.append(fill);
    const note = row
      ? `${row.detached_from_original_giant} surviving ${noun(row.detached_from_original_giant, 'page')} detached from the original giant; the deleted character is not counted. ${row.component_count} components remain across the full roster.`
      : `${data.nodes - originalGiant} pages already sit outside the giant: a nine-page island and 17 isolates.`;
    result.replaceChildren(status, count, element('p', 'in the largest component'), bar, element('p', note));
    if (row?.detached_ids.length) {
      const list = element('ul', undefined, 'w3-detached-list');
      list.setAttribute('aria-label', 'Pages detached from the original giant');
      row.detached_ids.forEach(node => {
        const item = element('li');
        item.append(pageLink(node));
        list.append(item);
      });
      result.append(list);
    }
    if (row) result.append(element('p', `Original degree rank #${row.degree_rank} · betweenness rank #${row.betweenness_rank}. Each uses all 303 pages; ties break by page ID.`));
  }
  $('w3-disconnect').addEventListener('click', () => removalResult(removeSelect.value));
  $('w3-reconnect').addEventListener('click', () => removalResult());

  function updateDial() {
    const removed = Number($('w3-removal-count').value);
    $('w3-count-label').value = `${removed} of ${data.nodes}`;
    $('w3-chart-cursor').style.left = `${9.2 + 83.2 * removed / data.nodes}%`;
    const random = data.removal.random[removed];
    const rows = [
      {title:'Betweenness first', value:data.removal.betweenness[removed], color:'#c74929', note:'Static shortest-path ranking'},
      {title:'Degree first', value:data.removal.degree[removed], color:'#244b93', note:'Static neighbour-count ranking'},
      {title:'Random removal', value:random.mean, color:'#426950', note:`200-trial mean · 5–95% band: ${random.p05}–${random.p95} pages`, mean:true}
    ];
    $('w3-order-results').replaceChildren(...rows.map(row => {
      const card = element('div', undefined, 'w3-order-result');
      card.style.setProperty('--result-color', row.color);
      card.append(element('h4', row.title), element('strong', row.mean ? row.value.toFixed(1) : row.value),
        element('p', `${percent(row.value)} of the original roster in the largest component. ${row.note}.`));
      return card;
    }));
  }
  $('w3-removal-count').addEventListener('input', updateDial);
  updateDial();

  // Use complete article titles in the datalist so namesakes remain selectable.
  $('w3-directory').replaceChildren(...names.map(node => {
    const option = element('option');
    option.value = node.name;
    return option;
  }));
  const normalize = value => value.trim().toLocaleLowerCase().replace(/\s+/g, ' ');
  function resolveCharacter(value) {
    const query = normalize(value);
    const exact = names.find(node => normalize(node.id) === query || normalize(node.name) === query);
    if (exact) return exact.id;
    const labels = names.filter(node => normalize(node.label) === query);
    return labels.length === 1 ? labels[0].id : null;
  }
  function renderRoute() {
    const input = $('w3-route-character');
    const result = $('w3-route-result');
    const id = resolveCharacter(input.value);
    const mode = $('w3-route-mode').value;
    const routes = data.routes[mode];
    const longest = document.querySelector('[data-route-id]');
    longest.dataset.routeId = routes.farthest[0].id;
    longest.title = `${display(routes.farthest[0].id)}: ${routes.maximum_distance} hops in this mode`;
    if (!id) {
      input.setAttribute('aria-invalid', 'true');
      result.replaceChildren(element('h3', 'That name is not in this directory.'), element('p', 'Type a character name and choose its complete article title from the suggestions. There are 303 pages in the frozen roster; other Marvel characters are outside this network.'));
      return;
    }
    input.removeAttribute('aria-invalid');
    input.value = byId.get(id).name;
    const path = routes.paths[id];
    const modeDescription = mode === 'directed' ? 'Following hyperlinks from the selected article' : 'Treating hyperlinks as connections in either direction';
    const scope = element('p', `${modeDescription}. ${routes.reachable} of ${data.nodes} pages can reach Spider-Man; ${routes.unreachable} cannot.`, 'w3-route-meta');
    if (!path) {
      const node = byId.get(id);
      const why = node.degree === 0
        ? `${display(id)} has no links in either direction within this roster. This page is an isolate.`
        : node.component !== byId.get('Spider-Man').component
          ? `${display(id)} belongs to a separate component, with no connection to Spider-Man even if arrows are ignored.`
          : `${display(id)} is in the same weak component as Spider-Man, but no route follows the arrows all the way. Try “Either direction”.`;
      result.replaceChildren(element('h3', 'No connection on this line.'), element('p', why), scope);
      return;
    }
    const hops = path.length - 1;
    const isLongest = hops === routes.maximum_distance;
    result.replaceChildren(element('h3', hops === 0 ? 'You’re already speaking to Spider-Man.' : `${hops} ${noun(hops, 'hop')} to Spider-Man${isLongest ? ' — a longest shortest route.' : '.'}`), scope);
    const chain = element('ol', undefined, 'w3-route-chain');
    chain.setAttribute('aria-label', 'Shortest route to Spider-Man');
    path.forEach((node, index) => {
      const item = element('li');
      const link = pageLink(node);
      link.prepend(element('small', index === 0 ? 'START / 00' : `HOP / ${String(index).padStart(2, '0')}`));
      item.append(link);
      chain.append(item);
    });
    result.append(chain);
    if (isLongest) result.append(element('p', `${routes.farthest.length} pages tie at ${hops} hops in this mode. This is one shortest route; ties between routes break by page ID.`, 'w3-route-meta'));
    if (path.length > 1) {
      const details = element('details', undefined, 'w3-route-edges');
      details.append(element('summary', 'Check the actual direction of each link'));
      const links = element('ul');
      for (let index = 0; index < path.length - 1; index += 1) {
        const from = path[index], to = path[index + 1];
        const forward = edgeKeys.has(JSON.stringify([from, to]));
        const reverse = edgeKeys.has(JSON.stringify([to, from]));
        const text = forward && reverse
          ? `${display(from)} ↔ ${display(to)}: both articles link to each other.`
          : forward ? `${display(from)} → ${display(to)}: follow the hyperlink.`
            : `${display(from)} ← ${display(to)}: this step traverses the hyperlink backwards.`;
        links.append(element('li', text));
      }
      details.append(links);
      result.append(details);
    }
  }
  $('w3-route-form').addEventListener('submit', event => { event.preventDefault(); renderRoute(); });
  $('w3-route-mode').addEventListener('change', renderRoute);
  document.querySelectorAll('[data-route-id]').forEach(button => button.addEventListener('click', () => {
    $('w3-route-character').value = byId.get(button.dataset.routeId).name;
    renderRoute();
  }));
  $('w3-isolate-preset').addEventListener('click', () => {
    $('w3-route-character').value = names.find(node => node.degree === 0).name;
    renderRoute();
  });
  document.querySelectorAll('.w3-main button:disabled, .w3-main input:disabled, .w3-main select:disabled').forEach(control => { control.disabled = false; });
  renderRoute();
})();
