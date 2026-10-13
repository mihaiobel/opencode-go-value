/* opencode-go Value – client-side role recommendation and sortable table.
 * Loads ./data/latest.json (same origin, no external requests) and applies the
 * role matrix documented in the Methodik section of index.html.
 */
"use strict";

const DATA_URL = "data/latest.json";

/* ---------- helpers ---------- */

// Family = leading alphabetic run of the model id.
// "deepseek-v4.1-flash" -> "deepseek", "claude-haiku-5-5" -> "claude",
// "qwen3.7-plus" -> "qwen", "hy3" -> "hy", "mimo-v2.6-pro" -> "mimo".
function familyOf(id) {
  const m = /^[a-z]+/.exec(String(id || ""));
  return m ? m[0] : String(id || "");
}

function isFree(m) {
  return m.free === true || /-free$/.test(m.id);
}

function num(v) {
  return typeof v === "number" && isFinite(v) ? v : null;
}

function maxBy(items, score) {
  let best = null;
  let bestScore = -Infinity;
  for (const it of items) {
    const s = score(it);
    if (s === null || !isFinite(s)) continue;
    if (s > bestScore) {
      bestScore = s;
      best = it;
    }
  }
  return best;
}

function minBy(items, score) {
  let best = null;
  let bestScore = Infinity;
  for (const it of items) {
    const s = score(it);
    if (s === null || !isFinite(s)) continue;
    if (s < bestScore) {
      bestScore = s;
      best = it;
    }
  }
  return best;
}

function idDesc(a, b) {
  return String(b.id).localeCompare(String(a.id));
}

/* ---------- role matrix ---------- */

// orchestrator: biggest req/5h among AA-intel >= 38, plus the muse-spark
// no_data special case (biggest quota wins there).
function pickOrchestrator(models) {
  const pool = models.filter((m) => {
    if (isFree(m)) return false;
    const intel = num(m.aa_intelligence);
    const isMuse = /^muse-spark/.test(m.id);
    return intel !== null && intel >= 38 ? true : isMuse;
  });
  pool.sort((a, b) => {
    const d = (num(b.requests_per_5h) ?? -1) - (num(a.requests_per_5h) ?? -1);
    if (d !== 0) return d;
    const di = (num(b.aa_intelligence) ?? -1) - (num(a.aa_intelligence) ?? -1);
    if (di !== 0) return di;
    return idDesc(a, b);
  });
  return pool[0] || null;
}

// dev: max(speed × req/5h) at intel >= 34 and monthly limit >= $30.
function pickDev(models) {
  const pool = models.filter((m) => {
    if (isFree(m)) return false;
    const intel = num(m.aa_intelligence);
    const speed = num(m.aa_speed_tps);
    const limit = num(m.monthly_limit_usd);
    const req = num(m.requests_per_5h);
    return (
      intel !== null && intel >= 34 &&
      limit !== null && limit >= 30 &&
      speed !== null && req !== null
    );
  });
  return maxBy(pool, (m) => num(m.aa_speed_tps) * num(m.requests_per_5h));
}

// researcher: cheapest AA-$/Task at req/5h >= 3000 with a usable intelligence
// floor (>= 34, same bar as dev) and not the dev model.
function pickResearcher(models, dev) {
  const pool = models.filter((m) => {
    if (isFree(m)) return false;
    if (dev && m.id === dev.id) return false;
    const intel = num(m.aa_intelligence);
    const cost = num(m.aa_cost_per_task);
    const req = num(m.requests_per_5h);
    return intel !== null && intel >= 34 && cost !== null && req !== null && req >= 3000;
  });
  pool.sort((a, b) => {
    const d = num(a.aa_cost_per_task) - num(b.aa_cost_per_task);
    if (d !== 0) return d;
    const dr = (num(b.requests_per_5h) ?? -1) - (num(a.requests_per_5h) ?? -1);
    if (dr !== 0) return dr;
    return (num(b.aa_intelligence) ?? -1) - (num(a.aa_intelligence) ?? -1);
  });
  return pool[0] || null;
}

