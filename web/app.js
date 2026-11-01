const state = { workspace: null, activeView: 'overview', selectedScenarioId: null, toastTimer: null };
const viewTitles = {
  overview: 'Executive overview',
  planning: 'Financial plan',
  cash: 'Cash flow',
  scenarios: 'Scenario studio',
  investment: 'Capital investments',
  reports: 'Reports & exports',
};
const assumptionHelp = {
  starting_units: 'Starting monthly unit volume',
  monthly_unit_growth: 'Monthly compound growth in unit volume',
  unit_price: 'Average selling price per unit',
  variable_cost_per_unit: 'Direct variable cost for each unit',
  fixed_opex: 'Monthly fixed operating expenses, excluding payroll',
  payroll: 'Monthly payroll and benefits',
  depreciation: 'Monthly depreciation and amortization',
  interest_expense: 'Monthly interest expense',
  tax_rate: 'Effective tax rate on positive pre-tax income',
  opening_cash: 'Cash available at the start of the forecast',
  minimum_cash: 'Liquidity reserve threshold',
  collection_rate: 'Share of recognized revenue collected in the same period',
  payment_rate: 'Share of COGS and operating expenses paid in the same period',
  monthly_capex: 'Monthly capital expenditure',
  monthly_debt_proceeds: 'Monthly cash proceeds from new borrowing',
  monthly_debt_repayment: 'Monthly debt principal repayments',
  monthly_equity_contribution: 'Monthly equity contributions',
};

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char]));
}

function number(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function fmt(value, currency = state.workspace?.currency || 'USD', compact = false) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return 'N/M';
  return new Intl.NumberFormat(undefined, {
    style: 'currency', currency, maximumFractionDigits: 0,
    notation: compact ? 'compact' : 'standard',
  }).format(Number(value));
}

function fmtNumber(value, digits = 1) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return 'N/M';
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: digits }).format(Number(value));
}

function fmtPercent(value, digits = 1) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return 'N/M';
  return `${fmtNumber(Number(value) * 100, digits)}%`;
}

function toast(message, error = false) {
  const element = document.querySelector('#toast');
  element.textContent = message;
  element.className = `toast show${error ? ' error' : ''}`;
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => { element.className = 'toast'; }, 3600);
}

async function request(url, options = {}) {
  let response;
  try {
    response = await fetch(url, {
      ...options,
      headers: { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...options.headers },
    });
  } catch {
    throw new Error('Unable to reach the local service. Check that the app is running and try again.');
  }
  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try { message = (await response.json()).error?.message || message; } catch {}
    throw new Error(message);
  }
  return response.json();
}

async function refresh(showError = true) {
  try {
    const data = await request('/api/v1/workspace');
    state.workspace = data.workspace;
    render();
  } catch (error) {
    if (showError) toast(error.message, true);
    throw error;
  }
}

function activeModel() {
  return state.workspace?.models?.find((model) => String(model.scenario_id) === String(state.selectedScenarioId))
    || state.workspace?.models?.find((model) => model.scenario_name.toLowerCase() === 'base case')
    || state.workspace?.models?.[0];
}

function render() {
  const hasWorkspace = Boolean(state.workspace);
  document.querySelector('#empty-state').classList.toggle('hidden', hasWorkspace);
  document.querySelector('#workspace-content').classList.toggle('hidden', !hasWorkspace);
  document.querySelector('#service-state').classList.toggle('hidden', true);
  if (!hasWorkspace) return;
  const scenarioSelect = document.querySelector('#overview-scenario-select');
  const existingScenario = String(state.selectedScenarioId || scenarioSelect.value || '');
  scenarioSelect.innerHTML = state.workspace.models.map((model) =>
    `<option value="${model.scenario_id}">${escapeHtml(model.scenario_name)}</option>`).join('');
  state.selectedScenarioId = state.workspace.models.some((model) => String(model.scenario_id) === existingScenario)
    ? existingScenario
    : String((state.workspace.models.find((model) => model.scenario_name.toLowerCase() === 'base case')
      || state.workspace.models[0]).scenario_id);
  scenarioSelect.value = state.selectedScenarioId;
  renderOverview();
  renderAssumptions();
  renderCashFlow();
  renderScenarios();
  renderInvestment();
  document.querySelector('#period-label').textContent =
    `${state.workspace.start_period} · ${state.workspace.horizon} months`;
  document.querySelector('#plan-period-label').textContent =
    `${state.workspace.start_period} · ${state.workspace.horizon} months`;
  showView(state.activeView);
}

