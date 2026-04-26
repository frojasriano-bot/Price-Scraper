/**
 * Blue Rental Intelligence - Dashboard Application
 * All API calls, chart rendering, and UI logic.
 */

'use strict';

// ── Helpers ────────────────────────────────────────────────────────────────
/** Escape special HTML characters to prevent XSS when interpolating into innerHTML. */
function escHtml(str) {
  if (str == null) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

/** Update every element sharing a given ID (the HTML has duplicates in top-bar + tab). */
function setSourceBadge(id, source) {
  const isLive = source === 'live' || source === 'database' || source === 'cached';
  document.querySelectorAll(`#${id}`).forEach(el => {
    el.textContent = isLive ? 'Live Data' : 'Mock Data';
    el.className = `badge ${isLive ? 'badge-green' : 'badge-gray'}`;
    el.style.display = '';
  });
}

function updateScraperWarning(statusData) {
  const strip = document.getElementById('scraper-warning-strip');
  const textEl = document.getElementById('scraper-warning-text');
  if (!strip || !textEl) return;
  const unstable = statusData?.unstable_competitors || [];
  if (!unstable.length) {
    strip.style.display = 'none';
    return;
  }
  const names = unstable.join(', ');
  const plural = unstable.length === 1 ? 'scraper has' : 'scrapers have';
  textEl.textContent = `${names} ${plural} produced errors in recent runs — data may be stale or estimated. Check Settings → Tracked Competitors for details.`;
  strip.style.display = 'flex';
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
  ratesGroup: 'now',   // 'now' | 'trends' | 'seasonal' | 'forward' | 'competitive'
  ratesView: 'list',   // the active view within the current group
  rates: [],
  ratesSource: 'mock',
  ratesHistory: [],
  matrix: null,
  matrixSource: 'mock',
  historyData: null,
  historyCharts: {},        // kept for teardown safety
  historyFocusModel: null,  // canonical model name currently focused in history
  historyFocusChart: null,  // Chart.js instance for the focus panel
  historySource: 'mock',
  historyCategory: '',
  historyModelSearch: '',
  historyCoverage: null,
  ratesSort: { col: null, dir: 'asc' },
  seasonalData: null,
  seasonalChart: null,
  historyMode: false,
  historyEvolutionData: null,
  historyEvolutionChart: null,
  historyEvolutionMonth: null,
  heatmapMode: false,
  heatmapGranularity: 'category',   // 'category' | 'model'
  gapByModelData: null,             // cached response from /seasonal/gap-by-model
  gapByModelCategory: null,         // what category the cache was fetched for
  catalog:            null,           // canonical car catalog (cached from /api/rates/car-catalog)
  timelineModelChart: null,
  lensHistoryChart:   null,
  horizonData: null,
  horizonChart: null,
  horizonCategory: '',
  horizonWeeks: 26,
  bookingChart: null,
  horizonScraping: false,
  horizonModel: '',
  modelHorizonData: null,
  modelHorizonChart: null,
  deltas: {},
  deltasAvailable: false,
  priceChanges: {},
  priceChangesAvailable: false,
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
  insuranceData: null,
};

// ── API helpers ────────────────────────────────────────────────────────────
const API_BASE = '';

async function apiFetch(path, options = {}, timeoutMs = 30000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(API_BASE + path, {
      headers: { 'Content-Type': 'application/json' },
      signal: controller.signal,
      ...options,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Request failed');
    }
    return res.json();
  } catch (err) {
    if (err.name === 'AbortError') throw new Error('Request timed out');
    throw err;
  } finally {
    clearTimeout(timer);
  }
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
  // Reset seasonal history + heatmap modes when leaving the rates tab
  if (state.currentTab === 'rates' && tab !== 'rates') {
    if (state.historyMode) {
      state.historyMode = false;
      document.getElementById('btn-history-mode')?.classList.remove('active');
      const monthSel = document.getElementById('history-month-select');
      if (monthSel) monthSel.style.display = 'none';
      const hc = document.getElementById('history-chart-card');
      if (hc) hc.style.display = 'none';
      const sc = document.getElementById('seasonal-chart-card');
      if (sc) sc.style.display = '';
      const sm = document.getElementById('seasonal-summary-card');
      if (sm) sm.style.display = '';
      const cc = document.getElementById('seasonal-category-card');
      if (cc) cc.style.display = '';
    }
    if (state.heatmapMode) {
      state.heatmapMode = false;
      document.getElementById('btn-heatmap-mode')?.classList.remove('active');
      const hc2 = document.getElementById('heatmap-card');
      if (hc2) hc2.style.display = 'none';
      const sc2 = document.getElementById('seasonal-chart-card');
      if (sc2) sc2.style.display = '';
    }
  }
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
    insurance: 'Insurance Comparison',
    settings: 'Settings',
    guide: 'How to Use',
  };
  document.getElementById('page-title').textContent = titles[tab] || tab;

  // Hide all source badges — each loadX() will re-show its own
  ['rates-source-badge', 'seo-source-badge', 'insurance-source-badge'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
  });

  if (tab === 'rates') loadRates();
  if (tab === 'seo') loadRankings();
  if (tab === 'settings') { loadSettings(); loadScrapeLog(); loadCategoryAudit(); }
  if (tab === 'insurance') loadInsurance();
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

function shortName(c) {
  if (c === 'Go Car Rental') return 'Go Car';
  if (c === 'Go Iceland')    return 'Go Iceland';
  return c.replace(' Car Rental', '').replace(' Iceland', '');
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

function syncDateConstraints() {
  const pickupEl = document.getElementById('filter-pickup');
  const returnEl = document.getElementById('filter-return');
  if (!pickupEl || !returnEl || !pickupEl.value) return;

  // Return date must be at least 1 day after pickup
  const pickupDate = new Date(pickupEl.value + 'T00:00:00');
  const minReturn  = new Date(pickupDate);
  minReturn.setDate(minReturn.getDate() + 1);
  returnEl.min = minReturn.toISOString().slice(0, 10);

  // If current return date is on or before pickup, auto-advance it to pickup + 3 days
  if (returnEl.value && returnEl.value <= pickupEl.value) {
    const autoReturn = new Date(pickupDate);
    autoReturn.setDate(autoReturn.getDate() + 3);
    returnEl.value = autoReturn.toISOString().slice(0, 10);
  }
}

// ── VIEW TOGGLE ────────────────────────────────────────────────────────────
// ── Two-tier Rate Intelligence navigation ─────────────────────────────────

// Which group each view belongs to
const _VIEW_GROUP = {
  'list':            'now',
  'matrix':          'now',
  'history':         'trends',
  'timeline':        'trends',
  'seasonal':        'seasonal',
  'horizon-fwd':     'forward',
  'booking-window':  'forward',
  'win-loss':        'competitive',
  'fleet-pressure':  'competitive',
};

// Default view shown when switching to a group
const _GROUP_DEFAULT = {
  'now':         'list',
  'trends':      'history',
  'seasonal':    'seasonal',
  'forward':     'horizon-fwd',
  'competitive': 'win-loss',
};

// All groups; those with sub-tabs
const _ALL_GROUPS    = ['now', 'trends', 'seasonal', 'forward', 'competitive'];
const _SUBTAB_GROUPS = ['now', 'trends', 'forward', 'competitive'];

function setRatesGroup(group) {
  state.ratesGroup = group;
  _ALL_GROUPS.forEach(g => {
    document.getElementById(`grp-${g}`).classList.toggle('active', g === group);
  });
  _SUBTAB_GROUPS.forEach(g => {
    const el = document.getElementById(`subtabs-${g}`);
    if (el) el.style.display = g === group ? 'flex' : 'none';
  });
  setRatesView(_GROUP_DEFAULT[group]);
}

function setRatesView(view) {
  state.ratesView = view;
  const group = _VIEW_GROUP[view] || 'now';

  // Sync group nav + sub-tab bars whenever the group changes
  if (group !== state.ratesGroup) {
    state.ratesGroup = group;
    _ALL_GROUPS.forEach(g => {
      document.getElementById(`grp-${g}`).classList.toggle('active', g === group);
    });
    _SUBTAB_GROUPS.forEach(g => {
      const el = document.getElementById(`subtabs-${g}`);
      if (el) el.style.display = g === group ? 'flex' : 'none';
    });
  }

  // Show the active view panel, hide the rest
  const VIEW_PANEL_IDS = {
    'list':           'view-list',
    'matrix':         'view-matrix',
    'history':        'view-history',
    'seasonal':       'view-seasonal',
    'horizon-fwd':    'view-horizon-fwd',
    'timeline':       'view-timeline',
    'booking-window': 'view-booking-window',
    'win-loss':       'view-win-loss',
    'fleet-pressure': 'view-fleet-pressure',
  };
  Object.entries(VIEW_PANEL_IDS).forEach(([v, id]) => {
    document.getElementById(id).style.display = v === view ? '' : 'none';
  });

  // Update sub-tab active state
  const SUB_TAB_IDS = {
    'list':           'sub-list',
    'matrix':         'sub-matrix',
    'history':        'sub-history',
    'timeline':       'sub-timeline',
    'horizon-fwd':    'sub-horizon',
    'booking-window': 'sub-booking',
    'win-loss':       'sub-win-loss',
    'fleet-pressure': 'sub-fleet',
  };
  Object.entries(SUB_TAB_IDS).forEach(([v, id]) => {
    const el = document.getElementById(id);
    if (el) el.classList.toggle('active', v === view);
  });

  // Data loading
  if (view === 'matrix'         && !state.matrix)       loadMatrix();
  if (view === 'history')                               loadHistory();
  if (view === 'seasonal'       && !state.seasonalData) loadSeasonal();
  if (view === 'horizon-fwd'    && !state.horizonData)  loadHorizon();
  if (view === 'timeline')                              { loadPeriodSummary(); loadTimeline(); initModelLens(); }
  if (view === 'booking-window')                        initBookingWindow();
  if (view === 'win-loss')                              loadWinLoss();
  if (view === 'fleet-pressure')                        loadFleetPressure();
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



/**
 * Check scheduler status and show the stale-data banner if the last scrape
 * is more than 6 hours old (or has never run). Dismissable by the user.
 */
let _staleDismissed = false;

function dismissStaleBanner() {
  _staleDismissed = true;
  const el = document.getElementById('stale-banner');
  if (el) el.style.display = 'none';
}

async function refreshAllData() {
  const btn   = document.getElementById('btn-refresh-all');
  const msgEl = document.getElementById('stale-banner-msg');
  if (!btn || !msgEl) return;

  btn.disabled = true;
  btn.style.opacity = '0.6';
  btn.style.cursor  = 'not-allowed';

  // Full data refresh sequence — order matters (rates before alerts so
  // alerts fire against fresh data; fleet calendar last as it's slowest)
  const steps = [
    {
      label: 'Scraping current rates…',
      url:   '/api/rates/scrape',
      method: 'POST',
      countField: ['scraped'],
    },
    {
      label: 'Scraping 12-month seasonal anchors…',
      url:   '/api/rates/scrape-seasonal',
      method: 'POST',
      countField: ['scraped'],
    },
    {
      label: 'Scraping 26-week forward horizon…',
      url:   '/api/rates/scrape-horizon',
      method: 'POST',
      countField: ['scraped'],
    },
    {
      label: 'Polling near-term fleet availability…',
      url:   '/api/fleet/poll',
      method: 'POST',
      countField: ['polled'],
    },
    {
      label: 'Running 12-month fleet calendar sweep…',
      url:   '/api/fleet/calendar/poll',
      method: 'POST',
      countField: ['calendar'],
    },
    {
      label: 'Checking price alerts…',
      url:   '/api/alerts/check',
      method: 'POST',
      countField: [],   // fire-and-forget; don't add to rate count
    },
  ];

  let totalRates = 0;
  const errors   = [];

  for (let i = 0; i < steps.length; i++) {
    const step = steps[i];
    msgEl.innerHTML =
      `<span style="margin-right:6px">⏳</span>${step.label} <span style="opacity:.6">(${i + 1}/${steps.length})</span>`;

    try {
      const res = await fetch(step.url, {
        method:  step.method,
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({}),
      });
      if (res.ok) {
        const data = await res.json().catch(() => ({}));
        for (const field of (step.countField || [])) {
          totalRates += data[field] || 0;
        }
      } else {
        errors.push(`step ${i + 1} (${res.status})`);
      }
    } catch (err) {
      errors.push(`step ${i + 1} (network error)`);
      console.warn(`refreshAllData step ${i + 1} failed:`, err);
      // Always continue — a single scraper failure shouldn't block the rest
    }
  }

  // Re-enable button
  btn.disabled = false;
  btn.style.opacity = '';
  btn.style.cursor  = '';

  // Update topbar freshness badge immediately
  checkDataFreshness();

  const rateMsg  = totalRates ? `${totalRates.toLocaleString()} rate records updated.` : 'Data refreshed.';
  const errorMsg = errors.length ? ` (${errors.length} step(s) had errors — check console)` : '';

  msgEl.innerHTML = `<span style="margin-right:6px">✅</span>All scrapers complete! ${rateMsg}${errorMsg}`;
  showToast(`Full refresh done. ${rateMsg}`, 'success');

  // Dismiss banner after 4 s and reload active view
  setTimeout(() => {
    _staleDismissed = true;
    const banner = document.getElementById('stale-banner');
    if (banner) banner.style.display = 'none';
    loadCurrentView();
  }, 4000);
}

/** Reload data for the currently visible view */
function loadCurrentView() {
  // Map view-panel IDs → their load functions
  const viewMap = {
    'view-list':          () => { typeof loadRates         === 'function' && loadRates(); },
    'view-matrix':        () => { typeof loadMatrix       === 'function' && loadMatrix(); },
    'view-history':       () => { typeof loadHistory      === 'function' && loadHistory(); },
    'view-timeline':      () => { typeof loadPeriodSummary === 'function' && loadPeriodSummary(); typeof loadTimeline === 'function' && loadTimeline(); typeof initModelLens === 'function' && initModelLens(); },
    'view-win-loss':      () => { typeof loadWinLoss      === 'function' && loadWinLoss(); },
    'view-fleet-pressure':() => { typeof loadFleetPressure=== 'function' && loadFleetPressure(); },
    'view-seasonal':      () => { typeof loadSeasonal     === 'function' && loadSeasonal(); },
    'view-horizon-fwd':   () => { typeof loadHorizon      === 'function' && loadHorizon(); },
  };
  for (const [panelId, fn] of Object.entries(viewMap)) {
    const el = document.getElementById(panelId);
    if (el && el.style.display !== 'none') {
      try { fn(); } catch (_) {}
      break;
    }
  }
}

async function checkDataFreshness() {
  try {
    // Fetch rates age and fleet age in parallel
    const [schedData, fleetData] = await Promise.all([
      apiFetch('/api/scheduler/status').catch(() => null),
      apiFetch('/api/fleet/pressure/latest').catch(() => null),
    ]);

    // ── Update persistent data-age indicator in the header ────────────────
    const indicator = document.getElementById('data-age-indicator');
    if (indicator) {
      const ratesTs = schedData?.last_scrape_at;
      // Fleet: find the most recent scraped_at across all fleet rows
      const fleetRows = fleetData?.latest || [];
      const fleetTs   = fleetRows.length
        ? fleetRows.reduce((max, r) => (!max || r.scraped_at > max ? r.scraped_at : max), null)
        : null;

      const ratesAge = ratesTs ? (Date.now() - new Date(ratesTs).getTime()) / 3600000 : null;
      const fleetAge = fleetTs ? (Date.now() - new Date(fleetTs).getTime()) / 3600000 : null;

      const ageColor = h => h === null ? '#6b7280' : h < 4 ? '#22c55e' : h < 24 ? '#f59e0b' : '#ef4444';
      const ageLabel = h => h === null ? 'never' : h < 1 ? '<1h ago' : h < 24 ? `${Math.floor(h)}h ago` : `${Math.floor(h/24)}d ago`;

      indicator.innerHTML =
        `<span style="color:${ageColor(ratesAge)}" title="Last rate scrape: ${ratesTs || 'never'}">` +
        `📡 Rates: ${ageLabel(ratesAge)}</span>` +
        (fleetTs
          ? ` <span style="color:var(--text-muted);margin:0 4px">·</span>` +
            `<span style="color:${ageColor(fleetAge)}" title="Last fleet poll: ${fleetTs}">` +
            `🚗 Fleet: ${ageLabel(fleetAge)}</span>`
          : '');
      indicator.style.display = 'inline-flex';
    }

    // ── Stale banner (dismissable, only for seriously old data) ───────────
    if (!_staleDismissed) {
      const banner = document.getElementById('stale-banner');
      const msgEl  = document.getElementById('stale-banner-msg');
      if (!banner || !msgEl) return;

      if (!schedData?.last_scrape_at) {
        msgEl.textContent = 'No rate data has been scraped yet. Trigger a manual scrape or wait for the scheduler to run.';
        banner.style.display = 'flex';
        return;
      }

      const ageHrs = (Date.now() - new Date(schedData.last_scrape_at).getTime()) / 3600000;
      if (ageHrs > 6) {
        const label = ageHrs >= 24
          ? `${Math.floor(ageHrs / 24)}d ${Math.floor(ageHrs % 24)}h`
          : `${Math.floor(ageHrs)}h`;
        msgEl.textContent = `Rate data is ${label} old — last scraped ${timeAgo(schedData.last_scrape_at)}. The scheduler may need attention.`;
        banner.style.display = 'flex';
      } else {
        banner.style.display = 'none';
      }
    }
  } catch (_) {
    // Not critical — silently ignore
  }
}

// ── PRICE HISTORY VIEW ─────────────────────────────────────────────────────
// Per-competitor colour palette (used in focus chart + coverage chips)
const COMPETITOR_COLORS = {
  'Blue Car Rental':   '#3b82f6',   // blue
  'Lotus Car Rental':  '#f59e0b',   // amber
  'Go Car Rental':     '#10b981',   // emerald
  'Hertz Iceland':     '#f97316',   // orange
  'Avis Iceland':      '#ef4444',   // red
  'Holdur':            '#8b5cf6',   // purple
  'Europcar Iceland':  '#06b6d4',   // cyan
  'Go Iceland':        '#15803d',   // dark green
};
const COMPETITOR_COLORS_DEFAULT = '#9ca3af';

const MODEL_COLORS = [
  '#3b82f6','#ef4444','#22c55e','#f59e0b','#8b5cf6',
  '#06b6d4','#f97316','#15803d','#10b981','#eab308',
  '#6366f1','#14b8a6','#f43f5e','#a855f7','#84cc16',
  '#0ea5e9','#fb923c','#e879f9','#34d399','#fbbf24',
  '#818cf8','#2dd4bf','#fb7185','#c084fc','#a3e635',
];

const CATEGORY_ICONS = {
  'Economy': '🚗', 'Compact': '🚙', 'SUV': '🛻', '4x4': '🏔️', 'Minivan': '🚐',
};

async function loadHistory() {
  const location = document.getElementById('filter-location').value;
  const days     = document.getElementById('history-days').value;

  const params = new URLSearchParams({ days });
  if (location) params.set('location', location);

  try {
    const [result, coverageResult] = await Promise.all([
      apiFetch(`/api/rates/history/models?${params}`),
      apiFetch(`/api/rates/history/coverage?${params}`).catch(() => null),
    ]);
    state.historyData     = result.data      || {};
    state.historySource   = result.source    || 'mock';
    state.historyCoverage = coverageResult?.coverage || null;
    setSourceBadge('history-source-badge', state.historySource);
    // Reset focus when data reloads
    closeFocusPanel();
    renderModelNavigator();
  } catch (e) {
    showToast(`Failed to load price history: ${e.message}`, 'error');
  }
}

// ── HISTORY FILTER HANDLERS ────────────────────────────────────────────────
function setHistoryCategory(cat) {
  state.historyCategory = cat;
  ['', 'Economy', 'Compact', 'SUV', '4x4', 'Minivan'].forEach(c => {
    const btn = document.getElementById(`hcat-btn-${c}`);
    if (btn) btn.classList.toggle('active', c === cat);
  });
  renderModelNavigator();
}

function filterHistoryModels(query) {
  state.historyModelSearch = query.trim().toLowerCase();
  renderModelNavigator();
}

function closeFocusPanel() {
  const empty  = document.getElementById('history-focus-empty');
  const active = document.getElementById('history-focus-active');
  if (empty)  empty.style.display  = 'flex';
  if (active) active.style.display = 'none';
  if (state.historyFocusChart) {
    state.historyFocusChart.destroy();
    state.historyFocusChart = null;
  }
  state.historyFocusModel = null;
  document.querySelectorAll('.history-model-row').forEach(r => {
    r.classList.remove('selected');
    r.style.background  = '';
    r.style.borderLeft  = '';
  });
}

// ── MODEL NAVIGATOR ────────────────────────────────────────────────────────
function renderModelNavigator() {
  const container = document.getElementById('history-model-list');
  if (!container) return;

  const CATEGORY_ORDER = ['Economy', 'Compact', 'SUV', '4x4', 'Minivan'];
  const data        = state.historyData    || {};
  const coverage    = state.historyCoverage || {};
  const modelSearch = state.historyModelSearch || '';

  let categories = CATEGORY_ORDER.filter(c => data[c] && Object.keys(data[c]).length > 0);
  if (state.historyCategory) categories = categories.filter(c => c === state.historyCategory);

  if (categories.length === 0) {
    container.innerHTML = '<div style="padding:24px;text-align:center;color:#6b7280;font-size:13px">No data available.</div>';
    renderTopMovers([]);
    return;
  }

  let html = '';
  const allModelsForMovers = [];

  categories.forEach((cat, catIdx) => {
    const catData    = data[cat];
    const catCov     = coverage[cat] || {};
    const icon       = CATEGORY_ICONS[cat] || '🚗';

    const models = Object.entries(catData).filter(([name]) =>
      !modelSearch || name.toLowerCase().includes(modelSearch)
    );
    if (models.length === 0) return;

    // Category header
    html += `<div style="padding:7px 12px 5px;font-size:10px;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:.07em;background:rgba(255,255,255,0.03);border-bottom:1px solid rgba(255,255,255,0.05)${catIdx > 0 ? ';border-top:1px solid rgba(255,255,255,0.05)' : ''}">${icon} ${cat}</div>`;

    models.forEach(([modelName, series]) => {
      if (!series || series.length === 0) return;
      const latestPrice = series[series.length - 1].avg_price;
      const firstPrice  = series[0].avg_price;
      const changePct   = firstPrice > 0 ? (latestPrice - firstPrice) / firstPrice * 100 : 0;
      const compCount   = (catCov[modelName] || []).length;
      const changeColor = changePct > 2 ? '#f87171' : changePct < -2 ? '#4ade80' : '#9ca3af';
      const changeSign  = changePct > 0 ? '+' : '';
      const changeLabel = Math.abs(changePct) < 0.5 ? '—' : `${changeSign}${changePct.toFixed(1)}%`;
      const isSelected  = state.historyFocusModel === modelName;

      allModelsForMovers.push({ modelName, cat, changePct, latestPrice, compCount });

      html += `<div class="history-model-row${isSelected ? ' selected' : ''}"
          data-model="${escHtml(modelName)}" data-cat="${escHtml(cat)}"
          onclick="focusHistoryModel(this.dataset.model, this.dataset.cat)"
          style="display:flex;align-items:center;justify-content:space-between;padding:9px 12px;cursor:pointer;border-bottom:1px solid rgba(255,255,255,0.04);gap:8px;transition:background .12s;${isSelected ? 'background:rgba(59,130,246,0.15);border-left:3px solid #3b82f6;' : ''}"
          onmouseover="if(!this.classList.contains('selected'))this.style.background='rgba(255,255,255,0.04)'"
          onmouseout="if(!this.classList.contains('selected'))this.style.background=''">
        <div style="flex:1;min-width:0">
          <div style="font-size:13px;font-weight:500;color:#e5e7eb;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${modelName}">${modelName}</div>
          <div style="font-size:11px;color:#6b7280;margin-top:1px">${compCount} competitor${compCount !== 1 ? 's' : ''}</div>
        </div>
        <div style="text-align:right;flex-shrink:0">
          <div style="font-size:12px;font-weight:600;color:#d1d5db">${(latestPrice / 1000).toFixed(1)}k</div>
          <div style="font-size:11px;color:${changeColor}">${changeLabel}</div>
        </div>
      </div>`;
    });
  });

  container.innerHTML = html || `<div style="padding:20px;text-align:center;color:#6b7280;font-size:13px">No models match "<strong>${modelSearch}</strong>".</div>`;
  renderTopMovers(allModelsForMovers);
}

function renderTopMovers(models) {
  const el = document.getElementById('history-top-movers');
  if (!el) return;
  if (!models || models.length === 0) { el.innerHTML = ''; return; }

  const sorted = [...models].sort((a, b) => Math.abs(b.changePct) - Math.abs(a.changePct));
  const top = sorted.slice(0, 5).filter(m => Math.abs(m.changePct) >= 0.5);
  if (top.length === 0) { el.innerHTML = ''; return; }

  const rows = top.map(m => {
    const sign  = m.changePct > 0 ? '+' : '';
    const color = m.changePct > 2 ? '#f87171' : m.changePct < -2 ? '#4ade80' : '#9ca3af';
    return `<div data-model="${escHtml(m.modelName)}" data-cat="${escHtml(m.cat)}"
      onclick="focusHistoryModel(this.dataset.model, this.dataset.cat)"
      style="display:flex;justify-content:space-between;align-items:center;padding:6px 10px;cursor:pointer;border-radius:6px;background:rgba(255,255,255,0.04);transition:background .12s"
      onmouseover="this.style.background='rgba(59,130,246,0.1)'" onmouseout="this.style.background='rgba(255,255,255,0.04)'">
      <span style="font-size:12px;color:#d1d5db">${m.modelName}</span>
      <span style="font-size:12px;font-weight:600;color:${color}">${sign}${m.changePct.toFixed(1)}%</span>
    </div>`;
  }).join('');

  el.innerHTML = `<div style="text-align:left;border-top:1px solid rgba(255,255,255,0.07);padding-top:12px;margin-top:4px">
    <div style="font-size:11px;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px">Top movers this period</div>
    <div style="display:flex;flex-direction:column;gap:4px">${rows}</div>
  </div>`;
}

// ── FOCUS CHART ────────────────────────────────────────────────────────────
async function focusHistoryModel(modelName, cat) {
  state.historyFocusModel = modelName;

  // Highlight the selected row in the navigator
  document.querySelectorAll('.history-model-row').forEach(row => {
    const nameEl  = row.querySelector('[title]');
    const isThis  = nameEl && nameEl.getAttribute('title') === modelName;
    row.classList.toggle('selected', isThis);
    row.style.background = isThis ? 'rgba(59,130,246,0.15)' : '';
    row.style.borderLeft = isThis ? '3px solid #3b82f6' : '';
  });

  // Show active focus panel
  const emptyEl  = document.getElementById('history-focus-empty');
  const activeEl = document.getElementById('history-focus-active');
  if (emptyEl)  emptyEl.style.display  = 'none';
  if (activeEl) activeEl.style.display = 'block';

  // Header
  const days = document.getElementById('history-days').value;
  const nameEl = document.getElementById('focus-model-name');
  const metaEl = document.getElementById('focus-model-meta');
  if (nameEl) nameEl.textContent = modelName;
  if (metaEl) metaEl.textContent = `${CATEGORY_ICONS[cat] || ''} ${cat} · Last ${days} days`;

  // Coverage chips (from cached coverage data)
  const coverageList = (state.historyCoverage?.[cat] || {})[modelName] || [];
  const covEl = document.getElementById('focus-coverage');
  if (covEl) {
    if (coverageList.length > 0) {
      covEl.innerHTML = coverageList.map(c => {
        const color = COMPETITOR_COLORS[c] || COMPETITOR_COLORS_DEFAULT;
        return `<span style="display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:500;background:${color}22;border:1px solid ${color}55;color:${color}">
          <span style="width:6px;height:6px;border-radius:50%;background:${color};flex-shrink:0"></span>${c}
        </span>`;
      }).join('');
    } else {
      covEl.innerHTML = '<span style="color:#6b7280;font-size:12px">Coverage data unavailable</span>';
    }
  }

  // Fetch per-competitor price detail
  const location = document.getElementById('filter-location').value;
  const params   = new URLSearchParams({ model: modelName, days });
  if (location) params.set('location', location);

  try {
    const result = await apiFetch(`/api/rates/history/model-detail?${params}`);
    renderFocusChart(result.data || {});
  } catch (e) {
    showToast(`Could not load detail for ${modelName}: ${e.message}`, 'error');
  }
}

function renderFocusChart(competitorData) {
  if (state.historyFocusChart) {
    state.historyFocusChart.destroy();
    state.historyFocusChart = null;
  }
  const canvas = document.getElementById('history-focus-chart');
  if (!canvas) return;

  // Collect all unique dates across all competitors
  const dateSet = new Set();
  Object.values(competitorData).forEach(series => series.forEach(pt => dateSet.add(pt.date)));
  const allDates = Array.from(dateSet).sort();

  const datasets = Object.entries(competitorData).map(([comp, series]) => {
    const color  = COMPETITOR_COLORS[comp] || COMPETITOR_COLORS_DEFAULT;
    const byDate = Object.fromEntries(series.map(pt => [pt.date, pt.avg_price]));
    return {
      label:           comp,
      data:            allDates.map(d => byDate[d] ?? null),
      borderColor:     color,
      backgroundColor: color + '18',
      borderWidth:     2.5,
      pointRadius:     allDates.length <= 14 ? 4 : 2,
      pointHoverRadius: 6,
      tension:         0.3,
      spanGaps:        true,
      fill:            false,
    };
  });

  state.historyFocusChart = new Chart(canvas.getContext('2d'), {
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
          grid:  { color: 'rgba(255,255,255,0.05)' },
        },
        y: {
          ticks: {
            color: '#9ca3af',
            font:  { size: 11 },
            callback: v => (v / 1000).toFixed(0) + 'k',
          },
          grid: { color: 'rgba(255,255,255,0.07)' },
        },
      },
    },
  });
}

