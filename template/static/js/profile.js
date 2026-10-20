/* Профиль загружается из API; пользовательские строки вставляются как текст. */
(async function () {
  "use strict";
  const status = document.getElementById("profile-status");
  const cell = text => { const td = document.createElement("td"); td.textContent = text; return td; };
  function chart(history) {
    const canvas = document.getElementById("progressChart");
    const ctx = canvas.getContext("2d");
    const width = canvas.parentElement.clientWidth || 600;
    const height = 220;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = width * ratio; canvas.height = height * ratio;
    canvas.style.width = width + "px"; canvas.style.height = height + "px";
    ctx.scale(ratio, ratio);
    ctx.font = "12px sans-serif";
    ctx.fillStyle = "#efeaff";
    if (!history.length) { ctx.fillText("График появится после первой тренировки", 12, 40); return; }
    const entries = [...history].reverse();
    const maxSpeed = Math.max(100, ...entries.map(item => item.speed));
    ctx.fillText("Скорость (бирюзовый) / точность, % (розовый)", 12, 20);
    for (const [field, color, max] of [["speed", "#5eead4", maxSpeed], ["accuracy", "#ff6b9a", 100]]) {
      ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = 2; ctx.beginPath();
      entries.forEach((entry, i) => {
        const x = 20 + i * (width - 40) / Math.max(entries.length - 1, 1);
        const y = height - 25 - entry[field] / max * (height - 65);
        if (i) ctx.lineTo(x, y); else ctx.moveTo(x, y);
      });
      ctx.stroke();
      entries.forEach((entry, i) => {
        ctx.beginPath();
        ctx.arc(20 + i * (width - 40) / Math.max(entries.length - 1, 1), height - 25 - entry[field] / max * (height - 65), 3, 0, Math.PI * 2);
        ctx.fill();
      });
    }
    ctx.fillStyle = "#efeaff";
    ctx.fillText(`Максимум шкалы скорости: ${maxSpeed} слов/мин. Точность: 0–100%.`, 12, height - 4);
    canvas.setAttribute("aria-label", entries.map(item => `${item.speed} слов/мин, точность ${item.accuracy}%`).join("; "));
  }
  try {
    if (!await App.ready) return;
    const [summary, history, errors, all, unlocked] = await Promise.all([
      App.request("/stats/summary"), App.request("/stats/history"), App.request("/stats/error-analysis"),
      App.request("/stats/achievements"), App.request("/stats/achievements/my"),
    ]);
    document.getElementById("best-wpm").textContent = summary.best_wpm;
    document.getElementById("best-acc").textContent = summary.best_accuracy.toFixed(1) + "%";
    document.getElementById("sessions").textContent = summary.total_lessons;
    const minutes = Math.floor(summary.total_seconds / 60);
    document.getElementById("total-time").textContent = minutes < 1
      ? `${Math.floor(summary.total_seconds)} с`
      : `${Math.floor(minutes / 60)} ч ${minutes % 60} м`;
    document.getElementById("hard-keys").replaceChildren(...errors.problem_keys.map(key => {
      const li = document.createElement("li"); li.className = "chip";
      const b = document.createElement("b"); b.textContent = key === " " ? "␣" : key;
      li.append(b); return li;
    }));
    if (!errors.problem_keys.length) document.getElementById("hard-keys").textContent = "Пока нет ошибок";
    const ids = new Set(unlocked.map(item => item.id));
    document.querySelector(".ach-grid").replaceChildren(...all.map(item => {
      const div = document.createElement("div"); div.className = "ach" + (ids.has(item.id) ? "" : " is-locked");
      const icon = document.createElement("span"); icon.className = "ach__icon"; icon.textContent = ids.has(item.id) ? "🏆" : "🔒";
      const description = document.createElement("div");
      const title = document.createElement("strong"); title.textContent = item.title;
      const small = document.createElement("small"); small.textContent = item.description;
      description.append(title, small); div.append(icon, description); return div;
    }));
    const modes = { words: "Слова", sentences: "Предложения", text: "Предложения", code: "Код", symbols: "Символы" };
    document.getElementById("history").replaceChildren(...history.map(item => {
      const row = document.createElement("tr");
      // SQLite сохраняет UTC без суффикса часового пояса.
      row.append(...[new Date(item.created_at.replace(" ", "T") + "Z").toLocaleString("ru-RU"), modes[item.mode], item.speed, item.accuracy.toFixed(1) + "%", item.errors, "+" + item.xp_gained].map(cell));
      return row;
    }));
    if (!history.length) {
      const row = document.createElement("tr"); const td = cell("Пока нет тренировок. Начните игру!"); td.colSpan = 6; row.append(td);
      document.getElementById("history").append(row);
    }
    chart(history);
    window.addEventListener("resize", () => chart(history));
    status.textContent = "";
  } catch (error) { status.textContent = error.message; }
})();
