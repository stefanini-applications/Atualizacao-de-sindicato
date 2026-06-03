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
          percentual_padrao: 50, percentual_sabado: 75, percentual_domingo_feriado: 100,
          valor: null, tipo: 'percentual', unidade: '%',
          regra_textual: 'Hora extra: 50% dias úteis, 75% sábados, 100% domingos/feriados.',
          status_parametro: 'valido', conflito: false, ids_registros_conflitantes: null,
          fonte_documento: 'CCT/SP/SINTTEL/2025.pdf', observacao: null,
          data_validacao: '2025-04-10T09:45:00', origem_atualizacao: 'importacao_pdf',
        },
        sobreaviso: {
          percentual: 33.33, valor: null,
          regra_textual: 'Sobreaviso de 33,33% sobre a hora normal.',
          tipo: 'percentual', unidade: '%',
          status_parametro: 'valido', conflito: false, ids_registros_conflitantes: null,
          fonte_documento: 'CCT/SP/SINTTEL/2025.pdf', observacao: null,
          data_validacao: '2025-04-10T09:50:00', origem_atualizacao: 'importacao_pdf',
        },
        jornada: {
          horas_semanais: 44, opcoes_identificadas: '44h',
          regra_textual: 'Jornada de 44 horas semanais.',
          tipo: 'horas_semanais', unidade: 'horas',
          status_parametro: 'valido', conflito: false, ids_registros_conflitantes: null,
          fonte_documento: 'CCT/SP/SINTTEL/2025.pdf', observacao: null,
          data_validacao: '2025-04-10T09:52:00', origem_atualizacao: 'importacao_pdf',
        },
        plr: {
          valor: null, tipo: 'regra_textual', unidade: null,
          status_parametro: 'pendente_revisao', conflito: false, ids_registros_conflitantes: null,
          fonte_documento: 'CCT/SP/SINTTEL/2025.pdf',
          observacao: 'Regra não extraída do PDF — requer revisão manual',
          data_validacao: null, origem_atualizacao: null,
        },
      },
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
      itens_cct: {
        piso_salarial: {
          valor: 1540.47, piso_unico: 1540.47, piso_tecnico: null,
          piso_administrativo: null, valor_piso_cct: null,
          percentual: null, valor_textual: null,
          regra_textual: 'O piso salarial para a categoria é de R$ 1.540,47 mensais conforme cláusula terceira.',
          tipo: 'piso_unico', unidade: 'BRL',
          clausula: 'CLÁUSULA TERCEIRA - PISO SALARIAL',
          fonte_documento: 'CCT/SP/Sindtest-Demo/CCT_2025_Sindtest_Demo.pdf',
          observacao: null,
          status_parametro: 'extraido_para_revisao', conflito: false, ids_registros_conflitantes: null,
        },
        adicional_noturno: {
          valor: 35, percentual: 35, valor_textual: null,
          regra_textual: 'O adicional noturno é de 35% sobre a hora normal para trabalhos realizados entre 22h e 5h.',
          tipo: 'percentual', unidade: '%',
          clausula: 'CLÁUSULA DÉCIMA SEGUNDA - ADICIONAL NOTURNO',
          fonte_documento: 'CCT/SP/Sindtest-Demo/CCT_2025_Sindtest_Demo.pdf',
          observacao: null,
          status_parametro: 'extraido_para_revisao', conflito: false, ids_registros_conflitantes: null,
        },
        auxilio_alimentacao: {
          valor: null, percentual: null, valor_textual: null,
          regra_textual: null,
          tipo: 'valor_mensal', unidade: 'BRL',
          clausula: null,
          fonte_documento: 'CCT/SP/Sindtest-Demo/CCT_2025_Sindtest_Demo.pdf',
          observacao: 'Valor não identificado no documento.',
          status_parametro: 'pendente_revisao', conflito: false, ids_registros_conflitantes: null,
        },
        hora_extra: {
          percentual_padrao: 50, percentual_sabado: 75, percentual_domingo_feriado: 100,
          valor: null, tipo: 'percentual', unidade: '%',
          regra_textual: 'Hora extra: 50% dias úteis, 75% sábados, 100% domingos/feriados.',
          clausula: 'CLÁUSULA VIGÉSIMA - HORAS EXTRAS',
          fonte_documento: 'CCT/SP/Sindtest-Demo/CCT_2025_Sindtest_Demo.pdf',
          observacao: null,
          status_parametro: 'extraido_para_revisao', conflito: false, ids_registros_conflitantes: null,
        },
        sobreaviso: {
          percentual: 33.33, valor: null,
          regra_textual: 'Sobreaviso de 33,33% sobre a hora normal.',
          tipo: 'percentual', unidade: '%',
          clausula: null,
          fonte_documento: 'CCT/SP/Sindtest-Demo/CCT_2025_Sindtest_Demo.pdf',
          observacao: null,
          status_parametro: 'extraido_para_revisao', conflito: false, ids_registros_conflitantes: null,
        },
        jornada: {
          horas_semanais: 44, opcoes_identificadas: '44h',
          regra_textual: 'Jornada de trabalho de 44 horas semanais.',
          tipo: 'horas_semanais', unidade: 'horas',
          clausula: null,
          fonte_documento: 'CCT/SP/Sindtest-Demo/CCT_2025_Sindtest_Demo.pdf',
          observacao: null,
          status_parametro: 'extraido_para_revisao', conflito: false, ids_registros_conflitantes: null,
        },
        plr: {
          valor: null, percentual: null, valor_textual: null,
          regra_textual: null, tipo: 'regra_textual', unidade: null,
          clausula: null,
          fonte_documento: 'CCT/SP/Sindtest-Demo/CCT_2025_Sindtest_Demo.pdf',
          observacao: 'Regra de PLR não identificada no documento.',
          status_parametro: 'pendente_revisao', conflito: false, ids_registros_conflitantes: null,
        },
      },
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
    // PRJ-52: Demo record with variation lists (por_cargo, por_jornada, por_escala, por_modalidade)
    {
      id_registro_reajuste: 'DEMO-VARI-001',
      ids_registros_conflitantes: null,
      sindicato: 'SINDTEST-VARIAÇÕES',
      uf: 'SP',
      categoria: 'Tecnologia da Informação',
      ano_referencia: 2025,
      status_parametro: 'pendente_revisao',
      conflito: false,
      percentual_reajuste: 6.2,
      data_base: '2025-03-01',
      vigencia_inicio: '2025-03-01',
      vigencia_fim: '2026-02-28',
      fonte_documento: 'CCT/SP/Sindtest-Vari/CCT_2025_Sindtest_Vari.pdf',
      observacao: 'Parâmetros com variações por cargo, jornada, escala e modalidade — demo PRJ-52',
      itens_cct: {
        piso_salarial: {
          valor: null, tipo: null, unidade: 'BRL',
          regra_textual: 'Piso salarial diferenciado por cargo/função conforme cláusula 5ª.',
          clausula: 'CLÁUSULA QUINTA — PISO SALARIAL',
          fonte_documento: 'CCT/SP/Sindtest-Vari/CCT_2025_Sindtest_Vari.pdf',
          observacao: null,
          status_parametro: 'extraido_para_revisao', conflito: false, ids_registros_conflitantes: null,
          por_cargo: [
            { cargo: 'Técnico', valor: 2800.00, unidade: 'BRL', status_parametro: 'extraido_para_revisao', conflito: false },
            { cargo: 'Administrativo', valor: 2200.00, unidade: 'BRL', status_parametro: 'extraido_para_revisao', conflito: false },
            { cargo: 'Analista', valor: 3500.00, unidade: 'BRL', status_parametro: 'extraido_para_revisao', conflito: false },
          ],
        },
        auxilio_alimentacao: {
          valor: null, tipo: 'valor_mensal', unidade: 'BRL',
          regra_textual: 'VA/VR varia conforme jornada de trabalho — cláusula 8ª.',
          clausula: 'CLÁUSULA OITAVA — VALE ALIMENTAÇÃO/REFEIÇÃO',
          fonte_documento: 'CCT/SP/Sindtest-Vari/CCT_2025_Sindtest_Vari.pdf',
          observacao: null,
          status_parametro: 'extraido_para_revisao', conflito: false, ids_registros_conflitantes: null,
          por_jornada: [
            { jornada: '8h', valor: 1100.00, unidade: 'BRL', tipo: 'valor_mensal', status_parametro: 'extraido_para_revisao', conflito: false },
            { jornada: '6h', valor: 825.00, unidade: 'BRL', tipo: 'valor_mensal', status_parametro: 'extraido_para_revisao', conflito: false },
          ],
        },
        jornada: {
          valor: null, horas_semanais: null, opcoes_identificadas: null,
          regra_textual: 'Jornada varia conforme escala de trabalho.',
          clausula: 'CLÁUSULA DÉCIMA — JORNADA DE TRABALHO',
          fonte_documento: 'CCT/SP/Sindtest-Vari/CCT_2025_Sindtest_Vari.pdf',
          observacao: null,
          status_parametro: 'extraido_para_revisao', conflito: false, ids_registros_conflitantes: null,
          por_escala: [
            { escala: '6x1', horas_semanais: 36, regra_textual: '6 dias de trabalho e 1 de folga.', status_parametro: 'extraido_para_revisao', conflito: false },
            { escala: '5x2', horas_semanais: 44, regra_textual: '5 dias de trabalho e 2 de folga.', status_parametro: 'extraido_para_revisao', conflito: false },
          ],
        },
        hora_extra: {
          valor: null, tipo: 'percentual', unidade: '%',
          regra_textual: 'Percentuais de hora extra variam por tipo de dia.',
          clausula: 'CLÁUSULA DÉCIMA SEGUNDA — HORAS EXTRAS',
          fonte_documento: 'CCT/SP/Sindtest-Vari/CCT_2025_Sindtest_Vari.pdf',
          observacao: null,
          status_parametro: 'extraido_para_revisao', conflito: false, ids_registros_conflitantes: null,
          por_modalidade: [
            { modalidade: 'Dia útil', percentual: 50, unidade: '%', status_parametro: 'extraido_para_revisao', conflito: false },
            { modalidade: 'Sábado', percentual: 75, unidade: '%', status_parametro: 'extraido_para_revisao', conflito: false },
            { modalidade: 'Dom./Feriado', percentual: 100, unidade: '%', status_parametro: 'extraido_para_revisao', conflito: false },
          ],
        },
      },
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
let elTableContainer;
let elScrollHint;

let filterUf;
let filterSindicato;
let filterAno;
let filterStatus;
let filterCctItem;
let filterItemStatus;
let filterItemPreenchimento;
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
  elTableContainer = document.getElementById('table-responsive-container');
  elScrollHint = document.getElementById('table-scroll-hint');
  elEmptyState = document.getElementById('no-results');

  elTotalRecords = document.getElementById('result-count');

  filterUf = document.getElementById('filter-uf');
  filterSindicato = document.getElementById('filter-sindicato');
  filterAno = document.getElementById('filter-ano');
  filterStatus = document.getElementById('filter-status');
  filterCctItem = document.getElementById('filter-cct-item');
  filterItemStatus = document.getElementById('filter-item-status');
  filterItemPreenchimento = document.getElementById('filter-item-preenchimento');

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
    filterCctItem,
    filterItemStatus,
    filterItemPreenchimento,
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

  if (elTableContainer) {
    elTableContainer.addEventListener('scroll', updateScrollHint, { passive: true });
    window.addEventListener('resize', updateScrollHint, { passive: true });
  }
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
  normalizeItensGovernance(allRecords); // PRJ-51: idempotent; runs after overrides to cover all items
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
      const key = getRecordKey(record);
      if (!key || !overrides[key]) return;

      // Apply record-level overrides only for reviewable records
      const isReviewable =
        record.status_parametro === 'pendente_revisao' ||
        record.status_parametro === 'conflito' ||
        record.conflito === true;
      if (isReviewable) {
        const safe = {};
        OVERRIDE_FIELDS.forEach((field) => {
          if (field in overrides[key]) safe[field] = overrides[key][field];
        });
        Object.assign(record, safe);
      }

      // Apply itens_cct item-level overrides unconditionally
      // (a parent-valid record may still have reviewable items)
      if (overrides[key].itens_cct) {
        record.itens_cct = record.itens_cct || {};
        Object.entries(overrides[key].itens_cct).forEach(([itemKey, itemData]) => {
          record.itens_cct[itemKey] = {
            ...(record.itens_cct[itemKey] || {}),
            ...itemData,
          };
        });
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
    // Merge with existing record override (preserve itens_cct and other keys)
    overrides[key] = { ...(overrides[key] || {}), ...safe };
    localStorage.setItem(OVERRIDES_KEY, JSON.stringify(overrides));
  } catch {
    // ignore localStorage errors (e.g. private mode, quota exceeded)
  }
}

