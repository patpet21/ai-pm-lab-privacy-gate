const input = document.querySelector('#input');
const output = document.querySelector('#output');
const count = document.querySelector('#count');
const chips = document.querySelector('#chips');
const copy = document.querySelector('#copy');

const rules = [
  ['US_SSN', /\b\d{3}-\d{2}-\d{4}\b/g],
  ['EMAIL_ADDRESS', /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi],
  ['PHONE_NUMBER', /(?<!\d)(?:\+?1[-.\s]?)?(?:\(\d{3}\)|\d{3})[-.\s]\d{3}[-.\s]\d{4}(?!\d)/g],
  ['CREDIT_CARD', /\b(?:\d[ -]*?){13,16}\b/g],
  ['IP_ADDRESS', /\b(?:\d{1,3}\.){3}\d{1,3}\b/g],
  ['US_ZIP_CODE', /\b\d{5}(?:-\d{4})?\b/g]
];

function protectText(text) {
  const matches = [];
  rules.forEach(([type, regex]) => {
    for (const match of text.matchAll(regex)) matches.push({type, value: match[0], start: match.index, end: match.index + match[0].length});
  });
  matches.sort((a,b) => a.start-b.start || b.end-a.end);
  const accepted = matches.filter((item, index, all) => !all.some((other, j) => j < index && item.start < other.end));
  const counters = {};
  const tokens = new Map();
  let protectedText = text;
  [...accepted].sort((a,b) => b.start-a.start).forEach(item => {
    const key = `${item.type}:${item.value}`;
    if (!tokens.has(key)) {
      counters[item.type] = (counters[item.type] || 0) + 1;
      tokens.set(key, `[[PG_${item.type}_${String(counters[item.type]).padStart(3,'0')}]]`);
    }
    protectedText = protectedText.slice(0,item.start) + tokens.get(key) + protectedText.slice(item.end);
  });
  return {protectedText, findings: accepted};
}

document.querySelector('#sample').addEventListener('click', () => {
  input.value = `Tenant: Michael Johnson\nEmail: michael.johnson@example.com\nPhone: (212) 555-0184\nSSN: 123-45-6789\nProperty ZIP: 10001\nAccess device: 192.168.10.25`;
});

document.querySelector('#protect').addEventListener('click', () => {
  const result = protectText(input.value);
  output.value = result.protectedText;
  count.textContent = result.findings.length;
  const totals = result.findings.reduce((all, finding) => ({...all, [finding.type]:(all[finding.type]||0)+1}), {});
  chips.replaceChildren(...Object.entries(totals).map(([type,total]) => {
    const chip = document.createElement('span'); chip.textContent = `${type} ${total}`; return chip;
  }));
  if (!result.findings.length) { const chip=document.createElement('span'); chip.textContent='No structured identifiers detected'; chips.append(chip); }
  copy.disabled = !output.value;
});

copy.addEventListener('click', async () => {
  await navigator.clipboard.writeText(output.value);
  const old = copy.textContent; copy.textContent = 'Copied'; setTimeout(() => copy.textContent = old, 1200);
});
