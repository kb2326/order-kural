// Order Kural front end: plain JS, no build step. All text goes in via textContent (never innerHTML).
// Two modes share one screen: "live" (the real shop, talk / upload / type) and "sample" (this tab's own sample shop,
// replaying saved AI results with a synthetic voice, so the whole flow works with no API key).

const $ = (id) => document.getElementById(id);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (v !== null && v !== undefined) node.setAttribute(k, v);
  }
  for (const c of children) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

function newId() { return (crypto.randomUUID && crypto.randomUUID()) || String(Date.now()) + Math.random(); }
function remembered(key) {
  try { const v = sessionStorage.getItem(key) || newId(); sessionStorage.setItem(key, v); return v; }
  catch (_) { return newId(); }
}

const AGENT_SESSION = remembered("kural-agent-session");
let SAMPLE_SESSION = newId();
const state = { mode: "live", keyReady: false, voice: null, botBubble: null };
const rupees = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 });
const money = (paise) => rupees.format(paise / 100).replace(/\.00$/, "");
const FLAG_TEXT = { below_min: "below minimum", sizes_missing: "sizes missing", rate_off_list: "rate differs from list" };

async function api(path, { method = "GET", json, form } = {}) {
  const headers = { "X-Agent-Session": AGENT_SESSION };
  if (state.mode === "sample") headers["X-Sample-Session"] = SAMPLE_SESSION;
  let body;
  if (json !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(json); }
  if (form) body = form;
  const res = await fetch(path, { method, headers, body });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.detail || res.statusText), { status: res.status });
  return data;
}

// ---- conversation ---------------------------------------------------------------------------------------------
function bubble(who, text, meta) {
  $("chat-empty")?.remove();
  const b = el("div", { class: `bubble ${who}` }, el("p", { class: "voice" }, text), meta ? el("p", { class: "meta" }, meta) : null);
  $("chat").append(b);
  b.scrollIntoView({ behavior: "smooth", block: "end" });
  return b;
}
const owner = (text, meta) => { state.botBubble = null; return bubble("owner", text, meta); };
const bot = (text, meta) => { state.botBubble = null; return bubble("bot", text, meta); };
function botPartial(text) {
  if (!state.botBubble) state.botBubble = bubble("bot", "");
  state.botBubble.querySelector(".voice").textContent += text;
}
function addMeta(node, text) {
  if (!node) return;
  const m = node.querySelector(".meta") || node.appendChild(el("p", { class: "meta" }));
  m.textContent = m.textContent ? `${m.textContent} · ${text}` : text;
}

// ---- the slip: what is waiting for "sari" ----------------------------------------------------------------------
function renderSlip(ui) {
  const box = $("slip");
  const p = ui && ui.pending;
  if (!p) { box.replaceChildren(); return; }
  const parts = [];
  if (p.kind === "order") {
    const rows = (p.lines || []).map((l) => el("tr", {},
      el("td", {}, l.item, el("span", { class: "sizes" }, l.qty),
        ...(l.flags || []).map((f) => el("span", { class: "badge" }, FLAG_TEXT[f] || f))),
      el("td", { class: "num" }, money(l.rate_paise)),
      el("td", { class: "num" }, money(l.amount_paise))));
    parts.push(el("table", {},
      el("thead", {}, el("tr", {}, el("th", {}, "Item"), el("th", { class: "num" }, "Rate"), el("th", { class: "num" }, "Amount"))),
      el("tbody", {}, ...rows)));
    parts.push(el("div", { class: "totals" }, el("span", { class: "grand" }, "Order total"),
      el("span", { class: "grand" }, money(p.total_paise))));
    const details = [p.transport && `Transport: ${p.transport}`, p.payment && `Payment: ${p.payment}`].filter(Boolean);
    if (details.length) parts.push(el("p", { class: "needed" }, details.join(" · ")));
    if (p.problems && p.problems.length) parts.push(el("ul", { class: "problems" }, ...p.problems.map((x) => el("li", {}, x))));
    parts.push(el("p", { class: "foot" }, "GST is added on the tax invoice when you say “bill it”."));
  } else if (p.kind === "bill") {
    parts.push(el("p", { class: "big" }, `GST tax invoice: ${money(p.total_paise)}`),
      el("p", { class: "needed" }, `Taxable ${money(p.taxable_paise)} + ${p.interstate ? "IGST" : "CGST + SGST"} ${money(p.tax_paise)} · ${p.b2b ? "B2B (GSTIN)" : "B2C (no GSTIN)"}`));
  } else if (p.kind === "payment") {
    parts.push(el("p", { class: "big" }, `Payment received: ${money(p.amount_paise)} by ${String(p.mode).toUpperCase()}`));
  } else if (p.kind === "ship") {
    parts.push(el("p", { class: "big" }, `Mark as shipped${p.transport ? ` by ${p.transport}` : ""}`));
  }
  const title = { order: p.is_new_order ? "New order" : "Adding to the order", bill: "Bill", payment: "Khata", ship: "Shipping" }[p.kind];
  const slip = el("article", { class: "slip fresh", "aria-label": "Waiting for sari" },
    el("div", { class: "slip-head" }, el("h3", {}, p.customer), el("span", { class: "tag" }, title)),
    ...parts);
  if (state.mode === "live") {
    const yes = el("button", { class: "yes" }, "Sari ✔");
    const no = el("button", { class: "no" }, "Cancel ✖");
    yes.addEventListener("click", () => tap("confirm"));
    no.addEventListener("click", () => tap("discard"));
    slip.append(el("p", { class: "hint" }, "Say sari, or tap:"), el("div", { class: "actions" }, yes, no));
  } else {
    slip.append(el("p", { class: "hint" }, "Waiting for “சரி” (next step)"));
  }
  box.replaceChildren(slip);
}

