/* ============================================ */
/*  NotebookLM Toolkit — Frontend JS            */
/* ============================================ */

// ---- State ----
const state = {
  notebooks: [],
  sources: [],
  artifacts: [],
  selectedNotebook: null,
  conversationId: null,
  // Transcriber
  audioPath: null,
  fullText: '',
  chunks: [],
  currentChunk: 0,
  // PDF
  pdfPaths: [],
};

// ---- Helpers ----
async function api(method, url, body = null) {
  const opts = { method, headers: {} };
  if (body && !(body instanceof FormData)) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  } else if (body instanceof FormData) {
    opts.body = body;
  }
  const res = await fetch(url, opts);
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err);
  }
  return res.json();
}

function toast(msg, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  document.getElementById('toast-container').appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

function $(id) { return document.getElementById(id); }

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

// ---- Tab switching ----
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
  });
});

document.querySelectorAll('.sub-tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const parent = btn.parentElement;
    parent.querySelectorAll('.sub-tab-btn').forEach(b => b.classList.remove('active'));
    const panels = parent.parentElement.querySelectorAll('.sub-tab-panel');
    panels.forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('subtab-' + btn.dataset.subtab).classList.add('active');
  });
});

// ---- Health Check ----
async function checkHealth() {
  try {
    const checks = await api('GET', '/api/preflight');
    const banner = $('health-banner');
    banner.innerHTML = checks.map(c =>
      `<div class="health-item">
        <div class="health-dot ${c.status}"></div>
        <span>${c.name}: ${c.detail}</span>
      </div>`
    ).join('');
    banner.classList.remove('hidden');
  } catch (e) {
    toast('Health check failed: ' + e.message, 'error');
  }
}

// Run health check on load
checkHealth();

// ---- Load saved prompts ----
async function loadPrompts() {
  try {
    const prompts = await api('GET', '/api/prompts');
    const sel = $('prompt-select');
    sel.innerHTML = '<option value="">Saved prompts...</option>';
    Object.keys(prompts).filter(k => k !== '__last_used__').sort().forEach(name => {
      const opt = document.createElement('option');
      opt.value = name;
      opt.textContent = name;
      sel.appendChild(opt);
    });
    // Restore last used
    if (prompts.__last_used__) {
      $('gen-instructions').value = prompts.__last_used__;
    }
  } catch (e) { /* ignore */ }
}
loadPrompts();

function loadPrompt() {
  const name = $('prompt-select').value;
  if (!name) return;
  api('GET', '/api/prompts').then(prompts => {
    if (prompts[name]) $('gen-instructions').value = prompts[name];
  });
}

async function savePrompt() {
  const text = $('gen-instructions').value.trim();
  if (!text) return toast('Write instructions first', 'error');
  const name = prompt('Prompt name:');
  if (!name) return;
  await api('POST', '/api/prompts', { name, text });
  toast('Prompt saved', 'success');
  loadPrompts();
}

async function deletePrompt() {
  const name = $('prompt-select').value;
  if (!name) return;
  if (!confirm(`Delete prompt "${name}"?`)) return;
  await api('DELETE', `/api/prompts/${encodeURIComponent(name)}`);
  toast('Prompt deleted', 'success');
  loadPrompts();
}

// ==================================================
//  NotebookLM Tab
// ==================================================

function nlmStatus(msg) { $('nlm-status').textContent = msg; }

async function nlmLogin() {
  nlmStatus('Opening browser — log in to Google...');
  try {
    await api('POST', '/api/nlm/login');
    $('nlm-auth-status').textContent = 'Authenticated';
    $('nlm-auth-status').style.color = 'var(--success)';
    nlmStatus('Login successful! Click List to load notebooks.');
    toast('Login successful', 'success');
  } catch (e) {
    nlmStatus('Login failed: ' + e.message);
    toast('Login failed: ' + e.message, 'error');
  }
}

async function nlmRefresh() {
  await nlmListNotebooks();
}

