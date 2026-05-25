/* app.js - Tela de Consulta de Parâmetros Sindicais */

const DATA_URL = 'data/base_parametros_sindicais.json';
const EXAMPLE_DATA_URL = 'data/base_parametros_sindicais.example.json';
const STORAGE_KEY = 'parametros_sindicais_aplicados';

const OVERRIDE_ALLOWED_FIELDS = [
  'percentual_reajuste',
  'data_base',
  'vigencia_inicio',
  'vigencia_fim',
  'ano_referencia',
  'status_parametro',
  'conflito',
  'observacao',
  'aplicado_manualmente_em',
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
      id_registro_reajuste: 'DEMO-PEND-001',
      ids_registros_conflitantes: null,
      sindicato: 'SINDTEST-SP',
      uf: 'SP',
      categoria: null,
      ano_referencia: null,
      status_parametro: 'pendente_revisao',
      conflito: false,
      percentual_reajuste: null,
      data_base: null,
      vigencia_inicio: null,
      vigencia_fim: null,
      fonte_documento: 'CCT/SP/SINDTEST/CCT_2025_SINDTEST-SP.pdf',
      observacao: 'Sindicato encontrado na pasta CCT, mas sem parâmetro aprovado disponível',
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
  loadAppliedOverrides();
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

function loadAppliedOverrides() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const overrides = JSON.parse(raw);
    if (!overrides || typeof overrides !== 'object' || Array.isArray(overrides)) return;
    allRecords.forEach((record) => {
      const id = record.id_registro_reajuste;
      if (!id || !overrides[id] || typeof overrides[id] !== 'object') return;
      const safe = {};
      OVERRIDE_ALLOWED_FIELDS.forEach((field) => {
        if (Object.prototype.hasOwnProperty.call(overrides[id], field)) {
          safe[field] = overrides[id][field];
        }
      });
      Object.assign(record, safe);
    });
  } catch {
    // ignore storage errors
  }
}

function saveAppliedOverride(record) {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const overrides = raw ? JSON.parse(raw) : {};
    const stored = {};
    OVERRIDE_ALLOWED_FIELDS.forEach((field) => {
      stored[field] = record[field] ?? null;
    });
    overrides[record.id_registro_reajuste] = stored;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(overrides));
  } catch {
    // ignore storage errors (private browsing, quota exceeded, etc.)
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
    } else if (record.status_parametro === 'pendente_revisao') {
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
  const isConflict = isConflictRecord(record);
  const modalBody = document.getElementById('detail-modal-body');
  const modalTitle = document.getElementById('detail-modal-label');

  if (modalTitle) {
    modalTitle.textContent = `${record.sindicato ?? '—'} — ${record.uf ?? '—'} (${record.ano_referencia ?? '—'})`;
  }

  if (modalBody) {
    modalBody.innerHTML = buildDetailHtml(record, isConflict);
    bindDetailModalEvents(record, modalBody);
  }

  if (detailModal) {
    detailModal.show();
  }
}

