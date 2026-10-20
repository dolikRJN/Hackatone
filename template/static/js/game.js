/* Игра: загрузка упражнения, ввод, метрики и сохранение завершённой тренировки. */
(async function () {
  "use strict";
  const status = document.getElementById("game-status");
  const typing = document.getElementById("typing");
  const restart = document.getElementById("restart");
  const pause = document.getElementById("pause");
  const mobileInput = document.getElementById("mobile-input");
  let usesMobileInput = false;
  const comboBadge = document.getElementById("combo");
  const feedback = document.getElementById("game-feedback");
  const streakHint = document.getElementById("streak-hint");
  const sessionFill = document.getElementById("session-fill");
  const sessionCount = document.getElementById("session-count");
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const animations = new Map();
  const keyboard = [...document.querySelectorAll("#keyboard .k")].map(node => ({
    node, latin: node.dataset.key, russian: node.querySelector(".ru")?.textContent,
    primary: node.firstChild, secondary: node.querySelector(".ru"),
    finger: Number([...node.classList].find(name => /^f\d$/.test(name))?.slice(1)),
  }));
  let characters = [], paintedLength = 0, feedbackTimer = 0, lastErrorAt = -Infinity;
  let text = "", typed = [], mistakes = {}, started = 0, elapsedBefore = 0;
  let attempts = 0, correct = 0, combo = 0, maxCombo = 0;
  let paused = false, finished = false, loading = false, saving = false, version = 0;
  let pendingResult = null;
  const selected = (group, attr) => document.querySelector(`#${group} [aria-selected="true"]`).dataset[attr];
  const elapsed = () => elapsedBefore + (started ? (performance.now() - started) / 1000 : 0);

  function updateKeyboardLayout() {
    const russian = selected("langs", "lang") === "ru";
    keyboard.forEach(key => {
      // Меняем только подписи, сохраняя физическую клавишу, цвет и её DOM-узел.
      if (key.russian) {
        key.primary.nodeValue = russian ? key.russian : key.latin;
        key.secondary.textContent = russian ? key.latin : key.russian;
      }
      key.node.classList.remove("is-next");
    });
  }

  function animateOnce(node, frames, duration = 200) {
    // Не больше одной короткой анимации на элемент, без циклов и forced reflow.
    animations.get(node)?.cancel();
    animations.delete(node);
    if (reducedMotion.matches || !node.animate) return;
    const animation = node.animate(frames, { duration, easing: "ease-out" });
    animations.set(node, animation);
    animation.onfinish = () => { if (animations.get(node) === animation) animations.delete(node); };
  }
  function message(text, persistent = false) {
    clearTimeout(feedbackTimer);
    feedback.textContent = text;
    animateOnce(feedback, [{ opacity: 0, transform: "translateY(3px)" }, { opacity: 1, transform: "none" }]);
    if (!persistent) feedbackTimer = setTimeout(() => { feedback.textContent = ""; }, 2400);
  }
  function resetEffects() {
    clearTimeout(feedbackTimer);
    animations.forEach(animation => animation.cancel());
    animations.clear();
    feedback.textContent = "";
    typing.classList.remove("is-complete", "is-paused");
    characters = []; paintedLength = 0; lastErrorAt = -Infinity;
  }

  function metrics() {
    const seconds = Math.max(elapsed(), 1);
    // Повторный ввод после Backspace не увеличивает полезную скорость.
    const completed = typed.reduce((sum, char, index) => sum + Number(char === text[index]), 0);
    return { speed_wpm: completed / 5 / (seconds / 60), accuracy_pct: attempts ? correct / attempts * 100 : 100 };
  }
  function hud() {
    const stats = metrics();
    document.getElementById("wpm").textContent = Math.round(stats.speed_wpm);
    document.getElementById("cpm").textContent = Math.round(stats.speed_wpm * 5);
    document.getElementById("acc").textContent = Math.round(stats.accuracy_pct) + "%";
    document.getElementById("err").textContent = attempts - correct;
    document.getElementById("score").textContent = correct;
    comboBadge.querySelector("span").textContent = "×" + (combo >= 50 ? 5 : combo >= 20 ? 3 : combo >= 10 ? 2 : 1);
    comboBadge.querySelector("small").textContent = combo ? `${combo} подряд` : "комбо";
    comboBadge.classList.toggle("is-hot", combo >= 10);
    const next = [10, 20, 50].find(mark => mark > combo);
    const multiplier = next === 10 ? 2 : next === 20 ? 3 : 5;
    streakHint.textContent = finished ? `Лучшая серия: ${maxCombo}`
      : next ? `До ×${multiplier}: ещё ${next - combo} подряд` : "×5 — держите ритм!";
  }
  function hint() {
    const next = text[typed.length];
    document.getElementById("hint-key").textContent = next === " " ? "Пробел" : next === "\n" ? "Enter" : next || "✓";
    const fingers = ["левый мизинец", "левый безымянный", "левый средний", "левый указательный", "правый указательный", "правый средний", "правый безымянный", "правый мизинец", "большой палец"];
    const russian = selected("langs", "lang") === "ru";
    let finger = "";
    keyboard.forEach(key => {
      const label = (russian ? key.russian : null) || key.latin || key.node.textContent;
      const active = !!next && label === next.toLowerCase();
      key.node.classList.toggle("is-next", active);
      if (active) finger = fingers[key.finger - 1];
    });
    document.getElementById("hint-text").textContent = finger || (next ? "используйте нужную раскладку и Shift" : "готово");
  }
  function render() {
    if (!characters.length) {
      // Создаём символы один раз. textContent безопасен для упражнений с HTML-кодом.
      characters = [...text].map(char => {
        const span = document.createElement("span");
        span.className = "ch"; span.textContent = char;
        return span;
      });
      typing.replaceChildren(...characters);
    }
    // При вводе/Backspace меняются только соседние символы, а не весь DOM текста.
    for (let i = Math.max(0, Math.min(paintedLength, typed.length) - 1); i <= Math.max(paintedLength, typed.length) && i < characters.length; i++) {
      characters[i].className = "ch" + (i < typed.length ? (typed[i] === text[i] ? " ok" : " bad") : i === typed.length ? " cur" : "");
    }
    paintedLength = typed.length;
    const percent = text.length ? Math.round(typed.length / text.length * 100) : 0;
    sessionFill.style.transform = `scaleX(${percent / 100})`;
    sessionFill.parentElement.setAttribute("aria-valuenow", percent);
    sessionCount.textContent = percent + "%";
    hint();
  }
  async function load() {
    if (saving) return;
    const requestVersion = ++version;
    loading = true;
    updateKeyboardLayout();
    resetEffects();
    sessionFill.style.transform = "scaleX(0)";
    sessionFill.parentElement.setAttribute("aria-valuenow", "0");
    sessionCount.textContent = "0%";
    text = "";
    started = elapsedBefore = attempts = correct = combo = maxCombo = 0;
    typed = []; mistakes = {}; paused = finished = false; pendingResult = null;
    mobileInput.value = "";
    pause.textContent = "Пауза"; pause.disabled = true;
    restart.textContent = "Заново";
    typing.textContent = "Загрузка…"; status.textContent = ""; hud();
    try {
      const query = new URLSearchParams({ mode: selected("modes", "mode"), lang: selected("langs", "lang") });
      const exercise = await App.request("/exercises/generate?" + query);
      if (requestVersion !== version) return; // Старый ответ не заменяет новый режим.
      text = exercise.text.replace(/\r\n?/g, "\n").replace(/\t/g, "    ");
      render(); pause.disabled = false;
      status.textContent = "Нажмите на текст и начните печатать. Backspace — исправить, Enter — новая строка.";
      typing.focus();
    } catch (error) {
      if (requestVersion === version) { typing.textContent = "Не удалось загрузить упражнение"; status.textContent = error.message; }
    } finally { if (requestVersion === version) loading = false; }
  }
  async function save() {
    saving = true; restart.disabled = true;
    document.querySelectorAll("#modes button, #langs button").forEach(el => { el.disabled = true; });
    try {
      const result = await App.request("/stats/submit", { method: "POST", body: JSON.stringify(pendingResult) });
      pendingResult = null;
      status.textContent = `Тренировка сохранена! +${result.xp_gained} XP.` + result.new_achievements.map(item => " «" + item.title + "»").join("");
      restart.textContent = "Следующее упражнение";
      typing.classList.add("is-complete");
      const reward = `+${result.xp_gained} XP` + (result.level_up ? " · Новый уровень!" : " · Отличная работа!");
      message(reward, true);
      animateOnce(typing, [{ opacity: .7 }, { opacity: 1 }], 420);
      App.progress(await App.request("/users/me"));
    } catch (error) {
      status.textContent = error.message;
      restart.textContent = pendingResult ? "Повторить сохранение" : "Следующее упражнение";
    } finally {
      saving = false; restart.disabled = false;
      document.querySelectorAll("#modes button, #langs button").forEach(el => { el.disabled = false; });
    }
  }
  function handleTypingKey(event) {
    if (loading || paused || finished || !text || event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.key === "Backspace") {
      event.preventDefault(); typed.pop(); mobileInput.value = typed.join(""); combo = 0; render(); hud(); return;
    }
    const key = event.key === "Enter" ? "\n" : event.key;
    if (key.length !== 1) return;
    event.preventDefault();
    if (!started) started = performance.now();
    const expected = text[typed.length];
    const pressedKey = keyboard.find(key => key.node.classList.contains("is-next"));
    attempts++;
    if (key === expected) { correct++; combo++; maxCombo = Math.max(maxCombo, combo); }
    else { mistakes[expected] = (mistakes[expected] || 0) + 1; combo = 0; }
    typed.push(key); render(); hud();
    mobileInput.value = typed.join("");
    if (key === expected) {
      animateOnce(characters[typed.length - 1], [{ opacity: .35 }, { opacity: 1 }], 150);
      if (pressedKey) animateOnce(pressedKey.node, [{ transform: "translateY(2px)", opacity: .65 }, { transform: "none", opacity: 1 }], 130);
      if ([10, 20, 50].includes(combo) || (combo > 50 && combo % 50 === 0)) {
        message(`Серия ${combo}! ` + (combo >= 50 ? "×5 к опыту" : combo >= 20 ? "×3 к опыту" : "×2 к опыту"));
        animateOnce(comboBadge, [{ transform: "scale(1)" }, { transform: "scale(1.09)", offset: .45 }, { transform: "scale(1)" }], 260);
      }
    } else if (performance.now() - lastErrorAt > 350) {
      // Одна мягкая вспышка рамки даже при нескольких ошибках подряд.
      lastErrorAt = performance.now();
      animateOnce(typing, [{ borderColor: "#ff5470" }, { borderColor: "#ffc857" }], 180);
    }
    if (typed.length === text.length) {
      finished = true; elapsedBefore = elapsed(); started = 0; pause.disabled = true;
      hud();
      pendingResult = { ...metrics(), max_combo: maxCombo, errors_json: mistakes, mode: selected("modes", "mode"), duration_seconds: elapsedBefore };
      save();
    }
  }
  typing.addEventListener("keydown", handleTypingKey);
  mobileInput.addEventListener("focus", () => { usesMobileInput = true; });
  // input работает и с экранной клавиатурой, где keydown часто возвращает Unidentified.
  mobileInput.addEventListener("input", event => {
    if (event.isComposing) return;
    const incoming = mobileInput.value;
    if (loading || paused || finished) { mobileInput.value = typed.join(""); return; }
    let common = 0;
    while (common < typed.length && common < incoming.length && typed[common] === incoming[common]) common++;
    while (typed.length > common) handleTypingKey({ key: "Backspace", preventDefault() {} });
    for (const key of incoming.slice(common)) handleTypingKey({ key: key === "\n" ? "Enter" : key, preventDefault() {} });
    mobileInput.value = typed.join("");
  });
  mobileInput.addEventListener("compositionend", () => mobileInput.dispatchEvent(new Event("input")));
  typing.addEventListener("click", () => {
    if (window.matchMedia("(pointer: coarse)").matches) mobileInput.focus();
  });
  pause.onclick = () => {
    if (loading || finished) return;
    if (!paused) { elapsedBefore = elapsed(); started = 0; }
    else if (attempts) started = performance.now();
    paused = !paused; pause.textContent = paused ? "Продолжить" : "Пауза";
    typing.classList.toggle("is-paused", paused);
    status.textContent = paused ? "Тренировка приостановлена" : "Продолжайте печатать";
    if (!paused) (usesMobileInput ? mobileInput : typing).focus();
  };
  restart.onclick = () => pendingResult ? save() : load();
  for (const [group, attr] of [["modes", "mode"], ["langs", "lang"]]) {
    document.getElementById(group).addEventListener("click", event => {
      const button = event.target.closest("button");
      if (!button || saving) return;
      document.querySelectorAll(`#${group} button`).forEach(el => el.setAttribute("aria-selected", el === button));
      load();
    });
  }
  document.addEventListener("visibilitychange", () => { if (document.hidden && started && !paused && !finished) pause.click(); });
  updateKeyboardLayout();
  try { if (!await App.ready) return; await load(); }
  catch (error) { status.textContent = error.message; }
  setInterval(() => { if (started && !paused && !finished) hud(); }, 250);
})();
