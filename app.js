/**
 * Parâmetros Sindicais — consulta e revisão manual
 * Carrega data/base_parametros_sindicais.json e renderiza a listagem com filtros.
 * Permite revisão e validação manual de registros pendentes e em conflito.
 */

const DATA_URL = 'data/base_parametros_sindicais.json';
const EXAMPLE_DATA_URL = 'data/base_parametros_sindicais.example.json';
const LS_KEY = 'sindicatos_parametros_local';

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
      id_registro_reajuste: null,
      ids_registros_conflitantes: null,
      sindicato: 'SINDPREV-RS',
      uf: 'RS',
      categoria: 'Previdência Social',
      ano_referencia: 2025,
      status_parametro: 'pendente_revisao',
      conflito: false,
      percentual_reajuste: null,
      data_base: null,
      vigencia_inicio: null,
      vigencia_fim: null,
      fonte_documento: null,
      observacao: null,
    },
    {
      id_registro_reajuste: null,
      ids_registros_conflitantes: null,
      sindicato: 'SEEB-BA',
      uf: 'BA',
      categoria: 'Bancários',
      ano_referencia: 2025,
      status_parametro: 'pendente_revisao',
      conflito: false,
      percentual_reajuste: null,
      data_base: null,
      vigencia_inicio: null,
      vigencia_fim: null,
      fonte_documento: 'https://example.com/cct-seeb-ba-2025.pdf',
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
let detailModal = null;
let currentDataGeracao = null;

// ── Bootstrap date the app ──────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  if (window.bootstrap) {
    detailModal = new bootstrap.Modal(document.getElementById('detail-modal'));
  }
  document.getElementById('btn-export-json').addEventListener('click', exportJson);
  document.getElementById('btn-discard-local').addEventListener('click', discardLocalChanges);
  loadData();
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
    currentDataGeracao = dataGeracao;
    originalRecords = JSON.parse(JSON.stringify(records));
    allRecords = loadFromLocalStorage(records, dataGeracao);
    showApp(dataGeracao, demoMessage);
    if (allRecords !== records) {
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

  document.getElementById('detail-modal-label').textContent =
    `${record.sindicato ?? '—'} — ${record.uf ?? '—'} (${record.ano_referencia ?? '—'})`;

  document.getElementById('detail-modal-body').innerHTML = buildDetailHtml(record, isConflict, isPending);

  if (isPending || isConflict) {
    const btnPdf = document.getElementById('btn-open-pdf');
    if (btnPdf) {
      btnPdf.addEventListener('click', () => openPdf(record.fonte_documento));
    }

    const validateForm = document.getElementById('validate-form');
    if (validateForm) {
      validateForm.addEventListener('submit', (e) => {
        e.preventDefault();
        handleValidate(record);
      });
    }
  }

  if (detailModal) {
    detailModal.show();
  }
}

