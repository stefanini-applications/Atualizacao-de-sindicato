/* app.js - Tela de Consulta de Parâmetros Sindicais */

const DATA_URL = 'data/base_parametros_sindicais.json';
const EXAMPLE_DATA_URL = 'data/base_parametros_sindicais.example.json';
const OVERRIDES_KEY = 'parametros_sindicais_overrides';

// Fields persisted by local overrides (audit + status fields)
const OVERRIDE_FIELDS = [
  'status_parametro', 'conflito', 'ids_registros_conflitantes',
  'percentual_reajuste', 'data_base', 'vigencia_inicio', 'vigencia_fim',
  'observacao', 'ano_referencia', 'aplicado_em',
  'origem_atualizacao', 'data_hora_validacao_manual', 'data_hora_rejeicao_manual',
  'status_anterior',
];

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
      id_registro_reajuste: 'DEMO-003',
      ids_registros_conflitantes: ['DEMO-004'],
      sindicato: 'SENALBA-RJ',
      uf: 'RJ',
      categoria: 'Trabalhadores em Empresas de Asseio e Conservação',
      ano_referencia: 2025,
      status_parametro: 'conflito',
      conflito: true,
      percentual_reajuste: 4.8,
      data_base: '2025-01-01',
      vigencia_inicio: '2025-01-01',
      vigencia_fim: '2025-12-31',
      fonte_documento: 'CCT/RJ/Senalba/CCT_SENALBA_RJ_2025_v1.pdf',
      observacao:
        'Dois documentos distintos apresentam percentuais divergentes: 4,80% vs 5,20%. Requer verificação manual.',
    },
    {
      id_registro_reajuste: 'DEMO-004',
      ids_registros_conflitantes: ['DEMO-003'],
      sindicato: 'SENALBA-RJ',
      uf: 'RJ',
      categoria: 'Trabalhadores em Empresas de Asseio e Conservação',
      ano_referencia: 2025,
      status_parametro: 'conflito',
      conflito: true,
      percentual_reajuste: 5.2,
      data_base: '2025-01-01',
      vigencia_inicio: '2025-01-01',
      vigencia_fim: '2025-12-31',
      fonte_documento: 'CCT/RJ/Senalba/CCT_SENALBA_RJ_2025_aditivo.pdf',
      observacao:
        'Dois documentos distintos apresentam percentuais divergentes: 4,80% vs 5,20%. Requer verificação manual.',
    },
    {
      id_registro_reajuste: 'PEND-DEMO-001',
      ids_registros_conflitantes: null,
      sindicato: 'Sindtest-Demo',
      uf: 'SP',
      categoria: 'Tecnologia da Informação',
      ano_referencia: 2025,
      status_parametro: 'pendente_revisao',
      conflito: false,
      percentual_reajuste: 5.75,
      data_base: '2025-03-01',
      vigencia_inicio: '2025-03-01',
      vigencia_fim: '2026-02-28',
      fonte_documento: 'CCT/SP/Sindtest-Demo/CCT_2025_Sindtest_Demo.pdf',
      observacao: 'Parâmetros extraídos automaticamente — aguardando conferência manual',
    },
    {
      id_registro_reajuste: 'PEND-DEMO-002',
      ids_registros_conflitantes: null,
      sindicato: 'Sindtest-Vazio',
      uf: 'SP',
      categoria: null,
      ano_referencia: null,
      status_parametro: 'pendente_revisao',
      conflito: false,
      percentual_reajuste: null,
      data_base: null,
      vigencia_inicio: null,
      vigencia_fim: null,
      fonte_documento: 'CCT/SP/Sindtest-Vazio/CCT_2025_Sindtest_Vazio.pdf',
      observacao: 'Sindicato encontrado na pasta CCT, mas sem parâmetros extraídos disponíveis',
    },
  ],
};

let allRecords = [];
let filteredRecords = [];
let detailModal = null;
let modalFallbackHandlers = [];

let elLoading;
let elUnavailable;
let elApp;
let elDataGeracao;
let elTableBody;
let elEmptyState;
let elTotalRecords;

let filterUf;
let filterSindicato;
let filterAno;
let filterStatus;
let searchInput;

document.addEventListener('DOMContentLoaded', () => {
  bindElements();
  bindEvents();

  const modalElement = document.getElementById('detail-modal');

  if (window.bootstrap && modalElement) {
    detailModal = new bootstrap.Modal(modalElement);
  }

  loadData();
});