async function tap(action) {
  owner(action === "confirm" ? "Sari ✔" : "Cancel ✖", "tapped");
  if (state.voice && state.voice.open) { state.voice.send({ type: "tap", action }); return; }
  try {
    const r = await api(`/api/agent/${action}`, { method: "POST" });
    r.spoken.forEach((s) => bot(s));
    renderSlip(r.ui);
    refreshPanels();
  } catch (e) { bot(`Could not ${action}: ${e.message}`); }
}

// ---- panels: open orders, bills, khata -------------------------------------------------------------------------
function billLink(n) {
  const q = state.mode === "sample" ? `?sample=${encodeURIComponent(SAMPLE_SESSION)}` : "";
  return `/bill/${n}${q}`;
}

async function refreshPanels() {
  try {
    const [orders, bills, customers, books] = await Promise.all([api("/api/orders"), api("/api/bills"),
      api("/api/customers"), api("/api/books")]);
    renderBooks(books);
    $("panel-orders").replaceChildren(...(orders.length ? orders.map((o) => el("div", { class: "row" },
      el("span", { class: "name" }, o.customer_name), el("span", { class: "amt" }, o.total),
      el("span", { class: "sub" }, [o.city, `${o.line_count} ${o.line_count === 1 ? "item" : "items"}`].filter(Boolean).join(" · "))))
      : [el("p", { class: "muted" }, "No open orders.")]));
    $("panel-bills").replaceChildren(...(bills.length ? bills.map((b) => el("div", { class: "row" },
      el("a", { class: "name", href: billLink(b.number), target: "_blank" }, `Invoice ${b.number} · ${b.customer}`),
      el("span", { class: "amt" }, b.total),
      el("span", { class: "sub" }, b.voided ? "undone" : b.created_at.slice(0, 10)),
      el("span", { class: "row-actions" }, shareButton(b.number))))
      : [el("p", { class: "muted" }, "No invoices yet. Say “bill it” after an order is saved.")]),
      reportLink());
    $("panel-khata").replaceChildren(...(customers.length ? customers.map((c) => {
      const undo = el("button", { class: "link" }, "Undo last");
      undo.addEventListener("click", () => undoLast(c));
      return el("div", { class: "row" }, el("span", { class: "name" }, c.name),
        el("span", { class: `amt ${c.balance_paise < 0 ? "advance" : ""}` }, c.balance_paise < 0 ? `Advance ${c.balance.replace("-", "")}` : c.balance),
        el("span", { class: "sub" }, c.balance_paise > 0 ? "owes the shop" : c.balance_paise < 0 ? "paid in advance" : "settled"),
        el("span", { class: "row-actions" }, undo));
    }) : [el("p", { class: "muted" }, "No customers yet.")]));
  } catch (e) { /* panels are a convenience; the conversation still works */ }
}

function reportLink() {
  const month = new Date().toISOString().slice(0, 7);
  const a = el("a", { class: "report", href: `/api/reports/gst.csv?month=${month}`, download: "" },
    `⤓ Monthly GST report for the auditor (${month})`);
  if (state.mode === "sample") {
    a.addEventListener("click", async (ev) => {
      ev.preventDefault();
      const res = await fetch(a.getAttribute("href"), { headers: { "X-Sample-Session": SAMPLE_SESSION } });
      const url = URL.createObjectURL(await res.blob());
      Object.assign(document.createElement("a"), { href: url, download: `gst-invoices-${month}.csv` }).click();
    });
  }
  return a;
}

