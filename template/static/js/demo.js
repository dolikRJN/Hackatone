/* Живой пример на главной: один таймер, пауза вне экрана, без автопечати в игре. */
(function () {
  "use strict";
  const line = document.querySelector("[data-typing-demo]");
  if (!line) return;
  const phrase = [...line.textContent];
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const characters = phrase.map(char => {
    const span = document.createElement("span");
    span.textContent = char;
    return span;
  });
  line.replaceChildren(...characters);
  const typoAt = phrase.findIndex((char, index) => index > phrase.length / 2 && char !== " ");
  let index = 0, phase = "type", corrected = false, timer = 0, visible = false;
  const between = (min, max) => min + Math.random() * (max - min);

  function paint() {
    characters.forEach((span, i) => {
      const mistake = phase === "fix" && i === index;
      span.textContent = mistake ? (phrase[i] === "р" ? "т" : "р") : phrase[i];
      span.className = "ch " + (mistake ? "bad" : i < index ? "ok" : i === index ? "demo-caret" : "demo-pending");
    });
  }
  function schedule(delay) {
    clearTimeout(timer);
    if (visible && !document.hidden && !reducedMotion.matches) timer = setTimeout(tick, delay);
  }
  function tick() {
    if (phase === "fix") {
      // Небольшая заминка, Backspace и правильная буква.
      phase = "type";
      corrected = true;
      paint();
      schedule(between(260, 420));
      return;
    }
    if (phase === "erase") {
      index--;
      if (index === 0) { phase = "type"; corrected = false; }
      paint();
      schedule(index ? between(45, 85) : 650);
      return;
    }
    if (index === typoAt && !corrected) {
      phase = "fix";
      paint();
      schedule(between(550, 750));
      return;
    }
    index++;
    paint();
    if (index === phrase.length) {
      phase = "erase";
      schedule(2200);
    } else schedule(phrase[index - 1] === " " ? between(250, 440) : between(90, 200));
  }
  function sync() {
    clearTimeout(timer);
    line.classList.toggle("is-demo-paused", !visible || document.hidden || reducedMotion.matches);
    if (reducedMotion.matches) {
      index = phrase.length; phase = "type"; corrected = false;
      paint(); // При уменьшении движения показываем готовую фразу без анимации.
    } else {
      if (index === phrase.length && phase === "type") { index = 0; paint(); }
      schedule(450);
    }
  }
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver(entries => {
      visible = entries[0].isIntersecting;
      sync();
    }, { threshold: .1 });
    observer.observe(line.closest(".lp-demo"));
  } else visible = true;
  document.addEventListener("visibilitychange", sync);
  reducedMotion.addEventListener("change", sync);
  paint();
  sync();
})();
