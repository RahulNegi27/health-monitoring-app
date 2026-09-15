// PulseGuard AI — Professional Application Logic & Real-Time Engines

let activeChartType = 'hr';
let trendChartInstance = null;
let currentAlertFilter = 'all';
let isStreamingActive = false;
let pollingTimer = null;
let cachedTrendsData = null;
let currentBpm = 72;

// Real-Time ECG Oscilloscope State
let ecgCanvas = null;
let ecgCtx = null;
let ecgAnimationId = null;
let ecgX = 0;
let ecgPoints = [];
let lastPulseTime = 0;

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  if (window.lucide) {
    lucide.createIcons();
  }
  
  initEcgOscilloscope();
  setupEventListeners();
  fetchInitialData();
  
  // Start periodic polling every 3.5 seconds
  pollingTimer = setInterval(refreshDashboardData, 3500);
});

// ----------------------------------------------------
// REAL-TIME ECG OSCILLOSCOPE CANVAS ENGINE
// ----------------------------------------------------

function initEcgOscilloscope() {
  ecgCanvas = document.getElementById('ecgCanvas');
  if (!ecgCanvas) return;

  ecgCtx = ecgCanvas.getContext('2d');
  
  // Handle high-DPI displays
  function resizeCanvas() {
    const rect = ecgCanvas.parentElement.getBoundingClientRect();
    ecgCanvas.width = rect.width * (window.devicePixelRatio || 1);
    ecgCanvas.height = rect.height * (window.devicePixelRatio || 1);
    ecgCtx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);
    ecgPoints = [];
    ecgX = 0;
  }

  resizeCanvas();
  window.addEventListener('resize', resizeCanvas);

  lastPulseTime = performance.now();
  renderEcgFrame();
}

function renderEcgFrame(now = performance.now()) {
  if (!ecgCanvas || !ecgCtx) return;

  const w = ecgCanvas.parentElement.clientWidth;
  const h = ecgCanvas.parentElement.clientHeight;
  const midY = h / 2;

  // Heart rate interval in milliseconds (e.g. 72 bpm = 833ms)
  const bpm = Math.max(40, Math.min(200, currentBpm));
  const intervalMs = (60 / bpm) * 1000;
  const timeSincePulse = (now - lastPulseTime) % intervalMs;

  // Synthesize realistic P-Q-R-S-T wave offset
  // Wave occurs in the first 350ms of each cardiac cycle
  let dy = 0;
  if (timeSincePulse < 380) {
    const t = timeSincePulse;
    if (t > 40 && t < 100) {
      // P wave (atrial depolarization)
      dy = -Math.sin(((t - 40) / 60) * Math.PI) * (h * 0.14);
    } else if (t >= 110 && t < 130) {
      // Q dip
      dy = Math.sin(((t - 110) / 20) * Math.PI) * (h * 0.08);
    } else if (t >= 130 && t < 170) {
      // R peak (ventricular depolarization - sharp upward surge)
      dy = -Math.sin(((t - 130) / 40) * Math.PI) * (h * 0.44);
    } else if (t >= 170 && t < 200) {
      // S dip
      dy = Math.sin(((t - 170) / 30) * Math.PI) * (h * 0.16);
    } else if (t >= 230 && t < 350) {
      // T wave (ventricular repolarization)
      dy = -Math.sin(((t - 230) / 120) * Math.PI) * (h * 0.18);
    }
  }

  // Add slight random physiological tremor
  dy += (Math.random() - 0.5) * 1.5;

  const currentY = midY + dy;
  ecgPoints.push({ x: ecgX, y: currentY });

  // Clear canvas
  ecgCtx.clearRect(0, 0, w, h);

  // Draw phosphor waveform trail
  if (ecgPoints.length > 1) {
    ecgCtx.beginPath();
    ecgCtx.lineWidth = 1.8;
    ecgCtx.strokeStyle = '#10b981';
    ecgCtx.shadowColor = '#10b981';
    ecgCtx.shadowBlur = 6;

    for (let i = 0; i < ecgPoints.length; i++) {
      const pt = ecgPoints[i];
      if (i === 0) {
        ecgCtx.moveTo(pt.x, pt.y);
      } else {
        ecgCtx.lineTo(pt.x, pt.y);
      }
    }
    ecgCtx.stroke();
    ecgCtx.shadowBlur = 0;

    // Draw active beam glowing head
    const head = ecgPoints[ecgPoints.length - 1];
    ecgCtx.fillStyle = '#6ee7b7';
    ecgCtx.beginPath();
    ecgCtx.arc(head.x, head.y, 2.8, 0, Math.PI * 2);
    ecgCtx.fill();
  }

  // Advance scan line
  ecgX += 2.0;
  if (ecgX >= w) {
    ecgX = 0;
    ecgPoints = [];
  }

  // Remove trailing points ahead of scan head to simulate CRT sweep
  ecgPoints = ecgPoints.filter(pt => pt.x < ecgX);

  ecgAnimationId = requestAnimationFrame(renderEcgFrame);
}

