/* Один скрипт наполняет таблицу лидеров и краткий рейтинг на главной. */
(async function () {
  "use strict";
  const table = document.getElementById("leaders") || document.getElementById("home-leaders");
  const compact = table.id === "home-leaders";
  const status = document.getElementById("leaders-status");
  const number = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 });
  // Колонки читаются из заголовков: порядок ячеек всегда совпадает с таблицей.
  const headers = [...table.closest("table").querySelectorAll("th[data-field]")];
  let version = 0;
  async function load() {
    const current = ++version;
    status.textContent = "Загрузка рейтинга…";
    const metric = document.querySelector('#metric [aria-selected="true"]')?.dataset.metric || "speed";
    const period = document.querySelector('#period [aria-selected="true"]')?.dataset.period || "all";
    try {
      const entries = await App.request(`/stats/leaderboard?sort_by=${metric}&period=${period}`);
      if (current !== version) return;
      const xpHeader = headers.find(header => header.dataset.field === "xp");
      if (xpHeader) xpHeader.textContent = { all: "Опыт", day: "Опыт за сегодня", week: "Опыт за неделю" }[period];
      table.replaceChildren(...entries.slice(0, compact ? 5 : 20).map(item => {
        const row = document.createElement("tr");
        if (item.user_id === App.user?.id) row.className = "is-me";
        const values = {
          rank: item.rank, username: item.username, wpm: number.format(item.wpm),
          cpm: number.format(Math.round(item.wpm * 5)), accuracy: number.format(item.accuracy) + "%",
          xp: number.format(period === "all" ? item.xp : item.value),
        };
        headers.forEach(header => {
          const td = document.createElement("td");
          td.dataset.field = header.dataset.field;
          // И заголовки, и значения чисел должны выравниваться по правому краю.
          td.className = header.className;
          if (header.dataset.field === "rank") {
            const badge = document.createElement("span");
            badge.className = "place" + (item.rank <= 3 ? " place--" + item.rank : "");
            badge.textContent = item.rank;
            td.append(badge);
          } else td.textContent = values[header.dataset.field];
          row.append(td);
        });
        return row;
      }));
      status.textContent = entries.length ? "" : "Пока нет завершённых тренировок за этот период";
    } catch (error) { if (current === version) status.textContent = error.message; }
  }
  for (const id of ["metric", "period"]) {
    document.getElementById(id)?.addEventListener("click", event => {
      const button = event.target.closest("button");
      if (!button) return;
      document.querySelectorAll(`#${id} button`).forEach(el => el.setAttribute("aria-selected", el === button));
      load();
    });
  }
  try { await App.ready; await load(); } catch (error) { status.textContent = error.message; }
})();