// The two paper notebooks, as records: the customer book and the order book (each line keeps the words it came from).
function renderBooks(books) {
  const box = $("panel-books");
  if (!books.customers.length) { box.replaceChildren(el("p", { class: "muted" }, "Nothing in the books yet.")); return; }
  const customerRows = books.customers.map((c) => el("tr", {},
    el("td", {}, c.name), el("td", {}, [c.city, c.state].filter(Boolean).join(", ")),
    el("td", {}, c.gstin || "—"), el("td", { class: "num" }, c.orders), el("td", { class: "num" }, c.balance)));
  const orderCards = books.orders.map((o) => el("div", { class: "book-order" },
    el("div", { class: "book-head" },
      el("b", {}, `#${o.id} ${o.customer}`),
      el("span", {}, [o.date, o.state, o.invoice_no].filter(Boolean).join(" · "))),
    el("table", { class: "book" }, el("tbody", {}, ...o.lines.map((l, i) => el("tr", {},
      el("td", {}, l.item, el("span", { class: "said" },
        l.said && (i === 0 || l.said !== o.lines[i - 1].said) ? `🎤 “${l.said}”` : "")),
      el("td", {}, l.qty), el("td", { class: "num" }, l.amount))))),
    el("p", { class: "sub" }, [o.transport && `Transport ${o.transport}`, o.payment && `Payment ${o.payment}`]
      .filter(Boolean).join(" · "))));
  box.replaceChildren(
    el("h3", { class: "book-title" }, "Customer book"),
    el("table", { class: "book" },
      el("thead", {}, el("tr", {}, el("th", {}, "Customer"), el("th", {}, "Place"), el("th", {}, "GSTIN"),
        el("th", { class: "num" }, "Orders"), el("th", { class: "num" }, "Balance"))),
      el("tbody", {}, ...customerRows)),
    el("h3", { class: "book-title" }, "Order book"),
    ...orderCards);
}

function shareButton(number) {
  const b = el("button", { class: "link" }, "Share");
  b.addEventListener("click", async () => {
    const bill = await api(`/api/bills/${number}`);
    try {
      if (navigator.share) await navigator.share({ title: `Bill ${number}`, text: bill.share_text });
      else { await navigator.clipboard.writeText(bill.share_text); b.textContent = "Copied"; }
    } catch (_) { /* the owner closed the share sheet */ }
  });
  return b;
}

async function undoLast(c) {
  try {
    const r = await api(`/api/customers/${c.id}/undo`, { method: "POST" });
    bot(`${c.name}: ${r.message}`);
  } catch (e) { bot(`${c.name}: ${e.message}`); }
  refreshPanels();
}

// ---- live: talk, upload, type ----------------------------------------------------------------------------------
function turnMeta(r) {
  const ms = Object.values(r.timings_ms || {}).reduce((a, b) => a + b, 0);
  return ms ? `AI ${(ms / 1000).toFixed(1)} s · ₹${(r.cost_paise / 100).toFixed(2)} (estimated)` : null;
}

async function typed(text) {
  owner(text, "typed");
  try {
    const r = await api("/api/agent/text", { method: "POST", json: { text } });
    r.spoken.forEach((s, i) => bot(s, i === r.spoken.length - 1 ? turnMeta(r) : null));
    renderSlip(r.ui);
    refreshPanels();
  } catch (e) { bot(e.message); }
}

async function uploaded(file) {
  const form = new FormData();
  form.append("audio", file, file.name);
  const note = owner(`📎 ${file.name}`, "transcribing…");
  try {
    if (state.voice && state.voice.open) {
      const t = await api("/api/agent/transcribe", { method: "POST", form });
      note.querySelector(".voice").textContent = `📎 ${t.transcript}`;
      note.querySelector(".meta").textContent = "forwarded voice note";
      state.voice.send({ type: "note", text: t.transcript });
      return;
    }
    const r = await api("/api/agent/upload", { method: "POST", form });
    note.querySelector(".voice").textContent = `📎 ${r.transcript}`;
    note.querySelector(".meta").textContent = "forwarded voice note";
    r.spoken.forEach((s, i) => bot(s, i === r.spoken.length - 1 ? turnMeta(r) : null));
    renderSlip(r.ui);
    refreshPanels();
  } catch (e) { note.querySelector(".meta").textContent = e.message; }
}