function bindElements() {
  elLoading = document.getElementById('state-loading');
  elUnavailable = document.getElementById('state-unavailable');
  elApp = document.getElementById('app');
  elDataGeracao = document.getElementById('data-geracao-badge');

  elTableBody = document.getElementById('params-tbody') || document.querySelector('tbody');

  elEmptyState = document.getElementById('no-results');

  elTotalRecords = document.getElementById('result-count');

  filterUf = document.getElementById('filter-uf');
  filterSindicato = document.getElementById('filter-sindicato');
  filterAno = document.getElementById('filter-ano');
  filterStatus = document.getElementById('filter-status');

  searchInput =
    document.getElementById('search-input') ||
    document.getElementById('busca') ||
    document.getElementById('search');
}

function bindEvents() {
  const filterElements = [
    filterUf,
    filterSindicato,
    filterAno,
    filterStatus,
    searchInput,
  ].filter(Boolean);

  filterElements.forEach((element) => {
    element.addEventListener('input', applyFilters);
    element.addEventListener('change', applyFilters);
  });

  const btnClearFilters = document.getElementById('btn-clear-filters');
  if (btnClearFilters) btnClearFilters.addEventListener('click', clearFilters);

  const btnExport = document.getElementById('btn-export-data');
  if (btnExport) btnExport.addEventListener('click', exportData);

  const btnDiscard = document.getElementById('btn-discard-changes');
  if (btnDiscard) btnDiscard.addEventListener('click', discardLocalChanges);
}

async function tryFetch(url) {
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  const text = await response.text();

  if (!text.trim()) {
    throw new Error('Empty file');
  }

  const data = JSON.parse(text);
  const records = Array.isArray(data) ? data : data.registros;

  if (!Array.isArray(records)) {
    throw new Error('Invalid structure');
  }

  return {
    data,
    records,
  };
}

async function loadData() {
  let records = null;
  let dataGeracao = null;
  let demoMessage = null;

  // Prefer inline data injected by export_inline_data.py (works with file:// protocol)
  if (window.BASE_PARAMETROS_SINDICAIS) {
    const inlineData = window.BASE_PARAMETROS_SINDICAIS;
    records = Array.isArray(inlineData) ? inlineData : inlineData.registros;
    dataGeracao = inlineData.data_geracao ?? null;
  }

  if (!Array.isArray(records)) {
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
        records = EMBEDDED_DEMO.registros;
        dataGeracao = EMBEDDED_DEMO.data_geracao;
        demoMessage = 'Ambiente de demonstração — base embutida para teste local';
      }
    }
  }

  if (!Array.isArray(records)) {
    showUnavailable();
    return;
  }

  allRecords = records;
  loadLocalOverrides(allRecords);
  filteredRecords = [...allRecords];

  showApp(dataGeracao, demoMessage);
  populateFilterOptions();
  renderTable();
}

function showUnavailable() {
  if (elLoading) elLoading.classList.add('d-none');
  if (elApp) elApp.classList.add('d-none');
  if (elUnavailable) elUnavailable.classList.remove('d-none');
}

function getRecordKey(record) {
  if (record.id_registro_reajuste) return record.id_registro_reajuste;
  // Stable composite key for records without an assigned ID
  return 'composite:' + JSON.stringify([
    record.sindicato ?? null,
    record.uf ?? null,
    record.categoria ?? null,
    record.ano_referencia ?? null,
  ]);
}

function loadLocalOverrides(records) {
  try {
    const raw = localStorage.getItem(OVERRIDES_KEY);
    if (!raw) return;
    const overrides = JSON.parse(raw);
    records.forEach((record) => {
      const isReviewable =
        record.status_parametro === 'pendente_revisao' ||
        record.status_parametro === 'conflito' ||
        record.conflito === true;
      const key = getRecordKey(record);
      if (key && overrides[key] && isReviewable) {
        const safe = {};
        OVERRIDE_FIELDS.forEach((field) => {
          if (field in overrides[key]) safe[field] = overrides[key][field];
        });
        Object.assign(record, safe);
      }
    });
  } catch {
    // ignore malformed localStorage
  }
}

function saveLocalOverride(key, fields) {
  try {
    const raw = localStorage.getItem(OVERRIDES_KEY) || '{}';
    const overrides = JSON.parse(raw);
    // Persist only whitelisted fields to avoid storing stale source data
    const safe = {};
    OVERRIDE_FIELDS.forEach((field) => {
      if (field in fields) safe[field] = fields[field];
    });
    overrides[key] = safe;
    localStorage.setItem(OVERRIDES_KEY, JSON.stringify(overrides));
  } catch {
    // ignore localStorage errors (e.g. private mode, quota exceeded)
  }
}

