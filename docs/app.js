import { createClient } from 'https://esm.sh/genlayer-js@1.1.8';
import {
  localnet,
  studionet,
  testnetAsimov,
  testnetBradbury,
} from 'https://esm.sh/genlayer-js@1.1.8/chains';

const NETWORKS = { localnet, studionet, testnetAsimov, testnetBradbury };
const STORE = { address: 'overrule.contract', network: 'overrule.network' };

const DEFAULT_RULES = [
  {
    id: 'H1',
    title: 'No targeted harassment',
    text: 'Do not post content that demeans, threatens, or dehumanizes a specific person or group.',
  },
  {
    id: 'H2',
    title: 'No doxxing',
    text: 'Do not publish another person\u2019s private information such as home address, phone number, or government identifiers.',
  },
  {
    id: 'S1',
    title: 'No bulk spam',
    text: 'Do not post repetitive promotional content or unsolicited advertising at scale.',
  },
];

const el = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = String(text);
  return node;
};

const $ = (id) => document.getElementById(id);

let networkKey = localStorage.getItem(STORE.network) || 'studionet';
let contractAddress = localStorage.getItem(STORE.address) || '';
let account = null;
let client = createClient({ chain: NETWORKS[networkKey] });

// ------------------------------------------------------------------ reporting

function log(message, kind) {
  const node = $('log');
  node.hidden = false;
  node.className = 'log' + (kind ? ' ' + kind : '');
  node.textContent = message;
}

function setOut(node, text, kind) {
  node.textContent = text;
  node.className = 'out' + (kind ? ' ' + kind : '');
}

function report(node, text, kind) {
  if (node) setOut(node, text, kind);
  else log(text, kind);
}

function errorText(error) {
  if (!error) return 'Unknown error';
  return error.shortMessage || error.message || String(error);
}

function fail(node, error) {
  const message = errorText(error);
  report(node, message, 'error');
  if (node) log(message, 'error');
}

// --------------------------------------------------------------------- render

function kv(rows) {
  const list = el('dl', 'kv');
  for (const [key, value] of rows) {
    list.append(el('dt', null, key));
    list.append(el('dd', null, value === undefined || value === null ? '\u2014' : value));
  }
  return list;
}

function badge(status) {
  return el('span', 'badge ' + status, status);
}

function renderDecision(container, record) {
  container.replaceChildren();
  container.append(badge(record.outcome ? record.outcome.result : record.status));
  container.append(
    kv([
      ['Decision id', record.id],
      ['Rulebook', record.rulebook_name + ' (#' + record.rulebook_id + ')'],
      ['Rulebook digest', record.rulebook_digest],
      ['Platform', record.platform],
      ['Subject', record.subject],
      ['Case reference', record.case_ref],
      ['Action', record.action],
      ['Content URL', record.content_url],
      ['Cited rules', record.cited_rule_ids.join(', ')],
      ['Stated reason', record.platform_reason],
    ]),
  );

  if (record.appeal) {
    container.append(el('h2', null, 'Appeal'));
    container.append(
      kv([
        ['Appellant', record.appeal.appellant],
        ['Argument', record.appeal.argument],
        [
          'Evidence',
          record.appeal.evidence_urls.length ? record.appeal.evidence_urls.join('\n') : '(none)',
        ],
      ]),
    );
  }

  if (record.outcome) {
    container.append(el('h2', null, 'Outcome'));
    container.append(
      kv([
        ['Result', record.outcome.result],
        ['Content available', record.outcome.content_available ? 'yes' : 'no'],
        ['Confidence', record.outcome.confidence],
        ['Reasoning', record.outcome.reasoning],
      ]),
    );
    const rows = el('div');
    for (const item of record.outcome.rule_verdicts) {
      const row = el('div', 'rule-row');
      row.append(el('span', 'rid', item.id));
      row.append(el('span', 'v-' + item.verdict, item.verdict));
      row.append(el('span', null, item.reason));
      rows.append(row);
    }
    container.append(rows);
  }
}