function saveItemCctOverride(recordKey, itemKey, itemData) {
  try {
    const raw = localStorage.getItem(OVERRIDES_KEY) || '{}';
    const overrides = JSON.parse(raw);
    if (!overrides[recordKey]) overrides[recordKey] = {};
    if (!overrides[recordKey].itens_cct) overrides[recordKey].itens_cct = {};
    overrides[recordKey].itens_cct[itemKey] = itemData;
    localStorage.setItem(OVERRIDES_KEY, JSON.stringify(overrides));
  } catch {
    // ignore localStorage errors
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
  const cctItemValue = filterCctItem?.value ?? '';
  const itemStatusValue = filterItemStatus?.value ?? '';
  const itemPreenchimentoValue = filterItemPreenchimento?.value ?? '';

  filteredRecords = allRecords.filter((record) => {
    const isConflict = isConflictRecord(record);
    const status = record.status_parametro === 'pendente_revisao'
      ? 'pendente_revisao'
      : isConflict ? 'conflito' : 'valido';

    const matchesUf = !ufValue || String(record.uf ?? '') === ufValue;
    const matchesSindicato =
      !sindicatoValue ||
      normalizeText(record.sindicato ?? '').includes(normalizeText(sindicatoValue));
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
        ...buildCctSearchTokens(record),
      ].join(' ')
    );

    const matchesSearch = !searchValue || searchableText.includes(searchValue);

    // CCT item filters (AC11, AC12, AC13 + PRJ-52 AC7)
    let matchesCctFilters = true;
    if (cctItemValue || itemStatusValue || itemPreenchimentoValue) {
      matchesCctFilters = false;
      const itens = record.itens_cct || {};

      if (cctItemValue) {
        const item = itens[cctItemValue];
        if (item) {
          const statusOk = !itemStatusValue || itemOrSubitemMatchesStatus(item, itemStatusValue);
          let fillOk = true;
          if (itemPreenchimentoValue === 'preenchido') {
            fillOk = isCctItemPreenchido(cctItemValue, item);
          } else if (itemPreenchimentoValue === 'nao_preenchido') {
            fillOk = !isCctItemPreenchido(cctItemValue, item);
          }
          matchesCctFilters = statusOk && fillOk;
        } else {
          // Item is absent from this record
          // "item X + sem valor" includes records where the item doesn't exist at all
          if (itemPreenchimentoValue === 'nao_preenchido' && !itemStatusValue) {
            matchesCctFilters = true;
          }
        }
      } else {
        // No specific item — match if ANY item satisfies the conditions
        const allItems = Object.entries(itens);
        matchesCctFilters = allItems.some(([itemKey, item]) => {
          const statusOk = !itemStatusValue || itemOrSubitemMatchesStatus(item, itemStatusValue);
          let fillOk = true;
          if (itemPreenchimentoValue === 'preenchido') {
            fillOk = isCctItemPreenchido(itemKey, item);
          } else if (itemPreenchimentoValue === 'nao_preenchido') {
            fillOk = !isCctItemPreenchido(itemKey, item);
          }
          return statusOk && fillOk;
        });
        // Records with no CCT items at all: match only "sem valor" without a status requirement
        if (!matchesCctFilters && allItems.length === 0 && itemPreenchimentoValue === 'nao_preenchido' && !itemStatusValue) {
          matchesCctFilters = true;
        }
      }
    }

    return (
      matchesUf &&
      matchesSindicato &&
      matchesAno &&
      matchesStatus &&
      matchesSearch &&
      matchesCctFilters
    );
  });

  renderTable();
}