function showApp(dataGeracao, demoMessage = null) {
  if (elLoading) elLoading.classList.add('d-none');
  if (elUnavailable) elUnavailable.classList.add('d-none');
  if (elApp) elApp.classList.remove('d-none');

  const existingBanner = document.getElementById('demo-banner');

  if (demoMessage && elApp) {
    let demoBanner = existingBanner;

    if (!demoBanner) {
      demoBanner = document.createElement('div');
      demoBanner.id = 'demo-banner';
      demoBanner.className = 'alert alert-warning text-center mb-3';
      demoBanner.setAttribute('role', 'alert');
      elApp.insertAdjacentElement('afterbegin', demoBanner);
    }

    demoBanner.textContent = demoMessage;
  } else if (existingBanner) {
    existingBanner.remove();
  }

  if (elDataGeracao && dataGeracao) {
    elDataGeracao.textContent = `Base gerada em: ${formatDateTime(dataGeracao)}`;
    elDataGeracao.classList.remove('d-none');
  } else if (elDataGeracao) {
    elDataGeracao.classList.add('d-none');
  }

  updateLocalChangesBanner();
}

function populateFilterOptions() {
  populateSelect(filterUf, uniqueValues(allRecords, 'uf'), 'Todas as UFs');
  populateSelect(filterSindicato, uniqueValues(allRecords, 'sindicato'), 'Todos os sindicatos');
  populateSelect(filterAno, uniqueValues(allRecords, 'ano_referencia'), 'Todos os anos');
  populateSelect(filterStatus, ['valido', 'conflito', 'pendente_revisao'], 'Todos os status');
}

function populateSelect(selectElement, values, defaultLabel) {
  if (!selectElement) return;

  const currentValue = selectElement.value;

  selectElement.innerHTML = '';

  const defaultOption = document.createElement('option');
  defaultOption.value = '';
  defaultOption.textContent = defaultLabel;
  selectElement.appendChild(defaultOption);

  values.forEach((value) => {
    if (value === null || value === undefined || value === '') return;

    const option = document.createElement('option');
    option.value = String(value);
    option.textContent = formatSelectLabel(value);
    selectElement.appendChild(option);
  });

  selectElement.value = currentValue;
}

function uniqueValues(records, fieldName) {
  return [...new Set(records.map((record) => record[fieldName]))]
    .filter((value) => value !== null && value !== undefined && value !== '')
    .sort((a, b) => String(a).localeCompare(String(b), 'pt-BR'));
}

function formatSelectLabel(value) {
  if (value === 'valido') return 'Válido';
  if (value === 'conflito') return 'Conflito';
  if (value === 'pendente_revisao') return 'Pendente revisão';
  return String(value);
}

function applyFilters() {
  const ufValue = filterUf?.value ?? '';
  const sindicatoValue = filterSindicato?.value ?? '';
  const anoValue = filterAno?.value ?? '';
  const statusValue = filterStatus?.value ?? '';
  const searchValue = normalizeText(searchInput?.value ?? '');

  filteredRecords = allRecords.filter((record) => {
    const isConflict = isConflictRecord(record);
    const status = record.status_parametro === 'pendente_revisao'
      ? 'pendente_revisao'
      : isConflict ? 'conflito' : 'valido';

    const matchesUf = !ufValue || String(record.uf ?? '') === ufValue;
    const matchesSindicato =
      !sindicatoValue || String(record.sindicato ?? '') === sindicatoValue;
    const matchesAno =
      !anoValue || String(record.ano_referencia ?? '') === anoValue;
    const matchesStatus = !statusValue || status === statusValue;

    const searchableText = normalizeText(
      [
        record.sindicato,
        record.uf,
        record.categoria,
        record.ano_referencia,
        record.status_parametro,
        record.fonte_documento,
        record.observacao,
      ].join(' ')
    );

    const matchesSearch = !searchValue || searchableText.includes(searchValue);

    return (
      matchesUf &&
      matchesSindicato &&
      matchesAno &&
      matchesStatus &&
      matchesSearch
    );
  });

  renderTable();
}