function renderOverview() {
  const model = activeModel();
  const totals = model.totals;
  const kpis = [
    ['Forecast revenue', fmt(totals.revenue, state.workspace.currency, true), 'Cumulative forecast period', '↗'],
    ['Gross margin', fmtPercent(Number(totals.gross_profit) / Number(totals.revenue)), 'Across forecast horizon', '◒'],
    ['EBITDA', fmt(totals.ebitda, state.workspace.currency, true), 'Before D&A, interest and tax', '▥'],
    ['Closing cash', fmt(totals.closing_cash, state.workspace.currency, true), `Minimum ${fmt(totals.minimum_projected_cash, state.workspace.currency, true)}`, '◉'],
  ];
  document.querySelector('#kpi-grid').innerHTML = kpis.map(([label, value, foot, icon]) => `
    <article class="kpi-card"><div class="kpi-top"><span>${label}</span><span class="kpi-symbol">${icon}</span></div>
    <div class="kpi-value ${label === 'Closing cash' && Number(totals.closing_cash) < 0 ? 'negative' : ''}">${escapeHtml(value)}</div>
    <div class="kpi-foot">${escapeHtml(foot)}</div></article>`).join('');
  const alerts = model.periods.filter((row) => row.cash_status !== 'within_reserve');
  const alertStrip = document.querySelector('#alert-strip');
  alertStrip.classList.toggle('hidden', alerts.length === 0);
  alertStrip.classList.toggle('warning', alerts.some((row) => row.cash_status === 'below_reserve'));
  if (alerts.length) {
    const first = alerts[0];
    alertStrip.textContent = first.cash_status === 'negative'
      ? `Liquidity risk: projected cash turns negative in ${first.period}. Review collections, spending, or financing assumptions.`
      : `Reserve alert: projected cash first falls below the configured reserve in ${first.period}.`;
  }
  drawPerformanceChart(model.periods);
  drawCashChart(model.periods);
  const header = ['Period', 'Revenue', 'Gross profit', 'EBITDA', 'Net income', 'Closing cash'];
  document.querySelector('#overview-table').innerHTML = `
    <thead><tr>${header.map((item) => `<th>${item}</th>`).join('')}</tr></thead>
    <tbody>${model.periods.slice(0, 8).map((row) => `<tr>
      <td><strong>${escapeHtml(row.period)}</strong></td><td>${fmt(row.revenue)}</td>
      <td>${fmt(row.gross_profit)}</td><td class="${Number(row.ebitda) < 0 ? 'negative' : ''}">${fmt(row.ebitda)}</td>
      <td>${fmt(row.net_income)}</td><td class="${Number(row.closing_cash) < 0 ? 'negative' : ''}">${fmt(row.closing_cash)}</td>
    </tr>`).join('')}</tbody>`;
  const events = state.workspace.audit_events || [];
  document.querySelector('#audit-list').innerHTML = events.length
    ? events.slice(0, 5).map((event) => `<div class="audit-row"><i class="audit-dot"></i>
      <span>${escapeHtml(event.entity)} · ${escapeHtml(event.entity_key)} — ${escapeHtml(event.reason)}</span>
      <time class="audit-time">${escapeHtml(new Date(event.occurred_at).toLocaleString())}</time></div>`).join('')
    : '<div class="audit-row">No changes recorded yet.</div>';
}