// reviewer: max intel at req/5h >= 1000 in a family not already used by the
// other roles (dev + researcher + orchestrator) -> uncorrelated failures.
function pickReviewer(models, usedFamilies) {
  const pool = models.filter((m) => {
    if (isFree(m)) return false;
    const intel = num(m.aa_intelligence);
    const req = num(m.requests_per_5h);
    if (intel === null || req === null || req < 1000) return false;
    return !usedFamilies.has(familyOf(m.id));
  });
  pool.sort((a, b) => {
    const d = num(b.aa_intelligence) - num(a.aa_intelligence);
    if (d !== 0) return d;
    const dr = (num(b.requests_per_5h) ?? -1) - (num(a.requests_per_5h) ?? -1);
    if (dr !== 0) return dr;
    return (num(a.aa_cost_per_task) ?? Infinity) - (num(b.aa_cost_per_task) ?? Infinity);
  });
  return pool[0] || null;
}

function recommend(models) {
  const orchestrator = pickOrchestrator(models);
  const dev = pickDev(models);
  const researcher = pickResearcher(models, dev);
  const usedFamilies = new Set();
  for (const m of [orchestrator, dev, researcher]) {
    if (m) usedFamilies.add(familyOf(m.id));
  }
  const reviewer = pickReviewer(models, usedFamilies);
  return { orchestrator, dev, reviewer, researcher };
}

/* ---------- rendering ---------- */

const ROLE_META = {
  orchestrator: {
    label: "Orchestrator",
    reason:
      "Viele kleine Turns und lange, repetitive Sessions: größte req/5h bei AA-Intel ≥ 38 (bzw. muse-spark als no_data-Sonderfall mit der größten Quota) plus hoher Cache-Rabatt.",
  },
  dev: {
    label: "Dev",
    reason:
      "Meiste Calls pro Task: maximiert Speed × req/5h bei AA-Intel ≥ 34 und Monatslimit ≥ $30 — Frequenz schlägt Spitze.",
  },
  reviewer: {
    label: "Reviewer",
    reason:
      "~1 Call/Task, lange Reports: höchster AA-Intel in einer Familie, die weder Dev noch Researcher nutzt (unkorrelierte Fehler), req/5h ≥ 1000.",
  },
  researcher: {
    label: "Researcher",
    reason:
      "Nur Lesen, darf keine Dev-Quota verbrennen: günstigster AA-$/Task bei req/5h ≥ 3000 und brauchbarer Intelligenz (≥ 34), nicht das Dev-Modell.",
  },
};

function fmtNum(v, digits) {
  if (v === null || v === undefined) return "–";
  const n = Number(v);
  if (!isFinite(n)) return "–";
  return n.toLocaleString("de-DE", {
    minimumFractionDigits: digits ?? 0,
    maximumFractionDigits: digits ?? 0,
  });
}

function fmtUsd(v, digits) {
  if (v === null || v === undefined) return "–";
  const n = Number(v);
  if (!isFinite(n)) return "–";
  return "$" + n.toLocaleString("de-DE", {
    minimumFractionDigits: digits ?? 0,
    maximumFractionDigits: Math.max(digits ?? 0, 4),
  });
}

function metricRow(label, value) {
  const span = document.createElement("span");
  span.className = "metric";
  const l = document.createElement("span");
  l.className = "metric-label";
  l.textContent = label;
  const v = document.createElement("span");
  v.className = "metric-value";
  v.textContent = value;
  span.append(l, v);
  return span;
}

function roleCard(roleKey, model) {
  const meta = ROLE_META[roleKey];
  const card = document.createElement("article");
  card.className = "card";
  card.dataset.role = roleKey;

  const h = document.createElement("h3");
  h.textContent = meta.label;
  card.append(h);

  if (!model) {
    const p = document.createElement("p");
    p.className = "card-warning";
    p.textContent =
      "Kein Modell erfüllt die Kriterien dieser Rolle. Matrix prüfen oder Daten aktualisieren.";
    card.append(p);
    return card;
  }

  const mid = document.createElement("p");
  mid.className = "card-model";
  mid.textContent = model.id;
  card.append(mid);

  const metrics = document.createElement("div");
  metrics.className = "metrics";
  metrics.append(
    metricRow("req/5h", fmtNum(model.requests_per_5h)),
    metricRow("$/Monat", fmtUsd(model.monthly_limit_usd, 0)),
    metricRow("AA-Intel", fmtNum(model.aa_intelligence)),
    metricRow("AA-Speed", model.aa_speed_tps == null ? "–" : fmtNum(model.aa_speed_tps, 1) + " t/s"),
    metricRow("AA-$/Task", fmtUsd(model.aa_cost_per_task, 2)),
    metricRow("AA-Status", model.aa_status || "–")
  );
  card.append(metrics);

  const why = document.createElement("p");
  why.className = "card-reason";
  why.textContent = meta.reason;
  card.append(why);

  return card;
}

