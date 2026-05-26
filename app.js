/**
 * Parâmetros Sindicais — consulta somente leitura
 * Carrega data/base_parametros_sindicais.json e renderiza a listagem com filtros.
 */

const DATA_URL = 'data/base_parametros_sindicais.json';
const EXAMPLE_DATA_URL = 'data/base_parametros_sindicais.example.json';
const LS_KEY = 'params_sindicais_local';

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
      id_registro_reajuste: 'DEMO-005',
      ids_registros_conflitantes: null,
      sindicato: 'SINTEPE-PE',
      uf: 'PE',
      categoria: 'Professores',
      ano_referencia: 2025,
      status_parametro: 'pendente_revisao',
      conflito: false,
      percentual_reajuste: null,
      data_base: null,
      vigencia_inicio: null,
      vigencia_fim: null,
      fonte_documento: 'CCT/PE/SINTEPE-PE-2025.pdf',
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
const elBtnExportJson = document.getElementById('btn-export-json');
const elBtnDiscardLocal = document.getElementById('btn-discard-local');

let allRecords = [];
let originalRecords = [];
let detailModal = null;

// ── Bootstrap date the app ──────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  if (window.bootstrap) {
    detailModal = new bootstrap.Modal(document.getElementById('detail-modal'));
  }
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
    originalRecords = records.map((r) => ({ ...r }));

    const savedRecords = loadFromLocalStorage();
    if (savedRecords && Array.isArray(savedRecords)) {
      allRecords = savedRecords;
    } else {
      allRecords = records;
    }

    showApp(dataGeracao, demoMessage);
    populateFilterOptions();
    renderTable();

    if (savedRecords) {
      showLocalChangesBanner();
    }
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

elBtnExportJson.addEventListener('click', exportJson);
elBtnDiscardLocal.addEventListener('click', discardLocalChanges);

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
    attachValidationListeners(record);
  }

  if (detailModal) {
    detailModal.show();
  }
}

function detailFieldHtml(label, value) {
  return `
    <div class="col-12 col-sm-6">
      <div class="detail-field-label">${escHtml(label)}</div>
      <div class="detail-field-value">${value ?? '—'}</div>
    </div>`;
}

