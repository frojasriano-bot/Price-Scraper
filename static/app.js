/**
 * Blue Rental Intelligence - Dashboard Application
 * All API calls, chart rendering, and UI logic.
 */

'use strict';

// ── Helpers ────────────────────────────────────────────────────────────────
/** Update every element sharing a given ID (the HTML has duplicates in top-bar + tab). */
function setSourceBadge(id, source) {
  document.querySelectorAll(`#${id}`).forEach(el => {
    el.textContent = source === 'live' || source === 'database' ? 'Live Data' : 'Mock Data';
    el.className = `badge ${source === 'live' || source === 'database' ? 'badge-green' : 'badge-gray'}`;
  });
}

// ── Theme ──────────────────────────────────────────────────────────────────
function toggleTheme() {
  const isDark = document.body.classList.toggle('dark-mode');
  document.getElementById('theme-icon').textContent = isDark ? '☀️' : '🌙';
  localStorage.setItem('theme', isDark ? 'dark' : 'light');
}

(function applyStoredTheme() {
  if (localStorage.getItem('theme') === 'dark') {
    document.body.classList.add('dark-mode');
    const icon = document.getElementById('theme-icon');
    if (icon) icon.textContent = '☀️';
  }
})();

// ── State ──────────────────────────────────────────────────────────────────
const state = {
  currentTab: 'rates',
  ratesView: 'list',  // 'list' | 'matrix' | 'history'
  rates: [],
  ratesSource: 'mock',
  ratesHistory: [],
  matrix: null,
  matrixSource: 'mock',
  historyData: null,
  historyCharts: {},
  historySource: 'mock',
  historyCategory: '',
  historyModelSearch: '',
  historyCoverage: null,
  ratesSort: { col: null, dir: 'asc' },
  seasonalData: null,
  seasonalChart: null,
  deltas: {},
  deltasAvailable: false,
  rankings: [],
  rankingsSource: 'mock',
  rankingsHistory: [],
  seoKeywords: [],
  seoSort: { col: 'rank', dir: 'asc' },
  seoChartFilter: 'all',
  settings: {},
  locations: [],
  mappings: [],
  rateChart: null,
  seoChart: null,
  scraping: false,
  checkingSeo: false,
  savingSettings: false,
};

// ── API helpers ────────────────────────────────────────────────────────────
const API_BASE = '';

async function apiFetch(path, options = {}) {
  const res = await fetch(API_BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

// ── Toast notifications ────────────────────────────────────────────────────
function showToast(message, type = 'info', duration = 3500) {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    toast.style.transition = 'all .3s';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// ── Navigation ─────────────────────────────────────────────────────────────
function switchTab(tab) {
  state.currentTab = tab;

  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.tab === tab);
  });
  document.querySelectorAll('.tab-panel').forEach(el => {
    el.style.display = el.id === `tab-${tab}` ? 'block' : 'none';
  });

  const titles = {
    rates: 'Rate Intelligence',
    seo: 'SEO Rank Tracker',
    settings: 'Settings',
  };
  document.getElementById('page-title').textContent = titles[tab] || tab;

  if (tab === 'rates') loadRates();
  if (tab === 'seo') loadRankings();
  if (tab === 'settings') loadSettings();
}

