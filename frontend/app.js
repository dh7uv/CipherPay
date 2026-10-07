const API_BASE = `${window.location.origin === 'null' ? 'http://localhost:8000' : ''}/api/v1`;
const SESSION_KEY = 'cipherpay-session';

const workspaceLinks = [...document.querySelectorAll('.nav-link[href^="#"]')];
const workspaceTitle = document.getElementById('breadcrumb-current');
const sectionTitles = new Map(workspaceLinks.map((link) => [
  link.hash,
  link.querySelector('.nav-count') ? 'Risk alerts' : link.textContent.trim(),
]));

function syncWorkspaceNavigation() {
  const currentHash = window.location.hash || '#overview';
  const currentTitle = sectionTitles.get(currentHash) || 'Overview';

  workspaceLinks.forEach((link) => {
    const isCurrent = link.hash === currentHash;
    link.classList.toggle('is-active', isCurrent);
    if (isCurrent) {
      link.setAttribute('aria-current', 'page');
    } else {
      link.removeAttribute('aria-current');
    }
  });

  workspaceTitle.textContent = currentTitle;
  document.title = `${currentTitle} · CipherPay`;
}

window.addEventListener('hashchange', syncWorkspaceNavigation);
syncWorkspaceNavigation();

function readSession() {
  try {
    const session = JSON.parse(sessionStorage.getItem(SESSION_KEY) || 'null');
    return session && typeof session.token === 'string' ? session : null;
  } catch {
    sessionStorage.removeItem(SESSION_KEY);
    return null;
  }
}

const session = readSession();

if (!session) {
  window.location.replace('/login');
}

const elements = {
  totalTransactions: document.getElementById('total_txn'),
  averageRisk: document.getElementById('avg_risk'),
  alertCount: document.getElementById('alerts_count'),
  sidebarAlertCount: document.getElementById('sidebar-alert-count'),
  systemStatus: document.getElementById('system-status'),
  transactionCount: document.getElementById('transaction-count'),
  transactionList: document.getElementById('transactions-list'),
  alertList: document.getElementById('alerts-list'),
  search: document.getElementById('transaction-search'),
  riskFilter: document.getElementById('risk-filter'),
  riskTotal: document.getElementById('risk-total'),
  refreshButton: document.getElementById('refresh-button'),
  form: document.getElementById('transaction-form'),
  submitButton: document.getElementById('submit-button'),
  formFeedback: document.getElementById('form-feedback'),
  logoutButton: document.getElementById('logout-button'),
};

let transactions = [];
let alerts = [];

async function requestJson(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set('Authorization', `Bearer ${session.token}`);
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  let data;

  try {
    data = await response.json();
  } catch {
    throw new Error('The server returned an invalid response.');
  }

  if (!response.ok) {
    if (response.status === 401) {
      sessionStorage.removeItem(SESSION_KEY);
      window.location.replace('/login');
    }
    const detail = typeof data.detail === 'string' ? data.detail : `Request failed (${response.status})`;
    throw new Error(detail);
  }

  return data;
}

function setSystemStatus(online, message) {
  elements.systemStatus.classList.toggle('is-online', online);
  elements.systemStatus.classList.toggle('is-offline', !online);
  elements.systemStatus.lastChild.textContent = ` ${message}`;
}

function formatDate(value) {
  if (!value) return 'Date unavailable';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Date unavailable';
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}

function formatAmount(amount, currency = 'USD') {
  const numericAmount = Number(amount);
  if (!Number.isFinite(numericAmount)) return '—';

  try {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency,
      maximumFractionDigits: 2,
    }).format(numericAmount);
  } catch {
    return `${currency} ${numericAmount.toFixed(2)}`;
  }
}

function makeCell(className, text) {
  const cell = document.createElement('td');
  if (className) cell.className = className;
  cell.textContent = text;
  return cell;
}

function setMetric(id, value) {
  document.getElementById(id).textContent = value;
}

