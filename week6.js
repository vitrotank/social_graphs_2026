/* The computation lives in analyze_week6.py; this view only reads frozen results. */
(function () {
  'use strict';
  const data = window.WEEK6_DATA;
  const explorer = document.getElementById('lookalikes');
  const select = document.getElementById('w6-character');
  if (!data || !explorer || !select) return;
  const rows = new Map(data.rows.map(row => [row.node, row]));
  const panel = document.getElementById('w6-neighbors');
  const comparison = document.getElementById('w6-comparison');

  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  function card(condition, result) {
    const article = element('article', undefined, 'w6-neighbor-card');
    article.dataset.condition = condition;
    article.append(element('p', condition === 'before' ? 'ORIGINAL TF-IDF' : 'TITLE WORDS REMOVED', 'eyebrow'));
    const heading = element('h3');
    const link = element('a', result.name);
    link.href = result.url;
    heading.append(link);
    article.append(heading);
    article.append(element('p', 'Cosine ' + result.similarity.toFixed(3) + ' · ' + (result.linked ? 'Direct Wikipedia link' : 'No direct Wikipedia link'), 'w6-score'));
    article.append(element('p', 'Words contributing most to this match', 'eyebrow'));
    const list = element('ul', undefined, 'w6-terms');
    result.terms.slice(0, 6).forEach(term => {
      const item = element('li');
      item.append(element('span', term.term, 'w6-term'));
      const track = element('span', undefined, 'w6-term-track');
      track.setAttribute('aria-hidden', 'true');
      const bar = element('i');
      bar.style.width = Math.max(0, Math.min(100, 100 * term.share)) + '%';
      track.append(bar);
      item.append(track, element('span', (100 * term.share).toFixed(1) + '%', 'w6-term-share'));
      list.append(item);
    });
    if (!result.terms.length) list.append(element('li', 'No weighted terms in common.'));
    article.append(list);
    return article;
  }

  function render() {
    const row = rows.get(select.value);
    if (!row) return;
    panel.replaceChildren(card('before', row.before), card('after', row.after));
    comparison.textContent = row.name + ': ' + (row.changed ? 'the nearest neighbor changes.' : 'the nearest neighbor stays the same.') +
      ' The original pair’s cosine after removal is ' + row.original_pair_after_similarity.toFixed(3) +
      '. ' + (100 * row.removed_token_fraction).toFixed(1) + '% of this article’s tokens were removed.';
  }

  data.rows.slice().sort((a, b) => a.name.localeCompare(b.name) || a.node.localeCompare(b.node)).forEach(row => {
    const title = row.node.replaceAll('_', ' ');
    const option = element('option', title.includes(row.name) ? title : row.name + ' · ' + title);
    option.value = row.node;
    select.append(option);
  });
  select.value = rows.has('Storm_(Marvel_Comics)') ? 'Storm_(Marvel_Comics)' : data.rows[0].node;
  select.addEventListener('change', render);
  render();
  explorer.hidden = false;
}());