function chartSvg(periods, series, minValue, maxValue) {
  const width = 660;
  const height = 190;
  const padding = { top: 10, right: 12, bottom: 25, left: 12 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const range = maxValue - minValue || 1;
  const x = (index) => padding.left + (periods.length <= 1 ? 0 : (index * plotWidth) / (periods.length - 1));
  const y = (value) => padding.top + plotHeight - ((Number(value) - minValue) / range) * plotHeight;
  const grid = [0, 1, 2, 3].map((step) => {
    const lineY = padding.top + (step * plotHeight) / 3;
    return `<line class="chart-gridline" x1="${padding.left}" x2="${width - padding.right}" y1="${lineY}" y2="${lineY}"/>`;
  }).join('');
  const lines = series.map(({ key, color }) => {
    const coordinates = periods.map((row, index) => `${x(index)},${y(row[key])}`).join(' ');
    return `<polyline fill="none" stroke="${color}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round" points="${coordinates}"/>`;
  }).join('');
  const labels = periods.filter((_, index) => index % Math.ceil(periods.length / 6) === 0 || index === periods.length - 1)
    .map((row) => {
      const index = periods.indexOf(row);
      return `<text class="chart-label" x="${x(index)}" y="${height - 5}" text-anchor="middle">${escapeHtml(row.period.slice(2))}</text>`;
    }).join('');
  return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Monthly forecast chart">${grid}${lines}${labels}</svg>`;
}

function drawPerformanceChart(periods) {
  const values = periods.flatMap((row) => [Number(row.revenue), Number(row.ebitda)]);
  const min = Math.min(0, ...values);
  const max = Math.max(1, ...values);
  document.querySelector('#performance-chart').innerHTML = chartSvg(periods, [
    { key: 'revenue', color: '#bd9e64' }, { key: 'ebitda', color: '#6388a8' },
  ], min, max);
}

function drawCashChart(periods) {
  const minReserve = Number(state.workspace.assumptions.minimum_cash.value);
  const values = periods.flatMap((row) => [Number(row.closing_cash), minReserve]);
  const min = Math.min(0, ...values);
  const max = Math.max(1, ...values);
  document.querySelector('#cash-chart').innerHTML = chartSvg(periods, [
    { key: 'closing_cash', color: '#3a9975' },
    { key: 'minimum_cash', color: '#c4aa78' },
  ], min, max);
}

function renderAssumptions() {
  const entries = Object.entries(state.workspace.assumptions);
  const categories = [...new Set(entries.map(([, item]) => item.category))];
  document.querySelector('#assumptions-table').innerHTML = `
    <thead><tr><th>Driver</th><th>Current value</th><th>Unit</th><th>Last change</th><th>Save change</th></tr></thead>
    <tbody>${categories.flatMap((category) => {
      const categoryRows = entries.filter(([, item]) => item.category === category);
      return [`<tr><td colspan="5"><strong>${escapeHtml(category.toUpperCase())}</strong></td></tr>`,
        ...categoryRows.map(([key, item]) => {
          const suffix = item.unit === 'fraction' ? (key === 'monthly_unit_growth' ? '%' : '%') : '';
          const shown = suffix ? Number(item.value) * 100 : item.value;
          return `<tr><td><strong>${escapeHtml(item.label)}</strong><div class="kpi-foot">${escapeHtml(assumptionHelp[key] || '')}</div></td>
            <td><input class="assumption-input" type="number" step="any" aria-label="${escapeHtml(item.label)}" name="value" value="${escapeHtml(shown)}" data-key="${escapeHtml(key)}" data-scale="${suffix ? '100' : '1'}"></td>
            <td>${escapeHtml(suffix ? '%' : item.unit)}</td><td>${escapeHtml(item.source)}<div class="kpi-foot">${escapeHtml(item.updated_at)}</div></td>
            <td><form class="assumption-form" data-assumption-form="${escapeHtml(key)}"><input class="reason-input" aria-label="Reason for ${escapeHtml(item.label)} change" name="reason" maxlength="500" placeholder="Change reason"><button class="button button-secondary button-small" type="submit">Save</button></form></td></tr>`;
        })];
    }).join('')}</tbody>`;
}

function renderCashFlow() {
  const model = activeModel();
  const periods = model.periods;
  const firstBreach = periods.find((row) => row.cash_status !== 'within_reserve');
  document.querySelector('#cash-alert').innerHTML = firstBreach
    ? `<strong>Liquidity requires review.</strong> ${firstBreach.cash_status === 'negative' ? 'Cash is projected to turn negative' : 'Cash is projected to breach the reserve'} in ${escapeHtml(firstBreach.period)}. This model uses same-period collection/payment assumptions and omits working-capital roll-forward.`
    : '<strong>No modeled reserve breach.</strong> Forecast cash stays above the configured minimum reserve under this scenario. Model completeness and assumptions still require review.';
  document.querySelector('#cash-table').innerHTML = `
    <thead><tr><th>Period</th><th>Opening cash</th><th>Collections</th><th>Other inflows</th><th>Cash outflows</th><th>Net movement</th><th>Closing cash</th><th>Status</th></tr></thead>
    <tbody>${periods.map((row) => {
      const otherInflows = Number(row.cash_inflows) - Number(row.cash_collections);
      return `<tr><td><strong>${escapeHtml(row.period)}</strong></td><td>${fmt(row.opening_cash)}</td>
        <td>${fmt(row.cash_collections)}</td><td>${fmt(otherInflows)}</td><td>${fmt(row.cash_outflows)}</td>
        <td class="${Number(row.net_cash_movement) < 0 ? 'negative' : 'positive'}">${fmt(row.net_cash_movement)}</td>
        <td class="${Number(row.closing_cash) < 0 ? 'negative' : ''}"><strong>${fmt(row.closing_cash)}</strong></td>
        <td><span class="cash-status ${escapeHtml(row.cash_status)}">${escapeHtml(row.cash_status.replace('_', ' '))}</span></td></tr>`;
    }).join('')}</tbody>`;
}

function renderScenarios() {
  const models = state.workspace.models;
  const maxRevenue = Math.max(1, ...models.map((model) => Number(model.totals.revenue)));
  document.querySelector('#scenario-table').innerHTML = `
    <thead><tr><th>Scenario</th><th>Revenue</th><th>EBITDA</th><th>Net income</th><th>Minimum cash</th><th>Period-end cash</th><th>Revenue scale</th></tr></thead>
    <tbody>${models.map((model) => `<tr><td><strong>${escapeHtml(model.scenario_name)}</strong></td>
      <td>${fmt(model.totals.revenue)}</td><td class="${Number(model.totals.ebitda) < 0 ? 'negative' : ''}">${fmt(model.totals.ebitda)}</td>
      <td>${fmt(model.totals.net_income)}</td><td>${fmt(model.totals.minimum_projected_cash)}</td>
      <td>${fmt(model.totals.closing_cash)}</td><td class="scenario-bar-cell"><progress class="scenario-progress" max="100" value="${Math.max(3, (Number(model.totals.revenue) / maxRevenue) * 100)}" aria-label="Revenue relative to highest scenario"></progress></td></tr>`).join('')}</tbody>`;
  const select = document.querySelector('#scenario-select');
  const previous = select.value;
  select.innerHTML = models.map((model) => `<option value="${model.scenario_id}">${escapeHtml(model.scenario_name)}</option>`).join('');
  if ([...select.options].some((option) => option.value === previous)) select.value = previous;
  const base = models.find((model) => model.scenario_name.toLowerCase() === 'base case') || models[0];
  const downside = models.find((model) => /downside|worst/i.test(model.scenario_name));
  const insight = document.querySelector('#scenario-insight');
  if (downside && base) {
    const baseCash = Number(base.totals.minimum_projected_cash);
    const downCash = Number(downside.totals.minimum_projected_cash);
    insight.innerHTML = `<strong>Liquidity comparison:</strong> ${escapeHtml(downside.scenario_name)} minimum cash is ${fmt(downCash)} versus ${fmt(baseCash)} in ${escapeHtml(base.scenario_name)}. ${downCash < Number(state.workspace.assumptions.minimum_cash.value) ? 'The downside case breaches the configured cash reserve.' : 'The downside case remains above the configured reserve.'}`;
  } else {
    insight.textContent = 'Create an upside or downside scenario to view a transparent comparison against the base case.';
  }
}

function renderInvestment() {
  const existing = state.workspace.investment;
  const form = document.querySelector('#investment-form');
  if (!existing) return;
  for (const [key, value] of Object.entries(existing.inputs)) {
    const field = form.elements.namedItem(key);
    if (field) field.value = key === 'discount_rate' ? Number(value) * 100 : value;
  }
  const results = existing.results;
  document.querySelector('#investment-results').className = 'investment-results';
  document.querySelector('#investment-results').innerHTML = [
    ['Net present value', fmt(results.npv)],
    ['Internal rate of return', results.irr === null ? escapeHtml(results.irr_status.replaceAll('_', ' ')) : fmtPercent(results.irr)],
    ['Simple payback', results.simple_payback_years === null ? 'Not recovered' : `${fmtNumber(results.simple_payback_years, 2)} years`],
    ['Discounted payback', results.discounted_payback_years === null ? 'Not recovered' : `${fmtNumber(results.discounted_payback_years, 2)} years`],
    ['Profitability index', fmtNumber(results.profitability_index, 2)],
    ['IRR search status', escapeHtml(results.irr_status.replaceAll('_', ' '))],
  ].map(([label, value]) => `<div class="result-item"><span>${label}</span><strong>${value}</strong></div>`).join('')
    + `<div class="kpi-foot result-foot">${escapeHtml(results.timing_convention)}</div>`;
}

function showView(name) {
  state.activeView = viewTitles[name] ? name : 'overview';
  document.querySelectorAll('.view').forEach((view) => view.classList.toggle('active', view.id === `view-${state.activeView}`));
  document.querySelectorAll('.nav-item').forEach((item) => item.classList.toggle('active', item.dataset.view === state.activeView));
  document.querySelector('#breadcrumb-current').textContent = viewTitles[state.activeView];
}

document.querySelectorAll('.nav-item').forEach((item) => {
  item.addEventListener('click', () => showView(item.dataset.view));
});
document.querySelector('#overview-scenario-select').addEventListener('change', (event) => {
  state.selectedScenarioId = event.currentTarget.value;
  render();
});
document.querySelectorAll('[data-navigate]').forEach((button) => {
  button.addEventListener('click', () => showView(button.dataset.navigate));
});

document.querySelector('#setup-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const assumptions = {};
  ['starting_units', 'unit_price', 'variable_cost_per_unit', 'fixed_opex', 'payroll', 'opening_cash'].forEach((key) => {
    assumptions[key] = form.get(key);
  });
  try {
    const result = await request('/api/v1/workspace', {
      method: 'POST',
      body: JSON.stringify({
        company_name: form.get('company_name'), currency: form.get('currency'),
        start_period: form.get('start_period'), horizon: Number(form.get('horizon')), assumptions,
      }),
    });
    state.workspace = result.workspace;
    render();
    toast('Financial workspace created. Review assumptions before relying on the forecast.');
  } catch (error) { toast(error.message, true); }
});