// ── Utility ────────────────────────────────────────────────────────────────
function formatISK(amount) {
  return new Intl.NumberFormat('is-IS', {
    style: 'currency',
    currency: 'ISK',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

function formatDate(isoStr) {
  if (!isoStr) return '—';
  const d = new Date(isoStr.includes('T') ? isoStr : isoStr + 'T00:00:00');
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

function timeAgo(isoStr) {
  if (!isoStr) return '—';
  const diff = Date.now() - new Date(isoStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function defaultPickup() {
  const d = new Date();
  d.setDate(d.getDate() + 7);
  return d.toISOString().slice(0, 10);
}

function defaultReturn() {
  const d = new Date();
  d.setDate(d.getDate() + 10);
  return d.toISOString().slice(0, 10);
}

// ── VIEW TOGGLE ────────────────────────────────────────────────────────────
function setRatesView(view) {
  state.ratesView = view;
  document.getElementById('view-list').style.display     = view === 'list'     ? '' : 'none';
  document.getElementById('view-matrix').style.display   = view === 'matrix'   ? '' : 'none';
  document.getElementById('view-history').style.display  = view === 'history'  ? '' : 'none';
  document.getElementById('view-seasonal').style.display = view === 'seasonal' ? '' : 'none';
  document.getElementById('btn-list-view').classList.toggle('active',     view === 'list');
  document.getElementById('btn-matrix-view').classList.toggle('active',   view === 'matrix');
  document.getElementById('btn-history-view').classList.toggle('active',  view === 'history');
  document.getElementById('btn-seasonal-view').classList.toggle('active', view === 'seasonal');
  if (view === 'matrix'   && !state.matrix)       loadMatrix();
  if (view === 'history')                         loadHistory();
  if (view === 'seasonal' && !state.seasonalData) loadSeasonal();
}

// ── SCHEDULER STATUS ───────────────────────────────────────────────────────
async function loadSchedulerStatus() {
  try {
    const data = await apiFetch('/api/scheduler/status');
    const dot      = document.getElementById('scheduler-dot');
    const schedEl  = document.getElementById('scheduler-schedule');
    const nextEl   = document.getElementById('scheduler-next');
    const lastEl   = document.getElementById('scheduler-last');

    if (dot) dot.style.background = data.is_running ? '#22c55e' : '#ef4444';
    if (schedEl) schedEl.textContent = data.schedule || '—';

    if (nextEl) {
      if (data.next_run) {
        const d = new Date(data.next_run);
        nextEl.textContent = d.toLocaleString('en-GB', {
          month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
        });
      } else {
        nextEl.textContent = '—';
      }
    }

    if (lastEl) {
      lastEl.textContent = data.last_scrape_at ? timeAgo(data.last_scrape_at) : 'Never';
    }
  } catch (_) {
    // Silently ignore — not critical
  }
}

// ── PRICE HISTORY VIEW ─────────────────────────────────────────────────────
const MODEL_COLORS = [
  '#3b82f6','#ef4444','#22c55e','#f59e0b','#8b5cf6',
  '#06b6d4','#f97316','#ec4899','#10b981','#eab308',
  '#6366f1','#14b8a6','#f43f5e','#a855f7','#84cc16',
  '#0ea5e9','#fb923c','#e879f9','#34d399','#fbbf24',
  '#818cf8','#2dd4bf','#fb7185','#c084fc','#a3e635',
];

const CATEGORY_ICONS = {
  'Economy': '🚗', 'Compact': '🚙', 'SUV': '🛻', '4x4': '🏔️', 'Minivan': '🚐',
};

async function loadHistory() {
  const location   = document.getElementById('filter-location').value;
  const competitor = document.getElementById('history-competitor').value;
  const days       = document.getElementById('history-days').value;

  const params = new URLSearchParams({ days });
  if (location)   params.set('location',   location);
  if (competitor) params.set('competitor', competitor);

  // Coverage doesn't filter by competitor — we want all companies even when
  // the chart is scoped to one, so the grid stays fully populated.
  const coverageParams = new URLSearchParams({ days });
  if (location) coverageParams.set('location', location);

  try {
    const [result, coverageResult] = await Promise.all([
      apiFetch(`/api/rates/history/models?${params}`),
      apiFetch(`/api/rates/history/coverage?${coverageParams}`).catch(() => null),
    ]);
    state.historyData     = result.data       || {};
    state.historySource   = result.source     || 'mock';
    state.historyCoverage = coverageResult?.coverage || null;
    setSourceBadge('history-source-badge', state.historySource);
    renderHistoryCharts();
  } catch (e) {
    showToast(`Failed to load price history: ${e.message}`, 'error');
  }
}

// ── HISTORY FILTER HANDLERS ────────────────────────────────────────────────
function setHistoryCategory(cat) {
  state.historyCategory = cat;
  // Update pill button active state
  ['', 'Economy', 'Compact', 'SUV', '4x4', 'Minivan'].forEach(c => {
    const btn = document.getElementById(`hcat-btn-${c}`);
    if (btn) btn.classList.toggle('active', c === cat);
  });
  renderHistoryCharts();
}

function filterHistoryModels(query) {
  state.historyModelSearch = query.trim().toLowerCase();
  renderHistoryCharts();
}

function toggleCoverageGrid(cat, btn) {
  const grid = document.getElementById(`coverage-${cat}`);
  if (!grid) return;
  const isHidden = grid.style.display === 'none';
  grid.style.display = isHidden ? 'block' : 'none';
  btn.textContent = isHidden ? '🏢 Hide coverage' : '🏢 Show coverage';
}

function renderHistoryCharts() {
  // Destroy previous charts
  Object.values(state.historyCharts).forEach(c => c.destroy());
  state.historyCharts = {};

  const container = document.getElementById('history-charts');
  if (!container) return;
  container.innerHTML = '';

  const CATEGORY_ORDER = ['Economy', 'Compact', 'SUV', '4x4', 'Minivan'];
  const data = state.historyData || {};
  const modelSearch = state.historyModelSearch || '';

  // Apply category filter
  let categories = CATEGORY_ORDER.filter(c => data[c] && Object.keys(data[c]).length > 0);
  if (state.historyCategory) {
    categories = categories.filter(c => c === state.historyCategory);
  }

  if (categories.length === 0) {
    container.innerHTML = '<p style="padding:40px;text-align:center;color:#6b7280">No history data available.</p>';
    return;
  }

  categories.forEach(cat => {
    const allModels = data[cat];

    // Apply model search filter
    const models = modelSearch
      ? Object.fromEntries(
          Object.entries(allModels).filter(([name]) =>
            name.toLowerCase().includes(modelSearch)
          )
        )
      : allModels;

    if (Object.keys(models).length === 0) return; // nothing matches — skip card

    // Collect all unique dates across models
    const dateSet = new Set();
    Object.values(models).forEach(series => series.forEach(pt => dateSet.add(pt.date)));
    const allDates = Array.from(dateSet).sort();

    const colorIdx = { i: 0 };
    const datasets = Object.entries(models).map(([modelName, series]) => {
      const color = MODEL_COLORS[colorIdx.i % MODEL_COLORS.length];
      colorIdx.i++;
      const byDate = {};
      series.forEach(pt => { byDate[pt.date] = pt.avg_price; });
      return {
        label: modelName,
        data: allDates.map(d => byDate[d] ?? null),
        borderColor: color,
        backgroundColor: color + '22',
        borderWidth: 2,
        pointRadius: allDates.length <= 14 ? 3 : 1,
        tension: 0.3,
        spanGaps: true,
        fill: false,
      };
    });

    // Card wrapper
    const card = document.createElement('div');
    card.className = 'history-category-card';

    const icon = CATEGORY_ICONS[cat] || '🚗';
    const totalModels = Object.keys(allModels).length;
    const shownModels = Object.keys(models).length;
    const countLabel = shownModels < totalModels
      ? `${shownModels} of ${totalModels} models`
      : `${totalModels} models`;

    // Build coverage grid HTML (model × competitor)
    const coverageCat   = state.historyCoverage?.[cat] || {};
    const covModelNames = Object.keys(models); // respect current model search
    const allComps = [...new Set(Object.values(coverageCat).flat())].sort();
    let coverageHtml = '';
    if (allComps.length > 0 && covModelNames.length > 0) {
      const headerCells = allComps
        .map(c => `<th style="font-size:10px;font-weight:600;color:#9ca3af;padding:4px 8px;white-space:nowrap;text-align:center">${c}</th>`)
        .join('');
      const rows = covModelNames.map(m => {
        const compSet = new Set(coverageCat[m] || []);
        const cells = allComps.map(c =>
          `<td style="text-align:center;padding:3px 8px">${
            compSet.has(c)
              ? '<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#22c55e" title="' + c + '"></span>'
              : '<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:rgba(255,255,255,0.1)"></span>'
          }</td>`
        ).join('');
        return `<tr><td style="font-size:11px;color:#d1d5db;padding:3px 8px;white-space:nowrap;max-width:220px;overflow:hidden;text-overflow:ellipsis" title="${m}">${m}</td>${cells}</tr>`;
      }).join('');
      coverageHtml = `
        <div id="coverage-${cat}" style="display:none;margin-top:16px;overflow-x:auto">
          <table style="width:100%;border-collapse:collapse;font-size:12px">
            <thead>
              <tr style="border-bottom:1px solid rgba(255,255,255,0.08)">
                <th style="font-size:10px;font-weight:600;color:#9ca3af;padding:4px 8px;text-align:left">Model</th>
                ${headerCells}
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>`;
    }

    const toggleId = `coverage-${CSS.escape(cat)}`;
    card.innerHTML = `
      <div class="card-header" style="margin-bottom:12px">
        <div>
          <div class="card-title">${icon} ${cat}</div>
          <div class="card-subtitle" style="font-size:12px">${countLabel}</div>
        </div>
        ${allComps.length > 0 ? `<button class="btn btn-secondary btn-sm" onclick="toggleCoverageGrid('${cat}', this)" style="font-size:11px;padding:3px 10px">🏢 Show coverage</button>` : ''}
      </div>
      <div class="history-chart-wrap"><canvas id="hchart-${cat}"></canvas></div>
      ${coverageHtml}
    `;
    container.appendChild(card);

    const ctx = document.getElementById(`hchart-${cat}`).getContext('2d');
    state.historyCharts[cat] = new Chart(ctx, {
      type: 'line',
      data: { labels: allDates, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            position: 'bottom',
            labels: { color: '#d1d5db', boxWidth: 12, padding: 10, font: { size: 11 } },
          },
          tooltip: {
            callbacks: {
              label: ctx => ` ${ctx.dataset.label}: ${(ctx.parsed.y / 1000).toFixed(1)}k ISK`,
            },
          },
        },
        scales: {
          x: {
            ticks: { color: '#9ca3af', maxTicksLimit: 10, font: { size: 11 } },
            grid: { color: 'rgba(255,255,255,0.05)' },
          },
          y: {
            ticks: {
              color: '#9ca3af',
              font: { size: 11 },
              callback: v => (v / 1000).toFixed(0) + 'k',
            },
            grid: { color: 'rgba(255,255,255,0.07)' },
          },
        },
      },
    });
  });

  // If every category was skipped (model search matched nothing), show hint
  if (container.children.length === 0) {
    container.innerHTML = `
      <p style="padding:40px;text-align:center;color:#6b7280">
        No models match <strong style="color:#d1d5db">"${modelSearch}"</strong>.
        <a href="#" style="color:#60a5fa;margin-left:6px" onclick="document.getElementById('history-model-search').value='';filterHistoryModels('');return false">Clear filter</a>
      </p>`;
  }
}

// ── SEASONAL ANALYSIS ──────────────────────────────────────────────────────
const SEASON_COLORS = {
  low:      'rgba(59,130,246,0.08)',
  shoulder: 'rgba(245,158,11,0.11)',
  high:     'rgba(239,68,68,0.07)',
  peak:     'rgba(239,68,68,0.15)',
};

const COMP_PALETTE = [
  '#2563eb','#0ea5e9','#22c55e','#f59e0b','#8b5cf6','#f97316','#ec4899',
];

async function loadSeasonal(force = false) {
  if (state.seasonalData && !force) {
    renderSeasonalChart();
    renderSeasonalTable();
    renderSeasonalCategoryTable();
    return;
  }

  const loadingEl = document.getElementById('seasonal-loading');
  if (loadingEl) loadingEl.style.display = 'flex';

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 90000);

  try {
    const data = await apiFetch('/api/rates/seasonal', { signal: controller.signal });
    clearTimeout(timeoutId);
    state.seasonalData = data;

    setSourceBadge('seasonal-source-badge', data.source);
    document.querySelectorAll('#seasonal-source-badge').forEach(el => el.style.display = '');

    renderSeasonalChart();
    renderSeasonalTable();
    renderSeasonalCategoryTable();
  } catch (e) {
    showToast(`Failed to load seasonal data: ${e.message}`, 'error');
  } finally {
    if (loadingEl) loadingEl.style.display = 'none';
  }
}

// Module-level season sequence — set before chart construction so beforeDraw sees it
let _seasonBandSeq = [];

// Chart.js plugin: draw translucent season bands behind the lines
const seasonBandPlugin = {
  id: 'seasonBands',
  beforeDraw(chart) {
    const { ctx, chartArea } = chart;
    if (!chartArea || !_seasonBandSeq.length) return;
    const n = chart.data.labels.length;
    if (!n) return;
    const stepPx = (chartArea.right - chartArea.left) / n;
    _seasonBandSeq.forEach((season, i) => {
      const color = SEASON_COLORS[season] || 'transparent';
      ctx.fillStyle = color;
      ctx.fillRect(chartArea.left + i * stepPx, chartArea.top, stepPx, chartArea.bottom - chartArea.top);
    });
  },
};

function renderSeasonalChart() {
  const canvas = document.getElementById('seasonal-chart');
  if (!canvas || !state.seasonalData) return;

  const months = state.seasonalData.months;
  const catFilter = document.getElementById('seasonal-category')?.value || '';

  // Build per-competitor series
  const compNames = [...new Set(months.flatMap(m => Object.keys(m.competitors)))].sort();
  const labels    = months.map(m => m.month_label);
  const seasonSeq = months.map(m => m.season);

  const datasets = compNames.map((comp, i) => {
    const data = months.map(m => {
      if (catFilter) {
        return m.competitors[comp]?.[catFilter] ?? null;
      }
      return m.comp_overall[comp] ?? null;
    });
    const color = COMP_PALETTE[i % COMP_PALETTE.length];
    return {
      label: comp,
      data,
      borderColor: color,
      backgroundColor: color + '18',
      borderWidth: 2,
      pointRadius: 4,
      pointHoverRadius: 6,
      tension: 0.35,
      spanGaps: true,
      fill: false,
    };
  });

  if (state.seasonalChart) state.seasonalChart.destroy();

  // Set band sequence BEFORE constructing — beforeDraw fires during constructor
  _seasonBandSeq = seasonSeq;

  const chart = new Chart(canvas, {
    type: 'line',
    plugins: [seasonBandPlugin],
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          position: 'bottom',
          labels: { font: { size: 11 }, boxWidth: 12, padding: 10 },
        },
        tooltip: {
          callbacks: {
            title: items => {
              const i = items[0].dataIndex;
              return `${labels[i]}  ·  ${capitalize(months[i].season_label)}`;
            },
            label: ctx => ctx.parsed.y !== null
              ? ` ${ctx.dataset.label}: ${formatISK(ctx.parsed.y)}/day`
              : null,
          },
        },
      },
      scales: {
        x: {
          ticks: { color: '#6b7280', font: { size: 11 } },
          grid: { color: 'rgba(0,0,0,0.06)' },
        },
        y: {
          ticks: {
            color: '#6b7280',
            font: { size: 11 },
            callback: v => (v / 1000).toFixed(0) + 'k ISK',
          },
          grid: { color: 'rgba(0,0,0,0.06)' },
          title: { display: true, text: 'Per-Day Price (ISK)', font: { size: 11 }, color: '#9ca3af' },
        },
      },
    },
  });

  state.seasonalChart = chart;
}

