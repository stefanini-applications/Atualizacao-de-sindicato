/* app.js - Tela de Consulta de Parâmetros Sindicais */

const DATA_URL = 'data/base_parametros_sindicais.json';
const EXAMPLE_DATA_URL = 'data/base_parametros_sindicais.example.json';
const OVERRIDES_KEY = 'parametros_sindicais_overrides';

// Fields that may be modified by manual parameter application
const OVERRIDE_FIELDS = [
  'status_parametro', 'conflito', 'percentual_reajuste', 'data_base',
  'vigencia_inicio', 'vigencia_fim', 'observacao', 'ano_referencia', 'aplicado_em',
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
      id_registro_reajuste: 'PEND-DEMO-001',
      ids_registros_conflitantes: null,
      sindicato: 'Sindtest-Demo',
      uf: 'SP',
      categoria: null,
      ano_referencia: null,
      status_parametro: 'pendente_revisao',
      conflito: false,
      percentual_reajuste: null,
      data_base: null,
      vigencia_inicio: null,
      vigencia_fim: null,
      fonte_documento: 'CCT/SP/Sindtest-Demo/CCT_2025_Sindtest_Demo.pdf',
      observacao: 'Sindicato encontrado na pasta CCT, mas sem parâmetro aprovado disponível',
    },
  ],
};

let allRecords = [];
let filteredRecords = [];
let detailModal = null;

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
  elDataGeracao = document.getElementById('data-geracao');

  elTableBody =
    document.getElementById('table-body') ||
    document.getElementById('parametros-table-body') ||
    document.getElementById('registros-tbody') ||
    document.querySelector('tbody');

  elEmptyState =
    document.getElementById('empty-state') ||
    document.getElementById('state-empty');

  elTotalRecords =
    document.getElementById('total-records') ||
    document.getElementById('records-count') ||
    document.getElementById('contador-registros');

  filterUf =
    document.getElementById('filter-uf') ||
    document.getElementById('uf-filter') ||
    document.getElementById('uf');

  filterSindicato =
    document.getElementById('filter-sindicato') ||
    document.getElementById('sindicato-filter') ||
    document.getElementById('sindicato');

  filterAno =
    document.getElementById('filter-ano') ||
    document.getElementById('ano-filter') ||
    document.getElementById('ano-referencia');

  filterStatus =
    document.getElementById('filter-status') ||
    document.getElementById('status-filter') ||
    document.getElementById('status');

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

function loadLocalOverrides(records) {
  try {
    const raw = localStorage.getItem(OVERRIDES_KEY);
    if (!raw) return;
    const overrides = JSON.parse(raw);
    records.forEach((record) => {
      const id = record.id_registro_reajuste;
      if (id && overrides[id] && record.status_parametro === 'pendente_revisao') {
        const safe = {};
        OVERRIDE_FIELDS.forEach((field) => {
          if (field in overrides[id]) safe[field] = overrides[id][field];
        });
        Object.assign(record, safe);
      }
    });
  } catch {
    // ignore malformed localStorage
  }
}

