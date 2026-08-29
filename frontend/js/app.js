// PulseGuard AI Application Logic

let activeChartType = 'hr';
let trendChartInstance = null;
let currentAlertFilter = 'all';
let isStreamingActive = false;
let pollingTimer = null;
let cachedTrendsData = null;

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  if (window.lucide) {
    lucide.createIcons();
  }
  
  setupEventListeners();
  fetchInitialData();
  
  // Start periodic polling every 4 seconds
  pollingTimer = setInterval(refreshDashboardData, 4000);
});

function setupEventListeners() {
  // 1. Chart Tabs
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.tab-btn').forEach(b => {
        b.classList.remove('active', 'bg-emerald-600', 'text-white');
        b.classList.add('text-gray-400');
      });
      btn.classList.add('active', 'bg-emerald-600', 'text-white');
      btn.classList.remove('text-gray-400');
      
      activeChartType = btn.dataset.chart;
      if (cachedTrendsData) {
        renderTrendChart(cachedTrendsData);
      }
    });
  });

  // 2. Scenario Presets
  document.querySelectorAll('.btn-scenario').forEach(btn => {
    btn.addEventListener('click', async () => {
      const scenario = btn.dataset.scenario;
      const days = parseInt(document.getElementById('scenario-days').value || 7);
      await triggerScenario(scenario, days);
    });
  });

  // 3. Live Stream Toggle
  document.getElementById('btn-toggle-stream').addEventListener('click', toggleLiveStreaming);

  // 4. Alert Filters
  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-btn').forEach(b => {
        b.classList.remove('active', 'bg-gray-800', 'text-gray-200');
        b.classList.add('bg-slate-900', 'text-gray-400');
      });
      btn.classList.add('active', 'bg-gray-800', 'text-gray-200');
      btn.classList.remove('bg-slate-900', 'text-gray-400');

      currentAlertFilter = btn.dataset.filter;
      fetchAnomalies();
    });
  });

  // 5. Modals (Ingest & Profile)
  document.getElementById('btn-open-ingest').addEventListener('click', () => {
    document.getElementById('modal-ingest').classList.remove('hidden');
  });

  document.getElementById('btn-open-profile').addEventListener('click', openProfileModal);

  document.querySelectorAll('.btn-close-modal').forEach(btn => {
    btn.addEventListener('click', () => {
      document.getElementById('modal-ingest').classList.add('hidden');
      document.getElementById('modal-profile').classList.add('hidden');
    });
  });

  // 6. Form submissions
  document.getElementById('form-ingest').addEventListener('submit', handleManualIngest);
  document.getElementById('form-profile').addEventListener('submit', handleProfileUpdate);

  // 7. Reset DB
  document.getElementById('btn-reset-db').addEventListener('click', resetDatabase);
}

// ----------------------------------------------------
// API CALLS & DATA REFRESH
// ----------------------------------------------------

async function fetchInitialData() {
  await Promise.all([
    fetchSummary(),
    fetchRiskAssessment(),
    fetchTrends(),
    fetchAnomalies(),
    fetchSimulatorStatus()
  ]);
}

async function refreshDashboardData() {
  await Promise.all([
    fetchSummary(),
    fetchRiskAssessment(),
    fetchTrends(false), // don't fully recreate chart on fast poll unless updated
    fetchAnomalies(),
    fetchSimulatorStatus()
  ]);
}

