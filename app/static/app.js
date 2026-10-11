'use strict';

const API = '/api/v1';
const DEFAULT_RETRY_SECONDS = 2;
const MAX_POLL_ATTEMPTS = 300;
const PAGE_SIZE = 50;
const PREVIEW_LIMIT = 5;
const LARGE_BATCH_WARN = 3000;
const BIG_INPUT_CHARS = 1500; // show a loading skeleton above this size
const SKELETON_ROWS = 8;

// Set to false if your API does not accept a top-level "design" object yet.
const SEND_DESIGN = true;
const DESIGN_KEY = 'certgen.design.v1';

const TEMPLATES = [
  { id: 'classic', name: 'Classic', note: 'Gold double border' },
  { id: 'modern', name: 'Modern', note: 'Left accent band' },
  { id: 'royal', name: 'Royal', note: 'Navy and gold' },
  { id: 'minimal', name: 'Minimal', note: 'Clean and quiet' },
  { id: 'bold', name: 'Bold', note: 'Colour header' },
  { id: 'emerald', name: 'Emerald', note: 'Green frame' },
];

const SERIF = 'Georgia, "Times New Roman", serif';
const SANS = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
const FONTS = [
  { id: 'classic', name: 'Classic serif', body: 'Fraunces', bodyStack: `"Fraunces", ${SERIF}`, nameFont: 'Fraunces', nameStack: `"Fraunces", ${SERIF}`, nameStyle: 'italic', nameBoost: 1 },
  { id: 'elegant', name: 'Elegant script', body: 'Cormorant Garamond', bodyStack: `"Cormorant Garamond", ${SERIF}`, nameFont: 'Great Vibes', nameStack: '"Great Vibes", "Snell Roundhand", cursive', nameStyle: 'normal', nameBoost: 1.35 },
  { id: 'editorial', name: 'Editorial', body: 'Playfair Display', bodyStack: `"Playfair Display", ${SERIF}`, nameFont: 'Playfair Display', nameStack: `"Playfair Display", ${SERIF}`, nameStyle: 'italic', nameBoost: 0.95 },
  { id: 'modern', name: 'Modern sans', body: 'Plus Jakarta Sans', bodyStack: `"Plus Jakarta Sans", ${SANS}`, nameFont: 'Plus Jakarta Sans', nameStack: `"Plus Jakarta Sans", ${SANS}`, nameStyle: 'normal', nameBoost: 0.92 },
  { id: 'geometric', name: 'Geometric', body: 'Montserrat', bodyStack: `"Montserrat", ${SANS}`, nameFont: 'Montserrat', nameStack: `"Montserrat", ${SANS}`, nameStyle: 'normal', nameBoost: 0.88 },
];

const SIZE_PRESETS = [
  { id: 'small', label: 'Small', text: 90, name: 90 },
  { id: 'medium', label: 'Medium', text: 100, name: 100 },
  { id: 'large', label: 'Large', text: 110, name: 115 },
];

const DEFAULT_DESIGN = { template: 'classic', font: 'classic', textScale: 100, nameScale: 100 };

let recipients = [];
let activeTab = 'table';
let draftRows = [{ name: '', email: '' }];
let currentJob = null;
let allResults = [];
let filterStatus = 'all';
let searchQuery = '';
let currentPage = 1;
let pollTimerId = null;
let pollToken = 0; // invalidates in-flight polls when a new job starts
let polling = false;
let fileRecipients = null;
let previewIndex = 0;
let designTouched = false;
let design = loadDesign();

const $ = (id) => document.getElementById(id);

const tabButtons = document.querySelectorAll('.tab');
const tabPanels = document.querySelectorAll('.tab-panel');
const draftBody = $('draft-body');
const btnAddRow = $('btn-add-row');
const btnAdd10 = $('btn-add-10');
const btnClearTable = $('btn-clear-table');
const pasteArea = $('paste-area');
const btnLoadSample = $('btn-load-sample');
const btnLoadLarge = $('btn-load-large');
const btnClearPaste = $('btn-clear-paste');
const jsonArea = $('json-area');
const btnLoadJsonSample = $('btn-load-json-sample');
const btnClearJson = $('btn-clear-json');
const fileInput = $('file-input');
const dropzone = $('dropzone');
const dropzoneText = $('dropzone-text');
const btnDownloadTpl = $('btn-download-template');
const btnClearFile = $('btn-clear-file');
const previewEl = $('preview');
const previewIcon = previewEl.querySelector('.preview-icon');
const previewText = previewEl.querySelector('.preview-text');

const courseNameEl = $('course-name');
const issueDateEl = $('issue-date');
const instructorEl = $('instructor');
const certTitleEl = $('cert-title');
const reviewSummaryEl = $('review-summary');
const reviewTable = $('review-table');
const reviewBody = $('review-body');
const reviewMore = $('review-more');
const estimateEl = $('estimate');
const apiKeyEl = $('api-key');
const submitBtn = $('btn-submit');
const submitLabel = submitBtn.querySelector('.label');
const formErrorEl = $('form-error');

const stepResults = $('step-results');
const statusBadgeEl = $('status-badge');
const jobIdRow = $('job-id-row');
const jobIdText = $('job-id-text');
const btnCopyJobId = $('btn-copy-job-id');
const progressWrap = $('progress-wrap');
const progressBar = $('progress-bar');
const progressFill = $('progress-fill');
const progressLabel = $('progress-label');
const countsEl = $('counts');
const actionsRow = $('actions-row');
const btnDownloadZip = $('btn-download-zip');
const btnDownloadCsv = $('btn-download-csv');
const btnRetry = $('btn-retry');
const filtersEl = $('filters');
const filterChips = document.querySelectorAll('.chip');
const searchEl = $('search');
const resultsTable = $('results-table');
const resultsBody = $('results-body');
const paginationEl = $('pagination');
const pageInfoEl = $('page-info');
const btnPagePrev = $('btn-page-prev');
const btnPageNext = $('btn-page-next');
const resultRowTpl = $('result-row-tpl');
const skeletonRowTpl = $('skeleton-row-tpl');
const reviewSkelTpl = $('review-skeleton-tpl');