// ── SEASONAL ANALYSIS ──────────────────────────────────────────────────────
const SEASON_COLORS = {
  low:      'rgba(59,130,246,0.08)',
  shoulder: 'rgba(245,158,11,0.11)',
  high:     'rgba(239,68,68,0.07)',
  peak:     'rgba(239,68,68,0.15)',
};

// Brand colours — keyed by competitor name (case-sensitive, must match DB values)
const BRAND_COLORS = {
  'Avis Iceland':    '#ef4444',   // Avis red
  'Blue Car Rental': '#2563eb',   // Blue blue
  'Go Car Rental':   '#f97316',   // Go orange
  'Go Iceland':      '#15803d',   // Go Iceland dark green
  'Hertz Iceland':   '#eab308',   // Hertz yellow
  'Holdur':          '#22c55e',   // Holdur green
  'Lava Car Rental': '#a855f7',   // Lava purple
  'Lotus Car Rental':'#881337',   // Lotus maroon
};
const COMP_PALETTE = [
  '#2563eb','#ef4444','#22c55e','#eab308','#a855f7','#f97316','#881337',
];

function compColor(name, fallbackIndex = 0) {
  return BRAND_COLORS[name] || COMP_PALETTE[fallbackIndex % COMP_PALETTE.length];
}

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

    // Show note if any months were skipped (15th already past)
    const skipNote = document.getElementById('seasonal-skip-note');
    if (skipNote) {
      const skipped = data.skipped_months || [];
      skipNote.textContent = skipped.length
        ? `ℹ️ ${skipped.join(', ')} skipped — the 15th of that month has already passed.`
        : '';
      skipNote.style.display = skipped.length ? '' : 'none';
    }

    renderSeasonalChart();
    renderSeasonalTable();
    renderSeasonalCategoryTable();
  } catch (e) {
    showToast(`Failed to load seasonal data: ${e.message}`, 'error');
  } finally {
    if (loadingEl) loadingEl.style.display = 'none';
  }
}

function onSeasonalCategoryChange() {
  if (state.historyMode) {
    loadHistoryData(state.historyEvolutionMonth);
    return;
  }
  if (state.heatmapMode && state.heatmapGranularity === 'model') {
    // Model-level Gap Map is driven by this filter — refetch for the new category
    state.gapByModelData     = null;
    state.gapByModelCategory = null;
    loadGapByModel();
    return;
  }
  renderSeasonalChart();
  renderSeasonalTable();
  renderSeasonalCategoryTable();
}

async function scrapeSeasonalAnchors() {
  const btn = document.getElementById('btn-scrape-seasonal');
  if (!btn) return;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner" style="border-color:rgba(0,0,0,.2);border-top-color:#2563eb;width:11px;height:11px;display:inline-block"></span> Scraping…';
  const loadingEl = document.getElementById('seasonal-loading');
  if (loadingEl) loadingEl.style.display = 'flex';

  try {
    const data = await apiFetch('/api/rates/scrape-seasonal', { method: 'POST' });
    const skipNote = (data.skipped_months?.length)
      ? ` (${data.skipped_months.join(', ')} skipped — 15th already passed)`
      : '';
    showToast(`Scraped ${data.scraped.toLocaleString()} rates across ${data.months_scraped} months in ${data.duration_seconds}s.${skipNote}`, 'success');
    // Invalidate cached seasonal data so next load reads fresh DB results
    state.seasonalData = null;
    await loadSeasonal(true);
  } catch (e) {
    showToast(`Seasonal scrape failed: ${e.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="width:13px;height:13px"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg> Scrape All';
    if (loadingEl) loadingEl.style.display = 'none';
  }
}

function toggleHistoryMode() {
  state.historyMode = !state.historyMode;
  const btn          = document.getElementById('btn-history-mode');
  const monthSel     = document.getElementById('history-month-select');
  const overviewCard = document.getElementById('seasonal-chart-card');
  const heatmapCard  = document.getElementById('heatmap-card');
  const historyCard  = document.getElementById('history-chart-card');
  const summaryCard  = document.getElementById('seasonal-summary-card');
  const catCard      = document.getElementById('seasonal-category-card');

  if (state.historyMode) {
    // Exit heatmap mode if active
    if (state.heatmapMode) {
      state.heatmapMode = false;
      document.getElementById('btn-heatmap-mode')?.classList.remove('active');
      if (heatmapCard) heatmapCard.style.display = 'none';
    }

    btn.classList.add('active');
    monthSel.style.display     = '';
    overviewCard.style.display = 'none';
    historyCard.style.display  = '';
    if (summaryCard) summaryCard.style.display = 'none';
    if (catCard)     catCard.style.display     = 'none';

    // Populate month selector from loaded seasonal data
    if (state.seasonalData?.months) {
      monthSel.innerHTML = '<option value="">Select a month…</option>' +
        state.seasonalData.months.map(m =>
          `<option value="${m.month}">${m.month_label}</option>`
        ).join('');
    }

    // If a month was previously selected, reload it
    if (state.historyEvolutionMonth) {
      monthSel.value = state.historyEvolutionMonth;
      loadHistoryData(state.historyEvolutionMonth);
    }
  } else {
    btn.classList.remove('active');
    monthSel.style.display     = 'none';
    historyCard.style.display  = 'none';
    if (summaryCard) summaryCard.style.display = '';
    if (catCard)     catCard.style.display     = '';
    // Only restore overview chart if heatmap mode is not active
    if (!state.heatmapMode) {
      overviewCard.style.display = '';
      renderSeasonalChart();
    }
    renderSeasonalTable();
    renderSeasonalCategoryTable();
  }
}

function onHistoryMonthChange() {
  const sel   = document.getElementById('history-month-select');
  const month = sel?.value;
  if (!month) return;
  state.historyEvolutionMonth = month;
  loadHistoryData(month);
}

async function loadHistoryData(monthStr) {
  if (!monthStr) return;

  const category  = document.getElementById('seasonal-category')?.value || '';
  const pickupDate = monthStr + '-15';
  const titleEl   = document.getElementById('history-chart-title');
  const loadingEl = document.getElementById('history-loading');
  const noDataEl  = document.getElementById('history-no-data');
  const canvas    = document.getElementById('history-chart');

  if (titleEl) {
    const label = state.seasonalData?.months?.find(m => m.month === monthStr)?.month_label || monthStr;
    titleEl.textContent = `${label} — Price Evolution${category ? ' · ' + category : ''}`;
  }
  if (loadingEl) loadingEl.style.display = 'flex';
  if (noDataEl)  noDataEl.style.display  = 'none';
  if (canvas)    canvas.style.display    = '';

  try {
    const params = new URLSearchParams({ pickup_date: pickupDate });
    if (category) params.set('category', category);
    const data = await apiFetch(`/api/rates/seasonal/history?${params}`);
    state.historyEvolutionData = data;
    renderHistoryChart();
  } catch (e) {
    showToast(`Failed to load history: ${e.message}`, 'error');
  } finally {
    if (loadingEl) loadingEl.style.display = 'none';
  }
}

function renderHistoryChart() {
  const canvas   = document.getElementById('history-chart');
  const noDataEl = document.getElementById('history-no-data');
  const data     = state.historyEvolutionData;
  if (!canvas || !data) return;

  const series    = data.series || {};
  const compNames = Object.keys(series).sort();

  // Collect all unique scrape dates across all competitors
  const allDates = [...new Set(
    compNames.flatMap(c => series[c].map(pt => pt.date))
  )].sort();

  // Need at least 2 dates to show a trend
  if (allDates.length < 2) {
    canvas.style.display   = 'none';
    if (noDataEl) {
      const msgEl = document.getElementById('history-no-data-msg');
      if (msgEl) {
        msgEl.textContent = allDates.length === 0
          ? 'No prices scraped for this anchor month yet — click Scrape All to collect data.'
          : 'Only one scrape on record for this month — need at least 2 weekly snapshots to show a trend.';
      }
      noDataEl.style.display = '';
    }
    return;
  }
  canvas.style.display = '';
  if (noDataEl) noDataEl.style.display = 'none';

  const category = document.getElementById('seasonal-category')?.value || '';

  // Build datasets — one line per competitor
  // When no category filter: average across categories per date
  const datasets = compNames.map((comp, i) => {
    const pts = series[comp];
    const byDate = {};
    pts.forEach(pt => {
      if (!byDate[pt.date]) byDate[pt.date] = [];
      byDate[pt.date].push(pt.avg_per_day);
    });
    const chartData = allDates.map(d => {
      const vals = byDate[d];
      if (!vals) return null;
      return Math.round(vals.reduce((a, b) => a + b, 0) / vals.length);
    });
    const color = compColor(comp, i);
    return {
      label:           comp,
      data:            chartData,
      borderColor:     color,
      backgroundColor: color + '18',
      borderWidth:     2,
      pointRadius:     5,
      pointHoverRadius: 7,
      tension:         0.3,
      spanGaps:        true,
      fill:            false,
    };
  });

  if (state.historyEvolutionChart) state.historyEvolutionChart.destroy();

  state.historyEvolutionChart = new Chart(canvas, {
    type: 'line',
    data: {
      labels: allDates.map(d => {
        const dt = new Date(d + 'T12:00:00Z');
        return dt.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
      }),
      datasets,
    },
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
            title: items => `Scraped on ${items[0].label}`,
            label: ctx => ctx.parsed.y !== null
              ? ` ${ctx.dataset.label}: ${formatISK(ctx.parsed.y)}/day`
              : null,
          },
        },
      },
      scales: {
        x: {
          ticks:  { color: '#6b7280', font: { size: 11 } },
          grid:   { color: 'rgba(0,0,0,0.06)' },
          title:  { display: true, text: 'Scrape Date', font: { size: 11 }, color: '#9ca3af' },
        },
        y: {
          ticks: {
            color: '#6b7280',
            font: { size: 11 },
            callback: v => (v / 1000).toFixed(0) + 'k ISK',
          },
          grid:  { color: 'rgba(0,0,0,0.06)' },
          title: { display: true, text: 'Per-Day Price (ISK)', font: { size: 11 }, color: '#9ca3af' },
        },
      },
    },
  });
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
    const color = compColor(comp, i);
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

  // Compute each competitor's overall average across seasons with data
  function compAvg(name) {
    const vals = SEASON_ORDER.map(s => activeSummary[s]?.[name]).filter(v => v != null);
    return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
  }
  const blueAvg = compAvg('Blue Car Rental');

  tbody.innerHTML = compNames.map(comp => {
    const prices = SEASON_ORDER.map(s => activeSummary[s]?.[comp] ?? null);

    let vsBlue = '—';
    let vsBlueClass = 'color:#6b7280';
    if (comp === 'Blue Car Rental') {
      vsBlue = 'base';
    } else {
      const avg = compAvg(comp);
      if (avg != null && blueAvg != null) {
        const pct = Math.round((avg / blueAvg - 1) * 100);
        vsBlue = (pct >= 0 ? '+' : '') + pct + '%';
        vsBlueClass = pct > 0 ? 'color:#16a34a;font-weight:700'   // competitor more expensive = good for Blue
                    : pct < 0 ? 'color:#dc2626;font-weight:700'   // competitor cheaper = bad for Blue
                    : 'color:#6b7280';
      }
    }

    const cells = SEASON_ORDER.map((s, i) => {
      const p = prices[i];
      if (!p) return `<td style="text-align:center;color:#d1d5db">—</td>`;
      return `<td class="season-cell season-cell-${s}" style="text-align:center">
        <div style="font-weight:700;font-size:14px">${formatISK(p)}</div>
        <div style="font-size:10px;color:#9ca3af">/day</div>
      </td>`;
    }).join('');

    return `<tr>
      <td><strong>${escHtml(comp)}</strong></td>
      ${cells}
      <td style="text-align:center;font-size:13px;${vsBlueClass}">${vsBlue}</td>
    </tr>`;
  }).join('');
}

function renderSeasonalCategoryTable() {
  const tbody = document.getElementById('seasonal-category-tbody');
  if (!tbody || !state.seasonalData) return;

  const { category_season_summary, months } = state.seasonalData;
  const SEASON_ORDER = ['low', 'shoulder', 'high', 'peak'];
  const CAT_ORDER = ['Economy', 'Compact', 'SUV', '4x4', 'Minivan'];

  // Build Blue Car Rental's per-category average per season from monthly data
  const blueBuckets = {};  // season → category → [prices]
  (months || []).forEach(m => {
    const s = m.season;
    const blueCats = m.competitors?.['Blue Car Rental'] || {};
    Object.entries(blueCats).forEach(([cat, price]) => {
      if (price == null) return;
      blueBuckets[s] = blueBuckets[s] || {};
      blueBuckets[s][cat] = blueBuckets[s][cat] || [];
      blueBuckets[s][cat].push(price);
    });
  });
  // Average per season per category for Blue
  const blueSeasonCat = {};
  Object.entries(blueBuckets).forEach(([s, cats]) => {
    blueSeasonCat[s] = {};
    Object.entries(cats).forEach(([cat, vals]) => {
      blueSeasonCat[s][cat] = vals.reduce((a, b) => a + b, 0) / vals.length;
    });
  });
  // Blue's overall average per category (across all seasons with data)
  function blueAvgForCat(cat) {
    const vals = SEASON_ORDER.map(s => blueSeasonCat[s]?.[cat]).filter(v => v != null);
    return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
  }

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

    // vs Blue: market average for this category vs Blue's average for same category
    let vsBlue = '—';
    let vsBlueClass = 'color:#6b7280';
    const marketAvg = prices.filter(v => v != null);
    const marketMean = marketAvg.length ? marketAvg.reduce((a, b) => a + b, 0) / marketAvg.length : null;
    const blueMean = blueAvgForCat(cat);
    if (marketMean != null && blueMean != null) {
      const pct = Math.round((marketMean / blueMean - 1) * 100);
      vsBlue = (pct >= 0 ? '+' : '') + pct + '%';
      vsBlueClass = pct > 0 ? 'color:#16a34a;font-weight:700'   // market more expensive = Blue cheaper
                  : pct < 0 ? 'color:#dc2626;font-weight:700'   // market cheaper = Blue more expensive
                  : 'color:#6b7280';
    }

    const cells = SEASON_ORDER.map((s, i) => {
      const p = prices[i];
      if (!p) return `<td style="text-align:center;color:#d1d5db">—</td>`;
      return `<td class="season-cell season-cell-${s}" style="text-align:center">
        <div style="font-weight:700;font-size:14px">${formatISK(p)}</div>
        <div style="font-size:10px;color:#9ca3af">/day</div>
      </td>`;
    }).join('');

    return `<tr>
      <td><strong>${escHtml(cat)}</strong></td>
      ${cells}
      <td style="text-align:center;font-size:13px;${vsBlueClass}">${vsBlue}</td>
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

    const [ratesData, deltasData, changesData, scraperStatus] = await Promise.all([
      apiFetch(`/api/rates?${params}`),
      apiFetch(`/api/rates/deltas?${deltaParams}`).catch(() => ({ deltas: {}, available: false })),
      apiFetch(`/api/rates/price-changes?${deltaParams}`).catch(() => ({ changes: {}, available: false })),
      apiFetch('/api/rates/scraper-status').catch(() => null),
    ]);
    state.rates               = ratesData.rates || [];
    state.ratesSource         = ratesData.source;
    state.deltas              = deltasData.deltas || {};
    state.deltasAvailable     = deltasData.available || false;
    state.priceChanges        = changesData.changes || {};
    state.priceChangesAvailable = changesData.available || false;
    renderRatesTable();
    renderRateChart();
    updateStatusTiles(scraperStatus);
    renderExecutiveSummary();
    updateScraperWarning(scraperStatus);
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

    // Delta indicator — use per-competitor price change if available, else market-avg delta
    const compKey = `${r.competitor}::${r.location}::${r.canonical_name || r.car_model}`;
    const marketKey = r.canonical_name || r.car_model;
    const d = state.priceChangesAvailable
      ? (state.priceChanges[compKey] || state.priceChanges[marketKey] || state.deltas[marketKey])
      : state.deltas[marketKey];
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
      <td><span class="badge badge-blue" style="white-space:nowrap">${escHtml(r.car_category)}</span></td>
      <td class="${priceClass}">${formatISK(r.price_isk)}</td>
      <td>${formatISK(r._per_day)}/day</td>
      <td style="text-align:center;font-size:12px;font-weight:600">${deltaHtml}</td>
      <td><span class="badge badge-gray" style="white-space:nowrap">${escHtml(r.location)}</span></td>
      <td style="color:#6b7280;font-size:12px">${timeAgo(r.scraped_at)}</td>
    </tr>`;
  }).join('');
}

// ── Matrix category filter state ─────────────────────────────────────────────
let _matrixCat = '';

function setMatrixCat(cat) {
  _matrixCat = cat;
  ['all', 'Economy', 'Compact', 'SUV', '4x4', 'Minivan'].forEach(c => {
    const el = document.getElementById(`mcat-${c === '' ? 'all' : c}`);
    if (el) el.classList.toggle('active', (cat === '' ? '' : cat) === (c === 'all' ? '' : c));
  });
  renderMatrix();
}

function renderMatrix() {
  const wrap = document.getElementById('matrix-table-wrap');
  const data = state.matrix;
  if (!data || !data.cars || !data.cars.length) {
    wrap.innerHTML = `<p style="padding:40px;text-align:center;color:#6b7280">No data. Click "Scrape Now" to fetch rates.</p>`;
    return;
  }

  setSourceBadge('matrix-source-badge', state.matrixSource);

  // ── Info paragraph ─────────────────────────────────────────────────────────
  const infoEl = document.getElementById('matrix-info');
  if (infoEl) {
    const pickup = document.getElementById('filter-pickup')?.value;
    const ret    = document.getElementById('filter-return')?.value;

    // Collect all scraped_at timestamps from every cell
    const allScrapedAt = [];
    for (const car of data.cars) {
      for (const cell of Object.values(car.prices || {})) {
        if (cell?.scraped_at) allScrapedAt.push(new Date(cell.scraped_at));
      }
    }
    allScrapedAt.sort((a, b) => b - a); // newest first
    const newestScrape  = allScrapedAt[0] || null;
    const oldestScrape  = allScrapedAt[allScrapedAt.length - 1] || null;

    // Format dates nicely
    const fmtDate = d => d
      ? d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
      : '—';
    const fmtTime = d => d
      ? d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
      : '';

    // Rental window description
    let windowDesc = '';
    if (pickup && ret) {
      const pDate = new Date(pickup);
      const rDate = new Date(ret);
      const nights = Math.round((rDate - pDate) / 86400000);
      windowDesc = `Rental window: <strong>${fmtDate(pDate)} → ${fmtDate(rDate)}</strong> (${nights} night${nights !== 1 ? 's' : ''}).`;
    } else {
      windowDesc = `Showing <strong>latest available data</strong> — no specific rental window selected. Use the date filters above to price a particular trip.`;
    }

    // Scrape freshness description
    let scrapeDesc = '';
    if (newestScrape) {
      const ageMs  = Date.now() - newestScrape.getTime();
      const ageHrs = ageMs / 3600000;
      const ageLabel = ageHrs < 1
        ? `${Math.round(ageMs / 60000)} min ago`
        : ageHrs < 24
          ? `${Math.round(ageHrs)}h ago`
          : `${Math.round(ageHrs / 24)}d ago`;
      scrapeDesc = `Most recent price scraped <strong>${ageLabel}</strong> (${fmtDate(newestScrape)} at ${fmtTime(newestScrape)}).`;
      if (oldestScrape && (newestScrape - oldestScrape) > 3600000) {
        // There's meaningful age spread across the data
        scrapeDesc += ` Some prices date back to ${fmtDate(oldestScrape)} — cells highlighted in amber are older than 7 days.`;
      }
    } else {
      scrapeDesc = state.matrixSource === 'mock'
        ? `Prices are <strong>simulated demo data</strong> — run a scrape to get live competitor prices.`
        : `Scrape timestamp unavailable.`;
    }

    // How it works blurb
    const howDesc = `Each cell shows the lowest total price found for that car model per competitor, converted to ISK. <strong>Δ%</strong> is the deviation from the market average across all competitors for that model. The <strong>rank chip</strong> shows Blue's position from cheapest (#1) to most expensive.`;

    infoEl.innerHTML = `
      <div style="display:flex;flex-wrap:wrap;gap:12px 24px">
        <span>📅 ${windowDesc}</span>
        <span>🕐 ${scrapeDesc}</span>
        <span style="color:var(--text-muted)">ℹ️ ${howDesc}</span>
      </div>`;
    infoEl.style.display = '';
  }
  // ── End info paragraph ────────────────────────────────────────────────────

  const { competitors } = data;
  const blueOnly  = document.getElementById('matrix-blue-only')?.checked ?? false;
  const showStale = document.getElementById('matrix-show-stale')?.checked ?? true;
  const nowMs     = Date.now();
  const STALE_MS  = 7 * 24 * 3600 * 1000; // 7 days

  // Filter cars
  let cars = data.cars;
  if (_matrixCat)  cars = cars.filter(c => c.category === _matrixCat);
  if (blueOnly)    cars = cars.filter(c => c.prices['Blue Car Rental']);

  if (!cars.length) {
    wrap.innerHTML = `<p style="padding:40px;text-align:center;color:#6b7280">No models match the current filters.</p>`;
    return;
  }

  const BLUE = 'Blue Car Rental';

  // Reorder: Blue first, then others alphabetically
  const orderedComps = [BLUE, ...competitors.filter(c => c !== BLUE)];

  // Header
  const headerCells = orderedComps.map(comp => {
    const isBlue = comp === BLUE;
    return `<th style="text-align:center;min-width:110px;padding:10px 8px;${isBlue ? 'background:rgba(37,99,235,.07);border-bottom:2px solid #2563eb' : ''}">
      <div style="font-size:12px;font-weight:700;${isBlue ? 'color:#2563eb' : ''}">${escHtml(shortName(comp))}</div>
      ${isBlue ? '<div style="font-size:9px;font-weight:600;color:#2563eb;letter-spacing:.06em;text-transform:uppercase">YOU</div>' : ''}
    </th>`;
  }).join('');

  // Rows
  const CAT_EMOJI = { Economy:'🚗', Compact:'🚙', SUV:'🛻', '4x4':'🏔️', Minivan:'🚐' };
  let lastCat = '';
  const rows = cars.map(car => {
    // Category divider
    let divider = '';
    if (!_matrixCat && car.category !== lastCat) {
      lastCat = car.category;
      const catCars = data.cars.filter(c => c.category === car.category);
      const catWithBlue = catCars.filter(c => c.prices[BLUE]).length;
      divider = `<tr>
        <td colspan="${2 + orderedComps.length}" style="padding:8px 14px 5px;font-size:11px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.06em;background:var(--bg-alt);border-top:2px solid var(--border)">
          ${CAT_EMOJI[car.category] || ''} ${car.category}
          <span style="font-weight:400;margin-left:8px">${catCars.length} models · ${catWithBlue} with Blue price</span>
        </td>
      </tr>`;
    }

    // Compute market avg from all valid prices
    const allPrices = orderedComps.map(c => car.prices[c]?.price_isk).filter(Boolean);
    const marketAvg = allPrices.length ? Math.round(allPrices.reduce((a,b)=>a+b,0)/allPrices.length) : null;

    // Blue rank among all with prices (cheapest = 1)
    const sorted = orderedComps
      .filter(c => car.prices[c])
      .sort((a,b) => car.prices[a].price_isk - car.prices[b].price_isk);
    const blueRank = car.prices[BLUE] ? sorted.indexOf(BLUE) + 1 : null;
    const totalWithPrice = sorted.length;

    // Blue rank chip
    let rankChip = '';
    if (blueRank !== null) {
      const rc = blueRank === 1 ? '#16a34a' : blueRank <= 2 ? '#ca8a04' : '#dc2626';
      const rl = blueRank === 1 ? '🥇 #1' : `#${blueRank}/${totalWithPrice}`;
      rankChip = `<span style="display:inline-block;margin-left:6px;padding:1px 6px;border-radius:10px;font-size:10px;font-weight:700;color:${rc};background:${rc}1a;border:1px solid ${rc}33">${rl}</span>`;
    }

    const cells = orderedComps.map(comp => {
      const entry   = car.prices[comp];
      const isBlue  = comp === BLUE;
      const blueBg  = isBlue ? 'background:rgba(37,99,235,.04);' : '';

      if (!entry) {
        return `<td style="text-align:center;color:var(--text-muted);font-size:13px;${blueBg}">—</td>`;
      }

      const price    = entry.price_isk;
      const isMin    = car.min_price !== null && price === car.min_price;
      const isMax    = car.max_price !== null && price === car.max_price && allPrices.length > 1;
      const ageMs    = nowMs - new Date(entry.scraped_at).getTime();
      const isStale  = showStale && ageMs > STALE_MS;

      let bg = blueBg;
      if (isStale)     bg += 'background:rgba(234,179,8,.10);';
      if (isMin)       bg = `${blueBg}background:rgba(22,163,74,.16);`;
      if (isMax)       bg = `${blueBg}background:rgba(220,38,38,.12);`;

      // % vs market avg
      let diffBadge = '';
      if (marketAvg && allPrices.length > 1) {
        const diff = Math.round((price / marketAvg - 1) * 100);
        if (Math.abs(diff) >= 3) {
          const dc = diff < 0 ? '#16a34a' : '#dc2626';
          const ds = diff > 0 ? `+${diff}` : `${diff}`;
          diffBadge = `<div style="font-size:10px;font-weight:600;color:${dc}">${ds}%</div>`;
        }
      }

      // Stale indicator
      const staleNote = isStale
        ? `<div style="font-size:9px;color:#b45309;font-weight:600">${Math.floor(ageMs/86400000)}d old</div>`
        : '';

      // Model name note (if different from canonical)
      const modelNote = entry.car_model && entry.car_model !== car.canonical_name
        ? `<div style="font-size:9px;color:var(--text-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100px">${escHtml(entry.car_model)}</div>`
        : '';

      const border = isMin ? 'border:1px solid rgba(22,163,74,.35);' : isMax ? 'border:1px solid rgba(220,38,38,.3);' : '';

      return `<td style="text-align:center;padding:9px 6px;${bg}">
        <div style="display:inline-flex;flex-direction:column;align-items:center;gap:1px;padding:4px 6px;border-radius:6px;${border}min-width:80px">
          <div style="font-size:13px;font-weight:700;font-family:monospace">${formatISK(price)}</div>
          ${diffBadge}${modelNote}${staleNote}
        </div>
      </td>`;
    }).join('');

    // Market avg cell
    const avgCell = marketAvg
      ? `<td style="text-align:center;padding:9px 6px;border-left:2px solid var(--border);color:var(--text-muted)">
          <div style="font-size:12px;font-weight:600;font-family:monospace">${formatISK(marketAvg)}</div>
          <div style="font-size:9px;opacity:.7">${totalWithPrice} sources</div>
        </td>`
      : `<td style="text-align:center;color:var(--text-muted);border-left:2px solid var(--border)">—</td>`;

    return `${divider}<tr style="border-bottom:1px solid var(--border)">
      <td style="padding:9px 14px;min-width:190px">
        <div style="font-size:13px;font-weight:600">${escHtml(car.canonical_name)}${rankChip}</div>
        <div style="font-size:11px;color:var(--text-muted);margin-top:1px">${car.available_at}/${orderedComps.length} competitors</div>
      </td>
      ${cells}
      ${avgCell}
    </tr>`;
  }).join('');

  wrap.innerHTML = `<table style="width:100%;border-collapse:collapse;font-size:13px">
    <thead>
      <tr style="border-bottom:2px solid var(--border)">
        <th style="text-align:left;padding:10px 14px;font-size:12px;min-width:190px">Model</th>
        ${headerCells}
        <th style="text-align:center;padding:10px 8px;font-size:12px;border-left:2px solid var(--border);min-width:90px">Mkt Avg</th>
      </tr>
    </thead>
    <tbody>${rows}</tbody>
  </table>`;
}

function updateStatusTiles(scraperStatus) {
  const rates = state.rates;

  // ── Tile 1: Last Scrape ──────────────────────────────────────────────────
  const scrapeAgeEl   = document.getElementById('tile-scrape-age');
  const scrapeDetailEl = document.getElementById('tile-scrape-detail');
  const scrapeDot     = document.getElementById('tile-scrape-dot');
  const scrapeCard    = document.getElementById('tile-last-scrape');
  if (scraperStatus && scraperStatus.scrapers) {
    const timestamps = scraperStatus.scrapers
      .map(s => s.last_scraped ? new Date(s.last_scraped).getTime() : 0)
      .filter(t => t > 0);
    if (timestamps.length) {
      const latest = new Date(Math.max(...timestamps));
      const ageMs  = Date.now() - latest.getTime();
      const ageMin = Math.round(ageMs / 60000);
      let ageStr;
      if (ageMin < 60)       ageStr = `${ageMin}m ago`;
      else if (ageMin < 1440) ageStr = `${Math.round(ageMin / 60)}h ago`;
      else                   ageStr = `${Math.round(ageMin / 1440)}d ago`;
      scrapeAgeEl.textContent   = ageStr;
      const isStale = ageMin > 120;
      scrapeDot.className       = `status-dot ${isStale ? 'amber' : 'green'}`;
      scrapeCard.className      = `stat-card stat-card--status ${isStale ? 'status-amber' : 'status-green'}`;
      scrapeDetailEl.textContent = `${rates.length} rates loaded · ${latest.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}`;
    } else {
      scrapeAgeEl.textContent    = 'No data';
      scrapeDetailEl.textContent = 'Run a scrape to populate';
    }
  }

  // ── Tile 2: Scraper Health ───────────────────────────────────────────────
  const healthValEl    = document.getElementById('tile-health-val');
  const healthDetailEl = document.getElementById('tile-health-detail');
  const healthDot      = document.getElementById('tile-health-dot');
  const healthCard     = document.getElementById('tile-health');
  if (scraperStatus && scraperStatus.scrapers) {
    const total  = scraperStatus.scrapers.length;
    const live   = scraperStatus.scrapers.filter(s => s.source === 'live').length;
    const unstable = scraperStatus.unstable_competitors || [];
    healthValEl.textContent = `${live} / ${total}`;
    if (live === total) {
      healthDot.className      = 'status-dot green';
      healthCard.className     = 'stat-card stat-card--status status-green';
      healthDetailEl.textContent = 'All scrapers live';
    } else if (unstable.length) {
      healthDot.className      = 'status-dot amber';
      healthCard.className     = 'stat-card stat-card--status status-amber';
      healthDetailEl.textContent = `Issues: ${unstable.join(', ')}`;
    } else {
      healthDot.className      = 'status-dot red';
      healthCard.className     = 'stat-card stat-card--status status-red';
      healthDetailEl.textContent = `${total - live} scraper(s) down`;
    }
  }

  // ── Tile 3: Last Runs ────────────────────────────────────────────────────
  const blueDot  = document.getElementById('tile-blue-dot');
  const blueCard = document.getElementById('tile-blue-pos');
  const lastRuns = scraperStatus?.last_runs || {};

  function _fmtRunAge(isoStr) {
    if (!isoStr) return '—';
    const ageMin = Math.round((Date.now() - new Date(isoStr).getTime()) / 60000);
    if (ageMin < 60)        return `${ageMin}m ago`;
    if (ageMin < 1440)      return `${Math.round(ageMin / 60)}h ago`;
    return `${Math.round(ageMin / 1440)}d ago`;
  }

  const dailyRun    = lastRuns['manual']   || lastRuns['daily']    || null;
  const horizonRun  = lastRuns['horizon']  || null;
  const seasonalRun = lastRuns['seasonal'] || null;

  const dailyEl    = document.getElementById('tile-run-daily');
  const horizonEl  = document.getElementById('tile-run-horizon');
  const seasonalEl = document.getElementById('tile-run-seasonal');

  function _runRow(label, run) {
    const age = _fmtRunAge(run?.at);
    let rateStr = '';
    if (run?.rates) {
      const n = run.rates;
      rateStr = ` · ${n >= 1000 ? (n / 1000).toFixed(n >= 10000 ? 0 : 1) + 'k' : n}`;
    }
    return `<span>${label}</span><span>${age}${rateStr}</span>`;
  }
  if (dailyEl)    dailyEl.innerHTML    = _runRow('Daily',    dailyRun);
  if (horizonEl)  horizonEl.innerHTML  = _runRow('Horizon',  horizonRun);
  if (seasonalEl) seasonalEl.innerHTML = _runRow('Seasonal', seasonalRun);

  const anyStale = [dailyRun, horizonRun, seasonalRun].some(r => {
    if (!r?.at) return true;
    return (Date.now() - new Date(r.at).getTime()) > 48 * 3600000;
  });
  blueDot.className  = `status-dot ${anyStale ? 'amber' : 'green'}`;
  blueCard.className = `stat-card stat-card--status ${anyStale ? 'status-amber' : 'status-green'}`;

  // ── Tile 4: Price Alerts ─────────────────────────────────────────────────
  const alertsValEl    = document.getElementById('tile-alerts-val');
  const alertsDetailEl = document.getElementById('tile-alerts-detail');
  const alertsDot      = document.getElementById('tile-alerts-dot');
  const alertsCard     = document.getElementById('tile-alerts');
  const changes        = state.priceChanges || {};
  const changedCount   = Object.values(changes).filter(c => c && (c.delta_pct ?? 0) !== 0).length;
  if (state.priceChangesAvailable && changedCount > 0) {
    alertsValEl.textContent    = String(changedCount);
    alertsDetailEl.textContent = `${changedCount} model${changedCount > 1 ? 's' : ''} with price moves`;
    alertsDot.className        = 'status-dot amber';
    alertsCard.className       = 'stat-card stat-card--status status-amber';
  } else {
    alertsValEl.textContent    = state.priceChangesAvailable ? '0' : '—';
    alertsDetailEl.textContent = state.priceChangesAvailable ? 'No price moves detected' : 'Need baseline data';
    alertsDot.className        = 'status-dot green';
    alertsCard.className       = 'stat-card stat-card--status status-green';
  }

  // ── Shared: source badge ─────────────────────────────────────────────────
  setSourceBadge('rates-source-badge', state.ratesSource);
}

function renderExecutiveSummary() {
  const banner = document.getElementById('exec-banner');
  const items = document.getElementById('exec-banner-items');
  if (!banner || !items) return;

  const rates = state.rates;
  if (!rates.length) { banner.style.display = 'none'; return; }

  // Blue vs market
  const blueRates = rates.filter(r => r.competitor === 'Blue Car Rental');
  const competitorRates = rates.filter(r => r.competitor !== 'Blue Car Rental');

  const blueAvg = blueRates.length
    ? Math.round(blueRates.reduce((s, r) => s + r.price_isk, 0) / blueRates.length) : null;
  const mktAvg = competitorRates.length
    ? Math.round(competitorRates.reduce((s, r) => s + r.price_isk, 0) / competitorRates.length) : null;

  // Cheapest competitor overall
  const minRate = [...competitorRates].sort((a, b) => a.price_isk - b.price_isk)[0];

  // Competitors undercutting Blue (by any model)
  const blueByModel = {};
  blueRates.forEach(r => {
    const k = r.canonical_name || r.car_model;
    if (!blueByModel[k] || r.price_isk < blueByModel[k]) blueByModel[k] = r.price_isk;
  });
  const undercutters = new Set();
  competitorRates.forEach(r => {
    const k = r.canonical_name || r.car_model;
    if (blueByModel[k] && r.price_isk < blueByModel[k]) undercutters.add(r.competitor);
  });

  // Price movement arrows from per-competitor changes
  const changes = state.priceChanges;
  const allMovers = Object.values(changes);
  const upCount = allMovers.filter(c => c.direction === 'up').length;
  const downCount = allMovers.filter(c => c.direction === 'down').length;

  const chip = (icon, label, value, color) =>
    `<div style="display:flex;align-items:center;gap:6px;padding:6px 12px;background:rgba(255,255,255,0.07);border-radius:6px;white-space:nowrap">
      <span style="font-size:15px">${icon}</span>
      <span style="font-size:11px;color:#93c5fd">${label}</span>
      <span style="font-size:13px;font-weight:700;color:${color}">${value}</span>
    </div>`;

  const pct = (a, b) => b ? `${a > b ? '+' : ''}${Math.round(((a - b)/b)*100)}%` : '—';
  const blueVsMkt = (blueAvg && mktAvg)
    ? chip('📊', 'Blue vs Market', pct(blueAvg, mktAvg),
        blueAvg > mktAvg ? '#f87171' : '#4ade80')
    : '';
  const cheapestChip = minRate
    ? chip('💰', 'Market Low', `${formatISK(minRate.price_isk)} (${shortName(minRate.competitor)})`, '#fbbf24')
    : '';
  const undercutChip = chip(
    undercutters.size > 0 ? '⚠️' : '✅',
    'Undercutting Blue',
    undercutters.size > 0 ? `${undercutters.size} competitor${undercutters.size > 1 ? 's' : ''}` : 'None',
    undercutters.size > 0 ? '#f87171' : '#4ade80'
  );
  const movementChip = (upCount + downCount > 0)
    ? chip('📈', 'Price Moves', `↑${upCount} ↓${downCount}`, '#93c5fd')
    : '';

  items.innerHTML = [blueVsMkt, cheapestChip, undercutChip, movementChip].filter(Boolean).join('');
  banner.style.display = 'flex';
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

  const fullLabels = Object.keys(competitorMap);
  // Shorten labels for the x-axis — keep Go Car vs Go Iceland distinct
  const shortLabel = name => {
    if (name === 'Go Car Rental') return 'Go Car';
    if (name === 'Go Iceland')    return 'Go Iceland';
    return name.replace(' Car Rental', '').replace(' Iceland', '');
  };
  const labels = fullLabels.map(shortLabel);
  const data = fullLabels.map(c => Math.round(
    competitorMap[c].reduce((a, b) => a + b, 0) / competitorMap[c].length
  ));

  const colors = fullLabels.map((name, i) => compColor(name, i));

  if (state.rateChart) state.rateChart.destroy();

  state.rateChart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Avg. Price (ISK)',
        data,
        backgroundColor: colors,
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
            // Show full name in tooltip
            title: items => fullLabels[items[0].dataIndex],
            label: ctx => `  Avg: ${formatISK(ctx.raw)}`,
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
          ticks: { font: { size: 12 } },
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
    loadWatchlist();
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
      const source      = s?.source || 'mock';
      const reliability = s?.reliability || 'unknown';
      badge.textContent = source === 'live' ? 'Live Data' : 'Mock Data';
      badge.className   = `badge ${source === 'live' ? 'badge-green' : 'badge-gray'} scraper-status-badge`;
      // Add reliability indicator alongside badge
      const rel = badge.nextElementSibling?.classList.contains('scraper-reliability')
        ? badge.nextElementSibling
        : (() => { const span = document.createElement('span'); span.className = 'scraper-reliability'; badge.insertAdjacentElement('afterend', span); return span; })();
      if (reliability === 'unstable') {
        rel.innerHTML = `<span title="${s.error_runs} of last ${s.runs_checked} scrapes had errors" style="margin-left:6px;font-size:11px;color:#f59e0b;font-weight:600">⚠ unstable</span>`;
      } else {
        rel.innerHTML = '';
      }
    });

    document.querySelectorAll('.scraper-ts').forEach(el => {
      const s = scraperMap[el.dataset.competitor];
      el.textContent = s?.last_scraped ? timeAgo(s.last_scraped) : '';
    });

    // ── Show/hide the "competitor silent" warning banner in Settings ───────
    const unstable = data.unstable_competitors || [];
    const silentBanner = document.getElementById('scraper-silent-banner');
    if (silentBanner) {
      if (unstable.length > 0) {
        silentBanner.innerHTML = `
          <span style="font-size:15px">⚠️</span>
          <span><strong>${unstable.join(', ')}</strong> failed in 3+ of the last ${(data.scrapers?.[0]?.runs_checked ?? 5)} scrape runs — check Settings → Scrape History for details.</span>`;
        silentBanner.style.display = 'flex';
      } else {
        silentBanner.style.display = 'none';
      }
    }
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