function buildDetailHtml(r, isConflict, isPending) {
  const needsReview = isPending || isConflict;

  // Read-only fields always shown
  const fields = [
    ['UF', r.uf],
    ['Sindicato', r.sindicato],
    ['Ano de referência', r.ano_referencia],
    ['Percentual de reajuste', formatPercent(r.percentual_reajuste)],
    ['Data-base', formatDate(r.data_base)],
    ['Vigência início', formatDate(r.vigencia_inicio)],
    ['Vigência fim', formatDate(r.vigencia_fim)],
    ['Status', statusBadge(r)],
    ['Conflito', r.conflito ? 'Sim' : 'Não'],
  ];

  if (r.id_registro_reajuste != null) {
    fields.push(['ID do registro', r.id_registro_reajuste]);
  }

  fields.push(['Fonte do documento', r.fonte_documento ?? '—']);

  if (r.observacao != null) {
    fields.push(['Observação', r.observacao]);
  }

  // Traceability fields (shown for already-validated records)
  if (r.origem_atualizacao) {
    fields.push(['Origem da atualização', r.origem_atualizacao]);
  }
  if (r.data_hora_validacao_manual) {
    fields.push(['Data/hora da validação manual', formatDateTime(r.data_hora_validacao_manual)]);
  }
  if (r.status_anterior) {
    fields.push(['Status anterior', r.status_anterior]);
  }

  let html = '<div class="row g-3">';
  fields.forEach(([label, value]) => {
    html += `
      <div class="col-12 col-sm-6">
        <div class="detail-field-label">${escHtml(label)}</div>
        <div class="detail-field-value">${value ?? '—'}</div>
      </div>`;
  });
  html += '</div>';

  if (!needsReview) {
    return html;
  }

  // Review panel
  html += '<hr class="my-3"/>';

  if (isPending) {
    html += `
      <div class="review-panel review-panel-pendente mb-3">
        <div class="review-panel-header">
          <span>📋</span>
          <strong>Revisão necessária</strong>
        </div>
        <p class="review-panel-desc">Este sindicato existe na pasta CCT mas ainda não possui parâmetro aprovado. Abra o PDF de origem para localizar o percentual de reajuste, a data-base e o período de vigência.</p>
        ${buildChecklist(r)}
        ${buildPdfButton(r)}
      </div>`;
  }

  if (isConflict) {
    let conflictIds = '';
    if (Array.isArray(r.ids_registros_conflitantes) && r.ids_registros_conflitantes.length > 0) {
      conflictIds = r.ids_registros_conflitantes
        .map((id) => `<span class="conflicting-id">${escHtml(String(id))}</span>`)
        .join('');
    }
    html += `
      <div class="review-panel review-panel-conflito mb-3">
        <div class="review-panel-header">
          <span>⚠</span>
          <strong>Conflito encontrado</strong>
        </div>
        <p class="review-panel-desc">Existe ambiguidade entre documentos para este sindicato/UF/categoria. Nenhum parâmetro é escolhido automaticamente. Abra o PDF e preencha manualmente os valores corretos.</p>
        ${conflictIds ? `<div class="mb-2"><span class="detail-field-label">Registros conflitantes:</span> ${conflictIds}</div>` : ''}
        ${buildChecklist(r)}
        ${buildPdfButton(r)}
      </div>`;
  }

  // Validation form
  html += `
    <div class="validate-form-section">
      <h6 class="validate-form-title">Preenchimento para validação manual</h6>
      <p class="text-muted small mb-3">Todos os campos são obrigatórios. O sistema não sugere, calcula ou pré-preenche valores automaticamente.</p>
      <form id="validate-form" novalidate>
        <div class="row g-2">
          <div class="col-md-6">
            <label class="form-label form-label-sm" for="f-percentual">Percentual de reajuste (%) <span class="text-danger">*</span></label>
            <input type="number" id="f-percentual" class="form-control form-control-sm" step="0.01" min="-100" max="1000" placeholder="Ex: 5.50" />
          </div>
          <div class="col-md-6">
            <label class="form-label form-label-sm" for="f-data-base">Data-base <span class="text-danger">*</span></label>
            <input type="date" id="f-data-base" class="form-control form-control-sm" />
          </div>
          <div class="col-md-6">
            <label class="form-label form-label-sm" for="f-vigencia-inicio">Vigência início <span class="text-danger">*</span></label>
            <input type="date" id="f-vigencia-inicio" class="form-control form-control-sm" />
          </div>
          <div class="col-md-6">
            <label class="form-label form-label-sm" for="f-vigencia-fim">Vigência fim <span class="text-danger">*</span></label>
            <input type="date" id="f-vigencia-fim" class="form-control form-control-sm" />
          </div>
          <div class="col-12">
            <label class="form-label form-label-sm" for="f-observacao">Observação — justificativa obrigatória <span class="text-danger">*</span></label>
            <textarea
              id="f-observacao"
              class="form-control form-control-sm"
              rows="3"
              placeholder="Informe a cláusula do acordo, a página do PDF consultada, o trecho relevante ou o motivo da decisão. Ex: Cláusula 5ª, pág. 12 do PDF — reajuste de 5,5% a partir de jan/2025."
            ></textarea>
          </div>
        </div>
        <div id="validate-error" class="alert alert-danger mt-2 d-none small py-2" role="alert"></div>
        <div class="mt-3">
          <button type="submit" class="btn btn-primary btn-sm">✔ Validar</button>
        </div>
      </form>
    </div>`;

  return html;
}

function buildChecklist(r) {
  const checkFields = [
    ['Percentual de reajuste', r.percentual_reajuste],
    ['Data-base', r.data_base],
    ['Vigência início', r.vigencia_inicio],
    ['Vigência fim', r.vigencia_fim],
    ['Observação / justificativa', r.observacao],
  ];
  let html = '<div class="review-checklist">';
  checkFields.forEach(([label, val]) => {
    const missing = val == null || String(val).trim() === '';
    html += `
      <div class="checklist-item ${missing ? 'item-missing' : 'item-ok'}">
        <span class="checklist-icon">${missing ? '⬜' : '✔'}</span>
        ${escHtml(label)}
      </div>`;
  });
  html += '</div>';
  return html;
}

function buildPdfButton(r) {
  if (!r.fonte_documento) {
    return '<p class="mt-2 small text-muted">Fonte do documento não disponível para este registro.</p>';
  }
  const isUrl = /^https?:\/\//i.test(r.fonte_documento);
  if (isUrl) {
    return `<div class="mt-2"><button type="button" id="btn-open-pdf" class="btn btn-outline-secondary btn-sm">📄 Abrir PDF</button></div>`;
  }
  return `
    <div class="mt-2 d-flex align-items-center gap-2 flex-wrap">
      <button type="button" id="btn-open-pdf" class="btn btn-outline-secondary btn-sm">📄 Abrir PDF</button>
      <span class="text-muted small">${escHtml(r.fonte_documento)}</span>
    </div>`;
}

// ── Helpers ──────────────────────────────────────────────────────────

