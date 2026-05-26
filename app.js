/**
 * Parâmetros Sindicais — consulta e revisão manual
 * Carrega data/base_parametros_sindicais.json e renderiza a listagem com filtros.
 * Suporta revisão e validação manual de registros pendente_revisao e conflito.
 */

const DATA_URL = 'data/base_parametros_sindicais.json';
const EXAMPLE_DATA_URL = 'data/base_parametros_sindicais.example.json';
const LOCALSTORAGE_KEY = 'parametros_sindicais_registros';

const EMBEDDED_DEMO = {
  data_geracao: null,
  registros: [
    {
      id_registro_reajuste: 'DEMO-001',
      ids_registros_conflitantes: null,
      sindicato: 'SESCON-MG',
      uf: 'MG',
      categoria: 'Técnicos em Contabilidade',
      ano_referencia: 2025,
      status_parametro: 'valido',
      conflito: false,
      percentual_reajuste: 5.5,
      data_base: '2025-01-01',
      vigencia_inicio: '2025-01-01',
      vigencia_fim: '2025-12-31',
      fonte_documento: 'CCT 2025',
      observacao: null,
    },
    {
      id_registro_reajuste: 'DEMO-002',
      ids_registros_conflitantes: null,
      sindicato: 'SINTTEL-SP',
      uf: 'SP',
      categoria: 'Telecomunicações',
      ano_referencia: 2025,
      status_parametro: 'valido',
      conflito: false,
      percentual_reajuste: 6.0,
      data_base: '2025-04-01',
      vigencia_inicio: '2025-04-01',
      vigencia_fim: '2026-03-31',
      fonte_documento: 'CCT 2025',
      observacao: null,
    },
    {
      id_registro_reajuste: null,
      ids_registros_conflitantes: ['DEMO-003', 'DEMO-004'],
      sindicato: 'SENALBA-RJ',
      uf: 'RJ',
      categoria: 'Trabalhadores em Empresas de Asseio e Conservação',
      ano_referencia: 2025,
      status_parametro: 'conflito',
      conflito: true,
      percentual_reajuste: null,
      data_base: null,
      vigencia_inicio: null,
      vigencia_fim: null,
      fonte_documento: null,
      observacao:
        'Conflito: múltiplos registros aprovados para a mesma chave sindicato/UF/categoria. IDs conflitantes: DEMO-003, DEMO-004.',
    },
    {
      id_registro_reajuste: 'DEMO-003',
      ids_registros_conflitantes: null,
      sindicato: 'SINDUSCON-RS',
      uf: 'RS',
      categoria: 'Construção Civil',
      ano_referencia: 2025,
      status_parametro: 'pendente_revisao',
      conflito: false,
      percentual_reajuste: null,
      data_base: null,
      vigencia_inicio: null,
      vigencia_fim: null,
      fonte_documento: 'CCT/RS/SINDUSCON-RS_2025.pdf',
      observacao: null,
    },
  ],
};

const elLoading = document.getElementById('state-loading');
const elUnavailable = document.getElementById('state-unavailable');
const elApp = document.getElementById('app');
const elDataGeracao = document.getElementById('data-geracao-badge');
const elFilterUf = document.getElementById('filter-uf');
const elFilterSindicato = document.getElementById('filter-sindicato');
const elFilterAno = document.getElementById('filter-ano');
const elFilterStatus = document.getElementById('filter-status');
const elBtnClear = document.getElementById('btn-clear-filters');
const elTbody = document.getElementById('params-tbody');
const elNoResults = document.getElementById('no-results');
const elResultCount = document.getElementById('result-count');

let allRecords = [];
let originalRecords = [];
let currentDetailRecord = null;
let detailModal = null;

// ── Bootstrap date the app ──────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  if (window.bootstrap) {
    detailModal = new bootstrap.Modal(document.getElementById('detail-modal'));
  }
  loadData();

  document.getElementById('btn-validar').addEventListener('click', () => {
    if (currentDetailRecord) handleValidar(currentDetailRecord);
  });

  document.getElementById('btn-export-json').addEventListener('click', handleExportJson);
  document.getElementById('btn-discard-local').addEventListener('click', handleDiscardLocal);
});

// ── Data loading ────────────────────────────────────────────────────

async function tryFetch(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const text = await response.text();
  if (!text.trim()) throw new Error('Empty file');
  const data = JSON.parse(text);
  const records = Array.isArray(data) ? data : data.registros;
  if (!Array.isArray(records)) throw new Error('Invalid structure');
  return { data, records };
}

