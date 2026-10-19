// (function () {
//   "use strict";

//   var KEY = "th_user";

//   function getUser() {
//     try { return JSON.parse(localStorage.getItem(KEY)); } catch (e) { return null; }
//   }
//   function setUser(u) { localStorage.setItem(KEY, JSON.stringify(u)); }
//   function clearUser() { localStorage.removeItem(KEY); }
//   // Разрешаем редирект только на свои страницы вида name.html
//   function safeNext(v) { return /^[\w-]+\.html$/.test(v || "") ? v : "game.html"; }

//   var user = getUser();
//   var params = new URLSearchParams(location.search);
//   var page = location.pathname.split("/").pop() || "index.html";

//   // 1. Закрытые страницы (game, profile): без входа отправляем на регистрацию
//   if (document.body.dataset.auth === "required" && !user) {
//     location.replace("auth.html?mode=register&next=" + encodeURIComponent(page));
//     return;
//   }

//   // 2. Кнопки «Играть»: гость идёт на регистрацию, вошедший сразу в игру
//   document.querySelectorAll("[data-play]").forEach(function (a) {
//     a.href = user ? "game.html" : "auth.html?mode=register&next=game.html";
//   });

//   // 3. Элементы только для гостей / только для вошедших
//   document.querySelectorAll("[data-only]").forEach(function (el) {
//     el.hidden = el.dataset.only === "user" ? !user : !!user;
//   });

//   // 4. Ник игрока
//   if (user) {
//     document.querySelectorAll("[data-nickname]").forEach(function (el) {
//       el.textContent = user.nickname;
//     });
//   }

//   // 5. Выход
//   document.querySelectorAll("[data-logout]").forEach(function (a) {
//     a.addEventListener("click", function () { clearUser(); });
//   });

//   // 6. Страница входа и регистрации
//   var formLogin = document.getElementById("form-login");
//   if (!formLogin) return;

//   if (user) { location.replace(safeNext(params.get("next"))); return; }

//   var formRegister = document.getElementById("form-register");
//   var tabLogin = document.getElementById("tab-login");
//   var tabRegister = document.getElementById("tab-register");

//   function show(mode) {
//     var isLogin = mode !== "register";
//     formLogin.hidden = !isLogin;
//     formRegister.hidden = isLogin;
//     tabLogin.setAttribute("aria-selected", String(isLogin));
//     tabRegister.setAttribute("aria-selected", String(!isLogin));
//   }

//   tabLogin.addEventListener("click", function () { show("login"); });
//   tabRegister.addEventListener("click", function () { show("register"); });
//   document.querySelectorAll("[data-switch]").forEach(function (a) {
//     a.addEventListener("click", function (e) { e.preventDefault(); show(a.dataset.switch); });
//   });
//   show(params.get("mode"));

//   function showError(el, msg) { el.textContent = msg; el.hidden = false; }

//   // TODO бэкенд: заменить заглушку на настоящий запрос
//   // kind: "login" | "register", ответ должен вернуть { nickname, email, token }
//   async function request(kind, data) {
//     // var r = await fetch("/api/" + kind, {
//     //   method: "POST",
//     //   headers: { "Content-Type": "application/json" },
//     //   body: JSON.stringify(data)
//     // });
//     // if (!r.ok) throw new Error((await r.json()).message);
//     // return r.json();
//     return { nickname: data.nickname || data.email.split("@")[0], email: data.email, token: "demo" };
//   }

//   function handle(kind, form) {
//     var errEl = document.getElementById(kind + "-error");
//     form.addEventListener("submit", async function (e) {
//       e.preventDefault();
//       errEl.hidden = true;
//       var data = Object.fromEntries(new FormData(form));
//       if (kind === "register" && data.password !== data.password2) {
//         return showError(errEl, "Пароли не совпадают. Введи один и тот же пароль дважды.");
//       }
//       try {
//         setUser(await request(kind, data));
//         location.href = safeNext(params.get("next"));
//       } catch (err) {
//         showError(errEl, err.message || "Не получилось. Проверь данные и попробуй ещё раз.");
//       }
//     });
//   }

//   handle("login", formLogin);
//   handle("register", formRegister);
// })();