function saveLocalOverride(id, fields) {
  try {
    const raw = localStorage.getItem(OVERRIDES_KEY) || '{}';
    const overrides = JSON.parse(raw);
    overrides[id] = fields;
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
    elDataGeracao.textContent = `Data de atualização da base: ${formatDateTime(dataGeracao)}`;
    elDataGeracao.classList.remove('d-none');
  } else if (elDataGeracao) {
    elDataGeracao.classList.add('d-none');
  }
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
    elTotalRecords.textContent = String(filteredRecords.length);
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
        <button type="button" class="btn btn-sm btn-outline-primary" data-index="${index}">
          Detalhes
        </button>
      </td>
    `;

    const detailButton = row.querySelector('button[data-index]');
    detailButton.addEventListener('click', () => openDetail(record));

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
  const modalBody = document.getElementById('detail-modal-body');
  const modalTitle = document.getElementById('detail-modal-label');

  if (modalTitle) {
    modalTitle.textContent = `${record.sindicato ?? '—'} — ${record.uf ?? '—'} (${record.ano_referencia ?? '—'})`;
  }

  if (modalBody) {
    modalBody.innerHTML = buildDetailHtml(record, isConflict);

    if (isPending) {
      const form = modalBody.querySelector('#apply-param-form');
      if (form) {
        form.addEventListener('submit', (e) => {
          e.preventDefault();
          applyParameter(record);
        });
      }
    }
  }

  if (detailModal) {
    detailModal.show();
  }
}

function buildDetailHtml(record, isConflict) {
  const isPending = record.status_parametro === 'pendente_revisao';
  const conflictSection = isConflict ? buildConflictSection(record) : '';
  const pendingSection = isPending ? buildPendingSection(record) : '';
  const hideParams = isConflict || isPending;

  return `
    <div class="mb-3">
      ${buildStatusBadge(record)}
    </div>

    ${conflictSection}
    ${pendingSection}

    <dl class="row">
      <dt class="col-sm-4">ID do registro</dt>
      <dd class="col-sm-8">${escapeHtml(record.id_registro_reajuste ?? '—')}</dd>

      <dt class="col-sm-4">Sindicato</dt>
      <dd class="col-sm-8">${escapeHtml(record.sindicato ?? '—')}</dd>

      <dt class="col-sm-4">UF</dt>
      <dd class="col-sm-8">${escapeHtml(record.uf ?? '—')}</dd>

      <dt class="col-sm-4">Categoria</dt>
      <dd class="col-sm-8">${escapeHtml(record.categoria ?? '—')}</dd>

      <dt class="col-sm-4">Ano de referência</dt>
      <dd class="col-sm-8">${escapeHtml(record.ano_referencia ?? '—')}</dd>

      <dt class="col-sm-4">Percentual de reajuste</dt>
      <dd class="col-sm-8">${hideParams ? '—' : formatPercent(record.percentual_reajuste)}</dd>

      <dt class="col-sm-4">Data-base</dt>
      <dd class="col-sm-8">${hideParams ? '—' : formatDate(record.data_base)}</dd>

      <dt class="col-sm-4">Vigência início</dt>
      <dd class="col-sm-8">${hideParams ? '—' : formatDate(record.vigencia_inicio)}</dd>

      <dt class="col-sm-4">Vigência fim</dt>
      <dd class="col-sm-8">${hideParams ? '—' : formatDate(record.vigencia_fim)}</dd>

      ${!isPending ? `
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

  const observacao = record.observacao
    ? `<p class="mb-0 small">${escapeHtml(record.observacao)}</p>`
    : '';

  return `
    <div class="detail-conflict-box mb-3" role="alert" aria-label="Informações do conflito">
      <h3 class="conflict-section-title">⚠ Informações do conflito</h3>
      <p class="conflict-warning-msg">
        Este parâmetro possui conflito e não deve ser usado para precificação até revisão manual.
      </p>
      <div class="mb-2">
        <span class="detail-field-label">Registros/documentos conflitantes:</span>
        <div class="mt-1">${idBadges}</div>
      </div>
      ${observacao ? `<div><span class="detail-field-label">Observação:</span><br />${observacao}</div>` : ''}
    </div>
  `;
}

function buildPendingSection(record) {
  let fonteHtml = '';
  if (record.fonte_documento && isPdfPath(record.fonte_documento)) {
    fonteHtml = `
      <div class="mb-3">
        <a href="${escapeHtml(record.fonte_documento)}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-outline-secondary">
          📄 Abrir PDF
        </a>
        <span class="text-secondary small ms-2">${escapeHtml(pdfLabel(record.fonte_documento))}</span>
      </div>`;
  } else if (record.fonte_documento) {
    fonteHtml = `<p class="text-secondary small mb-3">Fonte: ${escapeHtml(record.fonte_documento)}</p>`;
  }

  return `
    <div class="detail-pending-box mb-3" role="region" aria-label="Sindicato pendente de revisão">
      <h3 class="pending-section-title">⏳ Sindicato pendente de revisão</h3>
      <p class="pending-info-msg">
        Este sindicato existe na estrutura de documentos CCT, mas ainda não possui parâmetro aprovado disponível.
        Abra o documento de origem, analise a CCT manualmente e aplique o parâmetro quando identificar o reajuste correto.
      </p>
      ${fonteHtml}
      <hr class="my-3" />
      <h4 class="pending-form-title">Aplicar parâmetro manualmente</h4>
      <form id="apply-param-form" novalidate>
        <div class="row g-2 mb-3">
          <div class="col-sm-6">
            <label for="apply-percentual" class="form-label form-label-sm">
              Percentual de reajuste (%) <span class="text-danger">*</span>
            </label>
            <input
              type="number"
              class="form-control form-control-sm"
              id="apply-percentual"
              step="0.01"
              min="0"
              placeholder="Ex: 5.50"
            />
          </div>
          <div class="col-sm-6">
            <label for="apply-data-base" class="form-label form-label-sm">
              Data-base <span class="text-danger">*</span>
            </label>
            <input type="date" class="form-control form-control-sm" id="apply-data-base" />
          </div>
          <div class="col-sm-6">
            <label for="apply-vigencia-inicio" class="form-label form-label-sm">
              Vigência início <span class="text-danger">*</span>
            </label>
            <input type="date" class="form-control form-control-sm" id="apply-vigencia-inicio" />
          </div>
          <div class="col-sm-6">
            <label for="apply-vigencia-fim" class="form-label form-label-sm">
              Vigência fim <span class="text-danger">*</span>
            </label>
            <input type="date" class="form-control form-control-sm" id="apply-vigencia-fim" />
          </div>
          <div class="col-12">
            <label for="apply-observacao" class="form-label form-label-sm">Observação</label>
            <textarea
              class="form-control form-control-sm"
              id="apply-observacao"
              rows="2"
              placeholder="Observações sobre a aplicação manual do parâmetro"
            ></textarea>
          </div>
        </div>
        <div id="apply-param-errors" class="alert alert-danger py-2 small d-none" role="alert"></div>
        <button type="submit" class="btn btn-primary btn-sm">Aplicar parâmetro</button>
      </form>
    </div>
  `;
}

function applyParameter(record) {
  const percentualEl = document.getElementById('apply-percentual');
  const dataBaseEl = document.getElementById('apply-data-base');
  const vigenciaInicioEl = document.getElementById('apply-vigencia-inicio');
  const vigenciaFimEl = document.getElementById('apply-vigencia-fim');
  const observacaoEl = document.getElementById('apply-observacao');
  const errorsEl = document.getElementById('apply-param-errors');

  const missing = [];

  const percentualRaw = percentualEl?.value?.trim();
  const percentual = parseFloat(percentualRaw);
  if (!percentualRaw || Number.isNaN(percentual) || percentual < 0) {
    missing.push('Percentual de reajuste (número maior ou igual a 0)');
  }

  if (!dataBaseEl?.value?.trim()) missing.push('Data-base');
  if (!vigenciaInicioEl?.value?.trim()) missing.push('Vigência início');
  if (!vigenciaFimEl?.value?.trim()) missing.push('Vigência fim');

  if (
    vigenciaInicioEl?.value && vigenciaFimEl?.value &&
    vigenciaFimEl.value < vigenciaInicioEl.value
  ) {
    missing.push('Vigência fim deve ser igual ou posterior à vigência início');
  }

  if (missing.length > 0) {
    if (errorsEl) {
      errorsEl.textContent = `Campos obrigatórios inválidos ou não preenchidos: ${missing.join('; ')}`;
      errorsEl.classList.remove('d-none');
    }
    return;
  }

  if (errorsEl) errorsEl.classList.add('d-none');

  const anoReferencia = dataBaseEl.value
    ? new Date(`${dataBaseEl.value}T00:00:00`).getFullYear()
    : (vigenciaInicioEl.value ? new Date(`${vigenciaInicioEl.value}T00:00:00`).getFullYear() : null);

  const updates = {
    status_parametro: 'valido',
    conflito: false,
    percentual_reajuste: percentual,
    data_base: dataBaseEl.value,
    vigencia_inicio: vigenciaInicioEl.value,
    vigencia_fim: vigenciaFimEl.value,
    observacao: observacaoEl?.value?.trim() || record.observacao,
    ano_referencia: anoReferencia,
    aplicado_em: new Date().toISOString(),
  };

  Object.assign(record, updates);
  saveLocalOverride(record.id_registro_reajuste, updates);

  // Refresh filter options (e.g. the new ano_referencia may be new)
  populateFilterOptions();
  applyFilters();

  if (detailModal) detailModal.hide();
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
