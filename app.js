/**
 * Parâmetros Sindicais — consulta somente leitura
 * Carrega data/base_parametros_sindicais.json e renderiza a listagem com filtros.
 */

const DATA_URL = 'data/base_parametros_sindicais.json';
const EXAMPLE_DATA_URL = 'data/base_parametros_sindicais.example.json';

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
      fonte_documento: 'CCT/MG/SESCON/2025.pdf',
      observacao: null,
      itens_cct: {
        reajuste_salarial: {
          valor: 5.5, tipo: 'percentual', unidade: '%',
          status_parametro: 'valido', conflito: false, ids_registros_conflitantes: null,
          fonte_documento: 'CCT/MG/SESCON/2025.pdf', observacao: null,
          data_validacao: '2025-03-01T10:00:00', origem_atualizacao: 'importacao_pdf',
        },
        auxilio_alimentacao: {
          valor: null, tipo: 'valor_mensal', unidade: 'BRL',
          status_parametro: 'pendente_revisao', conflito: false, ids_registros_conflitantes: null,
          fonte_documento: 'CCT/MG/SESCON/2025.pdf', observacao: 'Item ainda não validado',
          data_validacao: null, origem_atualizacao: null,
        },
        adicional_noturno: {
          valor: null, tipo: 'percentual', unidade: '%',
          status_parametro: 'pendente_revisao', conflito: false, ids_registros_conflitantes: null,
          fonte_documento: 'CCT/MG/SESCON/2025.pdf', observacao: null,
          data_validacao: null, origem_atualizacao: null,
        },
        hora_extra: {
          valor: null, tipo: 'regra_textual', unidade: null,
          status_parametro: 'pendente_revisao', conflito: false, ids_registros_conflitantes: null,
          fonte_documento: 'CCT/MG/SESCON/2025.pdf', observacao: null,
          data_validacao: null, origem_atualizacao: null,
        },
        plr: {
          valor: null, tipo: 'regra_textual', unidade: null,
          status_parametro: 'pendente_revisao', conflito: false, ids_registros_conflitantes: null,
          fonte_documento: 'CCT/MG/SESCON/2025.pdf', observacao: null,
          data_validacao: null, origem_atualizacao: null,
        },
      },
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
      fonte_documento: 'CCT/SP/SINTTEL/2025.pdf',
      observacao: null,
      itens_cct: {
        reajuste_salarial: {
          valor: 6.0, tipo: 'percentual', unidade: '%',
          status_parametro: 'valido', conflito: false, ids_registros_conflitantes: null,
          fonte_documento: 'CCT/SP/SINTTEL/2025.pdf', observacao: null,
          data_validacao: '2025-04-10T09:30:00', origem_atualizacao: 'importacao_pdf',
        },
        auxilio_alimentacao: {
          valor: 880.00, tipo: 'valor_mensal', unidade: 'BRL',
          status_parametro: 'valido', conflito: false, ids_registros_conflitantes: null,
          fonte_documento: 'CCT/SP/SINTTEL/2025.pdf', observacao: null,
          data_validacao: '2025-04-10T09:35:00', origem_atualizacao: 'importacao_pdf',
        },
        adicional_noturno: {
          valor: 35, tipo: 'percentual', unidade: '%',
          status_parametro: 'valido', conflito: false, ids_registros_conflitantes: null,
          fonte_documento: 'CCT/SP/SINTTEL/2025.pdf', observacao: null,
          data_validacao: '2025-04-10T09:40:00', origem_atualizacao: 'importacao_pdf',
        },
        hora_extra: {
          valor: null, tipo: 'regra_textual', unidade: null,
          status_parametro: 'pendente_revisao', conflito: false, ids_registros_conflitantes: null,
          fonte_documento: 'CCT/SP/SINTTEL/2025.pdf',
          observacao: 'Regra não extraída do PDF — requer revisão manual',
          data_validacao: null, origem_atualizacao: null,
        },
        plr: {
          valor: null, tipo: 'regra_textual', unidade: null,
          status_parametro: 'pendente_revisao', conflito: false, ids_registros_conflitantes: null,
          fonte_documento: 'CCT/SP/SINTTEL/2025.pdf', observacao: null,
          data_validacao: null, origem_atualizacao: null,
        },
      },
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
      itens_cct: {
        reajuste_salarial: {
          valor: null, tipo: 'percentual', unidade: '%',
          status_parametro: 'conflito', conflito: true,
          ids_registros_conflitantes: ['DEMO-003', 'DEMO-004'],
          fonte_documento: null, observacao: 'Conflito não resolvido — nenhum valor aprovado.',
          data_validacao: null, origem_atualizacao: null,
        },
        auxilio_alimentacao: {
          valor: null, tipo: 'valor_mensal', unidade: 'BRL',
          status_parametro: 'conflito', conflito: true,
          ids_registros_conflitantes: ['DEMO-003', 'DEMO-004'],
          fonte_documento: null, observacao: 'Conflito não resolvido — nenhum valor aprovado.',
          data_validacao: null, origem_atualizacao: null,
        },
        adicional_noturno: {
          valor: null, tipo: 'percentual', unidade: '%',
          status_parametro: 'conflito', conflito: true,
          ids_registros_conflitantes: ['DEMO-003', 'DEMO-004'],
          fonte_documento: null, observacao: 'Conflito não resolvido — nenhum valor aprovado.',
          data_validacao: null, origem_atualizacao: null,
        },
        hora_extra: {
          valor: null, tipo: 'regra_textual', unidade: null,
          status_parametro: 'conflito', conflito: true,
          ids_registros_conflitantes: ['DEMO-003', 'DEMO-004'],
          fonte_documento: null, observacao: 'Conflito não resolvido — nenhum valor aprovado.',
          data_validacao: null, origem_atualizacao: null,
        },
        plr: {
          valor: null, tipo: 'regra_textual', unidade: null,
          status_parametro: 'conflito', conflito: true,
          ids_registros_conflitantes: ['DEMO-003', 'DEMO-004'],
          fonte_documento: null, observacao: 'Conflito não resolvido — nenhum valor aprovado.',
          data_validacao: null, origem_atualizacao: null,
        },
      },
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
    allRecords = records;
    showApp(dataGeracao, demoMessage);
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
    const tr = document.createElement('tr');
    if (isConflict) tr.classList.add('row-conflito');
    tr.setAttribute('role', 'button');
    tr.setAttribute('tabindex', '0');
    tr.setAttribute('aria-label', `Ver detalhes: ${record.sindicato ?? ''} ${record.uf ?? ''}`);

    tr.innerHTML = `
      <td>${escHtml(record.uf ?? '—')}</td>
      <td>${escHtml(record.sindicato ?? '—')}</td>
      <td>${escHtml(String(record.ano_referencia ?? '—'))}</td>
      <td>${formatPercent(getReajusteValor(record))}</td>
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

  document.getElementById('detail-modal-label').textContent =
    `${record.sindicato ?? '—'} — ${record.uf ?? '—'} (${record.ano_referencia ?? '—'})`;

  document.getElementById('detail-modal-body').innerHTML = buildDetailHtml(record, isConflict);
  if (detailModal) {
    detailModal.show();
  }
}

function buildDetailHtml(r, isConflict) {
  const fields = [
    ['UF', r.uf],
    ['Sindicato', r.sindicato],
    ['Ano de referência', r.ano_referencia],
    ['Percentual de reajuste', formatPercent(getReajusteValor(r))],
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

  let html = '<div class="row g-3">';
  fields.forEach(([label, value]) => {
    html += `
      <div class="col-12 col-sm-6">
        <div class="detail-field-label">${escHtml(label)}</div>
        <div class="detail-field-value">${value ?? '—'}</div>
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

  if (r.itens_cct && typeof r.itens_cct === 'object') {
    html += buildCctItemsHtml(r.itens_cct);
  }

  return html;
}

