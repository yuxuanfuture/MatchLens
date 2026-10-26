(function () {
  "use strict";

  const scenarios = window.MATCHLENS_SCENARIOS || [];
  if (!scenarios.length) return;

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));

  const elements = {
    scenarioTabs: $("#scenario-tabs"),
    sceneNumber: $("#scene-number"),
    directorButton: $("#director-button"),
    fullscreenButton: $("#fullscreen-button"),
    playButton: $("#play-button"),
    resetButton: $("#reset-button"),
    speedControl: $("#speed-control"),
    eventRate: $("#event-rate"),
    homeName: $("#home-name"),
    awayName: $("#away-name"),
    homeColor: $("#home-color"),
    awayColor: $("#away-color"),
    homeScore: $("#home-score"),
    awayScore: $("#away-score"),
    matchClock: $("#match-clock"),
    viewerBadge: $("#viewer-badge"),
    pitch: $("#pitch"),
    playersLayer: $("#players-layer"),
    ball: $("#ball"),
    eventTrail: $("#event-trail"),
    pressureZone: $("#pressure-zone"),
    insightOverlay: $("#insight-overlay"),
    insightKicker: $("#insight-kicker"),
    insightConfidence: $("#insight-confidence"),
    insightHeadline: $("#insight-headline"),
    insightCopy: $("#insight-copy"),
    evidenceRow: $("#evidence-row"),
    groundingScore: $("#grounding-score"),
    timelineProgress: $("#timeline-progress"),
    timelineCurrent: $("#timeline-current"),
    timelineTotal: $("#timeline-total"),
    audienceControl: $("#audience-control"),
    focusSelect: $("#focus-select"),
    languageSelect: $("#language-select"),
    momentumValue: $("#momentum-value"),
    momentumLine: $("#momentum-line"),
    momentumArea: $("#momentum-area"),
    possessionStat: $("#possession-stat"),
    xgStat: $("#xg-stat"),
    pressureStat: $("#pressure-stat"),
    traceId: $("#trace-id"),
    eventFeed: $("#event-feed")
  };

  const state = {
    scenarioIndex: 0,
    currentEventIndex: -1,
    elapsed: 0,
    speed: 1,
    playing: false,
    director: false,
    audience: "analyst",
    language: "en",
    focus: "match",
    lastFrame: 0,
    raf: null,
    agentTimers: [],
    lastMoment: null,
    players: new Map()
  };

  const pitchBox = { x: 15, y: 15, width: 1020, height: 650 };

  const baseFormation = {
    1: [7, 34],
    2: [22, 10],
    4: [22, 25],
    5: [22, 43],
    3: [22, 58],
    6: [39, 34],
    7: [50, 12],
    8: [49, 27],
    10: [52, 43],
    11: [50, 57],
    9: [68, 34],
    17: [52, 49]
  };

  const fanMoments = {
    "PRESSURE SHIFT": {
      en: ["Riverside are running out of room", "Northbridge squeeze the pitch, taking away every safe exit."],
      zh: ["Riverside 已经无路可走", "Northbridge 不断压缩空间，封死了每一个安全出口。"]
    },
    "HIGH-VALUE REGAIN": {
      en: ["Northbridge pounce on the mistake", "They win it close to goal and attack before Riverside can breathe."],
      zh: ["Northbridge 抓住了失误", "他们在球门附近夺回球权，趁 Riverside 还没站稳立刻进攻。"]
    },
    "WHY IT MATTERS": {
      en: ["The goal started long before the finish", "Relentless pressure created the chance; the striker simply completed the story."],
      zh: ["这个进球早在射门前就开始了", "持续压迫创造了机会，前锋只是完成了故事的最后一笔。"]
    },
    "TRANSITION WINDOW": {
      en: ["Eastgate spot the break instantly", "The goalkeeper sees Harbour are exposed and launches the counter."],
      zh: ["Eastgate 瞬间看到了反击机会", "门将发现 Harbour 防线空虚，立即发动反击。"]
    },
    "LINE-BREAKING PASS": {
      en: ["One pass leaves Harbour chasing", "The diagonal opens the whole pitch and turns defence into a two-on-one."],
      zh: ["一脚传球让 Harbour 只能回追", "这脚斜传打开整片球场，将防守直接变成二打一。"]
    },
    "COUNTER COMPLETE": {
      en: ["From danger to delight in nine seconds", "Eastgate race from their own goal to the winner before Harbour can recover."],
      zh: ["九秒内，从险情到狂喜", "Harbour 还没来得及回防，Eastgate 已从自家球门前完成致命一击。"]
    },
    "TACTICAL CHANGE": {
      en: ["One substitution changes the match", "The new arrival gives Atlas an extra option in every attack."],
      zh: ["一次换人改变了比赛", "新上场的球员让 Atlas 的每次进攻都多了一个选择。"]
    },
    "MOMENTUM FLIP": {
      en: ["Atlas have taken over", "Two chances in a minute—and Union cannot get out of their own half."],
      zh: ["Atlas 已经接管比赛", "一分钟内两次机会，Union 甚至无法离开本方半场。"]
    },
    "IMPACT CONFIRMED": {
      en: ["The substitute makes the difference", "H17 unlocks the defence again and Atlas finally find the equaliser."],
      zh: ["替补球员成为关键先生", "H17 再次撕开防线，Atlas 终于扳平比分。"]
    }
  };

  function scenario() {
    return scenarios[state.scenarioIndex];
  }

  function toPitch(point) {
    return {
      x: pitchBox.x + (point[0] / 105) * pitchBox.width,
      y: pitchBox.y + (point[1] / 68) * pitchBox.height
    };
  }

  function formatClock(minute, second) {
    return `${String(minute).padStart(2, "0")}:${String(second).padStart(2, "0")}`;
  }

  function formatClipTime(seconds) {
    return `00:${String(Math.max(0, Math.floor(seconds))).padStart(2, "0")}`;
  }

  function createScenarioTabs() {
    elements.scenarioTabs.innerHTML = "";
    scenarios.forEach((item, index) => {
      const button = document.createElement("button");
      button.className = "scenario-tab";
      button.dataset.index = String(index);
      button.innerHTML = `<span>${String(index + 1).padStart(2, "0")} · ${item.label}</span><small>${item.subtitle}</small>`;
      button.addEventListener("click", () => loadScenario(index, true));
      elements.scenarioTabs.appendChild(button);
    });
  }

  function playerIdsForCurrentScenario() {
    const home = state.scenarioIndex === 2
      ? ["H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H9", "H10", "H17"]
      : ["H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H9", "H10", "H11"];
    const away = ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "A10", "A11"];
    return [...home, ...away];
  }

  function createPlayers() {
    state.players.clear();
    elements.playersLayer.innerHTML = "";
    const current = scenario();

    playerIdsForCurrentScenario().forEach((id) => {
      const team = id.startsWith("H") ? "home" : "away";
      const number = Number(id.slice(1));
      const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
      group.classList.add("player");
      group.dataset.id = id;
      group.dataset.team = team;

      const halo = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      halo.classList.add("halo");
      halo.setAttribute("r", "18");
      halo.setAttribute("stroke", current.teams[team].color);

      const body = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      body.classList.add("body");
      body.setAttribute("r", "15");
      body.setAttribute("fill", current.teams[team].color);

      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.textContent = String(number);
      label.setAttribute("y", ".5");

      group.append(halo, body, label);
      elements.playersLayer.appendChild(group);
      state.players.set(id, group);
    });
  }

  function formationPosition(id, event, index) {
    const isHome = id.startsWith("H");
    const number = Number(id.slice(1));
    const base = baseFormation[number] || baseFormation[11];
    const attacksLeft = scenario().homeAttacks === "left";
    const teamFacesRight = isHome ? !attacksLeft : attacksLeft;
    let x = teamFacesRight ? base[0] : 105 - base[0];
    let y = isHome ? base[1] : 68 - base[1];

    if (event) {
      const ball = event.end || event.start;
      const teamInPossession = event.team === (isHome ? "home" : "away");
      const directionBias = (ball[0] - 52.5) * (teamInPossession ? 0.18 : 0.11);
      x += directionBias;
      y += Math.sin((index + number * 1.73) * 0.74) * 1.7;

      if (id === event.player) [x, y] = event.start;
      if (id === event.recipient) [x, y] = event.end;
    }

    return [Math.max(3, Math.min(102, x)), Math.max(3, Math.min(65, y))];
  }

  function updatePlayers(event, index) {
    state.players.forEach((node, id) => {
      const position = formationPosition(id, event, index);
      const mapped = toPitch(position);
      node.style.transform = `translate(${mapped.x}px, ${mapped.y}px)`;
      node.classList.toggle("active", Boolean(event && (id === event.player || id === event.recipient)));
    });
  }

  function setBall(point, immediate = false) {
    const mapped = toPitch(point);
    if (immediate) elements.ball.style.transition = "none";
    elements.ball.style.transform = `translate(${mapped.x}px, ${mapped.y}px)`;
    if (immediate) {
      requestAnimationFrame(() => { elements.ball.style.transition = ""; });
    }
  }

  function showEventVector(event) {
    const from = toPitch(event.start);
    const to = toPitch(event.end);
    elements.eventTrail.setAttribute("x1", from.x);
    elements.eventTrail.setAttribute("y1", from.y);
    elements.eventTrail.setAttribute("x2", to.x);
    elements.eventTrail.setAttribute("y2", to.y);
    elements.eventTrail.classList.toggle("visible", ["pass", "cross", "throw", "shot", "corner", "clearance"].includes(event.type));

    const pressureEllipse = elements.pressureZone.querySelector("ellipse");
    pressureEllipse.setAttribute("cx", to.x);
    pressureEllipse.setAttribute("cy", to.y);
    const radius = 42 + (event.pressure || 0) * 62;
    pressureEllipse.setAttribute("rx", radius);
    pressureEllipse.setAttribute("ry", radius * 0.68);
    elements.pressureZone.classList.toggle("visible", (event.pressure || 0) > 0.62 || event.type === "pressure");

    setBall(event.start, true);
    requestAnimationFrame(() => requestAnimationFrame(() => setBall(event.end)));
  }

  function eventLabel(event) {
    const labels = {
      pass: "Pass completed",
      pressure: "Pressure applied",
      interception: "Interception",
      carry: "Progressive carry",
      shot: event.success ? "GOAL" : "Shot",
      rebound: "Rebound won",
      restart: "Restart",
      corner: "Corner delivered",
      claim: "Goalkeeper claim",
      throw: "Fast distribution",
      turn: "Turn under pressure",
      cross: "Cross",
      celebration: "Goal confirmed",
      substitution: "Substitution",
      recovery: "Ball recovery",
      clearance: "Clearance"
    };
    return labels[event.type] || event.type.replace(/_/g, " ");
  }

  function addFeedItem(event, index) {
    const current = scenario();
    const item = document.createElement("div");
    item.className = "feed-item";
    item.innerHTML = `
      <time>${formatClock(event.minute, event.second)}</time>
      <span class="team-dot" style="background:${current.teams[event.team].color}"></span>
      <strong>${eventLabel(event)} · ${event.player}</strong>
      <code>evt_${String(index + 1).padStart(3, "0")}</code>`;
    elements.eventFeed.prepend(item);
    while (elements.eventFeed.children.length > 6) {
      elements.eventFeed.lastElementChild.remove();
    }
  }

  function updateScoreAndClock(event, index) {
    const current = scenario();
    let score = [current.teams.home.score, current.teams.away.score];
    current.events.slice(0, index + 1).forEach((item) => {
      if (item.score) score = item.score;
    });
    elements.homeScore.textContent = score[0];
    elements.awayScore.textContent = score[1];
    elements.matchClock.textContent = formatClock(event.minute, event.second);
  }

  function calculateStats(index) {
    const current = scenario();
    const events = current.events.slice(0, index + 1);
    const initialStats = current.initialStats || { possession: [50, 50], xg: [0, 0], pressure: 0.3 };
    const touches = { home: initialStats.possession[0], away: initialStats.possession[1] };
    const xg = { home: initialStats.xg[0], away: initialStats.xg[1] };
    const pressure = [initialStats.pressure];

    events.forEach((event) => {
      if (!["pressure", "substitution", "celebration"].includes(event.type)) touches[event.team] += 1;
      if (event.xg) xg[event.team] += event.xg;
      if (typeof event.pressure === "number") pressure.push(event.pressure);
    });

    const totalTouches = touches.home + touches.away || 1;
    const homePossession = Math.round((touches.home / totalTouches) * 100);
    const awayPossession = 100 - homePossession;
    elements.possessionStat.textContent = `${homePossession}—${awayPossession}`;
    elements.xgStat.textContent = `${xg.home.toFixed(2)}—${xg.away.toFixed(2)}`;

    const recentPressure = pressure.slice(-4);
    const averagePressure = recentPressure.reduce((sum, value) => sum + value, 0) / (recentPressure.length || 1);
    elements.pressureStat.textContent = averagePressure > 0.72 ? "HIGH" : averagePressure > 0.4 ? "MED" : "LOW";

    const values = events.map((event) => event.momentum || 0);
    const latest = values.at(-1) || 0;
    elements.momentumValue.textContent = `${latest >= 0 ? "+" : ""}${latest}`;
    elements.momentumValue.style.color = latest >= 0 ? current.teams.home.color : current.teams.away.color;

    const width = 360;
    const points = values.length
      ? values.map((value, i) => {
          const x = values.length === 1 ? 0 : (i / (current.events.length - 1)) * width;
          const y = 52 - value * 0.42;
          return `${x.toFixed(1)},${Math.max(4, Math.min(100, y)).toFixed(1)}`;
        })
      : ["0,52"];
    const pointString = points.join(" ");
    elements.momentumLine.setAttribute("points", pointString);
    const areaPoints = `M ${points[0].replace(",", " ")} L ${points.slice(1).join(" L ").replaceAll(",", " ")} L ${points.at(-1).split(",")[0]} 104 L 0 104 Z`;
    elements.momentumArea.setAttribute("d", areaPoints);
  }

  function personalizedMoment(momentData, event) {
    const lang = state.language;
    let headline = momentData.headline[lang];
    let copy = momentData.copy[lang];

    if (state.audience === "fan" && fanMoments[momentData.kicker]) {
      [headline, copy] = fanMoments[momentData.kicker][lang];
    }

    if (state.focus === "home") {
      copy += lang === "zh"
        ? ` 当前视角重点关注 ${scenario().teams.home.name}。`
        : ` This lens prioritizes ${scenario().teams.home.name}.`;
    }
    if (state.focus === "player") {
      const player = event?.player || "H09";
      copy += lang === "zh"
        ? ` 球员视角：${player} 是这次变化的关键节点。`
        : ` Player lens: ${player} is the key node in this sequence.`;
    }

    return { headline, copy };
  }

  function renderInsight(momentData, event, animate = true) {
    if (!momentData) return;
    state.lastMoment = { data: momentData, event };
    const personalized = personalizedMoment(momentData, event);
    elements.insightKicker.textContent = momentData.kicker;
    elements.insightConfidence.textContent = momentData.confidence;
    elements.groundingScore.textContent = `${momentData.confidence}%`;
    elements.insightHeadline.textContent = personalized.headline;
    elements.insightCopy.textContent = personalized.copy;
    elements.evidenceRow.innerHTML = "";
    const evidence = [...momentData.evidence];
    if (state.focus === "home") evidence.push("HOME FOCUS");
    if (state.focus === "player") evidence.push(`${event?.player || "H09"} FOCUS`);
    evidence.forEach((item) => {
      const chip = document.createElement("span");
      chip.className = "evidence-chip";
      chip.textContent = item;
      elements.evidenceRow.appendChild(chip);
    });

    if (animate) {
      elements.insightOverlay.classList.remove("reveal");
      void elements.insightOverlay.offsetWidth;
      elements.insightOverlay.classList.add("reveal");
    }
  }

  function animateAgents(event, index) {
    state.agentTimers.forEach(clearTimeout);
    state.agentTimers = [];
    const steps = $$(".agent-step");
    const sequence = [0, 160, 340, 560];
    steps.forEach((step) => step.className = "agent-step");
    elements.traceId.textContent = `TRC-${event.minute}${String(event.second).padStart(2, "0")}-${String(index + 1).padStart(2, "0")}`;

    steps.forEach((step, stepIndex) => {
      state.agentTimers.push(setTimeout(() => {
        steps.forEach((item, indexInLoop) => {
          item.classList.toggle("done", indexInLoop < stepIndex);
          item.classList.toggle("active", indexInLoop === stepIndex);
        });
        if (stepIndex === steps.length - 1) {
          state.agentTimers.push(setTimeout(() => {
            steps.forEach((item) => {
              item.classList.add("done");
              item.classList.remove("active");
            });
          }, 380));
        }
      }, sequence[stepIndex]));
    });
  }

  function processEvent(event, index) {
    state.currentEventIndex = index;
    updatePlayers(event, index);
    showEventVector(event);
    addFeedItem(event, index);
    updateScoreAndClock(event, index);
    calculateStats(index);
    animateAgents(event, index);
    if (event.moment) renderInsight(event.moment, event);
  }

  function renderAudience() {
    $$("#audience-control button").forEach((button) => {
      button.classList.toggle("active", button.dataset.audience === state.audience);
    });
    elements.viewerBadge.textContent = state.audience === "analyst" ? "ANALYST VIEW" : "FAN VIEW";
    elements.viewerBadge.style.color = state.audience === "analyst" ? "var(--cyan)" : "var(--lime)";
    if (state.lastMoment) renderInsight(state.lastMoment.data, state.lastMoment.event, false);
  }

  function setAudience(audience) {
    state.audience = audience;
    renderAudience();
  }

  function defaultMoment() {
    const current = scenario();
    return {
      kicker: "LIVE CONTEXT",
      confidence: 96,
      headline: {
        en: `${current.label}: waiting for the decisive shift`,
        zh: `${current.label}：等待决定性变化`
      },
      copy: {
        en: "Every event is measured against the evolving match state. Only meaningful changes reach the screen.",
        zh: "每个事件都会与持续变化的比赛状态比较，只有真正重要的变化才会出现在屏幕上。"
      },
      evidence: ["Synthetic event stream", "State-aware", "Claim-level evidence"]
    };
  }

  function resetScenario() {
    pause();
    state.elapsed = 0;
    state.currentEventIndex = -1;
    state.lastFrame = 0;
    state.lastMoment = null;
    const current = scenario();
    elements.eventFeed.innerHTML = "";
    elements.homeScore.textContent = current.teams.home.score;
    elements.awayScore.textContent = current.teams.away.score;
    const first = current.events[0];
    elements.matchClock.textContent = formatClock(first.minute, first.second);
    elements.timelineProgress.style.width = "0%";
    elements.timelineCurrent.textContent = "00:00";
    elements.timelineTotal.textContent = formatClipTime(current.duration);
    const initialStats = current.initialStats || { possession: [50, 50], xg: [0, 0], pressure: 0.3 };
    elements.possessionStat.textContent = `${initialStats.possession[0]}—${initialStats.possession[1]}`;
    elements.xgStat.textContent = `${initialStats.xg[0].toFixed(2)}—${initialStats.xg[1].toFixed(2)}`;
    elements.pressureStat.textContent = initialStats.pressure > 0.72 ? "HIGH" : initialStats.pressure > 0.4 ? "MED" : "LOW";
    elements.momentumValue.textContent = "0";
    elements.momentumLine.setAttribute("points", "0,52");
    elements.momentumArea.setAttribute("d", "M 0 52 L 0 104 L 0 104 Z");
    elements.eventTrail.classList.remove("visible");
    elements.pressureZone.classList.remove("visible");
    createPlayers();
    updatePlayers(null, 0);
    setBall(first.start, true);
    renderInsight(defaultMoment(), first, false);
    renderAudience();
    $$(".agent-step").forEach((step, index) => {
      step.className = `agent-step${index === 0 ? " active" : ""}`;
    });
  }

  function loadScenario(index, autoplay = false) {
    const wasPlaying = state.playing || autoplay || state.director;
    state.scenarioIndex = index;
    const current = scenario();
    elements.sceneNumber.textContent = `${String(index + 1).padStart(2, "0")} / ${String(scenarios.length).padStart(2, "0")}`;
    elements.homeName.textContent = current.teams.home.name;
    elements.awayName.textContent = current.teams.away.name;
    elements.homeColor.style.background = current.teams.home.color;
    elements.awayColor.style.background = current.teams.away.color;
    elements.homeColor.style.color = current.teams.home.color;
    elements.awayColor.style.color = current.teams.away.color;
    $$(".scenario-tab").forEach((button, tabIndex) => button.classList.toggle("active", tabIndex === index));

    if (state.director) {
      const modes = ["analyst", "fan", "analyst"];
      const focuses = ["match", "home", "player"];
      state.audience = modes[index] || "analyst";
      state.focus = focuses[index] || "match";
      elements.focusSelect.value = state.focus;
    }

    resetScenario();
    if (wasPlaying) setTimeout(play, 260);
  }

  function frame(timestamp) {
    if (!state.playing) return;
    if (!state.lastFrame) state.lastFrame = timestamp;
    const delta = Math.min(0.08, (timestamp - state.lastFrame) / 1000);
    state.lastFrame = timestamp;
    state.elapsed += delta * state.speed;

    const current = scenario();
    let nextIndex = state.currentEventIndex + 1;
    while (nextIndex < current.events.length && current.events[nextIndex].t <= state.elapsed) {
      processEvent(current.events[nextIndex], nextIndex);
      nextIndex += 1;
    }

    const progress = Math.min(100, (state.elapsed / current.duration) * 100);
    elements.timelineProgress.style.width = `${progress}%`;
    elements.timelineCurrent.textContent = formatClipTime(state.elapsed);

    if (state.elapsed >= current.duration) {
      if (state.director && state.scenarioIndex < scenarios.length - 1) {
        pause();
        setTimeout(() => loadScenario(state.scenarioIndex + 1, true), 800);
        return;
      }
      if (state.director) {
        state.director = false;
        elements.directorButton.classList.remove("active");
      }
      pause();
      return;
    }

    state.raf = requestAnimationFrame(frame);
  }

  function play() {
    if (state.elapsed >= scenario().duration) resetScenario();
    state.playing = true;
    state.lastFrame = 0;
    elements.playButton.classList.add("playing");
    elements.playButton.setAttribute("aria-label", "Pause scenario");
    state.raf = requestAnimationFrame(frame);
  }

  function pause() {
    state.playing = false;
    state.lastFrame = 0;
    elements.playButton.classList.remove("playing");
    elements.playButton.setAttribute("aria-label", "Play scenario");
    if (state.raf) cancelAnimationFrame(state.raf);
    state.raf = null;
  }

  function setSpeed(speed) {
    state.speed = speed;
    elements.eventRate.textContent = `${speed.toFixed(speed % 1 ? 2 : 1).replace(/0$/, "")}× EVENT RATE`;
    $$("#speed-control button").forEach((button) => {
      button.classList.toggle("active", Number(button.dataset.speed) === speed);
    });
  }

  function toggleDirector() {
    state.director = !state.director;
    elements.directorButton.classList.toggle("active", state.director);
    if (state.director) {
      setSpeed(1.5);
      state.language = "en";
      elements.languageSelect.value = "en";
      loadScenario(0, true);
    } else {
      pause();
    }
  }

  function bindControls() {
    elements.playButton.addEventListener("click", () => state.playing ? pause() : play());
    elements.resetButton.addEventListener("click", resetScenario);
    elements.directorButton.addEventListener("click", toggleDirector);
    elements.speedControl.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-speed]");
      if (button) setSpeed(Number(button.dataset.speed));
    });
    elements.audienceControl.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-audience]");
      if (button) setAudience(button.dataset.audience);
    });
    elements.focusSelect.addEventListener("change", () => {
      state.focus = elements.focusSelect.value;
      if (state.lastMoment) renderInsight(state.lastMoment.data, state.lastMoment.event, false);
    });
    elements.languageSelect.addEventListener("change", () => {
      state.language = elements.languageSelect.value;
      if (state.lastMoment) renderInsight(state.lastMoment.data, state.lastMoment.event, false);
    });
    elements.fullscreenButton.addEventListener("click", async () => {
      try {
        if (!document.fullscreenElement) await document.documentElement.requestFullscreen();
        else await document.exitFullscreen();
      } catch (_) {
        // Fullscreen is optional; the product remains fully usable without it.
      }
    });
    document.addEventListener("keydown", (event) => {
      if (event.code === "Space" && !["SELECT", "INPUT"].includes(document.activeElement?.tagName)) {
        event.preventDefault();
        state.playing ? pause() : play();
      }
      if (event.key.toLowerCase() === "d") toggleDirector();
      if (event.key.toLowerCase() === "r") resetScenario();
    });
  }

  createScenarioTabs();
  bindControls();
  setSpeed(1);
  loadScenario(0, false);
})();