function updateScrollHint() {
  if (!elTableContainer || !elScrollHint) return;
  const isScrollable = elTableContainer.scrollWidth > elTableContainer.clientWidth + 2;
  const isScrolledRight =
    elTableContainer.scrollLeft + elTableContainer.clientWidth >= elTableContainer.scrollWidth - 4;
  elScrollHint.classList.toggle('d-none', !isScrollable || isScrolledRight);
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
    const hasCctReview = hasReviewableCctItems(record);

    let btnClass, btnLabel;
    if (isReviewable) {
      btnClass = 'btn btn-sm btn-warning';
      btnLabel = '🔍 Revisar';
    } else if (hasCctReview) {
      btnClass = 'btn btn-sm btn-outline-warning';
      btnLabel = '🔍 Revisar itens';
    } else {
      btnClass = 'btn btn-sm btn-outline-primary';
      btnLabel = 'Detalhes';
    }

    row.innerHTML = `
      <td>${escapeHtml(record.uf ?? '—')}</td>
      <td>${escapeHtml(record.sindicato ?? '—')}</td>
      <td>${escapeHtml(record.categoria ?? '—')}</td>
      <td class="text-end">${escapeHtml(record.ano_referencia ?? '—')}</td>
      <td class="text-end">${formatPercent(record.percentual_reajuste)}</td>
      <td>${formatDate(record.data_base)}</td>
      <td>${formatDate(record.vigencia_inicio)}</td>
      <td>${formatDate(record.vigencia_fim)}</td>
      ${buildCctTableCells(record)}
      <td class="status-group-start">${buildStatusBadge(record)}</td>
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

    if (isReviewable || hasCctReview) {
      row.addEventListener('click', (e) => {
        if (e.target.closest('a') || e.target.closest('.fonte-cell a')) return;
        openDetail(record);
      });
    }

    elTableBody.appendChild(row);
  });

  // Update scroll hint after DOM update (defer so layout is computed)
  setTimeout(updateScrollHint, 0);
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
  const hasCctReview = hasReviewableCctItems(record);
  const modalBody = document.getElementById('detail-modal-body');
  const modalTitle = document.getElementById('detail-modal-label');

  if (modalTitle) {
    let titlePrefix;
    if (isReviewable) {
      titlePrefix = 'Revisão';
    } else if (hasCctReview) {
      titlePrefix = 'Revisar itens CCT';
    } else {
      titlePrefix = 'Detalhe do parâmetro';
    }
    modalTitle.textContent = `${titlePrefix} — ${record.sindicato ?? '—'} — ${record.uf ?? '—'} (${record.ano_referencia ?? '—'})`;
  }

  if (modalBody) {
    modalBody.innerHTML = buildDetailHtml(record, isConflict);

    if (isReviewable) {
      bindReviewControls(record);
    }
    // Always bind CCT item controls — parent may be valid but items may be reviewable
    bindCctItemControls(record);
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
  const itensCctSection = `<div id="cct-items-section">${
    (record.itens_cct && Object.keys(record.itens_cct).length > 0)
      ? buildCctItemsContent(record)
      : ''
  }</div>`;

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

    ${itensCctSection}
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

function buildCctItemsContent(record) {
  const itens = record.itens_cct;
  if (!itens || Object.keys(itens).length === 0) return '';

  let html = `
    <hr class="my-3"/>
    <h3 class="cct-section-title">Itens da CCT</h3>
    <div class="row g-3">`;

  Object.entries(itens).forEach(([itemKey, item]) => {
    html += buildCctItemCard(itemKey, item);
  });

  html += '</div>';
  return html;
}

function buildCctItemCard(itemKey, item) {
  const label = CCT_ITEM_LABELS[itemKey] ?? itemKey;
  const badge = statusBadgeItem(item);
  const effectiveStatus = getItemEffectiveStatus(item);
  const isValido = effectiveStatus === 'valido' && item.conflito !== true;

  // Keep card editable if any subitem still needs review (AC6 granularity — PRJ-52)
  const hasReviewableSubitems = getAllSubitems(item).some(({ sub }) => {
    const subStatus = getSubitemEffectiveStatus(sub);
    return subStatus !== 'valido' || sub.conflito === true;
  });

  if (isValido && !hasReviewableSubitems) {
    return buildCctItemReadOnlyCard(itemKey, item, label, badge);
  }
  return buildCctItemEditCard(itemKey, item, label, badge);
}

function buildCctItemReadOnlyCard(itemKey, item, label, badge) {
  const valorDisplay = formatCctValor(item);
  const fonteRaw = item.fonte_documento ?? null;
  const fonteHtml = fonteRaw
    ? `<a href="${escapeHtml(fonteRaw)}" target="_blank" rel="noopener noreferrer" class="cct-item-meta fonte-link">📄 Abrir PDF</a>`
    : `<span class="cct-item-meta text-secondary">Fonte: —</span>`;

  const specFieldRows = buildItemSpecificFieldsDisplay(itemKey, item);
  const specFieldsHtml = specFieldRows.length > 0
    ? `<dl class="row cct-item-fields">${specFieldRows.join('')}</dl>`
    : '';

  const regraHtml = (item.regra_textual != null && item.regra_textual !== '')
    ? `<div class="cct-item-regra">${escapeHtml(String(item.regra_textual))}</div>`
    : '';

  const obsHtml = (item.observacao != null && item.observacao !== '')
    ? `<div class="cct-item-regra fst-italic mt-1">${escapeHtml(String(item.observacao))}</div>`
    : '';

  const clausulaHtml = (item.clausula != null && item.clausula !== '')
    ? `<div class="cct-item-meta mt-1">${escapeHtml(String(item.clausula))}</div>`
    : '';

  const variationHtml = buildVariationListsReadOnly(itemKey, item);

  return `
    <div class="col-12 col-sm-6">
      <div class="cct-item-card cct-item-card-valido">
        <div class="cct-item-header">
          <span class="cct-item-label">${escapeHtml(label)}</span>
          ${badge}
        </div>
        <div class="cct-item-valor">${valorDisplay}</div>
        ${specFieldsHtml}
        ${clausulaHtml}
        ${regraHtml}
        ${obsHtml}
        ${variationHtml}
        <div class="mt-1">${fonteHtml}</div>
      </div>
    </div>`;
}

function buildCctItemEditCard(itemKey, item, label, badge) {
  const isConflito = item.status_parametro === 'conflito' || item.conflito === true;
  const effectiveStatus = getItemEffectiveStatus(item);
  const isPendente = effectiveStatus === 'pendente_revisao' || effectiveStatus === 'pendente_avaliacao';
  const isExtraido = effectiveStatus === 'extraido_para_revisao';

  const fonteRaw = item.fonte_documento ?? null;
  const fonteHtml = fonteRaw
    ? `<a href="${escapeHtml(fonteRaw)}" target="_blank" rel="noopener noreferrer" class="btn btn-outline-secondary btn-sm py-0 px-2 mb-2">📄 Abrir PDF</a>`
    : '';

  let statusAlertHtml = '';
  if (isConflito) {
    let conflictIdsHtml = '';
    if (Array.isArray(item.ids_registros_conflitantes) && item.ids_registros_conflitantes.length > 0) {
      conflictIdsHtml = '<div class="mt-1">' + item.ids_registros_conflitantes
        .map((id) => `<span class="conflicting-id">${escapeHtml(String(id))}</span>`)
        .join('') + '</div>';
    }
    statusAlertHtml = `<div class="cct-item-alert cct-item-alert-conflito mb-2">⚠ Em conflito — não usar até revisão.${conflictIdsHtml}</div>`;
  } else if (isPendente) {
    statusAlertHtml = `<div class="cct-item-alert cct-item-alert-pendente mb-2">⏳ Aguardando revisão.</div>`;
  } else if (isExtraido) {
    statusAlertHtml = `<div class="cct-item-alert cct-item-alert-extraido mb-2">🔎 Extraído automaticamente — conferir antes de validar.</div>`;
  }

  const regraHtml = (item.regra_textual != null && item.regra_textual !== '')
    ? `<div class="cct-item-regra mb-2">${escapeHtml(String(item.regra_textual))}</div>`
    : '';

  const clausulaHtml = (item.clausula != null && item.clausula !== '')
    ? `<div class="cct-item-meta mb-1">${escapeHtml(String(item.clausula))}</div>`
    : '';

  const fieldDefs = CCT_ITEM_FIELDS[itemKey] ?? [];
  const inputsHtml = fieldDefs.map((fd) => {
    const currentVal = getItemFieldValue(itemKey, fd.key, item);
    const valStr = currentVal != null ? escapeHtml(String(currentVal)) : '';
    const inputId = `cct-item-${itemKey}-${fd.key}`;

    if (fd.type === 'text') {
      return `
        <div class="mb-2">
          <label for="${inputId}" class="form-label form-label-sm mb-1">${escapeHtml(fd.label)}</label>
          <textarea class="form-control form-control-sm" id="${inputId}" rows="2">${valStr}</textarea>
        </div>`;
    }
    return `
      <div class="mb-2">
        <label for="${inputId}" class="form-label form-label-sm mb-1">${escapeHtml(fd.label)}</label>
        <input type="number" class="form-control form-control-sm" id="${inputId}" step="0.01" value="${valStr}" placeholder="—" />
      </div>`;
  }).join('');

  const obsVal = escapeHtml(item.observacao ?? '');
  const obsId = `cct-item-${itemKey}-obs`;

  const variationEditHtml = buildVariationListsEdit(itemKey, item);

  return `
    <div class="col-12 col-sm-6">
      <div class="cct-item-card">
        <div class="cct-item-header">
          <span class="cct-item-label">${escapeHtml(label)}</span>
          ${badge}
        </div>
        ${statusAlertHtml}
        ${fonteHtml}
        ${clausulaHtml}
        ${regraHtml}
        <div class="cct-item-edit-form">
          ${inputsHtml}
          ${variationEditHtml}
          <div class="mb-2">
            <label for="${obsId}" class="form-label form-label-sm mb-1">
              Observação <span class="text-danger">*</span>
            </label>
            <textarea class="form-control form-control-sm" id="${obsId}" rows="2"
              placeholder="Descreva evidência consultada e motivo da decisão.">${obsVal}</textarea>
          </div>
          <div id="cct-item-${itemKey}-error" class="alert alert-danger py-1 small d-none mb-2" role="alert"></div>
          <div class="d-flex gap-2 flex-wrap">
            <button type="button" class="btn btn-success btn-sm" id="btn-cct-val-${itemKey}">
              ✔ Validar item
            </button>
            <button type="button" class="btn btn-outline-warning btn-sm" id="btn-cct-rej-${itemKey}">
              ✗ Rejeitar / manter em revisão
            </button>
          </div>
        </div>
      </div>
    </div>`;
}

/**
 * Gets the display/edit value for a specific field of a CCT item.
 * Handles backward compatibility for older data structures that used
 * generic `valor` + `tipo` instead of named sub-fields.
 */
function getItemFieldValue(itemKey, fieldKey, item) {
  const direct = item[fieldKey];
  if (direct != null && direct !== '') return direct;

  // Backward compat for piso_salarial
  if (itemKey === 'piso_salarial' && item.valor != null) {
    if (fieldKey === 'piso_unico' && item.tipo === 'piso_unico') return item.valor;
    if (fieldKey === 'piso_tecnico' && item.tipo === 'piso_tecnico') return item.valor;
    if (fieldKey === 'piso_administrativo' && item.tipo === 'piso_administrativo') return item.valor;
    if (fieldKey === 'valor_piso_cct' && !['piso_unico', 'piso_tecnico', 'piso_administrativo'].includes(item.tipo)) {
      return item.valor;
    }
  }
  return null;
}

function buildItemSpecificFieldsDisplay(itemKey, item) {
  const fieldDefs = CCT_ITEM_FIELDS[itemKey] ?? [];
  const rows = [];
  fieldDefs.forEach((fd) => {
    const v = getItemFieldValue(itemKey, fd.key, item);
    if (v == null || v === '') return;

    let display;
    if (fd.type === 'number' && fd.unit === '%') {
      const n = Number(v);
      display = isNaN(n) ? escapeHtml(String(v)) : `${n.toLocaleString('pt-BR', { maximumFractionDigits: 2 })}%`;
    } else if (fd.type === 'number' && fd.unit === 'BRL') {
      const n = Number(v);
      display = isNaN(n) ? escapeHtml(String(v)) : n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    } else if (fd.type === 'number') {
      display = escapeHtml(String(v));
    } else {
      const s = String(v);
      display = escapeHtml(s.length > 80 ? s.slice(0, 78) + '…' : s);
    }
    rows.push(`<dt class="col-5">${escapeHtml(fd.label)}</dt><dd class="col-7">${display}</dd>`);
  });
  return rows;
}

function formatCctValor(item) {
  if (item.valor != null) {
    if (typeof item.valor === 'string') return escapeHtml(item.valor);
    if (item.tipo === 'percentual') return `${Number(item.valor).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
    if (item.unidade === 'BRL') {
      return Number(item.valor).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    }
    return escapeHtml(String(item.valor));
  }
  if (item.valor_textual != null && item.valor_textual !== '') {
    return escapeHtml(String(item.valor_textual));
  }
  return '<span class="text-secondary">—</span>';
}

