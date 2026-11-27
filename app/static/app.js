// Order Kural front end: plain JS, no build step. All text goes in via textContent (never innerHTML).

const $ = (id) => document.getElementById(id);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else node.setAttribute(k, v);
  }
  for (const c of children) {
    if (c === null || c === undefined) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

// Each browser tab runs its own sample, so visitors never see or wipe each other's sample orders.
const SAMPLE_SESSION = (crypto.randomUUID && crypto.randomUUID()) || String(Date.now()) + Math.random();

async function api(path, method = "GET") {
  const res = await fetch(path, { method, headers: { "X-Sample-Session": SAMPLE_SESSION } });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(body.detail || res.statusText), { status: res.status });
  return body;
}

const FLAG_TEXT = { below_min: "below minimum", sizes_missing: "sizes missing", rate_off_list: "rate differs from list" };

function sizesText(sizes) {
  return Object.entries(sizes).map(([s, q]) => `${s} ${q}`).join(", ");
}

async function loadStatus() {
  const data = await api("/api/status");
  const missing = Object.values(data.providers).some((s) => s === "not_set");
  $("key-banner").hidden = !missing;
}

async function loadOrders() {
  const orders = await api("/api/orders");
  const box = $("orders");
  box.replaceChildren();
  if (!orders.length) {
    box.append(el("p", { class: "muted" }, "No open orders yet."));
    return;
  }
  for (const o of orders) {
    const lines = `${o.line_count} ${o.line_count === 1 ? "item" : "items"}`;
    box.append(el("div", { class: "order-row" },
      el("span", { class: "name" }, o.customer_name),
      el("span", { class: "amt" }, o.total),
      el("span", { class: "sub" }, [o.city, lines].filter(Boolean).join(", "))));
  }
}

function addBubble(sample) {
  $("chat-empty")?.remove();
  $("chat").append(el("div", { class: "bubble" },
    el("p", { class: "who" }, `Voice piece ${sample.index} of ${sample.total}`),
    el("p", { class: "voice", lang: "ta" }, sample.transcript),
    el("p", { class: "meta" }, sample.label)));
}

function renderSlip(p) {
  const kinds = {};
  for (const d of p.diff) if (d.item_code) kinds[d.item_code] = d.kind;

  const rows = p.order.lines.map((l) => {
    const flags = l.flags.map((f) => el("span", { class: "badge" }, FLAG_TEXT[f] || f));
    const sizes = Object.keys(l.sizes).length ? el("span", { class: "sizes" }, sizesText(l.sizes)) : null;
    return el("tr", { class: kinds[l.item_code] || "" },
      el("td", {}, `${l.name} `, sizes, ...flags),
      el("td", { class: "num" }, l.quantity),
      el("td", { class: "num" }, l.rate),
      el("td", { class: "num" }, l.line_total));
  });

  const slip = el("article", { class: "slip fresh", "aria-label": "Proposed change" },
    el("div", { class: "slip-head" },
      el("h3", {}, [p.order.customer_name, p.order.city].filter(Boolean).join(", ")),
      el("span", { class: "tag" }, p.is_new_order ? "New order" : `Adding to order #${p.order_id}`)),
    el("table", {},
      el("thead", {}, el("tr", {}, el("th", {}, "Item"), el("th", { class: "num" }, "Qty"),
        el("th", { class: "num" }, "Rate"), el("th", { class: "num" }, "Amount"))),
      el("tbody", {}, ...rows)),
    el("div", { class: "totals" },
      el("span", {}, "Subtotal"), el("span", {}, p.totals.subtotal),
      el("span", {}, "GST"), el("span", {}, p.totals.gst),
      el("span", { class: "grand" }, "Total"), el("span", { class: "grand" }, p.totals.total)),
    [p.order.transport && `Transport: ${p.order.transport}`, p.order.payment && `Payment: ${p.order.payment}`]
      .filter(Boolean).length
      ? el("p", { class: "needed" }, [p.order.transport && `Transport: ${p.order.transport}`,
          p.order.payment && `Payment: ${p.order.payment}`].filter(Boolean).join(". "))
      : null,
    p.missing.length ? el("p", { class: "needed" }, `Still needed: ${p.missing.join(", ")}`) : null,
    p.problems.length ? el("ul", { class: "problems" }, ...p.problems.map((x) => el("li", {}, x))) : null,
    el("p", { class: "readback" }, p.readback));

  if (!p.ask_customer) {
    const yes = el("button", { class: "yes" }, "Sari ✔");
    const no = el("button", { class: "no" }, "Vendaam ✖");
    const actions = el("div", { class: "actions" }, yes, no);
    yes.addEventListener("click", () => decide(p.piece_id, "confirm", slip, actions));
    no.addEventListener("click", () => decide(p.piece_id, "discard", slip, actions));
    slip.append(actions);
  }
  return slip;
}

async function decide(pieceId, action, slip, actions) {
  actions.querySelectorAll("button").forEach((b) => (b.disabled = true));
  try {
    await api(`/api/pieces/${pieceId}/${action}`, "POST");
    actions.replaceWith(el("p", { class: "status-line" },
      action === "confirm" ? "Saved to the order." : "Discarded. The order is unchanged."));
    slip.classList.add("done");
    $("chat").append(el("div", { class: "bubble reply" }, el("p", { class: "voice" }, action === "confirm" ? "Sari" : "Vendaam")));
    await loadOrders();
    $("sample-next").disabled = false;
  } catch (e) {
    actions.querySelectorAll("button").forEach((b) => (b.disabled = false));
    actions.after(el("p", { class: "problems" }, `Could not ${action}: ${e.message}`));
  }
}

async function nextPiece() {
  $("sample-next").disabled = true;
  try {
    const sample = await api("/api/sample/next", "POST");
    addBubble(sample);
    $("proposal").replaceChildren(renderSlip(sample.proposal));
    $("proposal").scrollIntoView({ behavior: "smooth", block: "start" });
    if (sample.index === sample.total) $("sample-next").hidden = true;
  } catch (e) {
    if (e.status === 409) $("sample-next").hidden = true;
    else $("proposal").replaceChildren(el("p", { class: "problems" }, `Could not load the next piece: ${e.message}`));
  }
}

async function startSample() {
  await api("/api/sample/reset", "POST");
  $("chat").replaceChildren();
  $("proposal").replaceChildren();
  await loadOrders();
  $("sample-start").textContent = "Restart the sample";
  $("sample-next").hidden = false;
  await nextPiece();
}

$("sample-start").addEventListener("click", startSample);
$("sample-next").addEventListener("click", nextPiece);
loadStatus();
loadOrders();
