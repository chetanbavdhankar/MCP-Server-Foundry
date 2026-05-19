/* ============================================================
   MCP Server Foundry — Frontend Logic
   State machine: IDLE → FILE_LOADED → SPEC_GENERATED → FORGING → SERVER_READY
   ============================================================ */

// ---- State ----
let appState = 'IDLE';
let forgePoller = null;
let specContent = '';
let serverPath = '';
let connectionConfig = {};

// ---- Helpers ----
function $(id) { return document.getElementById(id); }
function show(id) { $(id).classList.remove('hidden'); }
function hide(id) { $(id).classList.add('hidden'); }

function toast(msg, type = 'success') {
  const t = $('toast');
  t.textContent = msg;
  t.className = `toast ${type}`;
  t.classList.remove('hidden');
  setTimeout(() => t.classList.add('hidden'), 3000);
}

async function api(path, opts = {}) {
  const resp = await fetch(path, opts);
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.error || `HTTP ${resp.status}`);
  return data;
}

// ---- Tab Switching ----
function switchTab(tab) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  document.querySelectorAll('.page').forEach(p => p.classList.toggle('active', p.id === `page-${tab}`));
  if (tab === 'chat') loadOllamaModels();
}

// ---- File Upload ----
const dropZone = $('drop-zone');
const fileInput = $('file-input');

dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  fileInput.files = e.dataTransfer.files;
  uploadFiles(e.dataTransfer.files);
});
fileInput.addEventListener('change', () => uploadFiles(fileInput.files));

async function uploadFiles(files) {
  if (!files.length) return;
  const fd = new FormData();
  for (const f of files) fd.append('files', f);

  dropZone.querySelector('.dz-text').textContent = 'Uploading...';
  try {
    const data = await api('/api/upload', { method: 'POST', body: fd });
    renderFileInfo(data, files);
    appState = 'FILE_LOADED';
    toast(`${data.file_count} file(s) loaded — ${data.row_count} rows`);
  } catch (e) {
    toast(e.message, 'error');
    dropZone.querySelector('.dz-text').textContent = 'Drop CSV, XLSX, or JSON here — or click to browse';
  }
}

function renderFileInfo(data, files) {
  const names = Array.from(files).map(f => f.name).join(', ');
  dropZone.querySelector('.dz-text').textContent = names;
  dropZone.querySelector('.dz-sub').textContent = '✓ Loaded';

  let html = `
    <div class="file-info">
      <div class="file-stat"><div class="val">${data.file_count}</div><div class="lbl">Files</div></div>
      <div class="file-stat"><div class="val">${data.row_count}</div><div class="lbl">Rows</div></div>
      <div class="file-stat"><div class="val">${data.columns.length}</div><div class="lbl">Columns</div></div>
      <div class="file-stat"><div class="val">${data.file_size_kb} KB</div><div class="lbl">Size</div></div>
    </div>
    <table class="col-table">
      <tr><th>Column</th><th>Type</th><th>Sample</th></tr>
      ${data.columns.map(c => `<tr><td>${esc(c.name)}</td><td><span class="type-badge">${c.type}</span></td><td style="color:var(--text-dim);font-size:0.78rem">${esc(c.sample)}</td></tr>`).join('')}
    </table>
    <div class="input-row">
      <input class="input-field" id="api-title" placeholder="API Title (e.g. Home Cooking API)" value="My Dataset">
      <button class="btn" onclick="generateSpec()">⚡ Generate Spec</button>
    </div>`;

  $('file-info-area').innerHTML = html;
  show('file-info-area');
}

// ---- Spec Generation ----
async function generateSpec() {
  const title = $('api-title').value || 'My Dataset';
  try {
    const data = await api('/api/spec', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title })
    });
    specContent = data.content;
    $('spec-content').textContent = data.content;
    show('panel-spec');
    $('panel-spec').scrollIntoView({ behavior: 'smooth' });
    appState = 'SPEC_GENERATED';
    toast('OpenAPI spec generated');
  } catch (e) {
    toast(e.message, 'error');
  }
}

function copySpec() {
  navigator.clipboard.writeText(specContent);
  toast('YAML copied to clipboard');
}

function downloadSpec() {
  downloadText(specContent, 'openapi_spec.yaml', 'text/yaml');
}