// ── Helpers ──────────────────────────────────────────────────────────

// ── itens_cct governance schema (PRJ-51) ─────────────────────────────────
/**
 * Mandatory common governance fields for every itens_cct item.
 * Used by normalizeItensGovernance() — do not modify without updating that function.
 *
 * Mandatory fields (added with default when absent; NEVER overwritten if already set):
 *   status_parametro           {string}   "pendente_revisao" — review/approval status
 *   origem_regra               {null}     rule source identifier (e.g. normative reference)
 *   fonte_documento            {null}     source document path or reference
 *   clausula                   {null}     clause reference — traceability only, NEVER used as
 *                                         value in table cells; displayed exclusively in modal
 *   observacao                 {null}     free-text analyst observation
 *   conflito                   {false}    boolean conflict flag; default false
 *   ids_registros_conflitantes {null}     list of conflicting record IDs
 *   data_validacao             {null}     ISO timestamp of last manual validation
 *   origem_atualizacao         {null}     who/what last updated this item
 *
 * Optional item-specific fields (preserved as-is, NEVER altered by normalization):
 *   valor, percentual, regra, tipo, unidade  — core value fields (may overlap governance)
 *   regra_textual, valor_textual             — short operational summaries (table OK) or
 *                                              full-text descriptions (modal only)
 *   piso_unico, piso_tecnico, piso_administrativo, valor_piso_cct  — piso_salarial
 *   percentual_padrao, percentual_sabado, percentual_domingo_feriado — hora_extra
 *   horas_semanais, opcoes_identificadas     — jornada
 *   por_cargo, por_jornada, por_modalidade, por_escala — list-valued items (PRJ-52)
 *   trecho_fonte                             — raw source excerpt, traceability only
 */
const ITENS_CCT_GOVERNANCE_DEFAULTS = {
  status_parametro: 'pendente_revisao',
  origem_regra: null,
  fonte_documento: null,
  clausula: null,
  observacao: null,
  conflito: false,
  ids_registros_conflitantes: null,
  data_validacao: null,
  origem_atualizacao: null,
};

/**
 * Normalizes governance fields for all itens_cct items across all records (PRJ-51).
 *
 * Strictly additive and idempotent: fields already present are NEVER overwritten;
 * absent fields are added with their default from ITENS_CCT_GOVERNANCE_DEFAULTS.
 * Applying this function multiple times produces identical results to a single application.
 *
 * Call this after loadLocalOverrides() so that override-merged items are also covered.
 *
 * @param {Array} records - Array of parameter records (mutated in place).
 */
function normalizeItensGovernance(records) {
  if (!Array.isArray(records)) return;
  records.forEach((record) => {
    const itens = record.itens_cct;
    if (!itens || typeof itens !== 'object') return;
    Object.keys(itens).forEach((itemKey) => {
      const item = itens[itemKey];
      if (!item || typeof item !== 'object') return;
      Object.entries(ITENS_CCT_GOVERNANCE_DEFAULTS).forEach(([field, defaultValue]) => {
        if (!(field in item)) {
          item[field] = defaultValue;
        }
      });
      // Also normalize subitems in variation lists (PRJ-52)
      ['por_cargo', 'por_jornada', 'por_modalidade', 'por_escala'].forEach((listKey) => {
        if (!Array.isArray(item[listKey])) return;
        item[listKey].forEach((sub) => {
          if (!sub || typeof sub !== 'object') return;
          if (!('status_parametro' in sub)) sub.status_parametro = 'pendente_revisao';
          if (!('conflito' in sub)) sub.conflito = false;
          if (!('ids_registros_conflitantes' in sub)) sub.ids_registros_conflitantes = null;
        });
      });
    });
  });
}

/**
 * Returns true only when value is a short operational summary suitable for table display (AC6).
 *
 * Rejects full clause texts and legal prose that belong exclusively in the modal:
 *   - texts starting with clause/legal markers (cláusula, parágrafo, inciso, caput, fica)
 *   - multiline text (contains newlines)
 *   - texts longer than 80 characters
 */
function isShortOperationalSummary(value) {
  if (value == null || value === '') return false;
  const s = String(value).trim();
  if (/^(cl[aá]usula|par[aá]grafo|inciso|caput|fica\s)/i.test(s)) return false;
  if (s.includes('\n') || s.includes('\r')) return false;
  return s.length <= 80;
}

/** Labels for itens_cct keys */
const CCT_ITEM_LABELS = {
  reajuste_salarial: 'Reajuste Salarial',
  piso_salarial: 'Piso Salarial',
  adicional_noturno: 'Adicional Noturno',
  auxilio_alimentacao: 'Auxílio Alimentação/Refeição',
  plr: 'PLR',
  hora_extra: 'Hora Extra',
  sobreaviso: 'Sobreaviso',
  jornada: 'Jornada',
};

/** Editable field definitions for each CCT item type */
const CCT_ITEM_FIELDS = {
  reajuste_salarial: [
    { key: 'valor', label: 'Percentual (%)', type: 'number', unit: '%' },
    { key: 'regra_textual', label: 'Regra textual', type: 'text', unit: null },
  ],
  piso_salarial: [
    { key: 'valor_piso_cct', label: 'Piso CCT (R$)', type: 'number', unit: 'BRL' },
    { key: 'piso_tecnico', label: 'Piso técnico (R$)', type: 'number', unit: 'BRL' },
    { key: 'piso_administrativo', label: 'Piso adm. (R$)', type: 'number', unit: 'BRL' },
    { key: 'piso_unico', label: 'Piso único (R$)', type: 'number', unit: 'BRL' },
    { key: 'regra_textual', label: 'Regra textual', type: 'text', unit: null },
  ],
  adicional_noturno: [
    { key: 'percentual', label: 'Percentual (%)', type: 'number', unit: '%' },
    { key: 'valor', label: 'Valor (R$)', type: 'number', unit: 'BRL' },
    { key: 'regra_textual', label: 'Regra textual', type: 'text', unit: null },
  ],
  auxilio_alimentacao: [
    { key: 'valor', label: 'Valor (R$)', type: 'number', unit: 'BRL' },
    { key: 'regra_textual', label: 'Regra textual', type: 'text', unit: null },
  ],
  plr: [
    { key: 'valor', label: 'Valor (R$)', type: 'number', unit: 'BRL' },
    { key: 'percentual', label: 'Percentual (%)', type: 'number', unit: '%' },
    { key: 'regra_textual', label: 'Regra textual', type: 'text', unit: null },
  ],
  hora_extra: [
    { key: 'percentual_padrao', label: 'H.E. padrão (%)', type: 'number', unit: '%' },
    { key: 'percentual_sabado', label: 'H.E. sábado (%)', type: 'number', unit: '%' },
    { key: 'percentual_domingo_feriado', label: 'H.E. dom./feriado (%)', type: 'number', unit: '%' },
    { key: 'regra_textual', label: 'Regra textual', type: 'text', unit: null },
  ],
  sobreaviso: [
    { key: 'percentual', label: 'Percentual (%)', type: 'number', unit: '%' },
    { key: 'regra_textual', label: 'Regra textual', type: 'text', unit: null },
  ],
  jornada: [
    { key: 'horas_semanais', label: 'Horas semanais', type: 'number', unit: null },
    { key: 'opcoes_identificadas', label: 'Opções identificadas', type: 'text', unit: null },
    { key: 'regra_textual', label: 'Regra textual', type: 'text', unit: null },
  ],
};