async function nlmListNotebooks() {
  nlmStatus('Loading notebooks...');
  try {
    state.notebooks = await api('GET', '/api/nlm/notebooks');
    const sel = $('nlm-notebooks');
    sel.innerHTML = '';
    state.notebooks.forEach((nb, i) => {
      const opt = document.createElement('option');
      opt.value = i;
      opt.textContent = `${nb.title}  (${nb.sources_count} sources)`;
      sel.appendChild(opt);
    });
    nlmStatus(`Loaded ${state.notebooks.length} notebooks.`);
  } catch (e) {
    nlmStatus('Error: ' + e.message);
    toast(e.message, 'error');
  }
}

async function nlmCreateNotebook() {
  const title = prompt('Notebook title:');
  if (!title) return;
  nlmStatus(`Creating "${title}"...`);
  try {
    await api('POST', '/api/nlm/notebooks', { title });
    toast('Notebook created', 'success');
    await nlmListNotebooks();
  } catch (e) {
    toast(e.message, 'error');
  }
}

async function nlmDeleteNotebook() {
  const sel = $('nlm-notebooks');
  const idx = sel.selectedIndex;
  if (idx < 0) return;
  const nb = state.notebooks[idx];
  if (!confirm(`Delete "${nb.title}"?`)) return;
  try {
    await api('DELETE', `/api/nlm/notebooks/${nb.id}`);
    toast('Notebook deleted', 'success');
    await nlmListNotebooks();
  } catch (e) { toast(e.message, 'error'); }
}

async function nlmSelectNotebook() {
  const sel = $('nlm-notebooks');
  const idx = sel.selectedIndex;
  if (idx < 0) return;
  state.selectedNotebook = state.notebooks[idx];
  state.conversationId = null;
  await Promise.all([nlmListSources(), nlmListArtifacts()]);
}

async function nlmListSources() {
  if (!state.selectedNotebook) return;
  try {
    state.sources = await api('GET', `/api/nlm/notebooks/${state.selectedNotebook.id}/sources`);
    const sel = $('nlm-sources');
    sel.innerHTML = '';
    state.sources.forEach((s, i) => {
      const opt = document.createElement('option');
      opt.value = i;
      opt.textContent = s.title;
      sel.appendChild(opt);
    });
    nlmStatus(`${state.sources.length} sources loaded.`);
  } catch (e) { nlmStatus('Error: ' + e.message); }
}

async function nlmListArtifacts() {
  if (!state.selectedNotebook) return;
  try {
    state.artifacts = await api('GET', `/api/nlm/notebooks/${state.selectedNotebook.id}/artifacts`);
    const sel = $('nlm-artifacts');
    sel.innerHTML = '';
    state.artifacts.forEach((a, i) => {
      const opt = document.createElement('option');
      opt.value = i;
      opt.textContent = `[${a.kind}] ${a.title}`;
      sel.appendChild(opt);
    });
  } catch (e) { /* ignore */ }
}

async function nlmAddSourceUrl() {
  if (!state.selectedNotebook) return toast('Select a notebook first', 'error');
  const url = prompt('Enter URL (webpage or YouTube):');
  if (!url) return;
  nlmStatus('Adding URL source...');
  try {
    const src = await api('POST', `/api/nlm/notebooks/${state.selectedNotebook.id}/sources/url`, { url });
    toast(`Added: ${src.title}`, 'success');
    await nlmListSources();
  } catch (e) { toast(e.message, 'error'); }
}

function nlmAddSourceFile() {
  if (!state.selectedNotebook) return toast('Select a notebook first', 'error');
  const input = $('nlm-file-input');
  input.onchange = async () => {
    if (!input.files.length) return;
    const fd = new FormData();
    fd.append('file', input.files[0]);
    nlmStatus(`Uploading ${input.files[0].name}...`);
    try {
      const res = await fetch(`/api/nlm/notebooks/${state.selectedNotebook.id}/sources/file`, {
        method: 'POST', body: fd
      });
      if (!res.ok) throw new Error(await res.text());
      const src = await res.json();
      toast(`Added: ${src.title}`, 'success');
      await nlmListSources();
    } catch (e) { toast(e.message, 'error'); }
    input.value = '';
  };
  input.click();
}

async function nlmAddSourceText() {
  if (!state.selectedNotebook) return toast('Select a notebook first', 'error');
  const title = prompt('Source title:');
  if (!title) return;
  const content = prompt('Source content:');
  if (!content) return;
  nlmStatus('Adding text source...');
  try {
    const src = await api('POST', `/api/nlm/notebooks/${state.selectedNotebook.id}/sources/text`, { title, content });
    toast(`Added: ${src.title}`, 'success');
    await nlmListSources();
  } catch (e) { toast(e.message, 'error'); }
}