const certCard = $('cert-card');
const certTitleOut = $('cert-title-out');
const certName = $('cert-name');
const certCourse = $('cert-course');
const certDate = $('cert-date');
const certInstructor = $('cert-instructor');
const certPrev = $('cert-prev');
const certNext = $('cert-next');
const certCounter = $('cert-counter');
const sideRecipients = $('side-recipients');
const sideEstimate = $('side-estimate');
const toastsEl = $('toasts');

const certPreviewEl = $('cert-preview');
const tplGrid = $('tpl-grid');
const fontGrid = $('font-grid');
const sizePresetsEl = $('size-presets');
const textScaleEl = $('text-scale');
const nameScaleEl = $('name-scale');
const textScaleOut = $('text-scale-out');
const nameScaleOut = $('name-scale-out');
const btnResetDesign = $('btn-reset-design');
const designSummaryEl = $('design-summary');

/* ---------- Small helpers ---------- */

const prefersReducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function shimmer(cls) {
  const s = document.createElement('span');
  s.className = `shimmer ${cls}`;
  return s;
}

function toast(message, kind = 'info', ms = 4200) {
  while (toastsEl.children.length >= 4) toastsEl.firstElementChild.remove();

  const el = document.createElement('div');
  el.className = `toast toast-${kind}`;
  el.setAttribute('role', kind === 'error' ? 'alert' : 'status');
  el.innerHTML = '<span class="toast-dot"></span><span class="toast-text"></span>';
  el.querySelector('.toast-text').textContent = message;
  toastsEl.appendChild(el);

  setTimeout(() => {
    el.classList.add('leaving');
    setTimeout(() => el.remove(), 220);
  }, ms);
}

function setBadge(el, status) {
  [...el.classList].forEach((c) => {
    if (c.startsWith('badge-')) el.classList.remove(c);
  });

  const raw = String(status || 'idle').toLowerCase();
  el.classList.add('badge-' + raw);
  el.textContent = raw.replace(/_/g, ' ');
}

function setPreview(kind, icon, text) {
  previewEl.classList.remove('good', 'warn', 'busy');
  previewEl.classList.add(kind);
  previewIcon.textContent = kind === 'good' ? '✓' : '!';
  previewText.textContent = text;
}

function setPreviewBusy(text) {
  previewEl.classList.remove('good', 'warn');
  previewEl.classList.add('busy');
  previewIcon.textContent = '';
  previewText.textContent = text;
}

function debounce(fn, delay = 250) {
  let timer = null;
  return (...args) => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

function getApiKey() {
  const v = apiKeyEl.value.trim();
  return v ? v : null;
}

function formatDuration(totalSeconds) {
  if (totalSeconds < 60) return `${totalSeconds} sec`;
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return s ? `${m} min ${s} sec` : `${m} min`;
}

function formatDate(value) {
  if (!value) return '';
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const d = new Date(`${value}T00:00:00`);
    if (!Number.isNaN(d.getTime())) {
      return d.toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
    }
  }
  return value;
}

function todayIso() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/* ---------- Parsing ---------- */

function normalizeRecipient(raw) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;

  const name = String(raw.name ?? raw.recipient_name ?? '').trim();
  if (!name) return null;

  const email = raw.email ?? raw.recipient_email ?? null;
  const courseName = raw.course_name ?? raw.course ?? null;
  const issueDate = raw.issue_date ?? raw.date ?? null;

  return {
    name,
    email: email ? String(email).trim() : null,
    course_name: courseName ? String(courseName).trim() : null,
    issue_date: issueDate ? String(issueDate).trim() : null,
  };
}

function parseTextLines(text) {
  const out = [];
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;

    const parts = line.split(/\s*[|,\t]\s*/, 2);
    const name = (parts[0] || '').trim();
    const email = (parts[1] || '').trim();
    if (!name) continue;
    out.push({ name, email: email || null });
  }
  return out;
}

function parseJsonArray(value) {
  if (!value.trim()) return [];
  const parsed = JSON.parse(value);
  if (!Array.isArray(parsed)) throw new Error('JSON must be an array of recipient objects.');
  const items = [];
  for (const row of parsed) {
    const candidate = normalizeRecipient(row);
    if (candidate) items.push(candidate);
  }
  return items;
}

function parseCsv(text) {
  if (text.charCodeAt(0) === 0xfeff) text = text.slice(1);
  if (!text.trim()) return [];

  const rows = [];
  let row = [];
  let field = '';
  let inQuotes = false;
  let i = 0;

  while (i < text.length) {
    const ch = text[i];
    if (inQuotes) {
      if (ch === '"' && text[i + 1] === '"') {
        field += '"';
        i += 2;
        continue;
      }
      if (ch === '"') {
        inQuotes = false;
        i += 1;
        continue;
      }
      field += ch;
      i += 1;
      continue;
    }

    if (ch === '"') {
      inQuotes = true;
      i += 1;
      continue;
    }
    if (ch === ',') {
      row.push(field);
      field = '';
      i += 1;
      continue;
    }
    if (ch === '\r') {
      i += 1;
      continue;
    }
    if (ch === '\n') {
      row.push(field);
      rows.push(row);
      row = [];
      field = '';
      i += 1;
      continue;
    }
    field += ch;
    i += 1;
  }

  if (field !== '' || row.length) {
    row.push(field);
    rows.push(row);
  }

  if (rows.length === 0) return [];

  const headers = rows[0].map((h) => String(h).trim().toLowerCase());
  const out = [];
  for (let r = 1; r < rows.length; r++) {
    const cells = rows[r];
    if (cells.every((c) => !String(c).trim())) continue;

    const obj = {};
    headers.forEach((h, idx) => {
      const v = (cells[idx] || '').trim();
      if (v) obj[h] = v;
    });

    const name = obj.name || obj.recipient_name || obj.full_name || obj.fullname;
    if (!name) continue;

    out.push({
      name: String(name).trim(),
      email: obj.email || obj.recipient_email || null,
      course_name: obj.course_name || obj.course || null,
      issue_date: obj.issue_date || obj.date || null,
    });
  }
  return out;
}