function renderSeasonalTable() {
  const tbody = document.getElementById('seasonal-tbody');
  if (!tbody || !state.seasonalData) return;

  const { season_summary, months } = state.seasonalData;
  const SEASON_ORDER = ['low', 'shoulder', 'high', 'peak'];
  const SEASON_LABELS = { low: 'Low', shoulder: 'Shoulder', high: 'High', peak: 'Peak' };
  const catFilter = document.getElementById('seasonal-category')?.value || '';

  // If a category is selected, build a filtered season_summary from monthly data
  let activeSummary = season_summary;
  if (catFilter && months?.length) {
    const buckets = {};
    months.forEach(m => {
      const s = m.season;
      Object.entries(m.competitors || {}).forEach(([comp, cats]) => {
        const price = cats[catFilter];
        if (price == null) return;
        buckets[s] = buckets[s] || {};
        buckets[s][comp] = buckets[s][comp] || [];
        buckets[s][comp].push(price);
      });
    });
    activeSummary = {};
    Object.entries(buckets).forEach(([s, comps]) => {
      activeSummary[s] = {};
      Object.entries(comps).forEach(([comp, vals]) => {
        activeSummary[s][comp] = Math.round(vals.reduce((a, b) => a + b, 0) / vals.length);
      });
    });
  }

  // Collect all competitor names across all seasons
  const compNames = [...new Set(
    Object.values(activeSummary).flatMap(s => Object.keys(s))
  )].sort();

  if (!compNames.length) {
    tbody.innerHTML = `<tr><td colspan="6" style="padding:30px;text-align:center;color:#6b7280">No data${catFilter ? ` for ${catFilter}` : ''}</td></tr>`;
    return;
  }

  tbody.innerHTML = compNames.map(comp => {
    const prices = SEASON_ORDER.map(s => activeSummary[s]?.[comp] ?? null);
    const lowPrice  = prices[0];
    const peakPrice = prices[3];
    const uplift    = (lowPrice && peakPrice)
      ? `+${Math.round((peakPrice / lowPrice - 1) * 100)}%`
      : '—';

    const cells = SEASON_ORDER.map((s, i) => {
      const p = prices[i];
      if (!p) return `<td style="text-align:center;color:#d1d5db">—</td>`;
      return `<td class="season-cell season-cell-${s}" style="text-align:center">
        <div style="font-weight:700;font-size:14px">${formatISK(p)}</div>
        <div style="font-size:10px;color:#9ca3af">/day</div>
      </td>`;
    }).join('');

    const upliftClass = parseInt(uplift) > 80 ? 'color:#dc2626;font-weight:700'
      : parseInt(uplift) > 50 ? 'color:#f59e0b;font-weight:700'
      : 'color:#6b7280';

    return `<tr>
      <td><strong>${escHtml(comp)}</strong></td>
      ${cells}
      <td style="text-align:center;font-size:13px;${upliftClass}">${uplift}</td>
    </tr>`;
  }).join('');
}

function renderSeasonalCategoryTable() {
  const tbody = document.getElementById('seasonal-category-tbody');
  if (!tbody || !state.seasonalData) return;

  const { category_season_summary } = state.seasonalData;
  const SEASON_ORDER = ['low', 'shoulder', 'high', 'peak'];
  const CAT_ORDER = ['Economy', 'Compact', 'SUV', '4x4', 'Minivan'];

  // Collect all categories present in the data, preserving preferred order
  const allCats = [...new Set([
    ...CAT_ORDER,
    ...Object.values(category_season_summary || {}).flatMap(s => Object.keys(s)),
  ])].filter(cat => Object.values(category_season_summary || {}).some(s => s[cat] != null));

  if (!allCats.length) {
    tbody.innerHTML = `<tr><td colspan="6" style="padding:30px;text-align:center;color:#6b7280">No data</td></tr>`;
    return;
  }

  tbody.innerHTML = allCats.map(cat => {
    const prices = SEASON_ORDER.map(s => category_season_summary[s]?.[cat] ?? null);
    const lowPrice  = prices[0];
    const peakPrice = prices[3];
    const uplift    = (lowPrice && peakPrice)
      ? `+${Math.round((peakPrice / lowPrice - 1) * 100)}%`
      : '—';

    const cells = SEASON_ORDER.map((s, i) => {
      const p = prices[i];
      if (!p) return `<td style="text-align:center;color:#d1d5db">—</td>`;
      return `<td class="season-cell season-cell-${s}" style="text-align:center">
        <div style="font-weight:700;font-size:14px">${formatISK(p)}</div>
        <div style="font-size:10px;color:#9ca3af">/day</div>
      </td>`;
    }).join('');

    const upliftClass = parseInt(uplift) > 80 ? 'color:#dc2626;font-weight:700'
      : parseInt(uplift) > 50 ? 'color:#f59e0b;font-weight:700'
      : 'color:#6b7280';

    return `<tr>
      <td><strong>${escHtml(cat)}</strong></td>
      ${cells}
      <td style="text-align:center;font-size:13px;${upliftClass}">${uplift}</td>
    </tr>`;
  }).join('');
}

