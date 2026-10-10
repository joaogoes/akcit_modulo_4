"use strict";

const PHASE_LABELS = {
  requirements: "Requirements",
  fspec: "FSpec",
  dspec: "DSpec",
  code: "Code",
  tests: "Tests",
};
const INVALID_LABEL = "Inválido";
const OTHER_LABEL = "Outros";
const MAX_SLOTS = 8;

const $ = (id) => document.getElementById(id);
const state = {
  repos: [],
  selected: new Set(), // ids marcados no filtro
  known: new Set(), // ids já vistos, para marcar repositórios novos
  dashboard: null,
  slots: new Map(), // veredito -> posição de cor; fixa enquanto a página está aberta
  chart: null,
  table: false,
  busy: new Set(),
};

/* ---------- API ---------- */

async function api(method, url, body) {
  const response = await fetch(url, {
    method,
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (response.status === 204) return null;
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(errorMessage(data, response.status));
  return data;
}

function errorMessage(data, status) {
  const detail = data && data.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail.map((item) => String(item.msg).replace(/^Value error, /, "")).join(" ");
  }
  return `Erro ${status}.`;
}

/* ---------- Mensagens ---------- */

function toast(message, isError = false) {
  const el = document.createElement("div");
  el.className = "toast" + (isError ? " error" : "");
  el.textContent = message;
  $("toasts").append(el);
  setTimeout(() => el.remove(), isError ? 9000 : 5000);
}

/* ---------- Repositórios ---------- */

function formatDate(iso) {
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function statusText(repo) {
  if (!repo.last_collected_at) return { text: "Nunca coletado", cls: "" };
  const when = formatDate(repo.last_collected_at);
  if (repo.last_collection_status === "failed") {
    return { text: `✕ Última coleta falhou em ${when}`, cls: "status-failed" };
  }
  return { text: `✓ Coletado em ${when}`, cls: "status-ok" };
}

function renderRepos() {
  const list = $("repo-list");
  list.replaceChildren();
  $("repo-empty").hidden = state.repos.length > 0;

  for (const repo of state.repos) {
    const li = document.createElement("li");

    const check = document.createElement("input");
    check.type = "checkbox";
    check.checked = state.selected.has(repo.id);
    check.setAttribute("aria-label", `Exibir ${repo.full_name} no gráfico`);
    check.addEventListener("change", () => {
      if (check.checked) state.selected.add(repo.id);
      else state.selected.delete(repo.id);
      refreshDashboard();
    });

    const name = document.createElement("span");
    name.className = "repo-name";
    name.textContent = repo.full_name;

    const meta = document.createElement("span");
    meta.className = "repo-meta";
    const st = statusText(repo);
    const branch = repo.branch ? ` · branch ${repo.branch}` : "";
    meta.innerHTML = "";
    const stEl = document.createElement("span");
    stEl.className = st.cls;
    stEl.textContent = st.text;
    meta.append(stEl, document.createTextNode(branch));

    const actions = document.createElement("span");
    actions.className = "repo-actions";
    const collect = document.createElement("button");
    collect.type = "button";
    collect.textContent = state.busy.has(repo.id) ? "Coletando…" : "Coletar";
    collect.disabled = state.busy.size > 0;
    collect.addEventListener("click", () => collectRepos([repo.id]));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "danger";
    remove.textContent = "Remover";
    remove.addEventListener("click", () => removeRepo(repo));
    actions.append(collect, remove);

    li.append(check, name, meta, actions);
    list.append(li);
  }
  $("collect-all").disabled = state.busy.size > 0 || state.repos.length === 0;
}

async function loadRepos() {
  state.repos = await api("GET", "/repositories");
  for (const repo of state.repos) {
    if (!state.known.has(repo.id)) {
      state.known.add(repo.id);
      state.selected.add(repo.id);
    }
  }
  const ids = new Set(state.repos.map((repo) => repo.id));
  for (const id of [...state.selected]) if (!ids.has(id)) state.selected.delete(id);
  renderRepos();
}

async function addRepo(event) {
  event.preventDefault();
  const full_name = $("repo-name").value;
  const branch = $("repo-branch").value.trim() || null;
  try {
    const repo = await api("POST", "/repositories", { full_name, branch });
    $("repo-form").reset();
    toast(`Cadastrado: ${repo.full_name}. Use “Coletar” para ler os relatórios.`);
    await loadRepos();
    await refreshDashboard();
  } catch (error) {
    toast(error.message, true);
  }
}

async function removeRepo(repo) {
  if (!confirm(`Remover ${repo.full_name} e seus relatórios coletados?`)) return;
  try {
    await api("DELETE", `/repositories/${repo.id}`);
    toast(`Removido: ${repo.full_name}.`);
    await loadRepos();
    await refreshDashboard();
  } catch (error) {
    toast(error.message, true);
  }
}

async function collectRepos(ids) {
  const targets = ids || state.repos.map((repo) => repo.id);
  targets.forEach((id) => state.busy.add(id));
  renderRepos();
  try {
    const results = await api("POST", "/collections", ids ? { repository_ids: ids } : undefined);
    for (const result of results) {
      const repo = state.repos.find((item) => item.id === result.repository_id);
      const name = repo ? repo.full_name : `#${result.repository_id}`;
      if (result.status === "failed") {
        toast(`${name}: ${result.errors.map((e) => e.message).join(" ")}`, true);
      } else if (result.errors.length) {
        toast(`${name}: ${result.files_read} relatórios lidos, ${result.errors.length} com problema.`, true);
      } else {
        toast(`${name}: ${result.files_read} relatórios lidos.`);
      }
    }
  } catch (error) {
    toast(error.message, true);
  } finally {
    state.busy.clear();
    await loadRepos();
    await refreshDashboard();
  }
}

/* ---------- Dashboard ---------- */

async function refreshDashboard() {
  const params = new URLSearchParams();
  if (state.selected.size === 0) {
    state.dashboard = { phases: [], repository_ids: [], last_collected_at: null };
  } else {
    state.selected.forEach((id) => params.append("repository_ids", id));
    try {
      state.dashboard = await api("GET", `/api/dashboard?${params}`);
    } catch (error) {
      toast(error.message, true);
      return;
    }
  }
  renderDashboard();
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** Séries do gráfico: um veredito por série, com cor fixa pela ordem da primeira aparição. */
function buildSeries(dashboard) {
  const phases = dashboard.phases;
  const verdicts = new Map();
  for (const phase of phases) {
    for (const item of phase.verdicts) {
      if (item.verdict !== INVALID_LABEL && !verdicts.has(item.verdict)) verdicts.set(item.verdict, true);
    }
  }
  for (const verdict of [...verdicts.keys()].sort((a, b) => a.localeCompare(b, "pt-BR"))) {
    if (!state.slots.has(verdict)) state.slots.set(verdict, state.slots.size);
  }
  const named = [...verdicts.keys()].sort((a, b) => state.slots.get(a) - state.slots.get(b));
  const shown = named.slice(0, MAX_SLOTS);
  const folded = new Set(named.slice(MAX_SLOTS));

  const countOf = (phase, wanted) =>
    phase.verdicts.filter((item) => wanted(item.verdict)).reduce((sum, item) => sum + item.count, 0);

  const series = shown.map((verdict) => ({
    label: verdict,
    color: `--s${(state.slots.get(verdict) % MAX_SLOTS) + 1}`,
    data: phases.map((phase) => countOf(phase, (v) => v === verdict)),
  }));
  if (folded.size) {
    series.push({ label: OTHER_LABEL, color: "--other", data: phases.map((p) => countOf(p, (v) => folded.has(v))) });
  }
  const invalid = phases.map((phase) => countOf(phase, (v) => v === INVALID_LABEL));
  if (invalid.some((n) => n > 0)) series.push({ label: INVALID_LABEL, color: "--invalid", data: invalid });
  return series;
}

function renderDashboard() {
  const dashboard = state.dashboard;
  const series = buildSeries(dashboard);
  const total = dashboard.phases.reduce((sum, phase) => sum + phase.total, 0);

  $("dash-sub").textContent = dashboard.last_collected_at
    ? `Última coleta: ${formatDate(dashboard.last_collected_at)} · ${total} features`
    : "Sem coleta realizada.";
  $("dash-empty").hidden = total > 0;
  $("chart-wrap").hidden = total === 0 || state.table;
  $("table-wrap").hidden = total === 0 || !state.table;
  $("legend").hidden = total === 0;

  const legend = $("legend");
  legend.replaceChildren();
  for (const item of series) {
    const li = document.createElement("li");
    const swatch = document.createElement("span");
    swatch.className = "swatch";
    swatch.style.background = cssVar(item.color);
    li.append(swatch, document.createTextNode(item.label));
    legend.append(li);
  }

  if (total === 0) {
    if (state.chart) state.chart.destroy();
    state.chart = null;
    return;
  }
  renderTable(dashboard, series);
  if (!state.table) renderChart(dashboard, series);
}

function renderTable(dashboard, series) {
  const table = document.createElement("table");
  const head = table.createTHead().insertRow();
  for (const text of ["Fase", ...series.map((s) => s.label), "Total"]) {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = text;
    head.append(th);
  }
  const body = table.createTBody();
  dashboard.phases.forEach((phase, index) => {
    const row = body.insertRow();
    const th = document.createElement("th");
    th.scope = "row";
    th.textContent = PHASE_LABELS[phase.phase];
    row.append(th);
    for (const s of series) row.insertCell().textContent = s.data[index];
    row.insertCell().textContent = phase.total;
  });
  $("table-wrap").replaceChildren(table);
}

function luminance(hex) {
  const n = parseInt(hex.replace("#", ""), 16);
  const channel = (v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel((n >> 16) & 255) + 0.7152 * channel((n >> 8) & 255) + 0.0722 * channel(n & 255);
}

/** Valor dentro do segmento, somente quando o texto cabe com folga. */
const segmentLabels = {
  id: "segmentLabels",
  afterDatasetsDraw(chart) {
    const { ctx } = chart;
    ctx.save();
    ctx.font = "600 12px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    chart.data.datasets.forEach((dataset, i) => {
      chart.getDatasetMeta(i).data.forEach((bar, j) => {
        const value = dataset.data[j];
        if (!value) return;
        const text = String(value);
        if (bar.width < ctx.measureText(text).width + 16) return;
        ctx.fillStyle = luminance(dataset.backgroundColor) > 0.35 ? "#0b0b0b" : "#ffffff";
        ctx.fillText(text, bar.x - bar.width / 2, bar.y);
      });
    });
    ctx.restore();
  },
};

function renderChart(dashboard, series) {
  const surface = cssVar("--surface");
  const config = {
    type: "bar",
    plugins: [segmentLabels],
    data: {
      labels: dashboard.phases.map((phase) => PHASE_LABELS[phase.phase]),
      datasets: series.map((item) => ({
        label: item.label,
        data: item.data,
        backgroundColor: cssVar(item.color),
        borderColor: surface,
        borderWidth: 2,
        borderRadius: 4,
        borderSkipped: false,
        maxBarThickness: 24,
      })),
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      scales: {
        x: {
          stacked: true,
          beginAtZero: true,
          ticks: { precision: 0, color: cssVar("--muted") },
          grid: { color: cssVar("--grid") },
          border: { color: cssVar("--axis") },
          title: { display: true, text: "Features", color: cssVar("--text-2") },
        },
        y: {
          stacked: true,
          reverse: false,
          ticks: { color: cssVar("--text-2") },
          grid: { display: false },
          border: { color: cssVar("--axis") },
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.x}`,
            footer: (items) => `Total: ${items.reduce((sum, item) => sum + item.parsed.x, 0)}`,
          },
        },
      },
    },
  };
  if (state.chart) state.chart.destroy();
  state.chart = new Chart($("chart"), config);
}

function toggleTable() {
  state.table = !state.table;
  $("toggle-table").setAttribute("aria-pressed", String(state.table));
  $("toggle-table").textContent = state.table ? "Ver como gráfico" : "Ver como tabela";
  if (state.dashboard) renderDashboard();
}

/* ---------- Inicialização ---------- */

$("repo-form").addEventListener("submit", addRepo);
$("collect-all").addEventListener("click", () => collectRepos(null));
$("toggle-table").addEventListener("click", toggleTable);
window
  .matchMedia("(prefers-color-scheme: dark)")
  .addEventListener("change", () => state.dashboard && renderDashboard());

(async () => {
  try {
    await loadRepos();
    await refreshDashboard();
  } catch (error) {
    toast(error.message, true);
  }
})();