// ---- Forge ----
async function startForge() {
  $('btn-forge').disabled = true;
  try {
    await api('/api/forge', { method: 'POST' });
    show('panel-forge');
    $('panel-forge').scrollIntoView({ behavior: 'smooth' });
    appState = 'FORGING';
    forgePoller = setInterval(pollForge, 1500);
  } catch (e) {
    toast(e.message, 'error');
    $('btn-forge').disabled = false;
  }
}

async function pollForge() {
  try {
    const data = await api('/api/forge-status');
    $('progress-fill').style.width = data.progress + '%';
    $('log-viewer').textContent = data.logs.join('\n');
    $('log-viewer').scrollTop = $('log-viewer').scrollHeight;

    // Update agent steps
    const steps = document.querySelectorAll('.agent-step');
    const agents = ['architect', 'builder', 'tester', 'documenter'];
    const thresholds = [25, 50, 75, 95];
    agents.forEach((name, i) => {
      const el = steps[i];
      if (data.progress >= thresholds[i]) {
        el.className = 'agent-step done';
        el.textContent = `✅ ${name.charAt(0).toUpperCase() + name.slice(1)} — complete`;
      } else if (data.progress >= (thresholds[i] - 24)) {
        el.className = 'agent-step active';
        el.textContent = `⏳ ${name.charAt(0).toUpperCase() + name.slice(1)} — processing...`;
      }
    });

    if (data.status === 'complete') {
      clearInterval(forgePoller);
      forgePoller = null;
      serverPath = data.server_main_path;
      appState = 'SERVER_READY';
      toast('MCP server forged successfully!');
      loadServerInfo();
    } else if (data.status === 'error') {
      clearInterval(forgePoller);
      forgePoller = null;
      toast(data.error || 'Forge failed', 'error');
      $('btn-forge').disabled = false;
    }
  } catch (e) {
    // Keep polling on transient errors
  }
}

// ---- Server Info ----
async function loadServerInfo() {
  try {
    const data = await api('/api/server/info');
    connectionConfig = data.connection_config || {};
    serverPath = data.server_path || '';

    // Tools
    if (data.tools && data.tools.length) {
      let html = '<div style="font-size:0.8rem;margin-bottom:0.5rem;color:var(--accent)">Available Tools:</div>';
      data.tools.forEach(t => {
        html += `<div style="padding:0.3rem 0;font-size:0.8rem">• <strong>${esc(t.name)}</strong> — ${esc(t.description)}</div>`;
      });
      $('tools-area').innerHTML = html;
    }

    // Config block
    $('config-block').textContent = JSON.stringify(connectionConfig, null, 2);

    // Status
    const badge = $('server-badge');
    if (data.status === 'running') {
      badge.className = 'status-badge running';
      badge.innerHTML = '<span class="status-dot"></span> RUNNING';
      $('server-pid').textContent = data.pid ? `PID: ${data.pid}` : '';
      show('btn-stop'); hide('btn-start');
    } else {
      badge.className = 'status-badge stopped';
      badge.innerHTML = '<span class="status-dot"></span> STOPPED';
      $('server-pid').textContent = '';
      hide('btn-stop'); show('btn-start');
    }

    // Terminal command
    if (data.terminal_command) {
      $('terminal-cmd').innerHTML = `<strong>Terminal:</strong> <code style="color:var(--accent)">${esc(data.terminal_command)}</code>`;
    }

    show('panel-server');
    $('panel-server').scrollIntoView({ behavior: 'smooth' });

    // Enable chat tab
    $('chat-server-name').textContent = connectionConfig?.mcpServers ? Object.keys(connectionConfig.mcpServers)[0] : 'Connected';

  } catch (e) {
    toast(e.message, 'error');
  }
}

async function stopServer() {
  try {
    await api('/api/server/stop', { method: 'POST' });
    toast('Server stopped');
    loadServerInfo();
  } catch (e) { toast(e.message, 'error'); }
}

async function startServer() {
  try {
    await api('/api/server/start', { method: 'POST' });
    toast('Server started');
    loadServerInfo();
  } catch (e) { toast(e.message, 'error'); }
}

function copyConfig() {
  navigator.clipboard.writeText(JSON.stringify(connectionConfig, null, 2));
  toast('Config copied');
}