function capitalize(str) {
  return str ? str.charAt(0).toUpperCase() + str.slice(1) : str;
}

// ── RATES TAB ──────────────────────────────────────────────────────────────
async function loadRates() {
  const location = document.getElementById('filter-location').value;
  const pickup = document.getElementById('filter-pickup').value;
  const ret = document.getElementById('filter-return').value;
  const category = document.getElementById('filter-category').value;

  const params = new URLSearchParams();
  if (location) params.set('location', location);
  if (pickup) params.set('pickup_date', pickup);
  if (ret) params.set('return_date', ret);
  if (category) params.set('car_category', category);

  try {
    const deltaParams = new URLSearchParams();
    if (location) deltaParams.set('location', location);
    if (category) deltaParams.set('category', category);

    const [ratesData, deltasData] = await Promise.all([
      apiFetch(`/api/rates?${params}`),
      apiFetch(`/api/rates/deltas?${deltaParams}`).catch(() => ({ deltas: {}, available: false })),
    ]);
    state.rates          = ratesData.rates || [];
    state.ratesSource    = ratesData.source;
    state.deltas         = deltasData.deltas || {};
    state.deltasAvailable = deltasData.available || false;
    renderRatesTable();
    renderRateChart();
    updateRateStats();
    // Reset matrix so it reloads with new filters if active
    state.matrix = null;
    if (state.ratesView === 'matrix') loadMatrix();
  } catch (e) {
    showToast(`Failed to load rates: ${e.message}`, 'error');
  }
}

async function loadMatrix() {
  const location = document.getElementById('filter-location').value;
  const pickup = document.getElementById('filter-pickup').value;
  const ret = document.getElementById('filter-return').value;
  const category = document.getElementById('filter-category').value;

  const params = new URLSearchParams();
  if (location) params.set('location', location);
  if (pickup) params.set('pickup_date', pickup);
  if (ret) params.set('return_date', ret);
  if (category) params.set('category', category);

  try {
    const data = await apiFetch(`/api/rates/matrix?${params}`);
    state.matrix = data;
    state.matrixSource = data.source;
    renderMatrix();
  } catch (e) {
    showToast(`Failed to load matrix: ${e.message}`, 'error');
  }
}

function setRateSort(col) {
  const s = state.ratesSort;
  if (s.col === col) {
    s.dir = s.dir === 'asc' ? 'desc' : 'asc';
  } else {
    s.col = col;
    s.dir = 'asc';
  }
  // Update sort icons in header
  document.querySelectorAll('.sort-icon').forEach(el => {
    if (el.dataset.col === col) {
      el.textContent = s.dir === 'asc' ? ' ↑' : ' ↓';
    } else {
      el.textContent = '';
    }
  });
  renderRatesTable();
}

function renderRatesTable() {
  const tbody = document.getElementById('rates-tbody');
  let rates = [...state.rates];

  if (!rates.length) {
    tbody.innerHTML = `<tr><td colspan="8" class="empty-state" style="padding:40px;text-align:center;color:#6b7280">No rate data available. Click "Scrape Now" to fetch rates.</td></tr>`;
    return;
  }

  // Calculate days + per_day for each row (needed for sorting)
  function getDays(pickup, ret) {
    try {
      const diff = new Date(ret) - new Date(pickup);
      return Math.max(1, Math.round(diff / 86400000));
    } catch { return 1; }
  }
  rates = rates.map(r => ({
    ...r,
    _days:    getDays(r.pickup_date, r.return_date),
    _per_day: Math.round(r.price_isk / Math.max(1, getDays(r.pickup_date, r.return_date))),
  }));

  // Sort
  const { col, dir } = state.ratesSort;
  if (col) {
    const key = col === 'per_day' ? '_per_day' : col;
    rates.sort((a, b) => {
      const av = a[key] ?? '';
      const bv = b[key] ?? '';
      const cmp = typeof av === 'number' ? av - bv : String(av).localeCompare(String(bv));
      return dir === 'asc' ? cmp : -cmp;
    });
  }

  // Cheapest per canonical model (across all competitors in current view)
  const cheapestPerModel = {};
  state.rates.forEach(r => {
    const key = r.canonical_name || r.car_model || r.car_category;
    if (cheapestPerModel[key] === undefined || r.price_isk < cheapestPerModel[key]) {
      cheapestPerModel[key] = r.price_isk;
    }
  });

  // Global max for "most expensive" highlight
  const maxPrice = Math.max(...state.rates.map(r => r.price_isk));

  tbody.innerHTML = rates.map(r => {
    const modelKey = r.canonical_name || r.car_model || r.car_category;
    let priceClass = '';
    if (r.price_isk === cheapestPerModel[modelKey]) priceClass = 'price-low';
    else if (r.price_isk === maxPrice) priceClass = 'price-high';

    const modelName = r.car_model || r.car_category;
    const canonicalNote = r.canonical_name && r.canonical_name !== r.car_model
      ? `<span style="color:#6b7280;font-size:11px"> → ${escHtml(r.canonical_name)}</span>` : '';

    // Delta indicator
    const deltaKey = r.canonical_name || r.car_model;
    const d = state.deltas[deltaKey];
    let deltaHtml = `<span style="color:#6b7280">—</span>`;
    if (d) {
      const sign = d.delta_pct > 0 ? '+' : '';
      if (d.direction === 'up')
        deltaHtml = `<span class="delta-up">↑ ${sign}${d.delta_pct}%</span>`;
      else if (d.direction === 'down')
        deltaHtml = `<span class="delta-down">↓ ${Math.abs(d.delta_pct)}%</span>`;
      else
        deltaHtml = `<span class="delta-same">± 0%</span>`;
    }

    return `<tr>
      <td><strong>${escHtml(r.competitor)}</strong></td>
      <td>${escHtml(modelName)}${canonicalNote}</td>
      <td><span class="badge badge-blue">${escHtml(r.car_category)}</span></td>
      <td class="${priceClass}">${formatISK(r.price_isk)}</td>
      <td>${formatISK(r._per_day)}/day</td>
      <td style="text-align:center;font-size:12px;font-weight:600">${deltaHtml}</td>
      <td><span class="badge badge-gray">${escHtml(r.location)}</span></td>
      <td style="color:#6b7280;font-size:12px">${timeAgo(r.scraped_at)}</td>
    </tr>`;
  }).join('');
}