/** Minimum fields required (at least one) before allowing item validation */
const CCT_ITEM_MIN_FIELDS = {
  reajuste_salarial: ['valor'],
  piso_salarial: ['valor_piso_cct', 'piso_tecnico', 'piso_administrativo', 'piso_unico', 'regra_textual'],
  adicional_noturno: ['percentual', 'valor', 'regra_textual'],
  auxilio_alimentacao: ['valor', 'regra_textual'],
  plr: ['valor', 'percentual', 'regra_textual'],
  hora_extra: ['percentual_padrao', 'percentual_sabado', 'percentual_domingo_feriado', 'regra_textual'],
  sobreaviso: ['percentual', 'regra_textual'],
  jornada: ['horas_semanais', 'opcoes_identificadas', 'regra_textual'],
};

/**
 * Returns the reajuste valor using itens_cct as the canonical source,
 * falling back to the legacy flat field for backward compatibility.
 */
function getReajusteValor(r) {
  return r.itens_cct?.reajuste_salarial?.valor ?? r.percentual_reajuste ?? null;
}

function hasReviewableCctItems(record) {
  const itens = record.itens_cct;
  if (!itens) return false;
  return Object.values(itens).some((item) => {
    const effectiveStatus = getItemEffectiveStatus(item);
    if (effectiveStatus === 'extraido_para_revisao' ||
      effectiveStatus === 'pendente_revisao' ||
      effectiveStatus === 'pendente_avaliacao' ||
      effectiveStatus === 'conflito' ||
      item.conflito === true) {
      return true;
    }
    // Also check subitems in variation lists (PRJ-52)
    return getAllSubitems(item).some(({ sub }) => {
      const subStatus = getSubitemEffectiveStatus(sub);
      return subStatus === 'extraido_para_revisao' ||
        subStatus === 'pendente_revisao' ||
        subStatus === 'pendente_avaliacao' ||
        subStatus === 'conflito' ||
        sub.conflito === true;
    });
  });
}

/**
 * Returns the effective display status of a CCT item, applying governance rules (AC14).
 * Items that were not manually validated must never appear as 'valido'.
 */
function getItemEffectiveStatus(item) {
  if (!item) return null;
  if (item.status_parametro === 'valido' && item.origem_atualizacao !== 'validacao_manual_item_cct') {
    return 'extraido_para_revisao';
  }
  return item.status_parametro;
}

// ── PRJ-52: Variation list helpers ───────────────────────────────────────────

/**
 * Metadata for each variation list: label shown in modal, keys to try as identifier, label for that key.
 */
const VARIATION_LIST_META = {
  por_cargo: {
    label: 'Por Cargo / Função',
    identifierKeys: ['cargo', 'funcao', 'identificador'],
    identifierLabel: 'Cargo/Função',
  },
  por_jornada: {
    label: 'Por Jornada',
    identifierKeys: ['jornada', 'tipo_jornada', 'identificador'],
    identifierLabel: 'Jornada',
  },
  por_modalidade: {
    label: 'Por Modalidade',
    identifierKeys: ['modalidade', 'identificador'],
    identifierLabel: 'Modalidade',
  },
  por_escala: {
    label: 'Por Escala',
    identifierKeys: ['escala', 'tipo_escala', 'identificador'],
    identifierLabel: 'Escala',
  },
};

/** Returns all subitem entries from all variation lists in a CCT item. */
function getAllSubitems(item) {
  if (!item) return [];
  const subitems = [];
  Object.keys(VARIATION_LIST_META).forEach((listKey) => {
    if (!Array.isArray(item[listKey])) return;
    item[listKey].forEach((sub, index) => {
      if (sub && typeof sub === 'object') subitems.push({ listKey, index, sub });
    });
  });
  return subitems;
}

/**
 * Effective status for a subitem in a variation list.
 * Same governance rule as getItemEffectiveStatus: manual validation required for 'valido'.
 */
function getSubitemEffectiveStatus(sub) {
  if (!sub) return null;
  if (sub.status_parametro === 'valido' && sub.origem_atualizacao !== 'validacao_manual_item_cct') {
    return 'extraido_para_revisao';
  }
  return sub.status_parametro || 'pendente_revisao';
}

/** Returns true when a subitem is immutably validated and must not be overwritten. */
function isSubitemImmutable(sub) {
  return sub != null &&
    sub.status_parametro === 'valido' &&
    sub.origem_atualizacao === 'validacao_manual_item_cct';
}

/** Status badge HTML for a subitem. */
function statusBadgeSubitem(sub) {
  if (!sub) return '';
  const effectiveStatus = getSubitemEffectiveStatus(sub);
  if (effectiveStatus === 'conflito' || sub.conflito === true) {
    return '<span class="badge-conflito">⚠ Conflito</span>';
  }
  if (effectiveStatus === 'pendente_revisao' || effectiveStatus === 'pendente_avaliacao') {
    return '<span class="badge-pendente">⏳ Pendente</span>';
  }
  if (effectiveStatus === 'extraido_para_revisao') {
    return '<span class="badge-extraido">🔎 Extraído</span>';
  }
  return '<span class="badge-valido">✔ Válido</span>';
}

/** Extracts the identifier string from a subitem using the provided key list. */
function getSubitemIdentifier(sub, identifierKeys) {
  for (const k of identifierKeys) {
    if (sub[k] != null && sub[k] !== '') return String(sub[k]);
  }
  return '—';
}

/**
 * Formats the primary value of a subitem for display.
 * Tries valor, percentual, horas_semanais/horas_mensais, valor_textual in that order.
 */
function getSubitemValueDisplay(sub) {
  if (!sub) return '<span class="text-secondary">—</span>';
  if (sub.valor != null) {
    const n = Number(sub.valor);
    if (!isNaN(n)) {
      const unidade = (sub.unidade ?? '').toLowerCase();
      const tipo = sub.tipo ?? '';
      if (unidade === 'brl' || unidade.startsWith('brl/') || tipo === 'valor_mensal' || tipo === 'valor_diario') {
        const brl = n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
        if (unidade.includes('/mes') || unidade.includes('/mês') || tipo === 'valor_mensal') return `${brl}/mês`;
        if (unidade.includes('/dia') || tipo === 'valor_diario') return `${brl}/dia`;
        return brl;
      }
      if (unidade === '%' || tipo === 'percentual') {
        return `${n.toLocaleString('pt-BR', { maximumFractionDigits: 2 })}%`;
      }
      return escapeHtml(String(n));
    }
  }
  if (sub.percentual != null) {
    const n = Number(sub.percentual);
    if (!isNaN(n)) return `${n.toLocaleString('pt-BR', { maximumFractionDigits: 2 })}%`;
  }
  if (sub.horas_semanais != null) return `${escapeHtml(String(sub.horas_semanais))}h/sem.`;
  if (sub.horas_mensais != null) return `${escapeHtml(String(sub.horas_mensais))}h/mês`;
  if (sub.valor_textual != null && sub.valor_textual !== '') return escapeHtml(String(sub.valor_textual));
  if (sub.regra_textual != null && sub.regra_textual !== '') {
    const s = String(sub.regra_textual);
    return escapeHtml(s.length > 60 ? s.slice(0, 58) + '…' : s);
  }
  return '<span class="text-secondary">—</span>';
}

/**
 * Builds a short summary label for a variation list for table display (AC9).
 * 1 entry → show value directly (or identifier if no value)
 * 2 entries → "Label1/Label2"
 * 3+ entries → "Múltiplos"
 */
function buildVariationCellSummary(items, identifierKeys) {
  if (!Array.isArray(items) || items.length === 0) return null;
  // Deduplicated labels
  const labels = [...new Set(
    items
      .map((entry) => {
        if (!entry || typeof entry !== 'object') return null;
        for (const k of identifierKeys) {
          if (entry[k] != null && entry[k] !== '') return String(entry[k]);
        }
        return null;
      })
      .filter(Boolean)
  )];
  if (items.length === 1) {
    // Single entry: show value or identifier
    return labels[0] ?? '—';
  }
  if (labels.length === 0) return 'Múltiplos';
  if (labels.length <= 2) return labels.map(escapeHtml).join('/');
  return 'Múltiplos';
}

/**
 * Returns true when an item OR any of its variation-list subitems matches
 * the given status filter value (AC7).
 */