async function loadData() {
  let records = null;
  let dataGeracao = null;
  let demoMessage = null;

  try {
    const result = await tryFetch(DATA_URL);
    records = result.records;
    dataGeracao = result.data.data_geracao ?? null;
  } catch {
    try {
      const result = await tryFetch(EXAMPLE_DATA_URL);
      records = result.records;
      dataGeracao = result.data.data_geracao ?? null;
      demoMessage = 'Ambiente de demonstração — usando base de exemplo';
    } catch {
      // both fetches failed — use embedded demo (e.g. file:// protocol)
      records = EMBEDDED_DEMO.registros;
      dataGeracao = null;
      demoMessage = 'Ambiente de demonstração — base embutida para teste local';
    }
  }

  if (!records) {
    showUnavailable();
    return;
  }

  try {
    originalRecords = JSON.parse(JSON.stringify(records));
    let loadedFromStorage = false;
    const saved = localStorage.getItem(LOCALSTORAGE_KEY);
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) {
          allRecords = parsed;
          loadedFromStorage = true;
        } else {
          allRecords = records;
        }
      } catch {
        allRecords = records;
      }
    } else {
      allRecords = records;
    }
    showApp(dataGeracao, demoMessage);
    if (loadedFromStorage) {
      showLocalChangesBanner();
    }
    populateFilterOptions();
    renderTable();
  } catch {
    showUnavailable();
  }
}

function showUnavailable() {
  elLoading.classList.add('d-none');
  elUnavailable.classList.remove('d-none');
}

function showApp(dataGeracao, demoMessage = null) {
  elLoading.classList.add('d-none');
  elApp.classList.remove('d-none');

  if (demoMessage) {
    let demoBanner = document.getElementById('demo-banner');
    if (!demoBanner) {
      demoBanner = document.createElement('div');
      demoBanner.id = 'demo-banner';
      demoBanner.className = 'alert alert-warning text-center mb-3';
      demoBanner.setAttribute('role', 'alert');
      elApp.insertAdjacentElement('afterbegin', demoBanner);
    }
    demoBanner.textContent = demoMessage;
  }

  if (dataGeracao) {
    elDataGeracao.textContent = `Data de atualização da base: ${formatDateTime(dataGeracao)}`;
    elDataGeracao.classList.remove('d-none');
  }
}

// ── Filter option population ────────────────────────────────────────

function populateFilterOptions() {
  const ufs = [...new Set(allRecords.map((r) => r.uf).filter(Boolean))].sort();
  ufs.forEach((uf) => {
    const opt = document.createElement('option');
    opt.value = uf;
    opt.textContent = uf;
    elFilterUf.appendChild(opt);
  });

  const anos = [...new Set(allRecords.map((r) => r.ano_referencia).filter(Boolean))].sort(
    (a, b) => b - a,
  );
  anos.forEach((ano) => {
    const opt = document.createElement('option');
    opt.value = ano;
    opt.textContent = ano;
    elFilterAno.appendChild(opt);
  });
}

// ── Filter listeners ────────────────────────────────────────────────

[elFilterUf, elFilterAno, elFilterStatus].forEach((el) =>
  el.addEventListener('change', renderTable),
);
elFilterSindicato.addEventListener('input', renderTable);
elBtnClear.addEventListener('click', () => {
  elFilterUf.value = '';
  elFilterSindicato.value = '';
  elFilterAno.value = '';
  elFilterStatus.value = '';
  renderTable();
});

// ── Table rendering ─────────────────────────────────────────────────

function applyFilters() {
  const uf = elFilterUf.value;
  const sindicato = elFilterSindicato.value.trim().toLowerCase();
  const ano = elFilterAno.value;
  const status = elFilterStatus.value;

  return allRecords.filter((r) => {
    if (uf && r.uf !== uf) return false;
    if (sindicato && !(r.sindicato ?? '').toLowerCase().includes(sindicato)) return false;
    if (ano && String(r.ano_referencia) !== ano) return false;
    if (status && r.status_parametro !== status) return false;
    return true;
  });
}