function renderMatrix() {
  const wrap = document.getElementById('matrix-table-wrap');
  const data = state.matrix;
  if (!data || !data.cars || !data.cars.length) {
    wrap.innerHTML = `<p style="padding:40px;text-align:center;color:#6b7280">No data. Click "Scrape Now" to fetch rates.</p>`;
    return;
  }

  const { cars, competitors } = data;

  setSourceBadge('matrix-source-badge', state.matrixSource);

  // Build header row
  const shortName = c => c.replace(' Car Rental', '').replace(' Iceland', '');
  const headerCells = competitors.map(c =>
    `<th style="text-align:center;min-width:100px">${escHtml(shortName(c))}</th>`
  ).join('');

  // Group rows by category
  let lastCategory = '';
  const rows = cars.map(car => {
    let categoryDivider = '';
    if (car.category !== lastCategory) {
      lastCategory = car.category;
      categoryDivider = `<tr style="background:#f8fafc">
        <td colspan="${2 + competitors.length}" style="padding:6px 12px;font-size:11px;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:.05em">
          ${escHtml(car.category)}
        </td>
      </tr>`;
    }

    const cells = competitors.map(comp => {
      const entry = car.prices[comp];
      if (!entry) return `<td style="text-align:center;color:#d1d5db">—</td>`;

      let cls = '';
      if (car.min_price !== null && entry.price_isk === car.min_price) cls = 'price-low';
      else if (car.max_price !== null && entry.price_isk === car.max_price) cls = 'price-high';

      const modelNote = entry.car_model && entry.car_model !== car.canonical_name
        ? `<div style="font-size:10px;color:#9ca3af">${escHtml(entry.car_model)}</div>` : '';

      // Delta badge for this canonical model
      const d = state.deltas[car.canonical_name];
      let deltaBadge = '';
      if (d) {
        const sign = d.delta_pct > 0 ? '+' : '';
        if (d.direction === 'up')
          deltaBadge = `<div class="delta-up" style="font-size:10px">↑ ${sign}${d.delta_pct}%</div>`;
        else if (d.direction === 'down')
          deltaBadge = `<div class="delta-down" style="font-size:10px">↓ ${Math.abs(d.delta_pct)}%</div>`;
      }

      return `<td class="${cls}" style="text-align:center">
        <div style="font-weight:600">${formatISK(entry.price_isk)}</div>
        ${modelNote}${deltaBadge}
      </td>`;
    }).join('');

    const availBadge = car.available_at > 0
      ? `<span style="font-size:10px;color:#6b7280">${car.available_at}/${competitors.length}</span>`
      : '';

    return `${categoryDivider}<tr>
      <td><strong>${escHtml(car.canonical_name)}</strong>${availBadge ? ' ' + availBadge : ''}</td>
      ${cells}
    </tr>`;
  }).join('');

  wrap.innerHTML = `
    <table>
      <thead>
        <tr>
          <th style="min-width:180px">Car Model</th>
          ${headerCells}
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function updateRateStats() {
  const rates = state.rates;
  if (!rates.length) return;

  const prices = rates.map(r => r.price_isk);
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const avgPrice = Math.round(prices.reduce((a, b) => a + b, 0) / prices.length);
  const cheapest = rates.find(r => r.price_isk === minPrice);

  document.getElementById('stat-min-price').textContent = formatISK(minPrice);
  document.getElementById('stat-max-price').textContent = formatISK(maxPrice);
  document.getElementById('stat-avg-price').textContent = formatISK(avgPrice);
  document.getElementById('stat-cheapest').textContent = cheapest ? cheapest.competitor : '—';
  document.getElementById('stat-competitors').textContent = new Set(rates.map(r => r.competitor)).size;

  setSourceBadge('rates-source-badge', state.ratesSource);

  // Populate history competitor dropdown from loaded rates
  const histComp = document.getElementById('history-competitor');
  if (histComp && rates.length) {
    const current = histComp.value;
    const comps = Array.from(new Set(rates.map(r => r.competitor))).sort();
    histComp.innerHTML = '<option value="">All Competitors</option>' +
      comps.map(c => `<option value="${c}"${c === current ? ' selected' : ''}>${c}</option>`).join('');
  }
}

function renderRateChart() {
  const canvas = document.getElementById('rate-chart');
  if (!canvas) return;

  const rates = state.rates;
  if (!rates.length) return;

  // Group by competitor, average price
  const competitorMap = {};
  rates.forEach(r => {
    if (!competitorMap[r.competitor]) competitorMap[r.competitor] = [];
    competitorMap[r.competitor].push(r.price_isk);
  });

  const labels = Object.keys(competitorMap);
  const data = labels.map(c => Math.round(
    competitorMap[c].reduce((a, b) => a + b, 0) / competitorMap[c].length
  ));

  const colors = [
    '#2563eb', '#0ea5e9', '#6366f1', '#8b5cf6',
    '#ec4899', '#f59e0b', '#10b981',
  ];

  if (state.rateChart) state.rateChart.destroy();

  state.rateChart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Avg. Price (ISK)',
        data,
        backgroundColor: colors.slice(0, labels.length),
        borderRadius: 6,
        borderSkipped: false,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => formatISK(ctx.raw),
          },
        },
      },
      scales: {
        y: {
          beginAtZero: false,
          ticks: {
            callback: val => formatISK(val),
            font: { size: 11 },
          },
          grid: { color: '#f3f4f6' },
        },
        x: {
          ticks: { font: { size: 11 } },
          grid: { display: false },
        },
      },
    },
  });
}

async function triggerScrape() {
  if (state.scraping) return;
  state.scraping = true;
  const btn = document.getElementById('btn-scrape');
  const origHtml = btn.innerHTML;
  btn.innerHTML = '<span class="spinner"></span> Scraping...';
  btn.classList.add('loading');

  try {
    const pickup = document.getElementById('filter-pickup').value || defaultPickup();
    const ret = document.getElementById('filter-return').value || defaultReturn();
    const location = document.getElementById('filter-location').value;
    const params = new URLSearchParams({ pickup_date: pickup, return_date: ret });
    if (location) params.set('location', location);

    const data = await apiFetch(`/api/rates/scrape?${params}`, { method: 'POST' });
    showToast(`Scraped ${data.scraped} rate records from ${data.competitors} competitors.`, 'success');
    await loadRates();
    loadSchedulerStatus();
  } catch (e) {
    showToast(`Scrape failed: ${e.message}`, 'error');
  } finally {
    state.scraping = false;
    btn.innerHTML = origHtml;
    btn.classList.remove('loading');
  }
}

// ── SEO TAB ────────────────────────────────────────────────────────────────
async function loadRankings() {
  try {
    const [data] = await Promise.all([
      apiFetch('/api/seo/rankings'),
    ]);
    state.rankings = data.rankings || [];
    state.rankingsSource = data.source;

    const warningEl = document.getElementById('seo-no-key-banner');
    if (warningEl) warningEl.style.display = data.has_api_key ? 'none' : 'flex';

    // Last checked — use most recent serp_date from results
    const dates = state.rankings.map(r => r.serp_date).filter(Boolean).sort();
    const lastCheckedEl = document.getElementById('seo-last-checked');
    if (lastCheckedEl && dates.length) {
      lastCheckedEl.textContent = `· Last checked: ${formatDate(dates[dates.length - 1])}`;
    }

    renderRankingsTable();
    await Promise.all([loadRankingsHistory(), loadKeywords()]);
  } catch (e) {
    showToast(`Failed to load rankings: ${e.message}`, 'error');
  }
}

function rankBadge(rank) {
  if (rank === null || rank === undefined) {
    return `<span class="rank-badge rank-none">Not in top 100</span>`;
  }
  if (rank === 1) return `<span class="rank-badge rank-gold">🥇 #1</span>`;
  if (rank === 2) return `<span class="rank-badge rank-gold">#2</span>`;
  if (rank === 3) return `<span class="rank-badge rank-gold">#3</span>`;
  if (rank <= 10) return `<span class="rank-badge rank-green">#${rank}</span>`;
  if (rank <= 20) return `<span class="rank-badge rank-blue">#${rank}</span>`;
  return `<span class="rank-badge rank-gray">#${rank}</span>`;
}