function renderRiskDistribution(distribution = {}) {
  const levels = [
    ['Low', 'risk-low-count', 'risk-low-bar'],
    ['Medium', 'risk-medium-count', 'risk-medium-bar'],
    ['High', 'risk-high-count', 'risk-high-bar'],
  ];
  const total = levels.reduce((sum, [level]) => sum + (Number(distribution[level]) || 0), 0);
  elements.riskTotal.textContent = total.toLocaleString();

  levels.forEach(([level, countId, barId]) => {
    const count = Number(distribution[level]) || 0;
    setMetric(countId, count.toLocaleString());
    document.getElementById(barId).style.width = total ? `${(count / total) * 100}%` : '0%';
  });
}

function renderDashboard(data) {
  setMetric('total_txn', (Number(data.total_transactions) || 0).toLocaleString());
  setMetric('avg_risk', (Number(data.average_risk_score) || 0).toLocaleString(undefined, {
    maximumFractionDigits: 1,
  }));
  const openAlerts = alerts.filter((alert) => alert.status !== 'Resolved' && alert.status !== 'Dismissed').length;
  setMetric('alerts_count', openAlerts.toLocaleString());
  elements.sidebarAlertCount.textContent = openAlerts > 99 ? '99+' : String(openAlerts);
  renderRiskDistribution(data.risk_distribution);
}

function renderProfile() {
  const email = session.email || 'Analyst';
  const displayName = email.split('@')[0].replace(/[._-]+/g, ' ');
  const role = session.role === 'analyst' ? 'Analyst account' : 'User account';
  const userIdField = document.getElementById('user_id');
  document.getElementById('profile-name').textContent = displayName;
  document.getElementById('profile-role').textContent = role;
  document.getElementById('welcome-user').textContent = displayName;
  document.querySelector('.avatar').textContent = displayName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join('');
  if (session.role !== 'analyst') {
    userIdField.value = session.user_id;
    userIdField.readOnly = true;
    userIdField.closest('.field').hidden = true;
    document.body.classList.add('user-dashboard');
    document.querySelector('.welcome-copy').textContent = 'Here’s a snapshot of your own transaction activity.';
  }
  document.querySelectorAll('.analyst-only').forEach((element) => {
    element.hidden = session.role !== 'analyst';
  });
}