function renderTable() {
  const filtered = applyFilters();

  elTbody.innerHTML = '';

  if (filtered.length === 0) {
    elNoResults.classList.remove('d-none');
    elResultCount.textContent = '';
    return;
  }

  elNoResults.classList.add('d-none');
  elResultCount.textContent = `${filtered.length} registro${filtered.length !== 1 ? 's' : ''}`;

  filtered.forEach((record, idx) => {
    const isConflict = record.status_parametro === 'conflito' || record.conflito === true;
    const isPending = record.status_parametro === 'pendente_revisao';
    const tr = document.createElement('tr');
    if (isConflict) tr.classList.add('row-conflito');
    if (isPending) tr.classList.add('row-pendente');
    tr.setAttribute('role', 'button');
    tr.setAttribute('tabindex', '0');
    tr.setAttribute('aria-label', `Ver detalhes: ${record.sindicato ?? ''} ${record.uf ?? ''}`);

    tr.innerHTML = `
      <td>${escHtml(record.uf ?? '—')}</td>
      <td>${escHtml(record.sindicato ?? '—')}</td>
      <td>${escHtml(String(record.ano_referencia ?? '—'))}</td>
      <td>${formatPercent(record.percentual_reajuste)}</td>
      <td>${formatDate(record.data_base)}</td>
      <td>${formatDate(record.vigencia_inicio)}</td>
      <td>${formatDate(record.vigencia_fim)}</td>
      <td>${statusBadge(record)}</td>
      <td class="fonte-cell" title="${escAttr(record.fonte_documento ?? '')}">${escHtml(record.fonte_documento ?? '—')}</td>
    `;

    tr.addEventListener('click', () => openDetail(record));
    tr.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        openDetail(record);
      }
    });

    elTbody.appendChild(tr);
  });
}

// ── Detail modal ────────────────────────────────────────────────────

function openDetail(record) {
  const isConflict = record.status_parametro === 'conflito' || record.conflito === true;
  const isPending = record.status_parametro === 'pendente_revisao';
  const needsReview = isPending || isConflict;

  currentDetailRecord = record;

  document.getElementById('detail-modal-label').textContent =
    `${record.sindicato ?? '—'} — ${record.uf ?? '—'} (${record.ano_referencia ?? '—'})`;

  document.getElementById('detail-modal-body').innerHTML = buildDetailHtml(record, isConflict, isPending);

  const btnValidar = document.getElementById('btn-validar');
  btnValidar.classList.toggle('d-none', !needsReview);

  if (detailModal) {
    detailModal.show();
  }
}

function buildDetailHtml(r, isConflict, isPending) {
  // [label, rawValue, isHtml] — isHtml=true means value is already trusted HTML
  const fields = [
    ['UF', r.uf, false],
    ['Sindicato', r.sindicato, false],
    ['Ano de referência', r.ano_referencia, false],
    ['Percentual de reajuste', formatPercent(r.percentual_reajuste), false],
    ['Data-base', formatDate(r.data_base), false],
    ['Vigência início', formatDate(r.vigencia_inicio), false],
    ['Vigência fim', formatDate(r.vigencia_fim), false],
    ['Status', statusBadge(r), true],
    ['Conflito', r.conflito ? 'Sim' : 'Não', false],
  ];

  if (r.id_registro_reajuste != null) {
    fields.push(['ID do registro', r.id_registro_reajuste, false]);
  }

  // Fonte do documento with optional "Abrir PDF" button
  if (r.fonte_documento) {
    const fonteDisplay = escHtml(r.fonte_documento);
    const fonteLink = `${fonteDisplay} <a href="${escAttr(r.fonte_documento)}" target="_blank" rel="noopener noreferrer" class="btn btn-outline-secondary btn-sm ms-2 py-0">📄 Abrir PDF</a>`;
    fields.push(['Fonte do documento', fonteLink, true]);
  } else {
    fields.push(['Fonte do documento', null, false]);
  }

  if (r.observacao != null) {
    fields.push(['Observação', r.observacao, false]);
  }

  // Rastreabilidade (shown for previously validated records)
  if (r.origem_atualizacao) {
    fields.push(['Origem da atualização', r.origem_atualizacao, false]);
  }
  if (r.data_hora_validacao_manual) {
    fields.push(['Data/hora da validação', formatDateTime(r.data_hora_validacao_manual), false]);
  }
  if (r.status_anterior) {
    fields.push(['Status anterior', r.status_anterior, false]);
  }

  let html = '<div class="row g-3">';
  fields.forEach(([label, value, isHtml]) => {
    const display = isHtml ? (value ?? '—') : escHtml(String(value ?? '—'));
    html += `
      <div class="col-12 col-sm-6">
        <div class="detail-field-label">${escHtml(label)}</div>
        <div class="detail-field-value">${display}</div>
      </div>`;
  });
  html += '</div>';

  if (isConflict && Array.isArray(r.ids_registros_conflitantes) && r.ids_registros_conflitantes.length > 0) {
    const ids = r.ids_registros_conflitantes
      .map((id) => `<span class="conflicting-id">${escHtml(String(id))}</span>`)
      .join('');
    html += `
      <hr class="my-3"/>
      <div class="detail-conflict-box">
        <div class="detail-field-label mb-1">⚠ Registros conflitantes</div>
        <div>${ids}</div>
        <p class="mb-0 mt-2 small text-warning-emphasis">
          Este parâmetro está em conflito e requer resolução manual. Nenhum parâmetro é sugerido ou priorizado automaticamente.
        </p>
      </div>`;
  }

  // Review panel for pending/conflict records
  if (isPending || isConflict) {
    html += buildReviewPanel(r, isConflict, isPending);
  }

  return html;
}

