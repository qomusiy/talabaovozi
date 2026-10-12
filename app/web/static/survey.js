/* Talaba Ovozi — the survey (Telegram Mini App). No framework: state -> render functions -> innerHTML.
   With a group picked in the bot: that group's teachers, one after another. Without one: every teacher, with a search. */
(() => {
  const CRITERIA = ["teaching", "fairness", "professionalism"];
  // Icons: Lucide (ISC license), inlined.
  const ICONS = {
    chevL: '<path d="m15 18-6-6 6-6"/>',
    chevR: '<path d="m9 18 6-6-6-6"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    cap: '<path d="M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z"/><path d="M22 10v6"/><path d="M6 12.5V16a6 3 0 0 0 12 0v-3.5"/>',
    book: '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
    scale: '<path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>',
    briefcase: '<path d="M16 20V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/><rect width="20" height="14" x="2" y="6" rx="2"/>',
    users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    building: '<path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/><path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/><path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"/><path d="M10 6h4"/><path d="M10 10h4"/><path d="M10 14h4"/><path d="M10 18h4"/>',
    door: '<path d="M13 4h3a2 2 0 0 1 2 2v14"/><path d="M2 20h3"/><path d="M13 20h9"/><path d="M10 12v.01"/><path d="M13 4.562v16.157a1 1 0 0 1-1.242.97L5 20V5.562a2 2 0 0 1 1.515-1.94l4-1A2 2 0 0 1 13 4.561Z"/>',
    msg: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    alert: '<circle cx="12" cy="12" r="10"/><path d="M12 8v4"/><path d="M12 16h.01"/>',
    inbox: '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
    phone: '<rect width="14" height="20" x="5" y="2" rx="2" ry="2"/><path d="M12 18h.01"/>',
    group: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    lock: '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
  };
  const icon = (name, cls = "") => `<svg class="i ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name]}</svg>`;

  const tg = window.Telegram && window.Telegram.WebApp;
  const inTelegram = !!(tg && tg.initData);
  const devUser = new URLSearchParams(location.search).get("dev");  // DEV_MODE, on this computer: ?dev=<Telegram id>
  const app = document.getElementById("app");

  let T = window.FALLBACK_TEXTS.uz;
  let data = null;
  let S = { comments: true, comment_required: false, edit: true, notice: "" }; // survey settings from the dashboard
  let query = "";  // the search, without a group

  // ---------- Helpers ----------
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = (s, vars) => s.replace(/\{(\w+)\}/g, (_, k) => vars[k]);
  const avg = (fb) => (CRITERIA.reduce((s, c) => s + fb[c], 0) / CRITERIA.length).toFixed(1);
  const isDark = () => document.documentElement.dataset.theme === "dark";

  function haptic(kind) {
    try {
      if (!tg || !tg.HapticFeedback) return;
      if (kind === "select") tg.HapticFeedback.selectionChanged();
      else tg.HapticFeedback.notificationOccurred(kind);
    } catch (_) { /* older Telegram clients */ }
  }
  function headerColor(color) {
    try { if (tg && tg.setHeaderColor) tg.setHeaderColor(color); } catch (_) { /* unsupported */ }
    document.querySelector('meta[name="theme-color"]').content = color;
  }
  function headers() {
    const h = { "Content-Type": "application/json" };
    if (inTelegram) h["X-Telegram-Init-Data"] = tg.initData;
    else if (devUser) h["X-Dev-User"] = devUser;
    return h;
  }
  function toast(msg, kind = "ok") {
    document.querySelectorAll(".toast").forEach((t) => t.remove());
    const el = document.createElement("div");
    el.className = `toast ${kind}`;
    el.setAttribute("role", "status");
    el.innerHTML = `${icon(kind === "ok" ? "check" : "alert")}<span>${esc(msg)}</span>`;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 3200);
  }
  function setBackButton(handler) {
    if (!tg || !tg.BackButton) return;
    if (setBackButton.current) tg.BackButton.offClick(setBackButton.current);
    setBackButton.current = handler;
    if (handler) { tg.BackButton.onClick(handler); tg.BackButton.show(); } else tg.BackButton.hide();
  }
  function show(html) {
    app.innerHTML = html;
    app.removeAttribute("aria-busy");
    window.scrollTo(0, 0);
  }
  function closesText() {
    const s = new Intl.DateTimeFormat("ru-RU", { timeZone: "Asia/Tashkent", day: "2-digit", month: "2-digit",
      year: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(data.campaign.closes_at));
    return fmt(T.closes, { date: s.replace(",", "") });
  }
  const allMode = () => !data.group;
  /** With a group: unrated teachers first, so the next one to do is on top. Without: the ones rated first. */
  const ordered = () => [...data.teachers].sort((a, b) =>
    (allMode() ? !!b.feedback - !!a.feedback : !!a.feedback - !!b.feedback) || a.name.localeCompare(b.name));
  const ratedCount = () => data.teachers.filter((t) => t.feedback).length;
  const fold = (s) => String(s || "").toLowerCase().replace(/[‘’ʻʼ'`]/g, "");
  const matches = (t, q) => !q || fold([t.name, t.department, ...t.subjects.map((x) => x.name)].join(" ")).includes(q);

  function state(iconName, title, text, tone = "") {
    setBackButton(null);
    headerColor(isDark() ? "#0d1117" : "#f4f5f9");
    show(`<main class="wrap"><div class="state fade">
      <div class="badge ${tone} pop">${icon(iconName)}</div>
      <h1>${esc(title)}</h1><p>${esc(text)}</p></div></main>`);
  }

  // ---------- List ----------
  const SHOWN = 60;  // without a group: at most this many cards until the search narrows them down
  function cards(list) {
    return list.map((t, i) => `
      <button class="t-card fade" style="animation-delay:${Math.min(i, 8) * 30}ms" data-id="${t.id}">
        <span><div class="name">${esc(t.name)}</div>
          <div class="subj">${esc(allMode() && t.department ? t.department : t.subjects.map((s) => s.name).join(" · "))}</div></span>
        ${t.feedback
          ? `<span class="status done">${icon("check")}${avg(t.feedback)}</span>`
          : `<span class="status">${esc(T.rate)}${icon("chevR")}</span>`}
      </button>`).join("");
  }
  function bindCards(root) {
    root.querySelectorAll(".t-card").forEach((b) => b.addEventListener("click", () => {
      const t = data.teachers.find((x) => x.id === Number(b.dataset.id));
      if (t.feedback && !S.edit) { haptic("warning"); return toast(T.rating_locked, "error"); }
      renderForm(t.id);
    }));
  }
  /** Without a group: the teachers rated so far, then everyone that matches the search. */
  function allList() {
    const q = fold(query.trim());
    const rated = ordered().filter((t) => t.feedback && matches(t, q));
    const rest = ordered().filter((t) => !t.feedback && matches(t, q));
    if (!rated.length && !rest.length) return `<p class="no-results">${esc(T.nothing_found)}</p>`;
    return (rated.length ? `<div class="section-title"><h3>${esc(T.rated_section)}</h3><span>${rated.length}</span></div>${cards(rated)}` : "")
      + `<div class="section-title"><h3>${esc(T.all_teachers)}</h3><span>${rest.length}</span></div>${cards(rest.slice(0, SHOWN))}`;
  }
  function renderList() {
    setBackButton(null);
    headerColor(isDark() ? "#0d1117" : "#f4f5f9");
    const done = ratedCount(), total = data.teachers.length;
    const C = 2 * Math.PI * 30;
    const offset = C * (1 - (total ? done / total : 0));
    const notice = S.notice ? `<div class="note notice fade">${icon("info")}<span>${esc(S.notice)}</span></div>` : "";
    if (allMode()) {
      show(`
        <main class="wrap">
          <section class="summary fade">
            <div class="badge pop">${icon("users")}</div>
            <div>
              <h2>${esc(T.title)}</h2>
              <div class="line">${icon("check")}${esc(fmt(T.rated_n, { n: done }))}</div>
              <div class="line">${icon("clock")}${esc(closesText())}</div>
            </div>
          </section>
          ${notice}
          <div class="note fade">${icon("info")}<span>${esc(T.no_group_note)}</span></div>
          <label class="search fade">${icon("search")}<input type="search" id="q" value="${esc(query)}"
            placeholder="${esc(T.search)}" aria-label="${esc(T.search)}" autocomplete="off"></label>
          <section id="cards">${allList()}</section>
          <div style="height:24px"></div>
        </main>`);
      const box = document.getElementById("cards");
      bindCards(box);
      document.getElementById("q").addEventListener("input", (e) => {
        query = e.target.value;
        box.innerHTML = allList();
        bindCards(box);
      });
      return;
    }
    show(`
      <main class="wrap">
        <section class="summary fade">
          <div class="ring ${done === total ? "done" : ""}">
            <svg viewBox="0 0 72 72" aria-hidden="true"><circle class="track" cx="36" cy="36" r="30"/>
              <circle class="bar" cx="36" cy="36" r="30" stroke-dasharray="${C}" stroke-dashoffset="${offset}"/></svg>
            <div class="num">${done}/${total}</div>
          </div>
          <div>
            <h2>${esc(T.title)}</h2>
            <div class="line">${icon("group")}${esc(data.group)}</div>
            <div class="line">${icon("check")}${esc(fmt(T.progress, { done, total }))}</div>
            <div class="line">${icon("clock")}${esc(closesText())}</div>
          </div>
        </section>
        ${notice}
        <div class="section-title"><h3>${esc(T.your_teachers)}</h3><span>${total}</span></div>
        <section id="cards">${cards(ordered())}</section>
        <div style="height:24px"></div>
      </main>`);
    bindCards(app);
  }

  // ---------- Form ----------
  // One structured form: the teacher, the three criteria on a 1-10 scale, the comment (optional or required).
  const COMMENT_MIN = 10;  // characters, when the dashboard makes the comment required
  function renderForm(teacherId) {
    const list = allMode() ? data.teachers.filter((x) => x.feedback || x.id === teacherId) : ordered();
    const t = data.teachers.find((x) => x.id === teacherId);
    const pos = list.findIndex((x) => x.id === teacherId) + 1;
    const values = Object.fromEntries(CRITERIA.map((c) => [c, t.feedback ? t.feedback[c] : null]));
    const needComment = S.comments && S.comment_required;
    setBackButton(renderList);
    headerColor(isDark() ? "#0d1117" : "#f4f5f9");

    const facts = [
      t.department && `<span>${icon("building")}${esc(t.department)}</span>`,
      t.room && `<span>${icon("door")}${esc(T.room)} ${esc(t.room)}</span>`,
    ].filter(Boolean).join("");
    const done = list.filter((x) => x.feedback).length;

    show(`
      <div class="topbar"><div class="wrap">
        <button class="icon-btn" id="back" aria-label="${esc(T.back_to_list)}">${icon("chevL")}</button>
        <span class="step">${esc(allMode() ? T.all_teachers : fmt(T.teacher_step, { n: pos, total: list.length }))}</span>
        <span class="topbar-count">${allMode() ? esc(fmt(T.rated_n, { n: done })) : `${done} / ${list.length}`}</span>
      </div><div class="topbar-progress"><i style="width:${allMode() ? 0 : list.length ? (100 * done) / list.length : 0}%"></i></div></div>
      <main class="wrap">
        <section class="card teacher">
          <h2>${esc(t.name)}</h2>
          ${facts ? `<div class="facts">${facts}</div>` : ""}
          <dl class="subjects">
            <dt>${esc(T.subjects)}</dt>
            ${t.subjects.map((s) => `<dd><b>${esc(s.name)}</b><span>${s.types.map((k) => esc(T[k] || k)).join(", ")}</span></dd>`).join("")}
          </dl>
        </section>
        <section class="card form">
          <div class="form-head"><h3>${esc(T.criteria_title)}</h3><span>${esc(T.scale_note)}</span></div>
          ${CRITERIA.map((c, i) => `
            <div class="criterion" data-c="${c}">
              <div class="crit-head">
                <span class="crit-num">${i + 1}</span>
                <div class="txt"><div class="label">${esc(T[c])}</div><div class="hint">${esc(T[c + "_hint"])}</div></div>
                <div class="score" aria-live="polite"></div>
              </div>
              <div class="scale" role="radiogroup" aria-label="${esc(T[c])}">
                ${Array.from({ length: 10 }, (_, k) =>
                  `<button class="chip" type="button" role="radio" aria-checked="false" data-v="${k + 1}">${k + 1}</button>`).join("")}
              </div>
            </div>`).join("")}
        </section>
        ${S.comments ? `<section class="card comment-card">
          <label class="field-label" for="comment">${esc(T.comment)}
            <span class="${needComment ? "req" : "opt"}">${esc(needComment ? T.comment_required : T.comment_optional)}</span></label>
          <textarea id="comment" maxlength="2000" placeholder="${esc(T.comment_placeholder)}">${esc(t.feedback ? t.feedback.comment : "")}</textarea>
          <div class="counter">${needComment ? `<span class="min">${esc(fmt(T.comment_min, { n: COMMENT_MIN }))}</span>` : "<span></span>"}
            <span><span id="count">0</span> / 2000</span></div>
        </section>` : ""}
        <div class="spacer"></div>
      </main>
      <div class="footer"><div class="wrap"><button class="btn" id="submit"></button></div></div>`);

    const submit = document.getElementById("submit");
    const comment = document.getElementById("comment"), count = document.getElementById("count");
    const commentShort = () => needComment && (!comment || comment.value.trim().length < COMMENT_MIN);
    const missing = () => CRITERIA.filter((c) => !values[c]);
    const updateSubmit = () => {
      const m = missing().length;
      submit.classList.toggle("pending", m > 0 || commentShort());
      submit.textContent = m ? fmt(T.remaining, { n: m }) : commentShort() ? T.write_comment : (t.feedback ? T.update : T.submit);
    };
    const paint = (section) => {
      const v = values[section.dataset.c];
      section.querySelectorAll(".chip").forEach((chip) => {
        const n = Number(chip.dataset.v);
        chip.classList.toggle("on", n === v);
        chip.classList.toggle("in", !!v && n < v);
        chip.setAttribute("aria-checked", String(n === v));
      });
      const score = section.querySelector(".score");
      score.classList.toggle("empty", !v);
      score.innerHTML = `<div class="v">${v || "—"}<small> / 10</small></div>`;
    };
    app.querySelectorAll(".criterion").forEach((section) => {
      paint(section);
      section.querySelectorAll(".chip").forEach((chip) => chip.addEventListener("click", () => {
        values[section.dataset.c] = Number(chip.dataset.v);
        haptic("select");
        paint(section);
        updateSubmit();
      }));
    });
    updateSubmit();

    if (comment) {
      const updateCount = () => {
        count.textContent = comment.value.length;
        const min = app.querySelector(".counter .min");
        if (min) min.classList.toggle("ok", !commentShort());
        updateSubmit();
      };
      comment.addEventListener("input", updateCount);
      updateCount();
    }
    document.getElementById("back").addEventListener("click", renderList);

    submit.addEventListener("click", async () => {
      const m = missing();
      if (m.length) {
        haptic("warning");
        toast(T.need_all, "error");
        app.querySelector(`[data-c="${m[0]}"]`).scrollIntoView({ behavior: "smooth", block: "center" });
        return;
      }
      if (commentShort()) {
        haptic("warning");
        toast(fmt(T.need_comment, { n: COMMENT_MIN }), "error");
        comment.focus();
        comment.scrollIntoView({ behavior: "smooth", block: "center" });
        return;
      }
      submit.disabled = true;
      submit.innerHTML = `<span class="spin"></span>${esc(T.saving)}`;
      let res;
      try {
        res = await fetch(`/api/survey/teachers/${t.id}`, {
          method: "POST", headers: headers(), body: JSON.stringify({ ...values, comment: comment ? comment.value : null }),
        });
      } catch (e) {
        return fail(T.network_error);
      }
      if (!res.ok) {
        const detail = await res.json().then((j) => j.detail, () => null);
        if (detail === "no_campaign") return fail(T.closed_now);
        if (detail === "locked") return fail(T.rating_locked);
        if (detail === "comment_required") return fail(fmt(T.need_comment, { n: COMMENT_MIN }));
        if (detail === "too_many") return fail(T.too_many);
        if (detail === "blocked" || detail === "suspended") return state("lock", "Talaba Ovozi", T.blocked, "bad");
        if (res.status === 401 || res.status === 403) return fail(T.session_expired);
        return fail(T.error);
      }
      t.feedback = { ...values, comment: comment ? comment.value : "" };
      haptic("success");
      toast(T.saved);
      if (allMode()) return renderList();
      const next = ordered().find((x) => !x.feedback);
      if (next) renderForm(next.id);
      else renderDone();
    });
    function fail(msg) {
      haptic("error");
      toast(msg, "error");
      submit.disabled = false;
      updateSubmit();
    }
  }

  // ---------- Done ----------
  function renderDone() {
    setBackButton(null);
    headerColor(isDark() ? "#0d1117" : "#f4f5f9");
    show(`
      <main class="wrap">
        <div class="state fade">
          <div class="badge good pop"><svg class="i check-anim" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg></div>
          <h1>${esc(T.all_done_title)}</h1>
          <p>${esc(T.all_done_text)}</p>
          <p class="small">${esc(S.edit ? T.all_done_hint : T.all_done_hint_locked)}</p>
        </div>
        <section class="card fade results">
          <div class="field-label" style="margin-bottom:6px">${esc(T.your_ratings)}</div>
          ${ordered().map((t) => `
            <div class="row"><span class="n">${esc(t.name)}</span><span class="s">${avg(t.feedback)}</span></div>`).join("")}
        </section>
        <div class="actions">
          ${inTelegram ? `<button class="btn" id="close">${esc(T.close_app)}</button>` : ""}
          <button class="btn secondary" id="list">${esc(T.back_to_list)}</button>
        </div>
        <div style="height:32px"></div>
      </main>`);
    document.getElementById("list").addEventListener("click", renderList);
    const close = document.getElementById("close");
    if (close) close.addEventListener("click", () => tg.close());
  }

  // ---------- Start ----------
  async function start() {
    if (inTelegram) {
      tg.ready();
      tg.expand();
      tg.onEvent("themeChanged", () => {
        document.documentElement.dataset.theme = tg.colorScheme === "dark" ? "dark" : "light";
      });
    }
    if (!inTelegram && !devUser) return state("phone", "Talaba Ovozi", T.open_in_telegram);
    let res;
    try {
      res = await fetch("/api/survey", { headers: headers() });
    } catch (e) {
      return state("alert", "Talaba Ovozi", T.network_error, "bad");
    }
    if (res.status === 403) {
      const detail = await res.json().then((j) => j.detail, () => null);
      if (detail === "blocked" || detail === "suspended") return state("lock", "Talaba Ovozi", T.blocked, "bad");
    }
    if (res.status === 401 || res.status === 403) return state("phone", "Talaba Ovozi", T.session_expired);
    if (!res.ok) return state("alert", "Talaba Ovozi", T.error, "bad");
    data = await res.json();
    T = data.texts;
    S = { ...S, ...(data.settings || {}) };
    document.documentElement.lang = data.lang;
    if (!data.campaign) return state("inbox", T.no_campaign_title, T.no_campaign_text);
    if (!data.teachers.length) return state("inbox", T.title, T.no_teachers);
    if (!allMode() && ratedCount() === data.teachers.length) return renderDone();
    renderList();
  }

  start();
})();