function renderStats(container, stats) {
  container.replaceChildren();
  const total = stats.adjudicated;
  container.append(
    kv([
      ['Decisions issued', stats.issued],
      ['Appeals adjudicated', total],
      ['Upheld', stats.upheld],
      ['Overturned', stats.overturned],
      ['Remanded', stats.remanded],
      ['Overturn rate', total ? Math.round((stats.overturned / total) * 100) + '%' : '\u2014'],
    ]),
  );
  if (!total) return;

  const parts = [
    ['upheld', stats.upheld, 'var(--ok)'],
    ['overturned', stats.overturned, 'var(--bad)'],
    ['remanded', stats.remanded, 'var(--warn)'],
  ];

  const meter = el('div', 'meter');
  const bar = el('div', 'bar');
  for (const [name, count, color] of parts) {
    const seg = el('i');
    seg.style.width = (count / total) * 100 + '%';
    seg.style.background = color;
    seg.title = name + ': ' + count;
    bar.append(seg);
  }
  meter.append(bar);

  const legend = el('div', 'legend');
  for (const [name, count, color] of parts) {
    const item = el('span');
    const swatch = el('span', 'swatch');
    swatch.style.background = color;
    item.append(swatch, document.createTextNode(name + ' ' + count));
    legend.append(item);
  }
  meter.append(legend);
  container.append(meter);
}

// ------------------------------------------------------------------ chain i/o

function requireContract(node) {
  if (!contractAddress) {
    report(node, 'Set the Overrule contract address first.', 'error');
    return false;
  }
  return true;
}

async function read(functionName, args = []) {
  return client.readContract({ address: contractAddress, functionName, args });
}

async function send(functionName, args, node, ok) {
  if (!account) {
    report(node, 'Connect a wallet first.', 'error');
    return null;
  }
  if (!requireContract(node)) return null;

  try {
    report(node, 'Sending transaction\u2026');
    const hash = await client.writeContract({
      address: contractAddress,
      functionName,
      args,
      value: 0n,
    });

    report(node, 'Submitted ' + hash + '\nWaiting for finalization\u2026');
    const tx = await client.waitForTransactionReceipt({
      hash,
      status: 'FINALIZED',
      interval: 4000,
      retries: 150,
    });

    if (tx.txExecutionResultName !== 'FINISHED_WITH_RETURN') {
      throw new Error(
        'Transaction ' + tx.statusName + ' / ' + (tx.txExecutionResultName || 'no execution result'),
      );
    }

    report(node, typeof ok === 'function' ? ok(tx) : ok, 'ok');
    log('Confirmed ' + hash);
    return tx;
  } catch (error) {
    fail(node, error);
    return null;
  }
}

const toU256 = (value) => {
  const trimmed = String(value).trim();
  return BigInt(trimmed === '' ? '0' : trimmed);
};

// ---------------------------------------------------------------- interaction

function switchTab(name) {
  for (const tab of document.querySelectorAll('.tab')) {
    tab.classList.toggle('active', tab.dataset.tab === name);
  }
  for (const panel of document.querySelectorAll('.panel')) {
    panel.hidden = panel.id !== 'panel-' + name;
  }
}

function setWalletState() {
  const node = $('walletState');
  node.textContent = account ? 'wallet: ' + account.slice(0, 6) + '\u2026' + account.slice(-4) : 'wallet: not connected';
  node.classList.toggle('on', Boolean(account));
}

function setContractState() {
  const node = $('contractState');
  node.textContent = contractAddress
    ? contractAddress.slice(0, 6) + '\u2026' + contractAddress.slice(-4)
    : 'not set';
  node.classList.toggle('on', Boolean(contractAddress));
}

async function connectWallet() {
  try {
    if (!window.ethereum) {
      throw new Error('No browser wallet found (window.ethereum is undefined).');
    }
    const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
    account = accounts[0];
    client = createClient({ chain: NETWORKS[networkKey], account, provider: window.ethereum });
    await client.connect(networkKey);
    setWalletState();
    log('Connected ' + account + ' on ' + networkKey);
  } catch (error) {
    fail(null, error);
  }
}

function applyNetwork(key) {
  networkKey = key;
  localStorage.setItem(STORE.network, key);
  client = account
    ? createClient({ chain: NETWORKS[key], account, provider: window.ethereum })
    : createClient({ chain: NETWORKS[key] });
  if (account) {
    client.connect(key).catch((error) => fail(null, error));
  }
  log('Network: ' + key);
}