function renderTable() {
  if (!elTableBody) return;

  elTableBody.innerHTML = '';

  if (elTotalRecords) {
    const total = filteredRecords.length;
    elTotalRecords.textContent = `${total} registro${total !== 1 ? 's' : ''} encontrado${total !== 1 ? 's' : ''}`;
  }

  if (elEmptyState) {
    elEmptyState.classList.toggle('d-none', filteredRecords.length > 0);
  }

  filteredRecords.forEach((record, index) => {
    const isConflict = isConflictRecord(record);
    const row = document.createElement('tr');

    if (isConflict) {
      row.classList.add('row-conflito');
    }

    if (record.status_parametro === 'pendente_revisao') {
      row.classList.add('row-pendente');
    }

    const isReviewable = isConflict || record.status_parametro === 'pendente_revisao';
    const btnClass = isReviewable ? 'btn btn-sm btn-warning' : 'btn btn-sm btn-outline-primary';
    const btnLabel = isReviewable ? '🔍 Revisar' : 'Detalhes';

    row.innerHTML = `
      <td>${escapeHtml(record.uf ?? '—')}</td>
      <td>${escapeHtml(record.sindicato ?? '—')}</td>
      <td>${escapeHtml(record.categoria ?? '—')}</td>
      <td>${escapeHtml(record.ano_referencia ?? '—')}</td>
      <td>${formatPercent(record.percentual_reajuste)}</td>
      <td>${formatDate(record.data_base)}</td>
      <td>${formatDate(record.vigencia_inicio)}</td>
      <td>${formatDate(record.vigencia_fim)}</td>
      <td>${buildStatusBadge(record)}</td>
      <td class="fonte-cell">${buildFonteLink(record.fonte_documento)}</td>
      <td>
        <button type="button" class="${btnClass}" data-index="${index}">
          ${btnLabel}
        </button>
      </td>
    `;

    const detailButton = row.querySelector('button[data-index]');
    detailButton.addEventListener('click', (e) => {
      e.stopPropagation();
      openDetail(record);
    });

    if (isReviewable) {
      row.addEventListener('click', (e) => {
        if (e.target.closest('a') || e.target.closest('.fonte-cell a')) return;
        openDetail(record);
      });
    }

    elTableBody.appendChild(row);
  });
}

function isConflictRecord(record) {
  return record.status_parametro === 'conflito' || record.conflito === true;
}

function buildStatusBadge(record) {
  if (record.status_parametro === 'pendente_revisao') {
    return '<span class="badge badge-pendente">⏳ Pendente revisão</span>';
  }
  if (isConflictRecord(record)) {
    return '<span class="badge badge-conflito">⚠ Conflito</span>';
  }
  return '<span class="badge badge-valido">✔ Válido</span>';
}

function openDetail(record) {
  const isPending = record.status_parametro === 'pendente_revisao';
  const isConflict = isConflictRecord(record);
  const isReviewable = isPending || isConflict;
  const modalBody = document.getElementById('detail-modal-body');
  const modalTitle = document.getElementById('detail-modal-label');

  if (modalTitle) {
    const titlePrefix = isReviewable ? 'Revisão' : 'Detalhe do parâmetro';
    modalTitle.textContent = `${titlePrefix} — ${record.sindicato ?? '—'} — ${record.uf ?? '—'} (${record.ano_referencia ?? '—'})`;
  }

  if (modalBody) {
    modalBody.innerHTML = buildDetailHtml(record, isConflict);

    if (isReviewable) {
      bindReviewControls(record);
    }
  }

  showDetailModal();
}

function showDetailModal() {
  if (detailModal) {
    try {
      detailModal.show();
      return;
    } catch (_) {
      // fall through to manual fallback
    }
  }

  const modalEl = document.getElementById('detail-modal');
  if (!modalEl) {
    showModalError('Não foi possível abrir o painel de revisão.');
    return;
  }

  // Clean up any previous fallback listeners before attaching new ones
  modalFallbackHandlers.forEach(({ el, fn, evt }) => el.removeEventListener(evt, fn));
  modalFallbackHandlers = [];

  // Show the modal with inline styles so it works even if Bootstrap CSS is unavailable
  modalEl.style.display = 'block';
  modalEl.style.position = 'fixed';
  modalEl.style.inset = '0';
  modalEl.style.zIndex = '1055';
  modalEl.style.overflowX = 'hidden';
  modalEl.style.overflowY = 'auto';
  modalEl.style.background = 'rgba(0,0,0,0.5)';
  modalEl.classList.add('show');
  document.body.classList.add('modal-open');
  document.body.style.overflow = 'hidden';

  // Escape key
  const keyHandler = (e) => { if (e.key === 'Escape') hideDetailModal(); };
  document.addEventListener('keydown', keyHandler);
  modalFallbackHandlers.push({ el: document, fn: keyHandler, evt: 'keydown' });

  // Backdrop click — only close when the click is directly on the modal overlay
  const backdropHandler = (e) => { if (e.target === modalEl) hideDetailModal(); };
  modalEl.addEventListener('click', backdropHandler);
  modalFallbackHandlers.push({ el: modalEl, fn: backdropHandler, evt: 'click' });

  // Close buttons
  modalEl.querySelectorAll('[data-bs-dismiss="modal"], .btn-close').forEach((btn) => {
    btn.addEventListener('click', hideDetailModal);
    modalFallbackHandlers.push({ el: btn, fn: hideDetailModal, evt: 'click' });
  });
}