// 1. Summary
async function fetchSummary() {
  try {
    const res = await fetch('/api/health/summary');
    if (!res.ok) return;
    const data = await res.json();

    // Heart Rate
    document.getElementById('val-hr').innerText = Math.round(data.heart_rate.current);
    document.getElementById('val-resting-hr').innerText = Math.round(data.resting_hr.current);
    document.getElementById('sub-hr').innerText = data.heart_rate.subtext;

    // Steps
    const stepsVal = Math.round(data.steps.current);
    document.getElementById('val-steps').innerText = stepsVal.toLocaleString();
    const targetSteps = data.steps.baseline || 8000;
    document.getElementById('val-step-goal').innerText = targetSteps.toLocaleString();
    const stepPct = Math.min(100, Math.round((stepsVal / targetSteps) * 100));
    document.getElementById('bar-steps').style.width = `${stepPct}%`;
    document.getElementById('sub-steps').innerText = `${stepPct}%`;

    // Sleep
    document.getElementById('val-sleep').innerText = data.sleep.current.toFixed(1);
    document.getElementById('val-sleep-goal').innerText = data.sleep.baseline || 7.5;
    const badgeSleep = document.getElementById('badge-sleep');
    badgeSleep.innerText = data.sleep.current >= 6.5 ? 'Optimal' : (data.sleep.current >= 5.0 ? 'Deficit' : 'Severe Debt');
    badgeSleep.className = data.sleep.current >= 6.5 ? 'text-indigo-400 font-medium' : 'text-amber-400 font-bold';

    // SpO2
    document.getElementById('val-spo2').innerText = data.spo2.current.toFixed(1);
    const badgeSpo2 = document.getElementById('badge-spo2');
    if (data.spo2.current < 90) {
      badgeSpo2.innerText = 'Critical';
      badgeSpo2.className = 'ml-auto text-xs px-2 py-0.5 rounded-full bg-rose-950 text-rose-400 border border-rose-800/80 animate-pulse';
    } else if (data.spo2.current < 95) {
      badgeSpo2.innerText = 'Borderline';
      badgeSpo2.className = 'ml-auto text-xs px-2 py-0.5 rounded-full bg-amber-950 text-amber-400 border border-amber-800/50';
    } else {
      badgeSpo2.innerText = 'Safe';
      badgeSpo2.className = 'ml-auto text-xs px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-400 border border-cyan-800/50';
    }

    // Temperature
    document.getElementById('val-temp').innerText = data.temperature.current.toFixed(1);
    const badgeTemp = document.getElementById('badge-temp');
    if (data.temperature.current >= 38.3) {
      badgeTemp.innerText = 'High Fever';
      badgeTemp.className = 'ml-auto text-xs px-2 py-0.5 rounded-full bg-rose-950 text-rose-400 border border-rose-800/80 animate-pulse';
    } else if (data.temperature.current >= 37.5) {
      badgeTemp.innerText = 'Elevated';
      badgeTemp.className = 'ml-auto text-xs px-2 py-0.5 rounded-full bg-amber-950 text-amber-400 border border-amber-800/50';
    } else {
      badgeTemp.innerText = 'Normal';
      badgeTemp.className = 'ml-auto text-xs px-2 py-0.5 rounded-full bg-teal-950 text-teal-400 border border-teal-800/50';
    }

  } catch (err) {
    console.error('Error fetching summary:', err);
  }
}