function setSeoSort(col) {
  if (state.seoSort.col === col) {
    state.seoSort.dir = state.seoSort.dir === 'asc' ? 'desc' : 'asc';
  } else {
    state.seoSort.col = col;
    state.seoSort.dir = 'asc';
  }
  renderRankingsTable();
}

function setSeoChartFilter(filter) {
  state.seoChartFilter = filter;
  ['all', '10', '5'].forEach(f => {
    const btn = document.getElementById(`seo-filter-${f}`);
    if (btn) btn.classList.toggle('active', f === filter);
  });
  renderSeoChart();
}

function renderRankingsTable() {
  const tbody = document.getElementById('rankings-tbody');
  const rankings = state.rankings;

  if (!rankings.length) {
    tbody.innerHTML = `<tr><td colspan="6" style="padding:40px;text-align:center;color:#6b7280">No ranking data yet. Click "Check Rankings Now".</td></tr>`;
    return;
  }

  // Sort a copy of rankings
  const { col, dir } = state.seoSort;
  const sorted = [...rankings].sort((a, b) => {
    let av, bv;
    switch (col) {
      case 'keyword':
        av = a.keyword || ''; bv = b.keyword || '';
        return dir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
      case 'rank':
        av = a.rank ?? 9999; bv = b.rank ?? 9999;
        return dir === 'asc' ? av - bv : bv - av;
      case 'previous':
        av = a.previous_rank ?? 9999; bv = b.previous_rank ?? 9999;
        return dir === 'asc' ? av - bv : bv - av;
      case 'change':
        av = a.change ?? -9999; bv = b.change ?? -9999;
        return dir === 'asc' ? av - bv : bv - av;
      case 'date':
        av = a.serp_date || ''; bv = b.serp_date || '';
        return dir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
      default: return 0;
    }
  });

  // Update sort indicator classes on column headers
  document.querySelectorAll('.sort-header').forEach(th => {
    th.classList.remove('sort-asc', 'sort-desc');
    if (th.dataset.col === col) {
      th.classList.add(dir === 'asc' ? 'sort-asc' : 'sort-desc');
    }
  });

  tbody.innerHTML = sorted.map(r => {
    let changeHtml = '<span class="rank-same">—</span>';
    if (r.change !== null && r.change !== undefined) {
      if (r.change > 0) changeHtml = `<span class="rank-up">▲ ${r.change}</span>`;
      else if (r.change < 0) changeHtml = `<span class="rank-down">▼ ${Math.abs(r.change)}</span>`;
      else changeHtml = `<span class="rank-same">↔ 0</span>`;
    }

    const prevRank = r.previous_rank !== null && r.previous_rank !== undefined
      ? rankBadge(r.previous_rank) : '<span style="color:#9ca3af">—</span>';

    // URL cell — truncated, linked if available
    let urlHtml = '<span style="color:#9ca3af">—</span>';
    if (r.url) {
      const short = r.url.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '').slice(0, 40);
      urlHtml = `<a href="${escHtml(r.url)}" target="_blank" rel="noopener"
                    style="color:#2563eb;font-size:11px;word-break:break-all"
                    title="${escHtml(r.url)}">${escHtml(short)}</a>`;
    }

    // Mover highlight — 3+ positions up/down
    const moverClass = (r.change !== null && r.change !== undefined)
      ? (r.change >= 3 ? 'row-mover-up' : (r.change <= -3 ? 'row-mover-down' : ''))
      : '';

    return `<tr class="${moverClass}">
      <td><strong>${escHtml(r.keyword)}</strong></td>
      <td>${rankBadge(r.rank)}</td>
      <td>${prevRank}</td>
      <td>${changeHtml}</td>
      <td>${urlHtml}</td>
      <td style="color:#6b7280;font-size:12px">${formatDate(r.serp_date)}</td>
    </tr>`;
  }).join('');

  // Update all stat cards
  const ranked = rankings.filter(r => r.rank !== null && r.rank !== undefined);
  const notRanked = rankings.length - ranked.length;
  document.getElementById('stat-keywords-tracked').textContent = rankings.length;
  document.getElementById('stat-avg-rank').textContent = ranked.length
    ? '#' + Math.round(ranked.reduce((a, r) => a + r.rank, 0) / ranked.length)
    : '—';
  document.getElementById('stat-top-10').textContent = ranked.filter(r => r.rank <= 10).length;
  const notRankedEl = document.getElementById('stat-not-ranked');
  if (notRankedEl) notRankedEl.textContent = notRanked;

  setSourceBadge('seo-source-badge', state.rankingsSource);
}

async function loadRankingsHistory() {
  const days = document.getElementById('seo-history-days')?.value || '30';
  try {
    const data = await apiFetch(`/api/seo/history?days=${days}`);
    state.rankingsHistory = data.history || [];
    renderSeoChart();
  } catch (e) {
    console.warn('Failed to load SEO history:', e);
  }
}

function renderSeoChart() {
  const canvas = document.getElementById('seo-chart');
  if (!canvas) return;

  const history = state.rankingsHistory;
  if (!history.length) return;

  // Group by keyword
  const kwMap = {};
  history.forEach(h => {
    if (!kwMap[h.keyword]) kwMap[h.keyword] = {};
    const dateKey = h.created_at.slice(0, 10);
    kwMap[h.keyword][dateKey] = h.rank;
  });

  // Apply chart filter (top N by best rank)
  let kwEntries = Object.entries(kwMap);
  if (state.seoChartFilter !== 'all') {
    const n = parseInt(state.seoChartFilter);
    kwEntries = kwEntries
      .map(([kw, dateRanks]) => {
        const ranks = Object.values(dateRanks).filter(v => v !== null);
        return { kw, dateRanks, bestRank: ranks.length ? Math.min(...ranks) : 9999 };
      })
      .sort((a, b) => a.bestRank - b.bestRank)
      .slice(0, n)
      .map(({ kw, dateRanks }) => [kw, dateRanks]);
  }

  // Collect all dates
  const allDates = [...new Set(history.map(h => h.created_at.slice(0, 10)))].sort();

  const palette = ['#2563eb', '#0ea5e9', '#6366f1', '#8b5cf6', '#ec4899',
                   '#f59e0b', '#22c55e', '#ef4444', '#8b5cf6', '#14b8a6'];
  const datasets = kwEntries.map(([kw, dateRanks], i) => ({
    label: kw,
    data: allDates.map(d => (dateRanks[d] !== undefined ? dateRanks[d] : null)),
    borderColor: palette[i % palette.length],
    backgroundColor: palette[i % palette.length] + '20',
    tension: 0.3,
    borderWidth: 2,
    pointRadius: 3,
    spanGaps: true,
  }));

  if (state.seoChart) state.seoChart.destroy();

  state.seoChart = new Chart(canvas, {
    type: 'line',
    data: {
      labels: allDates.map(d => formatDate(d)),
      datasets,
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          position: 'bottom',
          labels: { font: { size: 11 }, boxWidth: 12 },
        },
        tooltip: {
          callbacks: {
            label: ctx => ctx.parsed.y !== null ? `${ctx.dataset.label}: #${ctx.parsed.y}` : null,
          },
        },
      },
      scales: {
        y: {
          reverse: true, // lower rank number = better = top of chart
          ticks: {
            callback: val => `#${val}`,
            stepSize: 1,
            font: { size: 11 },
          },
          grid: { color: '#f3f4f6' },
          title: { display: true, text: 'Search Rank', font: { size: 11 } },
        },
        x: {
          ticks: { font: { size: 10 }, maxTicksLimit: 10 },
          grid: { display: false },
        },
      },
    },
  });
}

// ── KEYWORD MANAGEMENT ─────────────────────────────────────────────────────
async function loadKeywords() {
  try {
    const data = await apiFetch('/api/seo/keywords');
    state.seoKeywords = data.keywords || [];
    renderKeywordsList();
  } catch (e) {
    console.warn('Failed to load keywords:', e);
  }
}

