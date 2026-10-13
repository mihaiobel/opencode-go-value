/* opencode-go Value: client-side role recommendation and sortable table.
 * Loads ./data/latest.json (same origin, no external requests) and applies the
 * role matrix documented in the collapsed notes of index.html.
 */
"use strict";

const DATA_URL = "data/latest.json";

// Placeholder for a missing value across cards, table and meta.
const NA = "n/a";

/* ---------- helpers ---------- */

// Family = leading alphabetic run of the model id, so "abc-1.2" -> "abc"
// and "abc2.1-pro" -> "abc".
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

function idDesc(a, b) {
  return String(b.id).localeCompare(String(a.id));
}

/* ---------- combined score ---------- */

// Each source is normalised to 0..100 over its own range, then averaged.
// AA intelligence spans 0..60, LMArena Overall spans 1100..1550. A source with
// no value is skipped; when both are missing the score is null.
const SCORE_RANGES = {
  aa_intelligence: { min: 0, max: 60 },
  bench2_score: { min: 1100, max: 1550 },
};

function norm100(v, range) {
  return (100 * (v - range.min)) / (range.max - range.min);
}

function combinedScore(aa, arena) {
  const parts = [];
  const a = num(aa);
  if (a !== null) parts.push(norm100(a, SCORE_RANGES.aa_intelligence));
  const r = num(arena);
  if (r !== null) parts.push(norm100(r, SCORE_RANGES.bench2_score));
  if (!parts.length) return null;
  let sum = 0;
  for (const p of parts) sum += p;
  return sum / parts.length;
}

/* ---------- role matrix ---------- */

