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
// Vereditos conhecidos usam cores com sentido (azul, âmbar, vermelho); os demais seguem a ordem da paleta.
const PREFERRED_SLOTS = new Map([["aprovado", 0], ["aprovado com ressalvas", 3], ["reprovado", 7]]);

const $ = (id) => document.getElementById(id);
const state = {
  repos: [],
  dashboards: new Map(), // id do repositório -> resposta de /api/dashboard
  slots: new Map(), // veredito -> posição de cor; fixa enquanto a página está aberta
  charts: new Map(), // id do repositório -> instância do Chart.js
  mode: "chart", // chart | table | trend
  trendPhase: "tests",
  trends: new Map(), // id do repositório -> resposta de /api/trend
  busy: new Set(),
  tokenSettings: null, // resposta de /settings/tokens; nunca contém os valores dos tokens
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

/* ---------- Utilitários ---------- */

const PROVIDER_LABELS = { github: "GitHub", azure_devops: "Azure DevOps" };

function providerLabel(repo) {
  return PROVIDER_LABELS[repo.provider] || repo.provider;
}

function repoLabel(repo) {
  return repo.branch ? `${repo.full_name} @ ${repo.branch}` : repo.full_name;
}

function formatDate(iso) {
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function statusText(repo) {
  if (!repo.last_collected_at) return { text: "Nunca coletado", cls: "" };
  const when = formatDate(repo.last_collected_at);
  if (repo.last_collection_status === "failed") {
    return { text: `✕ Última coleta falhou em ${when}`, cls: "status-failed" };
  }
  const commit = repo.last_commit_sha ? ` · commit ${repo.last_commit_sha.slice(0, 7)}` : "";
  return { text: `✓ Coletado em ${when}${commit}`, cls: "status-ok" };
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/* ---------- Diálogo de repositórios (engrenagem) ---------- */

const dialog = $("settings");

function openSettings() {
  dialog.append($("toasts")); // o diálogo cobre a página; as mensagens precisam ficar acima dele
  dialog.showModal();
  $("repo-name").focus();
  loadTokens().catch((error) => toast(error.message, true));
}

dialog.addEventListener("close", () => document.body.append($("toasts")));
dialog.addEventListener("click", (event) => {
  if (event.target === dialog) dialog.close(); // clique no fundo
});

function renderRepoList() {
  const list = $("repo-list");
  list.replaceChildren();
  $("repo-empty").hidden = state.repos.length > 0;

  for (const repo of state.repos) {
    const li = document.createElement("li");

    const name = document.createElement("span");
    name.className = "repo-name";
    name.textContent = repoLabel(repo);

    const meta = document.createElement("span");
    meta.className = "repo-meta";
    const status = statusText(repo);
    const statusEl = document.createElement("span");
    statusEl.className = status.cls;
    statusEl.textContent = status.text;
    meta.append(`${providerLabel(repo)} · `, statusEl);

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
    remove.disabled = state.busy.size > 0;
    remove.addEventListener("click", () => removeRepo(repo));
    actions.append(collect, remove);

    li.append(name, meta, actions);
    list.append(li);
  }
  $("collect-all").disabled = state.busy.size > 0 || state.repos.length === 0;
}

/* ---------- Tokens de acesso ---------- */

async function loadTokens() {
  state.tokenSettings = await api("GET", "/settings/tokens");
  renderTokens();
}

function tokenStatusText(token) {
  if (token.source === "database") return `Salvo no banco, em ${formatDate(token.updated_at)}`;
  if (token.source === "environment") return "Definido por variável de ambiente";
  return "Não configurado";
}

function renderTokens() {
  const { secure_storage, tokens } = state.tokenSettings;
  $("tokens-note").textContent = secure_storage
    ? "O token é cifrado com o DPAPI do Windows e só pode ser lido por este usuário, nesta máquina. Depois de salvo, não é exibido de novo."
    : "O armazenamento protegido só existe no Windows. Neste sistema, use as variáveis de ambiente GITHUB_TOKEN e AZURE_DEVOPS_TOKEN.";

  const list = $("token-list");
  list.replaceChildren();
  for (const token of tokens) {
    const li = document.createElement("li");

    const head = document.createElement("div");
    head.className = "token-head";
    const name = document.createElement("strong");
    name.textContent = token.label;
    const status = document.createElement("span");
    status.className = token.configured ? "status-ok" : "muted";
    status.textContent = tokenStatusText(token);
    head.append(name, status);

    const form = document.createElement("form");
    form.className = "token-form";
    form.autocomplete = "off";
    const input = document.createElement("input");
    input.type = "password";
    input.autocomplete = "new-password";
    input.placeholder = token.configured ? "Colar um novo token para substituir" : "Colar o token";
    input.disabled = !secure_storage;
    input.setAttribute("aria-label", `Token de acesso do ${token.label}`);
    const save = document.createElement("button");
    save.type = "submit";
    save.className = "primary";
    save.textContent = "Salvar";
    save.disabled = !secure_storage;
    form.append(input, save);
    if (token.source === "database") {
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "danger";
      remove.textContent = "Remover";
      remove.addEventListener("click", () => removeToken(token));
      form.append(remove);
    }
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      saveToken(token, input);
    });

    li.append(head, form);
    list.append(li);
  }
}

async function saveToken(token, input) {
  const value = input.value;
  if (!value.trim()) {
    toast(`Cole o token do ${token.label} antes de salvar.`, true);
    return;
  }
  try {
    await api("PUT", `/settings/tokens/${token.provider}`, { token: value });
    input.value = ""; // o valor não fica na página
    toast(`Token do ${token.label} salvo. Já vale para as próximas coletas.`);
    await loadTokens();
  } catch (error) {
    toast(error.message, true);
  }
}

async function removeToken(token) {
  if (!confirm(`Remover o token do ${token.label} salvo no banco?`)) return;
  try {
    await api("DELETE", `/settings/tokens/${token.provider}`);
    toast(`Token do ${token.label} removido.`);
    await loadTokens();
  } catch (error) {
    toast(error.message, true);
  }
}

async function addRepo(event) {
  event.preventDefault();
  const full_name = $("repo-name").value;
  const branch = $("repo-branch").value.trim() || null;
  try {
    const repo = await api("POST", "/repositories", { full_name, branch });
    $("repo-form").reset();
    toast(`Cadastrado: ${repoLabel(repo)}. Use “Coletar” para ler os relatórios.`);
    await refreshAll();
  } catch (error) {
    toast(error.message, true);
  }
}

async function removeRepo(repo) {
  if (!confirm(`Remover ${repoLabel(repo)} e seus relatórios coletados?`)) return;
  try {
    await api("DELETE", `/repositories/${repo.id}`);
    toast(`Removido: ${repoLabel(repo)}.`);
    await refreshAll();
  } catch (error) {
    toast(error.message, true);
  }
}

/** Coleta os repositórios; com `onlyIfChanged`, só os que têm commit novo. */
async function collectRepos(ids, onlyIfChanged = false) {
  const targets = ids || state.repos.map((repo) => repo.id);
  targets.forEach((id) => state.busy.add(id));
  renderRepoList();
  renderPage();
  try {
    const body = ids || onlyIfChanged ? { repository_ids: ids, only_if_changed: onlyIfChanged } : undefined;
    const results = await api("POST", "/collections", body);
    for (const result of results) {
      const repo = state.repos.find((item) => item.id === result.repository_id);
      const name = repo ? repoLabel(repo) : `#${result.repository_id}`;
      if (result.status === "unchanged") {
        toast(`${name}: sem novos commits desde a última coleta.`);
      } else if (result.status === "failed") {
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
    await refreshAll();
  }
}

/* ---------- Dados ---------- */

async function refreshAll() {
  state.repos = await api("GET", "/repositories");
  const entries = await Promise.all(
    state.repos.map(async (repo) => [repo.id, await api("GET", `/api/dashboard?repository_ids=${repo.id}`)])
  );
  state.dashboards = new Map(entries);
  if (state.mode === "trend") await loadTrends();
  renderRepoList();
  renderPage();
}

/** Carrega a tendência de cada repositório, todas com o mesmo eixo de datas. */
async function loadTrends() {
  const phase = `phase=${state.trendPhase}`;
  const all = await api("GET", `/api/trend?${phase}`); // todos os repositórios: dá o intervalo comum
  const range = all.dates.length ? `&start=${all.dates[0]}&end=${all.dates[all.dates.length - 1]}` : "";
  const entries = await Promise.all(
    state.repos.map(async (repo) => [
      repo.id,
      await api("GET", `/api/trend?repository_ids=${repo.id}&${phase}${range}`),
    ])
  );
  state.trends = new Map(entries);
}

/* ---------- Séries ---------- */

const RESERVED_SLOTS = new Set(PREFERRED_SLOTS.values());

/** Posição de cor de um veredito: fixa depois de atribuída, para a cor não mudar com a lista. */
function ensureSlot(verdict) {
  if (state.slots.has(verdict)) return state.slots.get(verdict);
  let slot = PREFERRED_SLOTS.get(verdict.trim().toLowerCase());
  if (slot === undefined) {
    const used = new Set(state.slots.values());
    slot = 0;
    while (slot < MAX_SLOTS && (used.has(slot) || RESERVED_SLOTS.has(slot))) slot++;
    if (slot >= MAX_SLOTS) slot = state.slots.size;
  }
  state.slots.set(verdict, slot);
  return slot;
}

function assignSlots() {
  const found = new Set();
  for (const dashboard of state.dashboards.values()) {
    for (const phase of dashboard.phases) {
      for (const item of phase.verdicts) if (item.verdict !== INVALID_LABEL) found.add(item.verdict);
    }
  }
  for (const verdict of [...found].sort((a, b) => a.localeCompare(b, "pt-BR"))) ensureSlot(verdict);
  return [...found].sort((a, b) => state.slots.get(a) - state.slots.get(b));
}

function colorOf(verdict) {
  if (verdict === INVALID_LABEL) return "--invalid";
  if (verdict === OTHER_LABEL) return "--other";
  return `--s${(ensureSlot(verdict) % MAX_SLOTS) + 1}`;
}

/** Séries de um gráfico: um veredito por série, com os vereditos além do oitavo agrupados em "Outros". */
function buildSeries(dashboard, ordered) {
  const shown = ordered.slice(0, MAX_SLOTS);
  const folded = new Set(ordered.slice(MAX_SLOTS));
  const countOf = (phase, wanted) =>
    phase.verdicts.filter((item) => wanted(item.verdict)).reduce((sum, item) => sum + item.count, 0);

  const series = shown.map((verdict) => ({
    label: verdict,
    data: dashboard.phases.map((phase) => countOf(phase, (v) => v === verdict)),
  }));
  if (folded.size) {
    series.push({ label: OTHER_LABEL, data: dashboard.phases.map((p) => countOf(p, (v) => folded.has(v))) });
  }
  series.push({ label: INVALID_LABEL, data: dashboard.phases.map((p) => countOf(p, (v) => v === INVALID_LABEL)) });
  return series.filter((item) => item.data.some((n) => n > 0));
}

/* ---------- Página ---------- */

function renderLegend(ordered) {
  const legend = $("legend");
  legend.replaceChildren();
  const labels = ordered.slice(0, MAX_SLOTS);
  if (ordered.length > MAX_SLOTS) labels.push(OTHER_LABEL);
  const anyInvalid = [...state.dashboards.values()].some((d) =>
    d.phases.some((p) => p.verdicts.some((v) => v.verdict === INVALID_LABEL))
  );
  if (anyInvalid) labels.push(INVALID_LABEL);
  for (const label of labels) {
    const li = document.createElement("li");
    const swatch = document.createElement("span");
    swatch.className = "swatch";
    swatch.style.background = cssVar(colorOf(label));
    li.append(swatch, document.createTextNode(label));
    legend.append(li);
  }
  legend.hidden = labels.length === 0;
}

function renderPage() {
  for (const chart of state.charts.values()) chart.destroy();
  state.charts.clear();

  const ordered = assignSlots();
  renderLegend(ordered);

  $("empty").hidden = state.repos.length > 0;
  const container = $("charts");
  container.replaceChildren();
  for (const repo of state.repos) {
    container.append(renderCard(repo, state.dashboards.get(repo.id), ordered));
  }
}

function renderCard(repo, dashboard, ordered) {
  const card = document.createElement("section");
  card.className = "card chart-card";
  card.setAttribute("aria-labelledby", `title-${repo.id}`);

  const head = document.createElement("div");
  head.className = "card-head";
  const titles = document.createElement("div");
  const title = document.createElement("h2");
  title.id = `title-${repo.id}`;
  title.textContent = repoLabel(repo);
  const status = statusText(repo);
  const statusEl = document.createElement("p");
  statusEl.className = `status ${status.cls}`;
  statusEl.textContent = status.text;
  titles.append(title, statusEl);

  const refresh = document.createElement("button");
  refresh.type = "button";
  refresh.className = "refresh";
  const working = state.busy.has(repo.id);
  refresh.textContent = working ? "Atualizando…" : "Atualizar";
  refresh.disabled = state.busy.size > 0;
  refresh.title = "Coleta novos dados se houver um commit mais recente";
  refresh.setAttribute("aria-label", `Atualizar ${repoLabel(repo)}`);
  refresh.addEventListener("click", () => collectRepos([repo.id], true));
  head.append(titles, refresh);
  card.append(head);

  const total = dashboard.phases.reduce((sum, phase) => sum + phase.total, 0);
  if (total === 0) {
    const empty = document.createElement("div");
    empty.className = "chart-empty";
    empty.textContent = "Nenhum relatório coletado. Use “Atualizar” para coletar.";
    card.append(empty);
    return card;
  }

  const series = buildSeries(dashboard, ordered);
  if (state.mode === "table") {
    card.append(buildTable(dashboard, series));
  } else if (state.mode === "trend") {
    card.append(buildTrendView(repo));
  } else {
    const wrap = document.createElement("div");
    wrap.className = "chart-wrap";
    const canvas = document.createElement("canvas");
    canvas.setAttribute("role", "img");
    canvas.setAttribute(
      "aria-label",
      `Gráfico de barras empilhadas horizontais de ${repoLabel(repo)}: features por fase e veredito`
    );
    wrap.append(canvas);
    card.append(wrap);
    state.charts.set(repo.id, buildChart(canvas, dashboard, series));
  }
  return card;
}

function buildTable(dashboard, series) {
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
  return table;
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

function buildChart(canvas, dashboard, series) {
  return new Chart(canvas, {
    type: "bar",
    plugins: [segmentLabels],
    data: {
      labels: dashboard.phases.map((phase) => PHASE_LABELS[phase.phase]),
      datasets: series.map((item) => ({
        label: item.label,
        data: item.data,
        backgroundColor: cssVar(colorOf(item.label)),
        borderColor: cssVar("--surface"),
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
  });
}

function withAlpha(hex, alpha) {
  const n = parseInt(hex.replace("#", ""), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

function buildTrendView(repo) {
  const trend = state.trends.get(repo.id);
  if (!trend || trend.dates.length === 0) {
    const empty = document.createElement("div");
    empty.className = "chart-empty";
    empty.textContent = `Nenhum relatório datado de ${PHASE_LABELS[state.trendPhase]} para exibir a tendência.`;
    return empty;
  }
  const wrap = document.createElement("div");
  wrap.className = "chart-wrap";
  const canvas = document.createElement("canvas");
  canvas.setAttribute("role", "img");
  canvas.setAttribute(
    "aria-label",
    `Gráfico de linhas empilhadas de ${repoLabel(repo)}: evolução das features de ${PHASE_LABELS[state.trendPhase]} por veredito`
  );
  wrap.append(canvas);
  state.charts.set(repo.id, buildTrendChart(canvas, trend));
  return wrap;
}

const shortDate = (iso) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });

function buildTrendChart(canvas, trend) {
  const tickStep = Math.max(1, Math.ceil(trend.dates.length / 8));
  const series = [...trend.series].sort((a, b) => ensureSlot(a.verdict) - ensureSlot(b.verdict));
  return new Chart(canvas, {
    type: "line",
    data: {
      labels: trend.dates.map(shortDate),
      datasets: series.map((item, index) => {
        const color = cssVar(colorOf(item.verdict));
        return {
          label: item.verdict,
          data: item.counts,
          fill: index === 0 ? "origin" : "-1", // cada faixa vai até a linha de baixo, sem sobreposição
          borderColor: color,
          backgroundColor: withAlpha(color, 0.35),
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 4,
          pointHoverBackgroundColor: color,
          pointHoverBorderColor: cssVar("--surface"),
          pointHoverBorderWidth: 2,
          tension: 0.2,
        };
      }),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: {
          // Rótulos escolhidos pelo número de pontos, não pela largura: todos os gráficos mostram as mesmas datas.
          ticks: {
            autoSkip: false,
            maxRotation: 0,
            color: cssVar("--muted"),
            callback: (_, index) => (index % tickStep === 0 ? shortDate(trend.dates[index]) : ""),
          },
          grid: { display: false },
          border: { color: cssVar("--axis") },
        },
        y: {
          stacked: true,
          beginAtZero: true,
          ticks: { precision: 0, color: cssVar("--muted") },
          grid: { color: cssVar("--grid") },
          border: { color: cssVar("--axis") },
          title: { display: true, text: "Features", color: cssVar("--text-2") },
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: (items) =>
              new Date(`${trend.dates[items[0].dataIndex]}T00:00:00`).toLocaleDateString("pt-BR"),
            label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y}`,
            footer: (items) => `Total: ${items.reduce((sum, item) => sum + item.parsed.y, 0)}`,
          },
        },
      },
    },
  });
}

async function setMode(mode) {
  state.mode = mode;
  for (const button of document.querySelectorAll("#view-modes button")) {
    button.setAttribute("aria-pressed", String(button.dataset.mode === mode));
  }
  $("trend-controls").hidden = mode !== "trend";
  if (mode === "trend") {
    try {
      await loadTrends();
    } catch (error) {
      toast(error.message, true);
    }
  }
  renderPage();
}

async function changeTrendPhase(event) {
  state.trendPhase = event.target.value;
  try {
    await loadTrends();
  } catch (error) {
    toast(error.message, true);
  }
  renderPage();
}

/* ---------- Tema ---------- */

const ICON_ATTRS = 'viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" ' +
  'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"';
const SUN = `<svg ${ICON_ATTRS}><circle cx="12" cy="12" r="5"></circle><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"></path></svg>`;
const MOON = `<svg ${ICON_ATTRS}><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>`;
const systemDark = window.matchMedia("(prefers-color-scheme: dark)");

function effectiveTheme() {
  return document.documentElement.dataset.theme || (systemDark.matches ? "dark" : "light");
}

function updateThemeButton() {
  const dark = effectiveTheme() === "dark";
  const button = $("theme-toggle");
  button.innerHTML = dark ? SUN : MOON; // o ícone mostra o tema para o qual a troca leva
  const label = dark ? "Usar tema claro" : "Usar tema escuro";
  button.setAttribute("aria-label", label);
  button.title = label;
}

function applyThemeChange() {
  updateThemeButton();
  if (state.repos.length) renderPage(); // os gráficos leem as cores ao serem criados
}

function toggleTheme() {
  const next = effectiveTheme() === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  try {
    localStorage.setItem("theme", next);
  } catch (error) {
    // sem armazenamento: a escolha vale só até recarregar a página
  }
  applyThemeChange();
}

/* ---------- Inicialização ---------- */

$("open-settings").addEventListener("click", openSettings);
$("close-settings").addEventListener("click", () => dialog.close());
$("repo-form").addEventListener("submit", addRepo);
$("collect-all").addEventListener("click", () => collectRepos(null));
document.querySelectorAll("#view-modes button").forEach((button) =>
  button.addEventListener("click", () => setMode(button.dataset.mode))
);
$("trend-phase").addEventListener("change", changeTrendPhase);
$("theme-toggle").addEventListener("click", toggleTheme);
systemDark.addEventListener("change", applyThemeChange);
updateThemeButton();

refreshAll().catch((error) => toast(error.message, true));