function downloadConfig() {
  downloadText(JSON.stringify(connectionConfig, null, 2), 'mcp_config.json', 'application/json');
}

function copyPath() {
  navigator.clipboard.writeText(serverPath);
  toast('Path copied');
}

// ---- Reset ----
async function resetAll() {
  if (!confirm('This will stop the server and clear all data. Continue?')) return;
  try {
    await api('/api/reset', { method: 'POST' });
    // Reset UI
    if (forgePoller) clearInterval(forgePoller);
    hide('file-info-area'); hide('panel-spec'); hide('panel-forge'); hide('panel-server');
    $('file-info-area').innerHTML = '';
    $('spec-content').textContent = '';
    $('log-viewer').textContent = '';
    $('progress-fill').style.width = '0%';
    $('btn-forge').disabled = false;
    $('chat-messages').innerHTML = '<div class="chat-msg bot">Welcome! I\'m connected to your MCP server. Ask me anything about your data.</div>';
    dropZone.querySelector('.dz-text').textContent = 'Drop CSV, XLSX, or JSON here — or click to browse';
    dropZone.querySelector('.dz-sub').textContent = 'Multiple files accepted (same columns required)';
    document.querySelectorAll('.agent-step').forEach((el, i) => {
      const names = ['Architect — parsing spec', 'Builder — generating server', 'Tester — adversarial suite', 'Documenter — docs & scripts'];
      el.className = 'agent-step pending';
      el.textContent = `○ ${names[i]}`;
    });
    fileInput.value = '';
    specContent = ''; serverPath = ''; connectionConfig = {};
    appState = 'IDLE';
    switchTab('forge');
    toast('Reset complete');
  } catch (e) { toast(e.message, 'error'); }
}

// ---- Chat ----
async function loadOllamaModels() {
  try {
    const data = await api('/api/ollama/models');
    const sel = $('ollama-model');
    sel.innerHTML = '';
    if (data.models.length) {
      data.models.forEach(m => { const o = document.createElement('option'); o.value = m; o.textContent = m; sel.appendChild(o); });
    } else {
      sel.innerHTML = '<option value="">No models found</option>';
    }
  } catch (e) {
    $('ollama-model').innerHTML = '<option value="">Ollama offline</option>';
  }
}

function onProviderChange() {
  const v = $('llm-provider').value;
  if (v === 'ollama') { show('ollama-config'); hide('api-config'); loadOllamaModels(); }
  else { hide('ollama-config'); show('api-config'); }
}

async function sendChat() {
  const input = $('chat-input');
  const msg = input.value.trim();
  if (!msg) return;
  input.value = '';

  appendChat(msg, 'user');

  const provider = $('llm-provider').value;
  const body = { message: msg, provider };
  if (provider === 'ollama') {
    body.model = $('ollama-model').value;
  } else {
    body.model = $('api-model').value;
    body.api_key = $('api-key').value;
  }

  // Show spinner
  const spinnerId = 'spin-' + Date.now();
  appendChat('<span class="spinner"></span> Thinking...', 'bot', spinnerId);

  try {
    const data = await api('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });

    // Remove spinner
    const spinEl = document.getElementById(spinnerId);
    if (spinEl) spinEl.remove();

    if (data.tool_call) {
      appendChat(`🔧 Tool: ${data.tool_call.name}\n   Args: ${JSON.stringify(data.tool_call.args)}`, 'tool');
    }
    appendChat(data.reply || data.error || 'No response', 'bot');
  } catch (e) {
    const spinEl = document.getElementById(spinnerId);
    if (spinEl) spinEl.remove();
    appendChat(`Error: ${e.message}`, 'bot');
  }
}

function appendChat(text, role, id) {
  const div = document.createElement('div');
  div.className = `chat-msg ${role}`;
  if (id) div.id = id;
  div.innerHTML = text.replace(/\n/g, '<br>');
  $('chat-messages').appendChild(div);
  $('chat-messages').scrollTop = $('chat-messages').scrollHeight;
}

// ---- Utilities ----
function esc(s) {
  const d = document.createElement('div');
  d.textContent = s || '';
  return d.innerHTML;
}

function downloadText(content, name, mime) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([content], { type: mime }));
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

// ---- Init ----
loadOllamaModels();