function buildPayload() {
  const course = courseNameEl.value.trim();
  const issue = issueDateEl.value;
  const instructor = instructorEl.value.trim();
  const certTitle = certTitleEl.value.trim();

  const payloadRecipients = recipients.map((row) => {
    // Per-row values (e.g. from a CSV) win over the form defaults.
    const courseName = row.course_name || course;
    const issueDate = row.issue_date || issue;

    const item = { name: row.name };
    if (row.email) item.email = row.email;
    if (courseName) item.course_name = courseName;
    if (issueDate) item.issue_date = issueDate;
    if (instructor) item.instructor = instructor;
    if (certTitle) item.certificate_title = certTitle;
    return item;
  });

  const payload = { recipients: payloadRecipients };

  if (SEND_DESIGN) {
    const font = FONTS.find((f) => f.id === design.font) || FONTS[0];
    payload.design = {
      template: design.template,
      font: font.id,
      font_family: font.body,
      name_font_family: font.nameFont,
      text_scale: design.textScale / 100,
      name_scale: design.nameScale / 100,
    };
  }

  return payload;
}

/* ---------- Step 1: input rendering ---------- */

function renderDraftTable() {
  draftBody.replaceChildren();

  draftRows.forEach((row, index) => {
    const tr = document.createElement('tr');

    const idx = document.createElement('td');
    idx.className = 'col-idx';
    idx.textContent = String(index + 1);

    const nameTd = document.createElement('td');
    const nameInput = document.createElement('input');
    nameInput.type = 'text';
    nameInput.className = 'cell-name';
    nameInput.placeholder = 'Full name';
    nameInput.setAttribute('aria-label', `Name, row ${index + 1}`);
    nameInput.value = row.name || '';
    nameInput.addEventListener('input', (e) => {
      draftRows[index].name = e.target.value;
      recomputeRecipients();
    });
    nameInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        tr.querySelector('.cell-email').focus();
      }
    });
    nameTd.appendChild(nameInput);

    const emailTd = document.createElement('td');
    const emailInput = document.createElement('input');
    emailInput.type = 'email';
    emailInput.className = 'cell-email';
    emailInput.placeholder = 'Email (optional)';
    emailInput.setAttribute('aria-label', `Email, row ${index + 1}`);
    emailInput.value = row.email || '';
    emailInput.addEventListener('input', (e) => {
      draftRows[index].email = e.target.value;
      recomputeRecipients();
    });
    emailInput.addEventListener('keydown', (e) => {
      if (e.key !== 'Enter') return;
      e.preventDefault();
      if (index === draftRows.length - 1) {
        draftRows.push({ name: '', email: '' });
        renderDraftTable();
      }
      const names = draftBody.querySelectorAll('.cell-name');
      names[index + 1]?.focus();
    });
    emailTd.appendChild(emailInput);

    const removeTd = document.createElement('td');
    removeTd.className = 'col-remove';
    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'remove-btn';
    removeBtn.innerHTML = '<svg class="i"><use href="#i-x"/></svg>';
    removeBtn.title = 'Remove row';
    removeBtn.setAttribute('aria-label', `Remove row ${index + 1}`);
    removeBtn.addEventListener('click', () => {
      draftRows = draftRows.filter((_, i) => i !== index);
      if (draftRows.length === 0) draftRows = [{ name: '', email: '' }];
      renderDraftTable();
      recomputeRecipients();
    });
    removeTd.appendChild(removeBtn);

    tr.append(idx, nameTd, emailTd, removeTd);
    draftBody.appendChild(tr);
  });
}

/* ---------- Step 3: review ---------- */

function setReviewLoading() {
  reviewSummaryEl.replaceChildren(shimmer('w-180'));
  reviewBody.replaceChildren();
  for (let i = 0; i < 3; i++) reviewBody.appendChild(reviewSkelTpl.content.cloneNode(true));
  reviewTable.hidden = false;
  reviewMore.hidden = true;
  submitBtn.disabled = true;
}

function renderReviewTable() {
  reviewBody.replaceChildren();
  sideRecipients.textContent = recipients.length.toLocaleString();

  const visible = recipients.slice(0, PREVIEW_LIMIT);
  if (visible.length === 0) {
    reviewTable.hidden = true;
    reviewMore.hidden = true;
    reviewSummaryEl.textContent = 'Add recipients in step 1 to see a preview here.';
    return;
  }

  for (const [i, row] of visible.entries()) {
    const tr = document.createElement('tr');
    const idx = document.createElement('td');
    idx.textContent = String(i + 1);
    const name = document.createElement('td');
    name.textContent = row.name;
    const email = document.createElement('td');
    email.textContent = row.email || '—';
    tr.append(idx, name, email);
    reviewBody.appendChild(tr);
  }

  reviewTable.hidden = false;
  reviewSummaryEl.textContent = `${recipients.length.toLocaleString()} recipient${recipients.length === 1 ? '' : 's'} detected.`;

  if (recipients.length > PREVIEW_LIMIT) {
    reviewMore.hidden = false;
    reviewMore.textContent = `Showing the first ${PREVIEW_LIMIT}. The rest are queued for processing.`;
  } else {
    reviewMore.hidden = true;
  }
}

