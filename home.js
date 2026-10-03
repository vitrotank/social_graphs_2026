/* Keep bookmarks to the original one-page Week 1 report useful. */
(() => {
  const reportSections = new Set(["#report", "#atlas", "#degrees", "#islands", "#experiment", "#methods"]);
  if (reportSections.has(window.location.hash)) {
    window.location.replace(`week1/index.html${window.location.hash}`);
  }
})();

/* A small, local exhibit. The complete datasets belong in their own atlases. */
(() => {
  "use strict";
  const data = window.CROSSTALK_COVER;
  const map = document.getElementById("cover-map");
  if (!map || !data) return;

  const NS = "http://www.w3.org/2000/svg";
  const colors = ["#2849c7", "#dc512f", "#486452", "#806489", "#ad792c", "#3b818a", "#92533e", "#767839", "#526575"];
  const media = window.matchMedia("(max-width: 560px)");
  const controls = document.getElementById("cover-groups");
  const person = document.getElementById("cover-person");
  const insight = document.getElementById("cover-person-note");
  const edgeLayer = document.getElementById("cover-edges");
  const nodeLayer = document.getElementById("cover-nodes");
  const labelLayer = document.getElementById("cover-labels");
  let world = "philosophers";
  let selected = null;
  let focusedGroup = "all";
  let focusedNode = null;
  let network;
  let nodes;
  let edges;
  let groups;
  let adjacency;
  let groupColors;
  let positions;

  const number = value => Number(value).toLocaleString("en-US");
  const el = (name, attributes = {}, text) => {
    const element = document.createElementNS(NS, name);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
    if (text !== undefined) element.textContent = text;
    return element;
  };
  const groupName = id => String(network.communityLabels?.[id] || `Group ${Number(id) + 1}`);
  const groupShortName = id => groupName(id).split(/\s*[\/|·]\s*/)[0];
  const color = node => groupColors.get(String(node.community)) || colors[0];
  const shortName = label => ({ "Immanuel Kant": "Kant", "Friedrich Nietzsche": "Nietzsche", "Baruch Spinoza": "Spinoza", "René Descartes": "Descartes", "Ludwig Wittgenstein": "Wittgenstein", "Georg Wilhelm Friedrich Hegel": "Hegel", "John Stuart Mill": "J. S. Mill", "Jean-Paul Sartre": "Sartre", "Arthur Schopenhauer": "Schopenhauer", "Gottfried Wilhelm Leibniz": "Leibniz" }[label] || label);

  function updateDetails() {
    insight.replaceChildren();
    const heading = document.createElement("h3");
    const paragraph = document.createElement("p");
    if (selected) {
      const node = nodes.get(selected);
      heading.textContent = node.label;
      const count = adjacency.get(selected).size;
      const total = document.createElement("strong");
      total.textContent = `${number(node.degree)} neighbors`;
      paragraph.append(total, ` in the full network; ${number(count)} appear in this preview. ${world === "philosophers" ? "Community landmark: " : "Map lane: "}${groupName(node.community)}.`);
    } else if (focusedGroup !== "all") {
      heading.textContent = groupName(focusedGroup);
      const count = [...nodes.values()].filter(node => String(node.community) === focusedGroup).length;
      paragraph.textContent = `${number(count)} selected pages in this group. Their links to other colors stay visible so you can see where groups meet.`;
    } else {
      heading.textContent = "Start with a familiar name.";
      paragraph.textContent = world === "philosophers" ? "Colors show Louvain communities. Choose a dot or a name to trace their connections." : "Colors distinguish the main component, the small island, and isolated pages. Choose a name to trace its links.";
    }
    insight.append(heading, paragraph);
    person.value = selected || "";
    for (const button of controls.querySelectorAll("button")) button.setAttribute("aria-pressed", String(button.dataset.group === focusedGroup && !selected));
  }

  function chooseNode(id) {
    selected = id && nodes.has(String(id)) ? String(id) : null;
    focusedGroup = "all";
    if (selected) focusedNode = selected;
    updateDetails();
    draw();
  }

  function chooseGroup(id) {
    focusedGroup = id;
    selected = null;
    updateDetails();
    draw();
  }

  function draw() {
    const small = media.matches;
    const width = small ? 600 : 900;
    const height = small ? 620 : 530;
    map.setAttribute("viewBox", `0 0 ${width} ${height}`);
    map.querySelector("rect").setAttribute("width", width);
    map.querySelector("rect").setAttribute("height", height);
    const values = [...nodes.values()];
    const left = Math.min(...values.map(node => Number(node.x)));
    const right = Math.max(...values.map(node => Number(node.x)));
    const top = Math.min(...values.map(node => Number(node.y)));
    const bottom = Math.max(...values.map(node => Number(node.y)));
    positions = new Map(values.map(node => [String(node.id), {
      x: 40 + (Number(node.x) - left) / Math.max(.001, right - left) * (width - 80),
      y: 36 + (Number(node.y) - top) / Math.max(.001, bottom - top) * (height - 82)
    }]));
    const neighbors = selected ? adjacency.get(selected) : null;
    const activeNode = node => !selected && focusedGroup === "all" || selected && (String(node.id) === selected || neighbors.has(String(node.id))) || !selected && String(node.community) === focusedGroup;
    edgeLayer.replaceChildren();
    nodeLayer.replaceChildren();
    labelLayer.replaceChildren();

    const edgeFragment = document.createDocumentFragment();
    for (const edge of edges) {
      const source = positions.get(String(edge.source));
      const target = positions.get(String(edge.target));
      const active = selected ? String(edge.source) === selected || String(edge.target) === selected : focusedGroup !== "all" && (String(nodes.get(String(edge.source)).community) === focusedGroup || String(nodes.get(String(edge.target)).community) === focusedGroup);
      const muted = (selected || focusedGroup !== "all") && !active;
      const line = el("line", { x1: source.x, y1: source.y, x2: target.x, y2: target.y, class: `cover-edge${active ? " is-active" : ""}${muted ? " is-muted" : ""}` });
      if (active) line.style.setProperty("--edge-color", selected ? color(nodes.get(selected)) : groupColors.get(focusedGroup));
      edgeFragment.append(line);
    }
    edgeLayer.append(edgeFragment);

    const ranked = [...nodes.values()].sort((a, b) => b.degree - a.degree || a.label.localeCompare(b.label));
    const tabNode = focusedNode && nodes.has(focusedNode) ? focusedNode : String(ranked[0]?.id);
    const nodeFragment = document.createDocumentFragment();
    for (const node of nodes.values()) {
      const id = String(node.id);
      const position = positions.get(id);
      const size = world === "marvel" ? Number(node.strength) : Number(node.degree);
      const radius = Math.min(small ? 12 : 11, 3 + Math.sqrt(size) * .38);
      const group = el("g", { class: `cover-node${activeNode(node) ? "" : " is-muted"}${selected === id ? " is-selected" : ""}`, transform: `translate(${position.x} ${position.y})`, role: "button", tabindex: id === tabNode ? "0" : "-1", "aria-label": `${node.label}, ${number(node.degree)} neighbors. Show their connections.`, "aria-pressed": String(selected === id), "data-node": id });
      group.append(el("title", {}, `${node.label} · ${number(node.degree)} neighbors`));
      group.append(el("circle", { r: Math.max(15, radius + 7), fill: "transparent" }));
      group.append(el("circle", { r: radius + 4, class: "node-halo" }));
      group.append(el("circle", { r: radius, fill: color(node), class: "node-dot" }));
      group.addEventListener("click", () => chooseNode(id));
      group.addEventListener("keydown", event => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          chooseNode(id);
          nodeLayer.querySelector('[tabindex="0"]')?.focus();
        } else if (event.key.startsWith("Arrow")) {
          event.preventDefault();
          const direction = event.key === "ArrowLeft" || event.key === "ArrowUp" ? -1 : 1;
          const next = ranked[(ranked.findIndex(item => String(item.id) === id) + direction + ranked.length) % ranked.length];
          focusedNode = String(next.id);
          group.setAttribute("tabindex", "-1");
          const target = [...nodeLayer.children].find(item => item.dataset.node === focusedNode);
          nodeLayer.querySelector('[tabindex="0"]')?.setAttribute("tabindex", "-1");
          target?.setAttribute("tabindex", "0");
          target?.focus();
        } else if (event.key === "Escape") {
          event.preventDefault();
          chooseNode(null);
          nodeLayer.querySelector('[tabindex="0"]')?.focus();
        }
      });
      nodeFragment.append(group);
    }
    nodeLayer.append(nodeFragment);

    const preferred = world === "philosophers" ? ["Aristotle", "Plato", "Immanuel Kant", "Friedrich Nietzsche", "René Descartes", "Baruch Spinoza", "Socrates", "Ludwig Wittgenstein"] : ["Spider-Man", "Iron Man", "Captain America", "Black Widow", "Hulk", "Thor", "Blue Eagle", "Crimson Dynamo"];
    const candidates = ranked.filter(activeNode).sort((a, b) => {
      const score = node => String(node.id) === selected ? -2 : preferred.includes(node.label) ? preferred.indexOf(node.label) : 50;
      return score(a) - score(b) || b.degree - a.degree;
    });
    const occupied = [];
    let visibleLabels = 0;
    for (const node of candidates) {
      if (visibleLabels >= (small ? 5 : 11)) break;
      const id = String(node.id);
      const position = positions.get(id);
      const text = shortName(node.label);
      const right = position.x > width * .58;
      const fontSize = small ? 25 : 14;
      const estimatedWidth = Math.min(width - 30, text.length * fontSize * .57);
      const x = right ? Math.max(estimatedWidth + 10, position.x - 14) : Math.min(width - estimatedWidth - 10, position.x + 14);
      const y = Math.max(fontSize + 5, position.y - 10);
      const box = { left: right ? x - estimatedWidth : x, right: right ? x : x + estimatedWidth, top: y - fontSize, bottom: y + 5 };
      if (id !== selected && occupied.some(other => box.left < other.right + 7 && box.right > other.left - 7 && box.top < other.bottom + 7 && box.bottom > other.top - 7)) continue;
      const label = el("text", { x, y, "text-anchor": right ? "end" : "start", class: `cover-label${id === selected ? " is-selected" : ""}` }, text);
      labelLayer.append(label);
      occupied.push(box);
      visibleLabels++;
    }
  }

  function setWorld(name) {
    if (!data[name]) return;
    world = name;
    network = data[name];
    selected = null;
    focusedGroup = "all";
    focusedNode = null;
    const labelCounts = new Map();
    for (const node of network.nodes) labelCounts.set(node.label, (labelCounts.get(node.label) || 0) + 1);
    nodes = new Map(network.nodes.map(node => [String(node.id), {
      ...node,
      label: labelCounts.get(node.label) > 1 ? String(node.id).replace(/_/g, " ") : node.label,
    }]));
    edges = network.edges.filter(edge => nodes.has(String(edge.source)) && nodes.has(String(edge.target)));
    adjacency = new Map([...nodes.keys()].map(id => [id, new Set()]));
    groups = new Map();
    for (const node of nodes.values()) groups.set(String(node.community), (groups.get(String(node.community)) || 0) + 1);
    for (const edge of edges) {
      adjacency.get(String(edge.source)).add(String(edge.target));
      adjacency.get(String(edge.target)).add(String(edge.source));
    }
    groupColors = new Map([...groups.keys()].sort((a, b) => Number(a) - Number(b)).map((id, index) => [id, colors[index % colors.length]]));
    controls.replaceChildren();
    const groupButtons = [["all", "All connections"], ...[...groups].sort((a, b) => b[1] - a[1]).slice(0, world === "philosophers" ? 4 : 3).map(([id]) => [id, groupShortName(id)])];
    for (const [id, label] of groupButtons) {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.group = id;
      button.setAttribute("aria-pressed", String(id === "all"));
      button.setAttribute("aria-label", id === "all" ? "Show all connections in the preview" : `Focus ${groupName(id)}`);
      const dot = document.createElement("span");
      dot.className = "cover-group-dot";
      dot.setAttribute("aria-hidden", "true");
      dot.style.setProperty("--group-color", groupColors.get(id) || "#232927");
      button.append(dot, label);
      button.addEventListener("click", () => chooseGroup(id));
      controls.append(button);
    }
    person.replaceChildren();
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = `Choose a ${world === "philosophers" ? "philosopher" : "character"}`;
    person.append(placeholder);
    for (const node of [...nodes.values()].sort((a, b) => a.label.localeCompare(b.label))) {
      const option = document.createElement("option");
      option.value = String(node.id);
      option.textContent = node.label;
      person.append(option);
    }
    document.getElementById("cover-total-nodes").textContent = number(network.fullNodes);
    document.getElementById("cover-total-edges").textContent = number(network.fullEdges);
    document.getElementById("cover-node-unit").textContent = world === "philosophers" ? "philosophers in the core" : "character pages";
    document.getElementById("cover-edge-unit").textContent = world === "philosophers" ? "unique undirected ties" : "directed Wikipedia links";
    document.getElementById("cover-title").textContent = world === "philosophers" ? "Ideas have a social life." : "Every hero needs a connection.";
    document.getElementById("cover-map-title").textContent = `A selected preview of the ${world === "philosophers" ? "philosopher" : "Marvel"} network`;
    document.getElementById("cover-map-desc").textContent = `${network.sampleNote} Colors ${world === "philosophers" ? "show Louvain communities" : "distinguish components"}. Use the named selector to trace links, or focus the map and use arrow keys to move between names, Enter to select, and Escape to reset. Totals describe the full source network.`;
    document.getElementById("cover-sample-note").textContent = `${number(nodes.size)} selected pages / ${number(edges.length)} displayed ties. ${network.sampleNote}`;
    const atlas = document.getElementById("cover-open");
    atlas.href = world === "philosophers" ? "week4/index.html#atlas" : "week1/index.html#atlas";
    const arrow = document.createElement("span");
    arrow.setAttribute("aria-hidden", "true");
    arrow.textContent = "↗";
    atlas.replaceChildren(document.createTextNode("Enter the full atlas "), arrow);
    for (const button of document.querySelectorAll("[data-cover-world]")) button.setAttribute("aria-pressed", String(button.dataset.coverWorld === name));
    map.setAttribute("role", "group");
    updateDetails();
    draw();
  }

  person.addEventListener("change", () => chooseNode(person.value));
  document.getElementById("cover-reset").addEventListener("click", () => chooseGroup("all"));
  for (const button of document.querySelectorAll("[data-cover-world]")) button.addEventListener("click", () => setWorld(button.dataset.coverWorld));
  media.addEventListener("change", () => { if (network) draw(); });
  setWorld(world);
})();
