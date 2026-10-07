/* Talaba Ovozi — admin dashboard: motion, hover explanations, filters, sortable tables, charts (ECharts). */
(() => {
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const C = {
    ink: css("--ink"), ink2: css("--ink-2"), muted: css("--muted"), grid: css("--grid"), axis: css("--axis"),
    surface: css("--surface"), surface3: css("--surface-3"), border: css("--border"), other: css("--other"),
    s1: css("--s1"), s2: css("--s2"), s3: css("--s3"),
  };
  const ROOT = document.documentElement;
  // Ko‘rinish (the person's display settings) wins over the computer's settings.
  const DARK = ROOT.dataset.theme ? ROOT.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  const CALM = "motion" in ROOT.dataset || matchMedia("(prefers-reduced-motion: reduce)").matches;
  const FS = parseFloat(getComputedStyle(ROOT).fontSize) / 16 || 1;  // chart text follows the chosen text size
  const SERIES = [C.s1, C.s2, C.s3]; // the three criteria, always in this order
  const CRITERIA = ["teaching", "fairness", "professionalism"];
  const read = (id) => { const el = document.getElementById(id); return el ? JSON.parse(el.textContent) : {}; };
  const J = read("i18n");
  const D = read("page-data");
  const fmt = (s, vars) => String(s).replace(/\{(\w+)\}/g, (_, k) => vars[k]);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  // 1,234 in English; 1 234 in Uzbek and Russian (as the server writes them).
  const num = (n) => (n == null ? "—"
    : Number(n).toLocaleString("en-US").replace(/,/g, J.locale.startsWith("en") ? "," : " "));
  const alpha = (hex, a) => hex + Math.round(a * 255).toString(16).padStart(2, "0");

  // ---------- Motion ----------
  // The page comes in block by block (the delay per block is in admin.css).
  document.querySelectorAll(".content > *").forEach((el, i) => el.style.setProperty("--i", i));
  // Big numbers count up to their value; the final text is already in the page (and stays for "reduce motion").
  if (!CALM) document.querySelectorAll("[data-count]").forEach((el) => {
    const target = parseFloat(el.dataset.count), dec = Number(el.dataset.decimals || 0), final = el.textContent;
    if (!Number.isFinite(target)) return;
    const show = (v) => (dec ? v.toFixed(dec) : num(Math.round(v)));
    const t0 = performance.now(), dur = 900;
    el.classList.add("counting");
    el.textContent = show(0);
    const step = (now) => {
      const k = Math.min(1, (now - t0) / dur);
      el.textContent = k < 1 ? show(target * (1 - Math.pow(1 - k, 3))) : final;
      if (k < 1) requestAnimationFrame(step); else el.classList.remove("counting");
    };
    requestAnimationFrame(step);
  });
  // The header turns frosted with a hairline once the page scrolls under it.
  const topbar = document.getElementById("topbar");
  if (topbar) {
    const onScroll = () => topbar.classList.toggle("stuck", scrollY > 4);
    addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }
  // A thin bar at the top while the next page loads.
  const progress = document.getElementById("progress");
  const loading = () => progress && progress.classList.add("on");
  document.addEventListener("click", (e) => {
    const a = e.target.closest("a[href]");
    if (!a || e.defaultPrevented || e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey
        || a.target === "_blank" || a.hasAttribute("download")) return;
    const u = new URL(a.href, location.href);
    if (u.origin !== location.origin || /\.xlsx$/.test(u.pathname)
        || (u.pathname === location.pathname && u.search === location.search && u.hash)) return;
    loading();
  });
  document.addEventListener("submit", (e) => { if (!e.defaultPrevented) loading(); });
  addEventListener("pageshow", () => progress && progress.classList.remove("on"));
  // Opening a page from a script: the breadcrumbs (crumbs.js) count it as a step, like a link click.
  const go = (href) => { loading(); if (window.adminGo) window.adminGo(href); else location.href = href; };

  // Segmented controls: a thumb slides under the chosen option.
  function segmented(seg, onPick) {
    if (!seg) return;
    const buttons = [...seg.querySelectorAll("button")];
    const thumb = document.createElement("span");
    thumb.className = "thumb";
    thumb.setAttribute("aria-hidden", "true");
    seg.prepend(thumb);
    const place = (b, instant) => {
      if (instant) thumb.style.transition = "none";
      thumb.style.width = `${b.offsetWidth}px`;
      thumb.style.transform = `translateX(${b.offsetLeft}px)`;
      if (instant) { void thumb.offsetWidth; thumb.style.transition = ""; }
    };
    const current = () => seg.querySelector("button.on") || buttons[0];
    const init = () => { place(current(), true); seg.classList.add("ready"); };
    (document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(init);
    addEventListener("resize", () => place(current(), true));
    buttons.forEach((b) => b.addEventListener("click", () => {
      buttons.forEach((x) => { x.classList.toggle("on", x === b); x.setAttribute("aria-selected", String(x === b)); });
      place(b);
      if (onPick) onPick(b);
    }));
  }

  // ---------- Phones and tablets: the sidebar as a drawer ----------
  const navOpen = document.getElementById("nav-open"), scrim = document.getElementById("scrim");
  const setNav = (open) => {
    document.body.classList.toggle("nav-open", open);
    if (navOpen) navOpen.setAttribute("aria-expanded", String(open));
    if (scrim) scrim.hidden = !open;
  };
  if (navOpen) navOpen.addEventListener("click", () => setNav(true));
  const navClose = document.getElementById("nav-close");
  if (navClose) navClose.addEventListener("click", () => setNav(false));
  if (scrim) scrim.addEventListener("click", () => setNav(false));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") setNav(false); });
  addEventListener("pageshow", () => setNav(false));

  // ---------- Hover explanations: any element with data-tip ----------
  const tip = document.createElement("div");
  tip.className = "tip";
  tip.id = "tip";
  tip.setAttribute("role", "tooltip");
  document.body.appendChild(tip);
  let tipFor = null, tipTimer = 0, quiet = null; // quiet: clicked, so no tip until the pointer leaves it
  function showTip(el) {
    tip.textContent = el.dataset.tip;
    const r = el.getBoundingClientRect(), t = tip.getBoundingClientRect(), gap = 8;
    const top = r.top - t.height - gap >= gap ? r.top - t.height - gap : r.bottom + gap;  // above, or below if no room
    const left = Math.min(Math.max(gap, r.left + r.width / 2 - t.width / 2), innerWidth - t.width - gap);
    tip.style.top = `${top}px`;
    tip.style.left = `${left}px`;
    tip.classList.add("on");
    el.setAttribute("aria-describedby", "tip");
  }
  function hideTip() {
    clearTimeout(tipTimer);
    if (tipFor) tipFor.removeAttribute("aria-describedby");
    tipFor = null;
    tip.classList.remove("on");
  }
  function armTip(el) {
    if (el === tipFor) return;
    hideTip();
    if (!el || !el.dataset.tip) return;
    tipFor = el;
    tipTimer = setTimeout(() => showTip(el), 280);
  }
  document.addEventListener("mouseover", (e) => {
    const el = e.target.closest("[data-tip]");
    if (el !== quiet) quiet = null;
    if (!el || el !== quiet) armTip(el);
  });
  document.addEventListener("focusin", (e) => {
    if (e.target.matches(":focus-visible")) armTip(e.target.closest("[data-tip]"));
  });
  document.addEventListener("focusout", hideTip);
  document.addEventListener("mousedown", (e) => { quiet = e.target.closest("[data-tip]"); hideTip(); });
  let touchTimer = 0;
  document.addEventListener("pointerup", (e) => {
    if (e.pointerType !== "touch") return;
    const el = e.target.closest("[data-tip]");
    hideTip();
    if (!el || el.closest("a, button, input, select, textarea, summary, label")) return;
    tipFor = el;
    showTip(el);
    clearTimeout(touchTimer);
    touchTimer = setTimeout(hideTip, 2600);
  });
  window.addEventListener("scroll", hideTip, true);

  // ---------- Dropdowns (language): close on a click outside or Escape ----------
  const dropdowns = document.querySelectorAll("details.dropdown");
  document.addEventListener("click", (e) => dropdowns.forEach((d) => { if (d.open && !d.contains(e.target)) d.open = false; }));
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    hideTip();
    dropdowns.forEach((d) => { if (d.open) { d.open = false; d.querySelector("summary").focus(); } });
  });
  dropdowns.forEach((d) => d.addEventListener("toggle", () => { if (d.open) hideTip(); }));

  // ---------- Filters ----------
  const campaignSelect = document.getElementById("campaign-select");
  if (campaignSelect) campaignSelect.addEventListener("change", () => {
    const u = new URL(location.href);
    u.searchParams.set("campaign", campaignSelect.value);
    u.searchParams.delete("page");
    go(u.pathname + u.search);
  });
  document.querySelectorAll("tr.link").forEach((tr) => tr.addEventListener("click", (e) => {
    if (e.target.closest("a")) return;
    go(tr.dataset.href);
  }));

  // ---------- Overview: teacher ranking (top 10 / bottom 10 / most rated) ----------
  segmented(document.getElementById("rank-tabs"), (b) => {
    document.querySelectorAll(".rank").forEach((r) => (r.hidden = r.dataset.m !== b.dataset.m));
    document.getElementById("rank-sub").textContent = b.dataset.sub;
  });

  // ---------- Tables: search, filters, sorting by several columns ----------
  const table = document.getElementById("data-table");
  const search = document.getElementById("table-search");
  const onlyComments = document.getElementById("only-comments");
  const filters = [...document.querySelectorAll("select[data-filter]")];  // narrow the table only, never the charts
  function filterRows() {
    if (!table) return;
    const q = (search ? search.value : "").trim().toLowerCase();
    table.querySelectorAll("tbody tr").forEach((tr) => {
      const matches = !q || tr.textContent.toLowerCase().includes(q);
      const commentOk = !onlyComments || !onlyComments.checked || tr.dataset.hasComment === "1";
      const filtersOk = tr.children.length < 2 || filters.every((f) => !f.value || tr.dataset[f.dataset.filter] === f.value);
      tr.hidden = !(matches && commentOk && filtersOk);
    });
  }
  if (search) search.addEventListener("input", filterRows);
  if (onlyComments) onlyComments.addEventListener("change", filterRows);
  filters.forEach((f) => f.addEventListener("change", filterRows));

  // Sorting: the first column clicked orders the table, each next one orders within it (O‘qitish, then
  // Adolatlilik among equal O‘qitish...). Clicking a column again reverses it, a third time removes it.
  if (table && table.tBodies[0]) {
    const body = table.tBodies[0];
    const rows = [...body.rows].filter((r) => r.children.length > 1);
    rows.forEach((r, i) => (r.dataset.i = i));
    const heads = [...table.querySelectorAll("th.sortable")];
    // The page's own order (e.g. by overall score) gives way to the first click.
    let keys = heads.filter((th) => th.classList.contains("asc") || th.classList.contains("desc"))
      .map((th) => ({ th, desc: th.classList.contains("desc"), start: true, implicit: true }));
    const value = (tr, th) => {
      const td = tr.children[th.cellIndex], numeric = th.dataset.type === "num";
      const raw = td ? (td.dataset.v ?? td.textContent.trim()) : "";
      return numeric ? (parseFloat(raw) || 0) : String(raw).toLowerCase();
    };
    heads.forEach((th) => (th.dataset.label = th.textContent.trim()));   // before the order badges are added
    const label = (th) => th.dataset.label;
    const bar = document.createElement("div");
    bar.className = "sort-bar";
    bar.hidden = true;
    const head = table.closest(".card") && table.closest(".card").querySelector(".card-h");
    if (head) head.after(bar);
    function apply() {
      rows.sort((a, b) => {
        for (const k of keys) {
          const x = value(a, k.th), y = value(b, k.th);
          const r = typeof x === "number" ? x - y : x.localeCompare(y, J.locale);
          if (r) return k.desc ? -r : r;
        }
        return a.dataset.i - b.dataset.i;  // ties keep the page's order
      });
      rows.forEach((r) => body.appendChild(r));
      const user = keys.filter((k) => !k.implicit);
      heads.forEach((th) => {
        const k = keys.find((x) => x.th === th), n = user.indexOf(k) + 1;
        th.classList.toggle("asc", !!k && !k.desc);
        th.classList.toggle("desc", !!k && k.desc);
        th.setAttribute("aria-sort", k ? (k.desc ? "descending" : "ascending") : "none");
        let badge = th.querySelector(".sort-n");
        if (n && user.length > 1) {
          if (!badge) { badge = document.createElement("span"); badge.className = "sort-n"; th.appendChild(badge); }
          badge.textContent = n;
        } else if (badge) badge.remove();
      });
      bar.hidden = !user.length;
      bar.innerHTML = `<span class="lbl" data-tip="${esc(J.tip_sort)}">${esc(J.sort_by)}</span>` +
        user.map((k, i) => `<span class="key">${user.length > 1 ? `<b>${i + 1}</b>` : ""}${esc(label(k.th))}` +
          `<i>${k.desc ? "↓" : "↑"}</i></span>`).join('<span class="then">›</span>') +
        `<button type="button" class="clear">${esc(J.sort_clear)}</button>`;
    }
    bar.addEventListener("click", (e) => {
      if (!e.target.closest(".clear")) return;
      keys = [];
      apply();
    });
    heads.forEach((th) => {
      th.tabIndex = 0;
      const pick = () => {
        if (keys.every((k) => k.implicit)) keys = [];
        const i = keys.findIndex((k) => k.th === th), numeric = th.dataset.type === "num";
        if (i < 0) keys.push({ th, desc: numeric, start: numeric });   // numbers start high-to-low, text A-Z
        else if (keys[i].desc === keys[i].start) keys[i].desc = !keys[i].desc;
        else keys.splice(i, 1);
        apply();
      };
      th.addEventListener("click", pick);
      th.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } });
    });
  }

  // ---------- Management pages ----------
  // Forms that change or delete something ask first.
  document.querySelectorAll("form[data-confirm]").forEach((form) => form.addEventListener("submit", (e) => {
    if (!window.confirm(form.dataset.confirm)) e.preventDefault();
  }));
  // "Edit" buttons open the form below the row.
  document.querySelectorAll("[data-toggle]").forEach((b) => b.addEventListener("click", () => {
    const el = document.getElementById(b.dataset.toggle);
    el.hidden = !el.hidden;
    if (!el.hidden) (el.querySelector("input:not([type=hidden]), select, textarea") || el).focus();
  }));
  // Message to students: who gets it (lists per audience), how many, a photo/video/file, a Telegram-like preview.
  const bcForm = document.getElementById("bc-form");
  if (bcForm) {
    const audience = document.getElementById("bc-audience"), survey = document.getElementById("bc-survey");
    const count = document.getElementById("bc-count"), text = document.getElementById("bc-text");
    const media = document.getElementById("bc-media"), drop = document.getElementById("bc-drop");
    const fileRow = document.getElementById("bc-file"), len = document.getElementById("bc-len");
    const pvText = document.getElementById("pv-text"), pvImg = document.getElementById("pv-img");
    const pvDoc = document.getElementById("pv-doc"), pvBtn = document.getElementById("pv-btn");
    const button = document.getElementById("bc-button");
    const pickers = [...bcForm.querySelectorAll(".picker")];
    let timer;
    const update = () => {
      pickers.forEach((p) => {
        const on = p.dataset.aud === audience.value;
        p.hidden = !on;
        p.querySelectorAll("input[name=values]").forEach((i) => (i.disabled = !on));
        const n = p.querySelectorAll("input[name=values]:checked").length, label = p.querySelector(".pick-n");
        if (label) label.textContent = n ? fmt(label.dataset.text, { n }) : "";
      });
      clearTimeout(timer);
      timer = setTimeout(async () => {
        const q = new URLSearchParams({ audience: audience.value, survey: survey.disabled ? "" : survey.value });
        bcForm.querySelectorAll("input[name=values]:checked:not(:disabled)").forEach((i) => q.append("values", i.value));
        try {
          const r = await fetch(`/admin/bot/audience?${q}`);
          count.textContent = fmt(J.bc_count, { n: num((await r.json()).n) });
        } catch (e) { count.textContent = ""; }
      }, 200);
    };
    bcForm.addEventListener("change", (e) => { if (e.target !== media && e.target !== text) update(); });
    bcForm.querySelectorAll(".pick-search").forEach((box) => box.addEventListener("input", () => {
      const needle = box.value.trim().toLowerCase();
      const list = box.closest(".picker").querySelector(".pick-list");
      list.querySelectorAll(".pick-row").forEach((row) => (row.hidden = needle && !row.textContent.toLowerCase().includes(needle)));
      list.querySelectorAll(".pick-group").forEach((g) => (g.hidden = !g.querySelector(".pick-row:not([hidden])")));
    }));
    // Preview: the message as a student will see it in Telegram.
    let objectUrl = null;
    const preview = () => {
      pvText.textContent = text.value;
      const f = media.files[0], long = text.value.length > 1024 && f;
      len.textContent = text.value.length ? `${text.value.length} / 3500${long ? " · " + len.dataset.long : ""}` : "";
      if (objectUrl) { URL.revokeObjectURL(objectUrl); objectUrl = null; }
      pvImg.hidden = !(f && f.type.startsWith("image/"));
      if (!pvImg.hidden) { objectUrl = URL.createObjectURL(f); pvImg.src = objectUrl; }
      pvDoc.hidden = !f || !pvImg.hidden;
      if (!pvDoc.hidden) pvDoc.querySelector("span").textContent = f.name;
      pvBtn.hidden = !button.checked;
      drop.hidden = !!f;
      fileRow.hidden = !f;
      if (f) {
        fileRow.querySelector(".name").textContent = f.name;
        fileRow.querySelector(".size").textContent = `${(f.size / 1048576).toFixed(1)} MB`;
      }
    };
    text.addEventListener("input", preview);
    media.addEventListener("change", preview);
    button.addEventListener("change", preview);
    document.getElementById("bc-file-x").addEventListener("click", () => { media.value = ""; preview(); });
    ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, () => drop.classList.add("over")));
    ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, () => drop.classList.remove("over")));
    // A message needs text or a file (the textarea isn't "required" any more because a photo alone is fine).
    bcForm.addEventListener("submit", (e) => {
      if (!text.value.trim() && !media.files.length) { e.preventDefault(); text.focus(); }
    }, true);
    // "Send it to me first": to the admins' Telegram ids (settings), without leaving the page.
    const test = document.getElementById("bc-test");
    test.addEventListener("click", async () => {
      if (!text.value.trim() && !media.files.length) { text.focus(); return; }
      const label = test.innerHTML;
      test.disabled = true;
      test.classList.add("busy");
      test.textContent = test.dataset.busy;
      const data = new FormData(bcForm);
      try {
        const r = await (await fetch("/admin/bot/broadcast/test", { method: "POST", body: data })).json();
        toast(r.ok ? r.message : r.error, r.ok ? "good" : "bad");
      } catch (e) { toast(String(e), "bad"); }
      test.disabled = false;
      test.classList.remove("busy");
      test.innerHTML = label;
    });
    update();
    preview();
  }
  // A short message at the top of the page, like the server's "flash" (for actions that don't reload the page).
  function toast(message, kind = "good") {
    document.querySelectorAll(".flash.live").forEach((el) => el.remove());
    const el = document.createElement("div");
    el.className = `flash ${kind} live`;
    el.setAttribute("role", "status");
    el.textContent = message;
    const content = document.querySelector(".content");
    content.prepend(el);
    el.scrollIntoView({ block: "nearest", behavior: "smooth" });
    setTimeout(() => el.remove(), 7000);
  }

  // Admins: "show who rated" only matters for viewers.
  document.querySelectorAll("select[data-role]").forEach((sel) => {
    const sw = sel.closest("form").querySelector("[data-viewer-only]");
    const sync = () => { if (sw) sw.hidden = sel.value !== "viewer"; };
    sel.addEventListener("change", sync);
    sync();
  });

  // Editing data: one dialog per tab, filled from the row's edit button (or empty for "Add").
  const dialog = document.getElementById("rec-dialog");
  if (dialog) {
    const form = dialog.querySelector("form");
    const del = dialog.querySelector("[data-delete]");
    const title = dialog.querySelector("#rec-title");
    function open(rec) {
      const isNew = !rec;
      form.reset();
      form.action = isNew ? dialog.dataset.urlNew : dialog.dataset.urlBase + rec.id;
      title.textContent = isNew ? dialog.dataset.titleNew : dialog.dataset.titleEdit;
      Object.entries(rec || {}).forEach(([k, v]) => {
        const el = form.elements[k];
        if (!el || el.type === "hidden") return;
        if (el.type === "checkbox") el.checked = !!v; else el.value = v ?? "";
      });
      form.querySelectorAll("[data-only]").forEach((el) => (el.hidden = el.dataset.only !== (isNew ? "new" : "edit")));
      // Fields the timetable owns (a timetable group's name, course, language) are shown but can't be changed.
      const locks = [...form.querySelectorAll("[data-lock]")];
      locks.forEach((el) => (el.disabled = !isNew && !!rec[el.dataset.lock]));
      form.querySelectorAll("[data-lock-note]").forEach((el) => (el.hidden = isNew || !rec[el.dataset.lockNote]));
      dialog.querySelector("[data-save]").hidden = locks.length > 0 && locks.every((el) => el.disabled);
      // Rows with evaluations (or a group with students) can't be deleted: say why instead.
      const blocked = !isNew && rec.n > 0 && dialog.dataset.block;
      del.parentNode.hidden = isNew;
      del.disabled = !!blocked;
      del.parentNode.dataset.tip = blocked ? fmt(dialog.dataset.block, { n: rec.n }) : "";
      if (!isNew) {
        document.getElementById("rec-delete").action = dialog.dataset.urlBase + rec.id + "/delete";
        del.dataset.confirm = fmt(dialog.dataset.confirm, { label: rec.label });
      }
      dialog.showModal();
      const first = form.querySelector("input:not([type=hidden]):not(:disabled), select");
      if (first) first.focus();
    }
    document.querySelectorAll("[data-edit]").forEach((b) => b.addEventListener("click", () => open(JSON.parse(b.dataset.edit))));
    document.querySelectorAll("button[data-new]").forEach((b) => b.addEventListener("click", () => open(null)));
    dialog.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", () => dialog.close()));
    dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });  // the backdrop
    del.addEventListener("click", (e) => { if (!window.confirm(del.dataset.confirm)) e.preventDefault(); });
    // Opened from another page (teacher profile, students list): ?edit=<id>
    const wanted = dialog.dataset.open && document.querySelector(`[data-edit][data-id="${dialog.dataset.open}"]`);
    if (wanted) open(JSON.parse(wanted.dataset.edit));
  }

  // ---------- Ko‘rinish: the person's display settings (text size, theme, contrast, ...) ----------
  const dp = document.getElementById("display-dialog");
  if (dp) {
    const form = dp.querySelector("form"), saved = document.getElementById("dp-saved");
    const flags = ["contrast", "motion", "spacing", "links"];
    const hide = form.elements.hide_names;
    const snapshot = () => JSON.stringify([ROOT.dataset.text, ROOT.dataset.theme, "contrast" in ROOT.dataset]);
    let hideOpened = hide.checked;
    let opened = snapshot(), saving;
    const apply = () => {
      const text = form.elements.text.value, theme = form.elements.theme.value;
      if (text === "100") delete ROOT.dataset.text; else ROOT.dataset.text = text;
      if (theme === "auto") delete ROOT.dataset.theme; else ROOT.dataset.theme = theme;
      flags.forEach((k) => { if (form.elements[k].checked) ROOT.dataset[k] = ""; else delete ROOT.dataset[k]; });
    };
    const save = () => {
      clearTimeout(saving);
      saving = setTimeout(async () => {
        try {
          const r = await fetch(dp.dataset.url, { method: "POST", body: new URLSearchParams(new FormData(form)) });
          saved.textContent = r.ok ? saved.dataset.text : "";
        } catch (e) { saved.textContent = ""; }
      }, 250);
    };
    form.addEventListener("change", () => { apply(); save(); });
    document.getElementById("dp-reset").addEventListener("click", () => {
      form.elements.text.value = "100";
      form.elements.theme.value = "auto";
      flags.forEach((k) => (form.elements[k].checked = false));
      if (!hide.disabled) hide.checked = false;
      apply();
      save();
    });
    document.querySelectorAll("[data-open-display]").forEach((b) => b.addEventListener("click", () => {
      opened = snapshot();
      hideOpened = hide.checked;
      saved.textContent = "";
      setNav(false);
      dp.showModal();
    }));
    dp.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", () => dp.close()));
    dp.addEventListener("click", (e) => { if (e.target === dp) dp.close(); });
    // Charts take their colours and text size when they are drawn: draw them again by reloading the page.
    // Names are left out by the server, and charts take their colours and text size when they are drawn:
    // after such a change the page is loaded again.
    dp.addEventListener("close", () => {
      if (hide.checked !== hideOpened
          || (snapshot() !== opened && document.querySelector(".chart, [id^=ch-]"))) setTimeout(() => location.reload(), 300);
    });
  }

  // ---------- Suhbatlar (programmer): the bot's conversations, kept fresh while the page is open ----------
  const chatApp = document.getElementById("chat-app");
  if (chatApp) {
    const wall = document.getElementById("chat-wall"), items = document.getElementById("chat-items");
    const chatId = chatApp.dataset.chat, q = document.getElementById("chat-q");
    const atBottom = () => !wall || wall.scrollHeight - wall.scrollTop - wall.clientHeight < 80;
    const toBottom = () => { if (wall) wall.scrollTop = wall.scrollHeight; };
    toBottom();
    if (wall) wall.querySelectorAll("img").forEach((img) => img.addEventListener("load", () => { if (atBottom()) toBottom(); }, { once: true }));
    const poll = async () => {
      if (document.hidden) return;
      try {
        if (chatId) {
          const r = await (await fetch(`/admin/chats/${chatId}/feed?v=${encodeURIComponent(chatApp.dataset.v)}`)).json();
          if (r.html !== undefined) {
            const stick = atBottom();
            wall.innerHTML = r.html;
            chatApp.dataset.v = r.v;
            if (stick) toBottom();
          }
        }
        const params = new URLSearchParams({ v: chatApp.dataset.listV, q: q ? q.value : "" });
        if (chatId) params.set("c", chatId);
        const l = await (await fetch(`/admin/chats/list?${params}`)).json();
        if (l.html !== undefined) { items.innerHTML = l.html; chatApp.dataset.listV = l.v; }
      } catch (e) { /* offline for a moment: try again on the next round */ }
    };
    setInterval(poll, 4000);
    document.addEventListener("visibilitychange", poll);
    // Search as you type (the list is filtered on the server).
    if (q) {
      let wait;
      q.addEventListener("input", () => { clearTimeout(wait); wait = setTimeout(() => { chatApp.dataset.listV = ""; poll(); }, 300); });
    }
    const compose = document.getElementById("chat-compose");
    if (compose) {
      const box = document.getElementById("compose-text"), photo = document.getElementById("compose-photo");
      const fileRow = document.getElementById("compose-file"), note = document.getElementById("compose-note");
      const send = compose.querySelector(".send-btn"), noteText = note.textContent;
      const grow = () => { box.style.height = "auto"; box.style.height = `${Math.min(box.scrollHeight, 180)}px`; };
      box.addEventListener("input", grow);
      photo.addEventListener("change", () => {
        fileRow.hidden = !photo.files.length;
        if (photo.files.length) fileRow.querySelector(".name").textContent = photo.files[0].name;
      });
      document.getElementById("compose-file-x").addEventListener("click", () => { photo.value = ""; fileRow.hidden = true; });
      // Enter sends, Shift+Enter is a new line (as in Telegram).
      box.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); compose.requestSubmit(); }
      });
      compose.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!box.value.trim() && !photo.files.length) { box.focus(); return; }
        send.disabled = true;
        note.classList.remove("bad");
        note.textContent = compose.dataset.sending;
        try {
          const r = await (await fetch(compose.action, { method: "POST", body: new FormData(compose) })).json();
          if (r.ok) {
            box.value = "";
            photo.value = "";
            fileRow.hidden = true;
            grow();
            note.textContent = noteText;
            await poll();
            toBottom();
          } else {
            note.textContent = r.error;
            note.classList.add("bad");
          }
        } catch (err) {
          note.textContent = String(err);
          note.classList.add("bad");
        }
        send.disabled = false;
        box.focus();
      });
    }
  }

  // While a message is being sent, keep its progress fresh.
  const refresh = document.querySelector("[data-refresh]");
  if (refresh) setTimeout(() => location.reload(), Number(refresh.dataset.refresh) * 1000);

  // ---------- Timetable ----------
  const ttSwitch = document.getElementById("tt-switch");
  if (ttSwitch) ttSwitch.addEventListener("change", () => go(ttSwitch.value));
  document.querySelectorAll(".tt-sync").forEach((form) => form.addEventListener("submit", () => {
    const b = form.querySelector("button");
    b.disabled = true;
    b.classList.add("busy");
    b.querySelector("span").textContent = b.dataset.busy;
  }));
  // Group tiles: search, specialty and course filters work together.
  const tiles = document.getElementById("tiles");
  if (tiles) {
    const q = document.getElementById("tile-search");
    const spec = document.getElementById("tile-specialty");
    let course = "";
    const apply = () => {
      const s = q.value.trim().toLowerCase();
      let any = false;
      tiles.querySelectorAll(".tt-course").forEach((sec) => {
        let n = 0;
        sec.querySelectorAll(".tt-tile").forEach((a) => {
          const ok = (!s || a.dataset.q.includes(s)) && (!spec.value || a.dataset.spec === spec.value);
          a.hidden = !ok;
          n += ok;
        });
        sec.hidden = !n || (course !== "" && sec.dataset.course !== course);
        any = any || !sec.hidden;
      });
      document.getElementById("tiles-empty").hidden = any;
    };
    q.addEventListener("input", apply);
    spec.addEventListener("change", apply);
    segmented(document.getElementById("tile-course"), (b) => { course = b.dataset.course; apply(); });
  }

  // ---------- Data structure (programmer, Data page): tables as cards, their links drawn between them ----------
  const board = document.getElementById("schema-board");
  if (board) {
    const S = JSON.parse(document.getElementById("schema-data").textContent);
    const NS = "http://www.w3.org/2000/svg";
    const wrap = document.createElement("div");
    wrap.className = "schema-grid";
    board.appendChild(wrap);
    let sysRow = 1;
    S.tables.forEach((tb) => {
      const el = document.createElement("div");
      el.className = "tbl" + (tb.col === 5 ? " sys" : "");
      el.dataset.name = tb.name;
      el.style.gridColumn = tb.col;
      el.style.gridRow = tb.row || sysRow++;
      el.innerHTML = `<div class="tbl-h"><b>${esc(tb.name)}</b><span>${num(tb.n)}</span></div>` +
        (tb.note ? `<div class="tbl-note">${esc(tb.note)}</div>` : "") +
        `<ul>${tb.cols.map((c) => `<li class="${c.pk ? "pk" : c.fk ? "fk" : ""}"><span>${esc(c.name)}</span>` +
          `<i>${esc(c.type)}</i></li>`).join("")}</ul>`;
      wrap.appendChild(el);
    });
    const svg = document.createElementNS(NS, "svg");
    svg.classList.add("links");
    wrap.prepend(svg);
    const drawLinks = () => {
      const box = wrap.getBoundingClientRect();
      svg.setAttribute("width", wrap.scrollWidth);
      svg.setAttribute("height", wrap.scrollHeight);
      svg.innerHTML = "";
      S.links.forEach((l) => {
        const a = wrap.querySelector(`[data-name="${l.from}"]`), b = wrap.querySelector(`[data-name="${l.to}"]`);
        if (!a || !b || a === b) return;
        const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
        const li = [...a.querySelectorAll("li")].find((x) => x.firstChild.textContent === l.col);
        const rl = li ? li.getBoundingClientRect() : null;
        const ya = (rl ? rl.top + rl.height / 2 : ra.top + 16) - box.top;
        const yb = rb.top + 17 - box.top;
        const right = ra.right <= rb.left, left = ra.left >= rb.right;
        const xa = (left ? ra.left : ra.right) - box.left, xb = (right ? rb.left : rb.right) - box.left;
        const bend = left || right ? Math.max(28, Math.abs(xb - xa) / 2) : 36;   // same column: loop out on the right
        const c1 = xa + (left ? -bend : bend), c2 = xb + (right ? -bend : bend);
        const p = document.createElementNS(NS, "path");
        p.setAttribute("d", `M${xa},${ya} C${c1},${ya} ${c2},${yb} ${xb},${yb}`);
        p.dataset.from = l.from;
        p.dataset.to = l.to;
        if (l.soft) p.classList.add("soft");
        svg.appendChild(p);
        const dot = document.createElementNS(NS, "circle");   // the "one" end: the table that is referenced
        dot.setAttribute("cx", xb);
        dot.setAttribute("cy", yb);
        dot.setAttribute("r", 3);
        dot.dataset.from = l.from;
        dot.dataset.to = l.to;
        svg.appendChild(dot);
      });
    };
    // Hovering a table lights up its links and the tables it is linked with.
    const focusOn = (name) => {
      wrap.classList.toggle("focus", !!name);
      const near = new Set([name]);
      svg.querySelectorAll("path, circle").forEach((p) => {
        const hit = !!name && (p.dataset.from === name || p.dataset.to === name);
        p.classList.toggle("on", hit);
        if (hit) { near.add(p.dataset.from); near.add(p.dataset.to); }
      });
      wrap.querySelectorAll(".tbl").forEach((tb) => tb.classList.toggle("near", !!name && near.has(tb.dataset.name)));
    };
    wrap.addEventListener("mouseover", (e) => { const tb = e.target.closest(".tbl"); focusOn(tb && tb.dataset.name); });
    wrap.addEventListener("mouseleave", () => focusOn(null));
    (document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(drawLinks);
    addEventListener("resize", drawLinks);
  }

  // ---------- Charts ----------
  // One look everywhere: 2px lines with the last point marked, soft area fills, bars at most 24px with 4px rounded ends,
  // hairline grids, axis figures in mono. One indigo for a single series, series 1-3 for the criteria. Tooltips lead
  // with the value, and every chart can also be read as a table (the button in its header).
  if (!window.echarts) return;
  const charts = [];
  window.addEventListener("resize", () => charts.forEach((c) => c.resize()));
  // Draw after the web fonts are ready, so ECharts measures labels with the right font.
  (document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(drawCharts);

  const FONT = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
  const MONO = "'Geist Mono', ui-monospace, SFMono-Regular, Menlo, monospace";
  const axisText = { color: C.muted, fontSize: 10.5 * FS, fontFamily: MONO };
  const nameText = { color: C.ink2, fontSize: 12 * FS, fontWeight: 500, fontFamily: FONT };
  const base = {
    textStyle: { fontFamily: FONT, color: C.ink2 },
    animation: !CALM, animationDuration: 800, animationEasing: "cubicOut", animationDurationUpdate: 400,
    tooltip: {
      backgroundColor: C.surface, borderColor: C.border, borderWidth: 1, padding: [9, 12],
      textStyle: { color: C.ink, fontSize: 12.5 * FS, fontFamily: FONT },
      extraCssText: `box-shadow:0 14px 34px -10px rgba(0,0,0,${DARK ? 0.75 : 0.22});border-radius:10px;`,
    },
  };
  const valueAxis = (extra = {}) => ({
    type: "value", axisLine: { show: false }, axisTick: { show: false },
    splitLine: { lineStyle: { color: C.grid, width: 1 } }, axisLabel: { ...axisText }, ...extra,
  });
  const catAxis = (data, extra = {}) => ({
    type: "category", data, axisTick: { show: false }, axisLine: { show: true, lineStyle: { color: C.axis, width: 1 } },
    axisLabel: { ...axisText }, ...extra,
  });
  const crosshair = { type: "line", lineStyle: { color: C.axis, width: 1, type: "solid" } };
  const bandShade = { type: "shadow", shadowStyle: { color: alpha(C.grid, DARK ? 0.6 : 0.8) } };
  // Tooltip pieces. A short line keys a line series, a small square keys a bar series.
  const key = (color, bar) => `<span style="display:inline-block;width:${bar ? 8 : 12}px;height:${bar ? 8 : 2.5}px;` +
    `border-radius:2px;background:${color};margin-right:8px;vertical-align:middle"></span>`;
  const tipTitle = (s) => `<div style="font-weight:600;margin-bottom:5px">${esc(s)}</div>`;
  const tipRow = (color, value, name, bar) => `<div style="line-height:1.75;white-space:nowrap">${key(color, bar)}` +
    `<b style="font-family:${MONO};font-weight:500">${esc(value)}</b><span style="color:${C.muted};margin-left:8px">${esc(name)}</span></div>`;
  const tipMuted = (s) => `<div style="color:${C.muted};margin-top:5px">${esc(s)}</div>`;
  const evaluations = (n) => fmt(J.evaluations_n, { n: num(n) });
  const pad = (n) => String(n).padStart(2, "0");
  const shortDate = (v) => { const d = new Date(v); return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}`; };
  const longDate = (v) => { const d = new Date(v); return `${shortDate(d)}.${d.getFullYear()}`; };
  const wash = (color) => new echarts.graphic.LinearGradient(0, 0, 0, 1,
    [{ offset: 0, color: alpha(color, DARK ? 0.28 : 0.16) }, { offset: 1, color: alpha(color, 0) }]);
  // Line data with only the last point drawn as a dot (ringed in the surface colour).
  const endDot = (values, color) => values.map((v, i) => (i === values.length - 1 && v != null
    ? { value: v, symbol: "circle", symbolSize: 8, itemStyle: { color, borderColor: C.surface, borderWidth: 2 } } : v));
  const staggered = (i) => (CALM ? 0 : i * 22);

  function chart(id, option, height) {
    const el = document.getElementById(id);
    if (!el) return null;
    if (height) el.style.height = height + "px";
    const c = echarts.init(el, null, { renderer: "svg" });
    c.setOption({ ...base, ...option, tooltip: { ...base.tooltip, ...(option.tooltip || {}) } });
    charts.push(c);
    return c;
  }
  const empty = (id) => {
    const el = document.getElementById(id);
    if (el) el.outerHTML = `<div class="empty">${esc(J.no_data)}</div>`;
  };

  /** The same numbers as a table: a switch in the card header swaps the chart for it. */
  const ICON_TABLE = '<svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v18"/><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/><path d="M3 15h18"/></svg>';
  const ICON_CHART = '<svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/></svg>';
  function tableView(id, cols, rows) {
    const el = document.getElementById(id);
    const card = el && el.closest(".card, .status-card");
    const head = card && card.querySelector(".card-h");
    if (!head || !rows.length) return;
    const wrap = document.createElement("div");
    wrap.className = "table-wrap chart-table";
    wrap.hidden = true;
    const t = document.createElement("table");
    const hr = t.createTHead().insertRow();
    cols.forEach((c, i) => { const th = document.createElement("th"); th.textContent = c; if (i) th.className = "r"; hr.appendChild(th); });
    const body = t.createTBody();
    rows.forEach((r) => { const tr = body.insertRow(); r.forEach((v, i) => {
      const td = tr.insertCell(); td.textContent = v == null ? "—" : typeof v === "number" ? num(v) : v; if (i) td.className = "r"; }); });
    wrap.appendChild(t);
    el.after(wrap);
    let tools = head.querySelector(".card-tools");
    if (!tools) {
      tools = document.createElement("div");
      tools.className = "card-tools";
      const legend = head.querySelector(":scope > .legend");
      if (legend) tools.appendChild(legend);
      head.appendChild(tools);
    }
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "view-toggle";
    const show = (asTable) => {
      wrap.hidden = !asTable;
      el.hidden = asTable;
      btn.setAttribute("aria-pressed", String(asTable));
      btn.setAttribute("aria-label", asTable ? J.tip_chart : J.tip_table);
      btn.dataset.tip = asTable ? J.tip_chart : J.tip_table;
      btn.innerHTML = asTable ? ICON_CHART : ICON_TABLE;
      if (!asTable) charts.forEach((c) => c.resize());
    };
    btn.addEventListener("click", () => show(wrap.hidden));
    show(false);
    tools.appendChild(btn);
  }
  const criteriaCols = () => CRITERIA.map((k) => J["cs_" + k]);

  /** Horizontal bars, one series in indigo; the value sits at the bar's end. Height grows with the rows. */
  function barList(id, rows, { value, label, max, fmtValue, tip, table }) {
    if (!rows.length) return empty(id);
    chart(id, {
      grid: { left: 4, right: 52, top: 4, bottom: 4, containLabel: true },
      xAxis: valueAxis({ max, show: false }),
      yAxis: catAxis(rows.map(label), { inverse: true, axisLabel: { ...nameText, width: 190, overflow: "truncate" } }),
      tooltip: { trigger: "item", formatter: (p) => tip(rows[p.dataIndex]) },
      series: [{
        type: "bar", barMaxWidth: 10, color: C.s1, itemStyle: { borderRadius: [0, 4, 4, 0] }, data: rows.map(value),
        showBackground: true, backgroundStyle: { color: alpha(C.grid, 0.9), borderRadius: [0, 4, 4, 0] },
        label: { show: true, position: "right", distance: 6, color: C.ink, fontFamily: MONO, fontSize: 11.5 * FS,
          formatter: (p) => fmtValue(p.value) },
        emphasis: { itemStyle: { opacity: 0.8 } }, animationDelay: staggered,
      }],
    }, Math.max(140, rows.length * 30 + 10));
    if (table) tableView(id, table.cols, table.rows);
  }

  /** How many evaluations got each overall score 1..10: one series, one colour. */
  function histogram(id, counts) {
    if (!counts.some((n) => n)) return empty(id);
    chart(id, {
      grid: { left: 4, right: 8, top: 12, bottom: 4, containLabel: true },
      xAxis: catAxis(counts.map((_, i) => String(i + 1))),
      yAxis: valueAxis({ minInterval: 1 }),
      tooltip: { trigger: "axis", axisPointer: bandShade,
        formatter: (ps) => tipTitle(fmt(J.score_n, { n: ps[0].name })) + tipRow(C.s1, num(ps[0].value), J.col_evaluations, true) },
      series: [{ type: "bar", data: counts, color: C.s1, barMaxWidth: 22, itemStyle: { borderRadius: [4, 4, 0, 0] },
        emphasis: { itemStyle: { opacity: 0.8 } }, animationDelay: staggered }],
    });
    tableView(id, [J.col_score, J.col_evaluations], counts.map((n, i) => [String(i + 1), n]));
  }

  function drawCharts() {
    const page = document.body.dataset.page;

    // ---------- Overview ----------
    if (page === "overview") {
      // Status card (on its colour field): how participation grew day by day during the survey.
      const spark = D.curve.map((p) => ({ x: p.date, y: Math.round((1000 * p.count) / Math.max(1, D.students)) / 10, n: p.count }));
      const WHITE = "#ffffff";
      if (spark.length > 1) chart("chart-spark", {
        grid: { left: 6, right: 6, top: 10, bottom: 6 },
        xAxis: { type: "category", show: false, boundaryGap: false, data: spark.map((p) => p.x) },
        yAxis: { type: "value", show: false, min: (v) => v.min - (v.max - v.min) * 0.2 || 0 },
        tooltip: { trigger: "axis", axisPointer: { type: "line", lineStyle: { color: alpha(WHITE, 0.6), width: 1 } },
          formatter: (ps) => { const p = spark[ps[0].dataIndex];
            return tipTitle(longDate(p.x)) + tipRow(C.s1, `${p.y}%`, fmt(J.participants_n, { n: num(p.n) })); } },
        series: [{ type: "line", data: spark.map((p, i) => (i === spark.length - 1
            ? { value: p.y, symbol: "circle", symbolSize: 8, itemStyle: { color: WHITE, borderColor: alpha(WHITE, 0.35), borderWidth: 4 } }
            : p.y)),
          color: WHITE, lineStyle: { width: 2 }, symbol: "none", smooth: 0.3, animationDuration: 1200,
          areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1,
            [{ offset: 0, color: alpha(WHITE, 0.32) }, { offset: 1, color: alpha(WHITE, 0) }]) } }],
      });

      if (D.daily.length) {
        const counts = D.daily.map((d) => d.count);
        chart("chart-daily", {
          grid: { left: 6, right: 8, top: 12, bottom: 4, containLabel: true },
          xAxis: catAxis(D.daily.map((d) => shortDate(d.date)), { boundaryGap: false,
            axisLabel: { ...axisText, alignMinLabel: "left", alignMaxLabel: "right" } }),
          yAxis: valueAxis({ minInterval: 1, position: "right", splitNumber: 4 }),
          tooltip: { trigger: "axis", axisPointer: crosshair,
            formatter: (ps) => tipTitle(longDate(D.daily[ps[0].dataIndex].date)) + tipRow(C.s1, num(ps[0].value), J.col_evaluations) },
          series: [{ type: "line", data: endDot(counts, C.s1), color: C.s1, lineStyle: { width: 2 }, symbol: "none",
            smooth: 0.25, areaStyle: { color: wash(C.s1) }, animationDuration: 1100 }],
        });
        tableView("chart-daily", [J.col_date, J.col_evaluations], D.daily.map((d) => [longDate(d.date), d.count]));
      } else empty("chart-daily");

      if (D.specialties.length) {
        chart("chart-specialties", {
          grid: { left: 4, right: 20, top: 4, bottom: 4, containLabel: true },
          xAxis: valueAxis({ min: 0, max: 10, interval: 2 }),
          yAxis: catAxis(D.specialties.map((d) => d.name), { inverse: true,
            axisLabel: { ...nameText, width: 190, overflow: "break", lineHeight: 15 } }),
          tooltip: { trigger: "axis", axisPointer: bandShade,
            formatter: (ps) => { const d = D.specialties[ps[0].dataIndex];
              return tipTitle(d.name) + ps.map((p) => tipRow(p.color, p.value ?? "—", p.seriesName, true)).join("") +
                tipRow(C.ink, d.overall ?? "—", J.overall, true) + tipMuted(evaluations(d.n)); } },
          series: CRITERIA.map((k, i) => ({ name: D.criteria[k], type: "bar", data: D.specialties.map((d) => d[k]),
            color: SERIES[i], barMaxWidth: 6, barGap: "45%", barCategoryGap: "38%", itemStyle: { borderRadius: [0, 3, 3, 0] },
            animationDelay: (j) => staggered(j + i * 2) })),
        });
        tableView("chart-specialties", [J.tt_specialty, ...criteriaCols(), J.overall, J.col_evaluations],
          D.specialties.map((d) => [d.name, ...CRITERIA.map((k) => d[k]), d.overall, d.n]));
      } else empty("chart-specialties");

      histogram("chart-distribution", D.distribution);
    }

    // ---------- Teacher detail ----------
    if (page === "teacher") {
      barList("chart-groups", D.by_group, { value: (g) => g.overall, label: (g) => g.name, max: 10,
        fmtValue: (v) => v.toFixed(2),
        tip: (g) => tipTitle(g.name) + tipRow(C.s1, g.overall, J.overall, true) +
          CRITERIA.map((k, i) => tipRow(SERIES[i], g[k], D.criteria[k], true)).join("") + tipMuted(evaluations(g.n)),
        table: { cols: [J.col_group, J.overall, ...criteriaCols(), J.col_evaluations],
                 rows: D.by_group.map((g) => [g.name, g.overall, ...CRITERIA.map((k) => g[k]), g.n]) } });

      histogram("chart-distribution", D.distribution);
    }

    // ---------- Timetable: load heatmap (day x period), one indigo scale; no classes = neutral ----------
    if (page === "timetable" && D.load) {
      const cells = [];
      let max = 1;
      D.load.forEach((row, d) => row.forEach((v, p) => { cells.push([d, p, v]); max = Math.max(max, v); }));
      // Sequential: light -> dark on a light page, dark -> light on a dark one (low values sit near the surface).
      const ramp = DARK ? ["#262a65", "#3d3e82", "#5958b1", "#6e6ade", "#9b9ef0", "#e0dffe"]
                        : ["#e6e7ff", "#cbcdff", "#9b9ef0", "#5b5bd6", "#272962"];
      const onCell = (v) => ((v - 1) / Math.max(1, max - 1) >= 0.5 ? (DARK ? "#111113" : "#ffffff") : (DARK ? "#ededef" : C.ink));
      const periodLabel = (p) => `${p.n} · ${p.start}`;
      chart("chart-load", {
        grid: { left: 4, right: 4, top: 4, bottom: 4, containLabel: true },
        xAxis: catAxis(D.days, { position: "top", axisLine: { show: false }, splitArea: { show: false },
          axisLabel: { ...nameText, fontWeight: 600, interval: 0 } }),
        yAxis: catAxis(D.periods.map(periodLabel), { inverse: true, axisLine: { show: false }, axisLabel: { ...axisText } }),
        visualMap: { show: false, min: 1, max: Math.max(2, max), inRange: { color: ramp }, outOfRange: { color: [C.surface3] } },
        tooltip: { trigger: "item", formatter: (p) => {
          const [d, i, v] = p.value, per = D.periods[i];
          return tipTitle(`${D.days[d]} · ${fmt(J.tt_period, { n: per.n })}`) +
            tipRow(v ? p.color : C.surface3, fmt(J.tt_lessons_n, { n: v }), `${per.start}–${per.end}`, true); } },
        series: [{
          type: "heatmap",
          data: cells.map(([d, p, v]) => ({ value: [d, p, v], label: { color: onCell(v) } })),
          label: { show: true, fontSize: 12 * FS, fontFamily: MONO, formatter: (p) => (p.value[2] ? Math.round(p.value[2]) : "") },
          itemStyle: { borderColor: C.surface, borderWidth: 3, borderRadius: 7 },
          emphasis: { itemStyle: { borderColor: C.ink, borderWidth: 2 } },
        }],
      });
    }

    // ---------- Groups ----------
    if (page === "groups") {
      if (D.courses.length) {
        const courseName = (c) => (c.course ? fmt(J.course_n, { n: c.course }) : J.unknown);
        chart("chart-courses", {
          grid: { left: 4, right: 8, top: 24, bottom: 4, containLabel: true },
          xAxis: catAxis(D.courses.map(courseName), { axisLabel: { ...nameText } }),
          yAxis: valueAxis({ max: 100, interval: 25, axisLabel: { ...axisText, formatter: "{value}%" } }),
          tooltip: { trigger: "axis", axisPointer: bandShade, formatter: (ps) => { const c = D.courses[ps[0].dataIndex];
            return tipTitle(courseName(c)) + tipRow(C.s1, `${c.participation_pct}%`, J.col_participation, true) +
              tipMuted(fmt(J.of_students, { n: num(c.participants), total: num(c.students) })); } },
          series: [{ type: "bar", data: D.courses.map((c) => c.participation_pct), color: C.s1, barMaxWidth: 24,
            itemStyle: { borderRadius: [4, 4, 0, 0] }, emphasis: { itemStyle: { opacity: 0.8 } }, animationDelay: staggered,
            label: { show: true, position: "top", color: C.ink, fontFamily: MONO, fontSize: 11.5 * FS, formatter: (p) => p.value + "%" } }],
        });
        tableView("chart-courses", [J.col_course, `${J.col_participation} %`, J.col_participated, J.col_students],
          D.courses.map((c) => [courseName(c), c.participation_pct, c.participants, c.students]));
      } else empty("chart-courses");

      // Most active groups first; the switch in the card turns it around (the bars glide to their new places).
      const ordered = (order) => [...D.groups].sort((a, b) =>
        (order === "asc" ? 1 : -1) * (a.participation_pct - b.participation_pct) || a.name.localeCompare(b.name));
      const rows = ordered("desc");
      segmented(document.getElementById("part-order"), (b) => {
        rows.splice(0, rows.length, ...ordered(b.dataset.order));   // the tooltip reads this same list
        const c = echarts.getInstanceByDom(document.getElementById("chart-participation"));
        if (c) c.setOption({ yAxis: { data: rows.map((g) => g.name) }, series: [{ data: rows.map((g) => g.participation_pct) }] });
      });
      barList("chart-participation", rows, { value: (g) => g.participation_pct, label: (g) => g.name, max: 100,
        fmtValue: (v) => v + "%",
        tip: (g) => tipTitle(g.name) + tipRow(C.s1, `${g.participation_pct}%`, J.col_participation, true) +
          tipMuted(fmt(J.of_students, { n: num(g.participants), total: num(g.students) })) +
          tipMuted(fmt(J.completed_all, { n: num(g.completed) })) + tipMuted(fmt(J.registered_n, { n: num(g.registered) })),
        table: { cols: [J.col_group, `${J.col_participation} %`, J.col_participated, J.col_students],
                 rows: rows.map((g) => [g.name, g.participation_pct, g.participants, g.students]) } });
    }
  }
})();