function updateEstimate() {
  const total = recipients.length;
  const perSecond = 50;
  const seconds = total ? Math.max(2, Math.ceil(total / perSecond)) : 2;
  const text = formatDuration(seconds);
  estimateEl.textContent = `Estimated: ${text}`;
  sideEstimate.textContent = text;
}

function refreshPreviewState() {
  if (recipients.length === 0) {
    setPreview('warn', '', 'No recipients yet. Add a list to continue.');
    submitBtn.disabled = true;
    return;
  }

  const warning = recipients.length >= LARGE_BATCH_WARN;
  setPreview(
    warning ? 'warn' : 'good',
    '',
    `${recipients.length.toLocaleString()} recipients detected${warning ? '. Large batch: check your list before submitting' : ''}.`
  );

  submitBtn.disabled = false;
}

/* ---------- Live certificate preview + step state ---------- */

function updateCertPreview() {
  const n = recipients.length;
  if (previewIndex >= n) previewIndex = Math.max(0, n - 1);
  const r = recipients[previewIndex];

  certName.textContent = r ? r.name : 'Recipient name';
  certName.classList.toggle('is-placeholder', !r);

  certTitleOut.textContent = certTitleEl.value.trim() || 'Certificate of Completion';

  const course = (r && r.course_name) || courseNameEl.value.trim();
  certCourse.textContent = course || 'Course name';
  certCourse.classList.toggle('is-placeholder', !course);

  certDate.textContent = formatDate((r && r.issue_date) || issueDateEl.value) || '—';
  certInstructor.textContent = instructorEl.value.trim() || '—';

  certCounter.textContent = n ? `${previewIndex + 1} of ${n.toLocaleString()}` : 'Sample';
  certPrev.disabled = previewIndex <= 0;
  certNext.disabled = previewIndex >= n - 1;
}

function updateStepStates() {
  const mark = (id, done) => $(id).classList.toggle('is-done', Boolean(done));
  mark('step-recipients', recipients.length > 0);
  mark('step-details', courseNameEl.value.trim() && issueDateEl.value);
  mark('step-design', designTouched);
  mark('step-review', currentJob);
  mark('step-results', currentJob && ['completed', 'completed_with_errors'].includes(currentJob.status));
}

function recomputeRecipients() {
  let next = [];

  if (activeTab === 'table') {
    next = draftRows
      .map((row) => ({ name: String(row.name || '').trim(), email: String(row.email || '').trim() }))
      .filter((row) => row.name)
      .map((row) => ({ name: row.name, email: row.email || null }));
  }

  if (activeTab === 'paste') {
    next = parseTextLines(pasteArea.value);
  }

  if (activeTab === 'json') {
    try {
      next = parseJsonArray(jsonArea.value);
    } catch (err) {
      recipients = [];
      renderReviewTable();
      updateEstimate();
      updateCertPreview();
      updateStepStates();
      setPreview('warn', '', `JSON parse error: ${err.message}`);
      submitBtn.disabled = true;
      return;
    }
  }

  if (activeTab === 'upload') {
    next = fileRecipients || [];
  }

  recipients = next;
  renderReviewTable();
  updateEstimate();
  refreshPreviewState();
  updateCertPreview();
  updateStepStates();
}

function setActiveTab(tab) {
  activeTab = tab;
  tabButtons.forEach((btn) => {
    const on = btn.dataset.tab === tab;
    btn.classList.toggle('active', on);
    btn.setAttribute('aria-selected', String(on));
  });
  tabPanels.forEach((panel) => panel.classList.toggle('active', panel.dataset.panel === tab));
  recomputeRecipients();
}

/* ---------- Step 3: design ---------- */

function clamp(n, lo, hi) {
  return Math.min(hi, Math.max(lo, n));
}

function loadDesign() {
  try {
    const saved = JSON.parse(localStorage.getItem(DESIGN_KEY) || 'null');
    if (saved && typeof saved === 'object') {
      const d = { ...DEFAULT_DESIGN, ...saved };
      if (!TEMPLATES.some((t) => t.id === d.template)) d.template = DEFAULT_DESIGN.template;
      if (!FONTS.some((f) => f.id === d.font)) d.font = DEFAULT_DESIGN.font;
      d.textScale = clamp(Number(d.textScale) || 100, 80, 120);
      d.nameScale = clamp(Number(d.nameScale) || 100, 80, 125);
      designTouched = true;
      return d;
    }
  } catch {
    // Storage can be unavailable (private mode, blocked); fall back to defaults.
  }
  return { ...DEFAULT_DESIGN };
}

function saveDesign() {
  try {
    localStorage.setItem(DESIGN_KEY, JSON.stringify(design));
  } catch {
    // Ignore: remembering the choice is a convenience only.
  }
}

function renderDesignControls() {
  tplGrid.replaceChildren();
  for (const t of TEMPLATES) {
    const label = document.createElement('label');
    label.className = 'tpl-card';
    label.innerHTML = `
      <input type="radio" name="design-template" value="${t.id}" />
      <span class="tpl-thumb" data-template="${t.id}">
        <span class="cert-deco"></span>
        <span class="tpl-lines"><i class="b-title"></i><i class="b-name"></i><i class="b-line"></i></span>
      </span>
      <span class="tpl-meta"><span class="tpl-name">${t.name}</span><span class="tpl-note">${t.note}</span></span>
      <span class="tpl-check"><svg class="i"><use href="#i-check" /></svg></span>`;
    label.querySelector('input').addEventListener('change', () => {
      design.template = t.id;
      designTouched = true;
      applyDesign({ animate: true });
    });
    tplGrid.appendChild(label);
  }

  fontGrid.replaceChildren();
  for (const f of FONTS) {
    const label = document.createElement('label');
    label.className = 'font-card';
    label.innerHTML = `
      <input type="radio" name="design-font" value="${f.id}" />
      <span class="font-sample" style="font-family:${f.nameStack};font-style:${f.nameStyle}">Jane Doe</span>
      <span class="font-name">${f.name}</span>`;
    label.querySelector('input').addEventListener('change', () => {
      design.font = f.id;
      designTouched = true;
      applyDesign({ animate: true });
    });
    fontGrid.appendChild(label);
  }

  sizePresetsEl.replaceChildren();
  for (const p of SIZE_PRESETS) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'pill';
    btn.dataset.preset = p.id;
    btn.textContent = p.label;
    btn.addEventListener('click', () => {
      design.textScale = p.text;
      design.nameScale = p.name;
      designTouched = true;
      applyDesign();
    });
    sizePresetsEl.appendChild(btn);
  }
}