async function nlmDeleteSource() {
  if (!state.selectedNotebook) return;
  const sel = $('nlm-sources');
  const indices = Array.from(sel.selectedOptions).map(o => parseInt(o.value));
  if (!indices.length) return;
  if (!confirm('Delete selected source(s)?')) return;
  for (const idx of indices) {
    try {
      await api('DELETE', `/api/nlm/notebooks/${state.selectedNotebook.id}/sources/${state.sources[idx].id}`);
    } catch (e) { toast(e.message, 'error'); }
  }
  toast('Source(s) deleted', 'success');
  await nlmListSources();
}

// ---- Generate ----
const PARAM_DEFS = {
  audio: [
    { key: 'audio_format', label: 'Format', options: { 'Deep Dive': 1, 'Brief': 2, 'Critique': 3, 'Debate': 4 } },
    { key: 'audio_length', label: 'Length', options: { 'Short': 1, 'Default': 2, 'Long': 3 } },
  ],
  video: [
    { key: 'video_format', label: 'Format', options: { 'Explainer': 1, 'Brief': 2, 'Cinematic': 3 } },
    { key: 'video_style', label: 'Style', options: { 'Auto Select': 1, 'Custom': 2, 'Classic': 3, 'Whiteboard': 4, 'Kawaii': 5, 'Anime': 6, 'Watercolor': 7, 'Retro Print': 8, 'Heritage': 9, 'Paper Craft': 10 } },
  ],
  report: [
    { key: 'report_format', label: 'Format', options: { 'Briefing Doc': 'briefing_doc', 'Study Guide': 'study_guide', 'Blog Post': 'blog_post', 'Custom': 'custom' } },
  ],
  quiz: [
    { key: 'quantity', label: 'Quantity', options: { 'Fewer': 1, 'Standard': 2 } },
    { key: 'difficulty', label: 'Difficulty', options: { 'Easy': 1, 'Medium': 2, 'Hard': 3 } },
  ],
  flashcards: [
    { key: 'quantity', label: 'Quantity', options: { 'Fewer': 1, 'Standard': 2 } },
    { key: 'difficulty', label: 'Difficulty', options: { 'Easy': 1, 'Medium': 2, 'Hard': 3 } },
  ],
  infographic: [
    { key: 'orientation', label: 'Orientation', options: { 'Landscape': 1, 'Portrait': 2, 'Square': 3 } },
    { key: 'detail_level', label: 'Detail', options: { 'Concise': 1, 'Standard': 2, 'Detailed': 3 } },
    { key: 'style', label: 'Style', options: { 'Auto Select': 1, 'Sketch Note': 2, 'Professional': 3, 'Bento Grid': 4, 'Editorial': 5, 'Instructional': 6, 'Bricks': 7, 'Clay': 8, 'Anime': 9, 'Kawaii': 10, 'Scientific': 11 } },
  ],
  slide_deck: [
    { key: 'slide_format', label: 'Format', options: { 'Detailed Deck': 1, 'Presenter Slides': 2 } },
    { key: 'slide_length', label: 'Length', options: { 'Default': 1, 'Short': 2 } },
  ],
  data_table: [],
  mind_map: [],
};

function onArtifactTypeChange() {
  const type = $('gen-type').value;
  const container = $('gen-params');
  container.innerHTML = '';
  if (!type || !PARAM_DEFS[type]) return;
  PARAM_DEFS[type].forEach(p => {
    const lbl = document.createElement('label');
    lbl.textContent = p.label;
    const sel = document.createElement('select');
    sel.id = 'gen-param-' + p.key;
    Object.entries(p.options).forEach(([name, val]) => {
      const opt = document.createElement('option');
      opt.value = val;
      opt.textContent = name;
      sel.appendChild(opt);
    });
    container.appendChild(lbl);
    container.appendChild(sel);
  });
}