async function refreshTotals() {
  try {
    const [rulebooks, decisions] = await Promise.all([
      read('total_rulebooks'),
      read('total_decisions'),
    ]);
    const counts = { rulebooks: Number(rulebooks), decisions: Number(decisions) };
    $('dRulebook').value = counts.rulebooks > 0 ? String(counts.rulebooks - 1) : '0';
    return counts;
  } catch (error) {
    return null;
  }
}

async function loadDecisionInto(container, id) {
  const raw = await read('get_decision', [toU256(id)]);
  const record = JSON.parse(raw);
  renderDecision(container, record);
  return record;
}

// ----------------------------------------------------------------------- init

function init() {
  const select = $('network');
  for (const key of Object.keys(NETWORKS)) {
    const option = el('option', null, key);
    option.value = key;
    select.append(option);
  }
  select.value = networkKey;
  select.onchange = () => applyNetwork(select.value);

  $('contract').value = contractAddress;
  setContractState();
  setWalletState();

  $('saveContract').onclick = () => {
    contractAddress = $('contract').value.trim();
    localStorage.setItem(STORE.address, contractAddress);
    setContractState();
    log(contractAddress ? 'Contract address saved.' : 'Contract address cleared.');
    if (contractAddress) refreshTotals();
  };

  $('connect').onclick = connectWallet;

  for (const tab of document.querySelectorAll('.tab')) {
    tab.onclick = () => switchTab(tab.dataset.tab);
  }

  $('rbRules').value = JSON.stringify(DEFAULT_RULES, null, 2);
  $('dUrl').placeholder = 'https://example.com/post/12345';

  $('publishRulebook').onclick = async () => {
    const tx = await send(
      'publish_rulebook',
      [$('rbName').value.trim(), $('rbRules').value.trim()],
      $('rbOut'),
      'Rulebook published. It is frozen on-chain.',
    );
    if (tx) {
      const totals = await refreshTotals();
      if (totals) setOut($('rbOut'), 'Rulebook #' + (totals.rulebooks - 1) + ' published and frozen on-chain.', 'ok');
    }
  };

  $('issueDecision').onclick = async () => {
    const cited = $('dRules')
      .value.split(',')
      .map((part) => part.trim())
      .filter(Boolean);
    await send(
      'issue_decision',
      [
        toU256($('dRulebook').value),
        $('dSubject').value.trim(),
        $('dCaseRef').value.trim(),
        $('dUrl').value.trim(),
        JSON.stringify(cited),
        $('dAction').value,
        $('dReason').value.trim(),
      ],
      $('dOut'),
      'Decision issued. The subject can now appeal once.',
    );
  };

  $('loadDecision').onclick = async () => {
    try {
      await loadDecisionInto($('aView'), $('aId').value);
    } catch (error) {
      fail($('aOut'), error);
    }
  };

  $('appeal').onclick = async () => {
    const evidence = $('aEvidence')
      .value.split('\n')
      .map((line) => line.trim())
      .filter(Boolean);
    await send(
      'appeal',
      [toU256($('aId').value), $('aArgument').value.trim(), JSON.stringify(evidence)],
      $('aOut'),
      'Appeal recorded on-chain. Anyone can now trigger adjudication.',
    );
  };

  $('loadAppealed').onclick = async () => {
    try {
      await loadDecisionInto($('jView'), $('jId').value);
    } catch (error) {
      fail(null, error);
    }
  };

  $('adjudicate').onclick = async () => {
    const id = toU256($('jId').value);
    const tx = await send('adjudicate', [id], null, 'Adjudication finalized.');
    if (!tx) return;
    try {
      const record = await loadDecisionInto($('jView'), id);
      log('Decision #' + record.id + ' adjudicated: ' + record.outcome.result);
    } catch (error) {
      fail(null, error);
    }
  };

  $('loadStats').onclick = async () => {
    if (!requireContract(null)) return;
    try {
      const raw = await read('get_platform_stats', [$('tAddress').value.trim()]);
      renderStats($('tView'), JSON.parse(raw));
    } catch (error) {
      fail(null, error);
    }
  };

  if (contractAddress) refreshTotals();
}

init();
