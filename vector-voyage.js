// Vector Voyage / Vector Drift: 3D Marvel Semantic Manifold Navigation
(function () {
  'use strict';

  let data = null;
  let activeMissionIdx = 0;
  let currentMission = null;
  let startChar = null;
  let targetChar = null;
  let history = []; // array of { word, sign, weight, x, y, z, dx, dy, dz }
  let currentSign = 1; // 1 = add (+), -1 = subtract (-)
  let currentWeight = 1.0;
  let isVictorious = false;
  let showCoordinates = false;

  // Viewport & 3D Camera State
  let viewMode = '3d'; // '3d' or '2d'
  let yaw = -0.55;     // horizontal rotation (radians)
  let pitch = 0.32;    // vertical elevation (radians)
  let zoom = 1.0;      // zoom factor (0.45 to 3.8)
  let panX = 0;        // screen pan X
  let panY = 0;        // screen pan Y

  // Interaction State
  let isDragging = false;
  let dragStartX = 0;
  let dragStartY = 0;
  let dragStartYaw = 0;
  let dragStartPitch = 0;
  let dragStartPanX = 0;
  let dragStartPanY = 0;
  let hoveredEntity = null;
  let mouseScreenPos = { x: -1, y: -1 };
  let animFrameId = null;

  // DOM Elements
  const container = document.getElementById('vv-container');
  if (!container) return;

  const canvas = document.getElementById('vv-stage-canvas');
  const stageWrap = document.getElementById('vv-stage-wrap');
  const tooltip = document.getElementById('vv-tooltip');

  function initGame() {
    data = window.CROSSTALK_VECTOR_GAME;
    if (!data) {
      console.error('Game data not found.');
      return;
    }
    renderMissionTabs();
    selectMission(0);
    renderPalette();
    bindGlobalControls();
    initCanvasEvents();
    startAnimationLoop();
  }

  function getCharacterById(id) {
    return data.characters.find(c => c.id === id);
  }

  function getWordObj(w) {
    for (const cat of data.palette) {
      for (const item of cat.words) {
        if (item.word.toLowerCase() === w.toLowerCase()) return item;
      }
    }
    return null;
  }

  function selectMission(idx) {
    activeMissionIdx = idx;
    currentMission = data.missions[idx];
    startChar = getCharacterById(currentMission.start) || data.characters[0];
    targetChar = getCharacterById(currentMission.target) || data.characters[1];
    
    history = [{
      word: startChar.label,
      sign: 1,
      weight: 1.0,
      x: startChar.x,
      y: startChar.y,
      z: startChar.z,
      dx: 0,
      dy: 0,
      dz: 0
    }];
    isVictorious = false;

    // Reset camera nicely for new mission
    yaw = -0.55;
    pitch = 0.32;
    zoom = 1.0;
    panX = 0;
    panY = 0;

    updateMissionUI();
    updateTelemetry();
    renderStage();
  }

  function renderMissionTabs() {
    const tabsContainer = document.getElementById('vv-mission-tabs');
    if (!tabsContainer) return;
    tabsContainer.innerHTML = '';

    data.missions.forEach((m, idx) => {
      const btn = document.createElement('button');
      btn.className = 'vv-mission-tab';
      btn.type = 'button';
      btn.setAttribute('aria-selected', idx === activeMissionIdx ? 'true' : 'false');
      btn.innerHTML = `<span class="step-num">MISSION 0${idx + 1}</span><strong>${m.title}</strong>`;
      btn.addEventListener('click', () => {
        document.querySelectorAll('.vv-mission-tab').forEach(t => t.setAttribute('aria-selected', 'false'));
        btn.setAttribute('aria-selected', 'true');
        selectMission(idx);
      });
      tabsContainer.appendChild(btn);
    });
  }

  function updateMissionUI() {
    document.getElementById('vv-mission-title').textContent = currentMission.title;
    document.getElementById('vv-mission-briefing').textContent = currentMission.briefing;

    // Origin Card Profile
    document.getElementById('vv-start-name').textContent = startChar.label;
    const startDescEl = document.getElementById('vv-start-desc');
    if (startDescEl) startDescEl.textContent = currentMission.start_desc || startChar.description;
    const startCoordsEl = document.getElementById('vv-start-coords');
    if (startCoordsEl) {
      startCoordsEl.innerHTML = showCoordinates
        ? `<code>X: ${startChar.x > 0 ? '+' : ''}${startChar.x} · Y: ${startChar.y > 0 ? '+' : ''}${startChar.y} · Z: ${startChar.z > 0 ? '+' : ''}${startChar.z}</code>`
        : `<span class="masked-coord">[CLASSIFIED · Click Reveal Coordinates]</span>`;
    }

    // Destination Card Profile
    document.getElementById('vv-target-name').textContent = targetChar.label;
    const targetDescEl = document.getElementById('vv-target-desc');
    if (targetDescEl) targetDescEl.textContent = currentMission.target_desc || targetChar.description;
    const targetCoordsEl = document.getElementById('vv-target-coords');
    if (targetCoordsEl) {
      targetCoordsEl.innerHTML = showCoordinates
        ? `<code>X: ${targetChar.x > 0 ? '+' : ''}${targetChar.x} · Y: ${targetChar.y > 0 ? '+' : ''}${targetChar.y} · Z: ${targetChar.z > 0 ? '+' : ''}${targetChar.z}</code>`
        : `<span class="masked-coord">[CLASSIFIED · Click Reveal Coordinates]</span>`;
    }
    const thresholdEl = document.getElementById('vv-target-threshold');
    if (thresholdEl) thresholdEl.textContent = `Goal: Dist ≤ ${currentMission.max_distance}`;
    
    const receipt = document.getElementById('vv-receipt-box');
    if (receipt) receipt.hidden = true;
    hideHeroCelebration();
  }

  function applyStep(wordStr, sign, weight) {
    if (isVictorious) return;
    const wObj = getWordObj(wordStr);
    if (!wObj) {
      alert(`Word "${wordStr}" is not in the curated 3D palette.`);
      return;
    }

    // 3D coordinate vector addition: P_new = P_curr + sign * weight * Delta
    const last = history[history.length - 1];
    const nx = Math.max(-100, Math.min(100, Math.round((last.x + sign * weight * wObj.dx) * 10) / 10));
    const ny = Math.max(-100, Math.min(100, Math.round((last.y + sign * weight * wObj.dy) * 10) / 10));
    const nz = Math.max(-100, Math.min(100, Math.round((last.z + sign * weight * wObj.dz) * 10) / 10));

    history.push({
      word: wordStr,
      sign: sign,
      weight: weight,
      dx: wObj.dx,
      dy: wObj.dy,
      dz: wObj.dz,
      x: nx,
      y: ny,
      z: nz
    });

    updateTelemetry();
    renderStage();
    checkVictory();
  }

  function undoStep() {
    if (history.length <= 1) return;
    history.pop();
    isVictorious = false;
    updateTelemetry();
    renderStage();
    const receipt = document.getElementById('vv-receipt-box');
    if (receipt) receipt.hidden = true;
    hideHeroCelebration();
  }

  function resetMission() {
    selectMission(activeMissionIdx);
  }

  function giveHint() {
    if (isVictorious) return;
    const last = history[history.length - 1];
    let bestWord = null;
    let minFutureDist = 9999;

    for (const cat of data.palette) {
      for (const wItem of cat.words) {
        const testX = last.x + 1.0 * wItem.dx;
        const testY = last.y + 1.0 * wItem.dy;
        const testZ = last.z + 1.0 * wItem.dz;
        const testDist = Math.hypot(targetChar.x - testX, targetChar.y - testY, targetChar.z - testZ);
        if (testDist < minFutureDist) {
          minFutureDist = testDist;
          bestWord = wItem.word;
        }
      }
    }

    if (bestWord) {
      const curDist = Math.hypot(targetChar.x - last.x, targetChar.y - last.y, targetChar.z - last.z);
      const gain = (curDist - minFutureDist).toFixed(1);
      alert(`Semantic 3D Radar Hint: Adding "+ ${bestWord}" steers directly toward ${targetChar.label} (reduces 3D distance by ${gain} units)!`);
      applyStep(bestWord, 1, 1.0);
    }
  }

  function getNearestCharacters3D(curX, curY, curZ, topK = 3) {
    const scored = data.characters.map(c => {
      const d = Math.hypot(c.x - curX, c.y - curY, c.z - curZ);
      return {
        label: c.label,
        category: c.category,
        distance: d,
        simPercent: Math.max(0, Math.min(100, Math.round(100 - d)))
      };
    });
    scored.sort((a, b) => a.distance - b.distance);
    return scored.slice(0, topK);
  }

  function updateTelemetry() {
    const last = history[history.length - 1];
    const dx = targetChar.x - last.x;
    const dy = targetChar.y - last.y;
    const dz = targetChar.z - last.z;
    const dist = Math.hypot(dx, dy, dz);
    const initDist = Math.hypot(targetChar.x - startChar.x, targetChar.y - startChar.y, targetChar.z - startChar.z);
    
    // Proximity percent: 100% when right on target
    const proximity = Math.max(0, Math.min(100, Math.round(100 * (1 - dist / (initDist + 15)))));

    // Proximity and Distance Readout
    document.getElementById('vv-similarity-val').textContent = proximity + '%';
    const fill = document.getElementById('vv-proximity-fill');
    if (fill) fill.style.width = proximity + '%';

    const distEl = document.getElementById('vv-distance-val');
    if (distEl) {
      distEl.textContent = `3D Distance: ${dist.toFixed(1)} · Goal: ≤ ${currentMission.max_distance}`;
    }

    // Moves and Remaining Deltas
    const moveCount = history.length - 1;
    document.getElementById('vv-move-count').textContent = moveCount;
    document.getElementById('vv-par-moves').textContent = currentMission.par_moves;

    const deltaEl = document.getElementById('vv-delta-readout');
    if (deltaEl) {
      deltaEl.innerHTML = showCoordinates
        ? `Needed: <code>ΔX(Magic): ${dx > 0 ? '+' : ''}${dx.toFixed(1)} · ΔY(Cosmic): ${dy > 0 ? '+' : ''}${dy.toFixed(1)} · ΔZ(Mind): ${dz > 0 ? '+' : ''}${dz.toFixed(1)}</code>`
        : `Remaining: <span class="masked-coord">ΔX: ??? · ΔY: ??? · ΔZ: ???</span> <small style="color:var(--ink-muted); font-size:10px;">(Coordinates hidden)</small>`;
    }

    // Equation readout
    let eqParts = [
      showCoordinates
        ? `${startChar.label} <small>[${startChar.x}, ${startChar.y}, ${startChar.z}]</small>`
        : `<strong>${startChar.label}</strong>`
    ];
    for (let i = 1; i < history.length; i++) {
      const step = history[i];
      const signStr = step.sign > 0 ? '+' : '−';
      eqParts.push(`${signStr} <span class="step-token">${step.word}</span>`);
    }
    const targetEq = showCoordinates
      ? `<em>${targetChar.label} <small>[${targetChar.x}, ${targetChar.y}, ${targetChar.z}]</small></em>`
      : `<em>${targetChar.label}</em>`;
    const eqHtml = eqParts.join(' ') + ` <span style="color:#94a3b8">≈</span> ${targetEq}`;
    document.getElementById('vv-equation').innerHTML = eqHtml;

    // Nearest characters radar
    const nearest = getNearestCharacters3D(last.x, last.y, last.z, 3);
    const radarContainer = document.getElementById('vv-radar-tags');
    if (radarContainer) {
      radarContainer.innerHTML = '';
      nearest.forEach((item, idx) => {
        const tag = document.createElement('span');
        tag.className = 'vv-radar-tag' + (idx === 0 ? ' top-match' : '');
        tag.innerHTML = `<strong>${item.label}</strong> (Dist: ${item.distance.toFixed(1)})`;
        radarContainer.appendChild(tag);
      });
    }
  }

  function checkVictory() {
    const last = history[history.length - 1];
    const dist = Math.hypot(targetChar.x - last.x, targetChar.y - last.y, targetChar.z - last.z);

    if (dist <= currentMission.max_distance && !isVictorious) {
      isVictorious = true;
      const moves = history.length - 1;
      const par = currentMission.par_moves;
      let stars = '⭐⭐⭐';
      let title = 'Master Semanticist';
      if (moves > par + 2) {
        stars = '⭐';
        title = 'Persistent Explorer';
      } else if (moves > par) {
        stars = '⭐⭐';
        title = 'Skilled Vector Navigator';
      }

      // Update bottom receipt box
      const receipt = document.getElementById('vv-receipt-box');
      if (receipt) {
        receipt.hidden = false;
        document.getElementById('vv-stars-display').textContent = stars;
        document.getElementById('vv-receipt-title').textContent = `Destination Reached: ${targetChar.label}!`;
        document.getElementById('vv-receipt-desc').innerHTML = `
          You successfully navigated the 3-dimensional Marvel semantic manifold from <strong>${startChar.label}</strong> to <strong>${targetChar.label}</strong> in <strong>${moves} moves</strong> (Par: ${par}).<br>
          Final 3D Distance: <strong>${dist.toFixed(1)} units</strong> (Target threshold: ≤ ${currentMission.max_distance}). Rank: <em>${title}</em>.
        `;
      }

      // Trigger On-Screen Marvel Superhero Victory Animation
      triggerHeroVictoryAnimation(targetChar, dist, moves, par);
    }
  }

  // -------------------------------------------------------------------------
  // Marvel Superhero Victory Celebration & Particle Visualizer
  // -------------------------------------------------------------------------
  let fxAnimId = null;

  const HERO_THEMES = {
    'Doctor_Strange': {
      mode: 'mystic',
      icon: '✨',
      accent: '#f59e0b',
      glow: 'rgba(245, 158, 11, 0.7)',
      eyebrow: 'MYSTIC DIMENSION CONQUERED · SORCERER SUPREME',
      quote: '“By the Eye of Agamotto! The mystic barrier has parted.”'
    },
    'Jean_Grey': {
      mode: 'phoenix',
      icon: '🔥',
      accent: '#ef4444',
      glow: 'rgba(239, 68, 68, 0.7)',
      eyebrow: 'OMEGA-LEVEL PSIONIC HARMONY · PHOENIX EMBODIMENT',
      quote: '“The Phoenix rises from the ashes of thought! Psionic connection established.”'
    },
    'Phoenix_Force': {
      mode: 'cosmic',
      icon: '🌌',
      accent: '#ec4899',
      glow: 'rgba(236, 72, 153, 0.7)',
      eyebrow: 'CELESTIAL SUPERNOVA · PRIMORDIAL COSMIC ENTITY',
      quote: '“I am life, fire, and rebirth across the infinite cosmos.”'
    },
    'Iron_Lad': {
      mode: 'cyber',
      icon: '⚡',
      accent: '#06b6d4',
      glow: 'rgba(6, 182, 212, 0.7)',
      eyebrow: 'NEURO-KINETIC ARMOR ENGAGED · 31ST CENTURY KANG TECH',
      quote: '“31st-century armor systems online. Time travel trajectory locked.”'
    },
    'Hulk': {
      mode: 'gamma',
      icon: '💥',
      accent: '#10b981',
      glow: 'rgba(16, 185, 129, 0.7)',
      eyebrow: 'GAMMA-RAY TITAN SYNCHRONIZED · SMASH PROTOCOL',
      quote: '“Hulk strongest there is! Physical barrier shattered!”'
    },
    'Spider-Man': {
      mode: 'web',
      icon: '🕷️',
      accent: '#ef4444',
      glow: 'rgba(239, 68, 68, 0.7)',
      eyebrow: 'SPIDER-SENSE TINGLING · QUEENS DEFENDER',
      quote: '“With great power comes great responsibility! Street vectors locked.”'
    }
  };

  function getHeroTheme(char) {
    if (HERO_THEMES[char.id]) return HERO_THEMES[char.id];
    if (char.category === 'mystic') return HERO_THEMES['Doctor_Strange'];
    if (char.category === 'mutant') return HERO_THEMES['Jean_Grey'];
    if (char.category === 'cosmic') return HERO_THEMES['Phoenix_Force'];
    if (char.category === 'science') return HERO_THEMES['Iron_Lad'];
    return {
      mode: 'cosmic',
      icon: '⭐',
      accent: '#3874cb',
      glow: 'rgba(56, 116, 203, 0.7)',
      eyebrow: 'HERO CONVERGENCE ACHIEVED',
      quote: '“Semantic coordinates aligned across the Marvel multiverse.”'
    };
  }

  function hideHeroCelebration() {
    const overlay = document.getElementById('vv-hero-celebration');
    if (overlay) overlay.hidden = true;
    if (fxAnimId) {
      cancelAnimationFrame(fxAnimId);
      fxAnimId = null;
    }
  }

  function triggerHeroVictoryAnimation(target, dist, moves, par) {
    const overlay = document.getElementById('vv-hero-celebration');
    const fxCanvas = document.getElementById('vv-fx-canvas');
    const card = document.getElementById('vv-celebration-card');
    if (!overlay || !fxCanvas || !card) return;

    const theme = getHeroTheme(target);

    // Apply theme colors to card
    card.style.setProperty('--hero-accent', theme.accent);
    card.style.setProperty('--hero-glow', theme.glow);

    document.getElementById('vv-cel-icon').textContent = theme.icon;
    document.getElementById('vv-cel-eyebrow').textContent = theme.eyebrow;
    document.getElementById('vv-cel-title').textContent = target.label;
    document.getElementById('vv-cel-quote').textContent = theme.quote;
    document.getElementById('vv-cel-dist').textContent = dist.toFixed(1);
    document.getElementById('vv-cel-moves').textContent = `${moves} / par ${par}`;

    overlay.hidden = false;

    // Bind Close & Dismiss Handlers
    const closeBtn = document.getElementById('vv-cel-close');
    const dismissBtn = document.getElementById('vv-cel-dismiss');
    if (closeBtn) closeBtn.onclick = hideHeroCelebration;
    if (dismissBtn) dismissBtn.onclick = hideHeroCelebration;

    // Launch Superhero Themed Particle Animation
    launchHeroFx(fxCanvas, theme.mode, theme.accent);
  }

  function launchHeroFx(canvasEl, mode, accentColor) {
    if (fxAnimId) cancelAnimationFrame(fxAnimId);

    const ctx = canvasEl.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const stageContainer = document.getElementById('vv-stage-wrap');
    const W = (stageContainer ? stageContainer.clientWidth : 600) || 600;
    const H = (stageContainer ? stageContainer.clientHeight : 440) || 440;
    canvasEl.width = W * dpr;
    canvasEl.height = H * dpr;

    const startTime = performance.now();
    const cx = W / 2;
    const cy = H / 2;

    // Generate Particles
    const particles = [];
    const count = 90;
    for (let i = 0; i < count; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = 1.0 + Math.random() * 4.0;
      particles.push({
        x: cx,
        y: cy,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        radius: 1.5 + Math.random() * 3.5,
        alpha: 0.6 + Math.random() * 0.4,
        color: accentColor,
        life: 0,
        maxLife: 60 + Math.random() * 80
      });
    }

    function renderFx() {
      const elapsed = (performance.now() - startTime) / 1000;
      ctx.save();
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, W, H);

      // Mode-specific animated hero sigils
      if (mode === 'mystic') {
        // Doctor Strange: Eldritch Magic Mandala
        const rot1 = elapsed * 1.3;
        const rot2 = -elapsed * 0.9;
        const pulseR = 120 + Math.sin(elapsed * 4) * 6;

        // Outer Mandala Ring with Rune Spokes
        ctx.strokeStyle = '#f59e0b';
        ctx.lineWidth = 2.0;
        ctx.shadowColor = '#f59e0b';
        ctx.shadowBlur = 15;
        ctx.beginPath();
        ctx.arc(cx, cy, pulseR, 0, Math.PI * 2);
        ctx.stroke();

        // 12 Outer Rune Rays
        ctx.lineWidth = 1.4;
        for (let i = 0; i < 12; i++) {
          const a = rot1 + (i * Math.PI) / 6;
          const x1 = cx + Math.cos(a) * (pulseR - 12);
          const y1 = cy + Math.sin(a) * (pulseR - 12);
          const x2 = cx + Math.cos(a) * (pulseR + 14);
          const y2 = cy + Math.sin(a) * (pulseR + 14);
          ctx.beginPath();
          ctx.moveTo(x1, y1);
          ctx.lineTo(x2, y2);
          ctx.stroke();
        }

        // Inner Rotating Dodecagon
        ctx.strokeStyle = '#fbbf24';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        for (let i = 0; i < 12; i++) {
          const a = rot2 + (i * Math.PI) / 6;
          const px = cx + Math.cos(a) * 75;
          const py = cy + Math.sin(a) * 75;
          if (i === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        }
        ctx.closePath();
        ctx.stroke();

        // Central Eye of Agamotto Arcs
        ctx.strokeStyle = '#f97316';
        ctx.beginPath();
        ctx.ellipse(cx, cy, 40, 24, rot1 * 0.5, 0, Math.PI * 2);
        ctx.stroke();
      } else if (mode === 'phoenix') {
        // Jean Grey: Flaming Phoenix Wings & Psionic Shockwaves
        const flap = Math.sin(elapsed * 3.5) * 22;

        // Psionic expanding rings
        for (let r = 0; r < 3; r++) {
          const ringRad = ((elapsed * 80 + r * 60) % 180) + 20;
          const ringAlpha = Math.max(0, 1 - ringRad / 180);
          ctx.strokeStyle = `rgba(239, 68, 68, ${ringAlpha * 0.7})`;
          ctx.lineWidth = 2.0;
          ctx.beginPath();
          ctx.arc(cx, cy, ringRad, 0, Math.PI * 2);
          ctx.stroke();
        }

        // Left Flame Wing
        ctx.strokeStyle = '#f59e0b';
        ctx.shadowColor = '#ef4444';
        ctx.shadowBlur = 18;
        ctx.lineWidth = 3.0;
        ctx.beginPath();
        ctx.moveTo(cx - 20, cy + 30);
        ctx.bezierCurveTo(cx - 90, cy - 40 + flap, cx - 130, cy - 80 + flap, cx - 180, cy - 20 + flap);
        ctx.bezierCurveTo(cx - 130, cy + 10, cx - 70, cy + 20, cx - 20, cy + 30);
        ctx.stroke();

        // Right Flame Wing
        ctx.beginPath();
        ctx.moveTo(cx + 20, cy + 30);
        ctx.bezierCurveTo(cx + 90, cy - 40 + flap, cx + 130, cy - 80 + flap, cx + 180, cy - 20 + flap);
        ctx.bezierCurveTo(cx + 130, cy + 10, cx + 70, cy + 20, cx + 20, cy + 30);
        ctx.stroke();
      } else if (mode === 'cyber') {
        // Iron Lad: Cybernetic Hexagon HUD Grid & Targeting Scan
        const rot = elapsed * 0.6;
        ctx.strokeStyle = '#06b6d4';
        ctx.shadowColor = '#06b6d4';
        ctx.shadowBlur = 14;
        ctx.lineWidth = 1.8;

        // Rotating Segmented HUD Reticle
        ctx.setLineDash([18, 10]);
        ctx.beginPath();
        ctx.arc(cx, cy, 110, rot, rot + Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([8, 6]);
        ctx.beginPath();
        ctx.arc(cx, cy, 75, -rot * 1.2, -rot * 1.2 + Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);

        // Vertical Laser Scanline
        const scanY = (elapsed * 160) % H;
        ctx.strokeStyle = 'rgba(6, 182, 212, 0.45)';
        ctx.lineWidth = 2.0;
        ctx.beginPath();
        ctx.moveTo(30, scanY);
        ctx.lineTo(W - 30, scanY);
        ctx.stroke();

        // Targeting Crosshair Brackets
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 2.5;
        const bSize = 25;
        [[cx - 80, cy - 80, 1, 1], [cx + 80, cy - 80, -1, 1], [cx - 80, cy + 80, 1, -1], [cx + 80, cy + 80, -1, -1]].forEach(([bx, by, dx, dy]) => {
          ctx.beginPath();
          ctx.moveTo(bx, by + dy * bSize);
          ctx.lineTo(bx, by);
          ctx.lineTo(bx + dx * bSize, by);
          ctx.stroke();
        });
      } else {
        // Phoenix Force / Cosmic: Supernova Galaxy Spiral
        const rot = elapsed * 0.9;
        ctx.shadowColor = accentColor;
        ctx.shadowBlur = 16;
        for (let arm = 0; arm < 3; arm++) {
          ctx.strokeStyle = arm === 0 ? '#ec4899' : (arm === 1 ? '#8b5cf6' : '#38bdf8');
          ctx.lineWidth = 2.2;
          ctx.beginPath();
          for (let step = 10; step < 140; step += 8) {
            const a = rot + (arm * Math.PI * 2) / 3 + step * 0.035;
            const px = cx + Math.cos(a) * step;
            const py = cy + Math.sin(a) * step;
            if (step === 10) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
          }
          ctx.stroke();
        }
      }

      // Draw Flying Particles
      ctx.shadowBlur = 8;
      particles.forEach(p => {
        p.life++;
        p.x += p.vx;
        p.y += p.vy;
        p.alpha = Math.max(0, 1 - p.life / p.maxLife);

        ctx.fillStyle = p.color;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fill();

        // Recycle particle
        if (p.life >= p.maxLife || p.x < 0 || p.x > W || p.y < 0 || p.y > H) {
          p.x = cx + (Math.random() - 0.5) * 30;
          p.y = cy + (Math.random() - 0.5) * 30;
          const a = Math.random() * Math.PI * 2;
          const spd = 1.0 + Math.random() * 3.5;
          p.vx = Math.cos(a) * spd;
          p.vy = Math.sin(a) * spd;
          p.life = 0;
          p.alpha = 0.8;
        }
      });

      ctx.restore();
      fxAnimId = requestAnimationFrame(renderFx);
    }

    renderFx();
  }

  function renderPalette() {
    const pContainer = document.getElementById('vv-palette-categories');
    if (!pContainer) return;
    pContainer.innerHTML = '';

    data.palette.forEach(cat => {
      const group = document.createElement('div');
      group.className = 'vv-category-group';
      
      const heading = document.createElement('div');
      heading.className = 'vv-cat-heading';
      heading.innerHTML = `<strong>${cat.category}</strong> <span style="font-size:11px; font-weight:normal; color:#64748b; margin-left:6px;">— ${cat.description}</span>`;
      group.appendChild(heading);

      const chips = document.createElement('div');
      chips.className = 'vv-word-chips';

      cat.words.forEach(wObj => {
        const chip = document.createElement('button');
        chip.className = 'vv-chip';
        chip.type = 'button';
        chip.innerHTML = `<span class="chip-word">${wObj.word}</span> <span class="chip-bias">${wObj.bias}</span>`;
        chip.addEventListener('click', () => {
          applyStep(wObj.word, currentSign, currentWeight);
        });
        chips.appendChild(chip);
      });

      group.appendChild(chips);
      pContainer.appendChild(group);
    });
  }

  function bindGlobalControls() {
    // Mode buttons (+ / -)
    const addBtn = document.getElementById('vv-mode-add');
    const subBtn = document.getElementById('vv-mode-sub');
    if (addBtn && subBtn) {
      addBtn.addEventListener('click', () => {
        currentSign = 1;
        addBtn.setAttribute('aria-pressed', 'true');
        subBtn.setAttribute('aria-pressed', 'false');
      });
      subBtn.addEventListener('click', () => {
        currentSign = -1;
        subBtn.setAttribute('aria-pressed', 'true');
        addBtn.setAttribute('aria-pressed', 'false');
      });
    }

    // Step Weight Buttons
    const wHalf = document.getElementById('vv-w-half');
    const wOne = document.getElementById('vv-w-one');
    const wOneHalf = document.getElementById('vv-w-onehalf');
    if (wHalf && wOne && wOneHalf) {
      const setWeight = (w, activeBtn) => {
        currentWeight = w;
        [wHalf, wOne, wOneHalf].forEach(b => b.classList.remove('active-weight'));
        activeBtn.classList.add('active-weight');
      };
      wHalf.addEventListener('click', () => setWeight(0.5, wHalf));
      wOne.addEventListener('click', () => setWeight(1.0, wOne));
      wOneHalf.addEventListener('click', () => setWeight(1.5, wOneHalf));
    }

    // Undo, Reset, Hint
    const undoBtn = document.getElementById('vv-undo-btn');
    if (undoBtn) undoBtn.addEventListener('click', undoStep);

    const resetBtn = document.getElementById('vv-reset-btn');
    if (resetBtn) resetBtn.addEventListener('click', resetMission);

    const hintBtn = document.getElementById('vv-hint-btn');
    if (hintBtn) hintBtn.addEventListener('click', giveHint);

    // Reveal / Hide Coordinates Toggle
    const coordsToggleBtn = document.getElementById('vv-coords-toggle');
    if (coordsToggleBtn) {
      coordsToggleBtn.addEventListener('click', () => {
        showCoordinates = !showCoordinates;
        coordsToggleBtn.setAttribute('aria-pressed', showCoordinates ? 'true' : 'false');
        if (showCoordinates) {
          coordsToggleBtn.classList.add('active-toggle');
          coordsToggleBtn.innerHTML = '🔒 Hide Coordinates';
        } else {
          coordsToggleBtn.classList.remove('active-toggle');
          coordsToggleBtn.innerHTML = '🔍 Reveal Coordinates';
        }
        updateMissionUI();
        updateTelemetry();
        renderStage();
      });
    }

    // Custom search input
    const customInput = document.getElementById('vv-custom-word');
    const customBtn = document.getElementById('vv-custom-submit');
    if (customInput && customBtn) {
      const handleCustom = () => {
        const val = customInput.value.trim().toLowerCase();
        if (val) {
          applyStep(val, currentSign, currentWeight);
          customInput.value = '';
        }
      };
      customBtn.addEventListener('click', handleCustom);
      customInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleCustom();
      });
    }

    // 3D vs 2D Toggle
    const btn3D = document.getElementById('vv-view-3d');
    const btn2D = document.getElementById('vv-view-2d');
    const hintText = document.getElementById('vv-stage-hint');

    if (btn3D && btn2D) {
      btn3D.addEventListener('click', () => {
        viewMode = '3d';
        btn3D.classList.add('active');
        btn3D.setAttribute('aria-pressed', 'true');
        btn2D.classList.remove('active');
        btn2D.setAttribute('aria-pressed', 'false');
        if (hintText) hintText.textContent = 'Drag mouse to orbit · Scroll to zoom · Hover dots for details';
        renderStage();
      });

      btn2D.addEventListener('click', () => {
        viewMode = '2d';
        btn2D.classList.add('active');
        btn2D.setAttribute('aria-pressed', 'true');
        btn3D.classList.remove('active');
        btn3D.setAttribute('aria-pressed', 'false');
        if (hintText) hintText.textContent = 'Drag mouse to pan · Scroll to zoom · Hover dots for details';
        renderStage();
      });
    }

    // Zoom Buttons
    const btnZoomIn = document.getElementById('vv-zoom-in');
    const btnZoomOut = document.getElementById('vv-zoom-out');
    const btnZoomReset = document.getElementById('vv-zoom-reset');

    if (btnZoomIn) {
      btnZoomIn.addEventListener('click', () => {
        zoom = Math.min(3.8, zoom * 1.25);
        renderStage();
      });
    }
    if (btnZoomOut) {
      btnZoomOut.addEventListener('click', () => {
        zoom = Math.max(0.45, zoom * 0.8);
        renderStage();
      });
    }
    if (btnZoomReset) {
      btnZoomReset.addEventListener('click', () => {
        zoom = 1.0;
        panX = 0;
        panY = 0;
        yaw = -0.55;
        pitch = 0.32;
        renderStage();
      });
    }
  }

  // -------------------------------------------------------------------------
  // Interactive Canvas & 3D Projection Engine
  // -------------------------------------------------------------------------

  function initCanvasEvents() {
    if (!canvas || !stageWrap) return;

    // Mouse drag
    stageWrap.addEventListener('mousedown', (e) => {
      if (e.button !== 0) return;
      isDragging = true;
      stageWrap.classList.add('is-dragging');
      dragStartX = e.clientX;
      dragStartY = e.clientY;
      dragStartYaw = yaw;
      dragStartPitch = pitch;
      dragStartPanX = panX;
      dragStartPanY = panY;
    });

    window.addEventListener('mousemove', (e) => {
      const rect = canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;
      mouseScreenPos = { x: mouseX, y: mouseY };

      if (isDragging) {
        const dx = e.clientX - dragStartX;
        const dy = e.clientY - dragStartY;

        if (viewMode === '3d') {
          yaw = dragStartYaw + dx * 0.009;
          pitch = Math.max(-1.35, Math.min(1.35, dragStartPitch + dy * 0.009));
        } else {
          panX = dragStartPanX + dx;
          panY = dragStartPanY + dy;
        }
        renderStage();
      } else if (mouseX >= 0 && mouseX <= rect.width && mouseY >= 0 && mouseY <= rect.height) {
        checkHover(mouseX, mouseY);
      } else {
        hideTooltip();
      }
    });

    window.addEventListener('mouseup', () => {
      if (isDragging) {
        isDragging = false;
        stageWrap.classList.remove('is-dragging');
      }
    });

    // Mouse wheel zoom
    stageWrap.addEventListener('wheel', (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.12 : 0.89;
      zoom = Math.max(0.45, Math.min(3.8, zoom * zoomFactor));
      renderStage();
      checkHover(mouseScreenPos.x, mouseScreenPos.y);
    }, { passive: false });

    // Touch support
    let touchStartX = 0, touchStartY = 0;
    stageWrap.addEventListener('touchstart', (e) => {
      if (e.touches.length === 1) {
        isDragging = true;
        touchStartX = e.touches[0].clientX;
        touchStartY = e.touches[0].clientY;
        dragStartYaw = yaw;
        dragStartPitch = pitch;
        dragStartPanX = panX;
        dragStartPanY = panY;
      }
    }, { passive: true });

    stageWrap.addEventListener('touchmove', (e) => {
      if (!isDragging || e.touches.length !== 1) return;
      const dx = e.touches[0].clientX - touchStartX;
      const dy = e.touches[0].clientY - touchStartY;
      if (viewMode === '3d') {
        yaw = dragStartYaw + dx * 0.01;
        pitch = Math.max(-1.35, Math.min(1.35, dragStartPitch + dy * 0.01));
      } else {
        panX = dragStartPanX + dx;
        panY = dragStartPanY + dy;
      }
      renderStage();
    }, { passive: true });

    stageWrap.addEventListener('touchend', () => {
      isDragging = false;
    });
  }

  function checkHover(screenX, screenY) {
    if (!data || !canvas) return;
    const candidates = [];

    // Check characters
    data.characters.forEach(c => {
      const p = projectPoint(c.x, c.y, c.z);
      if (!p.visible) return;
      const dist = Math.hypot(p.x - screenX, p.y - screenY);
      if (dist < 16) {
        candidates.push({ type: 'character', data: c, screenX: p.x, screenY: p.y, dist });
      }
    });

    // Check trajectory points
    history.forEach((h, idx) => {
      const p = projectPoint(h.x, h.y, h.z);
      if (!p.visible) return;
      const dist = Math.hypot(p.x - screenX, p.y - screenY);
      if (dist < 14) {
        candidates.push({ type: 'step', data: h, idx, screenX: p.x, screenY: p.y, dist });
      }
    });

    if (candidates.length > 0) {
      candidates.sort((a, b) => a.dist - b.dist);
      const match = candidates[0];
      hoveredEntity = match;
      canvas.style.cursor = 'pointer';
      showTooltip(match);
    } else {
      hoveredEntity = null;
      canvas.style.cursor = isDragging ? 'grabbing' : 'grab';
      hideTooltip();
    }
  }

  function showTooltip(match) {
    if (!tooltip) return;
    let html = '';
    if (match.type === 'character') {
      const c = match.data;
      const last = history[history.length - 1];
      const distToCurrent = Math.hypot(c.x - last.x, c.y - last.y, c.z - last.z);
      const coordsDisplay = showCoordinates
        ? `<div style="font-size:9px; color:#94a3b8;">3D COORDS: [X:${c.x}, Y:${c.y}, Z:${c.z}]</div>`
        : `<div style="font-size:9px; color:#64748b;">3D COORDS: <span style="font-style:italic;">[CLASSIFIED]</span></div>`;
      html = `
        <div style="font-weight:bold; color:#38bdf8; margin-bottom:2px;">${c.label}</div>
        <div style="font-size:9px; color:#cbd5e1; margin-bottom:3px; max-width:210px; line-height:1.3;">${c.description}</div>
        ${coordsDisplay}
        <div style="font-size:9px; color:#e2e8f0; margin-top:2px;">DIST TO CURRENT: <strong>${distToCurrent.toFixed(1)}</strong></div>
      `;
    } else if (match.type === 'step') {
      const s = match.data;
      const signStr = s.sign > 0 ? '+' : '−';
      const posDisplay = showCoordinates
        ? `<div style="font-size:9px; color:#38bdf8;">POSITION: [X:${s.x}, Y:${s.y}, Z:${s.z}]</div>`
        : `<div style="font-size:9px; color:#64748b;">POSITION: <span style="font-style:italic;">[CLASSIFIED]</span></div>`;
      html = `
        <div style="font-weight:bold; color:#f1f5f9; margin-bottom:2px;">STEP 0${match.idx}: ${signStr} ${s.word}</div>
        ${posDisplay}
      `;
    }
    tooltip.innerHTML = html;
    tooltip.style.left = `${match.screenX}px`;
    tooltip.style.top = `${match.screenY}px`;
    tooltip.hidden = false;
  }

  function hideTooltip() {
    if (tooltip) tooltip.hidden = true;
  }

  // Perspective 3D & 2D Projection
  function projectPoint(x, y, z) {
    const W = canvas.width / (window.devicePixelRatio || 1);
    const H = canvas.height / (window.devicePixelRatio || 1);
    const cx = W / 2;
    const cy = H / 2;

    if (viewMode === '2d') {
      // 2D Projection: X = Science ↔ Magic, Y = Street ↔ Cosmic
      const scale = 2.1 * zoom;
      const sx = cx + (x * scale) + panX;
      const sy = cy - (y * scale) + panY; // invert Y so +Cosmic points upwards
      return { x: sx, y: sy, depth: 0, scale: zoom, visible: true };
    }

    // 3D Orbital Perspective Projection
    const cosY = Math.cos(yaw), sinY = Math.sin(yaw);
    const x1 = x * cosY - z * sinY;
    const z1 = x * sinY + z * cosY;

    const cosP = Math.cos(pitch), sinP = Math.sin(pitch);
    // Y points upward in Marvel space, invert for canvas
    const yCanvas = -y;
    const y2 = yCanvas * cosP - z1 * sinP;
    const z2 = yCanvas * sinP + z1 * cosP;

    const camDist = 310;
    const depth = camDist + z2;
    if (depth <= 12) return { x: 0, y: 0, depth: z2, scale: 0, visible: false };

    const fov = 350 * zoom;
    const factor = fov / depth;
    const sx = cx + (x1 * factor) + panX;
    const sy = cy + (y2 * factor) + panY;

    return { x: sx, y: sy, depth: z2, scale: factor, visible: true };
  }

  function getCategoryColor(cat) {
    switch (cat) {
      case 'mystic': return '#c084fc';
      case 'science': return '#38bdf8';
      case 'mutant': return '#fbbf24';
      case 'cosmic': return '#818cf8';
      case 'street': return '#34d399';
      case 'villain': return '#f87171';
      case 'antihero': return '#f472b6';
      case 'hero': return '#60a5fa';
      default: return '#94a3b8';
    }
  }

  function drawRoundedRect(ctx, x, y, width, height, radius, fill, stroke) {
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.lineTo(x + width - radius, y);
    ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
    ctx.lineTo(x + width, y + height - radius);
    ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
    ctx.lineTo(x + radius, y + height);
    ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
    ctx.lineTo(x, y + radius);
    ctx.quadraticCurveTo(x, y, x + radius, y);
    ctx.closePath();
    if (fill) {
      ctx.fillStyle = fill;
      ctx.fill();
    }
    if (stroke) {
      ctx.strokeStyle = stroke;
      ctx.stroke();
    }
  }

  // Main Drawing Function
  function renderStage() {
    if (!canvas || !data) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Handle High-DPI screens
    const dpr = window.devicePixelRatio || 1;
    const displayW = stageWrap.clientWidth || 600;
    const displayH = stageWrap.clientHeight || 440;

    if (canvas.width !== displayW * dpr || canvas.height !== displayH * dpr) {
      canvas.width = displayW * dpr;
      canvas.height = displayH * dpr;
    }

    ctx.save();
    ctx.scale(dpr, dpr);

    const W = displayW;
    const H = displayH;
    const cx = W / 2;
    const cy = H / 2;

    // 1. Background gradient
    const bgGrad = ctx.createRadialGradient(cx, cy, 20, cx, cy, Math.max(W, H) * 0.8);
    bgGrad.addColorStop(0, '#131b2c');
    bgGrad.addColorStop(1, '#090d16');
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, W, H);

    // 2. Coordinate Grid & 3D Axes
    ctx.lineWidth = 1;
    if (viewMode === '3d') {
      // 3D Floor grid at y = -75
      ctx.strokeStyle = 'rgba(51, 65, 85, 0.22)';
      const floorY = -75;
      for (let g = -90; g <= 90; g += 30) {
        const p1 = projectPoint(-90, floorY, g);
        const p2 = projectPoint(90, floorY, g);
        if (p1.visible && p2.visible) {
          ctx.beginPath();
          ctx.moveTo(p1.x, p1.y);
          ctx.lineTo(p2.x, p2.y);
          ctx.stroke();
        }

        const p3 = projectPoint(g, floorY, -90);
        const p4 = projectPoint(g, floorY, 90);
        if (p3.visible && p4.visible) {
          ctx.beginPath();
          ctx.moveTo(p3.x, p3.y);
          ctx.lineTo(p4.x, p4.y);
          ctx.stroke();
        }
      }

      // Vertical bounding box tick marks
      ctx.strokeStyle = 'rgba(71, 85, 105, 0.25)';
      ctx.setLineDash([2, 4]);
      [[-90, -90], [90, -90], [90, 90], [-90, 90]].forEach(([bx, bz]) => {
        const top = projectPoint(bx, 80, bz);
        const btm = projectPoint(bx, -80, bz);
        if (top.visible && btm.visible) {
          ctx.beginPath();
          ctx.moveTo(top.x, top.y);
          ctx.lineTo(btm.x, btm.y);
          ctx.stroke();
        }
      });
      ctx.setLineDash([]);

      // Axis endpoint guides in 3D
      const pXPos = projectPoint(100, 0, 0);
      const pXNeg = projectPoint(-100, 0, 0);
      const pYPos = projectPoint(0, 100, 0);
      const pYNeg = projectPoint(0, -100, 0);
      const pZPos = projectPoint(0, 0, 100);
      const pZNeg = projectPoint(0, 0, -100);

      ctx.font = 'bold 9px monospace';
      if (pXPos.visible) { ctx.fillStyle = '#c084fc'; ctx.fillText('Magic +X →', pXPos.x + 5, pXPos.y); }
      if (pXNeg.visible) { ctx.fillStyle = '#38bdf8'; ctx.fillText('← Science −X', pXNeg.x - 65, pXNeg.y); }
      if (pYPos.visible) { ctx.fillStyle = '#818cf8'; ctx.fillText('Cosmic +Y ↑', pYPos.x, pYPos.y - 8); }
      if (pYNeg.visible) { ctx.fillStyle = '#34d399'; ctx.fillText('Street −Y ↓', pYNeg.x, pYNeg.y + 12); }
      if (pZPos.visible) { ctx.fillStyle = '#fbbf24'; ctx.fillText('Mind +Z ↗', pZPos.x + 5, pZPos.y); }
      if (pZNeg.visible) { ctx.fillStyle = '#f87171'; ctx.fillText('↙ Body −Z', pZNeg.x - 55, pZNeg.y); }
    } else {
      // 2D Plane Grid: Horizontal X (Science <-> Magic), Vertical Y (Street <-> Cosmic)
      ctx.strokeStyle = 'rgba(51, 65, 85, 0.25)';
      ctx.setLineDash([3, 4]);
      for (let gx = -100; gx <= 100; gx += 40) {
        const top = projectPoint(gx, 100, 0);
        const btm = projectPoint(gx, -100, 0);
        ctx.beginPath();
        ctx.moveTo(top.x, top.y);
        ctx.lineTo(btm.x, btm.y);
        ctx.stroke();
      }
      for (let gy = -100; gy <= 100; gy += 40) {
        const left = projectPoint(-100, gy, 0);
        const right = projectPoint(100, gy, 0);
        ctx.beginPath();
        ctx.moveTo(left.x, left.y);
        ctx.lineTo(right.x, right.y);
        ctx.stroke();
      }
      ctx.setLineDash([]);

      // Center crosshairs
      ctx.strokeStyle = 'rgba(100, 116, 139, 0.45)';
      const cLeft = projectPoint(-100, 0, 0);
      const cRight = projectPoint(100, 0, 0);
      ctx.beginPath();
      ctx.moveTo(cLeft.x, cLeft.y);
      ctx.lineTo(cRight.x, cRight.y);
      ctx.stroke();

      const cTop = projectPoint(0, 100, 0);
      const cBtm = projectPoint(0, -100, 0);
      ctx.beginPath();
      ctx.moveTo(cTop.x, cTop.y);
      ctx.lineTo(cBtm.x, cBtm.y);
      ctx.stroke();

      // Axis labels
      ctx.font = 'bold 9px monospace';
      ctx.fillStyle = '#c084fc'; ctx.fillText('Magic +X →', W - 75, cy - 6);
      ctx.fillStyle = '#38bdf8'; ctx.fillText('← Science −X', 12, cy - 6);
      ctx.fillStyle = '#818cf8'; ctx.fillText('↑ Cosmic +Y', cx + 8, 18);
      ctx.fillStyle = '#34d399'; ctx.fillText('↓ Street −Y', cx + 8, H - 12);
    }

    // 3. Render Objects with Depth Sorting
    const renderList = [];
    const lastStep = history[history.length - 1];

    // Background characters
    const nearestTop3 = getNearestCharacters3D(lastStep.x, lastStep.y, lastStep.z, 3).map(n => n.label);
    data.characters.forEach(c => {
      const isStart = (c.id === startChar.id);
      const isTarget = (c.id === targetChar.id);
      if (isStart || isTarget) return;

      const p = projectPoint(c.x, c.y, c.z);
      if (!p.visible) return;

      renderList.push({
        type: 'landmark',
        char: c,
        proj: p,
        depth: p.depth,
        isRelevant: nearestTop3.includes(c.label)
      });
    });

    // Trajectory segments
    for (let i = 1; i < history.length; i++) {
      const prev = history[i - 1];
      const curr = history[i];
      const p1 = projectPoint(prev.x, prev.y, prev.z);
      const p2 = projectPoint(curr.x, curr.y, curr.z);
      if (p1.visible && p2.visible) {
        renderList.push({
          type: 'segment',
          step: curr,
          p1,
          p2,
          depth: (p1.depth + p2.depth) / 2
        });
      }
    }

    // Start Character Node
    const pStart = projectPoint(startChar.x, startChar.y, startChar.z);
    if (pStart.visible) {
      renderList.push({ type: 'start', char: startChar, proj: pStart, depth: pStart.depth });
    }

    // Target Destination Beacon
    const pTarget = projectPoint(targetChar.x, targetChar.y, targetChar.z);
    if (pTarget.visible) {
      renderList.push({ type: 'target', char: targetChar, proj: pTarget, depth: pTarget.depth });
    }

    // Current Position
    const pCur = projectPoint(lastStep.x, lastStep.y, lastStep.z);
    if (pCur.visible) {
      renderList.push({ type: 'current', step: lastStep, proj: pCur, depth: pCur.depth + 0.1 });
    }

    // Sort by depth (ascending: furthest back first)
    renderList.sort((a, b) => a.depth - b.depth);

    // Draw all sorted items
    renderList.forEach(item => {
      if (item.type === 'landmark') {
        const { char, proj, isRelevant } = item;
        const color = getCategoryColor(char.category);
        const radius = Math.max(2.5, Math.min(5.5, 3.2 * proj.scale));

        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(proj.x, proj.y, radius, 0, Math.PI * 2);
        ctx.fill();

        const isHovered = hoveredEntity && hoveredEntity.type === 'character' && hoveredEntity.data.id === char.id;
        if (zoom >= 1.35 || isRelevant || isHovered) {
          ctx.font = '9px monospace';
          ctx.textAlign = 'center';
          ctx.fillStyle = isHovered ? '#38bdf8' : (isRelevant ? '#cbd5e1' : '#64748b');
          ctx.fillText(char.label, proj.x, proj.y - radius - 5);
        }
      }

      if (item.type === 'segment') {
        const { step, p1, p2 } = item;
        const isAdd = step.sign > 0;
        const col = isAdd ? '#3874cb' : '#dc512f';

        // Connecting trajectory line
        ctx.strokeStyle = col;
        ctx.lineWidth = Math.max(1.8, Math.min(3.5, 2.4 * p2.scale));
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
        ctx.stroke();

        // Direction chevron marker midway
        const mx = (p1.x + p2.x) / 2;
        const my = (p1.y + p2.y) / 2;
        const angle = Math.atan2(p2.y - p1.y, p2.x - p1.x);

        ctx.save();
        ctx.translate(mx, my);
        ctx.rotate(angle);
        ctx.fillStyle = col;
        ctx.beginPath();
        ctx.moveTo(6, 0);
        ctx.lineTo(-4, -4);
        ctx.lineTo(-2, 0);
        ctx.lineTo(-4, 4);
        ctx.closePath();
        ctx.fill();
        ctx.restore();

        // Midpoint Step Word Badge
        const badgeW = ctx.measureText(`${isAdd ? '+' : '−'} ${step.word}`).width + 12;
        const badgeH = 15;
        drawRoundedRect(ctx, mx - badgeW / 2, my - 16, badgeW, badgeH, 3, '#0b0f19', col);
        ctx.font = 'bold 9px monospace';
        ctx.textAlign = 'center';
        ctx.fillStyle = '#f1f5f9';
        ctx.fillText(`${isAdd ? '+' : '−'} ${step.word}`, mx, my - 6);
      }

      if (item.type === 'start') {
        const { char, proj } = item;
        ctx.fillStyle = '#10b981';
        ctx.beginPath();
        ctx.arc(proj.x, proj.y, 6, 0, Math.PI * 2);
        ctx.fill();

        ctx.strokeStyle = '#10b981';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(proj.x, proj.y, 11, 0, Math.PI * 2);
        ctx.stroke();

        const distToCur = Math.hypot(proj.x - pCur.x, proj.y - pCur.y);
        const badgeY = (distToCur < 42) ? proj.y - 28 : proj.y - 18;

        const labelText = `${char.label} [START]`;
        ctx.font = 'bold 9px monospace';
        const txtW = ctx.measureText(labelText).width + 14;
        drawRoundedRect(ctx, proj.x - txtW / 2, badgeY - 10, txtW, 16, 4, 'rgba(15, 23, 42, 0.92)', '#10b981');
        ctx.textAlign = 'center';
        ctx.fillStyle = '#6ee7b7';
        ctx.fillText(labelText, proj.x, badgeY + 1);
      }

      if (item.type === 'target') {
        const { char, proj } = item;
        const pulse = 16 + Math.sin(Date.now() / 240) * 4;

        // Radial glow
        const glow = ctx.createRadialGradient(proj.x, proj.y, 2, proj.x, proj.y, 32);
        glow.addColorStop(0, 'rgba(56, 116, 203, 0.45)');
        glow.addColorStop(1, 'rgba(56, 116, 203, 0)');
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(proj.x, proj.y, 32, 0, Math.PI * 2);
        ctx.fill();

        // Pulsing radar ring
        ctx.strokeStyle = '#3874cb';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 3]);
        ctx.beginPath();
        ctx.arc(proj.x, proj.y, pulse, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);

        // Core dot and reticle
        ctx.fillStyle = '#3874cb';
        ctx.beginPath();
        ctx.arc(proj.x, proj.y, 6, 0, Math.PI * 2);
        ctx.fill();

        ctx.strokeStyle = '#60a5fa';
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(proj.x - 10, proj.y);
        ctx.lineTo(proj.x + 10, proj.y);
        ctx.moveTo(proj.x, proj.y - 10);
        ctx.lineTo(proj.x, proj.y + 10);
        ctx.stroke();

        const distToCur = Math.hypot(proj.x - pCur.x, proj.y - pCur.y);
        const badgeY = (distToCur < 42) ? proj.y + 26 : proj.y + 20;

        const labelText = `${char.label} [TARGET]`;
        ctx.font = 'bold 10px monospace';
        const txtW = ctx.measureText(labelText).width + 16;
        drawRoundedRect(ctx, proj.x - txtW / 2, badgeY - 10, txtW, 18, 4, 'rgba(15, 23, 42, 0.92)', '#3874cb');
        ctx.textAlign = 'center';
        ctx.fillStyle = '#93c5fd';
        ctx.fillText(labelText, proj.x, badgeY + 2);
      }

      if (item.type === 'current') {
        const { proj } = item;
        const cGlow = ctx.createRadialGradient(proj.x, proj.y, 2, proj.x, proj.y, 24);
        cGlow.addColorStop(0, 'rgba(56, 189, 248, 0.6)');
        cGlow.addColorStop(1, 'rgba(56, 189, 248, 0)');
        ctx.fillStyle = cGlow;
        ctx.beginPath();
        ctx.arc(proj.x, proj.y, 24, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = '#38bdf8';
        ctx.beginPath();
        ctx.arc(proj.x, proj.y, 5, 0, Math.PI * 2);
        ctx.fill();

        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 1.6;
        ctx.beginPath();
        ctx.arc(proj.x, proj.y, 10, 0, Math.PI * 2);
        ctx.stroke();

        const distToStart = Math.hypot(proj.x - pStart.x, proj.y - pStart.y);
        const distToTarget = Math.hypot(proj.x - pTarget.x, proj.y - pTarget.y);
        let badgeY = proj.y - 20;
        if (distToStart < 42) {
          badgeY = proj.y + 20;
        } else if (distToTarget < 42) {
          badgeY = proj.y - 24;
        }

        const labelText = 'CURRENT POSITION';
        ctx.font = 'bold 9px monospace';
        const txtW = ctx.measureText(labelText).width + 12;
        drawRoundedRect(ctx, proj.x - txtW / 2, badgeY - 9, txtW, 15, 3, 'rgba(15, 23, 42, 0.95)', '#38bdf8');
        ctx.textAlign = 'center';
        ctx.fillStyle = '#7dd3fc';
        ctx.fillText(labelText, proj.x, badgeY + 2);
      }
    });

    // 4. Mini 3D Orientation Axis in Lower-Left Corner
    if (viewMode === '3d') {
      const axO = { x: 34, y: H - 34 };
      const axLen = 18;
      const cosY = Math.cos(yaw), sinY = Math.sin(yaw);
      const cosP = Math.cos(pitch), sinP = Math.sin(pitch);

      const drawAxis = (vx, vy, vz, label, col) => {
        const x1 = vx * cosY - vz * sinY;
        const z1 = vx * sinY + vz * cosY;
        const y2 = vy * cosP - z1 * sinP;
        const px = axO.x + x1 * axLen;
        const py = axO.y + y2 * axLen;

        ctx.strokeStyle = col;
        ctx.lineWidth = 1.8;
        ctx.beginPath();
        ctx.moveTo(axO.x, axO.y);
        ctx.lineTo(px, py);
        ctx.stroke();

        ctx.font = 'bold 8px monospace';
        ctx.fillStyle = col;
        ctx.textAlign = 'center';
        ctx.fillText(label, px + (x1 >= 0 ? 5 : -5), py + (y2 >= 0 ? 5 : -5));
      };

      drawAxis(1, 0, 0, 'X', '#c084fc');
      drawAxis(0, -1, 0, 'Y', '#818cf8');
      drawAxis(0, 0, 1, 'Z', '#fbbf24');
    }

    ctx.restore();
  }

  // Animation Loop for Smooth Radar Glow
  function startAnimationLoop() {
    function loop() {
      renderStage();
      animFrameId = requestAnimationFrame(loop);
    }
    if (animFrameId) cancelAnimationFrame(animFrameId);
    animFrameId = requestAnimationFrame(loop);
  }

  // Self-initialization
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initGame);
  } else {
    initGame();
  }
})();