async function nlmGenerate() {
  if (!state.selectedNotebook) return toast('Select a notebook first', 'error');
  const atype = $('gen-type').value;
  if (!atype) return toast('Select an artifact type', 'error');

  const params = { artifact_type: atype };
  if (['audio', 'video', 'report', 'infographic', 'slide_deck', 'data_table'].includes(atype)) {
    params.language = $('gen-language').value;
  }
  const instructions = $('gen-instructions').value.trim();
  if (instructions) {
    params[atype === 'report' ? 'extra_instructions' : 'instructions'] = instructions;
  }
  // Save last used prompt
  api('POST', '/api/prompts', { name: '__last_used__', text: instructions }).catch(() => {});

  // Dynamic params
  (PARAM_DEFS[atype] || []).forEach(p => {
    const el = $('gen-param-' + p.key);
    if (el) params[p.key] = isNaN(Number(el.value)) ? el.value : Number(el.value);
  });

  // Selected source IDs
  const srcSel = $('nlm-sources');
  const srcIds = Array.from(srcSel.selectedOptions).map(o => state.sources[parseInt(o.value)].id);
  if (srcIds.length) params.source_ids = srcIds;

  nlmStatus(`Generating ${atype}... (this may take a while)`);
  try {
    await api('POST', `/api/nlm/notebooks/${state.selectedNotebook.id}/generate`, params);
    toast(`Generated ${atype} successfully!`, 'success');
    nlmStatus(`Generated ${atype}!`);
    await nlmListArtifacts();
  } catch (e) {
    toast('Generation failed: ' + e.message, 'error');
    nlmStatus('Generation failed.');
  }
}

async function nlmDownloadArtifact() {
  if (!state.selectedNotebook) return;
  const sel = $('nlm-artifacts');
  if (sel.selectedIndex < 0) return toast('Select an artifact', 'error');
  const art = state.artifacts[sel.selectedIndex];
  const typeMap = { 1: 'audio', 2: 'report', 3: 'video', 4: 'quiz', 5: 'mind_map', 7: 'infographic', 8: 'slide_deck', 9: 'data_table' };
  const dlType = typeMap[art.type_code] || 'report';
  nlmStatus(`Downloading ${art.title}...`);
  try {
    const res = await fetch(`/api/nlm/notebooks/${state.selectedNotebook.id}/download`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ artifact_type: dlType, artifact_id: art.id })
    });
    if (!res.ok) throw new Error(await res.text());
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = art.title.replace(/[^a-zA-Z0-9 _-]/g, '_') + '.' + (dlType === 'audio' ? 'mp3' : dlType === 'video' ? 'mp4' : 'bin');
    a.click();
    URL.revokeObjectURL(url);
    nlmStatus('Downloaded!');
    toast('Download started', 'success');
  } catch (e) { toast(e.message, 'error'); }
}

async function nlmDeleteArtifact() {
  if (!state.selectedNotebook) return;
  const sel = $('nlm-artifacts');
  if (sel.selectedIndex < 0) return;
  const art = state.artifacts[sel.selectedIndex];
  if (!confirm(`Delete "${art.title}"?`)) return;
  try {
    await api('DELETE', `/api/nlm/notebooks/${state.selectedNotebook.id}/artifacts/${art.id}`);
    toast('Artifact deleted', 'success');
    await nlmListArtifacts();
  } catch (e) { toast(e.message, 'error'); }
}

// ---- Chat ----
async function nlmSetChatMode() {
  if (!state.selectedNotebook) return;
  const mode = $('chat-mode').value;
  try {
    await api('POST', `/api/nlm/notebooks/${state.selectedNotebook.id}/chat/mode`, { mode });
    toast(`Chat mode: ${mode}`, 'success');
  } catch (e) { toast(e.message, 'error'); }
}

async function nlmSendChat() {
  if (!state.selectedNotebook) return toast('Select a notebook first', 'error');
  const input = $('chat-input');
  const q = input.value.trim();
  if (!q) return;
  input.value = '';

  appendChat('You', q, 'user');
  nlmStatus('Thinking...');

  const srcSel = $('nlm-sources');
  const srcIds = Array.from(srcSel.selectedOptions).map(o => state.sources[parseInt(o.value)].id);

  try {
    const res = await api('POST', `/api/nlm/notebooks/${state.selectedNotebook.id}/chat`, {
      question: q,
      source_ids: srcIds.length ? srcIds : null,
      conversation_id: state.conversationId,
    });
    state.conversationId = res.conversation_id;
    let answer = res.answer;
    if (res.references && res.references.length) {
      answer += '\n\nReferences:';
      res.references.forEach(r => {
        answer += `\n  [${r.citation_number || '?'}] ${r.cited_text}`;
      });
    }
    appendChat('NotebookLM', answer, 'bot');
    nlmStatus('Response received.');
  } catch (e) {
    appendChat('Error', e.message, 'bot');
    nlmStatus('Chat error.');
  }
}