// orchestrator: biggest req/5h among models with AA intel >= 38.
function pickOrchestrator(models) {
  const pool = models.filter((m) => {
    if (isFree(m)) return false;
    const intel = num(m.aa_intelligence);
    return intel !== null && intel >= 38;
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

// dev: highest AA speed × req/5h at intel >= 34 and monthly limit >= $30.
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
// floor of >= 34, same bar as dev, and not the dev model.
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
// other roles, so failures stay uncorrelated.
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

/* ---------- formatting ---------- */

function fmtNum(v, digits) {
  if (v === null || v === undefined) return NA;
  const n = Number(v);
  if (!isFinite(n)) return NA;
  return n.toLocaleString("en-US", {
    minimumFractionDigits: digits ?? 0,
    maximumFractionDigits: digits ?? 0,
  });
}

function fmtUsd(v, digits) {
  if (v === null || v === undefined) return NA;
  const n = Number(v);
  if (!isFinite(n)) return NA;
  return "$" + n.toLocaleString("en-US", {
    minimumFractionDigits: digits ?? 0,
    maximumFractionDigits: Math.max(digits ?? 0, 4),
  });
}

/* ---------- role cards ---------- */

function fillRoleCard(card, model) {
  const field = (name) => card.querySelector('[data-field="' + name + '"]');
  // The slim cards carry model, score, req, month and intel. set() tolerates
  // a field being absent so the markup can stay lean.
  const set = (name, text) => {
    const el = field(name);
    if (el) el.textContent = text;
  };
  const modelLine = field("model");
  if (!model) {
    card.classList.add("card-empty");
    if (modelLine) modelLine.textContent = "No model meets this role's criteria.";
    return;
  }
  card.classList.remove("card-empty");
  if (modelLine) modelLine.textContent = model.id;
  set("score", fmtNum(combinedScore(model.aa_intelligence, model.bench2_score), 1));
  set("req", fmtNum(model.requests_per_5h));
  set("month", fmtUsd(model.monthly_limit_usd, 0));
  set("intel", fmtNum(model.aa_intelligence));
}

function renderRoles(reco) {
  const cards = document.querySelectorAll("#role-cards .card[data-role]");
  for (const card of cards) {
    fillRoleCard(card, reco[card.dataset.role]);
  }
}

/* ---------- sortable table ---------- */

// Only the columns that drive a decision. The collapsed notes in index.html
// document the rest of the data.
const COLUMNS = [
  { key: "id", label: "Model", type: "text", cell: (m) => m.id },
  { key: "score", label: "Score", type: "num", cell: (m) => combinedScore(m.aa_intelligence, m.bench2_score) },
  { key: "requests_per_5h", label: "req/5h", type: "num", cell: (m) => m.requests_per_5h },
  { key: "monthly_limit_usd", label: "$/month", type: "num", cell: (m) => m.monthly_limit_usd },
  { key: "aa_intelligence", label: "AA intel", type: "num", cell: (m) => m.aa_intelligence },
];

let sortState = { key: "aa_intelligence", dir: -1 };

function fmtCell(col, m) {
  const raw = col.cell(m);
  if (col.type === "text") return raw === null || raw === undefined ? NA : String(raw);
  switch (col.key) {
    case "monthly_limit_usd":
      return fmtUsd(raw, 0);
    case "score":
      return fmtNum(raw, 1);
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

    COLUMNS.forEach((col, idx) => {
      const td = document.createElement("td");
      td.textContent = fmtCell(col, m);
      if (col.type === "num") td.classList.add("num");
      if (idx === 0) {
        if (recommended.has(m.id)) {
          const badge = document.createElement("span");
          badge.className = "badge";
          badge.textContent = "recommended";
          td.append(" ", badge);
        }
        if (isFree(m)) {
          const tag = document.createElement("span");
          tag.className = "badge badge-free";
          tag.textContent = "free, excluded";
          tag.title =
            "Free model: limited-time availability, prone to instability/timeouts, no dedicated AA slug.";
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
  if (stand) stand.textContent = meta.stand_datum || NA;
  const plan = document.getElementById("plan-name");
  // meta.plan carries a parenthesised price; strip the parentheses for display.
  if (plan) {
    plan.textContent = String(meta.plan || "opencode-go")
      .replace(" (", ",")
      .replace(")", "");
  }
  const aav = document.getElementById("aa-version");
  if (aav) aav.textContent = meta.aa_index_version || NA;
}

// The data lists many deep links: opencode docs and models pages, and one AA
// page per model. The Sources line shows only the two canonical root domains.
const SOURCE_ROOTS = ["opencode.ai", "artificialanalysis.ai"];

function renderSources(meta) {
  const host = document.getElementById("sources-list");
  if (!host) return;
  host.textContent = "";
  const urls = Array.isArray(meta.quellen_urls) ? meta.quellen_urls : [];
  const seen = new Set();
  const roots = [];
  for (const raw of urls) {
    let hostname = "";
    try {
      hostname = new URL(raw).hostname.replace(/^www\./, "");
    } catch (err) {
      continue;
    }
    if (!SOURCE_ROOTS.includes(hostname) || seen.has(hostname)) continue;
    seen.add(hostname);
    roots.push(hostname);
  }
  for (const root of (roots.length ? roots : SOURCE_ROOTS)) {
    const url = "https://" + root;
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
  const label = btn.textContent;
  btn.addEventListener("click", async () => {
    const text = src.textContent.trim();
    try {
      await navigator.clipboard.writeText(text);
      btn.textContent = "Copied ✓";
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
        btn.textContent = "Copied ✓";
      } catch (e2) {
        btn.textContent = "Copy failed";
      }
      ta.remove();
    }
    setTimeout(() => (btn.textContent = label), 2000);
  });
}

/* ---------- bootstrap ---------- */

function showLoadError(message) {
  const host = document.getElementById("role-cards");
  if (!host) return;
  for (const card of host.querySelectorAll(".card[data-role]")) {
    card.classList.add("card-empty");
    const line = card.querySelector('[data-field="model"]');
    if (line) line.textContent = message;
  }
}

async function init() {
  wireCopy();
  let payload;
  try {
    const res = await fetch(DATA_URL, { cache: "no-store" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    payload = await res.json();
  } catch (err) {
    showLoadError("Data could not be loaded: " + err.message);
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

// Browser only. In node the file can be loaded to re-run the role logic.
if (typeof document !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
}