function itemOrSubitemMatchesStatus(item, itemStatusValue) {
  if (!itemStatusValue) return true;
  const effectiveStatus = getItemEffectiveStatus(item);
  if (effectiveStatus === itemStatusValue) return true;
  if (itemStatusValue === 'conflito' && item.conflito === true) return true;
  return getAllSubitems(item).some(({ sub }) => {
    const subStatus = getSubitemEffectiveStatus(sub);
    return subStatus === itemStatusValue || (itemStatusValue === 'conflito' && sub.conflito === true);
  });
}

/**
 * Builds HTML for variation lists displayed as read-only (inside a validated item card).
 */
function buildVariationListsReadOnly(itemKey, item) {
  let html = '';
  Object.entries(VARIATION_LIST_META).forEach(([listKey, meta]) => {
    const list = item[listKey];
    if (!Array.isArray(list) || list.length === 0) return;
    html += `
      <div class="variation-list-section mt-2">
        <div class="variation-list-label">${escapeHtml(meta.label)}</div>
        <table class="variation-table">
          <tbody>`;
    list.forEach((sub) => {
      if (!sub || typeof sub !== 'object') return;
      const identifier = getSubitemIdentifier(sub, meta.identifierKeys);
      const valueDisplay = getSubitemValueDisplay(sub);
      const badge = statusBadgeSubitem(sub);
      html += `<tr>
          <td class="variation-td-id">${escapeHtml(identifier)}</td>
          <td class="variation-td-val">${valueDisplay}</td>
          <td class="variation-td-badge">${badge}</td>
        </tr>`;
      if (sub.regra_textual) {
        html += `<tr><td colspan="3" class="variation-td-regra">${escapeHtml(String(sub.regra_textual))}</td></tr>`;
      }
    });
    html += '</tbody></table></div>';
  });
  return html;
}

/**
 * Builds HTML for variation lists in an editable item card, with per-subitem validate/reject (AC6).
 */
function buildVariationListsEdit(itemKey, item) {
  let html = '';
  Object.entries(VARIATION_LIST_META).forEach(([listKey, meta]) => {
    const list = item[listKey];
    if (!Array.isArray(list) || list.length === 0) return;
    html += `<div class="variation-list-section variation-list-edit mt-2">
      <div class="variation-list-label">${escapeHtml(meta.label)}</div>`;
    list.forEach((sub, idx) => {
      if (!sub || typeof sub !== 'object') return;
      html += buildSubitemEditBlock(itemKey, listKey, idx, sub, meta);
    });
    html += '</div>';
  });
  return html;
}

/** Builds the HTML block for a single subitem in edit mode. */
function buildSubitemEditBlock(itemKey, listKey, idx, sub, meta) {
  const effectiveStatus = getSubitemEffectiveStatus(sub);
  const isImmutable = isSubitemImmutable(sub);
  const identifier = getSubitemIdentifier(sub, meta.identifierKeys);
  const badge = statusBadgeSubitem(sub);
  const valueDisplay = getSubitemValueDisplay(sub);

  // Read-only for immutably validated subitems (AC6)
  if (isImmutable) {
    const regraHtml = sub.regra_textual
      ? `<div class="small text-muted mt-1">${escapeHtml(String(sub.regra_textual))}</div>`
      : '';
    return `<div class="cct-subitem-card cct-subitem-valido">
      <div class="cct-subitem-header">
        <span class="cct-subitem-id">${escapeHtml(identifier)}</span>
        <span class="cct-subitem-val">${valueDisplay}</span>
        ${badge}
      </div>
      ${regraHtml}
    </div>`;
  }

  // Editable subitem
  const obsId = `cct-subitem-${itemKey}-${listKey}-${idx}-obs`;
  const errId = `cct-subitem-${itemKey}-${listKey}-${idx}-error`;
  const obsVal = escapeHtml(sub.observacao ?? '');
  const regraHtml = sub.regra_textual
    ? `<div class="cct-item-regra small mb-1">${escapeHtml(String(sub.regra_textual))}</div>`
    : '';

  let statusAlertHtml = '';
  if (effectiveStatus === 'conflito' || sub.conflito === true) {
    statusAlertHtml = `<div class="cct-item-alert cct-item-alert-conflito mb-1 py-1 small">⚠ Em conflito — não usar até revisão.</div>`;
  } else if (effectiveStatus === 'extraido_para_revisao') {
    statusAlertHtml = `<div class="cct-item-alert cct-item-alert-extraido mb-1 py-1 small">🔎 Extraído — conferir antes de validar.</div>`;
  } else {
    statusAlertHtml = `<div class="cct-item-alert cct-item-alert-pendente mb-1 py-1 small">⏳ Aguardando revisão.</div>`;
  }

  return `<div class="cct-subitem-card cct-subitem-edit">
    <div class="cct-subitem-header">
      <span class="cct-subitem-id">${escapeHtml(identifier)}</span>
      <span class="cct-subitem-val">${valueDisplay}</span>
      ${badge}
    </div>
    ${statusAlertHtml}
    ${regraHtml}
    <div class="mb-1">
      <label for="${obsId}" class="form-label form-label-sm mb-0">
        Observação <span class="text-danger">*</span>
      </label>
      <textarea class="form-control form-control-sm" id="${obsId}" rows="1"
        placeholder="Motivo da decisão">${obsVal}</textarea>
    </div>
    <div id="${errId}" class="alert alert-danger py-1 small d-none mb-1" role="alert"></div>
    <div class="d-flex gap-1">
      <button type="button" class="btn btn-success btn-sm py-0 px-2"
        id="btn-cct-sub-val-${itemKey}-${listKey}-${idx}">✔ Validar</button>
      <button type="button" class="btn btn-outline-warning btn-sm py-0 px-2"
        id="btn-cct-sub-rej-${itemKey}-${listKey}-${idx}">✗ Rejeitar</button>
    </div>
  </div>`;
}

/**
 * Collects searchable text tokens from all itens_cct entries (AC7).
 * Includes item labels, values, rules, observations, clauses, and cargo/jornada info.
 */
function buildCctSearchTokens(record) {
  const itens = record.itens_cct;
  if (!itens) return [];
  const tokens = [];
  Object.entries(itens).forEach(([itemKey, item]) => {
    if (!item) return;
    tokens.push(CCT_ITEM_LABELS[itemKey] ?? itemKey);
    [
      item.valor_textual,
      item.regra_textual,
      item.observacao,
      item.clausula,
      item.fonte_documento,
      item.opcoes_identificadas,
    ].forEach((v) => { if (v != null && v !== '') tokens.push(String(v)); });
    // Numeric values (e.g. "40", "44h")
    ['valor', 'percentual', 'horas_semanais', 'horas_mensais'].forEach((f) => {
      if (item[f] != null) tokens.push(String(item[f]));
    });
    // Lists
    ['por_cargo', 'por_jornada', 'por_modalidade', 'por_escala'].forEach((f) => {
      if (Array.isArray(item[f])) {
        item[f].forEach((entry) => {
          if (typeof entry === 'object' && entry !== null) {
            Object.values(entry).forEach((v) => { if (v != null) tokens.push(String(v)); });
          } else if (entry != null) {
            tokens.push(String(entry));
          }
        });
      }
    });
  });
  return tokens;
}

/**
 * Returns true when a CCT item has a meaningful value that counts as "preenchido" (AC5).
 */
function isCctItemPreenchido(itemKey, item) {
  if (!item) return false;

  // Scalar fields that count as "preenchido" per AC5
  const scalarFields = [
    'valor', 'percentual', 'regra', 'regra_textual', 'valor_textual',
    'valor_piso_cct', 'piso_tecnico', 'piso_administrativo', 'piso_unico',
    'percentual_padrao', 'percentual_dia_util', 'percentual_sabado',
    'percentual_domingo', 'percentual_domingo_feriado', 'percentual_feriado',
    'horas_semanais', 'horas_mensais', 'valor_mensal', 'valor_dia_util',
  ];
  if (scalarFields.some((k) => item[k] != null && item[k] !== '')) return true;

  // Backward-compat: derive from tipo+valor for piso_salarial
  if (itemKey === 'piso_salarial' && item.valor != null && item.valor !== '') return true;

  // List fields (non-empty array with at least one meaningful entry counts as preenchido)
  const listFields = ['por_cargo', 'por_jornada', 'por_modalidade', 'por_escala'];
  if (listFields.some((k) => {
    const arr = item[k];
    if (!Array.isArray(arr) || arr.length === 0) return false;
    // At least one entry must have a meaningful identifier or value
    return arr.some((entry) => entry && typeof entry === 'object' &&
      Object.values(entry).some((v) => v != null && v !== '' && typeof v !== 'object'));
  })) return true;
  // opcoes_identificadas may be string or array
  if (Array.isArray(item.opcoes_identificadas) && item.opcoes_identificadas.length > 0) return true;

  return false;
}