function buildDetailHtml(r, isConflict, isPending) {
  let html = '<div class="row g-3">';

  html += detailFieldHtml('UF', escHtml(r.uf ?? '—'));
  html += detailFieldHtml('Sindicato', escHtml(r.sindicato ?? '—'));
  html += detailFieldHtml('Ano de referência', escHtml(String(r.ano_referencia ?? '—')));
  html += detailFieldHtml('Status', statusBadge(r));

  if (r.id_registro_reajuste != null) {
    html += detailFieldHtml('ID do registro', escHtml(r.id_registro_reajuste));
  }

  // Data fields: show for valido records only (pending/conflict fill via form)
  if (!isPending && !isConflict) {
    html += detailFieldHtml('Percentual de reajuste', formatPercent(r.percentual_reajuste));
    html += detailFieldHtml('Data-base', formatDate(r.data_base));
    html += detailFieldHtml('Vigência início', formatDate(r.vigencia_inicio));
    html += detailFieldHtml('Vigência fim', formatDate(r.vigencia_fim));
  }

  // Fonte do documento with optional PDF button
  const fonteHtml = r.fonte_documento
    ? `<div class="d-flex align-items-center gap-2 flex-wrap">
         <span>${escHtml(r.fonte_documento)}</span>
         <a href="${escAttr(r.fonte_documento)}" target="_blank" rel="noopener noreferrer"
            class="btn btn-sm btn-outline-primary py-0 btn-open-pdf">📄 Abrir PDF</a>
       </div>`
    : '—';
  html += `
    <div class="col-12 col-sm-6">
      <div class="detail-field-label">Fonte do documento</div>
      <div class="detail-field-value">${fonteHtml}</div>
    </div>`;

  // Observação for valido records
  if (!isPending && !isConflict && r.observacao != null) {
    html += detailFieldHtml('Observação', escHtml(r.observacao));
  }

  // Rastreabilidade fields (shown after manual validation)
  if (r.origem_atualizacao === 'validacao_manual_tela') {
    html += detailFieldHtml('Origem da atualização', 'Validação manual na tela');
    if (r.data_hora_validacao_manual) {
      html += detailFieldHtml('Data/hora da validação', escHtml(formatDateTime(r.data_hora_validacao_manual)));
    }
    if (r.status_anterior) {
      html += detailFieldHtml('Status anterior', escHtml(r.status_anterior));
    }
  }

  html += '</div>'; // close row

  // Review context section
  if (isPending) {
    html += `
      <hr class="my-3"/>
      <div class="review-section review-section-pendente">
        <div class="review-section-header">
          <span class="review-icon">📋</span>
          <strong>Revisão necessária</strong>
        </div>
        <p class="mb-2 small mt-2">Este sindicato existe na pasta CCT mas ainda não possui parâmetro aprovado.
          Abra o PDF de origem para localizar a cláusula de reajuste, a data-base e a vigência.</p>
        <ul class="review-checklist small">
          <li>☐ Abrir o PDF de origem e identificar a cláusula de reajuste</li>
          <li>☐ Verificar a data-base e vigência da CCT</li>
          <li>☐ Preencher todos os campos abaixo com as informações encontradas</li>
          <li>☐ Registrar a justificativa no campo Observação (cláusula, página do PDF, trecho consultado ou motivo)</li>
        </ul>
      </div>`;
  } else if (isConflict) {
    const conflictIds =
      Array.isArray(r.ids_registros_conflitantes) && r.ids_registros_conflitantes.length > 0
        ? r.ids_registros_conflitantes
            .map((id) => `<span class="conflicting-id">${escHtml(String(id))}</span>`)
            .join('')
        : '';
    html += `
      <hr class="my-3"/>
      <div class="review-section review-section-conflito">
        <div class="review-section-header">
          <span class="review-icon">⚠</span>
          <strong>Conflito encontrado</strong>
        </div>
        ${conflictIds ? `<div class="mt-2 mb-1">${conflictIds}</div>` : ''}
        <p class="mb-2 small mt-2">Foram identificados múltiplos documentos com parâmetros divergentes para este sindicato.
          Nenhum parâmetro é escolhido automaticamente — a decisão cabe ao analista.</p>
        <ul class="review-checklist small">
          <li>☐ Analisar os documentos em conflito identificados acima</li>
          <li>☐ Abrir o PDF de origem e identificar os parâmetros corretos</li>
          <li>☐ Preencher todos os campos abaixo com os valores definitivos</li>
          <li>☐ Registrar no campo Observação qual documento foi escolhido e por quê</li>
        </ul>
      </div>`;
  }

  // Validation form (only for pending or conflict)
  if (isPending || isConflict) {
    html += `
      <hr class="my-3"/>
      <div class="validation-form">
        <h6 class="mb-3">Preencher parâmetros manualmente</h6>
        <div id="val-error" class="alert alert-danger py-2 d-none" role="alert"></div>
        <div class="row g-3">
          <div class="col-12 col-sm-6">
            <label for="val-percentual" class="form-label form-label-sm">
              Percentual de reajuste (%) <span class="text-danger">*</span>
            </label>
            <input type="number" id="val-percentual" class="form-control form-control-sm"
              step="0.01" min="0" placeholder="Ex.: 5.50" />
          </div>
          <div class="col-12 col-sm-6">
            <label for="val-data-base" class="form-label form-label-sm">
              Data-base <span class="text-danger">*</span>
            </label>
            <input type="date" id="val-data-base" class="form-control form-control-sm" />
          </div>
          <div class="col-12 col-sm-6">
            <label for="val-vigencia-inicio" class="form-label form-label-sm">
              Vigência início <span class="text-danger">*</span>
            </label>
            <input type="date" id="val-vigencia-inicio" class="form-control form-control-sm" />
          </div>
          <div class="col-12 col-sm-6">
            <label for="val-vigencia-fim" class="form-label form-label-sm">
              Vigência fim <span class="text-danger">*</span>
            </label>
            <input type="date" id="val-vigencia-fim" class="form-control form-control-sm" />
          </div>
          <div class="col-12">
            <label for="val-observacao" class="form-label form-label-sm">
              Observação / Justificativa <span class="text-danger">*</span>
            </label>
            <textarea id="val-observacao" class="form-control form-control-sm" rows="3"
              placeholder="Informe a justificativa da validação: cláusula do acordo, página do PDF consultada, trecho relevante ou motivo da decisão."></textarea>
          </div>
        </div>
        <div class="mt-3">
          <button id="btn-validar" type="button" class="btn btn-success">✔ Validar</button>
        </div>
      </div>`;
  }

  return html;
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

// ── Validation listener ──────────────────────────────────────────────

function attachValidationListeners(record) {
  const btnValidar = document.getElementById('btn-validar');
  if (!btnValidar) return;

  btnValidar.addEventListener('click', () => {
    const percentualRaw = document.getElementById('val-percentual').value.trim();
    const dataBase = document.getElementById('val-data-base').value.trim();
    const vigInicio = document.getElementById('val-vigencia-inicio').value.trim();
    const vigFim = document.getElementById('val-vigencia-fim').value.trim();
    const observacao = document.getElementById('val-observacao').value.trim();

    const missing = [];
    if (!percentualRaw) missing.push('Percentual de reajuste');
    if (!dataBase) missing.push('Data-base');
    if (!vigInicio) missing.push('Vigência início');
    if (!vigFim) missing.push('Vigência fim');
    if (!observacao) missing.push('Observação');

    const elError = document.getElementById('val-error');
    if (missing.length > 0) {
      elError.textContent = `Campos obrigatórios não preenchidos: ${missing.join(', ')}.`;
      elError.classList.remove('d-none');
      return;
    }

    const percentual = parseFloat(percentualRaw.replace(',', '.'));
    if (isNaN(percentual)) {
      elError.textContent = 'Percentual de reajuste inválido. Use formato numérico (ex.: 5.50 ou 5,50).';
      elError.classList.remove('d-none');
      return;
    }

    elError.classList.add('d-none');

    const statusAnterior = record.status_parametro;
    Object.assign(record, {
      status_parametro: 'valido',
      conflito: false,
      ids_registros_conflitantes: null,
      percentual_reajuste: percentual,
      data_base: dataBase,
      vigencia_inicio: vigInicio,
      vigencia_fim: vigFim,
      observacao,
      origem_atualizacao: 'validacao_manual_tela',
      data_hora_validacao_manual: new Date().toISOString(),
      status_anterior: statusAnterior,
    });

    saveToLocalStorage();
    showLocalChangesBanner();
    renderTable();
    if (detailModal) detailModal.hide();
  });
}

// ── localStorage persistence ─────────────────────────────────────────

function saveToLocalStorage() {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(allRecords));
  } catch (e) {
    console.warn('Erro ao salvar no localStorage:', e);
  }
}

function loadFromLocalStorage() {
  try {
    const saved = localStorage.getItem(LS_KEY);
    return saved ? JSON.parse(saved) : null;
  } catch {
    return null;
  }
}

function clearLocalStorage() {
  localStorage.removeItem(LS_KEY);
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

// ── Export JSON ──────────────────────────────────────────────────────

function exportJson() {
  const payload = {
    data_geracao: new Date().toISOString(),
    registros: allRecords,
  };
  const json = JSON.stringify(payload, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `base_parametros_sindicais_${new Date().toISOString().slice(0, 10)}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ── Discard local changes ────────────────────────────────────────────

function discardLocalChanges() {
  if (
    !window.confirm(
      'Descartar todas as alterações locais e restaurar a base original?\nEsta ação não pode ser desfeita.',
    )
  ) {
    return;
  }
  clearLocalStorage();
  allRecords = originalRecords.map((r) => ({ ...r }));
  renderTable();
  hideLocalChangesBanner();
}