// 2. Risk Score & Assessment
async function fetchRiskAssessment() {
  try {
    const res = await fetch('/api/health/risk-score');
    if (!res.ok) return;
    const data = await res.json();

    const banner = document.getElementById('risk-banner');
    const badge = document.getElementById('risk-level-badge');
    const iconContainer = document.getElementById('risk-badge-icon');
    const statusText = document.getElementById('wellness-status-text');
    const concernsText = document.getElementById('risk-concerns-text');
    const scoreNum = document.getElementById('risk-score-num');
    const anomProb = document.getElementById('anomaly-prob-val');
    const recText = document.getElementById('wellness-rec-text');

    scoreNum.innerHTML = `${Math.round(data.risk_score_numeric)}<span class="text-xs text-gray-400 font-normal">/100</span>`;
    anomProb.innerText = `${Math.round(data.anomaly_probability * 100)}%`;
    recText.innerText = data.wellness_recommendation;

    badge.innerText = `${data.overall_risk_level} Risk`;

    if (data.overall_risk_level === 'High') {
      banner.className = 'rounded-2xl p-5 border transition-all duration-300 bg-gradient-to-r from-rose-950/60 via-slate-900/80 to-slate-900 border-rose-700/60 shadow-xl shadow-rose-950/30';
      badge.className = 'px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-900 text-rose-200 border border-rose-700 animate-pulse';
      iconContainer.className = 'w-14 h-14 rounded-2xl bg-rose-900/60 border border-rose-700 flex items-center justify-center text-rose-400 shrink-0 shadow-inner';
      statusText.innerText = 'Physiological Strain Detected';
    } else if (data.overall_risk_level === 'Moderate') {
      banner.className = 'rounded-2xl p-5 border transition-all duration-300 bg-gradient-to-r from-amber-950/50 via-slate-900/80 to-slate-900 border-amber-700/50 shadow-xl shadow-amber-950/20';
      badge.className = 'px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-900 text-amber-200 border border-amber-700';
      iconContainer.className = 'w-14 h-14 rounded-2xl bg-amber-900/60 border border-amber-700 flex items-center justify-center text-amber-400 shrink-0 shadow-inner';
      statusText.innerText = 'Elevated Baseline Deviation';
    } else {
      banner.className = 'rounded-2xl p-5 border transition-all duration-300 bg-gradient-to-r from-emerald-950/40 via-slate-900/60 to-slate-900 border-emerald-800/40 shadow-xl shadow-black/40';
      badge.className = 'px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-900 text-emerald-300 border border-emerald-700';
      iconContainer.className = 'w-14 h-14 rounded-2xl bg-emerald-900/50 border border-emerald-700/50 flex items-center justify-center text-emerald-400 shrink-0 shadow-inner';
      statusText.innerText = 'Physiological Equilibrium: Stable';
    }

    concernsText.innerText = data.primary_concerns.join(' • ');

    // Render Explainable Risk Factors (XAI)
    renderRiskFactors(data.risk_factors || []);

  } catch (err) {
    console.error('Error fetching risk assessment:', err);
  }
}

function renderRiskFactors(factors) {
  const container = document.getElementById('risk-factors-list');
  if (!container) return;

  if (factors.length === 0) {
    container.innerHTML = `
      <div class="text-center py-6 text-gray-500 text-xs">
        <i data-lucide="check-circle" class="w-6 h-6 mx-auto mb-1 text-emerald-500"></i>
        No elevated risk factors detected.
      </div>`;
    if (window.lucide) lucide.createIcons();
    return;
  }

  container.innerHTML = factors.map(f => {
    let barColor = 'bg-emerald-500';
    let textColor = 'text-emerald-400';
    if (f.impact === 'High') {
      barColor = 'bg-rose-500';
      textColor = 'text-rose-400';
    } else if (f.impact === 'Moderate') {
      barColor = 'bg-amber-500';
      textColor = 'text-amber-400';
    }

    const pct = Math.round(f.contribution * 100);

    return `
      <div class="p-2.5 rounded-xl bg-slate-800/60 border border-gray-800 text-xs">
        <div class="flex items-center justify-between mb-1">
          <span class="font-semibold text-gray-200">${f.feature}</span>
          <span class="${textColor} font-bold">${f.impact} Impact</span>
        </div>
        <p class="text-[11px] text-gray-400 mb-1.5 leading-snug">${f.description}</p>
        <div class="w-full bg-gray-900 rounded-full h-1.5 overflow-hidden">
          <div class="${barColor} h-full rounded-full transition-all duration-300" style="width: ${Math.max(10, pct)}%"></div>
        </div>
      </div>
    `;
  }).join('');

  if (window.lucide) lucide.createIcons();
}

// 3. Trends & Charts
async function fetchTrends(forceRecreate = true) {
  try {
    const days = document.getElementById('scenario-days')?.value || 7;
    const res = await fetch(`/api/health/trends?days=${days}`);
    if (!res.ok) return;
    const data = await res.json();
    cachedTrendsData = data;
    renderTrendChart(data);
  } catch (err) {
    console.error('Error fetching trends:', err);
  }
}

