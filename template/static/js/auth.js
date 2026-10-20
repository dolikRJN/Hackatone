/* Общий клиент API и авторизация. Все запросы идут на тот же сервер, что и сайт. */
(function () {
  "use strict";
  const KEY = "th_user";
  let user = null;
  try { user = JSON.parse(localStorage.getItem(KEY)); } catch (_) { /* Повреждённое хранилище — гостевой вход. */ }
  if (!user?.token) user = null;
  const params = new URLSearchParams(location.search);
  const page = location.pathname.replace(/\/+$/, "") || "/";
  const legacyPages = new Map([["index", "/"], ["game", "/game"], ["profile", "/profile"], ["leaderboard", "/leaderboard"]]);
  function safeNext(value) {
    // Принимаем старые next=profile.html, но разрешаем переходы только внутри сайта.
    const route = legacyPages.get((value || "").replace(/^\//, "").replace(/\.html$/, ""));
    return value === "/" ? "/" : route || "/game";
  }

  // Единая карточка аккаунта для всех шапок. Данные пользователя вставляются ниже через textContent.
  document.querySelectorAll("[data-account]").forEach(container => {
    container.innerHTML = `
      <a class="user-chip" href="/profile" aria-label="Открыть мой профиль">
        <img class="avatar avatar--sm" src="/static/img/avatar.svg" alt="" width="40" height="38">
        <span class="user-chip__info">
          <span class="user-chip__name" data-nickname>Игрок</span>
          <small>Уровень <span data-level>1</span> · <span data-xp>0</span> XP</small>
        </span>
      </a>
      <a class="logout" href="/" data-logout>Выйти</a>`;
  });

  function setUser(value) {
    user = value;
    if (value) localStorage.setItem(KEY, JSON.stringify(value));
    else localStorage.removeItem(KEY);
  }

  async function request(path, options = {}) {
    const headers = { ...options.headers };
    if (options.body) headers["Content-Type"] = "application/json";
    if (user?.token) headers.Authorization = "Bearer " + user.token;
    let response;
    try { response = await fetch("/api/v1" + path, { ...options, headers }); }
    catch (_) { throw new Error("Сервер недоступен. Проверьте, что он запущен."); }
    const data = await response.json();
    if (!response.ok) {
      if (response.status === 401 && user && !path.startsWith("/auth/")) {
        setUser(null);
        location.replace("/auth?next=" + encodeURIComponent(safeNext(page)));
      }
      const detail = Array.isArray(data.detail) ? data.detail.map(item => item.msg).join("; ") : data.detail;
      throw new Error(detail || "Ошибка запроса");
    }
    return data;
  }

  function paintUser() {
    document.querySelectorAll("[data-only]").forEach(el => { el.hidden = el.dataset.only === "user" ? !user : !!user; });
    document.querySelectorAll("[data-play]").forEach(el => { el.href = user ? "/game" : "/auth?mode=register&next=%2Fgame"; });
    document.querySelectorAll("[data-nickname]").forEach(el => { el.textContent = user?.nickname || "Игрок"; });
    if (user?.level_id) renderProgress(user);
  }

  function progress(me) {
    // После тренировки обновляем не только полосу XP, но и карточку/кеш аккаунта.
    if (user) setUser({ ...user, ...me });
    paintUser();
  }

  function renderProgress(me) {
    const next = me.next_level_xp;
    const percent = next ? Math.min(100, (me.xp - me.level_start) / (next - me.level_start) * 100) : 100;
    document.querySelectorAll("[data-level]").forEach(el => { el.textContent = me.level_id; });
    document.querySelectorAll("[data-xp]").forEach(el => { el.textContent = me.xp; });
    document.querySelectorAll("[data-xp-next]").forEach(el => { el.textContent = next ?? "максимум"; });
    const fill = document.getElementById("xp-fill");
    if (fill) {
      fill.style.setProperty("--p", percent + "%");
      fill.parentElement.setAttribute("aria-valuenow", Math.round(percent));
    }
  }

  // Другие скрипты ждут проверку сохранённого токена через App.ready.
  window.App = { request, progress, get user() { return user; } };
  App.ready = (async () => {
    if (user) {
      try {
        const me = await request("/users/me");
        progress(me);
      } catch (error) {
        paintUser();
        throw error;
      }
    }
    paintUser();
    if (document.body.dataset.auth === "required" && !user) {
      location.replace("/auth?mode=login&next=" + encodeURIComponent(safeNext(page)));
      return null;
    }
    return user;
  })();
  // На публичных страницах ошибка авторизации тоже должна быть обработана.
  App.ready.catch(error => { console.error(error.message); });
  paintUser();

  document.querySelectorAll("[data-logout]").forEach(el => {
    el.addEventListener("click", async event => {
      event.preventDefault();
      try { if (user) await request("/auth/logout", { method: "POST" }); }
      catch (_) { /* Локальный выход доступен и при недоступном сервере. */ }
      setUser(null);
      location.href = "/";
    });
  });

  const login = document.getElementById("form-login");
  if (!login) return;
  const register = document.getElementById("form-register");
  function show(mode) {
    const isLogin = mode !== "register";
    login.hidden = !isLogin;
    register.hidden = isLogin;
    document.getElementById("tab-login").setAttribute("aria-selected", isLogin);
    document.getElementById("tab-register").setAttribute("aria-selected", !isLogin);
  }
  document.getElementById("tab-login").onclick = () => show("login");
  document.getElementById("tab-register").onclick = () => show("register");
  document.querySelectorAll("[data-switch]").forEach(el => {
    el.onclick = event => { event.preventDefault(); show(el.dataset.switch); };
  });
  show(params.get("mode"));
  App.ready.then(current => { if (current) location.replace(safeNext(params.get("next"))); }).catch(() => {});

  for (const [kind, form] of [["login", login], ["register", register]]) {
    form.addEventListener("submit", async event => {
      event.preventDefault();
      const error = document.getElementById(kind + "-error");
      const button = form.querySelector('[type="submit"]');
      error.hidden = true;
      const data = Object.fromEntries(new FormData(form));
      if (kind === "register" && data.password !== data.password2) {
        error.textContent = "Пароли не совпадают";
        error.hidden = false;
        return;
      }
      delete data.password2;
      button.disabled = true;
      try {
        const result = await request("/auth/" + kind, { method: "POST", body: JSON.stringify(data) });
        setUser({ token: result.token });
        const me = await request("/users/me");
        setUser({ ...me, token: result.token });
        location.href = safeNext(params.get("next"));
      } catch (exception) {
        error.textContent = exception.message;
        error.hidden = false;
      } finally { button.disabled = false; }
    });
  }
})();