function applyDesign({ animate = false, persist = true } = {}) {
  const font = FONTS.find((f) => f.id === design.font) || FONTS[0];
  const tpl = TEMPLATES.find((t) => t.id === design.template) || TEMPLATES[0];

  certPreviewEl.dataset.template = tpl.id;
  const s = certPreviewEl.style;
  s.setProperty('--cert-font', font.bodyStack);
  s.setProperty('--name-font', font.nameStack);
  s.setProperty('--name-style', font.nameStyle);
  s.setProperty('--name-boost', String(font.nameBoost));
  s.setProperty('--text-scale', String(design.textScale / 100));
  s.setProperty('--name-scale', String(design.nameScale / 100));

  textScaleEl.value = design.textScale;
  nameScaleEl.value = design.nameScale;
  textScaleOut.textContent = `${design.textScale}%`;
  nameScaleOut.textContent = `${design.nameScale}%`;

  tplGrid.querySelectorAll('.tpl-card').forEach((card) => {
    const input = card.querySelector('input');
    const on = input.value === tpl.id;
    input.checked = on;
    card.classList.toggle('is-selected', on);
  });
  fontGrid.querySelectorAll('.font-card').forEach((card) => {
    const input = card.querySelector('input');
    const on = input.value === font.id;
    input.checked = on;
    card.classList.toggle('is-selected', on);
  });
  sizePresetsEl.querySelectorAll('.pill').forEach((btn) => {
    const p = SIZE_PRESETS.find((x) => x.id === btn.dataset.preset);
    btn.classList.toggle('active', p.text === design.textScale && p.name === design.nameScale);
  });

  designSummaryEl.textContent = `Design: ${tpl.name} template, ${font.name}, text ${design.textScale}%, name ${design.nameScale}%.`;

  if (animate && !prefersReducedMotion()) {
    certPreviewEl.classList.remove('swap');
    void certPreviewEl.offsetWidth; // restart the animation
    certPreviewEl.classList.add('swap');
  }

  if (persist) saveDesign();
  updateStepStates();
}

textScaleEl.addEventListener('input', () => {
  design.textScale = Number(textScaleEl.value);
  designTouched = true;
  applyDesign();
});

nameScaleEl.addEventListener('input', () => {
  design.nameScale = Number(nameScaleEl.value);
  designTouched = true;
  applyDesign();
});

btnResetDesign.addEventListener('click', () => {
  design = { ...DEFAULT_DESIGN };
  designTouched = false;
  applyDesign({ animate: true });
  toast('Design reset to defaults.', 'info', 1800);
});

/* ---------- Downloads ---------- */