function onVoiceEvent(m) {
  if (m.type === "user") owner(m.text, "🎤");
  else if (m.type === "bot" && m.partial) botPartial(m.text);
  else if (m.type === "bot") bot(m.text);
  else if (m.type === "latency") addMeta(state.botBubble || [...document.querySelectorAll(".bubble.bot")].pop(), `reply in ${m.s} s`);
  else if (m.type === "slip") { renderSlip(m); refreshPanels(); }
  else if (m.type === "closed") {
    setTalk(false);
    if (m.code === 4003) $("key-banner").hidden = false;
    else if (m.code === 4029) bot("Too many voice sessions from here. Please try again later, or type.");
  }
}

function setTalk(on) {
  $("talk").textContent = on ? "■ Stop" : "🎤 Talk";
  $("talk").classList.toggle("on", on);
}

async function toggleTalk() {
  if (state.voice && state.voice.open) { state.voice.stop(); setTalk(false); return; }
  state.voice = new window.KuralVoice(onVoiceEvent);
  try {
    await state.voice.start(AGENT_SESSION, $("lang").value);
    setTalk(true);
    bot("Listening… speak your order.");
  } catch (e) { bot(`Could not start the microphone: ${e.message}`); setTalk(false); }
}

// ---- sample ----------------------------------------------------------------------------------------------------
function playInOrder(urls) {
  const list = urls.filter(Boolean);
  const next = () => {
    const url = list.shift();
    if (!url) return;
    const a = new Audio(url);
    a.onended = next;
    a.play().catch(next);
  };
  next();
}

async function sampleNext() {
  $("sample-next").disabled = true;
  try {
    const s = await api("/api/sample/next", { method: "POST" });
    owner(s.user_text, `Step ${s.index} of ${s.total} · ${s.label}`);
    s.spoken.forEach((t) => bot(t));
    if (s.bill_number) {
      const b = bubble("bot", "");
      b.querySelector(".voice").append(el("a", { href: billLink(s.bill_number), target: "_blank" }, `Open tax invoice ${s.bill_number} and packing list`));
    }
    renderSlip(s.slip);
    refreshPanels();
    playInOrder([s.user_audio_url, s.bot_audio_url]);
    if (s.index === s.total) {
      $("sample-next").hidden = true;
      bot("That is the whole flow: order in pieces, sari, GST invoice, khata, and a question. Leave the sample to use the real shop.");
    }
  } catch (e) {
    if (e.status === 409) $("sample-next").hidden = true;
    else bot(`Could not load the next step: ${e.message}`);
  } finally { $("sample-next").disabled = false; }
}

async function sampleStart() {
  if (state.voice && state.voice.open) { state.voice.stop(); setTalk(false); }
  state.mode = "sample";
  SAMPLE_SESSION = newId();
  document.body.classList.add("sample-mode");
  $("mode-banner").hidden = false;
  $("chat").replaceChildren();
  $("slip").replaceChildren();
  await api("/api/sample/reset", { method: "POST" });
  $("sample-start").textContent = "Restart the sample";
  $("sample-next").hidden = false;
  await sampleNext();
}

async function leaveSample() {
  state.mode = "live";
  document.body.classList.remove("sample-mode");
  $("mode-banner").hidden = true;
  $("sample-next").hidden = true;
  $("sample-start").textContent = "Try the sample";
  $("chat").replaceChildren();
  await showLive();
}

async function showLive() {
  const r = await api("/api/agent/state").catch(() => ({ ui: null }));
  renderSlip(r.ui);
  refreshPanels();
}

// ---- start -----------------------------------------------------------------------------------------------------
async function loadStatus() {
  const data = await api("/api/status");
  state.keyReady = !Object.values(data.providers).some((s) => s === "not_set");
  $("key-banner").hidden = state.keyReady;
  $("talk").disabled = !state.keyReady;
  $("upload").disabled = !state.keyReady;
  $("type-box").disabled = !state.keyReady;
  $("upload-label").classList.toggle("disabled", !state.keyReady);
  if (!state.keyReady) $("type-box").placeholder = "Key not set: try the sample";
}

for (const tab of document.querySelectorAll('[role="tab"]')) {
  tab.addEventListener("click", () => {
    for (const t of document.querySelectorAll('[role="tab"]')) {
      const on = t === tab;
      t.setAttribute("aria-selected", String(on));
      $(`panel-${t.dataset.panel}`).hidden = !on;
    }
  });
}
$("talk").addEventListener("click", toggleTalk);
$("upload").addEventListener("change", (e) => { const f = e.target.files[0]; e.target.value = ""; if (f) uploaded(f); });
$("type-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const text = $("type-box").value.trim();
  if (text) { $("type-box").value = ""; typed(text); }
});
$("sample-start").addEventListener("click", sampleStart);
$("sample-next").addEventListener("click", sampleNext);
$("leave-sample").addEventListener("click", leaveSample);
loadStatus();
showLive();
