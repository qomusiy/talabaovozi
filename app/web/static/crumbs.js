/* Talaba Ovozi — breadcrumbs: the path taken to this page, remembered per browser tab.
   "O‘qituvchilar › Name › Dars jadvali › 25-16 IQT": every step links back, ‹ goes one step up.
   Loaded in the page header (not deferred), so the right path is shown before the page is drawn. */
(() => {
  const TRAIL = "admin.crumbs", NAV = "admin.nav", MAX = 8;
  const SEP = '<svg class="i sep" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6"/></svg>';
  const BACK = '<svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="m15 18-6-6 6-6"/></svg>';
  const data = JSON.parse(document.getElementById("crumb-data").textContent);
  const nav = document.getElementById("crumbs");
  const head = document.getElementById("head");
  const store = {
    get(key) { try { return JSON.parse(sessionStorage.getItem(key)); } catch (e) { return null; } },
    set(key, value) { try { sessionStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* storage off */ } },
    drop(key) { try { sessionStorage.removeItem(key); } catch (e) { /* storage off */ } },
  };
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = (s, vars) => String(s).replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? "");

  // Where the next page is opened from. Sidebar links (data-nav) start a new path.
  const mark = (reset) => store.set(NAV, { from: location.pathname, reset, at: Date.now() });
  window.adminGo = (href) => { mark(false); location.href = href; };
  document.addEventListener("click", (e) => {
    const a = e.target.closest("a[href]");
    if (!a || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || a.target === "_blank") return;
    const u = new URL(a.href, location.href);
    if (u.origin !== location.origin || !u.pathname.startsWith("/admin") || /\.xlsx$|\/logout$/.test(u.pathname)) return;
    mark(a.hasAttribute("data-nav"));
  }, true);

  // Labels are stored with their text key, so a path remembered in one language is shown in the current one.
  const text = (l) => (l.k && data.texts[l.k] ? fmt(data.texts[l.k], l.v || {}) : l.s);
  // A step that shows the same thing as the one before it uses its short name ("Name › Dars jadvali").
  const name = (c, prev) => text(c.ctx && prev && c.entity && prev.entity === c.entity ? c.ctx : c.label);
  // Going back keeps the survey chosen on this page.
  const campaign = new URLSearchParams(location.search).get("campaign");
  const href = (c) => {
    if (!campaign) return c.url;
    const u = new URL(c.url, location.origin);
    u.searchParams.set("campaign", campaign);
    return u.pathname + u.search + u.hash;
  };

  function draw(trail) {
    head.classList.toggle("crumbed", trail.length > 1);
    if (trail.length < 2) { nav.innerHTML = ""; return; }
    const steps = trail.map((c, i) => {
      const label = esc(name(c, trail[i - 1]));
      return `<li>${i ? SEP : ""}${i === trail.length - 1
        ? `<span aria-current="page">${label}</span>` : `<a href="${esc(href(c))}">${label}</a>`}</li>`;
    });
    nav.innerHTML = `<a class="crumb-back" href="${esc(href(trail[trail.length - 2]))}" data-tip="${esc(nav.dataset.back)}"
      aria-label="${esc(nav.dataset.backLabel)}">${BACK}</a><ol>${steps.join("")}</ol>`;
  }

  function sync() {
    const me = data.self;
    let trail = store.get(TRAIL) || [];
    const came = store.get(NAV);
    store.drop(NAV);
    const fresh = came && Date.now() - came.at < 15000;
    const at = trail.findIndex((c) => c.path === me.path);
    const last = trail[trail.length - 1];
    if (fresh && came.reset) trail = [me];
    else if (at >= 0) trail = [...trail.slice(0, at), me];          // back to a step (or the same page with new filters)
    else if (fresh && last && came.from === last.path) {
      trail = last.kind === me.kind ? [...trail.slice(0, -1), me] : [...trail, me];  // a sibling replaces the step
    } else trail = data.fallback;                                     // opened directly: the page's usual place
    if (trail.length > MAX) trail = [trail[0], ...trail.slice(-(MAX - 1))];
    store.set(TRAIL, trail);
    draw(trail);
  }

  sync();
  window.addEventListener("pageshow", (e) => { if (e.persisted) sync(); });  // back/forward from the browser's cache
})();