function renderTrendChart(data) {
  const canvas = document.getElementById('mainTrendChart');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  const base = data.baseline || {};

  if (trendChartInstance) {
    trendChartInstance.destroy();
  }

  // 1. Heart Rate High-Res View
  if (activeChartType === 'hr') {
    const timeline = data.timeline || [];
    const labels = timeline.map(t => {
      const d = new Date(t.timestamp);
      return `${d.getMonth()+1}/${d.getDate()} ${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`;
    });
    const hrValues = timeline.map(t => t.heart_rate);
    const upperLimit = timeline.map(() => base.resting_hr_upper || 82);
    const lowerLimit = timeline.map(() => base.resting_hr_lower || 58);
    const meanLine = timeline.map(() => base.resting_hr_mean || 70);

    trendChartInstance = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Heart Rate (BPM)',
            data: hrValues,
            borderColor: '#f43f5e',
            backgroundColor: 'rgba(244, 63, 94, 0.1)',
            borderWidth: 2,
            pointRadius: hrValues.length > 50 ? 0 : 2,
            tension: 0.3,
            fill: false
          },
          {
            label: 'Baseline Upper (+2σ)',
            data: upperLimit,
            borderColor: 'rgba(16, 185, 129, 0.4)',
            borderDash: [4, 4],
            borderWidth: 1.5,
            pointRadius: 0,
            fill: false
          },
          {
            label: 'Baseline Mean',
            data: meanLine,
            borderColor: 'rgba(52, 211, 153, 0.7)',
            borderDash: [2, 2],
            borderWidth: 1,
            pointRadius: 0,
            fill: false
          },
          {
            label: 'Baseline Lower (-2σ)',
            data: lowerLimit,
            borderColor: 'rgba(16, 185, 129, 0.4)',
            borderDash: [4, 4],
            borderWidth: 1.5,
            pointRadius: 0,
            fill: false
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { labels: { color: '#9ca3af', boxWidth: 12, font: { size: 11 } } }
        },
        scales: {
          x: { ticks: { color: '#6b7280', maxTicksLimit: 10 }, grid: { color: 'rgba(75, 85, 99, 0.15)' } },
          y: { min: 40, max: 180, ticks: { color: '#9ca3af' }, grid: { color: 'rgba(75, 85, 99, 0.2)' } }
        }
      }
    });

  // 2. Steps Bar View
  } else if (activeChartType === 'steps') {
    const daily = data.daily_trends || [];
    const labels = daily.map(d => d.date);
    const steps = daily.map(d => d.total_steps);
    const targetSteps = daily.map(() => base.target_steps || 8000);

    trendChartInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          {
            type: 'bar',
            label: 'Daily Steps',
            data: steps,
            backgroundColor: steps.map(s => s >= 8000 ? 'rgba(34, 197, 94, 0.7)' : 'rgba(245, 158, 11, 0.7)'),
            borderRadius: 6
          },
          {
            type: 'line',
            label: 'Target Goal (8,000)',
            data: targetSteps,
            borderColor: '#38bdf8',
            borderDash: [5, 5],
            borderWidth: 2,
            pointRadius: 0,
            fill: false
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#9ca3af', font: { size: 11 } } } },
        scales: {
          x: { ticks: { color: '#9ca3af' }, grid: { display: false } },
          y: { beginAtZero: true, ticks: { color: '#9ca3af' }, grid: { color: 'rgba(75, 85, 99, 0.2)' } }
        }
      }
    });

  // 3. Sleep & Resting HR View
  } else if (activeChartType === 'sleep') {
    const daily = data.daily_trends || [];
    const labels = daily.map(d => d.date);
    const sleepHours = daily.map(d => d.total_sleep);
    const restingHR = daily.map(d => d.resting_hr);

    trendChartInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          {
            type: 'bar',
            label: 'Sleep Duration (hrs)',
            data: sleepHours,
            backgroundColor: 'rgba(99, 102, 241, 0.65)',
            yAxisID: 'ySleep',
            borderRadius: 6
          },
          {
            type: 'line',
            label: 'Morning Resting HR (BPM)',
            data: restingHR,
            borderColor: '#f43f5e',
            backgroundColor: '#f43f5e',
            borderWidth: 2,
            pointRadius: 4,
            yAxisID: 'yHR'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#9ca3af', font: { size: 11 } } } },
        scales: {
          x: { ticks: { color: '#9ca3af' }, grid: { display: false } },
          ySleep: {
            type: 'linear',
            position: 'left',
            min: 0,
            max: 12,
            ticks: { color: '#818cf8' },
            grid: { color: 'rgba(75, 85, 99, 0.15)' }
          },
          yHR: {
            type: 'linear',
            position: 'right',
            min: 45,
            max: 115,
            ticks: { color: '#f43f5e' },
            grid: { display: false }
          }
        }
      }
    });

  // 4. SpO2 & Temp Stability View
  } else if (activeChartType === 'spo2') {
    const daily = data.daily_trends || [];
    const labels = daily.map(d => d.date);
    const avgSpo2 = daily.map(d => d.avg_spo2);
    const minSpo2 = daily.map(d => d.min_spo2);
    const avgTemp = daily.map(d => d.avg_temp);

    trendChartInstance = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Min SpO₂ (%)',
            data: minSpo2,
            borderColor: '#06b6d4',
            backgroundColor: 'rgba(6, 182, 212, 0.15)',
            borderWidth: 2,
            fill: true,
            yAxisID: 'ySpo2'
          },
          {
            label: 'Avg Temperature (°C)',
            data: avgTemp,
            borderColor: '#14b8a6',
            borderWidth: 2,
            pointRadius: 3,
            yAxisID: 'yTemp'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#9ca3af', font: { size: 11 } } } },
        scales: {
          x: { ticks: { color: '#9ca3af' }, grid: { display: false } },
          ySpo2: {
            type: 'linear',
            position: 'left',
            min: 75,
            max: 100,
            ticks: { color: '#06b6d4' },
            grid: { color: 'rgba(75, 85, 99, 0.15)' }
          },
          yTemp: {
            type: 'linear',
            position: 'right',
            min: 35.0,
            max: 40.5,
            ticks: { color: '#14b8a6' },
            grid: { display: false }
          }
        }
      }
    });
  }
}