function renderTransactions() {
  const query = elements.search.value.trim().toLowerCase();
  const risk = elements.riskFilter.value;
  const filtered = transactions.filter((transaction) => {
    const matchesSearch = [transaction.transaction_id, transaction.merchant]
      .some((value) => String(value || '').toLowerCase().includes(query));
    const matchesRisk = risk === 'all' || transaction.risk_category === risk;
    return matchesSearch && matchesRisk;
  });

  elements.transactionCount.textContent = `${filtered.length} ${filtered.length === 1 ? 'record' : 'records'}`;
  elements.transactionList.replaceChildren();

  if (!filtered.length) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 6;
    cell.className = 'empty-cell';
    cell.textContent = transactions.length ? 'No transactions match these filters.' : 'No transactions have been submitted yet.';
    row.appendChild(cell);
    elements.transactionList.appendChild(row);
    return;
  }

  filtered.slice(0, 8).forEach((transaction) => {
    const row = document.createElement('tr');
    const identity = document.createElement('td');
    const transactionId = document.createElement('div');
    transactionId.className = 'transaction-id';
    transactionId.textContent = transaction.transaction_id || 'Unknown transaction';
    const date = document.createElement('div');
    date.className = 'transaction-date';
    date.textContent = formatDate(transaction.created_at);
    identity.append(transactionId, date);
    row.appendChild(identity);

    const merchant = makeCell('merchant-name', transaction.merchant || 'Unknown');
    const amount = makeCell('amount-value', formatAmount(transaction.amount, transaction.currency));
    row.append(merchant, amount);

    const riskCell = document.createElement('td');
    const riskBadge = document.createElement('span');
    const riskLevel = ['Low', 'Medium', 'High'].includes(transaction.risk_category)
      ? transaction.risk_category
      : 'Medium';
    riskBadge.className = `risk-badge risk-${riskLevel.toLowerCase()}`;
    riskBadge.textContent = riskLevel;
    riskCell.appendChild(riskBadge);
    row.appendChild(riskCell);

    const statusCell = document.createElement('td');
    const statusBadge = document.createElement('span');
    const statusClass = String(transaction.status || '').toLowerCase().replace(/\s+/g, '-');
    statusBadge.className = `status-badge ${['approved', 'under-review', 'declined'].includes(statusClass) ? `status-${statusClass}` : ''}`;
    statusBadge.textContent = transaction.status || 'Unknown';
    statusCell.appendChild(statusBadge);
    row.appendChild(statusCell);

    const integrityCell = document.createElement('td');
    integrityCell.className = 'analyst-only';
    const verifyButton = document.createElement('button');
    verifyButton.className = 'integrity-button';
    verifyButton.type = 'button';
    verifyButton.textContent = 'Verify';
    verifyButton.setAttribute('aria-label', `Verify integrity for ${transaction.transaction_id}`);
    integrityCell.appendChild(verifyButton);

    const reviewActions = document.createElement('div');
    reviewActions.className = 'transaction-review-actions';
    reviewActions.hidden = true;
    ['Approved', 'Declined'].forEach((decision) => {
      const decisionButton = document.createElement('button');
      decisionButton.className = `decision-button decision-${decision.toLowerCase()}`;
      decisionButton.type = 'button';
      decisionButton.textContent = decision === 'Approved' ? 'Approve' : 'Reject';
      decisionButton.addEventListener('click', () => updateTransactionDecision(
        transaction,
        decision,
        reviewActions,
        statusBadge,
        verifyButton,
      ));
      reviewActions.appendChild(decisionButton);
    });
    integrityCell.appendChild(reviewActions);
    verifyButton.addEventListener(
      'click',
      () => verifyIntegrity(transaction.transaction_id, verifyButton, reviewActions),
    );
    row.appendChild(integrityCell);
    elements.transactionList.appendChild(row);
  });
  document.querySelectorAll('#transactions-list .analyst-only').forEach((element) => {
    element.hidden = session.role !== 'analyst';
  });
}

function renderAlerts() {
  elements.alertList.replaceChildren();
  const activeAlerts = alerts
    .filter((alert) => alert.status !== 'Resolved' && alert.status !== 'Dismissed')
    .slice(0, 4);

  if (!activeAlerts.length) {
    const empty = document.createElement('p');
    empty.className = 'empty-alerts';
    empty.textContent = alerts.length ? 'No open alerts. Your queue is clear.' : 'No alerts have been generated yet.';
    elements.alertList.appendChild(empty);
    return;
  }

  activeAlerts.forEach((alert) => {
    const item = document.createElement('div');
    item.className = 'alert-item';

    const symbol = document.createElement('span');
    const severity = String(alert.severity || 'Medium').toLowerCase();
    symbol.className = `alert-symbol ${severity === 'high' || severity === 'critical' ? `alert-${severity}` : ''}`;
    symbol.setAttribute('aria-hidden', 'true');
    symbol.textContent = severity === 'critical' || severity === 'high' ? '!' : '•';

    const body = document.createElement('div');
    body.className = 'alert-body';
    const title = document.createElement('div');
    title.className = 'alert-title';
    title.textContent = alert.reason || 'Risk indicators detected';
    const meta = document.createElement('div');
    meta.className = 'alert-meta';
    const severityLabel = document.createElement('span');
    severityLabel.textContent = `${alert.severity || 'Medium'} severity`;
    const separator = document.createElement('span');
    separator.className = 'alert-separator';
    separator.textContent = '·';
    const timestamp = document.createElement('span');
    timestamp.textContent = formatDate(alert.created_at);
    meta.append(severityLabel, separator, timestamp);
    body.append(title, meta);

    const review = document.createElement('select');
    review.className = 'alert-status-select';
    review.setAttribute('aria-label', `Review status for alert ${alert.alert_id}`);
    ['Open', 'Under Investigation', 'Resolved', 'Dismissed'].forEach((status) => {
      const option = document.createElement('option');
      option.value = status;
      option.textContent = status === 'Under Investigation' ? 'Investigating' : status;
      review.appendChild(option);
    });
    review.value = ['Open', 'Under Investigation', 'Resolved', 'Dismissed'].includes(alert.status)
      ? alert.status
      : 'Open';
    review.addEventListener('change', () => updateAlertStatus(alert.alert_id, review));

    item.append(symbol, body, review);
    elements.alertList.appendChild(item);
  });
}