function buildCctItemsHtml(itens) {
  const entries = Object.entries(itens);
  if (entries.length === 0) return '';

  let html = `
    <hr class="my-3"/>
    <h3 class="cct-section-title">Itens da CCT</h3>
    <div class="row g-3">`;

  entries.forEach(([key, item]) => {
    const label = CCT_ITEM_LABELS[key] ?? key;
    const valorDisplay = formatCctValor(item);
    const badge = statusBadgeItem(item);
    const isConflito = item.status_parametro === 'conflito' || item.conflito === true;
    const isPendente = item.status_parametro === 'pendente_revisao';
    const fonteRaw = item.fonte_documento ?? null;
    const obs = item.observacao ?? null;
    const dataVal = item.data_validacao ? formatDateTime(item.data_validacao) : null;
    const origem = item.origem_atualizacao ?? null;

    const fonteHtml = fonteRaw
      ? `<a href="${escAttr(fonteRaw)}" target="_blank" rel="noopener noreferrer" class="cct-item-meta">Abrir PDF</a>`
      : `<span class="cct-item-meta">Fonte: —</span>`;

    let metaHtml = `<div>${fonteHtml}</div>`;
    metaHtml += `<div class="cct-item-meta cct-item-obs">${obs ? escHtml(obs) : '—'}</div>`;
    if (dataVal) {
      metaHtml += `<div class="cct-item-meta">Validado em: ${escHtml(dataVal)}</div>`;
    }
    if (origem) {
      metaHtml += `<div class="cct-item-meta">Origem: ${escHtml(origem)}</div>`;
    }

    let statusAlertHtml = '';
    if (isConflito) {
      let conflictIdsHtml = '';
      if (Array.isArray(item.ids_registros_conflitantes) && item.ids_registros_conflitantes.length > 0) {
        const ids = item.ids_registros_conflitantes
          .map((id) => `<span class="conflicting-id">${escHtml(String(id))}</span>`)
          .join('');
        conflictIdsHtml = `<div class="mt-1">${ids}</div>`;
      }
      statusAlertHtml = `
        <div class="cct-item-alert cct-item-alert-conflito mt-2">
          ⚠ Este item não deve ser utilizado até revisão manual.
          ${conflictIdsHtml}
        </div>`;
    } else if (isPendente) {
      statusAlertHtml = `
        <div class="cct-item-alert cct-item-alert-pendente mt-2">
          ⏳ Este item aguarda revisão.
        </div>`;
    }

    html += `
      <div class="col-12 col-sm-6">
        <div class="cct-item-card">
          <div class="cct-item-header">
            <span class="cct-item-label">${escHtml(label)}</span>
            ${badge}
          </div>
          <div class="cct-item-valor">${valorDisplay}</div>
          ${metaHtml}
          ${statusAlertHtml}
        </div>
      </div>`;
  });

  html += '</div>';
  return html;
}