/** Generates 12 CCT item columns for the main table row */
function buildCctTableCells(record) {
  function cellGet(itemKey, ...fields) {
    const item = record.itens_cct?.[itemKey];
    if (!item) return null;
    for (const f of fields) {
      const v = item[f];
      if (v != null && v !== '') return v;
    }
    return null;
  }

  function fmtBRL(v) {
    if (v == null) return '—';
    const n = Number(v);
    if (isNaN(n)) return escapeHtml(String(v).slice(0, 22));
    return n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  }

  function fmtPct(v) {
    if (v == null) return '—';
    const n = Number(v);
    if (isNaN(n)) return escapeHtml(String(v).slice(0, 22));
    return n.toLocaleString('pt-BR', { maximumFractionDigits: 2 }) + '%';
  }

  function fmtShort(v) {
    if (v == null) return '—';
    const s = String(v);
    return escapeHtml(s.length > 22 ? s.slice(0, 20) + '…' : s);
  }

  // Wraps variation summary text in a styled span (AC9)
  function variationSummarySpan(text, title) {
    return `<span class="cct-variation-summary" title="${escapeHtml(title)}">${escapeHtml(text)}</span>`;
  }

  // Backward compat: derive piso columns from tipo+valor when specific fields absent
  const pisoItem = record.itens_cct?.piso_salarial;
  const pisoCct = cellGet('piso_salarial', 'valor_piso_cct')
    ?? (pisoItem?.valor != null && !['piso_unico', 'piso_tecnico', 'piso_administrativo'].includes(pisoItem.tipo)
      ? pisoItem.valor : null);
  const pisoTec = cellGet('piso_salarial', 'piso_tecnico')
    ?? (pisoItem?.tipo === 'piso_tecnico' ? pisoItem?.valor ?? null : null);
  const pisoAdm = cellGet('piso_salarial', 'piso_administrativo')
    ?? (pisoItem?.tipo === 'piso_administrativo' ? pisoItem?.valor ?? null : null);
  const pisoUnico = cellGet('piso_salarial', 'piso_unico')
    ?? (pisoItem?.tipo === 'piso_unico' ? pisoItem?.valor ?? null : null);

  // PRJ-52 AC9: piso_salarial variation summary when no scalar values exist
  let pisoCctDisplay = fmtBRL(pisoCct);
  if (pisoCctDisplay === '—' && pisoItem) {
    const pisoCargo = pisoItem.por_cargo;
    if (Array.isArray(pisoCargo) && pisoCargo.length > 0) {
      const summary = buildVariationCellSummary(pisoCargo, ['cargo', 'funcao', 'identificador']);
      if (summary && summary !== '—') {
        pisoCctDisplay = variationSummarySpan(summary, 'Múltiplas variações por cargo — ver detalhes');
      }
    }
  }

  const adNoturno = cellGet('adicional_noturno', 'percentual', 'valor');
  const vrItem = record.itens_cct?.auxilio_alimentacao ?? null;

  // PRJ-52 AC9: auxilio_alimentacao variation summary when no scalar valor exists
  let vrDisplay = fmtVR(vrItem);
  if (vrDisplay === '—' && vrItem) {
    const porJornada = vrItem.por_jornada;
    const porModalidade = vrItem.por_modalidade;
    if (Array.isArray(porJornada) && porJornada.length > 0) {
      const summary = buildVariationCellSummary(porJornada, ['jornada', 'tipo_jornada', 'identificador']);
      if (summary && summary !== '—') {
        vrDisplay = variationSummarySpan(summary, 'Variações por jornada — ver detalhes');
      }
    } else if (Array.isArray(porModalidade) && porModalidade.length > 0) {
      const summary = buildVariationCellSummary(porModalidade, ['modalidade', 'identificador']);
      if (summary && summary !== '—') {
        vrDisplay = variationSummarySpan(summary, 'Variações por modalidade — ver detalhes');
      }
    }
  }

  // PLR: numeric value preferred; regra_textual only if it is a short operational summary (AC6)
  const plrNumeric = cellGet('plr', 'valor', 'percentual');
  const plrRegra = cellGet('plr', 'regra_textual');
  const plrVal = plrNumeric ?? (isShortOperationalSummary(plrRegra) ? plrRegra : null);
  const heP = cellGet('hora_extra', 'percentual_padrao');
  const heSab = cellGet('hora_extra', 'percentual_sabado');
  const heDom = cellGet('hora_extra', 'percentual_domingo_feriado');

  // PRJ-52 AC9: hora_extra por_modalidade summary
  const heItem = record.itens_cct?.hora_extra ?? null;
  let hePDisplay = heP != null ? fmtPct(heP) : '—';
  if (hePDisplay === '—' && heItem) {
    const porModalidade = heItem.por_modalidade;
    if (Array.isArray(porModalidade) && porModalidade.length > 0) {
      const summary = buildVariationCellSummary(porModalidade, ['modalidade', 'identificador']);
      if (summary && summary !== '—') {
        hePDisplay = variationSummarySpan(summary, 'Variações por modalidade — ver detalhes');
      }
    }
  }

  // Sobreaviso: percentual preferred; regra_textual only if short operational summary (AC6)
  const sobNumeric = cellGet('sobreaviso', 'percentual');
  const sobRegra = cellGet('sobreaviso', 'regra_textual');
  const sob = sobNumeric ?? (isShortOperationalSummary(sobRegra) ? sobRegra : null);
  const jornadaItem = record.itens_cct?.jornada ?? null;

  const adNoturnoFmt = adNoturno != null
    ? (typeof adNoturno === 'number' ? fmtPct(adNoturno) : fmtShort(String(adNoturno)))
    : '—';
  const sobFmt = sob != null
    ? (typeof sob === 'number' ? fmtPct(sob) : fmtShort(String(sob)))
    : '—';

  // PRJ-52 AC9: jornada por_escala summary
  let jornadaDisplay = fmtJornada(jornadaItem);
  if (jornadaDisplay === '—' && jornadaItem) {
    const porEscala = jornadaItem.por_escala;
    if (Array.isArray(porEscala) && porEscala.length > 0) {
      const summary = buildVariationCellSummary(porEscala, ['escala', 'tipo_escala', 'identificador']);
      if (summary && summary !== '—') {
        jornadaDisplay = variationSummarySpan(summary, 'Variações por escala — ver detalhes');
      }
    }
  }

  return [
    `<td class="cct-col cct-group-start">${pisoCctDisplay}</td>`,
    `<td class="cct-col">${fmtBRL(pisoTec)}</td>`,
    `<td class="cct-col">${fmtBRL(pisoAdm)}</td>`,
    `<td class="cct-col">${fmtBRL(pisoUnico)}</td>`,
    `<td class="cct-col">${adNoturnoFmt}</td>`,
    `<td class="cct-col">${vrDisplay}</td>`,
    `<td class="cct-col">${fmtShort(plrVal)}</td>`,
    `<td class="cct-col">${hePDisplay}</td>`,
    `<td class="cct-col">${heSab != null ? fmtPct(heSab) : '—'}</td>`,
    `<td class="cct-col">${heDom != null ? fmtPct(heDom) : '—'}</td>`,
    `<td class="cct-col">${sobFmt}</td>`,
    `<td class="cct-col">${jornadaDisplay}</td>`,
  ].join('');
}

function bindCctItemControls(record) {
  if (!record.itens_cct) return;
  Object.keys(record.itens_cct).forEach((itemKey) => {
    const btnVal = document.getElementById(`btn-cct-val-${itemKey}`);
    const btnRej = document.getElementById(`btn-cct-rej-${itemKey}`);
    if (btnVal) btnVal.addEventListener('click', () => validateCctItem(record, itemKey));
    if (btnRej) btnRej.addEventListener('click', () => rejectCctItem(record, itemKey));

    // Bind per-subitem validate/reject buttons (PRJ-52)
    const item = record.itens_cct[itemKey];
    if (!item) return;
    Object.keys(VARIATION_LIST_META).forEach((listKey) => {
      if (!Array.isArray(item[listKey])) return;
      item[listKey].forEach((_sub, idx) => {
        const btnSubVal = document.getElementById(`btn-cct-sub-val-${itemKey}-${listKey}-${idx}`);
        const btnSubRej = document.getElementById(`btn-cct-sub-rej-${itemKey}-${listKey}-${idx}`);
        if (btnSubVal) btnSubVal.addEventListener('click', () => validateSubitem(record, itemKey, listKey, idx));
        if (btnSubRej) btnSubRej.addEventListener('click', () => rejectSubitem(record, itemKey, listKey, idx));
      });
    });
  });
}