function hideDetailModal() {
  if (detailModal) {
    try {
      detailModal.hide();
      return;
    } catch (_) {
      // fall through to manual fallback
    }
  }

  const modalEl = document.getElementById('detail-modal');
  if (modalEl) {
    modalEl.style.display = '';
    modalEl.style.position = '';
    modalEl.style.inset = '';
    modalEl.style.zIndex = '';
    modalEl.style.overflowX = '';
    modalEl.style.overflowY = '';
    modalEl.style.background = '';
    modalEl.classList.remove('show');
  }

  document.body.classList.remove('modal-open');
  document.body.style.overflow = '';

  modalFallbackHandlers.forEach(({ el, fn, evt }) => el.removeEventListener(evt, fn));
  modalFallbackHandlers = [];
}

function showModalError(message) {
  let errEl = document.getElementById('modal-open-error');
  if (!errEl) {
    errEl = document.createElement('div');
    errEl.id = 'modal-open-error';
    errEl.className = 'alert alert-danger';
    errEl.style.cssText =
      'position:fixed;top:1rem;left:50%;transform:translateX(-50%);z-index:9999;min-width:20rem;text-align:center;';
    document.body.appendChild(errEl);
  }
  errEl.textContent = message;
  errEl.style.display = 'block';
  setTimeout(() => { if (errEl) errEl.style.display = 'none'; }, 6000);
}

function buildDetailHtml(record, isConflict) {
  const isPending = record.status_parametro === 'pendente_revisao';
  const isReviewable = isPending || isConflict;
  const conflictSection = isConflict ? buildConflictSection(record) : '';
  const reviewSection = isReviewable ? buildReviewSection(record) : '';

  return `
    <div class="mb-3">
      ${buildStatusBadge(record)}
    </div>

    ${conflictSection}
    ${reviewSection}

    <dl class="row">
      <dt class="col-sm-4">ID do registro</dt>
      <dd class="col-sm-8">${escapeHtml(record.id_registro_reajuste ?? '—')}</dd>

      <dt class="col-sm-4">Sindicato</dt>
      <dd class="col-sm-8">${escapeHtml(record.sindicato ?? '—')}</dd>

      <dt class="col-sm-4">UF</dt>
      <dd class="col-sm-8">${escapeHtml(record.uf ?? '—')}</dd>

      <dt class="col-sm-4">Categoria</dt>
      <dd class="col-sm-8">${escapeHtml(record.categoria ?? '—')}</dd>

      ${!isReviewable ? `
      <dt class="col-sm-4">Ano de referência</dt>
      <dd class="col-sm-8">${escapeHtml(record.ano_referencia ?? '—')}</dd>

      <dt class="col-sm-4">Percentual de reajuste</dt>
      <dd class="col-sm-8">${formatPercent(record.percentual_reajuste)}</dd>

      <dt class="col-sm-4">Data-base</dt>
      <dd class="col-sm-8">${formatDate(record.data_base)}</dd>

      <dt class="col-sm-4">Vigência início</dt>
      <dd class="col-sm-8">${formatDate(record.vigencia_inicio)}</dd>

      <dt class="col-sm-4">Vigência fim</dt>
      <dd class="col-sm-8">${formatDate(record.vigencia_fim)}</dd>

      <dt class="col-sm-4">Fonte do documento</dt>
      <dd class="col-sm-8">${buildFonteLink(record.fonte_documento)}</dd>
      ` : ''}
    </dl>
  `;
}

