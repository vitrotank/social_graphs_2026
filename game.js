/* Crossed Wires: selected real links, uniquely solved by local degree targets. */
(() => {
  "use strict";
  const mount = document.getElementById("crossed-wires");
  if (!mount) return;
  const data = window.CROSSTALK_PUZZLES;
  const status = document.getElementById("cw-status");
  if (!data?.puzzles?.length) {
    status.textContent = "The puzzle data could not be loaded. Please reload the page to reconnect.";
    return;
  }

  const puzzles = data.puzzles;
  const select = document.getElementById("cw-select");
  const diagram = document.getElementById("cw-diagram");
  // Crop unused outer space so socket and wire labels stay legible on phones.
  diagram.setAttribute("viewBox", "50 10 460 340");
  const socketList = document.getElementById("cw-sockets");
  const wireList = document.getElementById("cw-wires");
  const progress = document.getElementById("cw-progress");
  const level = document.getElementById("cw-level");
  const assignedLabel = document.getElementById("cw-assigned");
  const checkButton = document.getElementById("cw-check");
  const hintButton = document.getElementById("cw-hint");
  const nextButton = document.getElementById("cw-next");
  const storageKey = "crosstalk-crossed-wires-v1";
  let completed = new Set();
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey) || "[]");
    if (Array.isArray(saved)) completed = new Set(saved.filter(id => puzzles.some(p => p.id === id)));
  } catch (_) { /* Storage is an optional convenience, including in private browsing. */ }

  let index = 0;
  let puzzle;
  let directions = [];
  let solved = false;
  let hints = 0;
  let sockets = [];
  let wires = [];
  let positions = [];
  const svgNS = "http://www.w3.org/2000/svg";
  const letters = "ABCDE";
  const byId = () => new Map(puzzle.nodes.map((node, i) => [node.id, {...node, letter: letters[i]}]));

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function svgElement(tag, attributes) {
    const node = document.createElementNS(svgNS, tag);
    for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
    return node;
  }

  function announce(message, type = "") {
    status.textContent = message;
    status.className = `cw-status${type ? ` cw-status-${type}` : ""}`;
  }

  function updateProgress() {
    progress.textContent = `${completed.size} / ${puzzles.length} connected`;
    for (const [i, option] of Array.from(select.options).entries()) {
      option.textContent = `${String(i + 1).padStart(2, "0")} — ${puzzles[i].title}${completed.has(puzzles[i].id) ? " ✓" : ""}`;
    }
  }

  function currentCounts() {
    const counts = new Map(puzzle.nodes.map(node => [node.id, {incoming: 0, outgoing: 0}]));
    puzzle.edges.forEach((edge, i) => {
      if (directions[i] === null) return;
      const source = directions[i] === 0 ? edge.a : edge.b;
      const target = directions[i] === 0 ? edge.b : edge.a;
      counts.get(source).outgoing += 1;
      counts.get(target).incoming += 1;
    });
    return counts;
  }

  function drawDiagram() {
    diagram.replaceChildren();
    const defs = svgElement("defs", {});
    const marker = svgElement("marker", {id: "cw-arrow", markerWidth: 9, markerHeight: 9, refX: 7, refY: 4.5, orient: "auto", markerUnits: "userSpaceOnUse"});
    marker.append(svgElement("path", {d: "M0 0 L9 4.5 L0 9 Z", fill: "#2849c7"}));
    defs.append(marker);
    diagram.append(defs);
    const records = byId();
    puzzle.edges.forEach((edge, i) => {
      const a = positions[puzzle.nodes.findIndex(n => n.id === edge.a)];
      const b = positions[puzzle.nodes.findIndex(n => n.id === edge.b)];
      const [start, end] = directions[i] === 1 ? [b, a] : [a, b];
      const distance = Math.hypot(end.x - start.x, end.y - start.y);
      const dx = (end.x - start.x) / distance;
      const dy = (end.y - start.y) / distance;
      const path = svgElement("line", {
        x1: start.x + dx * 32, y1: start.y + dy * 32,
        x2: end.x - dx * 34, y2: end.y - dy * 34,
        stroke: directions[i] === null ? "#9d9b94" : "#2849c7",
        "stroke-width": directions[i] === null ? 2 : 3,
        "stroke-linecap": "round",
      });
      if (directions[i] === null) path.setAttribute("stroke-dasharray", "5 7");
      else path.setAttribute("marker-end", "url(#cw-arrow)");
      diagram.append(path);
      // Wire labels sit partway along the line to avoid central intersections.
      const ratio = 0.39 + (i % 3) * 0.09;
      const lx = a.x + (b.x - a.x) * ratio;
      const ly = a.y + (b.y - a.y) * ratio;
      diagram.append(svgElement("circle", {cx: lx, cy: ly, r: 12, fill: "#f6f1e7", stroke: directions[i] === null ? "#c7c5bb" : "#2849c7"}));
      const label = svgElement("text", {x: lx, y: ly + 4, "text-anchor": "middle", class: "cw-svg-wire-label"});
      label.textContent = i + 1;
      diagram.append(label);
    });
    puzzle.nodes.forEach((node, i) => {
      const {x, y} = positions[i];
      diagram.append(svgElement("circle", {cx: x, cy: y, r: 30, fill: "#f6f1e7", stroke: "#232927", "stroke-width": 2}));
      diagram.append(svgElement("circle", {cx: x, cy: y, r: 23, fill: "#2849c7"}));
      const letter = svgElement("text", {x, y: y + 7, "text-anchor": "middle", class: "cw-svg-letter"});
      letter.textContent = records.get(node.id).letter;
      diagram.append(letter);
      const badge = svgElement("text", {x, y: y + 49, "text-anchor": "middle", class: "cw-svg-target"});
      badge.textContent = `IN ${node.in_target} / OUT ${node.out_target}`;
      diagram.append(badge);
    });
  }

  function updateBoard() {
    const counts = currentCounts();
    const names = byId();
    sockets.forEach(({node, card, incoming, outgoing, match}) => {
      const current = counts.get(node.id);
      incoming.textContent = current.incoming;
      outgoing.textContent = current.outgoing;
      const correct = current.incoming === node.in_target && current.outgoing === node.out_target;
      const over = current.incoming > node.in_target || current.outgoing > node.out_target;
      card.classList.toggle("cw-socket-matched", correct);
      card.classList.toggle("cw-socket-over", over);
      match.textContent = correct ? "Matched ✓" : over ? "Over target" : "In progress";
    });
    wires.forEach(({edge, button, arrow, label}, i) => {
      const a = names.get(edge.a), b = names.get(edge.b);
      const assigned = directions[i] !== null;
      arrow.textContent = assigned ? (directions[i] === 0 ? "→" : "←") : "?";
      button.classList.toggle("cw-wire-assigned", assigned);
      button.disabled = solved;
      const source = directions[i] === 1 ? b : a;
      const target = directions[i] === 1 ? a : b;
      label.textContent = assigned ? `${source.name} → ${target.name}` : `${a.name} · ${b.name}`;
      button.setAttribute("aria-label", `Wire ${i + 1}: ${assigned ? `${source.name} points to ${target.name}. Activate to reverse.` : `${a.name} and ${b.name}, unassigned. Activate to point from ${a.name} to ${b.name}.`}`);
    });
    const assigned = directions.filter(value => value !== null).length;
    assignedLabel.textContent = `${assigned} / ${directions.length} wires assigned`;
    mount.classList.toggle("cw-is-solved", solved);
    checkButton.disabled = solved;
    hintButton.disabled = solved;
    drawDiagram();
  }

  function loadBoard(newIndex) {
    index = newIndex;
    puzzle = puzzles[index];
    directions = puzzle.edges.map(() => null);
    solved = false;
    hints = 0;
    select.value = String(index);
    const degree = puzzle.difficulty[0].toUpperCase() + puzzle.difficulty.slice(1);
    level.textContent = `${degree} / ${puzzle.nodes.length} pages / ${puzzle.edges.length} wires`;
    nextButton.firstChild.textContent = index === puzzles.length - 1 ? "First board " : "Next board ";
    socketList.replaceChildren();
    wireList.replaceChildren();
    positions = puzzle.nodes.map((_, i) => {
      const angle = -Math.PI / 2 + i * Math.PI * 2 / puzzle.nodes.length;
      return {x: 280 + Math.cos(angle) * 187, y: 178 + Math.sin(angle) * 126};
    });
    sockets = puzzle.nodes.map((node, i) => {
      const card = element("article", "cw-socket");
      const identity = element("div", "cw-socket-identity");
      identity.append(element("span", "cw-socket-letter", letters[i]), element("h3", "", node.name));
      const counts = element("div", "cw-socket-counts");
      const incoming = element("strong", "", "0");
      const outgoing = element("strong", "", "0");
      const inCount = element("span", "");
      const outCount = element("span", "");
      inCount.append(document.createTextNode("IN "), incoming, document.createTextNode(` / ${node.in_target}`));
      outCount.append(document.createTextNode("OUT "), outgoing, document.createTextNode(` / ${node.out_target}`));
      counts.append(inCount, outCount);
      const match = element("span", "cw-socket-match", "In progress");
      card.append(identity, counts, match);
      socketList.append(card);
      return {node, card, incoming, outgoing, match};
    });
    const names = byId();
    wires = puzzle.edges.map((edge, i) => {
      const button = element("button", "cw-wire");
      button.type = "button";
      button.dataset.edge = i;
      const number = element("span", "cw-wire-number", String(i + 1).padStart(2, "0"));
      const ports = element("span", "cw-wire-ports");
      const arrow = element("span", "cw-wire-direction", "?");
      ports.setAttribute("aria-hidden", "true");
      ports.append(element("span", "", names.get(edge.a).letter), arrow, element("span", "", names.get(edge.b).letter));
      const label = element("span", "cw-wire-label");
      const flip = element("span", "cw-wire-flip", "↔");
      flip.setAttribute("aria-hidden", "true");
      button.append(number, ports, label, flip);
      button.addEventListener("click", () => {
        directions[i] = directions[i] === 0 ? 1 : 0;
        updateBoard();
        const source = names.get(directions[i] === 0 ? edge.a : edge.b);
        const target = names.get(directions[i] === 0 ? edge.b : edge.a);
        const counts = currentCounts();
        announce(`Wire ${i + 1}: ${source.name} → ${target.name}. ${source.name} now has ${counts.get(source.id).outgoing} of ${source.out_target} outgoing; ${target.name} has ${counts.get(target.id).incoming} of ${target.in_target} incoming.`);
      });
      wireList.append(button);
      return {edge, button, arrow, label};
    });
    updateBoard();
    announce(`Board ${index + 1}: ${puzzle.title}. Set the directions to match every IN and OUT target. Counts refer only to this board.`);
  }

  select.replaceChildren(...puzzles.map((puzzle, i) => {
    const option = element("option", "", puzzle.title);
    option.value = String(i);
    return option;
  }));
  select.addEventListener("change", () => loadBoard(Number(select.value)));
  document.getElementById("cw-reset").addEventListener("click", () => loadBoard(index));
  nextButton.addEventListener("click", () => loadBoard((index + 1) % puzzles.length));
  checkButton.addEventListener("click", () => {
    const missing = directions.filter(value => value === null).length;
    if (missing) {
      announce(`${missing} wire${missing === 1 ? " still needs" : "s still need"} a direction. Press the buttons marked with a question mark.`, "notice");
      return;
    }
    const counts = currentCounts();
    const wrong = puzzle.nodes.filter(node => counts.get(node.id).incoming !== node.in_target || counts.get(node.id).outgoing !== node.out_target);
    if (wrong.length) {
      announce(`${wrong.length} sockets have a crossed connection: ${wrong.map(node => node.name).join(", ")}. Try reversing a wire touching one of them.`, "notice");
      return;
    }
    solved = true;
    completed.add(puzzle.id);
    try { localStorage.setItem(storageKey, JSON.stringify([...completed])); } catch (_) { /* Gameplay also works without storage. */ }
    updateProgress();
    updateBoard();
    announce(`Connection restored! Every IN and OUT target matches the real links.${hints ? ` You used ${hints} hint${hints === 1 ? "" : "s"}.` : " All yours, without a hint."}${completed.size === puzzles.length ? " All twelve boards are connected. The switchboard is yours." : " Ready for another tangle?"}`, "success");
    nextButton.focus({preventScroll: true});
  });
  hintButton.addEventListener("click", () => {
    const i = puzzle.edges.findIndex((edge, i) => directions[i] !== (edge.source === edge.a ? 0 : 1));
    if (i < 0) {
      announce("The wires look ready. Press Check connections to test your work.");
      return;
    }
    const edge = puzzle.edges[i];
    directions[i] = edge.source === edge.a ? 0 : 1;
    hints += 1;
    updateBoard();
    const names = byId();
    announce(`Hint: in the snapshot, ${names.get(edge.source).name} links to ${names.get(edge.target).name}. Wire ${i + 1} is now set correctly. Follow that change through the remaining targets.`);
  });
  updateProgress();
  loadBoard(0);
})();