function formatCctValor(item) {
  if (item.valor == null) return '<span class="text-secondary">—</span>';
  if (typeof item.valor === 'string') return escHtml(item.valor);
  if (item.tipo === 'percentual') return `${Number(item.valor).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
  if (item.unidade === 'BRL') {
    return Number(item.valor).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  }
  return escHtml(String(item.valor));
}

// ── Helpers ──────────────────────────────────────────────────────────

/** Labels for itens_cct keys */
const CCT_ITEM_LABELS = {
  reajuste_salarial: 'Reajuste Salarial',
  auxilio_alimentacao: 'Auxílio Alimentação/Refeição',
  adicional_noturno: 'Adicional Noturno',
  hora_extra: 'Hora Extra',
  plr: 'PLR',
};

/**
 * Returns the reajuste valor using itens_cct as the canonical source,
 * falling back to the legacy flat field for backward compatibility.
 */
function getReajusteValor(r) {
  return r.itens_cct?.reajuste_salarial?.valor ?? r.percentual_reajuste ?? null;
}

function statusBadge(record) {
  const isConflict = record.status_parametro === 'conflito' || record.conflito === true;
  if (isConflict) {
    return '<span class="badge-conflito">⚠ Conflito</span>';
  }
  if (record.status_parametro === 'pendente_revisao') {
    return '<span class="badge-pendente">⏳ Pendente</span>';
  }
  return '<span class="badge-valido">✔ Válido</span>';
}

function statusBadgeItem(item) {
  if (!item) return '';
  if (item.status_parametro === 'conflito' || item.conflito === true) {
    return '<span class="badge-conflito">⚠ Conflito</span>';
  }
  if (item.status_parametro === 'pendente_revisao') {
    return '<span class="badge-pendente">⏳ Pendente</span>';
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