function buildConflictSection(record) {
  const conflictingIds = Array.isArray(record.ids_registros_conflitantes)
    ? record.ids_registros_conflitantes
    : (record.ids_registros_conflitantes ? [record.ids_registros_conflitantes] : []);

  const idBadges = conflictingIds.length > 0
    ? conflictingIds.map((id) => {
        if (isPdfPath(id)) {
          return `<a href="${escapeHtml(id)}" target="_blank" rel="noopener noreferrer" class="conflicting-id conflict-pdf-link">${escapeHtml(pdfLabel(id))}</a>`;
        }
        return `<span class="conflicting-id">${escapeHtml(id)}</span>`;
      }).join(' ')
    : '<span class="text-secondary">—</span>';

  return `
    <div class="detail-conflict-box mb-3" role="alert" aria-label="Informações do conflito">
      <h3 class="conflict-section-title">⚠ Informações do conflito</h3>
      <p class="conflict-warning-msg">
        Este parâmetro possui conflito e não deve ser usado para precificação até revisão manual.
      </p>
      <div>
        <span class="detail-field-label">Registros conflitantes:</span>
        <div class="mt-1">${idBadges}</div>
      </div>
    </div>
  `;
}

function buildPdfViewer(record) {
  if (!record.fonte_documento) {
    return `<p class="text-secondary small mb-0">Nenhum documento de origem disponível.</p>`;
  }

  if (!isPdfPath(record.fonte_documento)) {
    return `<p class="text-secondary small mb-0">Fonte: ${escapeHtml(record.fonte_documento)}</p>`;
  }

  const fonteUrl = escapeHtml(record.fonte_documento);
  const fonteLbl = escapeHtml(pdfLabel(record.fonte_documento));

  return `
    <div class="pdf-viewer-container mb-2">
      <div class="d-flex align-items-center justify-content-between mb-1">
        <span class="detail-field-label">Documento de origem</span>
        <a href="${fonteUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-outline-secondary py-0 px-2">
          📄 Abrir PDF em nova aba
        </a>
      </div>
      <iframe
        src="${fonteUrl}"
        class="pdf-iframe"
        title="PDF de origem: ${fonteLbl}"
        aria-label="PDF de origem: ${fonteLbl}"
      ></iframe>
    </div>
  `;
}

function buildReviewSection(record) {
  const isPending = record.status_parametro === 'pendente_revisao';
  const titleIcon = isPending ? '⏳' : '🔍';
  const titleText = isPending ? 'Conferência — pendente de revisão' : 'Conferência — conflito';

  const percentualValue = (record.percentual_reajuste !== null && record.percentual_reajuste !== undefined)
    ? escapeHtml(String(record.percentual_reajuste))
    : '';
  const dataBaseValue = record.data_base ? escapeHtml(record.data_base) : '';
  const vigenciaInicioValue = record.vigencia_inicio ? escapeHtml(record.vigencia_inicio) : '';
  const vigenciaFimValue = record.vigencia_fim ? escapeHtml(record.vigencia_fim) : '';
  const anoReferenciaValue = (record.ano_referencia !== null && record.ano_referencia !== undefined)
    ? escapeHtml(String(record.ano_referencia))
    : '';

  return `
    <div class="detail-review-box mb-3" role="region" aria-label="Conferência de dados extraídos">
      <h3 class="review-section-title">${titleIcon} ${escapeHtml(titleText)}</h3>
      <p class="review-info-msg">
        Confira os dados abaixo com o documento de origem. Preencha ou corrija os campos
        necessários, marque o checkbox e preencha a observação para habilitar a validação.
      </p>

      ${buildPdfViewer(record)}

      <hr class="my-3" />

      <h4 class="review-data-title">Dados para conferência</h4>
      <div class="row g-3 mb-3">
        <div class="col-sm-6">
          <label for="review-input-percentual" class="form-label form-label-sm fw-semibold">
            Percentual de reajuste (%) <span class="text-danger">*</span>
          </label>
          <input
            type="number"
            class="form-control form-control-sm"
            id="review-input-percentual"
            step="0.01"
            min="0"
            placeholder="Ex: 5.50"
            value="${percentualValue}"
          />
        </div>
        <div class="col-sm-6">
          <label for="review-input-data-base" class="form-label form-label-sm fw-semibold">
            Data-base <span class="text-danger">*</span>
          </label>
          <input
            type="date"
            class="form-control form-control-sm"
            id="review-input-data-base"
            value="${dataBaseValue}"
          />
        </div>
        <div class="col-sm-6">
          <label for="review-input-vigencia-inicio" class="form-label form-label-sm fw-semibold">
            Vigência início <span class="text-danger">*</span>
          </label>
          <input
            type="date"
            class="form-control form-control-sm"
            id="review-input-vigencia-inicio"
            value="${vigenciaInicioValue}"
          />
        </div>
        <div class="col-sm-6">
          <label for="review-input-vigencia-fim" class="form-label form-label-sm fw-semibold">
            Vigência fim <span class="text-danger">*</span>
          </label>
          <input
            type="date"
            class="form-control form-control-sm"
            id="review-input-vigencia-fim"
            value="${vigenciaFimValue}"
          />
        </div>
        <div class="col-sm-6">
          <label for="review-input-ano-referencia" class="form-label form-label-sm fw-semibold">
            Ano de referência
          </label>
          <input
            type="number"
            class="form-control form-control-sm"
            id="review-input-ano-referencia"
            step="1"
            min="2000"
            placeholder="Ex: 2025"
            value="${anoReferenciaValue}"
          />
        </div>
      </div>

      <hr class="my-3" />

      <div class="mb-3">
        <label for="review-observacao" class="form-label form-label-sm fw-semibold">
          Observação <span class="text-danger">*</span>
        </label>
        <textarea
          class="form-control form-control-sm"
          id="review-observacao"
          rows="3"
          placeholder="Ex: cláusula consultada, página do PDF, trecho relevante, motivo da decisão"
        >${escapeHtml(record.observacao ?? '')}</textarea>
        <div class="form-text">Obrigatório. Descreva a evidência consultada e o motivo da decisão.</div>
      </div>

      <div id="review-action-error" class="alert alert-danger py-2 small d-none mb-2" role="alert"></div>

      <div class="d-flex gap-2 flex-wrap">
        <button type="button" class="btn btn-success btn-sm" id="btn-aplicar">
          ✔ Aplicar
        </button>
        <button type="button" class="btn btn-outline-warning btn-sm" id="btn-reject-pending">
          ✗ Rejeitar / manter pendente
        </button>
      </div>

      <div id="review-local-notice" class="d-none mt-3 alert alert-info py-2 small" role="alert">
        Alteração aplicada localmente. Para tornar definitiva, exporte a base atualizada e submeta para validação/commit.
      </div>
    </div>
  `;
}