function buildReviewPanel(r, isConflict, isPending) {
  const title = isPending ? '⏳ Revisão necessária' : '⚠ Conflito encontrado';
  const guidance = isPending
    ? `<p class="mb-2">Este sindicato existe na pasta CCT mas ainda <strong>não possui parâmetro aprovado</strong>.
        Abra o PDF de origem para localizar o reajuste, a data-base e a vigência.</p>
       <ul class="review-checklist mb-0">
         <li>Abra o PDF da CCT utilizando o botão <strong>Abrir PDF</strong> no campo Fonte do documento</li>
         <li>Localize a cláusula de reajuste, data-base e vigência no documento</li>
         <li>Preencha todos os campos obrigatórios abaixo com os valores encontrados</li>
         <li>Registre a justificativa completa no campo Observação</li>
       </ul>`
    : `<p class="mb-2">Foi identificada <strong>ambiguidade entre documentos</strong> para este sindicato.
        Nenhum parâmetro é escolhido automaticamente.</p>
       <ul class="review-checklist mb-0">
         <li>Analise os registros conflitantes listados acima</li>
         <li>Abra o PDF de referência para determinar o valor correto</li>
         <li>Preencha manualmente os campos obrigatórios abaixo</li>
         <li>Registre a justificativa completa no campo Observação, indicando qual documento prevalece</li>
       </ul>`;

  return `
    <hr class="my-3"/>
    <div class="review-panel ${isPending ? 'review-panel-pendente' : 'review-panel-conflito'}">
      <h6 class="fw-bold mb-2">${escHtml(title)}</h6>
      ${guidance}
    </div>
    <hr class="my-3"/>
    <div class="validation-form">
      <h6 class="fw-semibold mb-3">Formulário de validação manual</h6>
      <div id="validation-error" class="alert alert-danger d-none" role="alert"></div>
      <div class="row g-3">
        <div class="col-12 col-sm-6">
          <label for="val-percentual" class="form-label form-label-sm fw-semibold">
            Percentual de reajuste (%) <span class="text-danger">*</span>
          </label>
          <input type="number" step="0.01" id="val-percentual" class="form-control form-control-sm"
            placeholder="Ex.: 5.50" autocomplete="off" />
        </div>
        <div class="col-12 col-sm-6">
          <label for="val-data-base" class="form-label form-label-sm fw-semibold">
            Data-base <span class="text-danger">*</span>
          </label>
          <input type="date" id="val-data-base" class="form-control form-control-sm" />
        </div>
        <div class="col-12 col-sm-6">
          <label for="val-vigencia-inicio" class="form-label form-label-sm fw-semibold">
            Vigência início <span class="text-danger">*</span>
          </label>
          <input type="date" id="val-vigencia-inicio" class="form-control form-control-sm" />
        </div>
        <div class="col-12 col-sm-6">
          <label for="val-vigencia-fim" class="form-label form-label-sm fw-semibold">
            Vigência fim <span class="text-danger">*</span>
          </label>
          <input type="date" id="val-vigencia-fim" class="form-control form-control-sm" />
        </div>
        <div class="col-12">
          <label for="val-observacao" class="form-label form-label-sm fw-semibold">
            Observação / Justificativa <span class="text-danger">*</span>
          </label>
          <textarea id="val-observacao" class="form-control form-control-sm" rows="3"
            placeholder="Informe a cláusula do acordo, número da página do PDF consultado, trecho relevante ou motivo da decisão de validação. Ex.: Cláusula 5ª, pág. 12 — reajuste de 5,50% a partir de 01/01/2025."></textarea>
        </div>
      </div>
      <p class="mt-2 mb-0 small text-muted">
        <span class="text-danger">*</span> Todos os campos são obrigatórios. O sistema não preenche nem sugere valores automaticamente.
      </p>
    </div>`;
}

// ── Validation handler ───────────────────────────────────────────────