// ── Category Audit ─────────────────────────────────────────────────────────
let _categoryAuditData = null;

async function loadCategoryAudit() {
  try {
    const data = await apiFetch('/api/settings/category-audit');
    _categoryAuditData = data;
    renderCategoryAudit();
  } catch (e) {
    showToast(`Failed to load category audit: ${e.message}`, 'error');
  }
}

function renderCategoryAudit() {
  if (!_categoryAuditData) return;
  const { summary, rows } = _categoryAuditData;
  const filter = document.getElementById('audit-filter')?.value || 'all';

  // Summary stats
  const sumEl = document.getElementById('audit-summary');
  if (sumEl) {
    sumEl.innerHTML = `
      <div style="background:var(--card-bg);border:1px solid var(--border);border-radius:8px;padding:8px 14px;font-size:13px">
        <span style="color:#6b7280">Total models</span><br>
        <strong style="font-size:18px">${summary.total_models}</strong>
      </div>
      <div style="background:var(--card-bg);border:1px solid var(--border);border-radius:8px;padding:8px 14px;font-size:13px">
        <span style="color:#22c55e">Mapped</span><br>
        <strong style="font-size:18px">${summary.mapped}</strong>
      </div>
      <div style="background:var(--card-bg);border:1px solid var(--border);border-radius:8px;padding:8px 14px;font-size:13px">
        <span style="color:#f59e0b">Unmapped</span><br>
        <strong style="font-size:18px">${summary.unmapped}</strong>
      </div>
      <div style="background:var(--card-bg);border:1px solid var(--border);border-radius:8px;padding:8px 14px;font-size:13px">
        <span style="color:#ef4444">Conflicts</span><br>
        <strong style="font-size:18px">${summary.conflicts}</strong>
      </div>
    `;
  }

  // Filter rows
  let filtered = rows;
  if (filter === 'conflicts') {
    filtered = rows.filter(r => !r.is_correct);
  } else if (filter === 'unmapped') {
    filtered = rows.filter(r => !r.is_mapped);
  }

  const tbody = document.getElementById('audit-tbody');
  if (!tbody) return;

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" style="padding:20px;text-align:center;color:#6b7280">No results for this filter</td></tr>';
    return;
  }

  const catColors = {
    Economy: '#3b82f6',
    Compact: '#8b5cf6',
    SUV:     '#f59e0b',
    '4x4':   '#ef4444',
    Minivan: '#22c55e',
  };

  function catBadge(cat) {
    const color = catColors[cat] || '#6b7280';
    return `<span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;background:${color}20;color:${color};border:1px solid ${color}40">${cat || '—'}</span>`;
  }

  tbody.innerHTML = filtered.map(r => {
    let statusBadge;
    if (!r.is_mapped) {
      statusBadge = '<span class="badge badge-gray" style="font-size:11px">Unmapped</span>';
    } else if (r.is_correct) {
      statusBadge = '<span class="badge badge-green" style="font-size:11px">OK</span>';
    } else {
      statusBadge = '<span class="badge" style="font-size:11px;background:#fef2f2;color:#dc2626;border:1px solid #fecaca">Mismatch</span>';
    }
    return `<tr${!r.is_correct ? ' style="background:rgba(239,68,68,0.04)"' : ''}>
      <td><strong>${r.canonical_name}</strong></td>
      <td>${catBadge(r.db_category)}</td>
      <td>${r.correct_category ? catBadge(r.correct_category) : '<span style="color:#9ca3af">—</span>'}</td>
      <td style="text-align:right;font-variant-numeric:tabular-nums">${r.count.toLocaleString()}</td>
      <td>${statusBadge}</td>
    </tr>`;
  }).join('');
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

// ── Model Watchlist ────────────────────────────────────────────────────────

let _watchlistModels = [];

async function loadWatchlist() {
  try {
    const [watchData, catalogData] = await Promise.all([
      apiFetch('/api/alerts/watchlist'),
      state.catalog ? Promise.resolve({ catalog: state.catalog }) : apiFetch('/api/rates/car-catalog'),
    ]);
    _watchlistModels = watchData.models || [];
    if (catalogData?.catalog) state.catalog = catalogData.catalog;
    renderWatchlist();
    populateWatchlistDropdown();
  } catch (_) { /* silent */ }
}

function renderWatchlist() {
  const container = document.getElementById('watchlist-chips');
  if (!container) return;
  if (!_watchlistModels.length) {
    container.innerHTML = `<span style="color:var(--text-muted);font-size:13px;font-style:italic">No models on watchlist yet — use the dropdown above to add one.</span>`;
    return;
  }
  container.innerHTML = _watchlistModels.map(m => `
    <span style="display:inline-flex;align-items:center;gap:5px;background:var(--bg-alt);border:1px solid var(--border);border-radius:20px;padding:3px 10px 3px 12px;font-size:12px;font-weight:600;color:var(--text)">
      🎯 ${escHtml(m)}
      <button onclick="removeWatchlistModel('${escHtml(m.replace(/'/g,"\\'"))}')"
        style="background:none;border:none;cursor:pointer;color:#9ca3af;font-size:14px;line-height:1;padding:0 2px"
        title="Remove from watchlist">×</button>
    </span>
  `).join('');
}

function populateWatchlistDropdown() {
  const sel = document.getElementById('watchlist-model-select');
  if (!sel) return;
  // Populate from canonical catalog if loaded, else from state
  const catalog = state.catalog || [];
  const currentSet = new Set(_watchlistModels);
  const options = catalog
    .filter(c => !currentSet.has(c.canonical_name))
    .sort((a, b) => a.canonical_name.localeCompare(b.canonical_name));
  sel.innerHTML = '<option value="">Select a model to watch…</option>' +
    options.map(c => `<option value="${escHtml(c.canonical_name)}">${escHtml(c.canonical_name)}</option>`).join('');
}

async function addWatchlistModel() {
  const sel = document.getElementById('watchlist-model-select');
  const model = sel?.value?.trim();
  if (!model) return;
  try {
    const data = await apiFetch('/api/alerts/watchlist', {
      method: 'POST',
      body: JSON.stringify({ model }),
    });
    _watchlistModels = data.models || [];
    renderWatchlist();
    populateWatchlistDropdown();
    showToast(`🎯 ${model} added to watchlist`, 'success');
    if (sel) sel.value = '';
  } catch (e) {
    showToast(`Failed to add to watchlist: ${e.message}`, 'error');
  }
}

async function removeWatchlistModel(model) {
  try {
    const data = await apiFetch(`/api/alerts/watchlist/${encodeURIComponent(model)}`, { method: 'DELETE' });
    _watchlistModels = data.models || [];
    renderWatchlist();
    populateWatchlistDropdown();
    showToast(`Removed ${model} from watchlist`, 'success');
  } catch (e) {
    showToast(`Failed to remove: ${e.message}`, 'error');
  }
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
  // Derive date window from the first rate that has dates
  let pickupDate = '', returnDate = '';
  for (const car of cars) {
    for (const comp of competitors) {
      const entry = car.prices[comp];
      if (entry && entry.scraped_at) { pickupDate = document.getElementById('filter-pickup')?.value || ''; returnDate = document.getElementById('filter-return')?.value || ''; break; }
    }
    if (pickupDate) break;
  }
  const headers = ['Category', 'Model', 'Pickup Date', 'Return Date', ...competitors.map(c => `${shortName(c)} (ISK total)`), 'Cheapest Competitor'];
  const rows = cars.map(car => [
    car.category,
    car.canonical_name,
    pickupDate,
    returnDate,
    ...competitors.map(c => car.prices[c] ? car.prices[c].price_isk : ''),
    car.cheapest_competitor || '',
  ]);
  downloadCSV(`rate_matrix_${new Date().toISOString().slice(0,10)}.csv`, [headers, ...rows]);
  showToast('Rate matrix exported!', 'success');
}

function exportSeasonalCSV() {
  const data = state.seasonalData;
  if (!data) return showToast('No seasonal data to export. Load seasonal analysis first.', 'error');

  const { season_summary, months } = data;
  const SEASON_ORDER = ['low', 'shoulder', 'high', 'peak'];
  const competitors  = [...new Set(SEASON_ORDER.flatMap(s => Object.keys(season_summary[s] || {})))].sort();

  // Sheet 1: month-by-month per-day prices
  const monthHeaders = ['Month', 'Season', ...competitors];
  const monthRows = (months || []).map(m => [
    m.month_label,
    m.season_label || m.season,
    ...competitors.map(c => m.comp_overall?.[c] ?? ''),
  ]);

  // Sheet 2: season-band summary
  const blueVals = SEASON_ORDER.map(s => season_summary[s]?.['Blue Car Rental']).filter(v => v != null);
  const blueAvgCSV = blueVals.length ? blueVals.reduce((a, b) => a + b, 0) / blueVals.length : null;
  const summaryHeaders = ['', 'Competitor', 'Low (ISK/day)', 'Shoulder (ISK/day)', 'High (ISK/day)', 'Peak (ISK/day)', 'vs Blue'];
  const summaryRows = competitors.map(comp => {
    const prices = SEASON_ORDER.map(s => season_summary[s]?.[comp] ?? '');
    let vsBlue = '';
    if (comp === 'Blue Car Rental') {
      vsBlue = 'base';
    } else {
      const vals = SEASON_ORDER.map(s => season_summary[s]?.[comp]).filter(v => v != null);
      if (vals.length && blueAvgCSV != null) {
        const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
        const pct = Math.round((avg / blueAvgCSV - 1) * 100);
        vsBlue = (pct >= 0 ? '+' : '') + pct + '%';
      }
    }
    return ['', comp, ...prices, vsBlue];
  });

  const rows = [
    monthHeaders,
    ...monthRows,
    [],  // blank separator row
    ['Season Band Summary'],
    summaryHeaders,
    ...summaryRows,
  ];
  downloadCSV(`seasonal_${new Date().toISOString().slice(0,10)}.csv`, rows);
  showToast('Seasonal data exported!', 'success');
}

function exportRatesCSV() {
  if (!state.rates.length) return showToast('No rate data to export. Scrape first.', 'error');
  const headers = ['Competitor', 'Location', 'Car Model', 'Canonical Name', 'Category',
                   'Total (ISK)', 'Per Day (ISK)', 'Pickup Date', 'Return Date', 'Scraped At'];
  function getDays(pickup, ret) {
    try { return Math.max(1, Math.round((new Date(ret) - new Date(pickup)) / 86400000)); }
    catch { return 1; }
  }
  const rows = state.rates.map(r => {
    const days = getDays(r.pickup_date, r.return_date);
    return [
      r.competitor, r.location,
      r.car_model || '', r.canonical_name || '',
      r.car_category, r.price_isk, Math.round(r.price_isk / days),
      r.pickup_date, r.return_date, r.scraped_at,
    ];
  });
  downloadCSV(`competitor_rates_${new Date().toISOString().slice(0,10)}.csv`, [headers, ...rows]);
  showToast(`Exported ${rows.length} rate records.`, 'success');
}

// ── INSURANCE TAB ─────────────────────────────────────────────────────────

const COVERAGE_STATUS = {
  included:    { label: '✓ Included',  cls: 'ins-cell-included',    order: 0 },
  optional:    { label: '+ Optional',  cls: 'ins-cell-optional',    order: 1 },
  zero:        { label: '◎ In Zero',   cls: 'ins-cell-zero',        order: 2 },
  unavailable: { label: '—',           cls: 'ins-cell-unavailable', order: 3 },
};

function setInsuranceView(view) {
  ['comparison', 'company', 'prices', 'deductibles'].forEach(v => {
    const el = document.getElementById(`ins-view-${v}`);
    const btn = document.getElementById(`btn-ins-${v}`);
    if (el) el.style.display = (v === view) ? '' : 'none';
    if (btn) btn.classList.toggle('active', v === view);
  });
  // Load review log when prices view is shown
  if (view === 'prices') loadInsuranceReviewLog();
}

async function loadInsurance() {
  // Always reload to get the latest last_reviewed timestamp
  try {
    const data = await apiFetch('/api/insurance');
    state.insuranceData = data;
    renderInsurance(data);
    const badge = document.getElementById('insurance-source-badge');
    if (badge) {
      badge.textContent = 'Manual Data';
      badge.className = 'badge badge-gray';
      badge.style.display = '';
    }
  } catch (e) {
    showToast(`Failed to load insurance data: ${e.message}`, 'error');
  }
}

function triggerInsuranceResearch() {
  const data = state.insuranceData;
  if (!data || !data.companies) {
    showToast('Insurance data not loaded yet.', 'error');
    return;
  }
  // Collect all insurance URLs from the loaded data
  const urls = Object.entries(data.companies)
    .map(([name, c]) => ({ name, url: c.insurance_url }))
    .filter(e => e.url);

  if (!urls.length) {
    showToast('No insurance URLs found.', 'error');
    return;
  }

  // Open each URL in a new tab
  urls.forEach(({ url }) => window.open(url, '_blank', 'noopener'));

  showToast(
    `Opened ${urls.length} insurance pages. Review each site, then click "Mark Reviewed" when done.`,
    'success',
    6000,
  );
}