function bindReviewControls(record) {
  const btnAplicar = document.getElementById('btn-aplicar');
  const btnReject = document.getElementById('btn-reject-pending');

  if (btnAplicar) {
    btnAplicar.addEventListener('click', () => validateRecord(record));
  }
  if (btnReject) {
    btnReject.addEventListener('click', () => rejectRecord(record));
  }
}

function validateRecord(record) {
  const observacaoEl = document.getElementById('review-observacao');
  const percentualEl = document.getElementById('review-input-percentual');
  const dataBaseEl = document.getElementById('review-input-data-base');
  const vigenciaInicioEl = document.getElementById('review-input-vigencia-inicio');
  const vigenciaFimEl = document.getElementById('review-input-vigencia-fim');
  const anoReferenciaEl = document.getElementById('review-input-ano-referencia');
  const errorEl = document.getElementById('review-action-error');

  const observacao = observacaoEl?.value?.trim() ?? '';
  const percentualStr = percentualEl?.value?.trim() ?? '';
  const dataBase = dataBaseEl?.value?.trim() ?? '';
  const vigenciaInicio = vigenciaInicioEl?.value?.trim() ?? '';
  const vigenciaFim = vigenciaFimEl?.value?.trim() ?? '';
  const anoReferenciaStr = anoReferenciaEl?.value?.trim() ?? '';

  const missingData = [];
  if (!percentualStr) missingData.push('Percentual de reajuste');
  if (!dataBase) missingData.push('Data-base');
  if (!vigenciaInicio) missingData.push('Vigência início');
  if (!vigenciaFim) missingData.push('Vigência fim');
  if (!observacao) missingData.push('Observação');

  if (missingData.length > 0) {
    if (errorEl) {
      errorEl.textContent =
        `Não é possível validar: campos obrigatórios ausentes — ${missingData.join(', ')}.`;
      errorEl.classList.remove('d-none');
    }
    return;
  }

  if (errorEl) errorEl.classList.add('d-none');

  const now = new Date().toISOString();
  const statusAnterior = record.status_parametro;
  const percentualNum = parseFloat(percentualStr);

  let anoReferencia;
  if (anoReferenciaStr === '') {
    anoReferencia = null;
  } else {
    const parsedAno = Number(anoReferenciaStr);
    anoReferencia = Number.isInteger(parsedAno) && parsedAno >= 2000 ? parsedAno : (record.ano_referencia ?? null);
  }

  const overrideFields = {
    status_parametro: 'valido',
    conflito: false,
    ids_registros_conflitantes: null,
    origem_atualizacao: 'validacao_manual_tela',
    data_hora_validacao_manual: now,
    status_anterior: statusAnterior,
    observacao: observacao,
    percentual_reajuste: Number.isNaN(percentualNum) ? null : percentualNum,
    data_base: dataBase,
    vigencia_inicio: vigenciaInicio,
    vigencia_fim: vigenciaFim,
    ano_referencia: anoReferencia,
  };

  // Capture stable key BEFORE mutating the record (composite key may include ano_referencia)
  const recordKey = getRecordKey(record);
  Object.assign(record, overrideFields);
  saveLocalOverride(recordKey, overrideFields);

  updateLocalChangesBanner();
  populateFilterOptions();
  applyFilters();

  hideDetailModal();
}