function downloadCsvText(text, name) {
  const blob = new Blob([text], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function csvEscape(value) {
  if (value === null || value === undefined) return '';
  const text = String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function downloadTemplate() {
  const csv = [
    'name,email,course_name,issue_date',
    'Alice Example,alice@example.com,Python Fundamentals,2024-03-01',
    'Bob Example,bob@example.com,Python Fundamentals,2024-03-01',
    'Carol Example,,Python Fundamentals,2024-03-01',
  ].join('\n');
  downloadCsvText(csv, 'certificate-template.csv');
}

/* ---------- Step 4: results ---------- */

function renderResultsSkeleton(n = SKELETON_ROWS) {
  resultsBody.replaceChildren();
  for (let i = 0; i < n; i++) resultsBody.appendChild(skeletonRowTpl.content.cloneNode(true));
  resultsTable.hidden = false;
}

function prepareResultsPanel(expectedCount) {
  renderResultsSkeleton(Math.max(3, Math.min(expectedCount, SKELETON_ROWS)));

  progressWrap.hidden = false;
  progressWrap.classList.add('is-indeterminate');
  progressWrap.classList.remove('is-active');
  progressFill.style.width = '0%';
  progressLabel.textContent = 'Queuing your job…';

  countsEl.hidden = false;
  countsEl.classList.add('is-loading');

  actionsRow.hidden = false;
  btnDownloadCsv.disabled = true;
  filtersEl.hidden = true;
  paginationEl.hidden = true;
  btnRetry.hidden = true;
  btnDownloadZip.hidden = true;

  allResults = [];
  currentPage = 1;
  filterStatus = 'all';
  searchQuery = '';
  searchEl.value = '';
  filterChips.forEach((c) => c.classList.toggle('active', c.dataset.filter === 'all'));
}

function renderCounts(counts) {
  for (const key of ['total', 'pending', 'success', 'failed', 'invalid']) {
    const el = countsEl.querySelector(`[data-count="${key}"]`);
    if (el) el.textContent = (counts[key] ?? 0).toLocaleString();
  }
}

function renderProgress(counts, status) {
  const done = (counts.success ?? 0) + (counts.failed ?? 0) + (counts.invalid ?? 0);
  const total = counts.total || 1;
  const pct = Math.min(100, Math.round((done / total) * 100));
  const terminal = ['completed', 'completed_with_errors', 'failed'].includes(status);

  progressWrap.classList.toggle('is-indeterminate', !terminal && done === 0);
  progressWrap.classList.toggle('is-active', !terminal && done > 0);

  progressFill.style.width = `${pct}%`;
  progressBar.setAttribute('aria-valuenow', String(pct));
  progressLabel.textContent = `${done.toLocaleString()} / ${total.toLocaleString()}  (${pct}%)`;
}

function applyFilters() {
  let out = allResults;
  if (filterStatus !== 'all') out = out.filter((r) => r.status === filterStatus);
  if (searchQuery) {
    const q = searchQuery.toLowerCase();
    out = out.filter((r) => {
      const name = (r.recipient_name || '').toLowerCase();
      const email = (r.recipient_email || '').toLowerCase();
      return name.includes(q) || email.includes(q);
    });
  }
  return out;
}

function jobInFlight() {
  return polling || (currentJob && ['queued', 'processing'].includes(currentJob.status));
}

function renderResultsPage() {
  // Nothing from the server yet: keep the skeleton on screen instead of an empty-state message.
  if (allResults.length === 0 && jobInFlight()) {
    if (!resultsBody.querySelector('tr.skeleton')) renderResultsSkeleton();
    return;
  }

  const filtered = applyFilters();
  const total = filtered.length;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  if (currentPage > totalPages) currentPage = totalPages;

  const start = (currentPage - 1) * PAGE_SIZE;
  const slice = filtered.slice(start, start + PAGE_SIZE);

  resultsBody.replaceChildren();
  if (slice.length === 0) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = 5;
    td.textContent = 'No rows match the current filter.';
    td.style.textAlign = 'center';
    td.style.color = 'var(--ink-dim)';
    td.style.padding = '32px 24px';
    tr.appendChild(td);
    resultsBody.appendChild(tr);
  } else {
    for (const cert of slice) {
      const frag = resultRowTpl.content.cloneNode(true);
      const row = frag.querySelector('tr');
      row.querySelector('.col-idx').textContent = String(cert.row_index + 1);
      row.querySelector('.col-name').textContent = cert.recipient_name || '—';
      row.querySelector('.col-email').textContent = cert.recipient_email || '—';
      setBadge(row.querySelector('.badge'), cert.status);

      const action = row.querySelector('.col-action');
      if (cert.status === 'success' && cert.download_url) {
        const a = document.createElement('a');
        a.href = cert.download_url;
        a.textContent = 'Download PDF';
        a.target = '_blank';
        a.rel = 'noopener';
        action.appendChild(a);
      } else if (cert.error) {
        action.textContent = cert.error;
        action.classList.add('col-error');
      } else if (cert.status === 'pending' || cert.status === 'processing') {
        action.appendChild(shimmer('w-70'));
      } else {
        action.textContent = '—';
      }

      resultsBody.appendChild(frag);
    }
  }

  resultsTable.hidden = false;
  filtersEl.hidden = false;
  btnDownloadCsv.disabled = allResults.length === 0;
  paginationEl.hidden = totalPages <= 1;
  pageInfoEl.textContent = `Page ${currentPage} of ${totalPages}  ·  ${total.toLocaleString()} rows`;
  btnPagePrev.disabled = currentPage <= 1;
  btnPageNext.disabled = currentPage >= totalPages;
}

function renderJobStatus(job) {
  countsEl.classList.remove('is-loading');
  setBadge(statusBadgeEl, job.status);
  renderCounts(job.counts || {});
  renderProgress(job.counts || {}, job.status);

  if (job.status === 'queued' || job.status === 'processing') {
    btnRetry.hidden = true;
  }

  if (['completed', 'completed_with_errors', 'failed'].includes(job.status)) {
    const success = (job.counts && job.counts.success) || 0;
    const failed = (job.counts && job.counts.failed) || 0;

    if (success > 0) {
      btnDownloadZip.href = `${API}/jobs/${job.id}/download`;
      btnDownloadZip.hidden = false;
    } else {
      btnDownloadZip.hidden = true;
      btnDownloadZip.removeAttribute('href');
    }

    btnRetry.hidden = failed <= 0;
  }
}

/* ---------- API ---------- */

async function getJobStatus(jobId) {
  const resp = await fetch(`${API}/jobs/${jobId}`);
  if (!resp.ok) throw new Error(`status fetch failed: HTTP ${resp.status}`);
  const data = await resp.json();
  const retryAfter = resp.headers.get('Retry-After');
  return { data, retryAfter };
}

async function listCertificates(jobId) {
  const resp = await fetch(`${API}/jobs/${jobId}/certificates?size=500`);
  if (!resp.ok) throw new Error(`certificates fetch failed: HTTP ${resp.status}`);
  const body = await resp.json();
  return body.items || [];
}

function announceFinished(job) {
  const c = job.counts || {};
  const success = c.success ?? 0;
  const failed = (c.failed ?? 0) + (c.invalid ?? 0);

  if (job.status === 'completed') {
    toast(`${success.toLocaleString()} certificate${success === 1 ? '' : 's'} ready to download.`, 'success');
  } else if (job.status === 'completed_with_errors') {
    toast(`${success.toLocaleString()} ready, ${failed.toLocaleString()} need attention.`, 'warn', 6000);
  } else {
    toast('The job failed. Check the results for details.', 'error', 6000);
  }
}

async function pollUntilDone(jobId) {
  if (pollTimerId) clearTimeout(pollTimerId);
  const token = ++pollToken;
  polling = true;
  let attempts = 0;

  const tick = async () => {
    if (token !== pollToken) return;
    attempts += 1;

    try {
      const { data: job, retryAfter } = await getJobStatus(jobId);
      if (token !== pollToken) return;

      currentJob = job;
      renderJobStatus(job);

      try {
        const certs = await listCertificates(jobId);
        if (token !== pollToken) return;
        allResults = certs;
      } catch (err) {
        console.warn('certificates fetch failed, will retry', err);
      }

      const terminal = ['completed', 'completed_with_errors', 'failed'].includes(job.status);
      if (terminal) polling = false;
      renderResultsPage();
      updateStepStates();

      if (terminal) {
        certCard.classList.remove('is-busy');
        announceFinished(job);
        return;
      }

      if (attempts >= MAX_POLL_ATTEMPTS) {
        progressLabel.textContent = 'Stopped checking after too many attempts. Refresh to see the latest status.';
        progressWrap.classList.remove('is-active', 'is-indeterminate');
        certCard.classList.remove('is-busy');
        polling = false;
        toast('Stopped checking for updates. Refresh to see the latest status.', 'warn', 6000);
        return;
      }

      const waitMs = (Number(retryAfter) || DEFAULT_RETRY_SECONDS) * 1000;
      pollTimerId = setTimeout(tick, waitMs);
    } catch (err) {
      if (token !== pollToken) return;
      console.error(err);
      polling = false;
      certCard.classList.remove('is-busy');
      formErrorEl.textContent = `Polling error: ${err.message}`;
      formErrorEl.hidden = false;
      toast(`Lost connection to the job: ${err.message}`, 'error', 6000);
    }
  };

  await tick();
}

async function createJob(payload) {
  const headers = { 'Content-Type': 'application/json' };
  const key = getApiKey();
  if (key) headers['X-API-Key'] = key;

  const resp = await fetch(`${API}/jobs`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  });

  const body = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(body.detail || `HTTP ${resp.status}`);
  return body;
}

function setSubmitting(on) {
  submitBtn.classList.toggle('is-loading', on);
  submitBtn.disabled = on || recipients.length === 0;
  submitLabel.textContent = on ? 'Submitting…' : 'Generate certificates';
  certCard.classList.toggle('is-busy', on);
}

/* ---------- Event wiring: step 1 ---------- */

btnAddRow.addEventListener('click', () => {
  draftRows.push({ name: '', email: '' });
  renderDraftTable();
  const inputs = draftBody.querySelectorAll('.cell-name');
  inputs[inputs.length - 1]?.focus();
});

btnAdd10.addEventListener('click', () => {
  for (let i = 0; i < 10; i++) draftRows.push({ name: '', email: '' });
  renderDraftTable();
});

btnClearTable.addEventListener('click', () => {
  draftRows = [{ name: '', email: '' }];
  renderDraftTable();
  recomputeRecipients();
});

const debouncedRecompute = debounce(recomputeRecipients, 250);

function onTextInput(area) {
  return () => {
    if (area.value.length > BIG_INPUT_CHARS) {
      setPreviewBusy('Reading your list…');
      setReviewLoading();
    }
    debouncedRecompute();
  };
}

pasteArea.addEventListener('input', onTextInput(pasteArea));
jsonArea.addEventListener('input', onTextInput(jsonArea));

btnLoadSample.addEventListener('click', () => {
  pasteArea.value = [
    'Alice Example | alice@example.com',
    'Bob Example | bob@example.com',
    'Carol Example',
    'David Ångström | david@example.com',
    'Eve Example | eve@example.com',
  ].join('\n');
  recomputeRecipients();
});

btnLoadLarge.addEventListener('click', () => {
  const lines = [];
  for (let i = 1; i <= 5000; i++) lines.push(`Person ${i} | person${i}@example.com`);
  pasteArea.value = lines.join('\n');
  setPreviewBusy('Reading your list…');
  setReviewLoading();
  setTimeout(recomputeRecipients, 160);
});

btnClearPaste.addEventListener('click', () => {
  pasteArea.value = '';
  recomputeRecipients();
});

btnLoadJsonSample.addEventListener('click', () => {
  jsonArea.value = JSON.stringify([
    { name: 'Alice Example', email: 'alice@example.com', course_name: 'Python Fundamentals', issue_date: '2024-03-01' },
    { name: 'Bob Example', email: 'bob@example.com' },
    { name: 'Carol Example' },
  ], null, 2);
  recomputeRecipients();
});

btnClearJson.addEventListener('click', () => {
  jsonArea.value = '';
  recomputeRecipients();
});

fileInput.addEventListener('change', async (e) => {
  const file = e.target.files?.[0];
  if (file) await handleCsvFile(file);
});

['dragenter', 'dragover'].forEach((evt) => {
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
  });
});