async function markInsuranceReviewed() {
  const btn = document.getElementById('btn-ins-review');
  if (btn) { btn.disabled = true; btn.textContent = 'Saving…'; }
  try {
    await apiFetch('/api/insurance/mark-reviewed', {
      method: 'POST',
      body: JSON.stringify({ notes: 'Manual review via dashboard' }),
    });
    showToast('Insurance data marked as reviewed.', 'success');
    // Reload to update timestamp
    state.insuranceData = null;
    await loadInsurance();
    await loadInsuranceReviewLog();
  } catch (e) {
    showToast(`Failed: ${e.message}`, 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="width:13px;height:13px"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg> Mark Reviewed`; }
  }
}

async function loadInsuranceReviewLog() {
  try {
    const data = await apiFetch('/api/insurance/review-log');
    const tbody = document.getElementById('insurance-review-log-tbody');
    if (!tbody) return;
    const reviews = data.reviews || [];
    if (!reviews.length) {
      tbody.innerHTML = `<tr><td colspan="3" style="padding:20px;text-align:center;color:#6b7280">No review history yet. Click "Mark Reviewed" after verifying company websites.</td></tr>`;
      return;
    }
    tbody.innerHTML = reviews.map(r => `<tr>
      <td style="white-space:nowrap">${formatDate(r.reviewed_at)}</td>
      <td>${escHtml(r.reviewer || '—')}</td>
      <td style="color:#6b7280;font-size:12px">${escHtml(r.notes || '—')}</td>
    </tr>`).join('');
  } catch {}
}

function renderCategoryPricingTable(categoryPricing) {
  const tbody = document.getElementById('insurance-prices-tbody');
  if (!tbody || !categoryPricing) return;
  const cats = ['Economy', 'Compact', 'SUV', '4x4', 'Minivan'];
  const companies = Object.keys(categoryPricing);

  // Find min ISK price per category to highlight cheapest
  const minPerCat = {};
  cats.forEach(cat => {
    const prices = companies
      .map(c => categoryPricing[c]?.prices?.[cat])
      .filter(p => p !== null && p !== undefined);
    minPerCat[cat] = prices.length ? Math.min(...prices) : null;
  });

  tbody.innerHTML = companies.map(company => {
    const entry = categoryPricing[company];
    const color = (state.insuranceData?.companies?.[company]?.color) || '#6b7280';
    const hasOverride = entry?._overrides && Object.keys(entry._overrides).length > 0;

    const cells = cats.map(cat => {
      const price   = entry?.prices?.[cat];
      const eur     = entry?.price_eur?.[cat];
      const isOverridden = entry?._overrides?.[cat];
      const isMin   = price !== null && price !== undefined && minPerCat[cat] !== null && price === minPerCat[cat];
      const cls     = isMin ? 'price-low' : '';
      const editedMark = isOverridden
        ? `<span title="Manually updated ${formatDate(isOverridden)}" style="font-size:9px;color:#2563eb;margin-left:3px">✎</span>` : '';

      let display;
      if (price !== null && price !== undefined) {
        display = formatISK(price);
      } else if (eur !== null && eur !== undefined) {
        display = `~€${eur}`;
      } else {
        display = '—';
      }

      // Each cell is click-to-edit
      return `<td class="${cls}" style="text-align:center;cursor:pointer;position:relative"
                  title="Click to edit"
                  onclick="editInsurancePriceCell(this,'${escHtml(company)}','${escHtml(cat)}',${price ?? 'null'})">
        <span class="ins-price-val">${display}${editedMark}</span>
      </td>`;
    }).join('');

    return `<tr>
      <td><strong style="color:${color}">${escHtml(company)}</strong>${hasOverride ? ' <span style="font-size:10px;color:#2563eb" title="Contains manual edits">✎</span>' : ''}</td>
      <td style="font-size:12px;color:#6b7280">${escHtml(entry?.package || '')}</td>
      ${cells}
      <td style="font-size:11px;color:#6b7280;max-width:220px">${escHtml(entry?.note || '')}</td>
    </tr>`;
  }).join('');
}

function editInsurancePriceCell(td, company, category, currentPrice) {
  // If already editing this cell, ignore
  if (td.querySelector('input')) return;

  const span = td.querySelector('.ins-price-val');
  const origHtml = span.innerHTML;

  // Replace with an input
  span.innerHTML = '';
  const input = document.createElement('input');
  input.type = 'number';
  input.min = '0';
  input.step = '50';
  input.value = currentPrice !== null ? currentPrice : '';
  input.placeholder = 'ISK/day';
  input.style.cssText = 'width:80px;padding:2px 6px;font-size:12px;border:1.5px solid #2563eb;border-radius:4px;text-align:center';
  input.title = 'Enter ISK/day, leave blank for unpublished. Press Enter to save, Escape to cancel.';
  span.appendChild(input);
  input.focus();
  input.select();

  async function save() {
    const raw = input.value.trim();
    const price = raw === '' ? null : parseInt(raw, 10);
    if (raw !== '' && (isNaN(price) || price < 0)) {
      showToast('Enter a valid positive number (ISK/day), or leave blank for unpublished.', 'error');
      input.focus();
      return;
    }
    span.innerHTML = '<span style="color:#6b7280;font-size:11px">Saving…</span>';
    try {
      await apiFetch('/api/insurance/prices', {
        method: 'POST',
        body: JSON.stringify({ company, category, price_isk: price }),
      });
      showToast(`Saved: ${company} · ${category} → ${price !== null ? formatISK(price) + '/day' : 'unpublished'}`, 'success');
      // Reload insurance data so the table re-renders with the new value
      state.insuranceData = null;
      await loadInsurance();
    } catch (e) {
      showToast(`Failed to save: ${e.message}`, 'error');
      span.innerHTML = origHtml;
    }
  }

  function cancel() {
    span.innerHTML = origHtml;
  }

  input.addEventListener('keydown', e => {
    if (e.key === 'Enter')  { e.preventDefault(); save(); }
    if (e.key === 'Escape') { e.preventDefault(); cancel(); }
  });
  input.addEventListener('blur', () => {
    // Small delay so Enter keydown fires before blur
    setTimeout(() => { if (td.querySelector('input')) cancel(); }, 150);
  });
}

function renderInsurance(data) {
  const { companies, protection_types, key_insights, disclaimer, last_updated, last_reviewed, category_pricing } = data;
  const companyNames = Object.keys(companies);

  // Last updated / reviewed label
  const upEl = document.getElementById('insurance-last-updated');
  if (upEl) {
    const reviewedStr = last_reviewed
      ? ` · Verified ${formatDate(last_reviewed)}`
      : ' · Not yet verified';
    upEl.textContent = `Research: ${last_updated}${reviewedStr}`;
  }

  if (category_pricing) renderCategoryPricingTable(category_pricing);

  // Disclaimer
  const discEl = document.getElementById('insurance-disclaimer');
  const discTextEl = document.getElementById('insurance-disclaimer-text');
  if (discEl && discTextEl) { discTextEl.textContent = disclaimer; discEl.style.display = ''; }

  // Key insight cards
  renderInsuranceInsights(key_insights, companies);

  // Build per-company coverage lookup
  const coverageMap = buildCoverageMap(companies, protection_types);

  renderCoverageMatrix(companies, protection_types, companyNames, coverageMap);
  renderCompanyCards(companies);
  renderDeductiblesTable(companies, companyNames);
  renderZeroExcessCards(companies);
}

function renderInsuranceInsights(insights, companies) {
  const row = document.getElementById('insurance-insights-row');
  if (!row) return;
  row.innerHTML = insights.map(ins => `
    <div class="stat-card" style="border-top:3px solid ${escHtml(ins.color)}">
      <div class="stat-label" style="font-size:12px">${escHtml(ins.icon)} ${escHtml(ins.company)}</div>
      <div class="stat-value" style="font-size:15px;line-height:1.3">${escHtml(ins.title)}</div>
      <div class="stat-sub" style="font-size:12px;margin-top:4px;line-height:1.4">${escHtml(ins.text)}</div>
    </div>
  `).join('');
}

function buildCoverageMap(companies, protection_types) {
  // Returns: { companyName: { protectionId: 'included'|'optional'|'zero'|'unavailable' } }
  const map = {};
  for (const [name, co] of Object.entries(companies)) {
    map[name] = {};
    for (const pt of protection_types) {
      map[name][pt.id] = getCoverageStatus(co, pt.id);
    }
  }
  return map;
}

function getCoverageStatus(company, protectionId) {
  // Check if in included_base
  if ((company.included_base || []).some(p => p.type === protectionId)) return 'included';

  // Check packages
  let foundInOptional = false;
  let foundInZero = false;
  for (const pkg of (company.packages || [])) {
    if (pkg.tier === 'base') continue;
    if ((pkg.covers || []).includes(protectionId)) {
      if (pkg.tier === 'zero') foundInZero = true;
      else foundInOptional = true;
    }
  }
  // Also check individual_products for Hertz
  if ((company.individual_products || []).some(p => p.type === protectionId)) foundInOptional = true;

  if (foundInOptional) return 'optional';
  if (foundInZero) return 'zero';
  return 'unavailable';
}

function renderCoverageMatrix(companies, protection_types, companyNames, coverageMap) {
  const table = document.getElementById('insurance-matrix-table');
  if (!table) return;

  // Header
  const thead = table.querySelector('thead');
  thead.innerHTML = `<tr>
    <th style="min-width:180px">Protection Type</th>
    ${companyNames.map(n => {
      const co = companies[n];
      return `<th style="text-align:center;min-width:100px">
        <div style="display:flex;flex-direction:column;align-items:center;gap:3px">
          <span style="width:10px;height:10px;border-radius:50%;background:${escHtml(co.color)};display:inline-block"></span>
          <span style="font-size:11px;line-height:1.2">${escHtml(shortCompanyName(n))}</span>
        </div>
      </th>`;
    }).join('')}
  </tr>`;

  // Body
  const tbody = table.querySelector('tbody');
  tbody.innerHTML = protection_types.map(pt => {
    const cells = companyNames.map(n => {
      const status = coverageMap[n][pt.id];
      const s = COVERAGE_STATUS[status];
      return `<td class="ins-cell ${s.cls}" style="text-align:center;font-size:12px">${s.label}</td>`;
    }).join('');
    return `<tr>
      <td>
        <strong style="font-size:13px">${escHtml(pt.acronym)}</strong>
        <div style="font-size:11px;color:#6b7280;margin-top:2px">${escHtml(pt.name)}</div>
      </td>
      ${cells}
    </tr>`;
  }).join('');
}

function renderCompanyCards(companies) {
  const container = document.getElementById('insurance-company-cards');
  if (!container) return;

  container.innerHTML = Object.entries(companies).map(([name, co]) => {
    const packagesHtml = (co.packages || []).map(pkg => {
      const tierLabel = { base: 'Base', addon: 'Add-on', zero: 'Zero Excess' }[pkg.tier] || pkg.tier;
      const tierCls   = { base: 'ins-tier-base', addon: 'ins-tier-addon', zero: 'ins-tier-zero' }[pkg.tier] || '';
      const coversHtml = (pkg.covers || []).map(c => `<span class="ins-cover-pill">${escHtml(c.toUpperCase())}</span>`).join('');
      return `
        <div class="ins-package ${tierCls}">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;margin-bottom:6px">
            <strong style="font-size:13px">${escHtml(pkg.name)}</strong>
            <span class="ins-tier-badge ${tierCls}">${escHtml(tierLabel)}</span>
          </div>
          <div style="font-size:12px;color:#6b7280;margin-bottom:6px">
            ${escHtml(pkg.price_note || (pkg.price_isk ? formatISK(pkg.price_isk) + '/day' : 'Included'))}
            &nbsp;·&nbsp; Excess: <strong>${escHtml(pkg.deductible_summary || '—')}</strong>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:4px">${coversHtml}</div>
        </div>`;
    }).join('');

    const baseItems = (co.included_base || []).map(b => {
      const label = b.deductible_label || (b.deductible_isk != null ? `${(b.deductible_isk/1000).toFixed(0)}k ISK excess` : 'Included');
      return `<li><strong>${escHtml(b.type.toUpperCase())}</strong> — ${escHtml(b.note || '')} <span style="color:#6b7280">(${escHtml(label)})</span></li>`;
    }).join('');

    return `
      <div class="card ins-company-card" style="border-top:4px solid ${escHtml(co.color)}">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px">
          <span style="width:12px;height:12px;border-radius:50%;background:${escHtml(co.color)};flex-shrink:0"></span>
          <div class="card-title" style="margin:0">${escHtml(name)}</div>
        </div>
        <div style="font-size:12px;margin-bottom:10px">
          <span class="badge badge-green" style="font-size:11px">${escHtml(co.highlight)}</span>
        </div>
        ${co.notes ? `<p style="font-size:12px;color:#6b7280;margin-bottom:10px">${escHtml(co.notes)}</p>` : ''}
        <div style="margin-bottom:10px">
          <div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;color:#9ca3af;margin-bottom:6px">Included in Base Rental</div>
          <ul style="font-size:12px;padding-left:16px;margin:0;line-height:2">${baseItems}</ul>
        </div>
        <div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;color:#9ca3af;margin-bottom:6px">Packages & Add-ons</div>
        <div style="display:flex;flex-direction:column;gap:8px">${packagesHtml}</div>
      </div>`;
  }).join('');
}

function renderDeductiblesTable(companies, companyNames) {
  const table = document.getElementById('deductibles-table');
  if (!table) return;

  const rows = [
    { label: 'CDW Collision Excess',     key: 'cdw'  },
    { label: 'After SCDW Upgrade',       key: 'scdw' },
    { label: 'Gravel / Glass (GP)',       key: 'gp'   },
    { label: 'Sand & Ash (SAAP)',         key: 'saap' },
    { label: 'Theft (TP)',                key: 'tp'   },
    { label: 'Tire & Wheel (TIP)',        key: 'tip'  },
    { label: 'Zero-Excess Package',       key: 'zero' },
  ];

  const thead = table.querySelector('thead') || table.createTHead();
  const tbody = table.querySelector('tbody') || table.createTBody();

  thead.innerHTML = `<tr>
    <th>Deductible / Excess</th>
    ${companyNames.map(n => {
      const co = companies[n];
      return `<th style="text-align:center">
        <div style="display:flex;flex-direction:column;align-items:center;gap:3px">
          <span style="width:10px;height:10px;border-radius:50%;background:${escHtml(co.color)};display:inline-block"></span>
          <span style="font-size:11px">${escHtml(shortCompanyName(n))}</span>
        </div>
      </th>`;
    }).join('')}
  </tr>`;

  tbody.innerHTML = rows.map(row => {
    const cells = companyNames.map(n => {
      const co = companies[n];
      const val = getDeductibleValue(co, row.key);
      const cls = val === '0' || val === '0 ISK' ? 'style="color:#22c55e;font-weight:600"' :
                  val === '—' ? 'style="color:#9ca3af"' : '';
      return `<td style="text-align:center;font-size:13px" ${cls}>${escHtml(val)}</td>`;
    }).join('');
    return `<tr><td style="font-size:13px;font-weight:500">${escHtml(row.label)}</td>${cells}</tr>`;
  }).join('');
}

function getDeductibleValue(company, key) {
  if (key === 'zero') {
    const zeroPkg = (company.packages || []).find(p => p.tier === 'zero');
    return zeroPkg ? (zeroPkg.price_note || (zeroPkg.price_isk ? zeroPkg.price_isk.toLocaleString() + ' ISK/day' : '—')) : '—';
  }
  // Check included_base first
  const base = (company.included_base || []).find(p => p.type === key);
  if (base) {
    if (base.deductible_label) return base.deductible_label;
    if (base.deductible_isk === 0) return '0 ISK';
    if (base.deductible_isk != null) return `${Math.round(base.deductible_isk / 1000)}k ISK`;
    return 'Included';
  }
  // Check individual_products (Hertz)
  const ind = (company.individual_products || []).find(p => p.type === key);
  if (ind) {
    if (ind.deductible_label) return ind.deductible_label;
    if (ind.deductible_isk === 0) return '0 ISK';
    if (ind.deductible_isk != null) return `${Math.round(ind.deductible_isk / 1000)}k ISK`;
  }
  // Check optional packages
  for (const pkg of (company.packages || [])) {
    if ((pkg.covers || []).includes(key) && pkg.tier !== 'base' && pkg.tier !== 'zero') {
      return pkg.deductible_summary || 'In add-on';
    }
  }
  return '—';
}

function renderZeroExcessCards(companies) {
  const container = document.getElementById('zero-excess-cards');
  if (!container) return;

  container.innerHTML = Object.entries(companies).map(([name, co]) => {
    const zeroPkg = (co.packages || []).find(p => p.tier === 'zero');
    const price = zeroPkg ? (zeroPkg.price_note || (zeroPkg.price_isk ? zeroPkg.price_isk.toLocaleString('is-IS') + ' ISK/day' : 'Quote only')) : 'Not available';
    const pkgName = zeroPkg ? zeroPkg.name : 'Not offered';
    const hasZero = !!zeroPkg;

    return `
      <div style="border:1px solid rgba(0,0,0,0.1);border-radius:var(--radius);padding:14px;border-top:3px solid ${escHtml(co.color)}">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
          <span style="width:9px;height:9px;border-radius:50%;background:${escHtml(co.color)};flex-shrink:0"></span>
          <strong style="font-size:13px">${escHtml(shortCompanyName(name))}</strong>
        </div>
        <div style="font-size:12px;color:#6b7280;margin-bottom:4px">${escHtml(pkgName)}</div>
        <div style="font-size:${hasZero ? '15px' : '13px'};font-weight:600;color:${hasZero ? '#22c55e' : '#9ca3af'}">${escHtml(price)}</div>
      </div>`;
  }).join('');
}

function shortCompanyName(name) {
  const shorts = {
    'Blue Car Rental': 'Blue',
    'Holdur': 'Holdur',
    'Lotus Car Rental': 'Lotus',
    'Avis Iceland': 'Avis',
    'Go Car Rental': 'Go',
    'Hertz Iceland': 'Hertz',
    'Lava Car Rental': 'Lava',
  };
  return shorts[name] || name;
}

// ── SCRAPE LOG ─────────────────────────────────────────────────────────────
async function loadScrapeLog() {
  try {
    const data = await apiFetch('/api/rates/scrape-log');
    renderScrapeLog(data.entries || []);
  } catch {
    // Not critical — silently skip
  }
}

function renderScrapeLog(entries) {
  const tbody = document.getElementById('scrape-log-tbody');
  if (!tbody) return;
  if (!entries.length) {
    tbody.innerHTML = `<tr><td colspan="7" style="padding:20px;text-align:center;color:#6b7280">No scrape history yet. Run a scrape first.</td></tr>`;
    return;
  }
  tbody.innerHTML = entries.map((e, idx) => {
    const hasErrors = e.errors && e.errors.length > 0;
    const statusHtml = hasErrors
      ? `<button onclick="toggleScrapeErrors('scrape-errors-${idx}')"
           style="background:#fef2f2;color:#b91c1c;border:1px solid #fca5a5;border-radius:12px;padding:2px 9px;font-size:11px;font-weight:600;cursor:pointer;line-height:1.5">
           ⚠ ${e.errors.length} error${e.errors.length > 1 ? 's' : ''} ▾
         </button>`
      : `<span class="badge" style="background:#f0fdf4;color:#15803d;border:1px solid #86efac">✓ OK</span>`;

    const triggerLabels = {
      scheduled: `<span class="badge badge-blue">Scheduled</span>`,
      manual:    `<span class="badge badge-gray">Manual</span>`,
      seasonal:  `<span class="badge" style="background:#faf5ff;color:#7c3aed;border:1px solid #c4b5fd">Seasonal</span>`,
      horizon:   `<span class="badge" style="background:#eff6ff;color:#1d4ed8;border:1px solid #93c5fd">Horizon</span>`,
    };
    const triggerBadge = triggerLabels[e.trigger] || `<span class="badge badge-gray">${escHtml(e.trigger)}</span>`;
    const duration = e.duration_seconds != null ? `${e.duration_seconds.toFixed(1)}s` : '—';

    // Error detail rows (hidden by default)
    const errorRows = hasErrors
      ? `<tr id="scrape-errors-${idx}" style="display:none">
           <td colspan="7" style="padding:0 12px 12px 12px">
             <div style="background:var(--bg-alt);border:1px solid #fca5a5;border-radius:6px;padding:10px 14px">
               <div style="font-size:11px;font-weight:700;color:#b91c1c;margin-bottom:6px;text-transform:uppercase;letter-spacing:.04em">Error Details</div>
               <ul style="margin:0;padding-left:18px;font-size:12px;color:var(--text);font-family:monospace;line-height:1.7">
                 ${e.errors.map(err => `<li>${escHtml(String(err))}</li>`).join('')}
               </ul>
             </div>
           </td>
         </tr>`
      : '';

    return `<tr>
      <td style="white-space:nowrap;color:#6b7280;font-size:12px">${timeAgo(e.scraped_at)}<br><span style="font-size:11px">${formatDate(e.scraped_at)}</span></td>
      <td>${triggerBadge}</td>
      <td style="font-size:12px">${escHtml(e.location || 'All Locations')}</td>
      <td style="font-weight:600">${e.total_rates.toLocaleString()}</td>
      <td>${e.competitors}</td>
      <td style="font-size:12px">${duration}</td>
      <td>${statusHtml}</td>
    </tr>${errorRows}`;
  }).join('');
}

function toggleScrapeErrors(id) {
  const row = document.getElementById(id);
  if (!row) return;
  row.style.display = row.style.display === 'none' ? '' : 'none';
  // Flip the arrow on the button
  const btn = row.previousElementSibling?.querySelector('button[onclick*="' + id + '"]');
  if (btn) btn.textContent = btn.textContent.includes('▾')
    ? btn.textContent.replace('▾', '▴')
    : btn.textContent.replace('▴', '▾');
}

// ── PRICE GAP HEATMAP ─────────────────────────────────────────────────────

function toggleHeatmapMode() {
  state.heatmapMode = !state.heatmapMode;
  const btn         = document.getElementById('btn-heatmap-mode');
  const heatCard    = document.getElementById('heatmap-card');
  const chartCard   = document.getElementById('seasonal-chart-card');
  const summaryCard = document.getElementById('seasonal-summary-card');
  const catCard     = document.getElementById('seasonal-category-card');

  if (state.heatmapMode) {
    // Exit history mode if active — restore tables it hid
    if (state.historyMode) {
      state.historyMode = false;
      document.getElementById('btn-history-mode')?.classList.remove('active');
      document.getElementById('history-month-select').style.display = 'none';
      document.getElementById('history-chart-card').style.display   = 'none';
      if (summaryCard) summaryCard.style.display = '';
      if (catCard)     catCard.style.display     = '';
    }
    btn.classList.add('active');
    chartCard.style.display = 'none';
    heatCard.style.display  = '';
    // Respect current granularity — default is category on first open
    if (state.heatmapGranularity === 'model') {
      loadGapByModel();
    } else {
      renderPriceGapHeatmap();
    }
  } else {
    btn.classList.remove('active');
    heatCard.style.display  = 'none';
    chartCard.style.display = '';
    renderSeasonalChart();
  }
}

// Shared color scale for both category and model gap views.
// Returns { bg, text, label } for a given gap% (Blue - market).
function gapCellStyle(pct) {
  const isDark = document.body.classList.contains('dark-mode');
  if (pct === null || pct === undefined) {
    return { bg: 'var(--bg-alt)', text: 'var(--text-muted)', label: '—' };
  }
  const abs   = Math.abs(pct);
  const label = (pct >= 0 ? '+' : '') + pct + '%';

  // Neutral band — no strong colour signal
  if (abs <= 3) {
    return {
      bg:   isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)',
      text: isDark ? '#9ca3af' : '#6b7280',
      label,
    };
  }

  // Discrete tiers — avoids muddy RGBA arithmetic
  if (pct > 0) {
    // Blue more expensive → green tint (good for Blue)
    if (abs < 10)  return { bg: isDark ? 'rgba(34,197,94,0.18)'  : 'rgba(22,163,74,0.12)', text: isDark ? '#86efac' : '#166534', label };
    if (abs < 20)  return { bg: isDark ? 'rgba(34,197,94,0.30)'  : 'rgba(22,163,74,0.22)', text: isDark ? '#4ade80' : '#15803d', label };
    return          { bg: isDark ? 'rgba(34,197,94,0.44)'  : 'rgba(22,163,74,0.32)', text: isDark ? '#bbf7d0' : '#14532d', label };
  }

  // Blue cheaper → red tint (competitor undercuts us)
  if (abs < 10)  return { bg: isDark ? 'rgba(239,68,68,0.18)'  : 'rgba(220,38,38,0.10)', text: isDark ? '#fca5a5' : '#991b1b', label };
  if (abs < 20)  return { bg: isDark ? 'rgba(239,68,68,0.30)'  : 'rgba(220,38,38,0.20)', text: isDark ? '#f87171' : '#b91c1c', label };
  return          { bg: isDark ? 'rgba(239,68,68,0.45)'  : 'rgba(220,38,38,0.32)', text: isDark ? '#fecaca' : '#7f1d1d', label };
}

/**
 * Switch the Gap Map between 'category' (default) and 'model' granularity.
 * Model granularity requires a category filter — otherwise we'd render
 * 40+ rows which is unreadable.
 */
function setHeatmapGranularity(mode) {
  state.heatmapGranularity = mode;
  document.getElementById('btn-heatmap-cat')?.classList.toggle('active', mode === 'category');
  document.getElementById('btn-heatmap-model')?.classList.toggle('active', mode === 'model');

  const sub = document.getElementById('heatmap-subtitle');
  if (sub) {
    sub.innerHTML = mode === 'model'
      ? `How Blue's per-day price compares to the market average for each car model. <span style="color:#16a34a;font-weight:600">Green = Blue is more expensive</span> &nbsp;·&nbsp; <span style="color:#dc2626;font-weight:600">Red = Blue is cheaper</span>`
      : `How Blue's per-day price compares to the market average, by category × month. <span style="color:#16a34a;font-weight:600">Green = Blue is more expensive</span> &nbsp;·&nbsp; <span style="color:#dc2626;font-weight:600">Red = Blue is cheaper</span>`;
  }

  if (mode === 'category') {
    renderPriceGapHeatmap();
  } else {
    loadGapByModel();
  }
}

/**
 * Fetch per-model gap data for the currently selected category and render it.
 * Keeps a small cache keyed on category to avoid refetching when toggling back.
 */
async function loadGapByModel() {
  const grid = document.getElementById('heatmap-grid');
  if (!grid) return;

  // The Gap Map is inside the Seasonal view, which has its own category filter
  const category = document.getElementById('seasonal-category')?.value || '';
  const location = document.getElementById('filter-location')?.value || '';

  if (!category) {
    grid.innerHTML = `<div style="padding:28px 20px;text-align:center;background:var(--bg-alt);border-radius:8px;color:var(--text-muted);font-size:13px">
      <div style="font-size:24px;margin-bottom:8px">🎯</div>
      <div style="font-weight:600;margin-bottom:4px;color:var(--text)">Pick a category to see model-level gaps</div>
      <div>Choose Economy, Compact, SUV, 4x4, or Minivan in the <em>Category</em> filter on the Seasonal controls — the Gap Map will then show every model in that category.</div>
    </div>`;
    return;
  }

  // Use cache if still matches this category
  if (state.gapByModelData && state.gapByModelCategory === category) {
    renderGapByModel();
    return;
  }

  grid.innerHTML = `<p style="color:var(--text-muted);font-size:13px;padding:20px"><span class="spinner" style="border-color:rgba(0,0,0,.15);border-top-color:#2563eb;width:12px;height:12px"></span> Loading model-level gaps…</p>`;
  try {
    const params = new URLSearchParams({ category });
    if (location) params.set('location', location);
    const data = await apiFetch(`/api/rates/seasonal/gap-by-model?${params}`);
    state.gapByModelData     = data;
    state.gapByModelCategory = category;
    renderGapByModel();
  } catch (e) {
    grid.innerHTML = `<p style="color:#ef4444;font-size:13px;padding:20px">Failed to load model gaps: ${escHtml(e.message)}</p>`;
  }
}

function renderGapByModel() {
  const grid = document.getElementById('heatmap-grid');
  if (!grid) return;
  const data = state.gapByModelData;
  if (!data) return;

  if (data.source === 'none' || !data.models?.length) {
    grid.innerHTML = `<div style="padding:28px 20px;text-align:center;background:var(--bg-alt);border-radius:8px;color:var(--text-muted);font-size:13px">
      <div style="font-weight:600;margin-bottom:6px;color:var(--text)">No model-level data for ${escHtml(data.category)}</div>
      <div>Run a seasonal scrape first so rates are stored, then try again.</div>
    </div>`;
    return;
  }

  const monthLabels = data.months.map(m => m.month_label);
  const colWidth    = '72px';

  // Collect all competitors that appear across any model/month
  const compSet = new Set();
  data.models.forEach(({ gaps }) => {
    gaps.forEach(g => {
      if (g?.by_competitor) Object.keys(g.by_competitor).forEach(c => compSet.add(c));
    });
  });
  const competitors = [...compSet].filter(c => c !== 'Blue Car Rental').sort();

  let html = `<table style="border-collapse:collapse;width:100%;font-size:12px">
    <thead>
      <tr>
        <th style="text-align:left;padding:8px 12px 8px 0;color:var(--text-muted);font-weight:600;white-space:nowrap;min-width:130px">Model</th>
        <th style="text-align:left;padding:8px 8px 8px 0;color:var(--text-muted);font-weight:600;white-space:nowrap;min-width:150px">vs Competitor</th>
        ${monthLabels.map(l => `<th style="text-align:center;padding:6px 4px;color:var(--text-muted);font-weight:600;min-width:${colWidth};font-size:11px;white-space:nowrap">${l}</th>`).join('')}
      </tr>
    </thead>
    <tbody>`;

  data.models.forEach(({ canonical_name, gaps }, modelIdx) => {
    // Determine which competitors appear for this model
    const modelComps = new Set();
    gaps.forEach(g => {
      if (g?.by_competitor) Object.keys(g.by_competitor).forEach(c => modelComps.add(c));
    });
    const compsForModel = [...modelComps].sort();

    if (!compsForModel.length) {
      // Blue only — no competitor data for this model
      html += `<tr style="border-top:2px solid var(--border)">
        <td style="padding:7px 12px 7px 0;font-weight:700;white-space:nowrap;color:var(--text);font-size:13px">${escHtml(canonical_name)}</td>
        <td style="padding:7px 8px 7px 0;font-size:11px;color:var(--text-muted);font-style:italic">no competitors</td>
        ${gaps.map(() => `<td style="text-align:center;padding:5px 3px"><div style="background:var(--bg-alt);color:var(--text-muted);border-radius:6px;padding:6px 4px;font-size:11px">—</div></td>`).join('')}
      </tr>`;
      return;
    }

    compsForModel.forEach((comp, compIdx) => {
      const isFirstRow  = compIdx === 0;
      const rowBorder   = isFirstRow ? 'border-top:2px solid var(--border)' : '';
      const rowBg       = compIdx % 2 === 1 ? 'background:rgba(255,255,255,0.025)' : '';
      const accentColor = COMPETITOR_COLORS[comp] || COMPETITOR_COLORS_DEFAULT;
      const modelCell   = isFirstRow
        ? `<td rowspan="${compsForModel.length}" style="padding:7px 12px 7px 0;font-weight:700;white-space:nowrap;color:var(--text);font-size:13px;vertical-align:top;${rowBorder}">${escHtml(canonical_name)}</td>`
        : '';

      html += `<tr style="${rowBorder};${rowBg}">
        ${modelCell}
        <td style="padding:5px 8px 5px 4px;white-space:nowrap;font-size:11px;font-weight:600;color:${accentColor};border-left:2px solid ${accentColor}44">${escHtml(comp)}</td>
        ${gaps.map(g => {
          if (!g) {
            return `<td style="text-align:center;padding:4px 3px"><div style="background:var(--bg-alt);color:var(--text-muted);border-radius:5px;padding:5px 3px;font-size:11px">—</div></td>`;
          }
          const compData = g.by_competitor?.[comp];
          if (!compData) {
            return `<td style="text-align:center;padding:4px 3px"><div style="background:var(--bg-alt);color:var(--text-muted);border-radius:5px;padding:5px 3px;font-size:11px;opacity:.5">—</div></td>`;
          }
          if (g.blue_price == null) {
            const tip = `No Blue price · ${escHtml(comp)} ${formatISK(compData.price)}/day`;
            return `<td style="text-align:center;padding:4px 3px" title="${tip}"><div style="background:var(--bg-alt);color:var(--text-muted);border-radius:5px;padding:5px 3px;font-size:11px;font-style:italic">n/a</div></td>`;
          }
          const { bg, text, label } = gapCellStyle(compData.gap_pct);
          const iskDiff  = Math.round(g.blue_price - compData.price);
          const iskSign  = iskDiff >= 0 ? '+' : '−';
          const iskAbs   = Math.abs(iskDiff);
          const iskShort = iskAbs >= 1000
            ? iskSign + (iskAbs / 1000).toFixed(1).replace(/\.0$/, '') + 'k'
            : iskSign + iskAbs;
          const tip = `Blue ${formatISK(g.blue_price)}/day · ${escHtml(comp)} ${formatISK(compData.price)}/day · ${label} (${iskSign}${formatISK(iskAbs)}/day)`;
          return `<td style="text-align:center;padding:4px 3px" title="${escHtml(tip)}">
            <div style="background:${bg};color:${text};border-radius:5px;padding:5px 4px;min-width:56px;line-height:1.3">
              <div style="font-weight:700;font-size:12px">${label}</div>
              <div style="font-size:10px;opacity:.85;font-weight:500">${iskShort}/d</div>
            </div>
          </td>`;
        }).join('')}
      </tr>`;
    });
  });

  html += `</tbody></table>`;

  const isDark = document.body.classList.contains('dark-mode');
  const legendGreen = isDark ? '#4ade80' : '#15803d';
  const legendRed   = isDark ? '#f87171' : '#b91c1c';
  html += `<div style="margin-top:14px;display:flex;gap:16px;font-size:11px;color:var(--text-muted);flex-wrap:wrap;align-items:center">
    <span style="display:inline-flex;align-items:center;gap:4px"><span style="display:inline-block;width:28px;height:14px;border-radius:3px;background:${isDark ? 'rgba(34,197,94,0.30)' : 'rgba(22,163,74,0.22)'}"></span><strong style="color:${legendGreen}">+%</strong> Blue pricier than competitor</span>
    <span style="display:inline-flex;align-items:center;gap:4px"><span style="display:inline-block;width:28px;height:14px;border-radius:3px;background:${isDark ? 'rgba(239,68,68,0.30)' : 'rgba(220,38,38,0.20)'}"></span><strong style="color:${legendRed}">−%</strong> Competitor undercuts Blue</span>
    <span style="opacity:.6">Neutral ≤ 3% · Hover cells for exact prices</span>
  </div>`;

  grid.innerHTML = html;
}

function renderPriceGapHeatmap() {
  const grid = document.getElementById('heatmap-grid');
  if (!grid || !state.seasonalData) {
    if (grid) grid.innerHTML = '<p style="color:#6b7280;font-size:13px;padding:20px">No seasonal data loaded. Go to Seasonal Analysis and click Refresh first.</p>';
    return;
  }

  const { months } = state.seasonalData;
  if (!months?.length) return;

  const CATEGORIES = ['Economy', 'Compact', 'SUV', '4x4', 'Minivan'];
  const CAT_EMOJI  = { Economy: '🚗', Compact: '🚙', SUV: '🛻', '4x4': '🏔️', Minivan: '🚐' };

  // Build Blue's per-day and market avg per-day for each month × category
  // month.competitors = { competitor: { category: avg_per_day } }
  // month.market_avg  = { category: avg_per_day }  (all competitors avg)
  const monthLabels = months.map(m => m.month_label);

  // For each category × month, compute gap% and keep the raw Blue/market prices
  // so the cell tooltip can show them.
  // Positive = Blue is MORE expensive than market
  // Negative = Blue is CHEAPER than market
  const rows = CATEGORIES.map(cat => {
    const gaps = months.map(m => {
      const bluePrice = m.competitors?.['Blue Car Rental']?.[cat];
      const marketAvg = m.market_avg?.[cat];
      if (bluePrice == null || marketAvg == null || marketAvg === 0) {
        return { pct: null, bluePrice, marketAvg };
      }
      return {
        pct:       Math.round((bluePrice / marketAvg - 1) * 100),
        bluePrice,
        marketAvg,
      };
    });
    return { cat, gaps };
  });

  const colWidth = '72px';

  let html = `<table style="border-collapse:collapse;width:100%;font-size:12px">
    <thead>
      <tr>
        <th style="text-align:left;padding:8px 12px 8px 0;color:var(--text-muted);font-weight:600;white-space:nowrap;min-width:100px">Category</th>
        ${monthLabels.map(l => `<th style="text-align:center;padding:6px 4px;color:var(--text-muted);font-weight:600;min-width:${colWidth};font-size:11px;white-space:nowrap">${l}</th>`).join('')}
      </tr>
    </thead>
    <tbody>`;

  rows.forEach(({ cat, gaps }) => {
    html += `<tr>
      <td style="padding:6px 12px 6px 0;font-weight:600;white-space:nowrap;color:var(--text)">${CAT_EMOJI[cat] || ''} ${cat}</td>
      ${gaps.map(g => {
        const { bg, text, label } = gapCellStyle(g.pct);
        const tip = (g.bluePrice != null && g.marketAvg != null)
          ? `Blue ${formatISK(g.bluePrice)}/day · market ${formatISK(g.marketAvg)}/day · ${label}`
          : 'No data';
        return `<td style="text-align:center;padding:5px 3px" title="${escHtml(tip)}">
          <div style="background:${bg};color:${text};border-radius:6px;padding:6px 4px;font-weight:700;font-size:12px;min-width:52px">${label}</div>
        </td>`;
      }).join('')}
    </tr>`;
  });

  html += `</tbody></table>`;

  // Legend
  const isDark = document.body.classList.contains('dark-mode');
  const legendGreen = isDark ? '#4ade80' : '#15803d';
  const legendRed   = isDark ? '#f87171' : '#b91c1c';
  html += `<div style="margin-top:14px;display:flex;gap:16px;font-size:11px;color:var(--text-muted);flex-wrap:wrap;align-items:center">
    <span style="display:inline-flex;align-items:center;gap:4px"><span style="display:inline-block;width:28px;height:14px;border-radius:3px;background:${isDark ? 'rgba(34,197,94,0.30)' : 'rgba(22,163,74,0.22)'}"></span><strong style="color:${legendGreen}">+%</strong> Blue pricier than market</span>
    <span style="display:inline-flex;align-items:center;gap:4px"><span style="display:inline-block;width:28px;height:14px;border-radius:3px;background:${isDark ? 'rgba(239,68,68,0.30)' : 'rgba(220,38,38,0.20)'}"></span><strong style="color:${legendRed}">−%</strong> Blue cheaper than market</span>
    <span style="opacity:.6">Neutral ≤ 3% · Hover cells for exact prices</span>
  </div>`;

  grid.innerHTML = html;
}

// ── COMPETITOR PRICE CHANGE TIMELINE ──────────────────────────────────────

function onTimelineCategoryChange() {
  // Reset model selector when category changes, then repopulate and reload
  const modelSel = document.getElementById('timeline-model');
  if (modelSel) { modelSel.innerHTML = '<option value="">— All Models —</option>'; }
  const cat = document.getElementById('timeline-category')?.value || '';
  populateViewModelSelector('timeline-model', cat);
  loadTimeline();
}

function onBookingCategoryChange() {
  const modelSel = document.getElementById('booking-model');
  if (modelSel) { modelSel.innerHTML = '<option value="">— All Models —</option>'; }
  const cat = document.getElementById('booking-category')?.value || '';
  populateViewModelSelector('booking-model', cat);
  loadBookingWindow();
}

async function populateViewModelSelector(selectId, categoryFilter = '') {
  const sel = document.getElementById(selectId);
  if (!sel) return;
  try {
    const { catalog } = await apiFetch('/api/rates/car-catalog');
    const CATEGORY_ORDER = ['Economy', 'Compact', 'SUV', '4x4', 'Minivan'];
    const byCategory = {};
    catalog.forEach(c => {
      if (categoryFilter && c.category !== categoryFilter) return;
      byCategory[c.category] = byCategory[c.category] || [];
      byCategory[c.category].push(c.canonical_name);
    });
    sel.innerHTML = '<option value="">— All Models —</option>';
    CATEGORY_ORDER.forEach(cat => {
      if (!byCategory[cat]) return;
      const group = document.createElement('optgroup');
      group.label = cat;
      byCategory[cat].sort().forEach(name => {
        const opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name;
        group.appendChild(opt);
      });
      sel.appendChild(group);
    });
  } catch (_) {}
}

async function loadTimeline() {
  const days     = document.getElementById('timeline-days')?.value || 30;
  const category = document.getElementById('timeline-category')?.value || '';
  const model    = document.getElementById('timeline-model')?.value || '';
  const minPct   = document.getElementById('timeline-min-pct')?.value || 5;
  const location = document.getElementById('filter-location')?.value || '';

  // Populate model selector on first load (no-op if already populated)
  const modelSel = document.getElementById('timeline-model');
  if (modelSel && modelSel.options.length <= 1) {
    populateViewModelSelector('timeline-model', category);
  }

  const loading = document.getElementById('timeline-loading');
  const feed    = document.getElementById('timeline-feed');
  if (loading) loading.style.display = '';
  if (feed)    feed.innerHTML = '';

  try {
    const params = new URLSearchParams({ days, min_change_pct: minPct });
    if (category) params.set('category', category);
    if (model)    params.set('model', model);
    if (location) params.set('location', location);
    const data = await apiFetch(`/api/rates/price-timeline?${params}`);
    renderTimeline(data.events || [], model);
  } catch (e) {
    if (feed) feed.innerHTML = `<div style="padding:40px;text-align:center;color:#6b7280;font-size:13px">Failed to load: ${escHtml(e.message)}</div>`;
  } finally {
    if (loading) loading.style.display = 'none';
  }
}

// ── Period Summary table ────────────────────────────────────────────────────

async function loadPeriodSummary() {
  const days     = document.getElementById('summary-days')?.value || 30;
  const location = document.getElementById('filter-location')?.value || '';
  const body     = document.getElementById('period-summary-body');
  if (!body) return;

  body.innerHTML = `<div style="padding:24px;text-align:center;color:#9ca3af;font-size:13px">
    <span class="spinner" style="border-color:rgba(0,0,0,.15);border-top-color:#2563eb;width:12px;height:12px;display:inline-block"></span>
    &nbsp;Loading…</div>`;

  try {
    const params = new URLSearchParams({ days });
    if (location) params.set('location', location);
    const data = await apiFetch(`/api/rates/period-summary?${params}`);
    renderPeriodSummary(data);
  } catch (e) {
    body.innerHTML = `<div style="padding:24px;text-align:center;color:#9ca3af;font-size:13px">Failed to load summary: ${escHtml(e.message)}</div>`;
  }
}

function renderPeriodSummary(data) {
  const body = document.getElementById('period-summary-body');
  if (!body) return;

  const CATS = ['Economy', 'Compact', 'SUV', '4x4', 'Minivan'];
  const { competitors = [], blue_current = {}, days } = data;

  if (!competitors.length) {
    body.innerHTML = `<div style="padding:24px;text-align:center;color:#9ca3af;font-size:13px">No data for this period yet — run a scrape to populate.</div>`;
    return;
  }

  // Cell renderer — returns td HTML
  function cell(d) {
    if (!d) return `<td style="text-align:center;padding:10px 6px;color:#d1d5db">—</td>`;

    const { change_pct, vs_blue_pct, first, last, scrape_count } = d;
    const hasHistory = change_pct !== null && change_pct !== undefined;

    let topHtml;
    if (!hasHistory) {
      topHtml = `<span style="font-size:11px;color:#9ca3af">snapshot only</span>`;
    } else if (Math.abs(change_pct) < 1) {
      topHtml = `<span style="font-size:13px;font-weight:700;color:#6b7280">Stable</span>`;
    } else {
      const col  = change_pct > 0 ? '#16a34a' : '#dc2626';
      const sign = change_pct > 0 ? '+' : '';
      topHtml = `<span style="font-size:15px;font-weight:800;color:${col}">${sign}${change_pct.toFixed(1)}%</span>`;
    }

    let vsHtml = '';
    if (vs_blue_pct !== null && vs_blue_pct !== undefined) {
      const vc  = vs_blue_pct < 0 ? '#dc2626' : '#16a34a';
      const vs  = vs_blue_pct > 0 ? '+' : '';
      const lbl = vs_blue_pct < 0 ? 'vs Blue ↓' : 'vs Blue ↑';
      vsHtml = `<div style="font-size:10px;color:${vc};margin-top:3px;font-weight:600">${vs}${vs_blue_pct.toFixed(1)}% ${lbl}</div>`;
    }

    const bg = !hasHistory ? '' : change_pct > 5
      ? 'background:rgba(22,163,74,.06);'
      : change_pct < -5
        ? 'background:rgba(220,38,38,.06);'
        : '';
    const title = hasHistory
      ? `title="${formatISK(first)}/day → ${formatISK(last)}/day · ${scrape_count} scrapes"`
      : `title="${formatISK(last)}/day (single snapshot)"`;

    return `<td style="text-align:center;padding:10px 6px;${bg}vertical-align:middle" ${title}>
      ${topHtml}${vsHtml}
    </td>`;
  }

  const isDark = document.body.classList.contains('dark-mode');
  const thStyle = `padding:8px 6px;font-size:11px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em;text-align:center;border-bottom:2px solid var(--border);white-space:nowrap`;
  const tdNameStyle = `padding:10px 12px;font-size:12px;font-weight:600;color:var(--text);white-space:nowrap;border-right:1px solid var(--border)`;

  let rows = competitors.map(c => {
    const dot = `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${compColor(c.competitor)};margin-right:6px;flex-shrink:0"></span>`;
    const cats = CATS.map(cat => cell(c.categories[cat])).join('');
    return `<tr style="border-bottom:1px solid var(--border)">
      <td style="${tdNameStyle}">${dot}${escHtml(c.competitor)}</td>
      ${cats}
    </tr>`;
  }).join('');

  // Blue reference row
  const blueRef = CATS.map(cat => {
    const p = blue_current[cat];
    return p
      ? `<td style="text-align:center;padding:8px 6px;font-size:12px;font-weight:700;color:var(--text)">${formatISK(p)}<span style="font-size:10px;font-weight:400;color:var(--text-muted)">/day</span></td>`
      : `<td style="text-align:center;color:#d1d5db">—</td>`;
  }).join('');

  body.innerHTML = `
    <div style="overflow-x:auto">
      <table style="width:100%;border-collapse:collapse;min-width:560px">
        <thead>
          <tr style="border-bottom:2px solid var(--border)">
            <th style="${thStyle};text-align:left;padding-left:12px">Competitor</th>
            ${CATS.map(c => `<th style="${thStyle}">${c}</th>`).join('')}
          </tr>
        </thead>
        <tbody>
          ${rows}
          <tr style="background:rgba(37,99,235,.04);border-top:2px solid var(--border)">
            <td style="${tdNameStyle};color:#2563eb">
              <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#2563eb;margin-right:6px"></span>
              Blue (reference)
            </td>
            ${blueRef}
          </tr>
        </tbody>
      </table>
    </div>
    <div style="padding:8px 12px;font-size:11px;color:var(--text-muted)">
      % = actual price change over ${days} days (first scrape → latest scrape in window). Hover a cell for absolute prices.
    </div>`;
}

// ── Model Lens ──────────────────────────────────────────────────────────────

async function initModelLens() {
  const sel = document.getElementById('lens-model');
  if (!sel || sel.options.length > 1) return;
  try {
    const catalog = state.catalog
      ? state.catalog
      : (await apiFetch('/api/rates/car-catalog')).catalog || [];
    if (!state.catalog) state.catalog = catalog;
    const sorted = [...catalog].sort((a, b) => a.canonical_name.localeCompare(b.canonical_name));
    sel.innerHTML = '<option value="">— Pick a model —</option>' +
      sorted.map(c => `<option value="${escHtml(c.canonical_name)}">${escHtml(c.canonical_name)}</option>`).join('');
  } catch (_) {}
}

async function loadModelLens() {
  const model    = document.getElementById('lens-model')?.value || '';
  const location = document.getElementById('filter-location')?.value || '';
  const body     = document.getElementById('lens-body');
  if (!body) return;

  if (!model) {
    body.innerHTML = `<div style="padding:30px;text-align:center;color:#9ca3af;font-size:13px">Select a model above to compare prices across competitors.</div>`;
    return;
  }

  body.innerHTML = `<div style="padding:24px;text-align:center;color:#9ca3af;font-size:13px">
    <span class="spinner" style="border-color:rgba(0,0,0,.15);border-top-color:#2563eb;width:12px;height:12px;display:inline-block"></span>
    &nbsp;Loading…</div>`;

  try {
    const ratesParams = new URLSearchParams({ car_model: model });
    if (location) ratesParams.set('location', location);
    const tlParams = new URLSearchParams({ model, days: 90, min_change_pct: 1 });
    if (location) tlParams.set('location', location);

    const [ratesData, tlData] = await Promise.all([
      apiFetch(`/api/rates?${ratesParams}`),
      apiFetch(`/api/rates/price-timeline?${tlParams}`).catch(() => ({ events: [] })),
    ]);

    renderModelLens(model, ratesData.rates || [], tlData.events || []);
  } catch (e) {
    body.innerHTML = `<div style="padding:24px;text-align:center;color:#9ca3af;font-size:13px">Failed to load: ${escHtml(e.message)}</div>`;
  }
}

function renderModelLens(model, rates, events) {
  const body = document.getElementById('lens-body');
  if (!body) return;

  if (!rates.length) {
    body.innerHTML = `<div style="padding:30px;text-align:center;color:#9ca3af;font-size:13px">No rate data found for <strong>${escHtml(model)}</strong> yet.</div>`;
    return;
  }

  // Aggregate: best (lowest) price per competitor for this model
  const byComp = {};
  rates.forEach(r => {
    const perDay = r.price_isk / Math.max((new Date(r.return_date) - new Date(r.pickup_date)) / 86400000, 1);
    if (!byComp[r.competitor] || perDay < byComp[r.competitor].per_day) {
      byComp[r.competitor] = { per_day: perDay, price_isk: r.price_isk, car_category: r.car_category };
    }
  });

  const sorted = Object.entries(byComp).sort((a, b) => a[1].per_day - b[1].per_day);
  const blueEntry = byComp['Blue Car Rental'];
  const maxPrice  = Math.max(...sorted.map(([, v]) => v.per_day));
  const category  = sorted[0]?.[1]?.car_category || '';

  // Bar chart rows
  const barsHtml = sorted.map(([comp, v], i) => {
    const pct    = (v.per_day / maxPrice * 100).toFixed(1);
    const color  = compColor(comp);
    const rank   = i + 1;
    let vsBadge  = '';
    if (blueEntry && comp !== 'Blue Car Rental') {
      const diff    = ((v.per_day - blueEntry.per_day) / blueEntry.per_day * 100).toFixed(1);
      const isBelow = diff < 0;
      const badgeC  = isBelow ? '#dc2626' : '#16a34a';
      const sign    = diff > 0 ? '+' : '';
      vsBadge = `<span style="font-size:10px;font-weight:700;color:${badgeC};margin-left:8px">${sign}${diff}% vs Blue</span>`;
    }
    const rankBadge = rank === 1
      ? `<span style="font-size:10px;background:#16a34a;color:#fff;border-radius:4px;padding:1px 5px;margin-left:6px">cheapest</span>`
      : '';

    return `<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">
      <div style="width:130px;font-size:12px;font-weight:600;color:var(--text);flex-shrink:0;text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escHtml(comp)}</div>
      <div style="flex:1;background:var(--bg-alt);border-radius:4px;height:22px;overflow:hidden">
        <div style="height:100%;width:${pct}%;background:${color};border-radius:4px;transition:width .4s ease;opacity:.85"></div>
      </div>
      <div style="width:110px;font-size:13px;font-weight:700;color:var(--text);flex-shrink:0">
        ${formatISK(Math.round(v.per_day))}<span style="font-size:10px;font-weight:400;color:var(--text-muted)">/day</span>
        ${vsBadge}${rankBadge}
      </div>
    </div>`;
  }).join('');

  // History sparkline using events (if any)
  let chartHtml = '';
  if (events.length) {
    // Build per-competitor time series from events
    const byCompEvents = {};
    events.forEach(ev => {
      byCompEvents[ev.competitor] = byCompEvents[ev.competitor] || [];
      byCompEvents[ev.competitor].push(ev);
    });
    Object.values(byCompEvents).forEach(arr => arr.sort((a, b) => a.scraped_at.localeCompare(b.scraped_at)));

    const dateSet = new Set();
    Object.values(byCompEvents).forEach(arr => arr.forEach(ev => dateSet.add(ev.scraped_at.slice(0, 10))));
    const dates = Array.from(dateSet).sort();

    if (dates.length >= 2) {
      const comps = Object.keys(byCompEvents).sort();
      const isDark    = document.body.classList.contains('dark-mode');
      const gridColor = isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.06)';
      const tickColor = isDark ? '#9ca3af' : '#6b7280';

      const datasets = comps.map(comp => {
        const priceMap = {};
        byCompEvents[comp].forEach(ev => { priceMap[ev.scraped_at.slice(0, 10)] = ev.curr_per_day; });
        return {
          label: comp,
          data: dates.map(d => priceMap[d] ?? null),
          borderColor: compColor(comp),
          backgroundColor: compColor(comp) + '18',
          tension: 0.35,
          pointRadius: 4,
          borderWidth: 2,
          spanGaps: true,
        };
      });

      chartHtml = `
        <div style="margin-top:20px;border-top:1px solid var(--border);padding-top:16px">
          <div style="font-size:11px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px">Price History (last 90 days)</div>
          <div style="position:relative;height:220px"><canvas id="lens-history-chart"></canvas></div>
        </div>`;

      // Render chart after DOM update
      setTimeout(() => {
        const ctx = document.getElementById('lens-history-chart')?.getContext('2d');
        if (!ctx) return;
        if (state.lensHistoryChart) state.lensHistoryChart.destroy();
        state.lensHistoryChart = new Chart(ctx, {
          type: 'line',
          data: {
            labels: dates.map(d => { const dt = new Date(d + 'T00:00:00'); return dt.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }); }),
            datasets,
          },
          options: {
            responsive: true, maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
              legend: { display: true, position: 'bottom', labels: { color: tickColor, boxWidth: 10, padding: 14, font: { size: 11 } } },
              tooltip: { callbacks: { label: c => c.parsed.y != null ? ` ${c.dataset.label}: ${formatISK(c.parsed.y)}/day` : ` ${c.dataset.label}: no data` } },
            },
            scales: {
              x: { grid: { color: gridColor }, ticks: { color: tickColor, font: { size: 10 }, maxRotation: 30 } },
              y: { grid: { color: gridColor }, ticks: { color: tickColor, font: { size: 11 }, callback: v => formatISK(v) } },
            },
          },
        });
      }, 50);
    }
  }

  body.innerHTML = `
    <div style="padding:4px 0 12px">
      <div style="font-size:11px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:14px">${escHtml(model)} ${category ? '· ' + category : ''}</div>
      ${barsHtml}
    </div>
    ${chartHtml}`;
}

