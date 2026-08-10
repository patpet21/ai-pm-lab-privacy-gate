const input = document.querySelector('#input');
const output = document.querySelector('#output');
const count = document.querySelector('#count');
const chips = document.querySelector('#chips');
const copy = document.querySelector('#copy');

// The browser demo intentionally uses deterministic, local rules. The desktop
// app performs the fuller Presidio analysis, but both surfaces cover the
// critical government, financial and real-estate identifiers below.
const rules = [
  {type:'PERSON', regex:/\b(?:tenant|owner|buyer|seller|realtor|broker|contractor|vendor|applicant|client|contact)(?:\s+name)?\s*[:#-]\s*([A-Z][A-Za-z'-]+(?:\s+[A-Z](?:\.|[A-Za-z'-]+)){1,3})/g, group:1, priority:100},
  {type:'US_SSN', regex:/\b\d{3}-\d{2}-\d{4}\b/g, priority:95},
  {type:'US_DRIVER_LICENSE', regex:/\b(?:driver(?:'s|s)?\s+licen[cs]e|driver\s+licen[cs]e|DL)\s*(?::|#|number|no\.?)?\s*([A-Z0-9][A-Z0-9 -]{5,17}[A-Z0-9])\b/gi, group:1, priority:100},
  {type:'US_PASSPORT', regex:/\bpassport(?:\s+(?:number|no\.?))?\s*(?::|#)?\s*([A-Z0-9]{6,12})\b/gi, group:1, priority:100},
  {type:'US_ROUTING_NUMBER', regex:/\b(?:(?:ABA\s+)?routing(?:\s+number)?)\s*(?::|#)?\s*(\d{9})\b/gi, group:1, priority:100},
  {type:'US_BANK_NUMBER', regex:/\b(?:bank|checking|savings)\s+account(?:\s+(?:number|no\.?))?\s*(?::|#)?\s*(\d{6,17})\b/gi, group:1, priority:100},
  {type:'TENANT_ID', regex:/\btenant\s+(?:ID|identifier)\s*(?::|#)?\s*([A-Z0-9][A-Z0-9-]{3,30})\b/gi, group:1, priority:100},
  {type:'LEASE_ID', regex:/\blease\s+(?:ID|identifier|number|no\.?)\s*(?::|#)?\s*([A-Z0-9][A-Z0-9-]{3,30})\b/gi, group:1, priority:100},
  {type:'NYC_BBL', regex:/\b(?:NYC\s+)?BBL\s*(?::|#)?\s*([1-5]-?\d{5}-?\d{4})\b/gi, group:1, priority:100},
  {type:'NYC_BIN', regex:/\b(?:NYC\s+)?BIN\s*(?::|#)?\s*(\d{7})\b/gi, group:1, priority:100},
  {type:'VENDOR_ACCOUNT_ID', regex:/\bvendor\s+(?:account\s+)?(?:ID|identifier|number|no\.?)\s*(?::|#)?\s*([A-Z0-9][A-Z0-9-]{3,30})\b/gi, group:1, priority:100},
  {type:'WORK_ORDER_ID', regex:/\bwork\s+order(?:\s+(?:ID|number|no\.?))?\s*(?::|#)?\s*([A-Z0-9][A-Z0-9-]{3,30})\b/gi, group:1, priority:100},
  {type:'PROPOSAL_ID', regex:/\bproposal(?:\s+(?:ID|number|no\.?))?\s*(?::|#)?\s*([A-Z0-9][A-Z0-9-]{3,30})\b/gi, group:1, priority:100},
  {type:'INSURANCE_POLICY_ID', regex:/\b(?:insurance\s+)?policy(?:\s+(?:ID|number|no\.?))?\s*(?::|#)?\s*([A-Z0-9][A-Z0-9-]{3,30})\b/gi, group:1, priority:100},
  {type:'PREAPPROVAL_ID', regex:/\bpre-?approval(?:\s+(?:ID|reference|number|no\.?))?\s*(?::|#)?\s*([A-Z0-9][A-Z0-9-]{3,30})\b/gi, group:1, priority:100},
  {type:'MORTGAGE_REFERENCE', regex:/\bmortgage(?:\s+(?:ID|reference|number|no\.?))?\s*(?::|#)?\s*([A-Z0-9][A-Z0-9-]{3,30})\b/gi, group:1, priority:100},
  {type:'TENANT_ID', regex:/\bTEN-[A-Z0-9-]{4,30}\b/g, priority:95},
  {type:'LEASE_ID', regex:/\bLEASE-[A-Z0-9-]{4,30}\b/g, priority:95},
  {type:'VENDOR_ACCOUNT_ID', regex:/\bVND-[A-Z0-9-]{4,30}\b/g, priority:95},
  {type:'WORK_ORDER_ID', regex:/\bWO-[A-Z0-9-]{4,30}\b/g, priority:95},
  {type:'PROPOSAL_ID', regex:/\bPROP-[A-Z0-9-]{4,30}\b/g, priority:95},
  {type:'INSURANCE_POLICY_ID', regex:/\bCGL-[A-Z0-9-]{4,30}\b/g, priority:95},
  {type:'PREAPPROVAL_ID', regex:/\bPA-[A-Z0-9-]{4,30}\b/g, priority:95},
  {type:'MORTGAGE_REFERENCE', regex:/\bMTG-[A-Z0-9-]{4,30}\b/g, priority:95},
  {type:'NYC_BBL', regex:/\b[1-5]-\d{5}-\d{4}\b/g, priority:95},
  {type:'EMAIL_ADDRESS', regex:/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi, priority:90},
  {type:'PHONE_NUMBER', regex:/(?<!\d)(?:\+?1[\s.()-]*)?(?:\(\s*\d{3}\s*\)|\d{3})[\s.()-]+\d{3}[\s.-]+\d{4}(?!\d)/g, priority:90},
  {type:'CREDIT_CARD', regex:/\b(?:\d[ -]*?){13,16}\b/g, priority:80},
  {type:'IP_ADDRESS', regex:/\b(?:\d{1,3}\.){3}\d{1,3}\b/g, priority:90},
  {type:'US_ZIP_CODE', regex:/\b\d{5}(?:-\d{4})?\b/g, priority:50},
  {type:'PERSON', regex:/\b[A-Z][a-z'-]{1,24}(?:\s+[A-Z]\.)?\s+[A-Z][a-z'-]{1,24}\b/g, priority:40}
];

function protectText(text) {
  const matches = [];
  rules.forEach(rule => {
    for (const match of text.matchAll(rule.regex)) {
      const value = rule.group ? match[rule.group] : match[0];
      const offset = rule.group ? match[0].lastIndexOf(value) : 0;
      const start = match.index + offset;
      matches.push({type:rule.type, value, start, end:start + value.length, priority:rule.priority || 0});
    }
  });
  matches.sort((a,b) => b.priority-a.priority || a.start-b.start || (b.end-b.start)-(a.end-a.start));
  const accepted = [];
  matches.forEach(item => {
    if (!accepted.some(other => item.start < other.end && other.start < item.end)) accepted.push(item);
  });
  accepted.sort((a,b) => a.start-b.start || b.end-a.end);
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

function renderProtectedText(text) {
  output.replaceChildren();
  output.classList.toggle('is-empty', !text);
  output.dataset.raw = text;
  if (!text) {
    output.textContent = 'Protected text will appear here.';
    return;
  }
  const tokenPattern = /\[\[PG_([A-Z0-9_]+)_\d{3}\]\]/g;
  let cursor = 0;
  for (const match of text.matchAll(tokenPattern)) {
    output.append(document.createTextNode(text.slice(cursor, match.index)));
    const token = document.createElement('span');
    token.className = `pii-token token-${match[1].toLowerCase()}`;
    token.textContent = match[0];
    token.title = match[1].replaceAll('_', ' ');
    output.append(token);
    cursor = match.index + match[0].length;
  }
  output.append(document.createTextNode(text.slice(cursor)));
}

document.querySelector('#sample').addEventListener('click', () => {
  input.value = `Tenant: Michael Johnson\nEmail: michael.johnson@example.com\nPhone: (212) 555-0184\nSSN: 123-45-6789\nProperty ZIP: 10001\nAccess device: 192.168.10.25`;
});

document.querySelector('#protect').addEventListener('click', () => {
  const result = protectText(input.value);
  renderProtectedText(result.protectedText);
  count.textContent = result.findings.length;
  const totals = result.findings.reduce((all, finding) => ({...all, [finding.type]:(all[finding.type]||0)+1}), {});
  chips.replaceChildren(...Object.entries(totals).map(([type,total]) => {
    const chip = document.createElement('span'); chip.textContent = `${type} ${total}`; return chip;
  }));
  if (!result.findings.length) { const chip=document.createElement('span'); chip.textContent='No structured identifiers detected'; chips.append(chip); }
  copy.disabled = !result.protectedText;
});

copy.addEventListener('click', async () => {
  await navigator.clipboard.writeText(output.dataset.raw || '');
  const old = copy.textContent; copy.textContent = 'Copied'; setTimeout(() => copy.textContent = old, 1200);
});

const contactForm = document.querySelector('#contact-form');
const formStatus = document.querySelector('#form-status');

contactForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const submitButton = contactForm.querySelector('button[type="submit"]');
  submitButton.disabled = true;
  submitButton.textContent = 'Sending...';
  formStatus.textContent = '';
  formStatus.className = 'form-status';

  try {
    const response = await fetch(contactForm.action, {
      method: 'POST',
      body: new FormData(contactForm),
      headers: {Accept: 'application/json'}
    });
    if (!response.ok) throw new Error('Form submission failed');
    contactForm.reset();
    formStatus.textContent = 'Thank you. Your message has been sent.';
    formStatus.classList.add('success');
  } catch (error) {
    formStatus.textContent = 'The message could not be sent. Please email peter@propertydex.xyz.';
    formStatus.classList.add('error');
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = 'Send message';
  }
});
