/* Week 2: The Cerebro Paradox & Multiverse Rewirer Game Engine
   Runs offline using window.CROSSTALK_DATA. No external dependencies. */
(() => {
  "use strict";

  if (!window.CROSSTALK_DATA) return;

  const { nodes, edges } = window.CROSSTALK_DATA.network;
  const summary = window.CROSSTALK_DATA.summary;
  const byId = new Map(nodes.map(n => [n.id, n]));

  // Build undirected adjacency graph
  const neighbors = new Map(nodes.map(n => [n.id, new Set()]));
  edges.forEach(({ source, target }) => {
    if (source !== target) {
      neighbors.get(source).add(target);
      neighbors.get(target).add(source);
    }
  });

  const labelCounts = new Map();
  nodes.forEach(n => labelCounts.set(n.label, (labelCounts.get(n.label) || 0) + 1));
  const nameOf = n => (labelCounts.get(n.label) > 1 ? n.name : n.label || n.name || n.id.replace(/_/g, " "));

  // Precompute character paradox profiles
  const profiles = new Map();
  let totalConnected = 0;
  let paradoxCount = 0;

  nodes.forEach(n => {
    const nbrIds = Array.from(neighbors.get(n.id));
    const k = nbrIds.length;
    let avgFriendK = 0;
    let maxFriendK = 0;
    let topFriend = null;

    if (k > 0) {
      totalConnected++;
      let sumK = 0;
      nbrIds.forEach(id => {
        const friendK = neighbors.get(id).size;
        sumK += friendK;
        if (friendK > maxFriendK) {
          maxFriendK = friendK;
          topFriend = byId.get(id);
        }
      });
      avgFriendK = sumK / k;
      if (avgFriendK > k) {
        paradoxCount++;
      }
    }

    profiles.set(n.id, {
      id: n.id,
      node: n,
      name: nameOf(n),
      degree: k,
      inDegree: n.in_degree,
      outDegree: n.out_degree,
      neighbors: nbrIds,
      avgFriendDegree: avgFriendK,
      maxFriendDegree: maxFriendK,
      topFriend: topFriend,
      isIsolate: k === 0,
      beatsParadox: k > 0 && k >= avgFriendK,
      isUndefeated: k > 0 && k >= maxFriendK
    });
  });

  // Precompute connected hero pool
  const connectedNodes = nodes.filter(n => neighbors.get(n.id).size > 0);

  // State
  let selectedHeroId = connectedNodes.length > 0
    ? connectedNodes[Math.floor(Math.random() * connectedNodes.length)].id
    : "Spider-Man";
  let score = 0;
  let streak = 0;
  let inspectedCount = 0;
  let hasGuessedCurrent = false;

  // Versus Mode State
  let currentVersusA = null;
  let currentVersusB = null;
  let hasGuessedVersus = false;

  // DOM Elements - Mode Switcher Tabs
  const tabDuelMode = document.getElementById("tab-duel-mode");
  const tabParadoxMode = document.getElementById("tab-paradox-mode");
  const panelDuel = document.getElementById("mode-duel-panel");
  const panelParadox = document.getElementById("mode-paradox-panel");

  // DOM Elements - Mode 1: Versus Duel
  const versusNameA = document.getElementById("versus-name-a");
  const versusMetaA = document.getElementById("versus-meta-a");
  const versusAvgA = document.getElementById("versus-avg-a");
  const btnPickA = document.getElementById("pick-hero-a-btn");
  const versusNameB = document.getElementById("versus-name-b");
  const versusMetaB = document.getElementById("versus-meta-b");
  const versusAvgB = document.getElementById("versus-avg-b");
  const btnPickB = document.getElementById("pick-hero-b-btn");
  const versusRandomBtn = document.getElementById("versus-random-btn");
  const versusRevealPanel = document.getElementById("versus-reveal-panel");

  // DOM Elements - Mode 2: Single Hero Paradox
  const searchInput = document.getElementById("duel-search-input");
  const searchForm = document.getElementById("duel-search-form");
  const searchOptions = document.getElementById("duel-character-options");
  const randomBtn = document.getElementById("duel-random-btn");
  const heroCard = document.getElementById("duel-hero-card");
  const guessFriendBtn = document.getElementById("guess-friend-btn");
  const guessHeroBtn = document.getElementById("guess-hero-btn");
  const revealPanel = document.getElementById("duel-reveal-panel");
  const streakDisplay = document.getElementById("duel-streak");
  const scoreDisplay = document.getElementById("duel-score");
  const inspectedDisplay = document.getElementById("duel-inspected");
  const chipButtons = document.querySelectorAll(".hero-chip");

  // Shared Radar & Voltmeter elements
  const radarSvg = document.getElementById("cerebro-radar-svg");
  const radarTargetLabel = document.getElementById("radar-target-label");
  const needleHero = document.getElementById("needle-hero");
  const needleFriend = document.getElementById("needle-friend");
  const voltmeterLamp = document.getElementById("voltmeter-lamp");
  // Mode 1: Dual Radar elements
  const versusRadarSvgA = document.getElementById("versus-radar-svg-a");
  const versusRadarSvgB = document.getElementById("versus-radar-svg-b");
  const radarLabelA = document.getElementById("radar-label-a");
  const radarLabelB = document.getElementById("radar-label-b");

  // Populate datalist if element exists
  if (searchOptions && searchOptions.children.length === 0) {
    const sorted = [...nodes].sort((a, b) => nameOf(a).localeCompare(nameOf(b)));
    sorted.forEach(n => {
      const opt = document.createElement("option");
      opt.value = nameOf(n);
      searchOptions.appendChild(opt);
    });
  }

  function animateNeedle(lineEl, targetDegree, length, durationMs = 400) {
    if (!lineEl) return;
    const currentX2 = parseFloat(lineEl.getAttribute("x2")) || (150 - length);
    const currentY2 = parseFloat(lineEl.getAttribute("y2")) || 140;
    const fraction = Math.min(1, Math.max(0, targetDegree / 60));
    const targetAngle = Math.PI * (1 - fraction);
    const targetX2 = 150 + length * Math.cos(targetAngle);
    const targetY2 = 140 - length * Math.sin(targetAngle);

    const start = performance.now();
    function step(now) {
      const elapsed = now - start;
      const t = Math.min(1, elapsed / durationMs);
      const ease = 1 - Math.pow(1 - t, 3);
      const x = currentX2 + (targetX2 - currentX2) * ease;
      const y = currentY2 + (targetY2 - currentY2) * ease;
      lineEl.setAttribute("x2", x.toFixed(1));
      lineEl.setAttribute("y2", y.toFixed(1));
      if (t < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  function renderHero(id) {
    const p = profiles.get(id);
    if (!p) return;

    selectedHeroId = id;
    hasGuessedCurrent = false;

    if (searchInput) searchInput.value = p.name;
    if (radarTargetLabel) radarTargetLabel.textContent = `FOCUS: ${p.name.toUpperCase()}`;

    // Reset Voltmeter needles smoothly to hero degree and 0 baseline
    if (needleHero) {
      animateNeedle(needleHero, p.degree, 95);
    }
    if (needleFriend) {
      animateNeedle(needleFriend, 0, 90);
    }
    if (voltmeterLamp) {
      voltmeterLamp.style.background = "#60645c";
      voltmeterLamp.style.boxShadow = "none";
    }

    // Reset buttons
    if (guessFriendBtn) {
      guessFriendBtn.disabled = p.isIsolate;
      guessFriendBtn.classList.remove("selected", "correct", "wrong");
    }
    if (guessHeroBtn) {
      guessHeroBtn.disabled = p.isIsolate;
      guessHeroBtn.classList.remove("selected", "correct", "wrong");
    }

    if (revealPanel) {
      revealPanel.hidden = true;
      revealPanel.innerHTML = "";
    }

    renderHeroCard(p);
    if (radarSvg) {
      renderRadarScope(radarSvg, p, {
        ringColor: "#2849c7",
        beamStroke: "#99d5c6",
        wedgeFill: "rgba(40, 73, 199, 0.22)",
        blipBase: "#99d5c6",
        blipBright: "#ffffff",
        waveStroke: "#99d5c6",
        reticleColor: "#dc512f",
        reticleLabel: p.name
      });
    }
  }

  function renderHeroCard(p) {
    if (!heroCard) return;

    let badgeHtml = "";
    if (p.isIsolate) {
      badgeHtml = '<span class="status-badge isolate-badge">QUIET LINE · 0 CONNECTIONS</span>';
    } else if (p.id === "Spider-Man") {
      badgeHtml = '<span class="status-badge apex-badge">★ MAINLAND APEX HUB</span>';
    } else if (p.id === "Radian_(Morituri)") {
      badgeHtml = '<span class="status-badge island-badge">★ MORITURI ISLAND MONARCH</span>';
    } else if (p.beatsParadox) {
      badgeHtml = '<span class="status-badge titan-badge">PARADOX DEFIER</span>';
    } else {
      badgeHtml = '<span class="status-badge trapped-badge">IN THE POPULARITY TRAP</span>';
    }

    heroCard.innerHTML = `
      <div class="duel-card-header">
        <div>
          <p class="eyebrow">CHOSEN HERO</p>
          <h3 class="duel-hero-name">${escapeHtml(p.name)}</h3>
        </div>
        ${badgeHtml}
      </div>
      <div class="duel-stats-grid">
        <div class="duel-stat-item">
          <span class="duel-stat-num">${p.degree}</span>
          <span class="duel-stat-label">UNDIRECTED LINKS</span>
        </div>
        <div class="duel-stat-item">
          <span class="duel-stat-num">${p.inDegree}</span>
          <span class="duel-stat-label">INCOMING</span>
        </div>
        <div class="duel-stat-item">
          <span class="duel-stat-num">${p.outDegree}</span>
          <span class="duel-stat-label">OUTGOING</span>
        </div>
      </div>
      <p class="duel-card-prompt">
        ${
          p.isIsolate
            ? "This hero has 0 connections in this snapshot. The paradox cannot evaluate because there are no friends to compare!"
            : "Does this hero fall victim to the Friendship Paradox? Will their friends have MORE connections on average than them, or does this hero beat the average?"
        }
      </p>
    `;
  }

  // Synchronized Vector Radar Engine
  const registeredRadars = new Map();

  function renderRadarScope(svgEl, hero, theme = {}) {
    if (!svgEl) return;
    const CX = 250;
    const CY = 250;
    const R = 225;

    const ringColor = theme.ringColor || "#2849c7";
    const beamStroke = theme.beamStroke || "#7fa5f7";
    const wedgeFill = theme.wedgeFill || "rgba(40, 73, 199, 0.22)";
    const blipBase = theme.blipBase || "#99d5c6";
    const blipBright = theme.blipBright || "#ffffff";
    const waveStroke = theme.waveStroke || "#7fa5f7";
    const reticleColor = theme.reticleColor || "#2849c7";
    const reticleLabel = theme.reticleLabel || (hero ? hero.name : "FOCUS");

    const parts = [];

    // Background range rings & crosshairs
    parts.push(`<g fill="none" stroke="${ringColor}" stroke-opacity="0.32" stroke-width="1">`);
    [60, 115, 170, 225].forEach((r, idx) => {
      const labels = ["ZONE 1", "ZONE 2", "ZONE 3", "OUTER SECTOR"];
      parts.push(`<circle cx="${CX}" cy="${CY}" r="${r}" stroke-dasharray="3 4"/>`);
      parts.push(`<text x="${CX + 4}" y="${CY - r + 11}" fill="#8fa0b5" font-family="Consolas, monospace" font-size="8">${labels[idx]}</text>`);
    });
    parts.push(`<line x1="25" y1="${CY}" x2="475" y2="${CY}" stroke-opacity="0.25"/>`);
    parts.push(`<line x1="${CX}" y1="25" x2="${CX}" y2="475" stroke-opacity="0.25"/>`);
    parts.push('</g>');

    if (!hero || hero.isIsolate) {
      parts.push(`
        <circle cx="${CX}" cy="${CY}" r="14" fill="#60645c" opacity="0.8"/>
        <circle cx="${CX}" cy="${CY}" r="22" fill="none" stroke="#60645c" stroke-dasharray="3 3"/>
        <text x="${CX}" y="${CY + 4}" fill="#fff" font-family="Consolas, monospace" font-size="8" text-anchor="middle">SILENT</text>
        <text x="${CX}" y="${CY + 48}" fill="#8fa0b5" font-family="Consolas, monospace" font-size="10" text-anchor="middle">ZERO CONTACTS DETECTED</text>
      `);
      svgEl.innerHTML = parts.join("");
      registeredRadars.delete(svgEl.id);
      return;
    }

    // Anonymous contacts with deterministic pseudo-random scatter
    const count = hero.neighbors.length;
    const maxDisplay = Math.min(count, 48);

    function pseudoRandom(seed) {
      const s = Math.sin(seed) * 10000;
      return s - Math.floor(s);
    }

    const contactsData = [];
    parts.push('<g class="radar-contacts">');
    for (let i = 0; i < maxDisplay; i++) {
      const angle = pseudoRandom(hero.degree * 47 + i * 19 + 7) * Math.PI * 2;
      const radius = 45 + Math.sqrt(pseudoRandom(hero.degree * 29 + i * 37 + 13)) * 170;
      const bx = CX + radius * Math.cos(angle);
      const by = CY + radius * Math.sin(angle);
      const normAngle = (angle % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI);

      contactsData.push({ angle: normAngle, x: bx, y: by });

      parts.push(`
        <g class="radar-contact-node" data-angle="${normAngle.toFixed(4)}">
          <circle class="radar-wave" cx="${bx.toFixed(1)}" cy="${by.toFixed(1)}" r="4" fill="none" stroke="${waveStroke}" opacity="0"/>
          <circle class="radar-blip" cx="${bx.toFixed(1)}" cy="${by.toFixed(1)}" r="4" fill="${blipBase}" opacity="0.25"/>
        </g>
      `);
    }
    parts.push('</g>');

    // Rotating sweep beam & trailing wedge
    parts.push(`
      <g class="radar-beam-group">
        <path class="radar-beam-wedge" d="" fill="${wedgeFill}"/>
        <line class="radar-beam-line" x1="${CX}" y1="${CY}" x2="${CX}" y2="${CY - R}" stroke="${beamStroke}" stroke-width="2.2" stroke-linecap="round"/>
      </g>
    `);

    // Central reticle
    parts.push(`
      <circle cx="${CX}" cy="${CY}" r="24" fill="${reticleColor}" fill-opacity="0.18"/>
      <circle cx="${CX}" cy="${CY}" r="14" fill="${reticleColor}" stroke="#fff" stroke-width="2"/>
      <circle cx="${CX}" cy="${CY}" r="6" fill="#fff"/>
      <text x="${CX}" y="${CY + 36}" fill="#fff" font-family="Consolas, monospace" font-size="9" font-weight="bold" text-anchor="middle">FOCUS: ${escapeHtml(reticleLabel)}</text>
      <text x="${CX}" y="${CY + 49}" fill="#8fa0b5" font-family="Consolas, monospace" font-size="8" text-anchor="middle">CONTACTS DETECTED: ${hero.degree}</text>
    `);

    svgEl.innerHTML = parts.join("");

    // Register into active radars
    const nodesList = Array.from(svgEl.querySelectorAll(".radar-contact-node"));
    registeredRadars.set(svgEl.id, {
      svgEl,
      theme: { ringColor, beamStroke, wedgeFill, blipBase, blipBright, waveStroke },
      beamLine: svgEl.querySelector(".radar-beam-line"),
      beamWedge: svgEl.querySelector(".radar-beam-wedge"),
      contacts: nodesList.map((n, idx) => ({
        angle: contactsData[idx].angle,
        blipEl: n.querySelector(".radar-blip"),
        waveEl: n.querySelector(".radar-wave")
      }))
    });
  }

  function animateAllRadars(timestamp) {
    const period = 4200; // ms per 360 rotation
    const beamAngle = ((timestamp % period) / period) * 2 * Math.PI;

    registeredRadars.forEach(radar => {
      if (!radar.svgEl || !radar.svgEl.isConnected) return;
      if (radar.svgEl.closest("[hidden]")) return;

      const CX = 250;
      const CY = 250;
      const R = 225;

      const bx = CX + R * Math.cos(beamAngle);
      const by = CY + R * Math.sin(beamAngle);

      if (radar.beamLine) {
        radar.beamLine.setAttribute("x2", bx.toFixed(1));
        radar.beamLine.setAttribute("y2", by.toFixed(1));
      }

      if (radar.beamWedge) {
        const trailAngle = beamAngle - 0.44;
        const tx = CX + R * Math.cos(trailAngle);
        const ty = CY + R * Math.sin(trailAngle);
        radar.beamWedge.setAttribute(
          "d",
          `M ${CX} ${CY} L ${tx.toFixed(1)} ${ty.toFixed(1)} A ${R} ${R} 0 0 1 ${bx.toFixed(1)} ${by.toFixed(1)} Z`
        );
      }

      for (let i = 0; i < radar.contacts.length; i++) {
        const c = radar.contacts[i];
        let diff = (beamAngle - c.angle) % (2 * Math.PI);
        if (diff < 0) diff += 2 * Math.PI;

        if (diff < 0.62) {
          const p = diff / 0.62; // 0 right as beam hits, 1 when faded
          c.blipEl.setAttribute("opacity", (1 - p * 0.65).toFixed(2));
          c.blipEl.setAttribute("r", (4 + (1 - p) * 2.5).toFixed(1));
          c.blipEl.setAttribute("fill", radar.theme.blipBright || "#ffffff");
          c.waveEl.setAttribute("r", (5 + p * 16).toFixed(1));
          c.waveEl.setAttribute("opacity", ((1 - p) * 0.85).toFixed(2));
          c.waveEl.setAttribute("stroke-width", (1.8 - p * 1.2).toFixed(1));
        } else {
          c.blipEl.setAttribute("opacity", "0.25");
          c.blipEl.setAttribute("r", "4");
          c.blipEl.setAttribute("fill", radar.theme.blipBase || "#99d5c6");
          c.waveEl.setAttribute("opacity", "0");
        }
      }
    });

    requestAnimationFrame(animateAllRadars);
  }

  // Start continuous RAF loop
  requestAnimationFrame(animateAllRadars);

  function updateBriefing(mode) {
    const titleEl = document.getElementById("briefing-title");
    const codeEl = document.getElementById("briefing-code");
    const container = document.getElementById("briefing-steps-container");
    if (!container) return;

    if (mode === "duel") {
      if (titleEl) {
        titleEl.innerHTML = '<span class="signal"><span class="legend-dot"></span></span> MISSION PROTOCOL // POPULARITY DUEL (CONTENDER A VS CONTENDER B)';
      }
      if (codeEl) codeEl.textContent = "MODE 01 · DUAL RADARS";
      container.innerHTML = `
        <div class="briefing-step">
          <span class="step-num">01</span>
          <div class="step-copy">
            <strong>Inspect the Dual Radars</strong>
            <p>Two superheroes are pitted head-to-head. Compare their direct connections (<em>k<sub>A</sub></em> vs <em>k<sub>B</sub></em>) on the twin tactical radar screens.</p>
          </div>
        </div>
        <div class="briefing-step">
          <span class="step-num">02</span>
          <div class="step-copy">
            <strong>Deduce Friend Popularity</strong>
            <p>Guess which hero's friends have a higher average degree (⟨<em>k</em><sub>friends</sub>⟩). Don't fall for the trap: fewer direct links can still connect to titan mega-hubs!</p>
          </div>
        </div>
        <div class="briefing-step">
          <span class="step-num">03</span>
          <div class="step-copy">
            <strong>Score the Multiverse</strong>
            <p>Lock in your choice to reveal the true network averages, test your intuition against variance, and build your win streak.</p>
          </div>
        </div>
      `;
    } else {
      if (titleEl) {
        titleEl.innerHTML = '<span class="signal"><span class="legend-dot"></span></span> MISSION PROTOCOL // THE PARADOX SCAN (SINGLE HERO TELEMETRY)';
      }
      if (codeEl) codeEl.textContent = "MODE 02 · PARADOX VOLTMETER";
      container.innerHTML = `
        <div class="briefing-step">
          <span class="step-num">01</span>
          <div class="step-copy">
            <strong>Scan Any Superhero</strong>
            <p>Choose any character via quick chips, search, or random roll. Cerebro sweeps for anonymous radar contacts.</p>
          </div>
        </div>
        <div class="briefing-step">
          <span class="step-num">02</span>
          <div class="step-copy">
            <strong>Predict the Paradox</strong>
            <p>Deduce whether their comic friends beat them on average (⟨<em>k</em><sub>friends</sub>⟩ &gt; <em>k</em>) or if this hero defies the friendship paradox.</p>
          </div>
        </div>
        <div class="briefing-step">
          <span class="step-num">03</span>
          <div class="step-copy">
            <strong>Inspect the Voltmeter</strong>
            <p>Watch the analog gauge sweep to reveal the variance boost and uncover which mega-hubs pull the strings.</p>
          </div>
        </div>
      `;
    }
  }

  function handleGuess(userGuessedFriendsMore) {
    if (hasGuessedCurrent) return;
    const p = profiles.get(selectedHeroId);
    if (!p || p.isIsolate) return;

    hasGuessedCurrent = true;
    inspectedCount++;

    const friendsActuallyMore = p.avgFriendDegree > p.degree;
    const isCorrect = userGuessedFriendsMore === friendsActuallyMore;

    if (isCorrect) {
      score += 10;
      streak++;
    } else {
      streak = 0;
    }

    if (streakDisplay) streakDisplay.textContent = String(streak);
    if (scoreDisplay) scoreDisplay.textContent = String(score);
    if (inspectedDisplay) inspectedDisplay.textContent = String(inspectedCount);

    // Animate Voltmeter needle to friend's degree
    if (needleFriend) {
      animateNeedle(needleFriend, p.avgFriendDegree, 90);
    }
    if (voltmeterLamp) {
      voltmeterLamp.style.background = friendsActuallyMore ? "#dc512f" : "#2849c7";
      voltmeterLamp.style.boxShadow = `0 0 10px ${friendsActuallyMore ? "#dc512f" : "#2849c7"}`;
    }

    // Visual button states
    if (guessFriendBtn) {
      guessFriendBtn.classList.toggle("selected", userGuessedFriendsMore);
      guessFriendBtn.classList.toggle("correct", userGuessedFriendsMore && isCorrect);
      guessFriendBtn.classList.toggle("wrong", userGuessedFriendsMore && !isCorrect);
    }
    if (guessHeroBtn) {
      guessHeroBtn.classList.toggle("selected", !userGuessedFriendsMore);
      guessHeroBtn.classList.toggle("correct", !userGuessedFriendsMore && isCorrect);
      guessHeroBtn.classList.toggle("wrong", !userGuessedFriendsMore && !isCorrect);
    }

    renderReveal(p, isCorrect, userGuessedFriendsMore);
  }

  function renderReveal(p, isCorrect, userGuessedFriendsMore) {
    if (!revealPanel) return;

    let verdictTitle = "";
    let verdictClass = "";
    let verdictIcon = "";

    if (isCorrect) {
      verdictTitle = "EXCELLENT DEDUCTION! +10 PTS";
      verdictClass = "verdict-correct";
      verdictIcon = "✓";
    } else {
      verdictTitle = "THE PARADOX TRICKED YOU!";
      verdictClass = "verdict-wrong";
      verdictIcon = "✗";
    }

    let storyExplanation = "";
    if (p.id === "Spider-Man") {
      storyExplanation = `
        <div class="easter-egg-banner apex">
          <strong>★ THE UNDEFEATED APEX PREDATOR:</strong>
          Spider-Man has 106 connections. Not only does he crush his friends' average (${p.avgFriendDegree.toFixed(1)}),
          he strictly out-populars <em>every single one</em> of his 106 neighbors (his highest connected neighbor is Wolverine at 65). Nobody out-populars Spider-Man on the mainland!
        </div>
      `;
    } else if (p.id === "Radian_(Morituri)") {
      storyExplanation = `
        <div class="easter-egg-banner island">
          <strong>★ THE MORITURI ISLAND MONARCH:</strong>
          In the detached 9-page Strikeforce: Morituri component, Radian has degree 6, easily beating his friends' average (${p.avgFriendDegree.toFixed(1)}) and defeating all 6 neighbors (max neighbor degree is 3)!
        </div>
      `;
    } else if (p.beatsParadox) {
      storyExplanation = `
        <div class="easter-egg-banner titan">
          <strong>A RARE TITAN:</strong> ${p.name} has ${p.degree} connections, exceeding the friends' average of ${p.avgFriendDegree.toFixed(1)}. Only 12.6% of connected heroes accomplish this!
        </div>
      `;
    } else {
      const topFriendName = p.topFriend ? nameOf(p.topFriend) : "a major hub";
      const topFriendK = p.maxFriendDegree;
      storyExplanation = `
        <p class="duel-explanation">
          <strong>The Popular Friend Effect:</strong> ${p.name} has <strong>${p.degree}</strong> connections, but their friends average <strong>${p.avgFriendDegree.toFixed(1)}</strong> links!
          Connecting to heavy hitters like <strong>${escapeHtml(topFriendName)}</strong> (${topFriendK} links) radically inflates the friend circle's average.
        </p>
      `;
    }

    revealPanel.hidden = false;
    revealPanel.innerHTML = `
      <div class="verdict-bar">
        <div class="verdict-banner ${verdictClass}">
          <span class="verdict-icon">${verdictIcon}</span>
          <strong>${verdictTitle}</strong>
        </div>
        <button type="button" class="button button-primary button-small" id="duel-next-btn-top">Try Another Hero ↗</button>
      </div>
      <div class="duel-comparison-cards">
        <div class="duel-comp-card hero-comp">
          <span class="eyebrow">${escapeHtml(p.name)}</span>
          <div class="comp-degree">${p.degree}</div>
          <span class="comp-label">HERO DEGREE</span>
        </div>
        <div class="duel-comp-vs">VS</div>
        <div class="duel-comp-card friend-comp">
          <span class="eyebrow">FRIENDS' AVERAGE</span>
          <div class="comp-degree ${p.avgFriendDegree > p.degree ? 'higher' : 'lower'}">${p.avgFriendDegree.toFixed(1)}</div>
          <span class="comp-label">⟨<em>k</em><sub>friends</sub>⟩</span>
        </div>
      </div>
      ${storyExplanation}
      <div class="duel-math-box">
        <p class="eyebrow">THE SCIENCE BEHIND IT</p>
        <p>
          Formula: <code>⟨<em>k</em><sub>friends</sub>⟩ = ⟨<em>k</em>⟩ + (σ² / ⟨<em>k</em>⟩)</code>. In Marvel's giant component, average degree is <code>10.26</code>,
          and variance boost <code>σ² / ⟨<em>k</em>⟩</code> is <code>11.99</code>, giving an expected friend degree of <strong>22.25</strong>!
        </p>
      </div>
    `;

    const topBtn = document.getElementById("duel-next-btn-top");
    if (topBtn) topBtn.addEventListener("click", pickRandomHero);
  }

  function pickRandomHero() {
    const connected = nodes.filter(n => neighbors.get(n.id).size > 0);
    const chosen = connected[Math.floor(Math.random() * connected.length)];
    renderHero(chosen.id);
  }

  function printReceipt(p) {
    const text = `
========================================
    CROSSTALK // CEREBRO DISPATCH
========================================
OPERATOR REPORT: WEEK 02
HERO SCANNED:    ${p.name.toUpperCase()}
HERO DEGREE:     ${p.degree} LINKS
FRIENDS AVERAGE: ${p.avgFriendDegree.toFixed(2)} LINKS
PARADOX STATUS:  ${p.avgFriendDegree > p.degree ? "TRAPPED (FRIENDS WIN)" : "DEFIED (HERO WINS)"}
TOP APEX FRIEND: ${p.topFriend ? nameOf(p.topFriend) : "NONE"} (${p.maxFriendDegree})
SCORE / STREAK:  ${score} PTS / STREAK ${streak}
========================================
https://vitrotank.github.io/social_graphs_2026/
    `.trim();

    navigator.clipboard.writeText(text).then(() => {
      alert("Receipt copied to clipboard!\n\n" + text);
    }).catch(() => {
      alert("Cerebro Dispatch:\n\n" + text);
    });
  }

  function escapeHtml(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // =========================================================================
  // Mode 1: Who Has More Popular Friends? (Versus Duel)
  // =========================================================================
  function pickVersusPair() {
    const pool = nodes
      .map(n => profiles.get(n.id))
      .filter(p => p && p.degree >= 2);

    let a, b;
    let attempts = 0;
    do {
      a = pool[Math.floor(Math.random() * pool.length)];
      b = pool[Math.floor(Math.random() * pool.length)];
      attempts++;
    } while (
      (a.id === b.id || Math.abs(a.avgFriendDegree - b.avgFriendDegree) < 0.8) &&
      attempts < 60
    );
    return [a, b];
  }

  function setupVersusRound() {
    if (!panelDuel) return;
    const [a, b] = pickVersusPair();
    currentVersusA = a;
    currentVersusB = b;
    hasGuessedVersus = false;

    if (versusNameA) versusNameA.textContent = a.name;
    if (versusMetaA) versusMetaA.textContent = `Direct Links: ${a.degree}`;
    if (versusAvgA) versusAvgA.textContent = "???";

    if (versusNameB) versusNameB.textContent = b.name;
    if (versusMetaB) versusMetaB.textContent = `Direct Links: ${b.degree}`;
    if (versusAvgB) versusAvgB.textContent = "???";

    if (btnPickA) {
      btnPickA.disabled = false;
      btnPickA.className = "choice-pick-btn";
    }
    if (btnPickB) {
      btnPickB.disabled = false;
      btnPickB.className = "choice-pick-btn";
    }

    if (versusRevealPanel) {
      versusRevealPanel.hidden = true;
      versusRevealPanel.innerHTML = "";
    }

    // Render Dual Radars for Contender A and Contender B (Mode 1 has NO Voltmeter)
    if (versusRadarSvgA) {
      renderRadarScope(versusRadarSvgA, a, {
        ringColor: "#2849c7",
        beamStroke: "#7fa5f7",
        wedgeFill: "rgba(40, 73, 199, 0.22)",
        blipBase: "#99d5c6",
        blipBright: "#ffffff",
        waveStroke: "#7fa5f7",
        reticleColor: "#2849c7",
        reticleLabel: `CONTENDER A: ${a.name}`
      });
      if (radarLabelA) radarLabelA.textContent = `FOCUS: ${a.name.toUpperCase()} · ${a.degree} CONTACTS`;
    }

    if (versusRadarSvgB) {
      renderRadarScope(versusRadarSvgB, b, {
        ringColor: "#dc512f",
        beamStroke: "#ff9e88",
        wedgeFill: "rgba(220, 81, 47, 0.22)",
        blipBase: "#ffbc94",
        blipBright: "#ffffff",
        waveStroke: "#ff9e88",
        reticleColor: "#dc512f",
        reticleLabel: `CONTENDER B: ${b.name}`
      });
      if (radarLabelB) radarLabelB.textContent = `FOCUS: ${b.name.toUpperCase()} · ${b.degree} CONTACTS`;
    }
  }

  function handleVersusPick(pick) {
    if (hasGuessedVersus || !currentVersusA || !currentVersusB) return;
    hasGuessedVersus = true;
    inspectedCount++;

    const a = currentVersusA;
    const b = currentVersusB;
    const aWins = a.avgFriendDegree > b.avgFriendDegree;
    const userPickedA = pick === "A";
    const isCorrect = (userPickedA && aWins) || (!userPickedA && !aWins);

    if (isCorrect) {
      score += 10;
      streak++;
    } else {
      streak = 0;
    }

    if (streakDisplay) streakDisplay.textContent = String(streak);
    if (scoreDisplay) scoreDisplay.textContent = String(score);
    if (inspectedDisplay) inspectedDisplay.textContent = String(inspectedCount);

    // Reveal friend averages
    if (versusAvgA) versusAvgA.textContent = a.avgFriendDegree.toFixed(1);
    if (versusAvgB) versusAvgB.textContent = b.avgFriendDegree.toFixed(1);

    // Button states
    if (btnPickA) {
      btnPickA.disabled = true;
      btnPickA.classList.toggle("selected-winner", userPickedA && isCorrect);
      btnPickA.classList.toggle("selected-loser", userPickedA && !isCorrect);
    }
    if (btnPickB) {
      btnPickB.disabled = true;
      btnPickB.classList.toggle("selected-winner", !userPickedA && isCorrect);
      btnPickB.classList.toggle("selected-loser", !userPickedA && !isCorrect);
    }

    // Render versus reveal panel (NO Voltmeter spoiler)
    if (!versusRevealPanel) return;
    const winner = aWins ? a : b;
    const topWinFriend = winner.topFriend ? nameOf(winner.topFriend) : "a major hub";
    const diff = Math.abs(a.avgFriendDegree - b.avgFriendDegree).toFixed(1);

    versusRevealPanel.hidden = false;
    versusRevealPanel.innerHTML = `
      <div class="verdict-bar">
        <div class="verdict-banner ${isCorrect ? 'verdict-correct' : 'verdict-wrong'}">
          <span class="verdict-icon">${isCorrect ? '✓' : '✗'}</span>
          <strong>${isCorrect ? 'EXCELLENT INTUITION! +10 PTS' : 'NOT QUITE! POPULARITY TRAP FOOLED YOU'}</strong>
        </div>
        <button type="button" class="button button-primary button-small" id="versus-next-btn">Next Matchup ↗</button>
      </div>
      <div class="duel-comparison-cards">
        <div class="duel-comp-card hero-comp">
          <span class="eyebrow">${escapeHtml(a.name)} FRIENDS</span>
          <div class="comp-degree ${aWins ? 'higher' : 'lower'}">${a.avgFriendDegree.toFixed(1)}</div>
          <span class="comp-label">⟨<em>k</em><sub>friends</sub>⟩ (${a.degree} links)</span>
        </div>
        <div class="duel-comp-vs">VS</div>
        <div class="duel-comp-card friend-comp">
          <span class="eyebrow">${escapeHtml(b.name)} FRIENDS</span>
          <div class="comp-degree ${!aWins ? 'higher' : 'lower'}">${b.avgFriendDegree.toFixed(1)}</div>
          <span class="comp-label">⟨<em>k</em><sub>friends</sub>⟩ (${b.degree} links)</span>
        </div>
      </div>
      <p class="duel-explanation" style="margin-top: 10px;">
        <strong>The Driving Force:</strong> <strong>${escapeHtml(winner.name)}</strong> wins with <strong>+${diff}</strong> links on average.
        Connecting to titan hubs like <strong>${escapeHtml(topWinFriend)}</strong> (${winner.maxFriendDegree} links) dramatically elevates their friend circle!
      </p>
    `;

    const nextBtn = document.getElementById("versus-next-btn");
    if (nextBtn) nextBtn.addEventListener("click", setupVersusRound);
  }

  // =========================================================================
  // Tab Switching between Mode 1 (Versus) and Mode 2 (Single Hero Paradox)
  // =========================================================================
  if (tabDuelMode && tabParadoxMode) {
    tabDuelMode.addEventListener("click", () => {
      tabDuelMode.classList.add("active");
      tabDuelMode.setAttribute("aria-selected", "true");
      tabParadoxMode.classList.remove("active");
      tabParadoxMode.setAttribute("aria-selected", "false");

      if (panelDuel) panelDuel.hidden = false;
      if (panelParadox) panelParadox.hidden = true;

      updateBriefing("duel");
    });

    tabParadoxMode.addEventListener("click", () => {
      tabParadoxMode.classList.add("active");
      tabParadoxMode.setAttribute("aria-selected", "true");
      tabDuelMode.classList.remove("active");
      tabDuelMode.setAttribute("aria-selected", "false");

      if (panelParadox) panelParadox.hidden = false;
      if (panelDuel) panelDuel.hidden = true;

      updateBriefing("paradox");

      // Update Voltmeter legend for single-hero mode
      const p = profiles.get(selectedHeroId);
      if (labelLegendA) labelLegendA.innerHTML = "Hero Degree (<em>k</em>)";
      if (labelLegendB) labelLegendB.innerHTML = "Friends' Avg (⟨<em>k</em><sub>friends</sub>⟩)";

      if (p) {
        if (needleHero) animateNeedle(needleHero, p.degree, 95);
        if (needleFriend) animateNeedle(needleFriend, hasGuessedCurrent ? p.avgFriendDegree : 0, 90);
        if (radarSvg) {
          renderRadarScope(radarSvg, p, {
            ringColor: "#2849c7",
            beamStroke: "#99d5c6",
            wedgeFill: "rgba(40, 73, 199, 0.22)",
            blipBase: "#99d5c6",
            blipBright: "#ffffff",
            waveStroke: "#99d5c6",
            reticleColor: "#dc512f",
            reticleLabel: p.name
          });
        }
      }
    });
  }

  // Event Listeners - Mode 1 Versus
  if (btnPickA) btnPickA.addEventListener("click", () => handleVersusPick("A"));
  if (btnPickB) btnPickB.addEventListener("click", () => handleVersusPick("B"));
  if (versusRandomBtn) versusRandomBtn.addEventListener("click", setupVersusRound);

  // Event Listeners - Mode 2 Single Hero Paradox
  if (searchForm) {
    searchForm.addEventListener("submit", e => {
      e.preventDefault();
      const val = searchInput.value.trim().toLowerCase();
      if (!val) return;
      const found = nodes.find(n => n.id.toLowerCase() === val || nameOf(n).toLowerCase() === val || n.label.toLowerCase() === val);
      if (found) {
        renderHero(found.id);
      }
    });
  }

  if (randomBtn) {
    randomBtn.addEventListener("click", () => pickRandomHero());
  }

  chipButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      const heroId = btn.dataset.hero;
      if (heroId) renderHero(heroId);
    });
  });

  if (guessFriendBtn) {
    guessFriendBtn.addEventListener("click", () => handleGuess(true));
  }

  if (guessHeroBtn) {
    guessHeroBtn.addEventListener("click", () => handleGuess(false));
  }

  // Initial renders
  if (panelDuel) {
    updateBriefing("duel");
    setupVersusRound();
  }
  if (heroCard) {
    renderHero(selectedHeroId);
  }

  // =========================================================================
  // Part 2: Multiverse Rewirer (Null Model Dial & Quiz)
  // =========================================================================
  const nullModes = [
    {
      id: "real",
      name: "Real Marvel Network",
      badge: "OBSERVED UNIVERSE",
      desc: "The frozen Wikipedia hyperlink network with all human, thematic, and comic crossover relationships intact.",
      c: "0.320",
      cFill: "100%",
      t: "0.182",
      tFill: "100%",
      paradox: "87.4%",
      paradoxFill: "87.4%",
      isolates: "17",
      isolatesFill: "100%",
      reciprocity: "39.0%",
      reciprocityFill: "100%"
    },
    {
      id: "swap",
      name: "Degree-Preserving Shuffle (Double Edge Swap)",
      badge: "NULL MODEL 01 · DEGREE CONSERVED",
      desc: "1,000 double edge swaps: (u,v) + (x,y) → (u,y) + (x,v). Degrees and variance remain mathematically identical; triad wiring is randomized.",
      c: "0.155",
      cFill: "48.4%",
      t: "0.119",
      tFill: "65.4%",
      paradox: "76.5%",
      paradoxFill: "76.5%",
      isolates: "17",
      isolatesFill: "100%",
      reciprocity: "~3.0%",
      reciprocityFill: "7.7%"
    },
    {
      id: "er",
      name: "Erdős–Rényi Randomizer G(n, m)",
      badge: "NULL MODEL 02 · UNIFORM RANDOM",
      desc: "All nodes have identical link probabilities p ≈ 〈k〉/N. Degree distribution collapses to thin-tailed Poisson; zero hubs.",
      c: "0.037",
      cFill: "11.6%",
      t: "0.037",
      tFill: "20.3%",
      paradox: "54.7%",
      paradoxFill: "54.7%",
      isolates: "~0 (0.02)",
      isolatesFill: "0.5%",
      reciprocity: "~1.5%",
      reciprocityFill: "3.8%"
    }
  ];

  let currentNullIndex = 0;
  const nullToggleButtons = document.querySelectorAll("[data-null-mode]");
  const nullDesc = document.getElementById("null-mode-desc");
  const nullBadge = document.getElementById("null-mode-badge");

  const valC = document.getElementById("null-val-c");
  const fillC = document.getElementById("null-fill-c");
  const valT = document.getElementById("null-val-t");
  const fillT = document.getElementById("null-fill-t");
  const valParadox = document.getElementById("null-val-paradox");
  const fillParadox = document.getElementById("null-fill-paradox");
  const valIsolates = document.getElementById("null-val-isolates");
  const fillIsolates = document.getElementById("null-fill-isolates");
  const valReciprocity = document.getElementById("null-val-reciprocity");
  const fillReciprocity = document.getElementById("null-fill-reciprocity");

  function setNullMode(index) {
    currentNullIndex = index;
    const m = nullModes[index];

    nullToggleButtons.forEach((btn, i) => {
      const active = i === index;
      btn.classList.toggle("active", active);
      btn.setAttribute("aria-pressed", String(active));
    });

    if (nullBadge) nullBadge.textContent = m.badge;
    if (nullDesc) nullDesc.textContent = m.desc;

    if (valC) valC.textContent = m.c;
    if (fillC) fillC.style.width = m.cFill;

    if (valT) valT.textContent = m.t;
    if (fillT) fillT.style.width = m.tFill;

    if (valParadox) valParadox.textContent = m.paradox;
    if (fillParadox) fillParadox.style.width = m.paradoxFill;

    if (valIsolates) valIsolates.textContent = m.isolates;
    if (fillIsolates) fillIsolates.style.width = m.isolatesFill;

    if (valReciprocity) valReciprocity.textContent = m.reciprocity;
    if (fillReciprocity) fillReciprocity.style.width = m.reciprocityFill;
  }

  nullToggleButtons.forEach((btn, i) => {
    btn.addEventListener("click", () => setNullMode(i));
  });

  // Multiverse Quiz (Interactive Question)
  const quizCards = document.querySelectorAll(".null-metric-card[data-survives]");
  const quizFeedback = document.getElementById("quiz-feedback");

  quizCards.forEach(card => {
    card.addEventListener("click", () => {
      const survives = card.dataset.survives === "true";
      const name = card.dataset.metricName;
      if (!quizFeedback) return;

      quizFeedback.hidden = false;
      if (survives) {
        quizFeedback.className = "quiz-feedback-box correct";
        quizFeedback.innerHTML = `
          <strong>✓ CORRECT: ${name} SURVIVES!</strong>
          Because a degree-preserving edge swap strictly conserves the degree sequence of every node,
          degree-dependent properties (such as the 17 isolated heroes and the variance-driven Friendship Paradox) remain 100% intact!
        `;
      } else {
        quizFeedback.className = "quiz-feedback-box wrong";
        quizFeedback.innerHTML = `
          <strong>✗ CASUALTY: ${name} DIES!</strong>
          Double edge swaps rewire links across disparate parts of the universe. Triads and reciprocal handshakes shatter, cutting clustering in half and destroying reciprocity.
        `;
      }
    });
  });

  // =========================================================================
  // Part 3: Interactive Figure Switchers for Week 2 Field Notes
  // =========================================================================
  const ccdfImg = document.getElementById("ccdf-switch-img");
  const ccdfDownload = document.getElementById("ccdf-download-link");
  const ccdfCaption = document.getElementById("ccdf-switch-caption");
  const ccdfButtons = document.querySelectorAll("[data-ccdf-view]");

  if (ccdfImg && ccdfButtons.length > 0) {
    const views = {
      models: {
        src: "assets/figures/ccdf-models.svg",
        alt: "Log-log CCDF comparison between Marvel in-degree, Barabási-Albert, and Erdős-Rényi.",
        caption: "Marvel closely follows the Barabási–Albert heavy tail up to k ≈ 35, completely separating from the thin-tailed Poisson distribution of Erdős–Rényi."
      },
      fit: {
        src: "assets/figures/ccdf-fit.svg",
        alt: "Empirical power-law fit slope of -1.35 and the discrete quantal steps in the tail past k=35.",
        caption: "Fitted power-law slope = −1.351 (implied γ = 2.351) over [2, 35]. Past k = 35, the tail shatters into discrete steps because only 5 characters exist."
      }
    };

    ccdfButtons.forEach(btn => {
      btn.addEventListener("click", () => {
        const key = btn.dataset.ccdfView;
        const v = views[key];
        if (!v) return;

        ccdfButtons.forEach(b => {
          b.classList.toggle("active", b === btn);
          b.setAttribute("aria-pressed", String(b === btn));
        });

        const rootPrefix = document.body.dataset.root || "";
        ccdfImg.src = rootPrefix + v.src;
        ccdfImg.alt = v.alt;
        if (ccdfDownload) ccdfDownload.href = rootPrefix + v.src;
        if (ccdfCaption) ccdfCaption.textContent = v.caption;
      });
    });
  }

  const nullImg = document.getElementById("null-switch-img");
  const nullDownload = document.getElementById("null-download-link");
  const nullCaption = document.getElementById("null-switch-caption");
  const nullButtons = document.querySelectorAll("[data-null-view]");

  if (nullImg && nullButtons.length > 0) {
    const nullViews = {
      clustering: {
        src: "assets/figures/clustering-nulls.svg",
        alt: "Histograms of clustering coefficient across Erdős-Rényi, Double Edge Swap, and real Marvel.",
        caption: "Double edge swap null (C ≈ 0.155) explains half of clustering via degree sequence; real Marvel (C = 0.320) has double that due to team alliances."
      },
      growth: {
        src: "assets/figures/growth-models.svg",
        alt: "Preferential attachment growth versus uniform growth.",
        caption: "Preferential attachment is the essential ingredient that creates heavy tails; uniform growth produces an exponential cutoff dying at k ≈ 20."
      }
    };

    nullButtons.forEach(btn => {
      btn.addEventListener("click", () => {
        const key = btn.dataset.nullView;
        const v = nullViews[key];
        if (!v) return;

        nullButtons.forEach(b => {
          b.classList.toggle("active", b === btn);
          b.setAttribute("aria-pressed", String(b === btn));
        });

        const rootPrefix = document.body.dataset.root || "";
        nullImg.src = rootPrefix + v.src;
        nullImg.alt = v.alt;
        if (nullDownload) nullDownload.href = rootPrefix + v.src;
        if (nullCaption) nullCaption.textContent = v.caption;
      });
    });
  }
})();