function renderTimeline(events, modelFilter = '') {
  const feed = document.getElementById('timeline-feed');
  if (!feed) return;

  if (!events.length) {
    feed.innerHTML = `<div style="padding:60px;text-align:center;color:#6b7280;font-size:13px">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:36px;height:36px;margin-bottom:10px;opacity:.4;display:block;margin-left:auto;margin-right:auto"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
      No price changes found matching these filters. Try a wider date range or lower threshold.
    </div>`;
    return;
  }

  // When a specific model is selected, render a chart showing its price history per competitor
  if (modelFilter) {
    renderTimelineModelChart(events, modelFilter);
    return;
  }

  // Group events by date (scraped_at date)
  const byDate = {};
  events.forEach(ev => {
    const date = ev.scraped_at.slice(0, 10);
    byDate[date] = byDate[date] || [];
    byDate[date].push(ev);
  });

  const dateKeys = Object.keys(byDate).sort().reverse();
  const CAT_EMOJI = { Economy:'🚗', Compact:'🚙', SUV:'🛻', '4x4':'🏔️', Minivan:'🚐' };

  let html = '';
  dateKeys.forEach(date => {
    const dt = new Date(date + 'T00:00:00');
    const dateLabel = dt.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });

    html += `<div style="margin-bottom:6px;padding:6px 0 2px;font-size:11px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid var(--border)">${dateLabel}</div>`;

    byDate[date].forEach(ev => {
      const isUp     = ev.direction === 'up';
      const color    = compColor(ev.competitor);
      const arrow    = isUp ? '↑' : '↓';
      const pctStr   = (isUp ? '+' : '') + ev.change_pct.toFixed(1) + '%';
      const pctColor = isUp ? '#dc2626' : '#16a34a';
      const cat      = ev.car_category;

      // Blue market rank badge
      let rankBadge = '';
      if (ev.blue_rank != null) {
        const rankColor = ev.blue_rank === 1 ? '#16a34a' : ev.blue_rank <= 2 ? '#ca8a04' : '#dc2626';
        const rankLabel = ev.blue_rank === 1 ? '🥇 Blue cheapest' : `Blue #${ev.blue_rank}/${ev.total_competitors}`;
        rankBadge = `<div style="display:inline-flex;align-items:center;gap:4px;margin-top:4px;padding:2px 7px;border-radius:20px;border:1px solid ${rankColor}33;background:${rankColor}11;font-size:10px;font-weight:700;color:${rankColor}">${rankLabel}</div>`;
      }

      html += `
        <div style="display:flex;align-items:center;gap:12px;padding:10px 12px;background:var(--bg);border:1px solid var(--border);border-radius:8px;margin-bottom:6px">
          <div style="width:10px;height:10px;border-radius:50%;background:${color};flex-shrink:0"></div>
          <div style="font-size:12px;font-weight:600;color:var(--text);min-width:110px;flex-shrink:0">${escHtml(ev.competitor)}</div>
          <div style="flex:1;min-width:0">
            <div style="font-size:13px;font-weight:600;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escHtml(ev.canonical_name)}</div>
            <div style="font-size:11px;color:var(--text-muted)">${CAT_EMOJI[cat] || ''} ${cat}</div>
          </div>
          <div style="text-align:right;flex-shrink:0">
            <div style="font-size:13px;font-weight:700;color:${pctColor}">${arrow} ${pctStr}</div>
            <div style="font-size:11px;color:var(--text-muted)">${formatISK(ev.prev_per_day)} → ${formatISK(ev.curr_per_day)}<span style="color:#9ca3af">/day</span></div>
            ${rankBadge}
          </div>
        </div>`;
    });
  });

  feed.innerHTML = html;
}