function handleValidar(record) {
  // Guard: record must still be in allRecords (not stale after a discard)
  if (!allRecords.includes(record)) return;

  const percentInput = document.getElementById('val-percentual');
  const dataBaseInput = document.getElementById('val-data-base');
  const vigInicioInput = document.getElementById('val-vigencia-inicio');
  const vigFimInput = document.getElementById('val-vigencia-fim');
  const observacaoInput = document.getElementById('val-observacao');
  const errorDiv = document.getElementById('validation-error');

  const percentVal = percentInput ? percentInput.valueAsNumber : NaN;
  const dataBase = dataBaseInput ? dataBaseInput.value : '';
  const vigInicio = vigInicioInput ? vigInicioInput.value : '';
  const vigFim = vigFimInput ? vigFimInput.value : '';
  const observacao = observacaoInput ? observacaoInput.value.trim() : '';

  const missing = [];
  if (!percentInput || !percentInput.value || !Number.isFinite(percentVal)) {
    missing.push('Percentual de reajuste');
  }
  if (!dataBase) missing.push('Data-base');
  if (!vigInicio) missing.push('Vigência início');
  if (!vigFim) missing.push('Vigência fim');
  if (!observacao) missing.push('Observação / Justificativa');

  if (missing.length > 0) {
    if (errorDiv) {
      errorDiv.textContent = `Campos obrigatórios não preenchidos: ${missing.join(', ')}.`;
      errorDiv.classList.remove('d-none');
    }
    return;
  }

  if (errorDiv) errorDiv.classList.add('d-none');

  const statusAnterior = record.status_parametro;

  // Update record in-place (mutates the object in allRecords)
  record.status_parametro = 'valido';
  record.conflito = false;
  record.ids_registros_conflitantes = null;
  record.percentual_reajuste = percentVal;
  record.data_base = dataBase;
  record.vigencia_inicio = vigInicio;
  record.vigencia_fim = vigFim;
  record.observacao = observacao;
  record.origem_atualizacao = 'validacao_manual_tela';
  record.data_hora_validacao_manual = new Date().toISOString();
  record.status_anterior = statusAnterior;

  try {
    localStorage.setItem(LOCALSTORAGE_KEY, JSON.stringify(allRecords));
  } catch {
    // localStorage may be unavailable; continue without persistence
  }

  showLocalChangesBanner();

  if (detailModal) detailModal.hide();
  currentDetailRecord = null;
  renderTable();
}

// ── Export / Discard handlers ────────────────────────────────────────

function handleExportJson() {
  const exportData = {
    data_geracao: new Date().toISOString(),
    registros: allRecords,
  };
  const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `base_parametros_sindicais_${new Date().toISOString().slice(0, 10)}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function handleDiscardLocal() {
  const hasLocal = !!localStorage.getItem(LOCALSTORAGE_KEY);
  if (!hasLocal) {
    alert('Não há alterações locais para descartar.');
    return;
  }
  if (!confirm('Deseja descartar todas as alterações locais e restaurar a base original? Esta ação não pode ser desfeita.')) {
    return;
  }
  // Close modal first to avoid stale record references
  if (detailModal) detailModal.hide();
  currentDetailRecord = null;

  try {
    localStorage.removeItem(LOCALSTORAGE_KEY);
  } catch {
    // ignore
  }
  allRecords = JSON.parse(JSON.stringify(originalRecords));
  hideLocalChangesBanner();
  renderTable();
}

// ── Local changes banner ─────────────────────────────────────────────

function showLocalChangesBanner() {
  const banner = document.getElementById('local-changes-banner');
  if (banner) banner.classList.remove('d-none');
}

function hideLocalChangesBanner() {
  const banner = document.getElementById('local-changes-banner');
  if (banner) banner.classList.add('d-none');
}



function statusBadge(record) {
  if (record.status_parametro === 'pendente_revisao') {
    return '<span class="badge-pendente">⏳ Pendente revisão</span>';
  }
  const isConflict = record.status_parametro === 'conflito' || record.conflito === true;
  if (isConflict) {
    return '<span class="badge-conflito">⚠ Conflito</span>';
  }
  return '<span class="badge-valido">✔ Válido</span>';
}

function formatDate(value) {
  if (!value) return '—';
  // Accept ISO date strings (YYYY-MM-DD or full ISO)
  const d = new Date(value.length === 10 ? value + 'T00:00:00' : value);
  if (isNaN(d.getTime())) return escHtml(String(value));
  return d.toLocaleDateString('pt-BR');
}

function formatDateTime(value) {
  if (!value) return '';
  const d = new Date(value);
  if (isNaN(d.getTime())) return String(value);
  return d.toLocaleString('pt-BR');
}

function formatPercent(value) {
  if (value == null) return '—';
  return `${Number(value).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function escAttr(str) {
  return escHtml(str);
}
