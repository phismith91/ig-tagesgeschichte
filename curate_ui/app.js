const MAX_SELECTED = 9;
let state = { date: null, candidates: [], selectedIds: [] };

function todayStr() {
  // ponytail: lokale Datumsteile statt toISOString() (UTC) — sonst kippt
  // "Heute" für ~1-2h um Mitternacht auf den Vortag (Code-Review-Fund).
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function shiftDate(dateStr, days) {
  const d = new Date(dateStr + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

let loadSeq = 0;

async function loadDay(date) {
  // ponytail: state.date wird sofort gesetzt, nicht erst nach Erfolg —
  // sonst wiederholen ◀/▶ auf einem Tag ohne Kandidaten immer denselben Sprung.
  const mySeq = ++loadSeq;
  state.date = date;
  state.candidates = [];
  state.selectedIds = [];
  document.getElementById("date").textContent = date;

  let res;
  try {
    res = await fetch(`/api/day/${date}`);
  } catch (e) {
    if (mySeq !== loadSeq) return; // von neuerem Nav-Klick überholt
    document.getElementById("cards").textContent = "Server nicht erreichbar.";
    document.getElementById("progress").textContent = "";
    return;
  }
  if (mySeq !== loadSeq) return; // von neuerem Nav-Klick überholt
  if (!res.ok) {
    document.getElementById("cards").textContent = "Keine Kandidaten für diesen Tag.";
    document.getElementById("progress").textContent = "";
    return;
  }
  const data = await res.json();
  if (mySeq !== loadSeq) return; // von neuerem Nav-Klick überholt
  state.candidates = data.candidates;
  state.selectedIds = [...data.selected_ids];
  render();
}

function toggle(id) {
  const idx = state.selectedIds.indexOf(id);
  if (idx >= 0) {
    state.selectedIds.splice(idx, 1);
  } else if (state.selectedIds.length < MAX_SELECTED) {
    state.selectedIds.push(id);
  }
  render();
}

function buildCard(c, order, disabled) {
  const div = document.createElement("div");
  div.className = "card" + (order >= 0 ? " selected" : "") + (disabled ? " disabled" : "");

  if (order >= 0) {
    const orderBadge = document.createElement("div");
    orderBadge.className = "order";
    orderBadge.textContent = String(order + 1);
    div.appendChild(orderBadge);
  }

  const sourceBadge = document.createElement("span");
  sourceBadge.className = "badge";
  sourceBadge.textContent = c.source;
  div.appendChild(sourceBadge);

  const langBadge = document.createElement("span");
  langBadge.className = "badge";
  langBadge.textContent = c.lang;
  div.appendChild(langBadge);

  const yearSpan = document.createElement("span");
  yearSpan.className = "year";
  yearSpan.textContent = c.year ?? "";
  div.appendChild(yearSpan);

  const mainText = document.createElement("p");
  mainText.textContent = c.text_de ? c.text_de : c.text;
  div.appendChild(mainText);

  if (c.text_de) {
    const original = document.createElement("div");
    original.className = "original";
    original.textContent = c.text;
    div.appendChild(original);
  }

  div.addEventListener("click", () => toggle(c.id));
  return div;
}

function render() {
  document.getElementById("date").textContent = state.date;
  document.getElementById("progress").textContent =
    `${state.selectedIds.length}/${MAX_SELECTED} ausgewählt`;
  const cards = document.getElementById("cards");
  cards.innerHTML = "";
  for (const c of state.candidates) {
    const order = state.selectedIds.indexOf(c.id);
    const disabled = order < 0 && state.selectedIds.length >= MAX_SELECTED;
    cards.appendChild(buildCard(c, order, disabled));
  }
}

async function save() {
  let saveRes;
  try {
    saveRes = await fetch(`/api/day/${state.date}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ selected_ids: state.selectedIds }),
    });
  } catch (e) {
    document.getElementById("progress").textContent = "Speichern fehlgeschlagen: Server nicht erreichbar.";
    return;
  }
  if (!saveRes.ok) {
    document.getElementById("progress").textContent = "Speichern fehlgeschlagen — bitte erneut versuchen.";
    return;
  }
  loadDay(shiftDate(state.date, 1));
}

document.getElementById("save").addEventListener("click", save);
document.getElementById("prev").addEventListener("click", () => loadDay(shiftDate(state.date, -1)));
document.getElementById("next").addEventListener("click", () => loadDay(shiftDate(state.date, 1)));
document.getElementById("today").addEventListener("click", () => loadDay(todayStr()));

const params = new URLSearchParams(location.search);
loadDay(params.get("date") || todayStr());