function renderTimelineModelChart(events, model) {
  const feed = document.getElementById('timeline-feed');
  if (!feed) return;

  // Build per-competitor time series from events
  // Each event = a price change snapshot; we want absolute price over time
  // Reconstruct: starting from prev_per_day at first event, then curr_per_day at each change
  const byComp = {};
  events.forEach(ev => {
    byComp[ev.competitor] = byComp[ev.competitor] || [];
    byComp[ev.competitor].push(ev);
  });

  // Sort each competitor's events chronologically
  Object.values(byComp).forEach(arr => arr.sort((a, b) => a.scraped_at.localeCompare(b.scraped_at)));

  const competitors = Object.keys(byComp).sort();

  // Collect all unique dates across all competitor events (both prev and curr points)
  const dateSet = new Set();
  Object.values(byComp).forEach(arr => {
    arr.forEach(ev => dateSet.add(ev.scraped_at.slice(0, 10)));
  });
  const dates = Array.from(dateSet).sort();

  if (!dates.length) {
    feed.innerHTML = '<div style="padding:40px;text-align:center;color:#6b7280;font-size:13px">No price change data for this model yet.</div>';
    return;
  }

  const isDark    = document.body.classList.contains('dark-mode');
  const gridColor = isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.06)';
  const tickColor = isDark ? '#9ca3af' : '#6b7280';

  const datasets = competitors.map((comp, i) => {
    // Build a price-at-date map: for each date we have curr_per_day
    const priceMap = {};
    byComp[comp].forEach(ev => {
      priceMap[ev.scraped_at.slice(0, 10)] = ev.curr_per_day;
    });
    return {
      label: comp,
      data: dates.map(d => priceMap[d] ?? null),
      borderColor: compColor(comp, i),
      backgroundColor: compColor(comp, i) + '18',
      tension: 0.35,
      pointRadius: 5,
      pointHoverRadius: 7,
      borderWidth: 2.5,
      spanGaps: true,
    };
  });

  const labels = dates.map(d => {
    const dt = new Date(d + 'T00:00:00');
    return dt.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
  });

  // Render chart container + summary cards
  feed.innerHTML = `
    <div class="card" style="margin-bottom:16px">
      <div class="card-header">
        <div>
          <div class="card-title">${escHtml(model)} — Price History</div>
          <div class="card-subtitle">Price at each scrape where a change was detected — per competitor</div>
        </div>
      </div>
      <div style="position:relative;height:320px"><canvas id="timeline-model-chart"></canvas></div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin-bottom:16px" id="timeline-model-cards"></div>
  `;

  const ctx = document.getElementById('timeline-model-chart')?.getContext('2d');
  if (!ctx) return;

  if (state.timelineModelChart) state.timelineModelChart.destroy();
  state.timelineModelChart = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: true, position: 'bottom', labels: { color: tickColor, boxWidth: 12, padding: 16, font: { size: 12 } } },
        tooltip: {
          callbacks: {
            label: ctx => ctx.parsed.y != null
              ? ` ${ctx.dataset.label}: ${formatISK(ctx.parsed.y)}/day`
              : ` ${ctx.dataset.label}: no change recorded`,
          },
        },
      },
      scales: {
        x: { grid: { color: gridColor }, ticks: { color: tickColor, font: { size: 11 }, maxRotation: 45 } },
        y: { grid: { color: gridColor }, ticks: { color: tickColor, font: { size: 11 }, callback: v => formatISK(v) } },
      },
    },
  });

  // Summary cards: last known price + net change per competitor
  const cardsEl = document.getElementById('timeline-model-cards');
  if (cardsEl) {
    cardsEl.innerHTML = competitors.map((comp, i) => {
      const arr     = byComp[comp];
      const first   = arr[0];
      const last    = arr[arr.length - 1];
      const netPct  = ((last.curr_per_day / first.prev_per_day) - 1) * 100;
      const isUp    = netPct > 0;
      const trend   = Math.abs(netPct) < 1 ? 'Stable' : (isUp ? `↑ +${netPct.toFixed(1)}%` : `↓ ${netPct.toFixed(1)}%`);
      const tColor  = Math.abs(netPct) < 1 ? '#6b7280' : isUp ? '#dc2626' : '#16a34a';
      return `<div style="background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:14px 16px">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
          <div style="width:10px;height:10px;border-radius:50%;background:${compColor(comp, i)};flex-shrink:0"></div>
          <div style="font-size:12px;font-weight:600;color:var(--text)">${escHtml(comp)}</div>
        </div>
        <div style="font-size:20px;font-weight:700;color:var(--text)">${formatISK(last.curr_per_day)}<span style="font-size:11px;font-weight:400;color:var(--text-muted)">/day</span></div>
        <div style="font-size:11px;margin-top:4px;font-weight:600;color:${tColor}">${trend} overall · ${arr.length} change${arr.length !== 1 ? 's' : ''}</div>
      </div>`;
    }).join('');
  }
}

// ── BOOKING WINDOW / LEAD TIME ANALYSIS ───────────────────────────────────

function initBookingWindow() {
  // Set a sensible default pickup date — next month's 15th
  const el = document.getElementById('booking-pickup-date');
  if (el && !el.value) {
    const d = new Date();
    d.setMonth(d.getMonth() + 1);
    d.setDate(15);
    el.value = d.toISOString().slice(0, 10);
  }
  populateViewModelSelector('booking-model');
}

async function loadBookingWindow() {
  const pickupDate = document.getElementById('booking-pickup-date')?.value;
  const category   = document.getElementById('booking-category')?.value || '';
  const model      = document.getElementById('booking-model')?.value || '';
  const location   = document.getElementById('filter-location')?.value || '';

  const prompt    = document.getElementById('booking-prompt');
  const chartCard = document.getElementById('booking-chart-card');
  const loading   = document.getElementById('booking-loading');
  const noData    = document.getElementById('booking-no-data');
  const insights  = document.getElementById('booking-insights');

  if (!pickupDate) {
    if (prompt)    prompt.style.display = '';
    if (chartCard) chartCard.style.display = 'none';
    if (insights)  insights.style.display = 'none';
    return;
  }

  if (prompt)    prompt.style.display = 'none';
  if (chartCard) chartCard.style.display = '';
  if (loading)   loading.style.display = '';
  if (noData)    noData.style.display = 'none';
  if (insights)  insights.style.display = 'none';

  // Update title
  const titleEl = document.getElementById('booking-chart-title');
  const dt = new Date(pickupDate + 'T00:00:00');
  const dateLabel = dt.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
  const modelLabel = model ? ` · ${model}` : (category ? ` · ${category}` : '');
  if (titleEl) titleEl.textContent = `Price Trajectory — Pickup ${dateLabel}${modelLabel}`;

  try {
    const params = new URLSearchParams({ pickup_date: pickupDate });
    if (model)    params.set('model', model);
    else if (category) params.set('category', category);
    if (location) params.set('location', location);
    const data = await apiFetch(`/api/rates/booking-window?${params}`);
    renderBookingChart(data, pickupDate);
  } catch (e) {
    if (noData) noData.style.display = '';
    showToast(`Booking window load failed: ${e.message}`, 'error');
  } finally {
    if (loading) loading.style.display = 'none';
  }
}

function renderBookingChart(data, pickupDate) {
  const series    = data.series || {};
  const noData    = document.getElementById('booking-no-data');
  const insights  = document.getElementById('booking-insights');
  const insCards  = document.getElementById('booking-insight-cards');

  const competitors = Object.keys(series).sort();
  if (!competitors.length) {
    if (noData)   noData.style.display = '';
    if (insights) insights.style.display = 'none';
    return;
  }

  // Collect all scrape dates, sorted ascending
  const dateSet = new Set();
  competitors.forEach(c => series[c].forEach(p => dateSet.add(p.scraped_at.slice(0,10))));
  const scrapeDates = Array.from(dateSet).sort();

  const pickup = new Date(pickupDate + 'T00:00:00');

  // Labels: "X weeks before pickup" (or the date if too close)
  const labels = scrapeDates.map(d => {
    const scrape = new Date(d + 'T00:00:00');
    const diffMs = pickup - scrape;
    const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));
    const diffWeeks = Math.round(diffDays / 7);
    if (diffDays <= 0) return 'Pickup day';
    if (diffDays < 7)  return `${diffDays}d before`;
    return `${diffWeeks}w before`;
  });

  const datasets = competitors.map((comp, i) => {
    const priceMap = {};
    series[comp].forEach(p => { priceMap[p.scraped_at.slice(0,10)] = p.per_day; });
    return {
      label: comp,
      data: scrapeDates.map(d => priceMap[d] ?? null),
      borderColor: compColor(comp, i),
      backgroundColor: compColor(comp, i) + '18',
      tension: 0.35,
      pointRadius: 5,
      pointHoverRadius: 7,
      borderWidth: 2.5,
      spanGaps: false,
    };
  });

  const isDark    = document.body.classList.contains('dark-mode');
  const gridColor = isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.06)';
  const tickColor = isDark ? '#9ca3af' : '#6b7280';

  const canvas = document.getElementById('booking-chart');
  if (!canvas) return;

  if (state.bookingChart) state.bookingChart.destroy();
  state.bookingChart = new Chart(canvas.getContext('2d'), {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: true, position: 'bottom', labels: { color: tickColor, boxWidth: 12, padding: 16, font: { size: 12 } } },
        tooltip: {
          callbacks: {
            title: items => {
              const d = scrapeDates[items[0].dataIndex];
              const dt2 = new Date(d + 'T00:00:00');
              return 'Scraped: ' + dt2.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
            },
            label: ctx => ctx.parsed.y != null
              ? ` ${ctx.dataset.label}: ${formatISK(ctx.parsed.y)}/day`
              : ` ${ctx.dataset.label}: no data`,
          },
        },
      },
      scales: {
        x: { grid: { color: gridColor }, ticks: { color: tickColor, font: { size: 11 } } },
        y: { grid: { color: gridColor }, ticks: { color: tickColor, font: { size: 11 }, callback: v => formatISK(v) } },
      },
    },
  });

  // Insight cards: first vs last price per competitor
  if (insCards && scrapeDates.length >= 2) {
    const firstDate = scrapeDates[0];
    const lastDate  = scrapeDates[scrapeDates.length - 1];
    insCards.innerHTML = competitors.map((comp, i) => {
      const priceMap = {};
      series[comp].forEach(p => { priceMap[p.scraped_at.slice(0,10)] = p.per_day; });
      const first = priceMap[firstDate];
      const last  = priceMap[lastDate];
      if (!first || !last) return '';
      const pct  = Math.round((last / first - 1) * 100);
      const isUp = pct > 0;
      const color = compColor(comp, i);
      const trend = pct === 0 ? 'Stable' : (isUp ? `↑ +${pct}% since first scrape` : `↓ ${pct}% since first scrape`);
      const trendColor = pct === 0 ? '#6b7280' : isUp ? '#dc2626' : '#16a34a';
      return `<div style="background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:14px 16px">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
          <div style="width:10px;height:10px;border-radius:50%;background:${color};flex-shrink:0"></div>
          <div style="font-size:12px;font-weight:600;color:var(--text)">${escHtml(comp)}</div>
        </div>
        <div style="font-size:20px;font-weight:700;color:var(--text)">${formatISK(last)}<span style="font-size:11px;color:var(--text-muted);font-weight:400">/day</span></div>
        <div style="font-size:11px;margin-top:4px;color:${trendColor};font-weight:600">${trend}</div>
      </div>`;
    }).join('');
    insights.style.display = '';
  }
}

// ── FORWARD RATES (HORIZON) VIEW ───────────────────────────────────────────

function setHorizonCategory(cat) {
  state.horizonCategory = cat;
  ['', 'Economy', 'Compact', 'SUV', '4x4', 'Minivan'].forEach(c => {
    const btn = document.getElementById(`hfwd-btn-${c}`);
    if (btn) btn.classList.toggle('active', c === cat);
  });
  state.horizonData = null; // force reload with new category filter
  loadHorizon();
}

function setHorizonRange(weeks) {
  state.horizonWeeks = weeks;
  [13, 26, 52].forEach(w => {
    const btn = document.getElementById(`hfwd-range-${w}`);
    if (btn) btn.classList.toggle('active', w === weeks);
  });
  state.horizonData = null;
  if (state.horizonModel) {
    renderModelHorizonChart(); // re-slice existing data to new range
  } else {
    loadHorizon();
  }
}

async function loadHorizon(force = false) {
  if (state.horizonData && !force) {
    renderHorizonChart();
    renderHorizonTable();
    return;
  }

  const loading = document.getElementById('horizon-loading');
  if (loading) loading.style.display = '';

  populateModelSelector();

  const location = document.getElementById('filter-location').value;
  const params = new URLSearchParams();
  if (location)               params.set('location', location);
  if (state.horizonCategory)  params.set('category', state.horizonCategory);

  try {
    params.set('weeks', String(state.horizonWeeks || 26));
    const data = await apiFetch(`/api/rates/horizon?${params}`);
    state.horizonData = data;
    setSourceBadge('horizon-source-badge', data.source);
    document.querySelectorAll('#horizon-source-badge').forEach(el => el.style.display = '');
    renderHorizonChart();
    renderHorizonTable();
  } catch (e) {
    showToast(`Failed to load forward rates: ${e.message}`, 'error');
  } finally {
    if (loading) loading.style.display = 'none';
  }
}

function renderHorizonChart() {
  const data = state.horizonData;
  if (!data || !data.weeks || !data.weeks.length) return;

  const weeks = data.weeks;
  const labels = weeks.map(w => w.week_label);

  // Collect all competitors that appear in any week
  const compSet = new Set();
  weeks.forEach(w => Object.keys(w.competitors).forEach(c => compSet.add(c)));
  const competitors = Array.from(compSet).sort();

  const field = state.horizonCategory || '_overall';
  const titleEl = document.getElementById('horizon-chart-title');
  if (titleEl) {
    const rangeLabel = state.horizonWeeks === 13 ? '3 Months' : state.horizonWeeks === 52 ? '12 Months' : '6 Months';
    titleEl.textContent = state.horizonCategory
      ? `Price Horizon — ${state.horizonCategory} · Next ${rangeLabel}`
      : `Price Horizon — All Categories · Next ${rangeLabel}`;
  }

  const datasets = competitors.map((comp, i) => ({
    label: comp,
    data: weeks.map(w => {
      const v = w.competitors[comp]?.[field];
      return (v != null && v > 0) ? v : null;
    }),
    borderColor: compColor(comp, i),
    backgroundColor: compColor(comp, i) + '18',
    tension: 0.35,
    pointRadius: 5,
    pointHoverRadius: 7,
    borderWidth: 2,
    spanGaps: false,
  }));

  if (state.horizonChart) state.horizonChart.destroy();

  const ctx = document.getElementById('horizon-chart')?.getContext('2d');
  if (!ctx) return;

  const isDark = document.body.classList.contains('dark-mode');
  const gridColor   = isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.06)';
  const tickColor   = isDark ? '#9ca3af' : '#6b7280';

  state.horizonChart = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          display: true,
          position: 'bottom',
          labels: { color: tickColor, boxWidth: 12, padding: 16, font: { size: 12 } },
        },
        tooltip: {
          callbacks: {
            label: ctx => ctx.parsed.y != null
              ? ` ${ctx.dataset.label}: ${formatISK(ctx.parsed.y)}/day`
              : ` ${ctx.dataset.label}: —`,
          },
        },
      },
      scales: {
        x: {
          grid: { color: gridColor },
          ticks: { color: tickColor, font: { size: 11 } },
        },
        y: {
          grid: { color: gridColor },
          ticks: {
            color: tickColor,
            font: { size: 11 },
            callback: v => formatISK(v),
          },
        },
      },
    },
  });
}

function renderHorizonTable() {
  const data = state.horizonData;
  const wrap = document.getElementById('horizon-table-wrap');
  if (!data || !data.weeks || !wrap) return;

  const weeks = data.weeks;
  const compSet = new Set();
  weeks.forEach(w => Object.keys(w.competitors).forEach(c => compSet.add(c)));
  const competitors = Array.from(compSet).sort();

  const field = state.horizonCategory || '_overall';

  // Collect all values for color scaling
  const allVals = [];
  weeks.forEach(w => {
    competitors.forEach(c => {
      const v = w.competitors[c]?.[field];
      if (v != null && v > 0) allVals.push(v);
    });
  });
  const minVal = Math.min(...allVals);
  const maxVal = Math.max(...allVals);
  const range  = maxVal - minVal || 1;

  function heatStyle(val) {
    if (val == null || val <= 0) return '';
    const t = (val - minVal) / range; // 0 = cheapest, 1 = most expensive
    // green (22c55e) → yellow (eab308) → red (ef4444)
    let r, g, b;
    if (t < 0.5) {
      const s = t * 2;
      r = Math.round(34  + s * (234 - 34));
      g = Math.round(197 + s * (179 - 197));
      b = Math.round(94  + s * (8   - 94));
    } else {
      const s = (t - 0.5) * 2;
      r = Math.round(234 + s * (239 - 234));
      g = Math.round(179 + s * (68  - 179));
      b = Math.round(8   + s * (68  - 8));
    }
    const alpha = 0.25 + t * 0.55;
    // Use dark text on light (cheap) cells, white on dark (expensive) cells
    const textColor = t < 0.55 ? '#111827' : '#fff';
    return `background:rgba(${r},${g},${b},${alpha});color:${textColor};font-weight:500`;
  }

  let html = '<table><thead><tr>';
  html += '<th style="min-width:90px">Week</th>';
  competitors.forEach(c => {
    html += `<th style="text-align:center;white-space:nowrap;font-size:12px">${escHtml(c)}</th>`;
  });
  html += '<th style="text-align:center;min-width:80px">Cheapest</th>';
  html += '</tr></thead><tbody>';

  weeks.forEach(w => {
    const noData = !w.has_data;

    html += `<tr>`;
    html += `<td style="white-space:nowrap">
      <strong style="font-size:13px">${escHtml(w.week_label)}</strong>
      <div style="font-size:11px;color:#9ca3af;margin-top:2px">${w.days_out}d out</div>
    </td>`;

    if (noData) {
      html += `<td colspan="${competitors.length + 1}" style="text-align:center;color:#4b5563;font-size:12px;padding:10px;font-style:italic">
        No data — click Scrape Horizon
      </td>`;
    } else {
      // Find cheapest competitor for this week
      let cheapComp = null, cheapVal = Infinity;
      competitors.forEach(c => {
        const v = w.competitors[c]?.[field];
        if (v != null && v > 0 && v < cheapVal) { cheapVal = v; cheapComp = c; }
      });

      competitors.forEach(c => {
        const val = w.competitors[c]?.[field];
        const style = heatStyle(val);
        const isCheap = c === cheapComp && val != null;
        html += `<td style="text-align:center;font-size:12px;padding:8px 10px;${style}">`;
        if (val != null && val > 0) {
          html += isCheap ? `<strong>${formatISK(val)}</strong>` : formatISK(val);
        } else {
          html += '<span style="color:rgba(255,255,255,0.3)">—</span>';
        }
        html += '</td>';
      });

      if (cheapComp) {
        html += `<td style="text-align:center;font-size:11px;color:#22c55e;font-weight:600">${escHtml(cheapComp.split(' ')[0])}<br><span style="font-weight:400;color:#9ca3af">${formatISK(cheapVal)}</span></td>`;
      } else {
        html += `<td style="text-align:center;color:#9ca3af">—</td>`;
      }
    }

    html += '</tr>';
  });

  html += '</tbody></table>';
  wrap.innerHTML = html;
}

async function scrapeHorizon() {
  if (state.horizonScraping) return;
  state.horizonScraping = true;
  const btn = document.getElementById('btn-scrape-horizon');
  if (btn) { btn.disabled = true; btn.textContent = 'Scraping…'; }

  const location = document.getElementById('filter-location').value;
  const params = new URLSearchParams();
  if (location) params.set('location', location);

  const scrapeWeeks = state.horizonWeeks || 26;
  const rangeLabel = scrapeWeeks === 13 ? '3 months' : scrapeWeeks === 52 ? '12 months' : '6 months';
  showToast(`Scraping horizon rates (${rangeLabel})… this may take a few minutes`, 'info', 120000);
  try {
    params.set('weeks', String(scrapeWeeks));
    const result = await apiFetch(`/api/rates/scrape-horizon?${params}`, { method: 'POST' });
    showToast(
      `Scraped ${result.scraped} rates across ${result.weeks_scraped} weeks in ${result.duration_seconds}s`,
      'success',
    );
    state.horizonData = null;
    loadHorizon();
  } catch (e) {
    showToast(`Horizon scrape failed: ${e.message}`, 'error');
  } finally {
    state.horizonScraping = false;
    if (btn) { btn.disabled = false; btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="width:13px;height:13px"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg> Scrape Horizon'; }
  }
}

// ── PER-MODEL HORIZON ──────────────────────────────────────────────────────

async function populateModelSelector() {
  const sel = document.getElementById('horizon-model-select');
  if (!sel || sel.options.length > 1) return; // already populated
  try {
    const { catalog } = await apiFetch('/api/rates/car-catalog');
    const CATEGORY_ORDER = ['Economy', 'Compact', 'SUV', '4x4', 'Minivan'];
    const byCategory = {};
    catalog.forEach(c => {
      byCategory[c.category] = byCategory[c.category] || [];
      byCategory[c.category].push(c.canonical_name);
    });
    CATEGORY_ORDER.forEach(cat => {
      if (!byCategory[cat]) return;
      const group = document.createElement('optgroup');
      group.label = cat;
      byCategory[cat].sort().forEach(name => {
        const opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name;
        group.appendChild(opt);
      });
      sel.appendChild(group);
    });
  } catch (_) {}
}

function setHorizonModel(model) {
  state.horizonModel = model;
  state.modelHorizonData = null;
  // Show/hide the aggregate vs model charts
  const aggChart  = document.getElementById('horizon-chart-card');
  const modChart  = document.getElementById('model-horizon-chart-card');
  const heatCard  = document.getElementById('horizon-heatmap-card');
  if (aggChart)  aggChart.style.display  = model ? 'none' : '';
  if (heatCard)  heatCard.style.display  = model ? 'none' : '';
  if (modChart)  modChart.style.display  = model ? ''     : 'none';
  if (model) loadModelHorizon();
}

async function loadModelHorizon() {
  const model = state.horizonModel;
  if (!model) return;
  const location = document.getElementById('filter-location').value;
  const params = new URLSearchParams({ model });
  if (location) params.set('location', location);

  const loading = document.getElementById('model-horizon-loading');
  if (loading) loading.style.display = '';

  try {
    const data = await apiFetch(`/api/rates/model-horizon?${params}`);
    state.modelHorizonData = data;
    renderModelHorizonChart();
  } catch (e) {
    showToast(`Failed to load model horizon: ${e.message}`, 'error');
  } finally {
    if (loading) loading.style.display = 'none';
  }
}

function renderModelHorizonChart() {
  const data = state.modelHorizonData;
  if (!data || !data.series) return;

  const series = data.series;
  const competitors = Object.keys(series).sort();

  // Collect and sort all unique future dates, then slice to the selected range
  const dateSet = new Set();
  competitors.forEach(c => series[c].forEach(p => dateSet.add(p.pickup_date)));
  const allDates = Array.from(dateSet).sort();

  const weeks = state.horizonWeeks || 26;
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() + weeks * 7);
  const cutoffStr = cutoff.toISOString().slice(0, 10);
  const dates = allDates.filter(d => d <= cutoffStr);

  const labels = dates.map(d => {
    const dt = new Date(d + 'T00:00:00');
    return dt.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
  });

  const datasets = competitors.map((comp, i) => {
    const priceMap = {};
    series[comp].forEach(p => { priceMap[p.pickup_date] = p.per_day; });
    return {
      label: comp,
      data: dates.map(d => priceMap[d] ?? null),
      borderColor: compColor(comp, i),
      backgroundColor: compColor(comp, i) + '18',
      tension: 0.35,
      pointRadius: 5,
      pointHoverRadius: 7,
      borderWidth: 2,
      spanGaps: false,
    };
  });

  if (state.modelHorizonChart) state.modelHorizonChart.destroy();

  const ctx = document.getElementById('model-horizon-chart')?.getContext('2d');
  if (!ctx) return;

  const isDark = document.body.classList.contains('dark-mode');
  const gridColor = isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.06)';
  const tickColor = isDark ? '#9ca3af' : '#6b7280';

  const titleEl = document.getElementById('model-horizon-title');
  const rangeLabel = weeks === 13 ? '3 Months' : weeks === 52 ? '12 Months' : '6 Months';
  if (titleEl) titleEl.textContent = `${data.model} — Price per Day · Next ${rangeLabel}`;

  state.modelHorizonChart = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          display: true,
          position: 'bottom',
          labels: { color: tickColor, boxWidth: 12, padding: 16, font: { size: 12 } },
        },
        tooltip: {
          callbacks: {
            title: items => {
              const d = dates[items[0].dataIndex];
              const dt = new Date(d + 'T00:00:00');
              return dt.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'long', year: 'numeric' });
            },
            label: ctx => ctx.parsed.y != null
              ? ` ${ctx.dataset.label}: ${formatISK(ctx.parsed.y)}/day`
              : ` ${ctx.dataset.label}: no data`,
          },
        },
      },
      scales: {
        x: {
          grid: { color: gridColor },
          ticks: { color: tickColor, font: { size: 11 }, maxRotation: 45 },
        },
        y: {
          grid: { color: gridColor },
          ticks: { color: tickColor, font: { size: 11 }, callback: v => formatISK(v) },
        },
      },
    },
  });
}