function validateCctItem(record, itemKey) {
  const item = record.itens_cct?.[itemKey];
  if (!item) return;

  const errorEl = document.getElementById(`cct-item-${itemKey}-error`);
  const obsEl = document.getElementById(`cct-item-${itemKey}-obs`);
  const observacao = obsEl?.value?.trim() ?? '';

  // Collect field values from form inputs
  const fields = {};
  (CCT_ITEM_FIELDS[itemKey] ?? []).forEach((fd) => {
    const el = document.getElementById(`cct-item-${itemKey}-${fd.key}`);
    if (!el) return;
    const val = el.value.trim();
    if (val === '') return;
    if (fd.type === 'number') {
      const n = parseFloat(val);
      if (!isNaN(n)) fields[fd.key] = n;
    } else {
      fields[fd.key] = val;
    }
  });

  // Validate minimum fields (AC15): combine form values with pre-existing item values
  const effectiveValues = { ...item, ...fields };
  const minKeys = CCT_ITEM_MIN_FIELDS[itemKey] ?? [];
  // Variation lists (por_cargo etc.) also count as having content (PRJ-52)
  const hasVariationEntries = ['por_cargo', 'por_jornada', 'por_modalidade', 'por_escala']
    .some((k) => Array.isArray(effectiveValues[k]) && effectiveValues[k].length > 0);
  const hasMin = minKeys.length === 0
    || minKeys.some((k) => effectiveValues[k] != null && effectiveValues[k] !== '')
    || hasVariationEntries;

  if (!hasMin) {
    if (errorEl) {
      errorEl.textContent = `Preencha ao menos um campo: ${minKeys.join(', ')}.`;
      errorEl.classList.remove('d-none');
    }
    return;
  }

  if (!observacao) {
    if (errorEl) {
      errorEl.textContent = 'Observação obrigatória.';
      errorEl.classList.remove('d-none');
    }
    return;
  }

  if (errorEl) errorEl.classList.add('d-none');

  const now = new Date().toISOString();
  record.itens_cct[itemKey] = {
    ...item,
    ...fields,
    status_parametro: 'valido',
    conflito: false,
    ids_registros_conflitantes: null,
    observacao,
    origem_atualizacao: 'validacao_manual_item_cct',
    data_validacao: now,
    data_hora_validacao_manual: now,
    status_anterior: item.status_parametro,
  };

  saveItemCctOverride(getRecordKey(record), itemKey, record.itens_cct[itemKey]);
  updateLocalChangesBanner();
  applyFilters();
  refreshCctItemsSection(record);
}

function rejectCctItem(record, itemKey) {
  const item = record.itens_cct?.[itemKey];
  if (!item) return;

  const obsEl = document.getElementById(`cct-item-${itemKey}-obs`);
  const observacao = obsEl?.value?.trim() ?? '';

  const now = new Date().toISOString();
  const wasConflito = item.conflito === true || item.status_parametro === 'conflito';

  record.itens_cct[itemKey] = {
    ...item,
    status_parametro: wasConflito ? 'conflito' : 'pendente_revisao',
    conflito: wasConflito,
    observacao: observacao || item.observacao || null,
    origem_atualizacao: 'rejeicao_manual_item_cct',
    data_hora_rejeicao_manual: now,
    status_anterior: item.status_parametro,
  };

  saveItemCctOverride(getRecordKey(record), itemKey, record.itens_cct[itemKey]);
  updateLocalChangesBanner();
  applyFilters();
  refreshCctItemsSection(record);
}

/** Targeted re-render of just the CCT items section — preserves record-level form values */
function refreshCctItemsSection(record) {
  const section = document.getElementById('cct-items-section');
  if (!section) return;
  const itens = record.itens_cct;
  section.innerHTML = (itens && Object.keys(itens).length > 0)
    ? buildCctItemsContent(record)
    : '';
  bindCctItemControls(record);
}

// ── PRJ-52: Per-subitem validation ────────────────────────────────────────────

/**
 * Validates a single subitem in a variation list.
 * AC6: immutably-validated subitems cannot be overwritten.
 */
function validateSubitem(record, itemKey, listKey, subIndex) {
  const item = record.itens_cct?.[itemKey];
  if (!item) return;
  const list = item[listKey];
  if (!Array.isArray(list) || subIndex >= list.length) return;
  const sub = list[subIndex];
  if (!sub) return;

  // AC6: immutable subitems cannot be re-validated
  if (isSubitemImmutable(sub)) return;

  const errId = `cct-subitem-${itemKey}-${listKey}-${subIndex}-error`;
  const obsId = `cct-subitem-${itemKey}-${listKey}-${subIndex}-obs`;
  const errorEl = document.getElementById(errId);
  const obsEl = document.getElementById(obsId);
  const observacao = obsEl?.value?.trim() ?? '';

  if (!observacao) {
    if (errorEl) {
      errorEl.textContent = 'Observação obrigatória.';
      errorEl.classList.remove('d-none');
    }
    return;
  }
  if (errorEl) errorEl.classList.add('d-none');

  const now = new Date().toISOString();
  list[subIndex] = {
    ...sub,
    status_parametro: 'valido',
    conflito: false,
    ids_registros_conflitantes: null,
    observacao,
    origem_atualizacao: 'validacao_manual_item_cct',
    data_validacao: now,
    data_hora_validacao_manual: now,
    status_anterior: sub.status_parametro,
  };

  saveItemCctOverride(getRecordKey(record), itemKey, item);
  updateLocalChangesBanner();
  applyFilters();
  refreshCctItemsSection(record);
}

/**
 * Rejects/keeps a single subitem in pending state.
 * AC6: immutably-validated subitems cannot be overwritten.
 */
function rejectSubitem(record, itemKey, listKey, subIndex) {
  const item = record.itens_cct?.[itemKey];
  if (!item) return;
  const list = item[listKey];
  if (!Array.isArray(list) || subIndex >= list.length) return;
  const sub = list[subIndex];
  if (!sub) return;

  // AC6: immutable subitems cannot be rejected
  if (isSubitemImmutable(sub)) return;

  const obsId = `cct-subitem-${itemKey}-${listKey}-${subIndex}-obs`;
  const obsEl = document.getElementById(obsId);
  const observacao = obsEl?.value?.trim() ?? '';

  const now = new Date().toISOString();
  const wasConflito = sub.conflito === true || sub.status_parametro === 'conflito';

  list[subIndex] = {
    ...sub,
    status_parametro: wasConflito ? 'conflito' : 'pendente_revisao',
    conflito: wasConflito,
    observacao: observacao || sub.observacao || null,
    origem_atualizacao: 'rejeicao_manual_item_cct',
    data_hora_rejeicao_manual: now,
    status_anterior: sub.status_parametro,
  };

  saveItemCctOverride(getRecordKey(record), itemKey, item);
  updateLocalChangesBanner();
  applyFilters();
  refreshCctItemsSection(record);
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
  const effectiveStatus = getItemEffectiveStatus(item);
  if (effectiveStatus === 'conflito' || item.conflito === true) {
    return '<span class="badge-conflito">⚠ Conflito</span>';
  }
  if (effectiveStatus === 'pendente_revisao' || effectiveStatus === 'pendente_avaliacao') {
    return '<span class="badge-pendente">⏳ Pendente</span>';
  }
  if (effectiveStatus === 'extraido_para_revisao') {
    return '<span class="badge-extraido">🔎 Extraído para revisão</span>';
  }
  return '<span class="badge-valido">✔ Válido</span>';
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
  if (filterCctItem) filterCctItem.value = '';
  if (filterItemStatus) filterItemStatus.value = '';
  if (filterItemPreenchimento) filterItemPreenchimento.value = '';
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

/**
 * Formats VR / auxílio alimentação with BRL and periodicity (AC5).
 * Supports real-data schema (unidade: 'BRL/mes', 'BRL/dia') and
 * demo-data schema (tipo: 'valor_mensal', 'valor_diario').
 */
function fmtVR(vrItem) {
  if (!vrItem) return '—';
  const v = vrItem.valor;
  if (v == null || v === '') return '—';
  const n = Number(v);
  if (isNaN(n)) return escapeHtml(String(v).slice(0, 22));
  const brl = n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  const unidade = (vrItem.unidade ?? '').toLowerCase();
  const tipo = vrItem.tipo ?? '';
  if (unidade.includes('/mes') || unidade.includes('/mês') || tipo === 'valor_mensal') {
    return `${brl}/mês`;
  }
  if (unidade.includes('/dia') || tipo === 'valor_diario' || tipo === 'vale_refeicao') {
    return `${brl}/dia`;
  }
  return brl;
}

/**
 * Formats jornada for table display (AC7).
 * Supports real-data schema (valor_textual: '44h/semana', unidade: 'h/semana') and
 * demo-data schema (horas_semanais, tipo: 'horas_semanais').
 */
function fmtJornada(jornadaItem) {
  if (!jornadaItem) return '—';
  // Pre-formatted textual value (real-data schema)
  const vt = jornadaItem.valor_textual;
  if (vt != null && vt !== '') return escapeHtml(String(vt).slice(0, 22));
  // Numeric value with unit
  const v = jornadaItem.valor ?? jornadaItem.horas_semanais;
  if (v != null) {
    const n = Number(v);
    if (!isNaN(n)) {
      const unidade = jornadaItem.unidade ?? '';
      if (unidade === 'h/semana' || unidade === 'horas' || jornadaItem.tipo === 'horas_semanais') {
        return `${n}h semanais`;
      }
      if (unidade === 'h/mes' || jornadaItem.tipo === 'horas_mensais') {
        return `${n}h mensais`;
      }
      return `${n}h`;
    }
  }
  if (jornadaItem.horas_mensais != null) return `${jornadaItem.horas_mensais}h mensais`;
  if (jornadaItem.opcoes_identificadas != null) {
    return escapeHtml(String(jornadaItem.opcoes_identificadas).slice(0, 22));
  }
  return '—';
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
