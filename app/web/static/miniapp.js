/* Talaba Ovozi — the admins' Mini App: survey numbers in Telegram. Read-only; the data comes from /api/miniapp/admin. */
(() => {
  const tg = window.Telegram && window.Telegram.WebApp;
  const inTelegram = !!(tg && tg.initData);
  const app = document.getElementById("app");
  let T = window.MINI_TEXTS.uz;

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = (s, v) => s.replace(/\{(\w+)\}/g, (_, k) => v[k]);
  const num = (n) => (n == null ? "—" : Number(n).toLocaleString("ru-RU"));
  const pct = (p) => Math.max(0, Math.min(100, Number(p) || 0));
  const state = (text) => { app.innerHTML = `<div class="state">${esc(text)}</div>`; app.removeAttribute("aria-busy"); };

  function bars(rows) {
    return `<div class="rows">${rows.map((r) => `<div class="row"><div class="t"><span>${esc(r.label)}</span><b>${esc(r.value)}</b></div>
      <div class="track"><i style="width:${pct(r.pct)}%;${r.color ? `background:${r.color}` : ""}"></i></div></div>`).join("")}</div>`;
  }

  function render(d) {
    T = d.texts;
    document.documentElement.lang = d.lang;
    const s = d.stats, c = s.campaign;
    let html = `<header class="head"><div><small>Talaba Ovozi</small><h1>${esc(T.title)}</h1></div>
      <div class="who">${esc(d.admin.name)}<br>${esc(d.admin.role)}<br><button class="refresh" id="refresh">${esc(T.refresh)}</button></div></header>`;
    if (!c) {
      html += `<section class="card"><div class="meta">${esc(T.no_survey)}</div></section>`;
    } else {
      const left = c.days_left <= 0 ? T.left_today : fmt(T.left, { n: c.days_left });
      html += `<section class="card survey"><div class="top"><div><b class="title">${esc(c.title)}</b>
          <div class="meta">${esc(fmt(T.closes, { date: c.closes }))}${c.open ? " · " + esc(left) : ""}</div></div>
          <span class="pill ${c.open ? "open" : "closed"}">${esc(c.open ? T.open : T.closed)}</span></div>
        <div class="big"><b>${s.participation_pct}%</b><span>${esc(T.participation)} · ${esc(fmt(T.of_students, { p: num(s.participants), n: num(s.students) }))}</span></div>
        <div class="track"><i style="width:${pct(s.participation_pct)}%"></i></div></section>
      <section class="grid2">
        <div class="kpi"><div class="l">${esc(T.ratings)}</div><div class="v">${num(s.evaluations)}</div>${c.open ? `<div class="f">${esc(fmt(T.today, { n: s.today }))}</div>` : ""}</div>
        <div class="kpi"><div class="l">${esc(T.average)}</div><div class="v">${s.overall ?? "—"}<small style="font-size:13px;color:var(--muted)"> / 10</small></div></div>
        <div class="kpi"><div class="l">${esc(T.completed)}</div><div class="v">${num(s.completed)}</div></div>
        <div class="kpi"><div class="l">${esc(T.comments)}</div><div class="v">${num(s.comments)}</div></div>
      </section>
      <section class="card"><h2>${esc(T.criteria)}</h2>${bars(["teaching", "fairness", "professionalism"].map((k, i) => (
        { label: T[k], value: s[k] ?? "—", pct: (s[k] || 0) * 10, color: `var(--c${i + 1})` })))}</section>`;
      if (s.courses && s.courses.length) {
        html += `<section class="card"><h2>${esc(T.by_course)}</h2>${bars(s.courses.map((x) => (
          { label: x.course ? fmt(T.course, { n: x.course }) : "—", value: `${x.participation_pct}% · ${x.participants}/${x.students}`, pct: x.participation_pct })))}</section>`;
      }
      if (s.low_groups && s.low_groups.length) {
        html += `<section class="card"><h2>${esc(T.low)}</h2><ul class="low">${s.low_groups.map((g) =>
          `<li>${esc(g.name)}<span><b>${g.participation_pct}%</b> · ${g.participants}/${g.students}</span></li>`).join("")}</ul></section>`;
      }
      if (s.daily && s.daily.length) {
        const max = Math.max(...s.daily.map((x) => x.count), 1);
        html += `<section class="card"><h2>${esc(T.daily)}</h2><div class="days">${s.daily.map((x) =>
          `<div><b>${x.count}</b><i style="height:${Math.round((x.count / max) * 80)}px"></i>${esc(x.date.slice(8, 10) + "." + x.date.slice(5, 7))}</div>`).join("")}</div></section>`;
      }
      if (d.comments.length) {
        html += `<section class="card"><h2>${esc(T.latest)}</h2>${d.comments.map((x) => `<div class="comment">
          <div class="h"><span><b>${esc(x.teacher)}</b> · ${esc(x.group || "—")}${x.student ? " · " + esc(x.student) : ""}</span><span>${x.overall} · ${esc(x.date)}</span></div>
          <p>${esc(x.comment)}</p></div>`).join("")}</section>`;
      }
    }
    const site = s.site;
    html += `<section class="card"><h2>${esc(T.links)} · ${esc(T["site_" + site.state] || T.site_unknown)}</h2>
      ${d.links.survey ? link(T.survey_link, d.links.survey) : ""}
      ${d.links.admin ? link(T.admin_link, d.links.admin) : `<div class="link"><span class="l">${esc(T.admin_link)}</span><span>${esc(T.admin_closed)}</span><code>${esc(d.links.local)}</code></div>`}
      <div class="link"><span class="l">${esc(T.in_bot)}</span><b>${num(s.in_bot)} / ${num(s.students)}</b></div></section>`;
    app.innerHTML = html;
    app.removeAttribute("aria-busy");
    document.getElementById("refresh").addEventListener("click", load);
    app.querySelectorAll("[data-copy]").forEach((b) => b.addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(b.dataset.copy); b.textContent = T.copied; } catch (e) { /* not allowed */ }
    }));
    app.querySelectorAll("[data-open]").forEach((b) => b.addEventListener("click", () => {
      if (inTelegram && tg.openLink) tg.openLink(b.dataset.open); else window.open(b.dataset.open, "_blank");
    }));
  }

  function link(label, url) {
    return `<div class="link"><span class="l">${esc(label)}</span><code>${esc(url)}</code>
      <div class="btns"><button class="primary" data-open="${esc(url)}">${esc(T.open_link)}</button><button data-copy="${esc(url)}">${esc(T.copy)}</button></div></div>`;
  }

  async function load() {
    if (!inTelegram) return state(T.open_in_telegram);
    let res;
    try {
      res = await fetch("/api/miniapp/admin", { headers: { "X-Telegram-Init-Data": tg.initData } });
    } catch (e) { return state(T.error); }
    if (res.status === 403) return state(T.not_admin);
    if (!res.ok) return state(T.error);
    render(await res.json());
  }

  if (inTelegram) {
    tg.ready();
    tg.expand();
    const lang = (tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.language_code) || "uz";
    T = window.MINI_TEXTS[lang] || window.MINI_TEXTS.uz;
  }
  load();
})();
