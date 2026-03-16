/* attendance.js – handles webcam capture and face recognition polling */

let stream = null;
let scanning = false;
let scanInterval = null;
const SCAN_INTERVAL_MS = 2500;

const video      = document.getElementById('video');
const canvas     = document.getElementById('canvas');
const statusBox  = document.getElementById('statusBox');
const logList    = document.getElementById('logList');
const logEmpty   = document.getElementById('logEmpty');
const startBtn   = document.getElementById('startBtn');
const scanBtn    = document.getElementById('scanBtn');
const stopCamBtn = document.getElementById('stopCamBtn');
const videoWrap  = document.getElementById('videoWrapper');

// ── Camera controls ──

async function startCamera() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: true });
    video.srcObject = stream;
    scanBtn.disabled = false;
    stopCamBtn.disabled = false;
    startBtn.disabled = true;
    setStatus('<i class="bi bi-camera-fill me-2"></i>Camera ready. Press <strong>Start Scanning</strong> to begin.', 'info');
  } catch (e) {
    setStatus('<i class="bi bi-x-circle-fill me-2"></i>Camera error: ' + e.message, 'danger');
    showToast('Camera error: ' + e.message, 'danger');
  }
}

function stopCamera() {
  stopScan();
  if (stream) {
    stream.getTracks().forEach(t => t.stop());
    stream = null;
  }
  video.srcObject = null;
  startBtn.disabled = false;
  scanBtn.disabled = true;
  stopCamBtn.disabled = true;
  setStatus('<i class="bi bi-stop-circle me-2"></i>Camera stopped.', 'secondary');
}

// ── Scan toggle ──

function toggleScan() {
  scanning ? stopScan() : startScan();
}

function startScan() {
  scanning = true;
  scanBtn.innerHTML = '<i class="bi bi-pause-circle me-1"></i>Pause';
  scanBtn.classList.replace('btn-success', 'btn-warning');
  if (videoWrap) videoWrap.classList.add('scanning');

  const badge = document.getElementById('scanBadge');
  if (badge) {
    badge.className = 'badge badge-success';
    badge.style.fontSize = '.72rem';
    badge.style.padding = '.35rem .7rem';
    badge.innerHTML = '<i class="bi bi-circle-fill me-1" style="font-size:.4rem;"></i>Scanning';
  }

  const scanStat = document.getElementById('scanStatus');
  if (scanStat) { scanStat.textContent = 'LIVE'; scanStat.style.color = 'var(--success-fg)'; }

  setStatus('<div class="spinner-border spinner-border-sm me-2"></div>Scanning for faces…', 'light');
  captureAndRecognize();
  scanInterval = setInterval(captureAndRecognize, SCAN_INTERVAL_MS);
}

function stopScan() {
  scanning = false;
  clearInterval(scanInterval);
  scanInterval = null;
  scanBtn.innerHTML = '<i class="bi bi-play-circle me-1"></i>Start Scanning';
  scanBtn.classList.replace('btn-warning', 'btn-success');
  if (videoWrap) videoWrap.classList.remove('scanning');

  const badge = document.getElementById('scanBadge');
  if (badge) {
    badge.className = 'badge badge-subtle';
    badge.style.fontSize = '.72rem';
    badge.style.padding = '.35rem .7rem';
    badge.innerHTML = '<i class="bi bi-circle-fill me-1" style="font-size:.4rem;"></i>Idle';
  }

  const scanStat2 = document.getElementById('scanStatus');
  if (scanStat2) { scanStat2.textContent = 'OFF'; scanStat2.style.color = ''; }

  if (stream) setStatus('<i class="bi bi-pause-circle me-2"></i>Paused. Press <strong>Start Scanning</strong> to resume.', 'info');
}

// ── Recognition ──

async function captureAndRecognize() {
  if (!stream || !video.videoWidth) return;

  canvas.width  = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext('2d').drawImage(video, 0, 0);
  const imageData = canvas.toDataURL('image/jpeg', 0.85);

  let result;
  try {
    const resp = await fetch('/api/recognize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image: imageData }),
    });
    result = await resp.json();
  } catch (e) {
    setStatus('<i class="bi bi-wifi-off me-2"></i>Network error: ' + e.message, 'danger');
    return;
  }

  if (!result.success) {
    setStatus('<i class="bi bi-exclamation-circle me-1"></i>' + result.error, 'warning');
    return;
  }

  const conf = (result.score * 100).toFixed(1);

  if (result.already_marked) {
    setStatus(
      `<i class="bi bi-info-circle-fill me-2"></i><strong>${result.name}</strong> already marked today <span class="badge badge-info ms-2" style="font-size:.75rem;">${conf}%</span>`,
      'light'
    );
    showToast(`${result.name} already marked today`, 'info');
  } else {
    const statusBadge = getStatusBadge(result.status);
    setStatus(
      `<i class="bi bi-check-circle-fill me-2"></i><strong>${result.name}</strong> marked present! ${statusBadge} <span class="badge badge-success ms-1" style="font-size:.75rem;">${conf}%</span>`,
      result.status === 'on_time' ? 'success' : result.status === 'late' ? 'warning' : 'danger'
    );
    const statusLabel = result.status === 'on_time' ? 'On Time' : result.status === 'late' ? 'Late' : 'Overtime';
    showToast(`${result.name} – ${statusLabel} (${conf}%)`, result.status === 'on_time' ? 'success' : result.status === 'late' ? 'warning' : 'danger');
    addLog(result.name, conf, result.status, result.check_in_time);
  }
}

// ── Helpers ──

function getStatusBadge(status) {
  if (status === 'on_time') return `<span class="badge ms-1" style="background:rgba(63,185,80,.15);color:var(--success-fg);border:1px solid rgba(63,185,80,.3);font-size:.72rem;">On Time</span>`;
  if (status === 'late')    return `<span class="badge ms-1" style="background:rgba(210,153,34,.15);color:var(--warning-fg);border:1px solid rgba(210,153,34,.3);font-size:.72rem;"><i class="bi bi-clock-fill me-1"></i>Late</span>`;
  if (status === 'overtime') return `<span class="badge ms-1" style="background:rgba(248,81,73,.12);color:var(--danger-fg);border:1px solid rgba(248,81,73,.3);font-size:.72rem;"><i class="bi bi-lightning-fill me-1"></i>Overtime</span>`;
  return '';
}

function setStatus(html, type) {
  statusBox.className = `status-box d-flex align-items-center justify-content-center p-3 alert alert-${type} mb-0`;
  statusBox.innerHTML = html;
}

function addLog(name, conf, status, checkInTime) {
  if (logEmpty) logEmpty.style.display = 'none';

  const now = checkInTime || new Date().toLocaleTimeString();
  const li = document.createElement('li');
  li.className = 'list-group-item d-flex justify-content-between align-items-center';
  li.innerHTML = `
    <span class="d-flex align-items-center gap-2">
      <span class="avatar-circle ${status === 'on_time' ? 'avatar-success' : status === 'late' ? 'avatar-warning' : 'avatar-danger'}">${name[0].toUpperCase()}</span>
      <div>
        <strong>${name}</strong>
        ${getStatusBadge(status)}
      </div>
    </span>
    <span style="color:var(--text-muted);font-size:.8rem;">${now}</span>
  `;
  logList.prepend(li);
  const countEl = document.getElementById('logCount');
  if (countEl) countEl.textContent = logList.children.length + ' checked in';
}
