async function loadStatus() {
  const res = await fetch("/api/status");
  const data = await res.json();
  const anyMissing = Object.values(data.providers).some((s) => s === "not_set");
  document.getElementById("key-banner").hidden = !anyMissing;
}
loadStatus();