function rejectRecord(record) {
  const observacaoEl = document.getElementById('review-observacao');
  const btnValidate = document.getElementById('btn-validate-info');
  const btnReject = document.getElementById('btn-reject-pending');
  const noticeEl = document.getElementById('review-local-notice');
  const errorEl = document.getElementById('review-action-error');
  const observacao = observacaoEl?.value?.trim() ?? '';

  if (errorEl) errorEl.classList.add('d-none');

  const now = new Date().toISOString();
  const statusAnterior = record.status_parametro;

  const overrideFields = {
    status_parametro: record.status_parametro,
    origem_atualizacao: 'rejeicao_manual_tela',
    data_hora_rejeicao_manual: now,
    status_anterior: statusAnterior,
    observacao: observacao,
  };

  Object.assign(record, overrideFields);
  saveLocalOverride(getRecordKey(record), overrideFields);

  // Disable buttons to prevent double-submission
  if (btnValidate) btnValidate.disabled = true;
  if (btnReject) btnReject.disabled = true;

  if (noticeEl) noticeEl.classList.remove('d-none');

  updateLocalChangesBanner();
  applyFilters();
}

function exportData() {
  const exportPayload = {
    data_geracao: new Date().toISOString(),
    registros: allRecords,
  };

  const json = JSON.stringify(exportPayload, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `base_parametros_sindicais_local_${new Date().toISOString().slice(0, 10)}.json`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

function discardLocalChanges() {
  if (!confirm('Descartar todas as alterações locais? Os dados serão restaurados para o estado original da base.')) {
    return;
  }
  try {
    localStorage.removeItem(OVERRIDES_KEY);
  } catch {
    // ignore
  }
  window.location.reload();
}

function updateLocalChangesBanner() {
  const banner = document.getElementById('local-changes-banner');
  if (!banner) return;

  let hasOverrides = false;
  try {
    const raw = localStorage.getItem(OVERRIDES_KEY);
    if (raw) {
      const overrides = JSON.parse(raw);
      hasOverrides = Object.keys(overrides).length > 0;
    }
  } catch {
    // ignore
  }

  banner.classList.toggle('d-none', !hasOverrides);
}

function clearFilters() {
  if (filterUf) filterUf.value = '';
  if (filterSindicato) filterSindicato.value = '';
  if (filterAno) filterAno.value = '';
  if (filterStatus) filterStatus.value = '';
  if (searchInput) searchInput.value = '';
  applyFilters();
}

function isPdfPath(value) {
  return typeof value === 'string' && value.trim().toLowerCase().endsWith('.pdf');
}

function pdfLabel(path) {
  const parts = path.split('/');
  return parts[parts.length - 1] || path;
}

function buildFonteLink(value) {
  if (!value || typeof value !== 'string' || !value.trim()) {
    return '—';
  }

  if (isPdfPath(value)) {
    return `<a href="${escapeHtml(value)}" target="_blank" rel="noopener noreferrer" class="fonte-link">${escapeHtml(pdfLabel(value))}</a>`;
  }

  return `<span class="text-secondary">${escapeHtml(value)}</span>`;
}

function formatPercent(value) {
  if (value === null || value === undefined || value === '') {
    return '—';
  }

  const numericValue = Number(value);

  if (Number.isNaN(numericValue)) {
    return '—';
  }

  return `${numericValue.toLocaleString('pt-BR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}%`;
}

function formatDate(value) {
  if (!value) return '—';

  const date = new Date(`${value}T00:00:00`);

  if (Number.isNaN(date.getTime())) {
    return '—';
  }

  return date.toLocaleDateString('pt-BR');
}

function formatDateTime(value) {
  if (!value) return '—';

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return '—';
  }

  return date.toLocaleString('pt-BR');
}

function normalizeText(value) {
  return String(value)
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim();
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}