['dragleave', 'drop'].forEach((evt) => {
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
  });
});

dropzone.addEventListener('drop', async (e) => {
  const file = e.dataTransfer?.files?.[0];
  if (file) await handleCsvFile(file);
});

dropzone.addEventListener('click', () => fileInput.click());
dropzone.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault();
    fileInput.click();
  }
});

async function handleCsvFile(file) {
  if (!file.name.toLowerCase().endsWith('.csv')) {
    setPreview('warn', '', `"${file.name}" is not a .csv file.`);
    toast('Only .csv files are supported.', 'error');
    return;
  }

  dropzone.classList.add('is-loading');
  dropzoneText.textContent = `Reading ${file.name}…`;
  setPreviewBusy(`Reading ${file.name}…`);
  setReviewLoading();

  try {
    const text = await file.text();
    await wait(180); // let the loading state register on fast machines
    const rows = parseCsv(text);
    fileRecipients = rows;
    dropzoneText.textContent = `Loaded ${file.name} (${rows.length.toLocaleString()} rows)`;
    recomputeRecipients();
    if (rows.length === 0) toast('No rows with a name column were found in that file.', 'warn');
  } catch (err) {
    console.error(err);
    dropzoneText.textContent = 'Click to choose a CSV, or drop it here';
    setPreview('warn', '', `Could not read ${file.name}: ${err.message}`);
    recomputeRecipients();
  } finally {
    dropzone.classList.remove('is-loading');
  }
}

btnClearFile.addEventListener('click', () => {
  fileInput.value = '';
  fileRecipients = null;
  dropzoneText.textContent = 'Click to choose a CSV, or drop it here';
  recomputeRecipients();
});

btnDownloadTpl.addEventListener('click', downloadTemplate);