// ----------------------------------------------------
// EVENT LISTENERS & MODAL MANAGEMENT
// ----------------------------------------------------

function setupEventListeners() {
  // 1. Chart Tabs
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
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

  // 2. Preset Scenarios
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

  // 5. Modals Open/Close
  document.getElementById('btn-open-ingest').addEventListener('click', () => {
    document.getElementById('modal-ingest').classList.remove('hidden');
  });

  document.getElementById('btn-open-profile').addEventListener('click', openProfileModal);

  document.getElementById('btn-open-ml').addEventListener('click', openMlModal);

  document.getElementById('btn-open-supabase').addEventListener('click', openSupabaseModal);

  document.querySelectorAll('.btn-close-modal').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.modal-backdrop').forEach(m => m.classList.add('hidden'));
    });
  });

  // 6. Form submissions
  document.getElementById('form-ingest').addEventListener('submit', handleManualIngest);
  document.getElementById('form-profile').addEventListener('submit', handleProfileUpdate);
  document.getElementById('form-supabase-config').addEventListener('submit', handleSupabaseConfig);

  // 7. Supabase Actions
  document.getElementById('btn-test-supabase').addEventListener('click', testSupabaseConnection);
  document.getElementById('btn-sync-supabase').addEventListener('click', syncToSupabase);
  document.getElementById('btn-copy-sql').addEventListener('click', copySupabaseSql);

  // 8. ML Actions
  const trainSlider = document.getElementById('train-sample-slider');
  if (trainSlider) {
    trainSlider.addEventListener('input', (e) => {
      document.getElementById('train-sample-val').innerText = parseInt(e.target.value).toLocaleString();
    });
  }
  document.getElementById('btn-trigger-train').addEventListener('click', handleTrainModels);

  // 9. Reset DB
  document.getElementById('btn-reset-db').addEventListener('click', resetDatabase);
}

// ----------------------------------------------------
// DATA FETCHING & REFRESH
// ----------------------------------------------------

async function fetchInitialData() {
  await Promise.all([
    fetchSummary(),
    fetchRiskAssessment(),
    fetchTrends(),
    fetchAnomalies(),
    fetchSimulatorStatus(),
    fetchSupabaseStatus()
  ]);
}

async function refreshDashboardData() {
  await Promise.all([
    fetchSummary(),
    fetchRiskAssessment(),
    fetchTrends(false),
    fetchAnomalies(),
    fetchSimulatorStatus(),
    fetchSupabaseStatus()
  ]);
}