function renderKeywordsList() {
  const list = document.getElementById('keywords-list');
  const countEl = document.getElementById('kw-count-badge');
  const keywords = state.seoKeywords || [];

  if (countEl) {
    countEl.textContent = `${keywords.length} / 20`;
    countEl.className = keywords.length >= 20 ? 'badge badge-amber' : 'badge badge-gray';
  }

  if (!list) return;
  if (!keywords.length) {
    list.innerHTML = `<span style="color:#9ca3af;font-size:13px">No keywords tracked yet.</span>`;
    return;
  }

  list.innerHTML = keywords.map(kw => `
    <span class="keyword-tag">
      ${escHtml(kw)}
      <button class="keyword-remove" onclick="removeSeoKeyword('${escHtml(kw)}')" title="Remove keyword">×</button>
    </span>
  `).join('');
}

async function addSeoKeyword() {
  const input = document.getElementById('new-keyword-input');
  const kw = input?.value?.trim();
  if (!kw) return;
  try {
    const data = await apiFetch(`/api/seo/keywords?keyword=${encodeURIComponent(kw)}`, { method: 'POST' });
    state.seoKeywords = data.keywords;
    renderKeywordsList();
    if (input) input.value = '';
    showToast(`Added keyword: "${kw}"`, 'success');
  } catch (e) {
    showToast(`Could not add keyword: ${e.message}`, 'error');
  }
}

async function removeSeoKeyword(kw) {
  try {
    const data = await apiFetch(`/api/seo/keywords/${encodeURIComponent(kw)}`, { method: 'DELETE' });
    state.seoKeywords = data.keywords;
    renderKeywordsList();
    showToast(`Removed keyword: "${kw}"`, 'info');
  } catch (e) {
    showToast(`Could not remove keyword: ${e.message}`, 'error');
  }
}

async function triggerSeoCheck() {
  if (state.checkingSeo) return;
  state.checkingSeo = true;
  const btn = document.getElementById('btn-check-seo');
  const origHtml = btn.innerHTML;
  btn.innerHTML = '<span class="spinner"></span> Checking...';
  btn.classList.add('loading');

  try {
    const data = await apiFetch('/api/seo/check', { method: 'POST' });
    showToast(data.message, 'success');
    await loadRankings();
  } catch (e) {
    showToast(`SEO check failed: ${e.message}`, 'error');
  } finally {
    state.checkingSeo = false;
    btn.innerHTML = origHtml;
    btn.classList.remove('loading');
  }
}

// ── SETTINGS TAB ───────────────────────────────────────────────────────────
async function loadSettings() {
  try {
    const [settingsData, mappingsData] = await Promise.all([
      apiFetch('/api/settings'),
      apiFetch('/api/rates/car-mappings'),
    ]);

    state.settings = settingsData;
    state.locations = settingsData.locations || [];
    state.mappings = mappingsData.mappings || [];

    const keyInput = document.getElementById('setting-serpapi-key');
    if (keyInput) {
      keyInput.placeholder = settingsData.serpapi_key_set
        ? '••••••••••••••••••••••••••••••••'
        : 'Enter your SerpAPI key';
    }

    const scheduleEl = document.getElementById('setting-schedule');
    if (scheduleEl) scheduleEl.value = settingsData.scrape_schedule || 'daily';

    renderLocationList();
    renderMappingsTable();
    await loadScraperStatus();
    loadAlertConfig();
  } catch (e) {
    showToast(`Failed to load settings: ${e.message}`, 'error');
  }
}

async function loadScraperStatus() {
  try {
    const data = await apiFetch('/api/rates/scraper-status');
    const scraperMap = {};
    for (const s of (data.scrapers || [])) scraperMap[s.name] = s;

    document.querySelectorAll('.scraper-status-badge').forEach(badge => {
      const s = scraperMap[badge.dataset.competitor];
      const source = s?.source || 'mock';
      badge.textContent = source === 'live' ? 'Live Data' : 'Mock Data';
      badge.className = `badge ${source === 'live' ? 'badge-green' : 'badge-gray'} scraper-status-badge`;
    });

    document.querySelectorAll('.scraper-ts').forEach(el => {
      const s = scraperMap[el.dataset.competitor];
      el.textContent = s?.last_scraped ? timeAgo(s.last_scraped) : '';
    });
  } catch (_) { /* leave badges as-is on failure */ }
}