function buildDetailHtml(record, isConflict) {
  const isPending = record.status_parametro === 'pendente_revisao';
  let specialSection = '';
  if (isPending) {
    specialSection = buildPendingSection(record);
  } else if (isConflict) {
    specialSection = buildConflictSection(record);
  }

  return `
    <div class="mb-3">
      ${buildStatusBadge(record)}
    </div>

    ${specialSection}

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
      <dd class="col-sm-8">${isConflict ? '—' : formatPercent(record.percentual_reajuste)}</dd>

      <dt class="col-sm-4">Data-base</dt>
      <dd class="col-sm-8">${isConflict ? '—' : formatDate(record.data_base)}</dd>

      <dt class="col-sm-4">Vigência início</dt>
      <dd class="col-sm-8">${isConflict ? '—' : formatDate(record.vigencia_inicio)}</dd>

      <dt class="col-sm-4">Vigência fim</dt>
      <dd class="col-sm-8">${isConflict ? '—' : formatDate(record.vigencia_fim)}</dd>

      <dt class="col-sm-4">Fonte do documento</dt>
      <dd class="col-sm-8">${buildFonteLink(record.fonte_documento)}</dd>

      ${record.observacao ? `
      <dt class="col-sm-4">Observação</dt>
      <dd class="col-sm-8"><span class="text-secondary small">${escapeHtml(record.observacao)}</span></dd>
      ` : ''}

      ${record.aplicado_manualmente_em ? `
      <dt class="col-sm-4">Aplicado manualmente em</dt>
      <dd class="col-sm-8"><span class="text-secondary small">${escapeHtml(formatDateTime(record.aplicado_manualmente_em))}</span></dd>
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
  const pdfButton = isPdfPath(record.fonte_documento)
    ? `<a href="${escapeHtml(record.fonte_documento)}" target="_blank" rel="noopener noreferrer"
         class="btn btn-sm btn-outline-secondary me-2">
         📄 Abrir PDF
       </a>`
    : '';

  const observacaoEscapada = escapeHtml(record.observacao ?? '');

  return `
    <div class="detail-pending-box mb-3" role="note" aria-label="Sindicato pendente de revisão">
      <h3 class="pending-section-title">⏳ Sindicato pendente de revisão</h3>
      <p class="pending-info-msg">
        Este sindicato existe na pasta CCT, mas ainda não possui parâmetro aprovado disponível.
        Consulte o documento de origem, analise manualmente a CCT e aplique o parâmetro correto.
      </p>
      <div class="d-flex flex-wrap gap-2 align-items-center">
        ${pdfButton}
        <button type="button" id="btn-mostrar-aplicar" class="btn btn-sm btn-warning">
          Aplicar parâmetro
        </button>
      </div>
    </div>

    <div id="apply-form-section" class="d-none border rounded p-3 mb-3 bg-light">
      <h4 class="fs-6 fw-semibold mb-3">Aplicar parâmetro manualmente</h4>
      <div id="apply-form-error" class="alert alert-danger d-none small" role="alert"></div>
      <form id="apply-param-form" novalidate>
        <div class="row g-2 mb-3">
          <div class="col-sm-6">
            <label for="apply-percentual" class="form-label form-label-sm fw-semibold">
              Percentual de reajuste (%) <span class="text-danger" aria-hidden="true">*</span>
            </label>
            <input type="number" id="apply-percentual" name="percentual_reajuste"
              class="form-control form-control-sm" step="0.01" min="-100" max="1000"
              placeholder="Ex.: 5.50" autocomplete="off" />
          </div>
          <div class="col-sm-6">
            <label for="apply-data-base" class="form-label form-label-sm fw-semibold">
              Data-base <span class="text-danger" aria-hidden="true">*</span>
            </label>
            <input type="date" id="apply-data-base" name="data_base"
              class="form-control form-control-sm" />
          </div>
          <div class="col-sm-6">
            <label for="apply-vigencia-inicio" class="form-label form-label-sm fw-semibold">
              Vigência início <span class="text-danger" aria-hidden="true">*</span>
            </label>
            <input type="date" id="apply-vigencia-inicio" name="vigencia_inicio"
              class="form-control form-control-sm" />
          </div>
          <div class="col-sm-6">
            <label for="apply-vigencia-fim" class="form-label form-label-sm fw-semibold">
              Vigência fim <span class="text-danger" aria-hidden="true">*</span>
            </label>
            <input type="date" id="apply-vigencia-fim" name="vigencia_fim"
              class="form-control form-control-sm" />
          </div>
          <div class="col-12">
            <label for="apply-observacao" class="form-label form-label-sm fw-semibold">
              Observação
            </label>
            <textarea id="apply-observacao" name="observacao"
              class="form-control form-control-sm" rows="2">${observacaoEscapada}</textarea>
          </div>
        </div>
        <div class="d-flex gap-2">
          <button type="submit" class="btn btn-sm btn-warning">Confirmar aplicação</button>
          <button type="button" id="btn-cancelar-aplicar" class="btn btn-sm btn-outline-secondary">Cancelar</button>
        </div>
      </form>
    </div>
  `;
}