document.querySelector('#assumptions-table').addEventListener('submit', async (event) => {
  const form = event.target.closest('[data-assumption-form]');
  if (!form) return;
  event.preventDefault();
  const key = form.dataset.assumptionForm;
  const input = document.querySelector(`.assumption-input[data-key="${key}"]`);
  const scale = Number(input.dataset.scale || 1);
  const raw = Number(input.value) / scale;
  try {
    const result = await request(`/api/v1/assumptions/${key}`, {
      method: 'PUT',
      body: JSON.stringify({ value: String(raw), reason: form.elements.reason.value || 'Assumption updated' }),
    });
    state.workspace = result.workspace;
    render();
    showView('planning');
    toast('Assumption saved; forecast recalculated.');
  } catch (error) { toast(error.message, true); }
});

document.querySelector('#scenario-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const overrides = {};
  const growth = String(form.get('monthly_unit_growth') || '').trim();
  if (growth !== '') overrides.monthly_unit_growth = String(Number(growth) / 100);
  try {
    const result = await request('/api/v1/scenarios', {
      method: 'POST', body: JSON.stringify({ name: form.get('name'), overrides }),
    });
    state.workspace = result.workspace;
    render();
    showView('scenarios');
    event.currentTarget.reset();
    toast('Scenario created without changing the base plan.');
  } catch (error) { toast(error.message, true); }
});