function renderRoles(reco) {
  const host = document.getElementById("role-cards");
  if (!host) return;
  host.textContent = "";
  for (const key of ["orchestrator", "dev", "reviewer", "researcher"]) {
    host.append(roleCard(key, reco[key]));
  }
}

/* ---------- sortable table ---------- */

const COLUMNS = [
  { key: "id", label: "Modell", type: "text", cell: (m) => m.id },
  { key: "monthly_limit_usd", label: "$/Monat", type: "num", cell: (m) => m.monthly_limit_usd },
  { key: "requests_per_5h", label: "req/5h", type: "num", cell: (m) => m.requests_per_5h },
  { key: "price_in", label: "In $/1M", type: "num", cell: (m) => m.price_in },
  { key: "price_out", label: "Out $/1M", type: "num", cell: (m) => m.price_out },
  { key: "price_cached", label: "Cached $/1M", type: "num", cell: (m) => m.price_cached },
  { key: "aa_intelligence", label: "AA-Intel", type: "num", cell: (m) => m.aa_intelligence },
  { key: "aa_speed_tps", label: "AA-Speed", type: "num", cell: (m) => m.aa_speed_tps },
  { key: "aa_cost_per_task", label: "AA-$/Task", type: "num", cell: (m) => m.aa_cost_per_task },
  { key: "aa_status", label: "AA-Status", type: "text", cell: (m) => m.aa_status || "" },
];

let sortState = { key: "aa_intelligence", dir: -1 };

function fmtCell(col, m) {
  const raw = col.cell(m);
  if (col.type === "text") return raw === null || raw === undefined ? "–" : String(raw);
  switch (col.key) {
    case "monthly_limit_usd":
      return fmtUsd(raw, 0);
    case "price_in":
    case "price_out":
    case "price_cached":
      return fmtUsd(raw, raw != null && Math.abs(raw) < 1 ? 3 : 2);
    case "aa_speed_tps":
      return raw == null ? "–" : fmtNum(raw, 1);
    case "aa_cost_per_task":
      return fmtUsd(raw, 2);
    default:
      return fmtNum(raw);
  }
}

function sortModels(models) {
  const col = COLUMNS.find((c) => c.key === sortState.key);
  if (!col) return models;
  const dir = sortState.dir;
  return models.slice().sort((a, b) => {
    const av = col.cell(a);
    const bv = col.cell(b);
    if (col.type === "text") {
      return String(av).localeCompare(String(bv)) * dir;
    }
    const an = num(av);
    const bn = num(bv);
    // nulls always last, regardless of direction
    if (an === null && bn === null) return String(a.id).localeCompare(String(b.id));
    if (an === null) return 1;
    if (bn === null) return -1;
    if (an === bn) return String(a.id).localeCompare(String(b.id));
    return (an - bn) * dir;
  });
}