async function updateAlertStatus(alertId, select) {
  const previousStatus = alerts.find((alert) => alert.alert_id === alertId)?.status || 'Open';
  select.disabled = true;

  try {
    select.parentElement.querySelector('.alert-error')?.remove();
    await requestJson(`/alerts/${encodeURIComponent(alertId)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: select.value }),
    });
    await refreshDashboard();
  } catch (error) {
    select.value = previousStatus;
    const message = document.createElement('div');
    message.className = 'alert-error';
    message.textContent = `Could not update alert: ${error.message}`;
    select.parentElement.appendChild(message);
  } finally {
    select.disabled = false;
  }
}

async function verifyIntegrity(transactionId, button, reviewActions) {
  button.disabled = true;
  button.textContent = 'Checking…';
  button.className = 'integrity-button';

  try {
    const result = await requestJson(
      `/transactions/${encodeURIComponent(transactionId)}/verify-integrity`,
      { method: 'POST' },
    );
    button.textContent = result.integrity_valid ? 'Verified' : 'Tampered';
    button.classList.add(result.integrity_valid ? 'is-valid' : 'is-invalid');
    reviewActions.hidden = !result.manual_review_available;
    button.title = result.integrity_valid
      ? 'Transaction signature matches its stored data.'
      : 'Stored transaction data does not match its original signature.';
  } catch (error) {
    button.textContent = 'Retry';
    button.title = `Integrity check failed: ${error.message}`;
  } finally {
    button.disabled = false;
  }
}

async function updateTransactionDecision(transaction, decision, actions, statusBadge, verifyButton) {
  actions.querySelectorAll('button').forEach((button) => {
    button.disabled = true;
  });
  verifyButton.disabled = true;

  try {
    const result = await requestJson(
      `/transactions/${encodeURIComponent(transaction.transaction_id)}/decision`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision }),
      },
    );
    transaction.status = result.transaction.status;
    transaction.reviewed_at = result.transaction.reviewed_at;
    transaction.reviewed_by = result.transaction.reviewed_by;
    statusBadge.textContent = result.transaction.status;
    statusBadge.className = `status-badge status-${result.transaction.status.toLowerCase()}`;
    actions.replaceChildren();

    const confirmation = document.createElement('span');
    confirmation.className = 'decision-confirmation';
    confirmation.textContent = `${decision} by analyst`;
    actions.appendChild(confirmation);
  } catch (error) {
    actions.querySelectorAll('button').forEach((button) => {
      button.disabled = false;
    });
    const message = document.createElement('span');
    message.className = 'decision-error';
    message.textContent = error.message;
    actions.appendChild(message);
  } finally {
    verifyButton.disabled = false;
  }
}

async function refreshDashboard() {
  elements.refreshButton.classList.add('is-refreshing');
  const isAnalyst = session.role === 'analyst';

  const results = await Promise.allSettled([
    isAnalyst ? requestJson('/analytics/dashboard') : Promise.resolve(null),
    requestJson('/transactions/'),
    isAnalyst ? requestJson('/alerts/') : Promise.resolve({ alerts: [] }),
    requestJson('/health'),
  ]);

  const [dashboardResult, transactionsResult, alertsResult, healthResult] = results;
  const failures = results.filter((result) => result.status === 'rejected');

  if (dashboardResult.status === 'fulfilled') {
    if (dashboardResult.value) {
      renderDashboard(dashboardResult.value);
    } else if (transactionsResult.status === 'fulfilled') {
      const ownTransactions = transactionsResult.value.transactions || [];
      const riskDistribution = { Low: 0, Medium: 0, High: 0 };
      ownTransactions.forEach((transaction) => {
        if (Object.hasOwn(riskDistribution, transaction.risk_category)) {
          riskDistribution[transaction.risk_category] += 1;
        }
      });
      renderDashboard({
        total_transactions: ownTransactions.length,
        average_risk_score: ownTransactions.length
          ? ownTransactions.reduce((sum, transaction) => sum + Number(transaction.risk_score || 0), 0) / ownTransactions.length
          : 0,
        risk_distribution: riskDistribution,
      });
    }
  } else {
    setMetric('total_txn', '—');
    setMetric('avg_risk', '—');
    elements.riskTotal.textContent = '—';
  }

  if (transactionsResult.status === 'fulfilled') {
    transactions = Array.isArray(transactionsResult.value.transactions)
      ? transactionsResult.value.transactions
      : [];
    renderTransactions();
  } else {
    transactions = [];
    renderTransactions();
    elements.transactionList.querySelector('.empty-cell').textContent = 'Could not load transactions. Refresh to try again.';
  }

  if (alertsResult.status === 'fulfilled') {
    alerts = Array.isArray(alertsResult.value.alerts) ? alertsResult.value.alerts : [];
    renderAlerts();
  } else {
    alerts = [];
    renderAlerts();
    elements.alertList.querySelector('.empty-alerts').textContent = 'Could not load alerts. Refresh to try again.';
    setMetric('alerts_count', '—');
    elements.sidebarAlertCount.textContent = '!';
  }

  if (healthResult.status === 'fulfilled' && healthResult.value.status === 'ok') {
    const storage = healthResult.value.database_connected ? 'MongoDB' : 'Local storage';
    const tracking = healthResult.value.redis_connected ? 'Redis' : 'local risk tracking';
    const serviceSummary = `API · ${storage} · ${tracking}`;
    setSystemStatus(true, failures.length ? `${serviceSummary} · Partial data` : serviceSummary);
  } else {
    setSystemStatus(false, 'API unavailable');
  }

  if (failures.length) {
    console.error('Some dashboard data could not be refreshed.', failures.map((result) => result.reason));
  }

  elements.refreshButton.classList.remove('is-refreshing');
}

async function submitTransaction(event) {
  event.preventDefault();
  elements.submitButton.disabled = true;
  elements.submitButton.querySelector('span').textContent = 'Analyzing…';
  elements.formFeedback.className = 'form-feedback';
  elements.formFeedback.textContent = 'Submitting transaction for risk analysis…';

  const payload = {
    user_id: document.getElementById('user_id').value.trim(),
    amount: Number(document.getElementById('amount').value),
    currency: document.getElementById('currency').value,
    merchant: document.getElementById('merchant').value.trim(),
    device_id: document.getElementById('device_id').value.trim(),
    location: document.getElementById('location').value.trim(),
  };

  try {
    const result = await requestJson('/transactions/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const risk = result.risk || {};
    const transactionId = result.transaction?.transaction_id || 'Transaction';
    const riskCategory = risk.risk_category || 'Unknown';
    elements.formFeedback.classList.add('is-success');
    elements.formFeedback.textContent = `${transactionId} analyzed — ${riskCategory} risk (${Number(risk.risk_score) || 0}/100).`;
    await refreshDashboard();
  } catch (error) {
    elements.formFeedback.classList.add('is-error');
    elements.formFeedback.textContent = `Transaction could not be analyzed: ${error.message}`;
  } finally {
    elements.submitButton.disabled = false;
    elements.submitButton.querySelector('span').textContent = 'Analyze transaction';
  }
}

elements.form.addEventListener('submit', submitTransaction);
elements.search.addEventListener('input', renderTransactions);
elements.riskFilter.addEventListener('change', renderTransactions);
elements.refreshButton.addEventListener('click', refreshDashboard);
elements.logoutButton.addEventListener('click', () => {
  sessionStorage.removeItem(SESSION_KEY);
  window.location.replace('/login');
});

renderProfile();
refreshDashboard();
