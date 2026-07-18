const MAX_SELECTED = 9;
let state = { date: null, candidates: [], selectedIds: [] };

async function loadDay(date) {
  let res;
  try {
    res = await fetch(`/api/day/${date}`);
  } catch (e) {
    document.getElementById("cards").textContent = "Server nicht erreichbar.";
    return;
  }
  if (!res.ok) {
    document.getElementById("cards").textContent = "Keine Kandidaten für diesen Tag.";
    return;
  }
  const data = await res.json();
  state = { date: data.date, candidates: data.candidates, selectedIds: [...data.selected_ids] };
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
  const month = state.date.slice(0, 7);
  const res = await fetch(`/api/next?month=${month}`);
  if (res.ok) {
    const { date } = await res.json();
    loadDay(date);
  }
}

document.getElementById("save").addEventListener("click", save);

const params = new URLSearchParams(location.search);
const startDate = params.get("date");
if (startDate) {
  loadDay(startDate);
} else {
  const currentMonth = new Date().toISOString().slice(0, 7);
  fetch(`/api/next?month=${currentMonth}`)
    .then((r) => r.json())
    .then(({ date }) => loadDay(date));
}
