/* The B-side: observed-link routes and an official-video radio. No dependencies. */
(() => {
  'use strict';
  const data = window.CROSSTALK_GRUNGE;
  const $ = id => document.getElementById(id);
  const set = (id, value) => { if ($(id)) $(id).textContent = value; };
  const make = (tag, text, className) => {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (className) element.className = className;
    return element;
  };

  if (data) {
    const nodes = new Map(data.nodes.map(node => [node.id, node]));
    const forward = new Map(data.nodes.map(node => [node.id, new Set()]));
    const neighbors = new Map(data.nodes.map(node => [node.id, new Set()]));
    data.edges.forEach(({source, target}) => {
      forward.get(source).add(target);
      neighbors.get(source).add(target);
      neighbors.get(target).add(source);
    });
    set('grunge-node-count', data.summary.nodes);
    set('grunge-edge-count', data.summary.directed_edges);
    set('grunge-component-count', data.summary.components.length);
    const date = data.meta.retrieved_at.slice(0, 10);
    set('grunge-snapshot-date', date);
    $('grunge-snapshot-date').dateTime = date;
    ['grunge-from', 'grunge-to'].forEach(id => {
      data.nodes.forEach(node => {
        const option = make('option', node.label);
        option.value = node.id;
        $(id).append(option);
      });
    });
    $('grunge-from').value = nodes.has('Jerry Cantrell') ? 'Jerry Cantrell' : data.nodes[0].id;
    $('grunge-to').value = nodes.has('Dave Grohl') ? 'Dave Grohl' : data.nodes.at(-1).id;

    function nodeLink(id) {
      const a = make('a', nodes.get(id).label);
      a.href = nodes.get(id).url;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      return a;
    }
    function rank(id, records, metric) {
      records.forEach(node => {
        const li = make('li');
        li.append(nodeLink(node.id), make('strong', metric === 'betweenness' ? node[metric].toFixed(4) : node[metric]));
        $(id).append(li);
      });
    }
    rank('grunge-popular', data.summary.top_in, 'in_degree');
    rank('grunge-bridges', data.summary.top_bridge, 'betweenness');
    const topIn = data.summary.top_in[0];
    const tiedIn = data.nodes.filter(n => n.in_degree === topIn.in_degree).map(n => n.label);
    const bridge = data.summary.top_bridge[0];
    set('grunge-comparison', `${tiedIn.join(' and ')} ${tiedIn.length > 1 ? 'tie' : 'leads'} for incoming links (${topIn.in_degree}). ${bridge.label} has the highest betweenness in this sample (${bridge.betweenness.toFixed(4)}). Small differences can reverse when unobserved links are added: read these as a prompt to investigate, not a verdict on the scene.`);

    function shortestPath(start, end, directed) {
      const graph = directed ? forward : neighbors;
      const previous = new Map([[start, null]]);
      const queue = [start];
      for (let i = 0; i < queue.length; i++) {
        const node = queue[i];
        if (node === end) break;
        [...graph.get(node)].sort().forEach(next => {
          if (!previous.has(next)) { previous.set(next, node); queue.push(next); }
        });
      }
      if (!previous.has(end)) return null;
      const result = [];
      for (let node = end; node !== null; node = previous.get(node)) result.push(node);
      return result.reverse();
    }

    const NS = 'http://www.w3.org/2000/svg';
    const svg = (tag, attributes, text) => {
      const el = document.createElementNS(NS, tag);
      Object.entries(attributes).forEach(([key, value]) => el.setAttribute(key, value));
      if (text !== undefined) el.textContent = text;
      return el;
    };
    const points = new Map();
    const layoutNodes = [...data.nodes].sort((a, b) => a.x - b.x || a.id.localeCompare(b.id));
    layoutNodes.forEach((node, index) => {
      const angle = -Math.PI / 2 + index / data.nodes.length * 2 * Math.PI;
      points.set(node.id, {x:450 + 270 * Math.cos(angle), y:260 + 188 * Math.sin(angle), angle});
    });
    function drawMap(route) {
      const map = $('grunge-map');
      map.querySelectorAll('g').forEach(group => group.remove());
      const links = svg('g', {}), dots = svg('g', {});
      const pathEdges = new Set();
      (route || []).slice(1).forEach((target, index) => pathEdges.add([route[index], target].sort().join('|')));
      const seen = new Set();
      data.edges.forEach(({source, target}) => {
        const key = [source, target].sort().join('|');
        if (seen.has(key)) return;
        seen.add(key);
        const a = points.get(source), b = points.get(target), selected = pathEdges.has(key);
        links.append(svg('line', {x1:a.x, y1:a.y, x2:b.x, y2:b.y, stroke:selected ? '#24251e' : '#b9baab', 'stroke-width':selected ? 4 : 1.2, opacity:selected ? 1 : .6}));
      });
      data.nodes.forEach(node => {
        const point = points.get(node.id), selected = route?.includes(node.id);
        const group = svg('g', {});
        const radius = 7 + Math.sqrt(node.in_degree) * 2;
        group.append(svg('circle', {cx:point.x, cy:point.y, r:radius + (selected ? 4 : 0), fill:selected ? '#d8eb48' : '#22231f', stroke:'#22231f', 'stroke-width':selected ? 3 : 1}));
        group.append(svg('title', {}, `${node.label}: ${node.in_degree} incoming links, ${node.out_degree} outgoing links`));
        const dx = Math.cos(point.angle), dy = Math.sin(point.angle);
        group.append(svg('text', {x:point.x + dx * 23, y:point.y + dy * 25 + 5, 'text-anchor':Math.abs(dx) < .15 ? 'middle' : dx > 0 ? 'start' : 'end', fill:'#22231f', 'font-family':'Arial, sans-serif', 'font-size':15, 'font-weight':selected ? 700 : 400}, node.label));
        dots.append(group);
      });
      map.append(links, dots);
    }
    function updateRoute(event) {
      event?.preventDefault();
      const start = $('grunge-from').value, end = $('grunge-to').value;
      const directed = $('grunge-direction').value === 'directed';
      const route = shortestPath(start, end, directed);
      const result = $('grunge-route-result');
      result.replaceChildren();
      if (!route) {
        result.append(make('p', 'No observed route in this direction.'));
        result.append(make('p', 'Try “In either direction” or choose another musician. Missing excerpt links may hide a route that exists on Wikipedia.'));
      } else {
        const hops = route.length - 1;
        result.append(make('p', hops === 0 ? 'Same musician. Zero hops. The shortest mixtape possible.' : `${hops} ${hops === 1 ? 'hop' : 'hops'} · ${directed ? 'following outgoing links' : 'using links in either direction'} · one shortest chain`));
        const chain = make('ol', undefined, 'grunge-chain');
        route.forEach(id => { const li = make('li'); li.append(nodeLink(id)); chain.append(li); });
        result.append(chain);
      }
      drawMap(route);
    }
    $('grunge-route-form').addEventListener('submit', updateRoute);
    updateRoute();
  } else {
    set('grunge-route-result', 'The frozen graph could not load. Reload the page or inspect the source evidence below.');
    $('grunge-route-form').querySelectorAll('select,button').forEach(control => { control.disabled = true; });
  }

  const stations = [
    {title:'Nirvana — Come As You Are', video:'vabnZ9-ex7o'},
    {title:'Alice In Chains — Would?', video:'Nco_kh8xJDs'},
    {title:'Soundgarden — Black Hole Sun', video:'3mbBbFH9fAg'}
  ];
  let station = Math.floor(Math.random() * stations.length);
  let player = null, apiLoading = false, ready = false, wantsPlay = false, state = -1, timeout;
  function status(text) { set('radio-status', text); }
  function showStation() {
    set('radio-station-label', `STATION ${String(station + 1).padStart(2, '0')} / 03`);
    set('radio-track-name', stations[station].title);
    $('radio-external').href = `https://www.youtube.com/watch?v=${stations[station].video}`;
  }
  function resetVisual() { $('grunge-radio').classList.remove('is-playing'); set('radio-play', '▶ Play radio'); }
  function fail(message) { clearTimeout(timeout); wantsPlay = false; resetVisual(); status(message); }
  function createPlayer() {
    if (player) return;
    $('radio-player-wrap').hidden = false;
    const playerVars = {playsinline:1, controls:1, rel:0};
    if (/^https?:$/.test(location.protocol)) playerVars.origin = location.origin;
    player = new YT.Player('radio-player', {
      host:'https://www.youtube-nocookie.com', width:'100%', height:260,
      videoId:stations[station].video, playerVars,
      events:{
        onReady(event) {
          ready = true; clearTimeout(timeout);
          event.target.getIframe().title = 'Official grunge music video player';
          event.target.setVolume(35);
          if (wantsPlay) { status('Ready. Starting the selected station…'); event.target.loadVideoById(stations[station].video); }
          else status('Ready. Press play to tune in.');
        },
        onStateChange(event) {
          state = event.data;
          $('grunge-radio').classList.toggle('is-playing', state === 1);
          set('radio-play', state === 1 ? 'Ⅱ Pause radio' : '▶ Play radio');
          if (state === 1) { wantsPlay = true; status('Playing · official video on YouTube'); }
          else if (state === 2) { wantsPlay = false; status('Paused. Press play whenever you’re ready.'); }
          else if (state === 3) status('Buffering the station…');
          else if (state === 5 || state === -1) status('Station cued. Press play here or in the video.');
          else if (state === 0) { station = (station + 1) % stations.length; showStation(); player.loadVideoById(stations[station].video); }
        },
        onError() { fail('This video cannot play here. Try the next station or open it on YouTube below.'); },
        onAutoplayBlocked() { fail('Your browser needs another click. Press play in the video below.'); }
      }
    });
  }
  function startRadio() {
    if (ready) {
      if (state === 1) { wantsPlay = false; player.pauseVideo(); }
      else { wantsPlay = true; status('Starting the selected station…'); player.playVideo(); }
      return;
    }
    wantsPlay = true;
    if (apiLoading) { status('Still connecting. If it does not load, use the YouTube link below.'); return; }
    apiLoading = true;
    status('Connecting to YouTube…');
    if (window.YT?.Player) { createPlayer(); return; }
    window.onYouTubeIframeAPIReady = createPlayer;
    const script = document.createElement('script');
    script.src = 'https://www.youtube.com/iframe_api';
    script.onerror = () => { apiLoading = false; script.remove(); fail('The radio could not connect. Check your connection or open the video on YouTube below.'); };
    document.head.append(script);
    timeout = setTimeout(() => { if (!ready) fail('YouTube is taking a while to connect. You can use the official video link below.'); }, 15000);
  }
  function changeStation(delta) {
    station = (station + delta + stations.length) % stations.length;
    showStation();
    resetVisual();
    if (ready) {
      if (wantsPlay) { status('Tuning to the next station…'); player.loadVideoById(stations[station].video); }
      else { player.cueVideoById(stations[station].video); status('Station cued. Press play to tune in.'); }
    } else status(apiLoading ? 'Station selected. Connecting to YouTube…' : 'Ready when you are. Press play to tune in.');
  }
  $('radio-play').addEventListener('click', startRadio);
  $('radio-prev').addEventListener('click', () => changeStation(-1));
  $('radio-next').addEventListener('click', () => changeStation(1));
  showStation();
})();
