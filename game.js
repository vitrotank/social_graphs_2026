/* Crossed Wires: Python supplies real, uniquely solvable boards and release dates. */
(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const mount = $("crossed-wires");
  if (!mount) return;
  const data = window.CROSSTALK_PUZZLES;
  if (!data?.puzzles?.length || !data?.weeks?.length) {
    $("cw-status").textContent = "The switchboard data could not be loaded. Please reload to reconnect.";
    return;
  }
  const practice = data.puzzles, weeks = data.weeks;
  const storageKey = "crosstalk-crossed-wires-v2";
  const letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ", stageNames = ["Dial in", "Crossed lines", "Blackout"];
  const diagram = $("cw-diagram"), select = $("cw-select"), weekSelect = $("cw-week-select");
  diagram.setAttribute("viewBox", "0 0 600 440");
  let saved = {version: 2, boards: {}, selection: {}};
  try {
    const parsed = JSON.parse(localStorage.getItem(storageKey) || "null");
    if (parsed?.version === 2 && parsed.boards && typeof parsed.boards === "object") {
      saved = {version: 2, boards: parsed.boards, selection: parsed.selection || {}};
    }
    const legacy = JSON.parse(localStorage.getItem("crosstalk-crossed-wires-v1") || "[]");
    if (Array.isArray(legacy)) practice.forEach(board => {
      if (legacy.includes(board.id) && !saved.boards[board.id]) saved.boards[board.id] = {
        directions: board.edges.map(answer), moves: 0, hints: 0, checks: 0, history: [], solved: true, bestStars: 1,
      };
    });
  } catch (_) { /* Storage is optional, including in private browsing. */ }
  const available = () => weeks.filter(item => Date.parse(item.release_at) <= Date.now());
  let mode = saved.selection.mode === "practice" ? "practice" : "weekly";
  let week = available().find(item => item.id === saved.selection.week) || available().at(-1) || null;
  let round = Number.isInteger(saved.selection.round) ? Math.max(0, Math.min(2, saved.selection.round)) : 0;
  let practiceIndex = Number.isInteger(saved.selection.practice) ? Math.max(0, Math.min(practice.length - 1, saved.selection.practice)) : 0;
  let puzzle = null, state = null, sockets = [], wires = [], positions = [], releaseSignature = null;

  function answer(edge) { return edge.source === edge.a ? 0 : 1; }
  function fresh() { return {directions: [], moves: 0, hints: 0, checks: 0, history: [], solved: false, bestStars: 0}; }
  function nonnegative(value) { return Number.isInteger(value) && value >= 0 ? value : 0; }
  function boardState(board) {
    const stored = saved.boards[board.id] || fresh();
    const valid = values => Array.isArray(values) && values.length === board.edges.length && values.every(value => value === null || value === 0 || value === 1);
    const directions = valid(stored.directions) ? stored.directions.slice() : board.edges.map(() => null);
    return {
      directions, moves: nonnegative(stored.moves), hints: nonnegative(stored.hints), checks: nonnegative(stored.checks),
      history: Array.isArray(stored.history) ? stored.history.filter(valid).slice(-80) : [],
      solved: stored.solved === true && directions.every((value, i) => value === answer(board.edges[i])),
      bestStars: Math.min(3, nonnegative(stored.bestStars)),
    };
  }
  function completed(board) { return boardState(board).bestStars > 0; }
  function save() {
    if (puzzle && state) saved.boards[puzzle.id] = state;
    saved.selection = {mode, week: week?.id || null, round, practice: practiceIndex};
    try { localStorage.setItem(storageKey, JSON.stringify(saved)); } catch (_) { /* Gameplay needs no storage. */ }
  }
  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function svgElement(tag, attrs) {
    const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
    return node;
  }
  function announce(message, type = "") {
    $("cw-status").textContent = message;
    $("cw-status").className = `cw-status${type ? ` cw-status-${type}` : ""}`;
  }
  function nameMap() { return new Map(puzzle.nodes.map((node, i) => [node.id, {...node, letter: letters[i]}])); }
  function counts() {
    const result = new Map(puzzle.nodes.map(node => [node.id, {incoming: 0, outgoing: 0}]));
    puzzle.edges.forEach((edge, i) => {
      if (state.directions[i] === null) return;
      result.get(state.directions[i] === 0 ? edge.a : edge.b).outgoing++;
      result.get(state.directions[i] === 0 ? edge.b : edge.a).incoming++;
    });
    return result;
  }
  function hiddenSocket(node) { return mode === "weekly" && round === 2 && !state.solved && node.id === puzzle.nodes.at(-1).id; }
  function dateLabel(instant) {
    return new Intl.DateTimeFormat("en-GB", {timeZone: data.schedule.timezone, weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZoneName: "short", hour12: false}).format(new Date(instant));
  }
  function renderSchedule() {
    const open = available(), current = open.at(-1);
    const next = weeks.find(item => Date.parse(item.release_at) > Date.now());
    const displayed = mode === "weekly" && week ? week : current;
    $("cw-release-title").textContent = displayed ? `Shift ${String(displayed.number).padStart(2, "0")} · ${displayed.title}` : "Your first night shift is on its way.";
    $("cw-release-detail").textContent = `${current && displayed !== current ? `Shift ${String(current.number).padStart(2, "0")} is now open. Choose “The weekly shift” to start it. ` : "Three rounds. One repaired switchboard. "}Fresh challenges every Wednesday at ${String(data.schedule.release_hour).padStart(2, "0")}:00, Copenhagen / Paris time.`;
    $("cw-release-time").textContent = next ? dateLabel(next.release_at) : `All ${weeks.length} shifts are open. The archive is yours.`;
    if (next) $("cw-release-time").dateTime = next.release_at;
    else $("cw-release-time").removeAttribute("datetime");
    if (next) {
      const seconds = Math.max(0, Math.ceil((Date.parse(next.release_at) - Date.now()) / 1000));
      $("cw-countdown").textContent = `${Math.floor(seconds / 86400)}d ${String(Math.floor(seconds % 86400 / 3600)).padStart(2, "0")}h ${String(Math.floor(seconds % 3600 / 60)).padStart(2, "0")}m ${String(seconds % 60).padStart(2, "0")}s`;
    } else $("cw-countdown").textContent = "Season complete";
    const signature = open.map(item => item.id).join();
    if (signature !== releaseSignature || !weekSelect.options.length) {
      releaseSignature = signature;
      weekSelect.replaceChildren(...weeks.map(item => {
        const unlocked = open.includes(item);
        const option = element("option", "", `${String(item.number).padStart(2, "0")} · ${item.title}${unlocked ? "" : ` · opens ${dateLabel(item.release_at)}`}`);
        option.value = item.id; option.disabled = !unlocked;
        return option;
      }));
      weekSelect.disabled = !open.length;
      if (!week && current) { week = current; round = 0; if (mode === "weekly") loadBoard(); }
      weekSelect.value = week?.id || "";
    }
  }
  function renderNavigation() {
    const focusedRound = document.activeElement.closest?.(".cw-round")?.dataset.round;
    $("cw-weekly").setAttribute("aria-pressed", String(mode === "weekly"));
    $("cw-practice").setAttribute("aria-pressed", String(mode === "practice"));
    $("cw-practice-panel").hidden = mode !== "practice";
    $("cw-week-panel").hidden = mode !== "weekly";
    $("cw-rounds").hidden = mode !== "weekly" || !week;
    weekSelect.value = week?.id || ""; select.value = String(practiceIndex);
    $("cw-rounds").replaceChildren();
    if (week) week.puzzles.forEach((board, i) => {
      const done = completed(board);
      const button = element("button", `cw-round${i === round ? " cw-round-active" : ""}${done ? " cw-round-complete" : ""}`);
      button.type = "button"; button.dataset.round = i;
      button.disabled = i > 0 && !completed(week.puzzles[i - 1]);
      if (i === round) button.setAttribute("aria-current", "step");
      button.append(element("span", "cw-round-number", done ? "✓" : String(i + 1).padStart(2, "0")), element("span", "cw-round-name", stageNames[i]), element("span", "cw-round-note", button.disabled ? "Complete the previous round" : done ? "Repaired · replay anytime" : ["3 pages · find your rhythm", "4 pages · follow the clues", "6 pages · one dark socket"][i]));
      button.addEventListener("click", () => { if (!button.disabled) { save(); round = i; loadBoard(); } });
      $("cw-rounds").append(button);
    });
    practice.forEach((board, i) => { select.options[i].textContent = `${String(i + 1).padStart(2, "0")} · ${board.title}${completed(board) ? " ✓" : ""}`; });
    $("cw-progress").textContent = mode === "practice" ? `${practice.filter(completed).length} / 12 connected` : `${week ? week.puzzles.filter(completed).length : 0} / 3 rounds restored`;
    if (focusedRound !== undefined && mode === "weekly") $("cw-rounds").querySelector(`[data-round="${focusedRound}"]`)?.focus({preventScroll: true});
  }
  function wireLabel(edge, i) {
    const names = nameMap(), direction = state.directions[i];
    const a = names.get(edge.a).name, b = names.get(edge.b).name;
    return `Wire ${i + 1}: ${direction === null ? `${a} and ${b}, unassigned. Activate to connect.` : `${direction === 0 ? a : b} points to ${direction === 0 ? b : a}. Activate to reverse.`}`;
  }
  function drawDiagram() {
    const focused = diagram.contains(document.activeElement) ? document.activeElement.dataset.wire : null;
    diagram.replaceChildren();
    const defs = svgElement("defs", {});
    const marker = svgElement("marker", {id: "cw-arrow", markerWidth: 11, markerHeight: 11, refX: 9, refY: 5.5, orient: "auto", markerUnits: "userSpaceOnUse"});
    marker.append(svgElement("path", {d: "M0 0 L11 5.5 L0 11 Z", fill: "#a8b8ff"}));
    defs.append(marker); diagram.append(defs);
    puzzle.edges.forEach((edge, i) => {
      const a = positions[puzzle.nodes.findIndex(node => node.id === edge.a)], b = positions[puzzle.nodes.findIndex(node => node.id === edge.b)];
      const [start, end] = state.directions[i] === 1 ? [b, a] : [a, b];
      const length = Math.hypot(end.x - start.x, end.y - start.y), dx = (end.x - start.x) / length, dy = (end.y - start.y) / length;
      const geometry = {x1: start.x + dx * 34, y1: start.y + dy * 34, x2: end.x - dx * 37, y2: end.y - dy * 37};
      const group = svgElement("g", {class: "cw-svg-wire", "data-wire": i, role: "button", tabindex: state.solved ? -1 : 0, "aria-label": wireLabel(edge, i), "aria-disabled": String(state.solved)});
      group.append(svgElement("line", {...geometry, stroke: "transparent", "stroke-width": 26, class: "cw-wire-hit"}));
      const assigned = state.directions[i] !== null;
      const line = svgElement("line", {...geometry, class: "cw-cable", stroke: assigned ? "#a8b8ff" : "#8b97ad", "stroke-width": assigned ? 3.5 : 2, "stroke-linecap": "round"});
      if (assigned) line.setAttribute("marker-end", "url(#cw-arrow)"); else line.setAttribute("stroke-dasharray", "5 8");
      group.append(line);
      if (assigned) group.append(svgElement("line", {...geometry, class: "cw-flow", "aria-hidden": "true"}));
      const ratio = .34 + i % 3 * .12, x = a.x + (b.x - a.x) * ratio, y = a.y + (b.y - a.y) * ratio;
      group.append(svgElement("circle", {cx: x, cy: y, r: 17, fill: "#232c44", stroke: "#a8b8ff", "stroke-width": 1.5}));
      const text = svgElement("text", {x, y: y + 5, "text-anchor": "middle", class: "cw-svg-wire-label"});
      text.textContent = i + 1; group.append(text);
      group.addEventListener("click", () => flip(i));
      group.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); flip(i); } });
      diagram.append(group);
    });
    const current = counts();
    puzzle.nodes.forEach((node, i) => {
      const {x, y} = positions[i];
      const matched = !hiddenSocket(node) && current.get(node.id).incoming === node.in_target && current.get(node.id).outgoing === node.out_target;
      diagram.append(svgElement("circle", {cx: x, cy: y, r: 31, fill: "#f6f1e7", stroke: matched ? "#aac8a4" : "#f6f1e7", "stroke-width": matched ? 5 : 2, class: `cw-port${matched ? " cw-port-matched" : ""}`}));
      diagram.append(svgElement("circle", {cx: x, cy: y, r: 25, fill: matched ? "#486452" : "#2849c7"}));
      const letter = svgElement("text", {x, y: y + 8, "text-anchor": "middle", class: "cw-svg-letter"});
      letter.textContent = letters[i]; diagram.append(letter);
      const target = svgElement("text", {x, y: y + 53, "text-anchor": "middle", class: "cw-svg-target"});
      target.textContent = hiddenSocket(node) ? "IN ? / OUT ?" : `IN ${node.in_target} / OUT ${node.out_target}`; diagram.append(target);
    });
    if (focused !== null && !state.solved) diagram.querySelector(`[data-wire="${focused}"]`)?.focus({preventScroll: true});
  }
  function updateBoard() {
    if (!puzzle) return;
    const current = counts(), names = nameMap();
    let matches = 0;
    sockets.forEach(({node, card, incoming, outgoing, inTarget, outTarget, match}) => {
      const value = current.get(node.id), hidden = hiddenSocket(node);
      incoming.textContent = value.incoming; outgoing.textContent = value.outgoing;
      inTarget.textContent = hidden ? "?" : node.in_target; outTarget.textContent = hidden ? "?" : node.out_target;
      const correct = !hidden && value.incoming === node.in_target && value.outgoing === node.out_target;
      const over = !hidden && (value.incoming > node.in_target || value.outgoing > node.out_target);
      if (correct) matches++;
      card.classList.toggle("cw-socket-matched", correct); card.classList.toggle("cw-socket-over", over); card.classList.toggle("cw-socket-blackout", hidden);
      match.textContent = hidden ? "Blackout · infer the targets" : correct ? "Matched ✓" : over ? "Over target" : "Waiting for a signal";
    });
    wires.forEach(({edge, button, arrow, label}, i) => {
      const direction = state.directions[i], assigned = direction !== null, a = names.get(edge.a), b = names.get(edge.b);
      arrow.textContent = assigned ? (direction === 0 ? "→" : "←") : "?";
      button.dataset.direction = assigned ? String(direction) : ""; button.classList.toggle("cw-wire-assigned", assigned); button.disabled = state.solved;
      label.textContent = assigned ? `${direction === 0 ? a.name : b.name} → ${direction === 0 ? b.name : a.name}` : `${a.name} · ${b.name}`;
      button.setAttribute("aria-label", wireLabel(edge, i));
    });
    $("cw-assigned").textContent = `${state.directions.filter(value => value !== null).length} / ${state.directions.length} wires assigned`;
    $("cw-moves").textContent = state.moves; $("cw-hints-used").textContent = state.hints;
    $("cw-matched").textContent = `${matches} / ${puzzle.nodes.length}${mode === "weekly" && round === 2 && !state.solved ? " · 1 dark" : ""}`;
    mount.classList.toggle("cw-is-solved", state.solved);
    $("cw-check").disabled = state.solved; $("cw-hint").disabled = state.solved; $("cw-undo").disabled = state.solved || !state.history.length;
    $("cw-next").disabled = mode === "weekly" && (!state.solved || round === 2);
    $("cw-next").textContent = mode === "practice" ? "Next practice board →" : round === 2 ? (state.solved ? "Shift complete ✓" : "Finish this round") : "Next round →";
    $("cw-receipt").hidden = !state.solved; drawDiagram(); if (state.solved) renderReceipt();
  }
  function flip(i) {
    if (!puzzle || state.solved) return;
    state.history.push(state.directions.slice()); state.history = state.history.slice(-80);
    state.directions[i] = state.directions[i] === 0 ? 1 : 0; state.moves++;
    save(); updateBoard(); announce(wireLabel(puzzle.edges[i], i));
  }
  function loadBoard() {
    renderNavigation();
    if (mode === "weekly" && !week) {
      puzzle = null; state = null;
      $("cw-board-title").textContent = "The exchange opens on Wednesday.";
      $("cw-briefing").textContent = "Your weekly shift will appear here automatically. Explore the practice boards while you wait.";
      ["cw-check", "cw-hint", "cw-reset", "cw-next", "cw-undo"].forEach(id => $(id).disabled = true);
      diagram.replaceChildren(); $("cw-wires").replaceChildren(); $("cw-sockets").replaceChildren(); $("cw-receipt").hidden = true;
      announce("The first shift has not opened yet. Practice is always available."); save(); return;
    }
    if (mode === "weekly") while (round > 0 && !completed(week.puzzles[round - 1])) round--;
    puzzle = mode === "practice" ? practice[practiceIndex] : week.puzzles[round]; state = boardState(puzzle);
    $("cw-reset").disabled = false; $("cw-share-text").hidden = true;
    $("cw-board-title").textContent = mode === "weekly" ? `${String(round + 1).padStart(2, "0")} / ${stageNames[round]}` : puzzle.title;
    $("cw-briefing").textContent = mode === "weekly" && round === 2
      ? `A power cut erased socket ${letters[puzzle.nodes.length - 1]}'s targets. Every wire adds one IN and one OUT, so each target column must total ${puzzle.edges.length}. Deduce the missing counts, then reconnect the board.`
      : mode === "weekly" && round === 1 ? "The exchange is getting busy. Follow one socket's counts through its neighbors. Every change sends a ripple through the board."
        : "Tap a numbered wire to connect it; tap again to reverse it. Match each socket's IN and OUT targets, then send a test signal.";
    $("cw-level").textContent = `${puzzle.difficulty.toUpperCase()} / ${puzzle.nodes.length} pages / ${puzzle.edges.length} wires`;
    positions = puzzle.nodes.map((_, i) => { const angle = -Math.PI / 2 + i * Math.PI * 2 / puzzle.nodes.length; return {x: 300 + Math.cos(angle) * 220, y: 205 + Math.sin(angle) * 150}; });
    $("cw-sockets").replaceChildren();
    sockets = puzzle.nodes.map((node, i) => {
      const card = element("article", "cw-socket"), identity = element("div", "cw-socket-identity");
      identity.append(element("span", "cw-socket-letter", letters[i]), element("h3", "", node.name));
      const countRow = element("div", "cw-socket-counts"), incoming = element("strong"), outgoing = element("strong"), inTarget = element("span"), outTarget = element("span");
      const inCount = element("span"), outCount = element("span");
      inCount.append("IN ", incoming, " / ", inTarget); outCount.append("OUT ", outgoing, " / ", outTarget); countRow.append(inCount, outCount);
      const match = element("span", "cw-socket-match"); card.append(identity, countRow, match); $("cw-sockets").append(card);
      return {node, card, incoming, outgoing, inTarget, outTarget, match};
    });
    const names = nameMap(); $("cw-wires").replaceChildren();
    wires = puzzle.edges.map((edge, i) => {
      const button = element("button", "cw-wire"); button.type = "button"; button.dataset.edge = i;
      const ports = element("span", "cw-wire-ports"), arrow = element("span", "cw-wire-direction", "?"); ports.setAttribute("aria-hidden", "true");
      ports.append(element("span", "", names.get(edge.a).letter), arrow, element("span", "", names.get(edge.b).letter));
      const label = element("span", "cw-wire-label"), flipIcon = element("span", "cw-wire-flip", "↔"); flipIcon.setAttribute("aria-hidden", "true");
      button.append(element("span", "cw-wire-number", String(i + 1).padStart(2, "0")), ports, label, flipIcon);
      button.addEventListener("click", () => flip(i)); $("cw-wires").append(button); return {edge, button, arrow, label};
    });
    save(); renderNavigation(); renderSchedule(); updateBoard();
    announce(state.solved ? "This board is repaired. Replay it to try for a better ticket, or continue your shift." : `${puzzle.title}. ${state.moves ? "Your unfinished board is restored." : "The targets count only the links on this board."}`);
  }
  function stars() { return state.hints + state.checks === 0 ? 3 : state.hints + state.checks <= 2 ? 2 : 1; }
  function renderReceipt() {
    const shiftDone = mode === "weekly" && week.puzzles.every(completed);
    $("cw-receipt-title").textContent = shiftDone ? "Night shift, signed off." : "Connection restored.";
    $("cw-receipt-rating").textContent = "★".repeat(stars()) + "☆".repeat(3 - stars()); $("cw-receipt-rating").dataset.stars = stars();
    $("cw-receipt-rating").setAttribute("aria-label", `${stars()} of 3 stars`);
    $("cw-receipt-detail").textContent = `${puzzle.edges.length} real Wikipedia links restored. ${state.hints} hint${state.hints === 1 ? "" : "s"}, ${state.checks} failed test${state.checks === 1 ? "" : "s"}. ${shiftDone ? `Shift total: ${week.puzzles.reduce((sum, board) => sum + boardState(board).bestStars, 0)} / 9 stars. ` : ""}Three stars with no hints or failed tests; two with one or two assists; one for seeing it through. Replays keep your best score.`;
  }
  select.replaceChildren(...practice.map((board, i) => { const option = element("option", "", board.title); option.value = i; return option; }));
  select.addEventListener("change", () => {
    const value = Number(select.value); if (!Number.isInteger(value) || value < 0 || value >= practice.length) return;
    save(); practiceIndex = value; mode = "practice"; loadBoard();
  });
  weekSelect.addEventListener("change", () => {
    const chosen = available().find(item => item.id === weekSelect.value);
    if (!chosen) { weekSelect.value = week?.id || ""; announce("That shift is still sealed. It opens on the Wednesday shown in the archive."); return; }
    save(); week = chosen; mode = "weekly"; round = Math.max(0, week.puzzles.findIndex(board => !completed(board))); loadBoard();
  });
  $("cw-weekly").addEventListener("click", () => { save(); mode = "weekly"; week = available().at(-1) || null; round = week ? Math.max(0, week.puzzles.findIndex(board => !completed(board))) : 0; loadBoard(); });
  $("cw-practice").addEventListener("click", () => { save(); mode = "practice"; loadBoard(); });
  $("cw-reset").addEventListener("click", () => { if (puzzle) { saved.boards[puzzle.id] = {...fresh(), bestStars: state.bestStars}; loadBoard(); announce("Fresh wires. Your best ticket is kept; this attempt starts from zero."); } });
  $("cw-undo").addEventListener("click", () => {
    if (!puzzle || state.solved || !state.history.length) return;
    state.directions = state.history.pop(); state.moves++; save(); updateBoard(); announce("Last wire change undone. Hints and failed tests still count for this attempt.");
  });
  $("cw-next").addEventListener("click", () => {
    if (!puzzle) return; save();
    if (mode === "practice") practiceIndex = (practiceIndex + 1) % practice.length;
    else if (state.solved && round < 2) round++; else return;
    loadBoard();
  });
  $("cw-check").addEventListener("click", () => {
    if (!puzzle || state.solved) return;
    const missing = state.directions.filter(value => value === null).length;
    if (missing) { announce(`${missing} wire${missing === 1 ? " still needs" : "s still need"} a direction. Connect the question marks before sending a signal.`, "notice"); return; }
    mount.classList.remove("cw-testing"); void mount.offsetWidth; mount.classList.add("cw-testing");
    const current = counts(), wrong = puzzle.nodes.filter(node => current.get(node.id).incoming !== node.in_target || current.get(node.id).outgoing !== node.out_target);
    if (wrong.length) { state.checks++; save(); updateBoard(); announce(`${wrong.length} sockets have a crossed connection: ${wrong.map(node => node.name).join(", ")}. Trace a wire touching them and try reversing it. This test counts as one assist.`, "notice"); return; }
    state.solved = true; state.bestStars = Math.max(state.bestStars, stars()); save(); renderNavigation(); updateBoard();
    announce(`Connection restored! ${stars()} of 3 stars. ${mode === "weekly" && round === 2 ? "Your night shift is complete. Your repair ticket is ready." : "Your ticket is ready. Continue when you like."}`, "success");
  });
  $("cw-hint").addEventListener("click", () => {
    if (!puzzle || state.solved) return;
    const wrong = puzzle.edges.findIndex((edge, i) => state.directions[i] !== null && state.directions[i] !== answer(edge));
    const names = nameMap(), current = counts(); let index = wrong, explanation = "";
    if (wrong >= 0) {
      const edge = puzzle.edges[wrong]; explanation = `The current directions cannot all satisfy the targets. Reverse wire ${wrong + 1}: ${names.get(edge.source).name} must send to ${names.get(edge.target).name}. Recount these sockets before following the next wire.`;
    } else {
      for (let i = 0; i < puzzle.edges.length; i++) {
        if (state.directions[i] !== null) continue;
        const edge = puzzle.edges[i], forcing = [names.get(edge.a), names.get(edge.b)].find(node => current.get(node.id).incoming === node.in_target || current.get(node.id).outgoing === node.out_target);
        if (!forcing) continue;
        index = i; const allIn = current.get(forcing.id).incoming === forcing.in_target;
        explanation = `${forcing.name} already has its ${allIn ? "IN" : "OUT"} target of ${allIn ? forcing.in_target : forcing.out_target}. Every unassigned wire here must point ${allIn ? "out" : "in"}. Wire ${i + 1} follows that rule.`; break;
      }
      if (index < 0) index = puzzle.edges.findIndex((edge, i) => state.directions[i] !== answer(edge));
      if (index < 0) { announce("All the wires are ready. Send a test signal to sign off this repair."); return; }
      if (!explanation) explanation = `Only one orientation matches all the targets: wire ${index + 1} must point from ${names.get(puzzle.edges[index].source).name} to ${names.get(puzzle.edges[index].target).name}. Follow the resulting counts.`;
    }
    state.history.push(state.directions.slice()); state.history = state.history.slice(-80);
    state.directions[index] = answer(puzzle.edges[index]); state.hints++; state.moves++; save(); updateBoard(); announce(`Hint: ${explanation}`);
  });
  $("cw-share").addEventListener("click", async () => {
    if (!puzzle || !state.solved) return;
    const shiftDone = mode === "weekly" && week.puzzles.every(completed);
    const score = shiftDone ? `${week.puzzles.reduce((sum, board) => sum + boardState(board).bestStars, 0)}/9 stars` : `${stars()}/3 stars`;
    const text = `CROSSTALK / Crossed Wires\n${mode === "weekly" ? `Shift ${String(week.number).padStart(2, "0")} · ${week.title}${shiftDone ? " · complete" : ` · round ${round + 1}`}` : `Practice · ${puzzle.title}`}\n${score}. Real links. Repaired by hand.\nhttps://vitrotank.github.io/social_graphs_2026/play/index.html`;
    try { await navigator.clipboard.writeText(text); announce("Repair ticket copied. Paste it wherever you like.", "success"); }
    catch (_) { $("cw-share-text").value = text; $("cw-share-text").hidden = false; $("cw-share-text").focus(); $("cw-share-text").select(); announce("Your ticket is selected below. Copy the text to share it."); }
  });
  renderSchedule(); loadBoard();
  setInterval(renderSchedule, 1000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) renderSchedule(); });
})();