function statusBadge(record) {
  const isConflict = record.status_parametro === 'conflito' || record.conflito === true;
  if (isConflict) {
    return '<span class="badge-conflito">⚠ Conflito</span>';
  }
  if (record.status_parametro === 'pendente_revisao') {
    return '<span class="badge-pendente">⏳ Pendente revisão</span>';
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

// ── Validation & localStorage ────────────────────────────────────────

function handleValidate(record) {
  const elPercentual = document.getElementById('f-percentual');
  const elDataBase = document.getElementById('f-data-base');
  const elVigInicio = document.getElementById('f-vigencia-inicio');
  const elVigFim = document.getElementById('f-vigencia-fim');
  const elObservacao = document.getElementById('f-observacao');
  const elError = document.getElementById('validate-error');

  const percentualRaw = elPercentual.value.trim();
  const dataBase = elDataBase.value.trim();
  const vigInicio = elVigInicio.value.trim();
  const vigFim = elVigFim.value.trim();
  const observacao = elObservacao.value.trim();

  const missing = [];
  if (!percentualRaw) missing.push('Percentual de reajuste');
  if (!dataBase) missing.push('Data-base');
  if (!vigInicio) missing.push('Vigência início');
  if (!vigFim) missing.push('Vigência fim');
  if (!observacao) missing.push('Observação');

  if (missing.length > 0) {
    elError.textContent = `Campos obrigatórios não preenchidos: ${missing.join(', ')}.`;
    elError.classList.remove('d-none');
    return;
  }

  const percentual = parseFloat(percentualRaw.replace(',', '.'));
  if (isNaN(percentual)) {
    elError.textContent = 'Percentual de reajuste deve ser um número válido.';
    elError.classList.remove('d-none');
    return;
  }

  if (vigInicio > vigFim) {
    elError.textContent = 'Vigência início não pode ser posterior à vigência fim.';
    elError.classList.remove('d-none');
    return;
  }

  elError.classList.add('d-none');

  const statusAnterior = record.status_parametro;

  record.percentual_reajuste = percentual;
  record.data_base = dataBase;
  record.vigencia_inicio = vigInicio;
  record.vigencia_fim = vigFim;
  record.observacao = observacao;
  record.status_parametro = 'valido';
  record.conflito = false;
  record.ids_registros_conflitantes = null;
  record.origem_atualizacao = 'validacao_manual_tela';
  record.data_hora_validacao_manual = new Date().toISOString();
  record.status_anterior = statusAnterior;

  // Assign a generated ID for records that had none (e.g. conflict records)
  if (record.id_registro_reajuste == null) {
    record.id_registro_reajuste = `MANUAL-${Date.now()}`;
  }

  saveToLocalStorage();
  showLocalChangesBanner();
  renderTable();

  if (detailModal) detailModal.hide();
}

function saveToLocalStorage() {
  try {
    const payload = {
      dataGeracao: currentDataGeracao,
      records: allRecords,
    };
    localStorage.setItem(LS_KEY, JSON.stringify(payload));
    setActionButtonsState(true);
  } catch (e) {
    console.warn('Não foi possível salvar no localStorage:', e);
  }
}

function loadFromLocalStorage(freshRecords, dataGeracao) {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return freshRecords;
    const payload = JSON.parse(raw);
    if (
      !Array.isArray(payload.records) ||
      payload.records.length === 0 ||
      payload.dataGeracao !== dataGeracao
    ) {
      return freshRecords;
    }
    setActionButtonsState(true);
    return payload.records;
  } catch {
    return freshRecords;
  }
}

function showLocalChangesBanner() {
  document.getElementById('local-changes-banner').classList.remove('d-none');
  setActionButtonsState(true);
}

function setActionButtonsState(hasChanges) {
  const btnExport = document.getElementById('btn-export-json');
  const btnDiscard = document.getElementById('btn-discard-local');
  if (btnExport) btnExport.disabled = !hasChanges;
  if (btnDiscard) btnDiscard.disabled = !hasChanges;
}

function openPdf(fonte) {
  if (!fonte) {
    alert('Fonte do documento não disponível para este registro.');
    return;
  }
  window.open(fonte, '_blank', 'noopener,noreferrer');
}

// ── Export & Discard ─────────────────────────────────────────────────

function exportJson() {
  const exportData = {
    data_geracao: new Date().toISOString(),
    registros: allRecords,
  };
  const json = JSON.stringify(exportData, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  const dateStr = new Date().toISOString().slice(0, 10);
  a.download = `base_parametros_sindicais_${dateStr}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function discardLocalChanges() {
  if (
    !confirm(
      'Descartar todas as alterações locais?\nOs dados serão restaurados para a base original carregada e as alterações salvas no navegador serão apagadas.',
    )
  ) {
    return;
  }
  allRecords = JSON.parse(JSON.stringify(originalRecords));
  try {
    localStorage.removeItem(LS_KEY);
  } catch {
    // ignore
  }
  document.getElementById('local-changes-banner').classList.add('d-none');
  setActionButtonsState(false);
  renderTable();
}