function renderTable(models, reco) {
  const table = document.getElementById("models-table");
  if (!table) return;
  const recommended = new Set(
    ["orchestrator", "dev", "reviewer", "researcher"]
      .map((k) => reco[k] && reco[k].id)
      .filter(Boolean)
  );

  const thead = document.createElement("thead");
  const htr = document.createElement("tr");
  for (const col of COLUMNS) {
    const th = document.createElement("th");
    th.textContent = col.label;
    th.dataset.key = col.key;
    th.className = "sortable";
    if (sortState.key === col.key) {
      th.classList.add(sortState.dir === 1 ? "sort-asc" : "sort-desc");
      th.setAttribute("aria-sort", sortState.dir === 1 ? "ascending" : "descending");
    }
    th.addEventListener("click", () => {
      if (sortState.key === col.key) {
        sortState.dir = -sortState.dir;
      } else {
        sortState = { key: col.key, dir: col.type === "text" ? 1 : -1 };
      }
      renderTable(models, reco);
    });
    htr.append(th);
  }
  thead.append(htr);
  table.textContent = "";
  table.append(thead);

  const tbody = document.createElement("tbody");
  for (const m of sortModels(models)) {
    const tr = document.createElement("tr");
    if (isFree(m) || m.aa_status === "no_data") tr.classList.add("muted");
    if (isFree(m)) tr.classList.add("free-excluded");
    if (recommended.has(m.id)) tr.classList.add("recommended-row");
    if (m.excluded_reason) tr.title = m.excluded_reason;

    COLUMNS.forEach((col, idx) => {
      const td = document.createElement("td");
      td.textContent = fmtCell(col, m);
      if (col.type === "num") td.classList.add("num");
      if (idx === 0) {
        if (recommended.has(m.id)) {
          const badge = document.createElement("span");
          badge.className = "badge";
          badge.textContent = "empfohlen";
          td.append(" ", badge);
        }
        if (isFree(m)) {
          const tag = document.createElement("span");
          tag.className = "badge badge-free";
          tag.textContent = "free – ausgeschlossen";
          if (m.excluded_reason) tag.title = m.excluded_reason;
          td.append(" ", tag);
        }
      }
      tr.append(td);
    });
    tbody.append(tr);
  }
  table.append(tbody);
}

/* ---------- chrome: meta, sources, copy ---------- */

function renderMeta(meta) {
  const stand = document.getElementById("stand-date");
  if (stand) stand.textContent = meta.stand_datum || "–";
  const plan = document.getElementById("plan-name");
  if (plan) plan.textContent = meta.plan || "opencode-go";
  const aav = document.getElementById("aa-version");
  if (aav) aav.textContent = meta.aa_index_version || "–";
  const note = document.getElementById("meta-hint");
  if (note && Array.isArray(meta.hinweise)) {
    note.textContent = meta.hinweise.join(" ");
  }
}

function renderSources(meta) {
  const host = document.getElementById("sources-list");
  if (!host) return;
  host.textContent = "";
  const urls = Array.isArray(meta.quellen_urls) ? meta.quellen_urls : [];
  for (const url of urls) {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = url;
    a.textContent = url;
    a.rel = "noopener noreferrer";
    a.target = "_blank";
    li.append(a);
    host.append(li);
  }
}

function wireCopy() {
  const btn = document.getElementById("copy-prompt");
  const src = document.getElementById("daily-prompt");
  if (!btn || !src) return;
  btn.addEventListener("click", async () => {
    const text = src.textContent.trim();
    try {
      await navigator.clipboard.writeText(text);
      btn.textContent = "Kopiert ✓";
    } catch (err) {
      // Fallback for non-secure contexts / older browsers.
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.append(ta);
      ta.select();
      try {
        document.execCommand("copy");
        btn.textContent = "Kopiert ✓";
      } catch (e2) {
        btn.textContent = "Kopieren fehlgeschlagen";
      }
      ta.remove();
    }
    setTimeout(() => (btn.textContent = "Daily-Prompt kopieren"), 2000);
  });
}

/* ---------- bootstrap ---------- */

async function init() {
  wireCopy();
  let payload;
  try {
    const res = await fetch(DATA_URL, { cache: "no-store" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    payload = await res.json();
  } catch (err) {
    const host = document.getElementById("role-cards");
    if (host) {
      const p = document.createElement("p");
      p.className = "card-warning";
      p.textContent = "Daten konnten nicht geladen werden (" + err.message + ").";
      host.append(p);
    }
    return;
  }

  const meta = payload.meta || {};
  const models = Array.isArray(payload.models) ? payload.models : [];
  renderMeta(meta);
  renderSources(meta);
  const reco = recommend(models);
  renderRoles(reco);
  renderTable(models, reco);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