function appendChat(sender, text, cls) {
  const container = $('chat-messages');
  const div = document.createElement('div');
  div.className = `chat-msg ${cls}`;
  div.innerHTML = `<div class="sender">${sender}</div><div>${text.replace(/\n/g, '<br>')}</div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

// ==================================================
//  Audio Transcriber Tab
// ==================================================

// Upload zone
const audioZone = $('audio-upload-zone');
const audioInput = $('audio-file-input');

audioZone.addEventListener('click', () => audioInput.click());
audioZone.addEventListener('dragover', e => { e.preventDefault(); audioZone.classList.add('dragover'); });
audioZone.addEventListener('dragleave', () => audioZone.classList.remove('dragover'));
audioZone.addEventListener('drop', e => {
  e.preventDefault();
  audioZone.classList.remove('dragover');
  if (e.dataTransfer.files.length) handleAudioFile(e.dataTransfer.files[0]);
});
audioInput.addEventListener('change', () => {
  if (audioInput.files.length) handleAudioFile(audioInput.files[0]);
});

async function handleAudioFile(file) {
  const fd = new FormData();
  fd.append('file', file);
  $('audio-file-info').textContent = `Uploading ${file.name}...`;
  $('audio-file-info').classList.remove('hidden');
  try {
    const res = await fetch('/api/transcribe/upload', { method: 'POST', body: fd });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    state.audioPath = data.path;
    $('audio-file-info').textContent = `${data.name} (${formatSize(data.size)})`;
    $('transcribe-btn').disabled = false;
    toast('Audio uploaded', 'success');
  } catch (e) {
    toast('Upload failed: ' + e.message, 'error');
  }
}

async function startTranscription() {
  if (!state.audioPath) return;
  $('transcribe-btn').disabled = true;
  $('transcribe-status').textContent = 'Starting transcription...';
  $('transcribe-progress').classList.remove('hidden');
  $('transcript-card').style.display = 'none';
  $('split-card').style.display = 'none';

  try {
    const res = await api('POST', '/api/transcribe/start', {
      path: state.audioPath,
      model: $('whisper-model').value,
      language: $('whisper-language').value,
    });
    pollTranscription(res.job_id);
  } catch (e) {
    toast('Transcription error: ' + e.message, 'error');
    $('transcribe-btn').disabled = false;
    $('transcribe-progress').classList.add('hidden');
  }
}

function pollTranscription(jobId) {
  const poll = setInterval(async () => {
    try {
      const s = await api('GET', `/api/transcribe/status/${jobId}`);
      $('transcribe-status').textContent = s.message || '';

      if (s.status === 'done') {
        clearInterval(poll);
        $('transcribe-progress').classList.add('hidden');
        $('transcribe-btn').disabled = false;
        state.fullText = s.text;
        state.chunks = [s.text];
        state.currentChunk = 0;
        showTranscript();
        toast('Transcription complete!', 'success');
      } else if (s.status === 'error') {
        clearInterval(poll);
        $('transcribe-progress').classList.add('hidden');
        $('transcribe-btn').disabled = false;
        toast('Error: ' + s.message, 'error');
      }
    } catch (e) {
      clearInterval(poll);
      toast('Poll error', 'error');
    }
  }, 2000);
}

function showTranscript() {
  $('transcript-card').style.display = '';
  $('split-card').style.display = '';
  $('split-info').textContent = `Total: ${state.fullText.length} chars`;
  showChunk(0);
}

function showChunk(idx) {
  idx = Math.max(0, Math.min(idx, state.chunks.length - 1));
  state.currentChunk = idx;
  $('transcript-output').value = state.chunks[idx];
  if (state.chunks.length > 1) {
    $('chunk-label').textContent = `Part ${idx + 1}/${state.chunks.length} (${state.chunks[idx].length} chars)`;
    $('prev-chunk-btn').disabled = idx === 0;
    $('next-chunk-btn').disabled = idx === state.chunks.length - 1;
  } else {
    $('chunk-label').textContent = `${state.chunks[0].length} chars`;
    $('prev-chunk-btn').disabled = true;
    $('next-chunk-btn').disabled = true;
  }
}

function prevChunk() { showChunk(state.currentChunk - 1); }
function nextChunk() { showChunk(state.currentChunk + 1); }

function copyChunk() {
  navigator.clipboard.writeText(state.chunks[state.currentChunk]);
  toast('Chunk copied', 'success');
}
function copyAll() {
  navigator.clipboard.writeText(state.fullText);
  toast('Full text copied', 'success');
}

async function applySplit() {
  const parts = parseInt($('split-parts').value) || 1;
  const overlap = parseInt($('split-overlap').value) || 0;
  if (parts <= 1) {
    state.chunks = [state.fullText];
  } else {
    try {
      const res = await api('POST', '/api/transcribe/split', {
        text: state.fullText, num_parts: parts, overlap
      });
      state.chunks = res.chunks;
    } catch (e) { toast(e.message, 'error'); return; }
  }
  $('split-info').textContent = `Total: ${state.fullText.length} chars | ${state.chunks.length} parts` +
    (overlap > 0 && parts > 1 ? `, ${overlap}-char overlap` : '');
  showChunk(0);
}

// ==================================================
//  PDF Cleaner Tab
// ==================================================

const pdfZone = $('pdf-upload-zone');
const pdfInput = $('pdf-file-input');

pdfZone.addEventListener('click', () => pdfInput.click());
pdfZone.addEventListener('dragover', e => { e.preventDefault(); pdfZone.classList.add('dragover'); });
pdfZone.addEventListener('dragleave', () => pdfZone.classList.remove('dragover'));
pdfZone.addEventListener('drop', e => {
  e.preventDefault();
  pdfZone.classList.remove('dragover');
  if (e.dataTransfer.files.length) handlePdfFiles(e.dataTransfer.files);
});
pdfInput.addEventListener('change', () => {
  if (pdfInput.files.length) handlePdfFiles(pdfInput.files);
});

async function handlePdfFiles(files) {
  const fd = new FormData();
  Array.from(files).forEach(f => fd.append('files', f));
  try {
    const res = await fetch('/api/pdf/upload', { method: 'POST', body: fd });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    state.pdfPaths = data.map(d => d.path);
    const list = $('pdf-file-list');
    list.innerHTML = data.map(d =>
      `<div class="file-item"><span class="name">${d.name}</span><span class="size">${formatSize(d.size)}</span></div>`
    ).join('');
    $('pdf-process-btn').disabled = false;
    toast(`${data.length} PDF(s) uploaded`, 'success');
  } catch (e) { toast(e.message, 'error'); }
}

async function startPdfProcess() {
  if (!state.pdfPaths.length) return;
  $('pdf-process-btn').disabled = true;
  $('pdf-progress-card').style.display = '';
  $('pdf-status').textContent = 'Starting...';
  $('pdf-progress-fill').style.width = '0%';

  try {
    const res = await api('POST', '/api/pdf/process', {
      paths: state.pdfPaths,
      resolution: parseInt($('pdf-resolution').value),
      supersample: parseInt($('pdf-supersample').value),
      sharpness: parseFloat($('pdf-sharpness').value),
    });
    pollPdf(res.job_id);
  } catch (e) {
    toast(e.message, 'error');
    $('pdf-process-btn').disabled = false;
  }
}

function pollPdf(jobId) {
  const poll = setInterval(async () => {
    try {
      const s = await api('GET', `/api/pdf/status/${jobId}`);
      $('pdf-status').textContent = s.message || '';
      if (s.total > 0) {
        $('pdf-progress-fill').style.width = `${(s.progress / s.total * 100).toFixed(1)}%`;
      }
      if (s.status === 'done') {
        clearInterval(poll);
        $('pdf-process-btn').disabled = false;
        toast(`Done! ${s.success} pages exported.`, 'success');
      }
    } catch (e) {
      clearInterval(poll);
    }
  }, 1500);
}