document.querySelector('#scenario-edit-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const key = form.get('key');
  const value = Number(form.get('value'));
  const scaledValue = key === 'monthly_unit_growth' || key === 'collection_rate' ? value / 100 : value;
  try {
    const result = await request(`/api/v1/scenarios/${form.get('scenario_id')}/overrides/${key}`, {
      method: 'PUT',
      body: JSON.stringify({ value: String(scaledValue), reason: form.get('reason') || 'Scenario assumption updated' }),
    });
    state.workspace = result.workspace;
    render();
    showView('scenarios');
    toast('Scenario override saved; other scenarios are unchanged.');
  } catch (error) { toast(error.message, true); }
});

document.querySelector('#investment-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const payload = Object.fromEntries(form.entries());
  payload.years = Number(payload.years);
  payload.discount_rate = String(Number(payload.discount_rate) / 100);
  if (payload.residual_value === '') payload.residual_value = '0';
  try {
    const result = await request('/api/v1/investment', { method: 'POST', body: JSON.stringify(payload) });
    state.workspace = result.workspace;
    render();
    showView('investment');
    toast('Investment appraisal saved and calculated.');
  } catch (error) { toast(error.message, true); }
});

document.querySelector('#retry-load').addEventListener('click', () => refresh().catch(() => {
  document.querySelector('#service-state').classList.remove('hidden');
}));

refresh().catch(() => {
  document.querySelector('#service-state').classList.remove('hidden');
});