async function testWebhook() {
  const btn = document.getElementById('btn-test-webhook');
  if (btn) { btn.disabled = true; btn.textContent = 'Sending…'; }
  try {
    const res = await apiFetch('/api/alerts/test-webhook', { method: 'POST' });
    if (res.sent) {
      showToast('Test webhook sent! Check your Slack channel.', 'success');
    } else {
      showToast(`Webhook test failed: ${res.error || 'Unknown error'}`, 'error');
    }
  } catch (e) {
    showToast(`Webhook test failed: ${e.message}`, 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Test Webhook'; btn.prepend((() => { const s = document.createElementNS('http://www.w3.org/2000/svg','svg'); s.setAttribute('viewBox','0 0 24 24'); s.setAttribute('fill','none'); s.setAttribute('stroke','currentColor'); s.setAttribute('stroke-width','2'); s.setAttribute('stroke-linecap','round'); s.setAttribute('stroke-linejoin','round'); s.style.cssText='width:13px;height:13px;margin-right:4px'; s.innerHTML='<path d="M22 2L11 13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>'; return s; })()); }
  }
}

function renderMappingsTable() {
  const tbody = document.getElementById('mappings-tbody');
  if (!tbody) return;
  if (!state.mappings.length) {
    tbody.innerHTML = `<tr><td colspan="4" style="padding:20px;text-align:center;color:#6b7280">No mappings configured.</td></tr>`;
    return;
  }
  tbody.innerHTML = state.mappings.map(m => `
    <tr>
      <td>${escHtml(m.competitor)}</td>
      <td><code>${escHtml(m.competitor_model)}</code></td>
      <td>${escHtml(m.canonical_name)}</td>
      <td><button class="btn-remove" onclick="deleteMapping(${m.id})" title="Remove">&times;</button></td>
    </tr>
  `).join('');
}

async function deleteMapping(id) {
  try {
    await apiFetch(`/api/rates/car-mappings/${id}`, { method: 'DELETE' });
    state.mappings = state.mappings.filter(m => m.id !== id);
    renderMappingsTable();
    showToast('Mapping removed.', 'success');
  } catch (e) {
    showToast(`Failed to remove mapping: ${e.message}`, 'error');
  }
}

async function addMapping() {
  const competitor = document.getElementById('new-map-competitor').value;
  const model = document.getElementById('new-map-model').value.trim();
  const canonical = document.getElementById('new-map-canonical').value.trim();

  if (!competitor || !model || !canonical) {
    showToast('Please fill in all three mapping fields.', 'error');
    return;
  }

  try {
    await apiFetch('/api/rates/car-mappings', {
      method: 'POST',
      body: JSON.stringify({ competitor, competitor_model: model, canonical_name: canonical }),
    });
    document.getElementById('new-map-competitor').value = '';
    document.getElementById('new-map-model').value = '';
    document.getElementById('new-map-canonical').value = '';
    showToast('Mapping saved.', 'success');
    const data = await apiFetch('/api/rates/car-mappings');
    state.mappings = data.mappings || [];
    renderMappingsTable();
  } catch (e) {
    showToast(`Failed to save mapping: ${e.message}`, 'error');
  }
}

function renderLocationList() {
  const container = document.getElementById('location-list');
  if (!container) return;

  if (!state.locations.length) {
    container.innerHTML = '<p style="color:#6b7280;font-size:13px">No locations configured.</p>';
    return;
  }

  container.innerHTML = state.locations.map((loc, i) => `
    <div class="location-item">
      <span class="loc-name">${escHtml(loc.name)}</span>
      <span class="loc-addr">${escHtml(loc.address)}</span>
      <button class="btn-remove" onclick="removeLocation(${i})" title="Remove">&times;</button>
    </div>
  `).join('');
}

function removeLocation(index) {
  state.locations.splice(index, 1);
  renderLocationList();
}

function addLocation() {
  const nameEl = document.getElementById('new-loc-name');
  const addrEl = document.getElementById('new-loc-addr');
  const name = nameEl.value.trim();
  const address = addrEl.value.trim();

  if (!name || !address) {
    showToast('Please enter both a name and address.', 'error');
    return;
  }

  state.locations.push({ name, address });
  nameEl.value = '';
  addrEl.value = '';
  renderLocationList();
}

async function saveSettings() {
  if (state.savingSettings) return;
  state.savingSettings = true;
  const btn = document.getElementById('btn-save-settings');
  const origHtml = btn.innerHTML;
  btn.innerHTML = '<span class="spinner"></span> Saving...';
  btn.classList.add('loading');

  try {
    const serpKey = document.getElementById('setting-serpapi-key').value.trim();
    const schedule = document.getElementById('setting-schedule').value;

    const payload = {
      scrape_schedule: schedule,
      locations: state.locations,
    };
    if (serpKey && !serpKey.startsWith('•')) {
      payload.serpapi_key = serpKey;
    }

    await apiFetch('/api/settings', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    // Reconfigure scheduler
    await apiFetch(`/api/scheduler/reconfigure?schedule=${schedule}`, { method: 'POST' });

    showToast('Settings saved successfully.', 'success');
    document.getElementById('setting-serpapi-key').value = '';
    await loadSettings();
  } catch (e) {
    showToast(`Failed to save settings: ${e.message}`, 'error');
  } finally {
    state.savingSettings = false;
    btn.innerHTML = origHtml;
    btn.classList.remove('loading');
  }
}

// ── PRICE ALERTS ───────────────────────────────────────────────────────────
async function loadAlertConfig() {
  try {
    const data = await apiFetch('/api/alerts/config');
    const webhookEl   = document.getElementById('alert-webhook-url');
    const thresholdEl = document.getElementById('alert-threshold');
    if (webhookEl)   webhookEl.placeholder = data.webhook_set ? '(webhook configured)' : 'https://hooks.slack.com/services/...';
    if (thresholdEl) thresholdEl.value = data.threshold_pct ?? 10;
  } catch (_) { /* silent — alerts are optional */ }
}

async function saveAlertConfig() {
  const webhookEl   = document.getElementById('alert-webhook-url');
  const thresholdEl = document.getElementById('alert-threshold');
  const btn = document.getElementById('btn-save-alerts');

  const webhook   = webhookEl?.value?.trim() || '';
  const threshold = parseFloat(thresholdEl?.value) || 10;

  const payload = { threshold_pct: threshold };
  if (webhook) payload.webhook_url = webhook;

  const origText = btn?.innerHTML;
  if (btn) { btn.innerHTML = '<span class="spinner"></span> Saving...'; btn.disabled = true; }

  try {
    await apiFetch('/api/alerts/config', { method: 'POST', body: JSON.stringify(payload) });
    showToast('Alert config saved.', 'success');
    if (webhookEl) webhookEl.value = '';
    await loadAlertConfig();
  } catch (e) {
    showToast(`Failed to save alert config: ${e.message}`, 'error');
  } finally {
    if (btn) { btn.innerHTML = origText; btn.disabled = false; }
  }
}

async function checkAlerts() {
  const btn = document.getElementById('btn-test-alert');
  const origHtml = btn?.innerHTML;
  if (btn) { btn.innerHTML = '<span class="spinner"></span> Checking...'; btn.disabled = true; }

  try {
    const result = await apiFetch('/api/alerts/check', { method: 'POST' });
    if (result.alerts_fired > 0) {
      const slackNote = result.webhook_sent ? ' — Slack notified!' : ' (no webhook configured)';
      showToast(`⚠️ ${result.alerts_fired} competitor(s) undercutting your rates${slackNote}`, 'error');
    } else {
      showToast('✓ No undercutting detected — your rates are competitive!', 'success');
    }
  } catch (e) {
    showToast(`Alert check failed: ${e.message}`, 'error');
  } finally {
    if (btn) { btn.innerHTML = origHtml; btn.disabled = false; }
  }
}

// ── CSV EXPORT ──────────────────────────────────────────────────────────────
function downloadCSV(filename, rows) {
  const content = rows
    .map(row => row.map(cell => `"${String(cell ?? '').replace(/"/g, '""')}"`).join(','))
    .join('\n');
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

function exportMatrixCSV() {
  const data = state.matrix;
  if (!data || !data.cars || !data.cars.length) {
    return showToast('No matrix data to export. Scrape first.', 'error');
  }
  const { cars, competitors } = data;
  const shortName = c => c.replace(' Car Rental', '').replace(' Iceland', '');
  const headers = ['Category', 'Model', ...competitors.map(shortName), 'Cheapest Competitor'];
  const rows = cars.map(car => [
    car.category,
    car.canonical_name,
    ...competitors.map(c => car.prices[c] ? car.prices[c].price_isk : ''),
    car.cheapest_competitor || '',
  ]);
  downloadCSV(`rate_matrix_${new Date().toISOString().slice(0,10)}.csv`, [headers, ...rows]);
  showToast('Rate matrix exported!', 'success');
}

function exportSeasonalCSV() {
  const data = state.seasonalData;
  if (!data) return showToast('No seasonal data to export. Load seasonal analysis first.', 'error');

  const { season_summary } = data;
  const SEASON_ORDER  = ['low', 'shoulder', 'high', 'peak'];
  const competitors   = [...new Set(SEASON_ORDER.flatMap(s => Object.keys(season_summary[s] || {})))].sort();

  const headers = ['Competitor', 'Low Season (ISK/day)', 'Shoulder (ISK/day)', 'High Season (ISK/day)', 'Peak Season (ISK/day)', 'Peak vs Low Uplift %'];
  const rows = competitors.map(comp => {
    const prices = SEASON_ORDER.map(s => season_summary[s]?.[comp] ?? '');
    const low  = season_summary['low']?.[comp];
    const peak = season_summary['peak']?.[comp];
    const uplift = (low && peak) ? `${Math.round(((peak - low) / low) * 100)}%` : '';
    return [comp, ...prices, uplift];
  });

  downloadCSV(`seasonal_summary_${new Date().toISOString().slice(0,10)}.csv`, [headers, ...rows]);
  showToast('Seasonal summary exported!', 'success');
}

// ── Security helper ────────────────────────────────────────────────────────
function escHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Init ───────────────────────────────────────────────────────────────────
function init() {
  // Set default filter dates
  const pickupEl = document.getElementById('filter-pickup');
  const returnEl = document.getElementById('filter-return');
  if (pickupEl && !pickupEl.value) pickupEl.value = defaultPickup();
  if (returnEl && !returnEl.value) returnEl.value = defaultReturn();

  // Nav click handlers
  document.querySelectorAll('.nav-item').forEach(el => {
    el.addEventListener('click', () => switchTab(el.dataset.tab));
  });

  // Filter change handlers
  ['filter-location', 'filter-pickup', 'filter-return', 'filter-category'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', loadRates);
  });

  // Button handlers
  document.getElementById('btn-scrape')?.addEventListener('click', triggerScrape);
  document.getElementById('btn-check-seo')?.addEventListener('click', triggerSeoCheck);
  document.getElementById('btn-save-settings')?.addEventListener('click', saveSettings);
  document.getElementById('btn-add-location')?.addEventListener('click', addLocation);
  document.getElementById('btn-add-mapping')?.addEventListener('click', addMapping);

  // Load scheduler status
  loadSchedulerStatus();

  // Start on rates tab
  switchTab('rates');
}

document.addEventListener('DOMContentLoaded', init);