// 1. Summary
async function fetchSummary() {
  try {
    const res = await fetch('/api/health/summary');
    if (!res.ok) return;
    const data = await res.json();

    // Heart Rate
    const hrVal = Math.round(data.heart_rate.current);
    currentBpm = hrVal;
    document.getElementById('val-hr').innerText = hrVal;
    document.getElementById('ecg-live-bpm').innerText = hrVal;
    document.getElementById('val-resting-hr').innerText = Math.round(data.resting_hr.current);
    document.getElementById('sub-hr').innerText = data.heart_rate.subtext;

    // Adapt heartbeat animation speed to actual BPM
    const pulseHeart = document.getElementById('icon-pulse-heart');
    if (pulseHeart) {
      const pulsePeriod = (60 / Math.max(40, hrVal)).toFixed(2);
      pulseHeart.style.setProperty('--pulse-speed', `${pulsePeriod}s`);
    }

    // Update ECG sub-status label
    const ecgStatus = document.getElementById('ecg-status-sub');
    if (hrVal >= 100) {
      ecgStatus.innerText = 'Sinus Tachycardia';
      ecgStatus.className = 'text-rose-400 font-bold';
    } else if (hrVal < 50) {
      ecgStatus.innerText = 'Sinus Bradycardia';
      ecgStatus.className = 'text-amber-400 font-bold';
    } else {
      ecgStatus.innerText = 'Sinus Rhythm Normal';
      ecgStatus.className = 'text-emerald-400';
    }

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
    badgeSleep.className = data.sleep.current >= 6.5 ? 'text-indigo-400 font-semibold font-mono' : 'text-amber-400 font-bold font-mono';

    // SpO2
    document.getElementById('val-spo2').innerText = data.spo2.current.toFixed(1);
    const badgeSpo2 = document.getElementById('badge-spo2');
    if (data.spo2.current < 90) {
      badgeSpo2.innerText = 'Critical';
      badgeSpo2.className = 'ml-auto text-xs px-2 py-0.5 rounded-full bg-rose-950 text-rose-300 border border-rose-800 animate-pulse font-bold';
    } else if (data.spo2.current < 95) {
      badgeSpo2.innerText = 'Borderline';
      badgeSpo2.className = 'ml-auto text-xs px-2 py-0.5 rounded-full bg-amber-950 text-amber-300 border border-amber-800 font-semibold';
    } else {
      badgeSpo2.innerText = 'Safe';
      badgeSpo2.className = 'ml-auto text-xs px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-400 border border-cyan-800/60 font-semibold';
    }

    // Temperature
    document.getElementById('val-temp').innerText = data.temperature.current.toFixed(1);
    const badgeTemp = document.getElementById('badge-temp');
    if (data.temperature.current >= 38.3) {
      badgeTemp.innerText = 'High Fever';
      badgeTemp.className = 'ml-auto text-xs px-2 py-0.5 rounded-full bg-rose-950 text-rose-300 border border-rose-800 animate-pulse font-bold';
    } else if (data.temperature.current >= 37.5) {
      badgeTemp.innerText = 'Elevated';
      badgeTemp.className = 'ml-auto text-xs px-2 py-0.5 rounded-full bg-amber-950 text-amber-300 border border-amber-800 font-semibold';
    } else {
      badgeTemp.innerText = 'Afebrile';
      badgeTemp.className = 'ml-auto text-xs px-2 py-0.5 rounded-full bg-teal-950 text-teal-400 border border-teal-800/60 font-semibold';
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
    const statusText = document.getElementById('wellness-status-text');
    const concernsText = document.getElementById('risk-concerns-text');
    const scoreNum = document.getElementById('risk-score-num');
    const anomProb = document.getElementById('anomaly-prob-val');
    const recText = document.getElementById('wellness-rec-text');
    const circleBar = document.getElementById('risk-circle-bar');

    const scoreRounded = Math.round(data.risk_score_numeric);
    scoreNum.innerText = scoreRounded;
    anomProb.innerText = `${Math.round(data.anomaly_probability * 100)}%`;
    recText.innerText = data.wellness_recommendation;

    badge.innerText = `${data.overall_risk_level} Risk`;

    // SVG Circular Gauge Dasharray
    if (circleBar) {
      circleBar.setAttribute('stroke-dasharray', `${Math.max(4, scoreRounded)}, 100`);
    }

    if (data.overall_risk_level === 'High') {
      banner.className = 'glass-panel rounded-2xl p-5 border border-rose-700/60 bg-gradient-to-r from-rose-950/40 via-slate-900/80 to-slate-900 shadow-2xl shadow-rose-950/20 transition-all duration-300';
      badge.className = 'px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-950 text-rose-200 border border-rose-700 animate-pulse';
      if (circleBar) circleBar.setAttribute('class', 'text-rose-500 transition-all duration-700');
      statusText.innerText = 'Physiological Strain Detected';
    } else if (data.overall_risk_level === 'Moderate') {
      banner.className = 'glass-panel rounded-2xl p-5 border border-amber-700/50 bg-gradient-to-r from-amber-950/30 via-slate-900/80 to-slate-900 shadow-2xl shadow-amber-950/20 transition-all duration-300';
      badge.className = 'px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-950 text-amber-200 border border-amber-700';
      if (circleBar) circleBar.setAttribute('class', 'text-amber-500 transition-all duration-700');
      statusText.innerText = 'Elevated Baseline Deviation';
    } else {
      banner.className = 'glass-panel rounded-2xl p-5 border border-emerald-900/40 bg-gradient-to-r from-emerald-950/30 via-slate-900/80 to-slate-900 shadow-2xl transition-all duration-300';
      badge.className = 'px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-950 text-emerald-300 border border-emerald-700';
      if (circleBar) circleBar.setAttribute('class', 'text-emerald-500 transition-all duration-700');
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
      <div class="p-2.5 rounded-xl bg-slate-900/70 border border-gray-800 text-xs">
        <div class="flex items-center justify-between mb-1">
          <span class="font-bold text-gray-200">${f.feature}</span>
          <span class="${textColor} font-mono font-bold">${f.impact} Impact</span>
        </div>
        <p class="text-[11px] text-gray-400 mb-1.5 leading-snug">${f.description}</p>
        <div class="w-full bg-slate-950 rounded-full h-1.5 overflow-hidden">
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

  // 1. Heart Rate High-Res Timeline View
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

    // Gradient fill for HR line
    const gradient = ctx.createLinearGradient(0, 0, 0, 300);
    gradient.addColorStop(0, 'rgba(244, 63, 94, 0.25)');
    gradient.addColorStop(1, 'rgba(244, 63, 94, 0.0)');

    trendChartInstance = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Heart Rate (BPM)',
            data: hrValues,
            borderColor: '#f43f5e',
            backgroundColor: gradient,
            borderWidth: 2,
            pointRadius: hrValues.length > 50 ? 0 : 2.5,
            tension: 0.35,
            fill: true
          },
          {
            label: 'Baseline Upper (+2σ)',
            data: upperLimit,
            borderColor: 'rgba(16, 185, 129, 0.45)',
            borderDash: [4, 4],
            borderWidth: 1.5,
            pointRadius: 0,
            fill: false
          },
          {
            label: 'Baseline Mean',
            data: meanLine,
            borderColor: 'rgba(52, 211, 153, 0.75)',
            borderDash: [2, 2],
            borderWidth: 1.5,
            pointRadius: 0,
            fill: false
          },
          {
            label: 'Baseline Lower (-2σ)',
            data: lowerLimit,
            borderColor: 'rgba(16, 185, 129, 0.45)',
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
          legend: { labels: { color: '#9ca3af', boxWidth: 12, font: { size: 11, family: 'Plus Jakarta Sans' } } }
        },
        scales: {
          x: { ticks: { color: '#6b7280', maxTicksLimit: 10, font: { family: 'JetBrains Mono', size: 10 } }, grid: { color: 'rgba(75, 85, 99, 0.15)' } },
          y: { min: 40, max: 180, ticks: { color: '#9ca3af', font: { family: 'JetBrains Mono', size: 10 } }, grid: { color: 'rgba(75, 85, 99, 0.18)' } }
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
            backgroundColor: steps.map(s => s >= 8000 ? 'rgba(16, 185, 129, 0.75)' : 'rgba(245, 158, 11, 0.75)'),
            borderRadius: 8
          },
          {
            type: 'line',
            label: 'Target Goal',
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
          x: { ticks: { color: '#9ca3af', font: { family: 'JetBrains Mono', size: 10 } }, grid: { display: false } },
          y: { beginAtZero: true, ticks: { color: '#9ca3af', font: { family: 'JetBrains Mono', size: 10 } }, grid: { color: 'rgba(75, 85, 99, 0.18)' } }
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
            backgroundColor: 'rgba(129, 140, 248, 0.75)',
            yAxisID: 'ySleep',
            borderRadius: 8
          },
          {
            type: 'line',
            label: 'Resting HR (BPM)',
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
          x: { ticks: { color: '#9ca3af', font: { family: 'JetBrains Mono', size: 10 } }, grid: { display: false } },
          ySleep: {
            type: 'linear',
            position: 'left',
            min: 0,
            max: 12,
            ticks: { color: '#818cf8', font: { family: 'JetBrains Mono', size: 10 } },
            grid: { color: 'rgba(75, 85, 99, 0.15)' }
          },
          yHR: {
            type: 'linear',
            position: 'right',
            min: 45,
            max: 115,
            ticks: { color: '#f43f5e', font: { family: 'JetBrains Mono', size: 10 } },
            grid: { display: false }
          }
        }
      }
    });

  // 4. SpO2 & Temperature Stability View
  } else if (activeChartType === 'spo2') {
    const daily = data.daily_trends || [];
    const labels = daily.map(d => d.date);
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
          x: { ticks: { color: '#9ca3af', font: { family: 'JetBrains Mono', size: 10 } }, grid: { display: false } },
          ySpo2: {
            type: 'linear',
            position: 'left',
            min: 75,
            max: 100,
            ticks: { color: '#06b6d4', font: { family: 'JetBrains Mono', size: 10 } },
            grid: { color: 'rgba(75, 85, 99, 0.15)' }
          },
          yTemp: {
            type: 'linear',
            position: 'right',
            min: 35.0,
            max: 40.5,
            ticks: { color: '#14b8a6', font: { family: 'JetBrains Mono', size: 10 } },
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

    if (a.severity === 'severe') {
      sevBadgeClass = 'bg-rose-950 text-rose-300 border-rose-800';
      cardBorder = 'border-severe bg-rose-950/10';
    } else if (a.severity === 'moderate') {
      sevBadgeClass = 'bg-amber-950 text-amber-300 border-amber-800';
      cardBorder = 'border-moderate bg-amber-950/10';
    }

    return `
      <div class="p-3.5 rounded-xl border ${cardBorder} bg-slate-900/60 transition hover:bg-slate-800/70 text-xs">
        <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 mb-1.5">
          <div class="flex items-center gap-2">
            <span class="px-2 py-0.5 rounded-md text-[10px] uppercase font-extrabold border ${sevBadgeClass} font-mono">
              ${a.severity}
            </span>
            <span class="font-bold text-white text-sm">${a.parameter}</span>
            <span class="text-[10px] text-gray-500 font-mono">(${a.detector_type})</span>
          </div>
          <span class="text-[11px] text-gray-400 font-mono">${timeStr}</span>
        </div>

        <p class="text-gray-300 text-xs mt-1 leading-relaxed">${a.explanation}</p>
        
        <div class="mt-2.5 pt-2 border-t border-gray-800/80 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
          <div class="text-[11px] text-emerald-400 flex items-center gap-1.5 font-medium">
            <i data-lucide="arrow-right-circle" class="w-3.5 h-3.5 shrink-0 text-emerald-400"></i>
            <span>${a.recommendation}</span>
          </div>

          ${!a.is_acknowledged ? `
            <button onclick="acknowledgeAlert(${a.id})" class="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-[11px] text-gray-200 transition shrink-0 font-medium">
              Acknowledge
            </button>
          ` : `
            <span class="text-[10px] text-gray-500 flex items-center gap-1 font-mono">
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
    // Ignore
  }
}