/* ---------- Event wiring: step 2 (details + live preview) ---------- */

[courseNameEl, issueDateEl, instructorEl, certTitleEl].forEach((el) => {
  el.addEventListener('input', () => {
    updateCertPreview();
    updateStepStates();
  });
});

certPrev.addEventListener('click', () => {
  if (previewIndex > 0) {
    previewIndex -= 1;
    updateCertPreview();
  }
});

certNext.addEventListener('click', () => {
  if (previewIndex < recipients.length - 1) {
    previewIndex += 1;
    updateCertPreview();
  }
});

/* ---------- Event wiring: step 4 ---------- */

filterChips.forEach((chip) => {
  chip.addEventListener('click', () => {
    filterStatus = chip.dataset.filter;
    currentPage = 1;
    filterChips.forEach((c) => c.classList.toggle('active', c === chip));
    renderResultsPage();
  });
});

searchEl.addEventListener('input', debounce(() => {
  searchQuery = searchEl.value.trim();
  currentPage = 1;
  renderResultsPage();
}, 200));

btnPagePrev.addEventListener('click', () => {
  if (currentPage > 1) {
    currentPage -= 1;
    renderResultsPage();
  }
});

btnPageNext.addEventListener('click', () => {
  const totalPages = Math.max(1, Math.ceil(applyFilters().length / PAGE_SIZE));
  if (currentPage < totalPages) {
    currentPage += 1;
    renderResultsPage();
  }
});

btnDownloadCsv.addEventListener('click', () => {
  if (allResults.length === 0) return;
  const lines = [['row_index', 'name', 'email', 'status', 'error', 'checksum'].join(',')];
  for (const r of allResults) {
    lines.push([
      r.row_index + 1,
      csvEscape(r.recipient_name || ''),
      csvEscape(r.recipient_email || ''),
      r.status,
      csvEscape(r.error || ''),
      csvEscape(r.checksum || ''),
    ].join(','));
  }
  downloadCsvText(lines.join('\n'), `job-${currentJob?.id || 'report'}-report.csv`);
});

btnRetry.addEventListener('click', async () => {
  if (!currentJob) return;
  btnRetry.disabled = true;
  formErrorEl.hidden = true;
  try {
    const headers = {};
    const key = getApiKey();
    if (key) headers['X-API-Key'] = key;

    const resp = await fetch(`${API}/jobs/${currentJob.id}/retry`, {
      method: 'POST',
      headers,
    });
    const body = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(body.detail || `HTTP ${resp.status}`);

    currentJob = body;
    jobIdText.textContent = body.id;
    setBadge(statusBadgeEl, body.status);
    renderCounts(body.counts);
    renderProgress(body.counts, body.status);
    btnRetry.hidden = true;
    toast('Retrying the failed rows…', 'info');
    updateStepStates();
    await pollUntilDone(body.id);
  } catch (err) {
    formErrorEl.textContent = `Retry failed: ${err.message}`;
    formErrorEl.hidden = false;
    toast(`Retry failed: ${err.message}`, 'error', 6000);
  } finally {
    btnRetry.disabled = false;
  }
});

btnCopyJobId.addEventListener('click', async () => {
  const label = btnCopyJobId.querySelector('.label');
  try {
    await navigator.clipboard.writeText(jobIdText.textContent || '');
    const old = label.textContent;
    label.textContent = 'Copied';
    toast('Job ID copied.', 'success', 1800);
    setTimeout(() => {
      label.textContent = old;
    }, 1500);
  } catch {
    // Clipboard may be blocked in some browsers; fail silently.
  }
});

submitBtn.addEventListener('click', async () => {
  if (recipients.length === 0) {
    formErrorEl.textContent = 'Add at least one recipient before submitting.';
    formErrorEl.hidden = false;
    return;
  }

  formErrorEl.hidden = true;
  setSubmitting(true);

  // Show the results card straight away, in its loading state.
  pollToken += 1; // cancel any poll still running for a previous job
  polling = true;
  currentJob = null;
  stepResults.hidden = false;
  jobIdRow.hidden = false;
  jobIdRow.classList.add('is-loading');
  jobIdText.textContent = '';
  setBadge(statusBadgeEl, 'submitting');
  prepareResultsPanel(recipients.length);
  stepResults.scrollIntoView({ behavior: prefersReducedMotion() ? 'auto' : 'smooth', block: 'start' });

  try {
    const payload = buildPayload();
    const body = await createJob(payload);
    currentJob = body;

    jobIdRow.classList.remove('is-loading');
    jobIdText.textContent = body.id;
    setBadge(statusBadgeEl, body.status);
    renderCounts(body.counts);
    countsEl.classList.remove('is-loading');
    renderProgress(body.counts, body.status);
    updateStepStates();
    toast('Job created. Generating certificates…', 'info', 2500);
    await pollUntilDone(body.id);
  } catch (err) {
    pollToken += 1;
    polling = false;
    jobIdRow.classList.remove('is-loading');
    stepResults.hidden = true;
    formErrorEl.textContent = `Could not create job: ${err.message}`;
    formErrorEl.hidden = false;
    toast(`Could not create job: ${err.message}`, 'error', 6000);
  } finally {
    setSubmitting(false);
    certCard.classList.remove('is-busy');
    if (polling) certCard.classList.add('is-busy');
  }
});

/* ---------- Init ---------- */

for (const btn of tabButtons) {
  btn.addEventListener('click', () => setActiveTab(btn.dataset.tab));
}

function initApp() {
  issueDateEl.value = todayIso();
  renderDesignControls();
  applyDesign({ persist: false });
  renderDraftTable();
  setActiveTab('table');
  renderReviewTable();
  updateEstimate();
  refreshPreviewState();
  updateCertPreview();
  updateStepStates();
  setBadge(statusBadgeEl, 'idle');
  btnDownloadZip.hidden = true;
}

initApp();