function bindDetailModalEvents(record, modalBody) {
  if (record.status_parametro !== 'pendente_revisao') return;

  const btnMostrar = modalBody.querySelector('#btn-mostrar-aplicar');
  const formSection = modalBody.querySelector('#apply-form-section');

  if (btnMostrar && formSection) {
    btnMostrar.addEventListener('click', () => {
      formSection.classList.remove('d-none');
      btnMostrar.classList.add('d-none');
    });
  }

  const btnCancelar = modalBody.querySelector('#btn-cancelar-aplicar');
  if (btnCancelar && formSection && btnMostrar) {
    btnCancelar.addEventListener('click', () => {
      formSection.classList.add('d-none');
      btnMostrar.classList.remove('d-none');
      const errorEl = formSection.querySelector('#apply-form-error');
      if (errorEl) errorEl.classList.add('d-none');
    });
  }

  const applyForm = modalBody.querySelector('#apply-param-form');
  if (applyForm) {
    applyForm.addEventListener('submit', (e) => {
      e.preventDefault();
      applyParameter(record, applyForm, modalBody);
    });
  }
}

function applyParameter(record, form, modalBody) {
  const percentualRaw = form.querySelector('[name="percentual_reajuste"]').value.trim().replace(',', '.');
  const dataBase = form.querySelector('[name="data_base"]').value.trim();
  const vigInicio = form.querySelector('[name="vigencia_inicio"]').value.trim();
  const vigFim = form.querySelector('[name="vigencia_fim"]').value.trim();
  const observacao = form.querySelector('[name="observacao"]').value.trim();

  const errorEl = modalBody.querySelector('#apply-form-error');

  const missing = [];
  if (!percentualRaw) missing.push('Percentual de reajuste');
  if (!dataBase) missing.push('Data-base');
  if (!vigInicio) missing.push('Vigência início');
  if (!vigFim) missing.push('Vigência fim');

  if (missing.length > 0) {
    if (errorEl) {
      errorEl.textContent = `Campos obrigatórios não preenchidos: ${missing.join(', ')}.`;
      errorEl.classList.remove('d-none');
    }
    return;
  }

  const percentual = parseFloat(percentualRaw);
  if (Number.isNaN(percentual)) {
    if (errorEl) {
      errorEl.textContent = 'Percentual de reajuste inválido. Use um número (ex.: 5.50).';
      errorEl.classList.remove('d-none');
    }
    return;
  }

  if (vigFim < vigInicio) {
    if (errorEl) {
      errorEl.textContent = 'Vigência fim não pode ser anterior à vigência início.';
      errorEl.classList.remove('d-none');
    }
    return;
  }

  if (errorEl) errorEl.classList.add('d-none');

  // Update record in-place (reference shared with allRecords and filteredRecords)
  record.percentual_reajuste = percentual;
  record.data_base = dataBase;
  record.vigencia_inicio = vigInicio;
  record.vigencia_fim = vigFim;
  record.observacao = observacao || null;
  record.status_parametro = 'valido';
  record.conflito = false;
  record.ano_referencia = new Date(`${vigInicio}T00:00:00`).getFullYear();
  record.aplicado_manualmente_em = new Date().toISOString();

  saveAppliedOverride(record);

  // Refresh year filter options to include the newly set year
  populateSelect(filterAno, uniqueValues(allRecords, 'ano_referencia'), 'Todos os anos');
  applyFilters();

  // Refresh modal body to show updated (now valid) record
  modalBody.innerHTML = buildDetailHtml(record, isConflictRecord(record));
  bindDetailModalEvents(record, modalBody);

  // Update modal title with new year
  const modalTitle = document.getElementById('detail-modal-label');
  if (modalTitle) {
    modalTitle.textContent = `${record.sindicato ?? '—'} — ${record.uf ?? '—'} (${record.ano_referencia ?? '—'})`;
  }
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