function exportHorizonCSV() {
  const data = state.horizonData;
  if (!data || !data.weeks || !data.weeks.length) {
    showToast('No horizon data to export', 'warning');
    return;
  }
  const weeks = data.weeks;
  const compSet = new Set();
  weeks.forEach(w => Object.keys(w.competitors).forEach(c => compSet.add(c)));
  const competitors = Array.from(compSet).sort();
  const field = state.horizonCategory || '_overall';
  const catLabel = state.horizonCategory || 'Overall';

  const rows = [['Week', 'Pickup Date', 'Days Out', ...competitors, 'Cheapest Competitor']];
  weeks.forEach(w => {
    const vals = competitors.map(c => w.competitors[c]?.[field] ?? '');
    const prices = competitors.map((c, i) => ({ c, v: vals[i] })).filter(x => x.v);
    const cheapest = prices.length ? prices.reduce((a, b) => a.v < b.v ? a : b).c : '';
    rows.push([w.week_label, w.pickup_date, w.days_out, ...vals, cheapest]);
  });

  downloadCSV(`forward_rates_${catLabel}_${new Date().toISOString().slice(0,10)}.csv`, rows);
  showToast('Forward rates exported!', 'success');
}

function exportModelHorizonCSV() {
  const data = state.modelHorizonData;
  const model = state.horizonModel;
  if (!data || !data.series || !model) {
    showToast('No model data to export', 'warning');
    return;
  }
  const series = data.series;
  const competitors = Object.keys(series).sort();
  if (!competitors.length) {
    showToast('No data for this model yet', 'warning');
    return;
  }
  // Collect all pickup dates, then slice to the selected range
  const dateSet = new Set();
  competitors.forEach(c => (series[c] || []).forEach(r => dateSet.add(r.pickup_date)));
  const weeks = state.horizonWeeks || 26;
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() + weeks * 7);
  const cutoffStr = cutoff.toISOString().slice(0, 10);
  const dates = [...dateSet].sort().filter(d => d <= cutoffStr);

  const headers = ['Pickup Date', ...competitors.map(c => `${c} (ISK/day)`)];
  const rows = dates.map(date => {
    return [
      date,
      ...competitors.map(c => {
        const entry = (series[c] || []).find(r => r.pickup_date === date);
        return entry ? entry.per_day : '';
      }),
    ];
  });
  const slug = model.replace(/[^a-z0-9]+/gi, '_').toLowerCase();
  const rangeLabel = weeks === 13 ? '3m' : weeks === 52 ? '12m' : '6m';
  downloadCSV(`model_horizon_${slug}_${rangeLabel}_${new Date().toISOString().slice(0,10)}.csv`, [headers, ...rows]);
  showToast(`Exported ${model} horizon data (${rangeLabel.toUpperCase()})`, 'success');
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

function exportWinLossCSV() {
  if (!_wlData || !_wlData.models || !_wlData.models.length) {
    return showToast('No Win/Loss data to export. Load the scorecard first.', 'error');
  }
  const competitors = _wlData.competitors || [...new Set(_wlData.models.flatMap(m => Object.keys(m.vs)))];
  const headers = ['Model', 'Category', 'Blue ISK/day',
    ...competitors.flatMap(c => [`${c} ISK/day`, `vs ${c}`])
  ];
  const rows = _wlData.models.map(m => {
    const days = 3; // scrape window is today+7 to today+10 (3 nights)
    const bluePerDay = m.blue_price_isk ? Math.round(m.blue_price_isk / days) : '';
    const compCols = competitors.flatMap(c => {
      const v = m.vs[c];
      if (!v) return ['', ''];
      const compPerDay = v.price_isk ? Math.round(v.price_isk / days) : '';
      const outcome = v.outcome === 'win' ? 'Blue cheaper' : v.outcome === 'loss' ? 'Blue pricier' : 'Tied';
      const margin = v.margin_pct != null ? `${v.margin_pct > 0 ? '+' : ''}${v.margin_pct.toFixed(1)}%` : '';
      return [compPerDay, margin ? `${outcome} (${margin})` : outcome];
    });
    return [m.canonical_name, m.category, bluePerDay, ...compCols];
  });
  downloadCSV(`win_loss_${new Date().toISOString().slice(0, 10)}.csv`, [headers, ...rows]);
  showToast(`Exported Win/Loss data — ${rows.length} models`, 'success');
}

// ── Win/Loss Scorecard ─────────────────────────────────────────────────────
// Module-level state so drill-down survives re-renders
let _wlData       = null;  // full API response
let _wlDrillComp  = null;  // currently drilled competitor
let _wlDrillCat   = null;  // currently drilled category (null = all)

let _wlCachedLoc  = null;  // location used for last successful fetch

// ── Drill helpers ────────────────────────────────────────────────────────────

function closeWLDrill() {
  _wlDrillComp = null;
  _wlDrillCat  = null;
  const card = document.getElementById('wl-drill-card');
  if (card) card.style.display = 'none';
}

function drillWL(comp, cat) {
  _wlDrillComp = comp || null;
  _wlDrillCat  = cat  || null;
  renderWLDrill();
}

function renderWLDrill() {
  const card     = document.getElementById('wl-drill-card');
  const titleEl  = document.getElementById('wl-drill-title');
  const subEl    = document.getElementById('wl-drill-subtitle');
  const tableEl  = document.getElementById('wl-drill-table');
  if (!card || !_wlData) return;

  const CAT_EMOJI = { Economy:'🚗', Compact:'🚙', SUV:'🛻', '4x4':'🏔️', Minivan:'🚐' };

  // Filter models by category if set
  const models = _wlData.models.filter(m => !_wlDrillCat || m.category === _wlDrillCat);

  if (!models.length) { card.style.display = 'none'; return; }

  if (_wlDrillComp) {
    // Single-competitor drill: model rows vs that competitor
    titleEl.textContent  = _wlDrillComp;
    subEl.textContent    = (_wlDrillCat ? `${CAT_EMOJI[_wlDrillCat] || ''} ${_wlDrillCat} · ` : '') + 'model-by-model breakdown';

    const rows = models
      .map(m => ({ m, v: m.vs[_wlDrillComp] }))
      .filter(({ v }) => v)
      .sort((a, b) => b.v.margin_pct - a.v.margin_pct);

    if (!rows.length) { card.style.display = 'none'; return; }

    const outcomeColor = o => o === 'win' ? '#16a34a' : o === 'loss' ? '#dc2626' : '#6b7280';
    const outcomeLabel = o => o === 'win' ? '✓ Cheaper' : o === 'loss' ? '✗ Pricier' : '≈ Tied';

    tableEl.innerHTML = `
      <table style="width:100%;border-collapse:collapse;font-size:12.5px">
        <thead><tr>
          <th style="text-align:left;padding:9px 12px;border-bottom:1px solid var(--border);color:var(--text-dim);font-size:10.5px;text-transform:uppercase;letter-spacing:.08em">Model</th>
          <th style="text-align:left;padding:9px 12px;border-bottom:1px solid var(--border);color:var(--text-dim);font-size:10.5px;text-transform:uppercase;letter-spacing:.08em">Category</th>
          <th style="text-align:right;padding:9px 12px;border-bottom:1px solid var(--border);color:var(--text-dim);font-size:10.5px;text-transform:uppercase;letter-spacing:.08em">Blue</th>
          <th style="text-align:right;padding:9px 12px;border-bottom:1px solid var(--border);color:var(--text-dim);font-size:10.5px;text-transform:uppercase;letter-spacing:.08em">${escHtml(_wlDrillComp)}</th>
          <th style="text-align:center;padding:9px 12px;border-bottom:1px solid var(--border);color:var(--text-dim);font-size:10.5px;text-transform:uppercase;letter-spacing:.08em">Gap</th>
          <th style="text-align:center;padding:9px 12px;border-bottom:1px solid var(--border);color:var(--text-dim);font-size:10.5px;text-transform:uppercase;letter-spacing:.08em">Result</th>
        </tr></thead>
        <tbody>
          ${rows.map(({ m, v }, i) => `
            <tr style="${i % 2 === 1 ? 'background:rgba(148,179,255,0.03)' : ''}">
              <td style="padding:9px 12px;font-weight:600">${escHtml(m.canonical_name)}</td>
              <td style="padding:9px 12px;color:var(--text-muted)">${CAT_EMOJI[m.category] || ''} ${m.category}</td>
              <td style="padding:9px 12px;text-align:right;font-variant-numeric:tabular-nums">${formatISK(m.blue_price_isk)}</td>
              <td style="padding:9px 12px;text-align:right;font-variant-numeric:tabular-nums">${formatISK(v.price_isk)}</td>
              <td style="padding:9px 12px;text-align:center;font-weight:700;color:${outcomeColor(v.outcome)}">${v.margin_pct > 0 ? '+' : ''}${v.margin_pct}%</td>
              <td style="padding:9px 12px;text-align:center;color:${outcomeColor(v.outcome)};font-weight:600">${outcomeLabel(v.outcome)}</td>
            </tr>`).join('')}
        </tbody>
      </table>`;
  } else {
    // Category drill: all models × all competitors for that category
    titleEl.textContent = `${CAT_EMOJI[_wlDrillCat] || ''} ${_wlDrillCat || 'All'} — Model Overview`;
    subEl.textContent   = `${models.length} model${models.length !== 1 ? 's' : ''} · competitive position vs all rivals`;

    const comps = _wlData.competitors || [];

    tableEl.innerHTML = `
      <table style="width:100%;border-collapse:collapse;font-size:12px">
        <thead><tr>
          <th style="text-align:left;padding:9px 12px;border-bottom:1px solid var(--border);color:var(--text-dim);font-size:10.5px;text-transform:uppercase;letter-spacing:.08em">Model</th>
          <th style="text-align:right;padding:9px 12px;border-bottom:1px solid var(--border);color:var(--text-dim);font-size:10.5px;text-transform:uppercase;letter-spacing:.08em">Blue</th>
          <th style="text-align:center;padding:9px 12px;border-bottom:1px solid var(--border);color:var(--text-dim);font-size:10.5px;text-transform:uppercase;letter-spacing:.08em">✓ Cheaper</th>
          <th style="text-align:center;padding:9px 12px;border-bottom:1px solid var(--border);color:var(--text-dim);font-size:10.5px;text-transform:uppercase;letter-spacing:.08em">✗ Pricier</th>
          <th style="text-align:right;padding:9px 12px;border-bottom:1px solid var(--border);color:var(--text-dim);font-size:10.5px;text-transform:uppercase;letter-spacing:.08em">Best Rival</th>
          <th style="text-align:right;padding:9px 12px;border-bottom:1px solid var(--border);color:var(--text-dim);font-size:10.5px;text-transform:uppercase;letter-spacing:.08em">Gap</th>
        </tr></thead>
        <tbody>
          ${models.map((m, i) => {
            const entries = Object.entries(m.vs).filter(([, v]) => v && v.price_isk);
            const wins    = entries.filter(([, v]) => v.outcome === 'win').length;
            const losses  = entries.filter(([, v]) => v.outcome === 'loss').length;
            const compPrices = entries.map(([, v]) => v.price_isk);
            const bestRivalPrice = compPrices.length ? Math.min(...compPrices) : null;
            const bestRivalName  = bestRivalPrice
              ? (entries.find(([, v]) => v.price_isk === bestRivalPrice) || [])[0]
              : null;
            const gapPct = bestRivalPrice
              ? ((m.blue_price_isk / bestRivalPrice - 1) * 100).toFixed(1)
              : null;
            const gapColor = gapPct == null ? 'var(--text-dim)'
              : Number(gapPct) > 5  ? '#dc2626'
              : Number(gapPct) < -5 ? '#16a34a'
              : '#6b7280';
            return `
              <tr style="${i % 2 === 1 ? 'background:rgba(148,179,255,0.03)' : ''}">
                <td style="padding:9px 12px;font-weight:600">${escHtml(m.canonical_name)}</td>
                <td style="padding:9px 12px;text-align:right;font-variant-numeric:tabular-nums">${formatISK(m.blue_price_isk)}</td>
                <td style="padding:9px 12px;text-align:center;color:#16a34a;font-weight:700">${wins || '—'}</td>
                <td style="padding:9px 12px;text-align:center;color:${losses ? '#dc2626' : 'var(--text-dim)'};font-weight:700">${losses || '—'}</td>
                <td style="padding:9px 12px;text-align:right;color:var(--text-muted);font-size:11px">${bestRivalName ? escHtml(shortName(bestRivalName)) + ' ' + formatISK(bestRivalPrice) : '—'}</td>
                <td style="padding:9px 12px;text-align:right;font-weight:700;color:${gapColor}">${gapPct != null ? (Number(gapPct) > 0 ? '+' : '') + gapPct + '%' : '—'}</td>
              </tr>`;
          }).join('')}
        </tbody>
      </table>`;
  }

  card.style.display = '';
  card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

async function loadWinLoss(forceRefresh = false) {
  const loadingBar = document.getElementById('wl-loading-bar');
  const pabContent = document.getElementById('pab-content');
  const emptyEl    = document.getElementById('wl-empty');

  const loc = document.getElementById('filter-location')?.value || '';

  // Return cached data immediately if location unchanged and not forced
  if (!forceRefresh && _wlData && _wlCachedLoc === loc) {
    if (_wlData.models && _wlData.models.length > 0) {
      if (pabContent) pabContent.style.display = '';
      // Re-render scatter in case dark mode changed
      renderWLScatter();
    } else {
      emptyEl.style.display = '';
    }
    return;
  }

  loadingBar.style.display = '';
  if (pabContent) pabContent.style.display = 'none';
  emptyEl.style.display    = 'none';
  closeWLDrill();

  try {
    const qs  = loc ? `?location=${encodeURIComponent(loc)}` : '';
    _wlData      = await apiFetch(`/api/rates/win-loss${qs}`);
    _wlCachedLoc = loc;

    if (!_wlData.models || _wlData.models.length === 0) {
      emptyEl.style.display = '';
    } else {
      // Show container BEFORE rendering charts so canvas has real dimensions
      if (pabContent) pabContent.style.display = '';
      renderPABSummary();
      renderPABRisks();
      renderPABOpportunities();
      renderPABCategoryStrip();
      renderWLScatter();
    }
  } catch (e) {
    showToast('Failed to load Pricing Actions: ' + e.message, 'error');
    emptyEl.style.display = '';
  } finally {
    loadingBar.style.display = 'none';
  }
}

// ── Pricing Action Board ─────────────────────────────────────────────────────

function renderPABSummary() {
  const strip = document.getElementById('pab-summary-strip');
  if (!_wlData || !strip) return;

  const CAT_EMOJI = { Economy:'🚗', Compact:'🚙', SUV:'🛻', '4x4':'🏔️', Minivan:'🚐' };
  let riskCount = 0, oppCount = 0, neutralCount = 0;

  _wlData.models.forEach(m => {
    const entries  = Object.values(m.vs);
    const losses   = entries.filter(v => v.outcome === 'loss').length;
    const wins     = entries.filter(v => v.outcome === 'win').length;
    if (losses >= 1) {
      riskCount++;
    } else if (wins === entries.length && entries.length > 0) {
      const compPrices = Object.values(m.vs).map(v => v.price_isk).filter(Boolean);
      const headroomPct = compPrices.length
        ? Math.round((Math.min(...compPrices) - m.blue_price_isk) / m.blue_price_isk * 100)
        : 0;
      if (headroomPct >= 5) oppCount++; else neutralCount++;
    } else {
      neutralCount++;
    }
  });

  const tile = (icon, label, count, color, borderColor) => `
    <div class="card" style="padding:18px 16px;text-align:center;border-top:3px solid ${borderColor}">
      <div style="font-size:32px;font-weight:800;color:${color};line-height:1">${count}</div>
      <div style="font-size:13px;font-weight:600;color:var(--text);margin-top:5px">${icon} ${label}</div>
      <div style="font-size:11px;color:var(--text-muted);margin-top:2px">${count === 1 ? 'model' : 'models'}</div>
    </div>`;

  strip.innerHTML =
    tile('🔴', 'Risk Alerts',        riskCount,    '#dc2626', '#dc2626') +
    tile('⚪', 'At Market',           neutralCount, '#6b7280', '#4b5563') +
    tile('🟢', 'Raise Opportunities', oppCount,     '#16a34a', '#16a34a');
}

function renderPABRisks() {
  const list = document.getElementById('pab-risks-list');
  if (!_wlData || !list) return;

  const CAT_EMOJI = { Economy:'🚗', Compact:'🚙', SUV:'🛻', '4x4':'🏔️', Minivan:'🚐' };

  const risks = _wlData.models.map(m => {
    const lossEntries = Object.entries(m.vs).filter(([, v]) => v.outcome === 'loss');
    if (!lossEntries.length) return null;
    const sorted    = [...lossEntries].sort((a, b) => a[1].price_isk - b[1].price_isk);
    const [, cheapData] = sorted[0];
    const iskGap    = m.blue_price_isk - cheapData.price_isk;
    const avgUnder  = lossEntries.reduce((s, [, v]) => s + Math.abs(v.margin_pct), 0) / lossEntries.length;
    return { model: m, lossCount: lossEntries.length, cheapPrice: cheapData.price_isk, iskGap, avgUnder, lossEntries };
  }).filter(Boolean).sort((a, b) => b.lossCount - a.lossCount || b.avgUnder - a.avgUnder);

  if (!risks.length) {
    list.innerHTML = `<div style="padding:16px 14px;font-size:13px;color:#16a34a;display:flex;align-items:center;gap:8px">
      <span style="font-size:16px">✓</span> No models currently undercut by competitors
    </div>`;
    return;
  }

  list.innerHTML = risks.map((r, i) => {
    const m          = r.model;
    const matchPct   = Math.round(r.iskGap / m.blue_price_isk * 100);
    const iskStr     = r.iskGap >= 1000
      ? (r.iskGap / 1000).toFixed(1).replace(/\.0$/, '') + 'k'
      : String(r.iskGap);
    const badges     = r.lossEntries.map(([comp, v]) => {
      const col = COMPETITOR_COLORS[comp] || COMPETITOR_COLORS_DEFAULT;
      return `<span style="font-size:10px;padding:2px 7px;border-radius:4px;background:${col}22;border:1px solid ${col}44;color:${col};white-space:nowrap">${shortName(comp)} ${v.margin_pct > 0 ? '+' : ''}${v.margin_pct}%</span>`;
    }).join('');
    return `
      <div style="padding:11px 14px;${i < risks.length - 1 ? 'border-bottom:1px solid var(--border)' : ''}">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:5px">
          <div style="width:7px;height:7px;border-radius:50%;background:#dc2626;flex-shrink:0"></div>
          <div style="font-size:13px;font-weight:600;flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${escHtml(m.canonical_name)}">${escHtml(m.canonical_name)}</div>
          <span style="font-size:11px;font-weight:700;color:#dc2626;flex-shrink:0">${r.lossCount} cheaper</span>
        </div>
        <div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:5px">${badges}</div>
        <div style="font-size:11px;color:var(--text-muted)">${CAT_EMOJI[m.category] || ''} ${m.category} · Blue: ${formatISK(m.blue_price_isk)} · Cheapest: ${formatISK(r.cheapPrice)}</div>
        <div style="font-size:11px;margin-top:3px;color:#b91c1c;font-weight:600">→ Match cheapest: −${matchPct}% (−${iskStr} ISK/trip)</div>
      </div>`;
  }).join('');
}

function renderPABOpportunities() {
  const list = document.getElementById('pab-opps-list');
  if (!_wlData || !list) return;

  const CAT_EMOJI = { Economy:'🚗', Compact:'🚙', SUV:'🛻', '4x4':'🏔️', Minivan:'🚐' };

  const opps = _wlData.models.map(m => {
    const entries = Object.entries(m.vs);
    if (!entries.length) return null;
    if (entries.some(([, v]) => v.outcome === 'loss')) return null;
    const wins = entries.filter(([, v]) => v.outcome === 'win');
    if (!wins.length) return null;
    const compPrices   = entries.map(([, v]) => v.price_isk).filter(Boolean);
    if (!compPrices.length) return null;
    const nextPrice    = Math.min(...compPrices);
    const headroomIsk  = nextPrice - m.blue_price_isk;
    const headroomPct  = Math.round(headroomIsk / m.blue_price_isk * 100);
    if (headroomPct < 5) return null;
    const avgMargin    = wins.reduce((s, [, v]) => s + Math.abs(v.margin_pct), 0) / wins.length;
    return { model: m, winsCount: wins.length, total: entries.length, headroomIsk, headroomPct, avgMargin, nextPrice };
  }).filter(Boolean).sort((a, b) => b.headroomPct - a.headroomPct);

  if (!opps.length) {
    list.innerHTML = `<div style="padding:16px 14px;font-size:13px;color:var(--text-muted)">No models with significant raise headroom right now.</div>`;
    return;
  }

  list.innerHTML = opps.map((o, i) => {
    const m      = o.model;
    const iskStr = o.headroomIsk >= 1000
      ? (o.headroomIsk / 1000).toFixed(1).replace(/\.0$/, '') + 'k'
      : String(o.headroomIsk);
    return `
      <div style="padding:11px 14px;${i < opps.length - 1 ? 'border-bottom:1px solid var(--border)' : ''}">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:5px">
          <div style="width:7px;height:7px;border-radius:50%;background:#16a34a;flex-shrink:0"></div>
          <div style="font-size:13px;font-weight:600;flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${escHtml(m.canonical_name)}">${escHtml(m.canonical_name)}</div>
          <span style="font-size:11px;font-weight:700;color:#16a34a;flex-shrink:0">+${o.headroomPct}% room</span>
        </div>
        <div style="font-size:11px;color:var(--text-muted);margin-bottom:3px">${CAT_EMOJI[m.category] || ''} ${m.category} · Blue cheapest of ${o.total + 1} · avg ${o.avgMargin.toFixed(1)}% advantage</div>
        <div style="font-size:11px;color:var(--text-muted)">Next competitor: ${formatISK(o.nextPrice)} — Blue: ${formatISK(m.blue_price_isk)}</div>
        <div style="font-size:11px;margin-top:3px;color:#15803d;font-weight:600">→ Headroom: +${iskStr} ISK/trip before losing position</div>
      </div>`;
  }).join('');
}

function renderPABCategoryStrip() {
  const cells = document.getElementById('pab-cat-cells');
  if (!_wlData || !cells) return;

  const CAT_ORDER = ['Economy', 'Compact', 'SUV', '4x4', 'Minivan'];
  const CAT_EMOJI = { Economy:'🚗', Compact:'🚙', SUV:'🛻', '4x4':'🏔️', Minivan:'🚐' };

  const catKeys = CAT_ORDER.filter(c => _wlData.by_category?.[c]);
  if (!catKeys.length) { cells.parentElement?.style && (cells.closest('.card').style.display = 'none'); return; }

  cells.innerHTML = catKeys.map(cat => {
    const catData = _wlData.by_category[cat] || {};
    let wins = 0, losses = 0, ties = 0;
    Object.values(catData).forEach(c => { wins += c.wins || 0; losses += c.losses || 0; ties += c.ties || 0; });
    const total   = wins + losses + ties;
    const wr      = total > 0 ? Math.round(wins / total * 100) : null;
    const pos     = wr == null ? 'No data'      : wr >= 60 ? 'Competitive' : wr >= 40 ? 'Neutral' : 'At Risk';
    const col     = wr == null ? '#6b7280'       : wr >= 60 ? '#15803d'    : wr >= 40 ? '#854d0e' : '#b91c1c';
    const bg      = wr == null ? 'rgba(255,255,255,0.05)' : wr >= 60 ? 'rgba(22,163,74,0.1)' : wr >= 40 ? 'rgba(202,138,4,0.1)' : 'rgba(220,38,38,0.1)';
    const border  = wr == null ? 'rgba(255,255,255,0.1)'  : wr >= 60 ? 'rgba(22,163,74,0.25)' : wr >= 40 ? 'rgba(202,138,4,0.25)' : 'rgba(220,38,38,0.25)';
    return `
      <div onclick="drillWL(null,'${cat}')" style="flex:1;min-width:130px;padding:14px 16px;background:${bg};border:1px solid ${border};border-radius:8px;text-align:center;cursor:pointer;transition:opacity .15s" onmouseover="this.style.opacity='.8'" onmouseout="this.style.opacity='1'">
        <div style="font-size:22px;margin-bottom:4px">${CAT_EMOJI[cat] || ''}</div>
        <div style="font-size:12px;font-weight:700;color:var(--text);margin-bottom:2px">${cat}</div>
        <div style="font-size:14px;font-weight:800;color:${col};margin-bottom:5px">${pos}</div>
        <div style="font-size:10px;color:var(--text-muted)">${wins}W · ${ties}T · ${losses}L</div>
      </div>`;
  }).join('');
}


// ── Price Scatter chart ──────────────────────────────────────────────────────
let _wlScatterChart = null;

function renderWLScatter() {
  const card = document.getElementById('wl-scatter-card');
  if (!_wlData || !_wlData.models.length) { card.style.display = 'none'; return; }

  const catFilter = document.getElementById('wl-scatter-cat')?.value || '';
  const models = _wlData.models.filter(m => {
    if (catFilter && m.category !== catFilter) return false;
    return Object.keys(m.vs).length > 0;
  });

  if (!models.length) { card.style.display = 'none'; return; }

  // Build scatter points
  const points = models.map(m => {
    const compPrices = Object.values(m.vs).map(v => v.price_isk).filter(Boolean);
    if (!compPrices.length) return null;
    const marketAvg = compPrices.reduce((s, p) => s + p, 0) / compPrices.length;
    const wins   = Object.values(m.vs).filter(v => v.outcome === 'win').length;
    const losses = Object.values(m.vs).filter(v => v.outcome === 'loss').length;
    const total  = Object.keys(m.vs).length;
    const winRate = total > 0 ? wins / total : 0.5;
    return { x: Math.round(marketAvg), y: m.blue_price_isk, label: m.canonical_name, category: m.category, winRate, wins, losses, total };
  }).filter(Boolean);

  if (!points.length) { card.style.display = 'none'; return; }

  const pointColors = points.map(p =>
    p.winRate >= 0.6 ? 'rgba(22,163,74,0.82)' : p.winRate <= 0.4 ? 'rgba(220,38,38,0.82)' : 'rgba(202,138,4,0.82)'
  );
  const allPrices = points.flatMap(p => [p.x, p.y]);
  const minP = Math.min(...allPrices) * 0.88;
  const maxP = Math.max(...allPrices) * 1.08;
  const isDark    = document.body.classList.contains('dark-mode');
  const gridColor = isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.07)';
  const textColor = isDark ? '#9ca3af' : '#6b7280';

  if (_wlScatterChart) { _wlScatterChart.destroy(); _wlScatterChart = null; }

  const ctx = document.getElementById('wl-scatter-canvas').getContext('2d');
  _wlScatterChart = new Chart(ctx, {
    type: 'scatter',
    data: {
      datasets: [
        {
          label: 'Models',
          data: points,
          backgroundColor: pointColors,
          pointRadius: 7,
          pointHoverRadius: 10,
          order: 1,
        },
        {
          label: 'Parity (Blue = Market)',
          data: [{ x: minP, y: minP }, { x: maxP, y: maxP }],
          type: 'line',
          borderColor: isDark ? 'rgba(255,255,255,0.18)' : 'rgba(0,0,0,0.13)',
          borderWidth: 1.5,
          borderDash: [6, 4],
          pointRadius: 0,
          fill: false,
          order: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          labels: {
            filter: item => item.datasetIndex === 1,
            color: textColor,
            font: { size: 11 },
            boxWidth: 24,
          },
        },
        tooltip: {
          callbacks: {
            title: items => {
              if (items[0].datasetIndex !== 0) return '';
              const p = points[items[0].dataIndex];
              return p ? `${p.label} (${p.category})` : '';
            },
            label: item => {
              if (item.datasetIndex !== 0) return null;
              const p = points[item.dataIndex];
              return [
                `Blue: ${p.y.toLocaleString()} ISK`,
                `Market avg: ${p.x.toLocaleString()} ISK`,
                `Result: ${p.wins}W / ${p.losses}L of ${p.total} competitors`,
              ];
            },
          },
        },
      },
      scales: {
        x: {
          title: { display: true, text: 'Competitor Market Avg (ISK)', color: textColor, font: { size: 11 } },
          grid: { color: gridColor },
          ticks: { color: textColor, callback: v => Math.round(v / 1000) + 'k' },
        },
        y: {
          title: { display: true, text: 'Blue Car Rental Price (ISK)', color: textColor, font: { size: 11 } },
          grid: { color: gridColor },
          ticks: { color: textColor, callback: v => Math.round(v / 1000) + 'k' },
        },
      },
    },
  });

  card.style.display = '';
}