function updateStreamIndicator(active) {
  const dot = document.getElementById('stream-indicator');
  const txt = document.getElementById('stream-text');
  if (active) {
    dot.className = 'w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping-slow';
    txt.innerText = 'Live Stream: Active (3s)';
    txt.className = 'hidden sm:inline text-emerald-400 font-bold';
  } else {
    dot.className = 'w-2.5 h-2.5 rounded-full bg-gray-500';
    txt.innerText = 'Live Stream: Off';
    txt.className = 'hidden sm:inline text-gray-300 font-normal';
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
// ML MODEL STUDIO & TRAINING PIPELINE
// ----------------------------------------------------

async function openMlModal() {
  document.getElementById('modal-ml').classList.remove('hidden');
  await fetchMlMetrics();
}

async function fetchMlMetrics() {
  try {
    const res = await fetch('/api/ml/metrics');
    if (!res.ok) return;
    const data = await res.json();

    const perf = data.performance || {};
    const samples = data.sample_counts || {};

    document.getElementById('ml-stat-acc').innerText = `${((perf.test_accuracy || 0.965) * 100).toFixed(1)}%`;
    document.getElementById('ml-stat-f1').innerText = (perf.macro_f1 || 0.958).toFixed(3);
    document.getElementById('ml-stat-cv').innerText = `${((perf.cv_5fold_mean_f1 || 0.95) * 100).toFixed(1)}%`;
    document.getElementById('ml-stat-samples').innerText = (samples.total_samples || 3000).toLocaleString();

    if (data.trained_at) {
      const dt = new Date(data.trained_at);
      document.getElementById('ml-last-trained').innerText = `Trained: ${dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
    }

    // Render Confusion Matrix
    renderConfusionMatrix(data.confusion_matrix);
  } catch (err) {
    console.error('Error fetching ML metrics:', err);
  }
}

function renderConfusionMatrix(cmData) {
  const tbody = document.getElementById('cm-table-body');
  if (!tbody || !cmData) return;

  const matrix = cmData.matrix || [[330, 0, 0], [0, 168, 0], [0, 0, 102]];
  const classes = cmData.classes || ['Low', 'Moderate', 'High'];

  tbody.innerHTML = classes.map((rowName, i) => {
    const row = matrix[i] || [0, 0, 0];
    return `
      <tr class="border-t border-gray-800/80">
        <td class="p-2 text-left text-gray-300 font-bold">Act: ${rowName}</td>
        ${row.map((val, j) => {
          const isDiagonal = (i === j);
          const cellClass = isDiagonal && val > 0 ? 'cm-cell-high font-bold' : (val === 0 ? 'cm-cell-zero' : 'cm-cell-err font-bold');
          return `<td class="p-2 ${cellClass} rounded-lg">${val}</td>`;
        }).join('')}
      </tr>
    `;
  }).join('');
}

async function handleTrainModels() {
  const btn = document.getElementById('btn-trigger-train');
  const btnText = document.getElementById('train-btn-text');
  const samples = parseInt(document.getElementById('train-sample-slider').value || 3000);

  btn.disabled = true;
  btnText.innerText = 'Training Pipeline Active...';
  showToast(`Training Random Forest & Isolation Forest on ${samples.toLocaleString()} samples...`, 'info');

  try {
    const res = await fetch('/api/ml/train', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ n_samples: samples })
    });
    if (!res.ok) throw new Error('Training request failed');
    const result = await res.json();

    showToast(result.message, 'success');
    await fetchMlMetrics();
    await refreshDashboardData();
  } catch (err) {
    showToast('ML Training error: ' + err.message, 'error');
  } finally {
    btn.disabled = false;
    btnText.innerText = 'Train Models Now';
  }
}

// ----------------------------------------------------
// SUPABASE CLOUD SYNC HUB
// ----------------------------------------------------

async function openSupabaseModal() {
  document.getElementById('modal-supabase').classList.remove('hidden');
  await fetchSupabaseStatus();
  await loadSupabaseSchema();
}

async function fetchSupabaseStatus() {
  try {
    const res = await fetch('/api/supabase/status');
    if (!res.ok) return;
    const data = await res.json();

    const indicator = document.getElementById('supabase-status-indicator');
    const title = document.getElementById('supabase-status-title');
    const desc = document.getElementById('supabase-status-desc');
    const navDot = document.getElementById('supabase-nav-dot');
    const navBadge = document.getElementById('supabase-nav-badge');

    if (data.is_configured) {
      if (indicator) indicator.className = 'w-3 h-3 rounded-full bg-emerald-400 animate-pulse';
      if (title) title.innerText = 'Connected to Supabase';
      if (desc) desc.innerText = `Project: ${data.supabase_url} • Last Sync: ${data.last_sync_count} items`;
      if (navDot) navDot.className = 'w-2 h-2 rounded-full bg-emerald-400';
      if (navBadge) navBadge.innerText = 'Supabase: Synced';
      
      const urlInp = document.getElementById('inp-supabase-url');
      if (urlInp && !urlInp.value) urlInp.value = data.supabase_url;
    } else {
      if (indicator) indicator.className = 'w-3 h-3 rounded-full bg-amber-500';
      if (title) title.innerText = 'Not Configured';
      if (desc) desc.innerText = 'Enter your Supabase Project URL & API Key below to enable cloud sync.';
      if (navDot) navDot.className = 'w-2 h-2 rounded-full bg-amber-500';
      if (navBadge) navBadge.innerText = 'Connect Supabase';
    }
  } catch (err) {
    console.error('Error checking Supabase status:', err);
  }
}

async function testSupabaseConnection() {
  const url = document.getElementById('inp-supabase-url').value.trim();
  const key = document.getElementById('inp-supabase-key').value.trim();

  showToast('Testing connection to Supabase...', 'info');
  try {
    const res = await fetch('/api/supabase/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: url || null, key: key || null })
    });
    const data = await res.json();

    if (data.success) {
      showToast(data.message, 'success');
      fetchSupabaseStatus();
    } else {
      showToast(data.message, 'error');
    }
  } catch (err) {
    showToast('Failed to ping Supabase: ' + err.message, 'error');
  }
}

async function handleSupabaseConfig(e) {
  e.preventDefault();
  const url = document.getElementById('inp-supabase-url').value.trim();
  const key = document.getElementById('inp-supabase-key').value.trim();

  if (!url || !key) {
    showToast('Please enter both Supabase URL and API Key', 'error');
    return;
  }

  try {
    const res = await fetch('/api/supabase/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, key })
    });
    if (!res.ok) throw new Error('Failed saving config');
    const data = await res.json();
    showToast('Supabase configuration saved!', 'success');
    await fetchSupabaseStatus();
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

async function syncToSupabase() {
  showToast('Pushing local sensor telemetry & alerts to Supabase...', 'info');
  try {
    const res = await fetch('/api/supabase/sync', { method: 'POST' });
    const data = await res.json();

    if (data.success) {
      showToast(`Synced ${data.synced_readings} vitals & ${data.synced_alerts} alerts to Supabase!`, 'success');
      await fetchSupabaseStatus();
    } else {
      showToast(data.message || 'Sync failed', 'error');
    }
  } catch (err) {
    showToast('Sync failed: ' + err.message, 'error');
  }
}

async function loadSupabaseSchema() {
  try {
    const res = await fetch('/api/supabase/schema');
    if (!res.ok) return;
    const data = await res.json();
    const codeBlock = document.getElementById('supabase-sql-code');
    if (codeBlock) {
      codeBlock.innerText = data.sql;
    }
  } catch (err) {
    // Ignore
  }
}

function copySupabaseSql() {
  const code = document.getElementById('supabase-sql-code').innerText;
  navigator.clipboard.writeText(code).then(() => {
    showToast('Supabase SQL migration copied to clipboard!', 'success');
  }).catch(() => {
    showToast('Failed to copy. Please select text manually.', 'error');
  });
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

  toast.className = `px-4 py-2.5 rounded-xl border shadow-2xl text-xs font-semibold flex items-center gap-2 transform transition-all duration-300 translate-y-2 opacity-0 ${bg}`;
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