// 4. Anomalies & Alerts
async function fetchAnomalies() {
  try {
    const res = await fetch('/api/health/anomalies?limit=25');
    if (!res.ok) return;
    const alerts = await res.json();

    const filtered = currentAlertFilter === 'all' 
      ? alerts 
      : alerts.filter(a => a.severity.toLowerCase() === currentAlertFilter.toLowerCase());

    const badge = document.getElementById('alerts-count-badge');
    const unackCount = alerts.filter(a => !a.is_acknowledged).length;
    badge.innerText = `${unackCount} Active`;

    renderAlerts(filtered);
  } catch (err) {
    console.error('Error fetching anomalies:', err);
  }
}

function renderAlerts(alerts) {
  const container = document.getElementById('alerts-container');
  if (!container) return;

  if (alerts.length === 0) {
    container.innerHTML = `
      <div class="text-center py-8 text-gray-500 text-xs bg-slate-950/40 rounded-xl border border-gray-800">
        <i data-lucide="shield-check" class="w-8 h-8 mx-auto mb-2 text-emerald-500"></i>
        No anomaly alerts match the current filter.
      </div>`;
    if (window.lucide) lucide.createIcons();
    return;
  }

  container.innerHTML = alerts.map(a => {
    const d = new Date(a.timestamp);
    const timeStr = `${d.toLocaleDateString()} ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;

    let sevBadgeClass = 'bg-blue-950 text-blue-300 border-blue-800';
    let cardBorder = 'border-gray-800';
    let iconName = 'info';

    if (a.severity === 'severe') {
      sevBadgeClass = 'bg-rose-950 text-rose-300 border-rose-800';
      cardBorder = 'border-severe bg-rose-950/10';
      iconName = 'alert-octagon';
    } else if (a.severity === 'moderate') {
      sevBadgeClass = 'bg-amber-950 text-amber-300 border-amber-800';
      cardBorder = 'border-moderate bg-amber-950/10';
      iconName = 'alert-triangle';
    }

    return `
      <div class="p-3.5 rounded-xl border ${cardBorder} bg-slate-800/40 transition hover:bg-slate-800/70 text-xs">
        <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 mb-1.5">
          <div class="flex items-center gap-2">
            <span class="px-2 py-0.5 rounded-md text-[10px] uppercase font-extrabold border ${sevBadgeClass}">
              ${a.severity}
            </span>
            <span class="font-bold text-white text-sm">${a.parameter}</span>
            <span class="text-[10px] text-gray-500 font-mono">(${a.detector_type})</span>
          </div>
          <span class="text-[11px] text-gray-400 font-mono">${timeStr}</span>
        </div>

        <p class="text-gray-300 text-xs mt-1 leading-relaxed">${a.explanation}</p>
        
        <div class="mt-2.5 pt-2 border-t border-gray-800/80 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
          <div class="text-[11px] text-emerald-400/90 flex items-center gap-1.5">
            <i data-lucide="arrow-right-circle" class="w-3.5 h-3.5 shrink-0"></i>
            <span>${a.recommendation}</span>
          </div>

          ${!a.is_acknowledged ? `
            <button onclick="acknowledgeAlert(${a.id})" class="px-2.5 py-1 rounded bg-slate-700 hover:bg-slate-600 text-[11px] text-gray-200 transition shrink-0">
              Acknowledge
            </button>
          ` : `
            <span class="text-[10px] text-gray-500 flex items-center gap-1">
              <i data-lucide="check" class="w-3 h-3 text-emerald-500"></i> Reviewed
            </span>
          `}
        </div>
      </div>
    `;
  }).join('');

  if (window.lucide) lucide.createIcons();
}

async function acknowledgeAlert(alertId) {
  try {
    await fetch(`/api/health/anomalies/${alertId}/acknowledge`, { method: 'POST' });
    showToast('Alert marked as reviewed', 'success');
    fetchAnomalies();
  } catch (err) {
    showToast('Error updating alert', 'error');
  }
}

// ----------------------------------------------------
// SCENARIO SIMULATOR & STREAMING
// ----------------------------------------------------

async function triggerScenario(scenario, days) {
  showToast(`Generating ${days}-day '${scenario}' scenario dataset...`, 'info');
  try {
    const res = await fetch('/api/simulator/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario: scenario, days: days })
    });
    if (!res.ok) throw new Error('Generation failed');
    const data = await res.json();
    
    showToast(`Injected '${scenario}' scenario (${data.samples_generated} points)`, 'success');
    await refreshDashboardData();
  } catch (err) {
    showToast('Failed to trigger scenario: ' + err.message, 'error');
  }
}

async function toggleLiveStreaming() {
  try {
    const res = await fetch('/api/simulator/stream/toggle', { method: 'POST' });
    const data = await res.json();
    isStreamingActive = data.is_streaming;
    updateStreamIndicator(isStreamingActive);
    showToast(data.message, isStreamingActive ? 'success' : 'info');
  } catch (err) {
    showToast('Error toggling stream', 'error');
  }
}

async function fetchSimulatorStatus() {
  try {
    const res = await fetch('/api/simulator/status');
    if (!res.ok) return;
    const data = await res.json();
    isStreamingActive = data.is_streaming;
    updateStreamIndicator(isStreamingActive);
  } catch (err) {
    // Ignore on normal refresh
  }
}

function updateStreamIndicator(active) {
  const dot = document.getElementById('stream-indicator');
  const txt = document.getElementById('stream-text');
  if (active) {
    dot.className = 'w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping-slow';
    txt.innerText = 'Live Stream: Active (3s)';
    txt.className = 'text-emerald-400 font-semibold';
  } else {
    dot.className = 'w-2.5 h-2.5 rounded-full bg-gray-500';
    txt.innerText = 'Live Stream: Off';
    txt.className = 'text-gray-300 font-normal';
  }
}

async function resetDatabase() {
  if (!confirm('Reset health history to default 7-day clean baseline?')) return;
  try {
    await fetch('/api/simulator/reset', { method: 'POST' });
    showToast('Database reset to clean baseline', 'success');
    await refreshDashboardData();
  } catch (err) {
    showToast('Error resetting database', 'error');
  }
}

// ----------------------------------------------------
// MANUAL INGEST & PROFILE MODALS
// ----------------------------------------------------

async function handleManualIngest(e) {
  e.preventDefault();
  const payload = {
    heart_rate: parseFloat(document.getElementById('inp-hr').value),
    spo2: parseFloat(document.getElementById('inp-spo2').value),
    steps: parseInt(document.getElementById('inp-steps').value),
    temperature: parseFloat(document.getElementById('inp-temp').value),
    activity: document.getElementById('inp-activity').value,
    sleep_hours: parseFloat(document.getElementById('inp-sleep').value),
    is_resting: document.getElementById('inp-activity').value === 'Sedentary' && parseInt(document.getElementById('inp-steps').value) === 0
  };

  try {
    const res = await fetch('/api/health/ingest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error('Ingest error');
    document.getElementById('modal-ingest').classList.add('hidden');
    showToast('Sensor reading recorded & analyzed!', 'success');
    await refreshDashboardData();
  } catch (err) {
    showToast('Failed to ingest reading', 'error');
  }
}

async function openProfileModal() {
  try {
    const res = await fetch('/api/user/profile');
    if (!res.ok) return;
    const p = await res.json();

    document.getElementById('prof-hr-mean').value = p.resting_hr_mean;
    document.getElementById('prof-hr-std').value = p.resting_hr_std;
    document.getElementById('prof-target-steps').value = p.target_steps;
    document.getElementById('prof-target-sleep').value = p.target_sleep;
    document.getElementById('prof-min-spo2').value = p.normal_spo2_min;

    document.getElementById('modal-profile').classList.remove('hidden');
  } catch (err) {
    showToast('Error loading profile', 'error');
  }
}

async function handleProfileUpdate(e) {
  e.preventDefault();
  const payload = {
    resting_hr_mean: parseFloat(document.getElementById('prof-hr-mean').value),
    resting_hr_std: parseFloat(document.getElementById('prof-hr-std').value),
    target_steps: parseInt(document.getElementById('prof-target-steps').value),
    target_sleep: parseFloat(document.getElementById('prof-target-sleep').value),
    normal_spo2_min: parseFloat(document.getElementById('prof-min-spo2').value)
  };

  try {
    const res = await fetch('/api/user/profile', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error('Update failed');
    document.getElementById('modal-profile').classList.add('hidden');
    showToast('Personal baselines updated!', 'success');
    await refreshDashboardData();
  } catch (err) {
    showToast('Failed to update baseline', 'error');
  }
}

// ----------------------------------------------------
// TOAST NOTIFICATIONS
// ----------------------------------------------------

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  let bg = 'bg-slate-900 border-gray-700 text-gray-200';
  if (type === 'success') bg = 'bg-emerald-950 border-emerald-700 text-emerald-200';
  if (type === 'error') bg = 'bg-rose-950 border-rose-700 text-rose-200';
  if (type === 'info') bg = 'bg-slate-900 border-cyan-700 text-cyan-200';

  toast.className = `px-4 py-2.5 rounded-xl border shadow-xl text-xs font-medium flex items-center gap-2 transform transition-all duration-300 translate-y-2 opacity-0 ${bg}`;
  toast.innerHTML = `<span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.remove('translate-y-2', 'opacity-0');
  }, 10);

  setTimeout(() => {
    toast.classList.add('opacity-0', 'translate-y-2');
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}