// ── Fleet Pressure ─────────────────────────────────────────────────────────
let _fleetChart     = null;
let _fleetSoldOutCache = [];  // last fetched sold-out records

async function loadFleetPressure() {
  const snapshotEl = document.getElementById('fleet-snapshot-cards');
  const chartCard  = document.getElementById('fleet-chart-card');
  const tableCard  = document.getElementById('fleet-table-card');
  const emptyEl    = document.getElementById('fleet-empty');

  snapshotEl.innerHTML = '<div style="grid-column:1/-1;padding:20px;color:var(--text-muted);font-size:13px">Loading…</div>';
  chartCard.style.display = 'none';
  tableCard.style.display = 'none';
  emptyEl.style.display   = 'none';
  const soldOutCard  = document.getElementById('fleet-sold-out-card');
  const calendarCard = document.getElementById('fleet-calendar-card');
  const absenceCard  = document.getElementById('fleet-absence-card');
  if (soldOutCard)  soldOutCard.style.display  = 'none';
  if (calendarCard) calendarCard.style.display = 'none';
  if (absenceCard)  absenceCard.style.display  = 'none';

  try {
    const days   = document.getElementById('fleet-days')?.value   || 30;
    const win    = document.getElementById('fleet-window')?.value || '';
    const loc    = document.getElementById('filter-location')?.value || '';

    const params = new URLSearchParams({ days });
    if (win) params.set('window_label', win);
    if (loc) params.set('location', loc);

    const locQS = loc ? '?location=' + encodeURIComponent(loc) : '';

    const [histData, snapData, soldOutData, calendarData, absenceData] = await Promise.all([
      apiFetch(`/api/fleet/pressure?${params}`),
      apiFetch(`/api/fleet/pressure/latest${locQS}`),
      apiFetch(`/api/fleet/sold-out${locQS}`),
      apiFetch(`/api/fleet/calendar${locQS}`),
      apiFetch(`/api/fleet/absence${locQS}`),
    ]);

    const records  = histData.records    || [];
    const latest   = snapData.records    || [];
    const soldOut  = soldOutData.records || [];
    const calendar = calendarData.records || [];
    const absences = absenceData.records  || [];

    _fleetSoldOutCache = soldOut;

    if (!latest.length && !records.length) {
      emptyEl.style.display = '';
      snapshotEl.innerHTML  = '';
      return;
    }

    renderFleetSnapshot(latest);
    if (records.length) {
      renderFleetChart(records);
      renderFleetTable(latest);
    }
    renderFleetSoldOut(soldOut);
    renderFleetCalendar(calendar);
    renderFleetAbsence(absences);
  } catch (e) {
    showToast('Failed to load fleet pressure: ' + e.message, 'error');
    emptyEl.style.display   = '';
    snapshotEl.innerHTML    = '';
  }
}

function renderFleetSnapshot(latest) {
  const el = document.getElementById('fleet-snapshot-cards');
  if (!latest.length) { el.innerHTML = ''; return; }

  // Group by competitor
  const byComp = {};
  latest.forEach(r => {
    byComp[r.competitor] = byComp[r.competitor] || [];
    byComp[r.competitor].push(r);
  });

  const WINDOW_LABELS = { '1w': '1 wk', '2w': '2 wks', '4w': '4 wks' };

  el.innerHTML = Object.entries(byComp).map(([comp, rows]) => {
    const color = compColor(comp);
    // Sort windows
    rows.sort((a, b) => a.window_label.localeCompare(b.window_label));
    const overall = rows.reduce((s, r) => s + r.availability_pct, 0) / rows.length;
    const avColor = overall >= 80 ? '#16a34a' : overall >= 60 ? '#ca8a04' : '#dc2626';
    const barBg   = overall >= 80 ? '#16a34a' : overall >= 60 ? '#ca8a04' : '#dc2626';

    // Count sold-out models for this competitor across all windows
    const soCount = _fleetSoldOutCache.filter(
      s => s.competitor === comp && !s.is_available
    ).length;
    const soBadge = soCount > 0
      ? `<span style="display:inline-block;background:#dc2626;color:#fff;border-radius:10px;padding:1px 7px;font-size:10px;font-weight:700;margin-left:6px">${soCount} sold out</span>`
      : '';

    const windowRows = rows.map(r => {
      const wc = r.availability_pct >= 80 ? '#16a34a' : r.availability_pct >= 60 ? '#ca8a04' : '#dc2626';
      // Count sold-out for this specific window
      const wSO = _fleetSoldOutCache.filter(
        s => s.competitor === comp && s.window_label === r.window_label && !s.is_available
      ).length;
      const wBadge = wSO > 0
        ? `<span style="font-size:10px;color:#dc2626;font-weight:600">${wSO} sold out</span>`
        : '';
      return `
        <div style="display:flex;justify-content:space-between;align-items:center;font-size:12px;padding:3px 0;gap:6px">
          <span style="color:var(--text-muted)">${WINDOW_LABELS[r.window_label] || r.window_label} out</span>
          <span style="display:flex;align-items:center;gap:6px">${wBadge}<span style="font-weight:700;color:${wc}">${r.availability_pct}%</span></span>
        </div>`;
    }).join('');

    return `
      <div class="card" style="padding:14px 16px">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
          <div style="width:10px;height:10px;border-radius:50%;background:${color};flex-shrink:0"></div>
          <div style="font-size:11px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.06em;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escHtml(comp)}</div>
          ${soBadge}
        </div>
        <div style="display:flex;align-items:baseline;gap:5px;margin-bottom:6px">
          <span style="font-size:28px;font-weight:800;line-height:1;color:${avColor}">${overall.toFixed(0)}%</span>
          <span style="font-size:11px;color:var(--text-muted)">available</span>
        </div>
        <div style="height:4px;border-radius:2px;background:var(--border);margin-bottom:12px;overflow:hidden">
          <div style="height:100%;background:${barBg};width:${overall}%;border-radius:2px"></div>
        </div>
        <div style="border-top:1px solid var(--border);padding-top:8px">${windowRows}</div>
      </div>`;
  }).join('');
}

function renderFleetChart(records) {
  const card = document.getElementById('fleet-chart-card');
  if (!records.length) { card.style.display = 'none'; return; }

  // Build time series per competitor × window
  // Key: "CompName (1w)"
  const series = {};
  records.forEach(r => {
    const key = `${r.competitor} (${r.window_label})`;
    series[key] = series[key] || [];
    series[key].push({ x: r.scraped_at.slice(0, 10), y: r.availability_pct });
  });

  // Deduplicate by date (take last value per date)
  Object.keys(series).forEach(k => {
    const byDate = {};
    series[k].forEach(p => { byDate[p.x] = p.y; });
    series[k] = Object.entries(byDate).map(([x, y]) => ({ x, y })).sort((a, b) => a.x.localeCompare(b.x));
  });

  const WINDOW_STYLE = { '1w': [], '2w': [5, 3], '4w': [2, 2] };

  const isDark    = document.body.classList.contains('dark-mode');
  const gridColor = isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.07)';
  const textColor = isDark ? '#9ca3af' : '#6b7280';

  if (_fleetChart) { _fleetChart.destroy(); _fleetChart = null; }

  const ctx = document.getElementById('fleet-chart-canvas').getContext('2d');
  _fleetChart = new Chart(ctx, {
    type: 'line',
    data: {
      datasets: Object.entries(series).map(([key, pts]) => {
        const compName = key.replace(/ \(\w+\)$/, '');
        const win      = key.match(/\((\w+)\)$/)?.[1] || '1w';
        const col      = compColor(compName);
        return {
          label:           key,
          data:            pts,
          borderColor:     col,
          backgroundColor: col + '22',
          borderWidth:     win === '1w' ? 2 : 1.5,
          borderDash:      WINDOW_STYLE[win] || [],
          pointRadius:     pts.length < 10 ? 4 : 2,
          tension:         0.3,
          fill:            false,
        };
      }),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: textColor, font: { size: 11 }, boxWidth: 24 } },
        tooltip: {
          callbacks: {
            label: item => `${item.dataset.label}: ${item.raw.y}% available`,
          },
        },
      },
      scales: {
        x: {
          type: 'category',
          grid: { color: gridColor },
          ticks: { color: textColor, maxTicksLimit: 10, font: { size: 10 } },
        },
        y: {
          min: 0, max: 100,
          title: { display: true, text: '% Available', color: textColor, font: { size: 11 } },
          grid: { color: gridColor },
          ticks: { color: textColor, callback: v => v + '%' },
        },
      },
    },
  });

  card.style.display = '';
}

function renderFleetTable(latest) {
  const card      = document.getElementById('fleet-table-card');
  const tableEl   = document.getElementById('fleet-table');
  const subtitleEl = document.getElementById('fleet-table-subtitle');
  if (!latest.length) { card.style.display = 'none'; return; }

  const comps   = [...new Set(latest.map(r => r.competitor))].sort();
  const windows = ['1w', '2w', '4w'];
  const WLABELS = { '1w': '1 week out', '2w': '2 weeks out', '4w': '4 weeks out' };

  // Build lookup: comp → window → record
  const lookup = {};
  latest.forEach(r => {
    lookup[r.competitor] = lookup[r.competitor] || {};
    lookup[r.competitor][r.window_label] = r;
  });

  const ts = latest[0]?.scraped_at ? new Date(latest[0].scraped_at).toLocaleString('en-GB', { dateStyle:'short', timeStyle:'short' }) : '';
  subtitleEl.textContent = ts ? `As of ${ts}` : '';

  let html = `<table class="rate-table" style="width:100%;border-collapse:collapse">
    <thead><tr>
      <th style="text-align:left;padding:10px 14px;font-size:12px">Competitor</th>
      ${windows.map(w => `<th style="text-align:center;padding:10px 10px;font-size:12px">${WLABELS[w]}</th>`).join('')}
    </tr></thead><tbody>`;

  comps.forEach(comp => {
    html += `<tr><td style="padding:10px 14px;font-weight:600;font-size:13px">${escHtml(comp)}</td>`;
    windows.forEach(w => {
      const r = lookup[comp]?.[w];
      if (!r) { html += `<td style="text-align:center;color:var(--text-muted);font-size:12px">—</td>`; return; }
      const pct = r.availability_pct;
      const bg  = pct >= 80 ? 'rgba(22,163,74,.15)' : pct >= 60 ? 'rgba(202,138,4,.15)' : 'rgba(220,38,38,.15)';
      const col = pct >= 80 ? '#15803d'              : pct >= 60 ? '#854d0e'              : '#b91c1c';
      html += `
        <td style="text-align:center;padding:8px 6px">
          <div style="display:inline-flex;flex-direction:column;align-items:center;min-width:80px;padding:6px 10px;border-radius:7px;background:${bg};color:${col}">
            <span style="font-size:16px;font-weight:800">${pct}%</span>
            <span style="font-size:10px;opacity:.8">${r.available_classes}/${r.total_classes} classes</span>
          </div>
        </td>`;
    });
    html += '</tr>';
  });

  html += '</tbody></table>';
  tableEl.innerHTML = html;
  card.style.display = '';
}

async function triggerFleetPoll() {
  const btn = document.getElementById('fleet-poll-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'Polling…'; }
  try {
    const data = await apiFetch('/api/fleet/poll', { method: 'POST' });
    showToast(`✓ ${data.message}`, 'success');
    await loadFleetPressure();
  } catch (e) {
    showToast('Fleet poll failed: ' + e.message, 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="width:13px;height:13px"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg> Poll Now`; }
  }
}

async function triggerFleetCalendarPoll() {
  const btn = document.getElementById('fleet-calendar-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'Sweeping 12 months…'; }
  try {
    const data = await apiFetch('/api/fleet/calendar/poll', { method: 'POST' });
    showToast(`✓ ${data.message}`, 'success');
    await loadFleetPressure();
  } catch (e) {
    showToast('Calendar sweep failed: ' + e.message, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="width:13px;height:13px"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg> Sweep 12 Months`;
    }
  }
}

// ── Option 1: Sold-out model names ─────────────────────────────────────────

function renderFleetSoldOutFromCache() {
  renderFleetSoldOut(_fleetSoldOutCache);
}

function renderFleetSoldOut(records) {
  const card     = document.getElementById('fleet-sold-out-card');
  const body     = document.getElementById('fleet-sold-out-body');
  const subtitle = document.getElementById('fleet-sold-out-subtitle');
  if (!card) return;

  const winFilter = document.getElementById('fleet-sold-out-window')?.value || '';
  const filtered  = winFilter ? records.filter(r => r.window_label === winFilter) : records;
  const soldOut   = filtered.filter(r => !r.is_available);

  if (!soldOut.length) { card.style.display = 'none'; return; }

  // Group by competitor → car_name → [{window_label, pickup_date}]
  const byComp = {};
  soldOut.forEach(r => {
    byComp[r.competitor] = byComp[r.competitor] || {};
    byComp[r.competitor][r.car_name] = byComp[r.competitor][r.car_name] || [];
    byComp[r.competitor][r.car_name].push({
      window:      r.window_label,
      pickup_date: r.pickup_date,
    });
  });

  const ts = records[0]?.scraped_at
    ? new Date(records[0].scraped_at).toLocaleString('en-GB', { dateStyle:'short', timeStyle:'short' })
    : '';
  subtitle.textContent = ts ? `As of ${ts}` : 'Models fully booked across tracked windows';

  // Window label → human-readable
  const WIN_HUMAN = { '1w': '1 week out', '2w': '2 weeks out', '4w': '4 weeks out' };

  // Format pickup date as "15 Jul" style
  const fmtDate = iso => {
    if (!iso) return '';
    const d = new Date(iso + 'T12:00:00Z');
    return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
  };

  body.innerHTML = Object.entries(byComp)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([comp, cars]) => {
      const color    = compColor(comp);
      const carCount = Object.keys(cars).length;

      const carRows = Object.entries(cars)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([car, windows]) => {
          // Sort windows by pickup_date ascending
          const sorted = windows.sort((a, b) => (a.pickup_date || '').localeCompare(b.pickup_date || ''));
          const windowPills = sorted.map(w => {
            const dateStr = w.pickup_date ? `pickup ${fmtDate(w.pickup_date)}` : (WIN_HUMAN[w.window] || w.window);
            return `<span style="display:inline-block;background:rgba(220,38,38,.10);color:#b91c1c;border:1px solid rgba(220,38,38,.22);border-radius:4px;padding:1px 7px;font-size:10px;font-weight:600;margin:1px 2px;white-space:nowrap">${escHtml(dateStr)}</span>`;
          }).join('');

          return `
            <div style="display:flex;align-items:flex-start;gap:8px;padding:4px 0 4px 14px;border-bottom:1px solid var(--border)">
              <div style="flex:0 0 auto;margin-top:3px;width:7px;height:7px;border-radius:50%;background:#dc2626"></div>
              <div style="flex:1;min-width:0">
                <span style="font-size:12px;font-weight:600;color:var(--text)">${escHtml(car)}</span>
                <div style="margin-top:3px;display:flex;flex-wrap:wrap;gap:2px">${windowPills}</div>
              </div>
            </div>`;
        }).join('');

      return `
        <div style="margin-bottom:16px;border:1px solid var(--border);border-radius:8px;overflow:hidden">
          <div style="display:flex;align-items:center;gap:8px;padding:8px 12px;background:var(--bg-alt);border-bottom:1px solid var(--border)">
            <div style="width:9px;height:9px;border-radius:50%;background:${color};flex-shrink:0"></div>
            <span style="font-size:12px;font-weight:700;color:var(--text)">${escHtml(comp)}</span>
            <span style="margin-left:auto;font-size:11px;font-weight:600;color:#b91c1c;background:rgba(220,38,38,.10);border-radius:10px;padding:1px 8px">${carCount} model${carCount !== 1 ? 's' : ''} sold out</span>
          </div>
          <div>${carRows}</div>
        </div>`;
    }).join('');

  card.style.display = '';
}

// ── Option 2: Seasonal availability calendar heatmap ───────────────────────

let _calendarSoldOutMap = {};  // key: "comp|month" → [sold-out names]

function renderFleetCalendar(records) {
  const card = document.getElementById('fleet-calendar-card');
  const body = document.getElementById('fleet-calendar-body');
  if (!card || !records.length) { if (card) card.style.display = 'none'; return; }

  // Build lookup of sold-out models per (competitor, anchor_month)
  _calendarSoldOutMap = {};
  records.forEach(r => {
    if (r.sold_out_models?.length) {
      _calendarSoldOutMap[`${r.competitor}|${r.anchor_month}`] = r.sold_out_models;
    }
  });

  const competitors = [...new Set(records.map(r => r.competitor))].sort();
  const months      = [...new Set(records.map(r => r.anchor_month))].sort();

  // Month label: "2026-04" → "Apr '26"
  const fmtMonth = m => {
    const [y, mo] = m.split('-');
    return new Date(+y, +mo - 1, 1).toLocaleString('en-GB', { month: 'short' }) + ' \'' + y.slice(2);
  };

  const cellW = 72;

  let html = `<table style="border-collapse:collapse;font-size:11px;min-width:${months.length * cellW + 160}px">
    <thead><tr>
      <th style="text-align:left;padding:8px 12px;font-size:11px;font-weight:600;white-space:nowrap;min-width:140px">Competitor</th>
      ${months.map(m => `<th style="text-align:center;padding:6px 4px;font-size:10px;font-weight:600;color:var(--text-muted);white-space:nowrap;min-width:${cellW}px">${fmtMonth(m)}</th>`).join('')}
    </tr></thead><tbody>`;

  competitors.forEach(comp => {
    const color = compColor(comp);
    html += `<tr>
      <td style="padding:8px 12px;font-size:12px;font-weight:600;white-space:nowrap">
        <span style="display:inline-flex;align-items:center;gap:6px">
          <span style="width:8px;height:8px;border-radius:50%;background:${color};display:inline-block;flex-shrink:0"></span>
          ${escHtml(comp)}
        </span>
      </td>`;
    months.forEach(month => {
      const row = records.find(r => r.competitor === comp && r.anchor_month === month);
      if (!row) {
        html += `<td style="text-align:center;padding:4px;color:var(--text-muted);font-size:11px">—</td>`;
        return;
      }
      const pct    = row.availability_pct;
      const soList = row.sold_out_models || [];
      const soN    = soList.length;
      // Colour: green→yellow→red as availability drops
      const bg  = pct >= 80 ? 'rgba(22,163,74,.18)'  : pct >= 60 ? 'rgba(202,138,4,.18)'  : pct >= 40 ? 'rgba(234,88,12,.18)' : 'rgba(220,38,38,.20)';
      const col = pct >= 80 ? '#15803d'               : pct >= 60 ? '#854d0e'               : pct >= 40 ? '#9a3412'            : '#b91c1c';
      const cursor = soN > 0 ? 'cursor:pointer' : '';
      const title  = soN > 0 ? `title="${soN} sold out"` : '';
      html += `
        <td style="text-align:center;padding:4px" ${title}>
          <div onclick="showCalendarDetail('${escHtml(comp)}','${month}')"
               style="display:inline-flex;flex-direction:column;align-items:center;min-width:58px;padding:5px 6px;border-radius:6px;background:${bg};color:${col};${cursor}">
            <span style="font-size:13px;font-weight:800;line-height:1">${pct}%</span>
            ${soN > 0 ? `<span style="font-size:9px;font-weight:600;margin-top:1px">${soN} sold out</span>` : `<span style="font-size:9px;opacity:.6">${row.available_classes}/${row.total_classes}</span>`}
          </div>
        </td>`;
    });
    html += '</tr>';
  });

  html += '</tbody></table>';
  body.innerHTML = html;
  card.style.display = '';

  const detail = document.getElementById('fleet-calendar-detail');
  if (detail) detail.style.display = 'none';
}

function showCalendarDetail(competitor, month) {
  const detail  = document.getElementById('fleet-calendar-detail');
  const title   = document.getElementById('fleet-calendar-detail-title');
  const detBody = document.getElementById('fleet-calendar-detail-body');
  if (!detail) return;

  const key   = `${competitor}|${month}`;
  const names = _calendarSoldOutMap[key] || [];

  const [y, mo] = month.split('-');
  const monthLabel = new Date(+y, +mo - 1, 1).toLocaleString('en-GB', { month: 'long', year: 'numeric' });

  title.textContent = `${competitor} — ${monthLabel}`;

  if (!names.length) {
    detBody.innerHTML = '<span style="color:var(--text-muted)">No sold-out models detected for this month.</span>';
  } else {
    // Also try to pull per-car date detail from the sold-out records cache
    // _fleetSoldOutCache contains {car_name, pickup_date, window_label, is_available, ...}
    const monthPrefix = month; // "2026-07"
    const relevantRecords = (_fleetSoldOutCache || []).filter(r =>
      r.competitor === competitor &&
      !r.is_available &&
      (r.pickup_date || '').startsWith(monthPrefix)
    );
    const carDateMap = {};
    relevantRecords.forEach(r => {
      carDateMap[r.car_name] = carDateMap[r.car_name] || [];
      if (r.pickup_date) carDateMap[r.car_name].push(r.pickup_date);
    });

    const fmtDate = iso => {
      const d = new Date(iso + 'T12:00:00Z');
      return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
    };

    detBody.innerHTML = `<div style="margin-bottom:8px;font-weight:600;color:var(--text)">${names.length} sold-out model${names.length !== 1 ? 's' : ''} in ${monthLabel}:</div>`
      + names.sort().map(n => {
          const dates = [...new Set(carDateMap[n] || [])].sort();
          const dateStr = dates.length
            ? `<span style="font-size:10px;color:var(--text-muted);margin-left:6px">${dates.map(fmtDate).join(', ')}</span>`
            : '';
          return `<div style="padding:4px 0;display:flex;align-items:center;gap:6px;border-bottom:1px solid var(--border)">
            <span style="width:5px;height:5px;border-radius:50%;background:#dc2626;display:inline-block;flex-shrink:0"></span>
            <span style="font-size:12px;font-weight:600;color:var(--text)">${escHtml(n)}</span>
            ${dateStr}
          </div>`;
        }).join('');
  }

  detail.style.display = '';
}

// ── Option 3: Absence-inferred alerts ─────────────────────────────────────

function renderFleetAbsence(records) {
  const card = document.getElementById('fleet-absence-card');
  const body = document.getElementById('fleet-absence-body');
  if (!card || !records.length) { if (card) card.style.display = 'none'; return; }

  // Group by competitor → pickup_month → car_name
  const byComp = {};
  records.forEach(r => {
    const month = r.pickup_date.slice(0, 7);
    byComp[r.competitor] = byComp[r.competitor] || {};
    byComp[r.competitor][month] = byComp[r.competitor][month] || new Set();
    byComp[r.competitor][month].add(r.car_name);
  });

  const competitors = Object.keys(byComp).sort();
  const allMonths   = [...new Set(records.map(r => r.pickup_date.slice(0, 7)))].sort();

  const fmtMonth = m => {
    const [y, mo] = m.split('-');
    return new Date(+y, +mo - 1, 1).toLocaleString('en-GB', { month: 'short', year: '2-digit' });
  };

  let html = `
    <div style="padding:10px 16px 6px;font-size:11px;color:var(--text-muted);display:flex;align-items:center;gap:6px">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:13px;height:13px;flex-shrink:0"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
      Inferred from absence in scrape results — only session-based scrapers (Hertz, Avis, Holdur). Not as reliable as direct availability data.
    </div>
    <table style="border-collapse:collapse;font-size:11px;width:100%">
      <thead><tr>
        <th style="text-align:left;padding:8px 12px;font-size:11px;font-weight:600">Competitor</th>
        ${allMonths.map(m => `<th style="text-align:center;padding:6px 4px;font-size:10px;font-weight:600;color:var(--text-muted)">${fmtMonth(m)}</th>`).join('')}
      </tr></thead><tbody>`;

  competitors.forEach(comp => {
    const color = compColor(comp);
    html += `<tr>
      <td style="padding:8px 12px;font-size:12px;font-weight:600;white-space:nowrap">
        <span style="display:inline-flex;align-items:center;gap:6px">
          <span style="width:8px;height:8px;border-radius:50%;background:${color};display:inline-block"></span>
          ${escHtml(comp)}
        </span>
      </td>`;
    allMonths.forEach(month => {
      const absent = byComp[comp]?.[month];
      if (!absent) {
        html += `<td style="text-align:center;padding:4px;color:var(--text-muted)">—</td>`;
        return;
      }
      const n = absent.size;
      const tip = [...absent].sort().join(', ');
      html += `
        <td style="text-align:center;padding:4px" title="${escHtml(tip)}">
          <div style="display:inline-flex;flex-direction:column;align-items:center;min-width:50px;padding:4px 6px;border-radius:6px;background:rgba(220,38,38,.10);color:#b91c1c;cursor:help">
            <span style="font-size:12px;font-weight:700">${n}</span>
            <span style="font-size:9px">absent</span>
          </div>
        </td>`;
    });
    html += '</tr>';
  });

  html += '</tbody></table>';
  body.innerHTML = html;
  card.style.display = '';
}

// ── Init ───────────────────────────────────────────────────────────────────
function init() {
  // Set default filter dates
  const pickupEl = document.getElementById('filter-pickup');
  const returnEl = document.getElementById('filter-return');
  if (pickupEl && !pickupEl.value) pickupEl.value = defaultPickup();
  if (returnEl && !returnEl.value) returnEl.value = defaultReturn();
  syncDateConstraints();

  // Nav click handlers
  document.querySelectorAll('.nav-item').forEach(el => {
    el.addEventListener('click', () => switchTab(el.dataset.tab));
  });

  // Filter change handlers
  // Location + category just reload existing DB rates (no new scrape needed)
  ['filter-location', 'filter-category'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', loadRates);
  });
  // Date inputs: debounce, then trigger a live scrape for the selected dates
  let _dateDebounce = null;
  ['filter-pickup', 'filter-return'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', () => {
      syncDateConstraints();
      clearTimeout(_dateDebounce);
      _dateDebounce = setTimeout(() => triggerScrape(), 800);
    });
  });

  // Button handlers
  document.getElementById('btn-scrape')?.addEventListener('click', triggerScrape);
  document.getElementById('btn-check-seo')?.addEventListener('click', triggerSeoCheck);
  document.getElementById('btn-save-settings')?.addEventListener('click', saveSettings);
  document.getElementById('btn-add-location')?.addEventListener('click', addLocation);
  document.getElementById('btn-add-mapping')?.addEventListener('click', addMapping);

  // Load scheduler status
  loadSchedulerStatus();

  // Check data freshness immediately (shows stale banner if needed)
  checkDataFreshness();

  // Auto-refresh: silently reload rates + freshness check every 5 minutes
  setInterval(() => {
    loadRates();
    checkDataFreshness();
  }, 5 * 60 * 1000);

  // Start on rates tab
  switchTab('rates');
}

document.addEventListener('DOMContentLoaded', init);
