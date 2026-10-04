const API_BASE = 'http://localhost:8000/api/v1';

async function fetchDashboard() {
  try {
    const response = await fetch(`${API_BASE}/analytics/dashboard`);
    const data = await response.json();

    document.getElementById('total_txn').textContent = data.total_transactions || 0;
    document.getElementById('avg_risk').textContent = data.average_risk_score || 0;
    document.getElementById('alerts_count').textContent = data.total_alerts || 0;
    document.getElementById('status-box').textContent = `Risk mix: ${JSON.stringify(data.risk_distribution)}`;
  } catch (error) {
    document.getElementById('status-box').textContent = 'API unavailable. Start the backend server first.';
  }
}

async function fetchAlerts() {
  try {
    const response = await fetch(`${API_BASE}/alerts/`);
    const data = await response.json();
    const container = document.getElementById('alerts-list');
    container.innerHTML = '';

    if (!data.alerts || !data.alerts.length) {
      container.innerHTML = '<div class="alert-item">No active alerts.</div>';
      return;
    }

    data.alerts.slice(0, 5).forEach((alert) => {
      const item = document.createElement('div');
      item.className = 'alert-item';
      item.innerHTML = `<strong>${alert.severity}</strong> — ${alert.reason} <br><small>${alert.status}</small>`;
      container.appendChild(item);
    });
  } catch (error) {
    document.getElementById('alerts-list').innerHTML = '<div class="alert-item">Could not load alerts.</div>';
  }
}

async function submitTransaction(event) {
  event.preventDefault();
  const payload = {
    user_id: document.getElementById('user_id').value,
    amount: Number(document.getElementById('amount').value),
    currency: document.getElementById('currency').value,
    merchant: document.getElementById('merchant').value,
    device_id: document.getElementById('device_id').value,
    location: document.getElementById('location').value,
  };

  try {
    const response = await fetch(`${API_BASE}/transactions/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    document.getElementById('status-box').textContent = `Transaction ${result.transaction.transaction_id} scored ${result.risk.risk_score} (${result.risk.risk_category})`;
    fetchDashboard();
    fetchAlerts();
  } catch (error) {
    document.getElementById('status-box').textContent = 'Failed to submit transaction.';
  }
}

document.getElementById('transaction-form').addEventListener('submit', submitTransaction);
fetchDashboard();
fetchAlerts();
