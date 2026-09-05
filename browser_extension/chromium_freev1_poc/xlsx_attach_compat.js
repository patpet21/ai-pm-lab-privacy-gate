(() => {
  "use strict";

  if (window.top !== window) return;
  const host = location.hostname.toLowerCase();
  if (!new Set(["chatgpt.com", "claude.ai", "gemini.google.com"]).has(host)) return;

  let rerouting = false;
  const recent = new Map();
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

  function isProtectedXlsx(file) {
    return file instanceof File && /_privacygate\.xlsx$/i.test(file.name || "");
  }

  function inputs() {
    return Array.from(document.querySelectorAll('input[type="file"]')).filter(input =>
      input instanceof HTMLInputElement &&
      input.isConnected &&
      !input.id?.startsWith("privacygate-") &&
      !input.closest?.('[id^="privacygate-"]')
    );
  }

  function acceptScore(input) {
    const accept = String(input.accept || "").trim().toLowerCase();
    const label = `${input.name || ""} ${input.id || ""} ${input.getAttribute("aria-label") || ""}`.toLowerCase();
    let score = 0;

    if (!accept || accept === "*/*" || accept.includes("application/*")) {
      score += 220;
    }
    if (
      accept.includes(".xlsx") ||
      accept.includes("spreadsheet") ||
      accept.includes("excel") ||
      accept.includes("officedocument.spreadsheetml")
    ) {
      score += 420;
    }
    if (/image\//.test(accept) && !/xlsx|spreadsheet|excel/.test(accept)) {
      score -= 500;
    }
    if (/file|upload|attach|document/.test(label)) score += 35;
    if (!input.multiple) score += 10;
    return score;
  }

  function bestXlsxInput(exclude = null) {
    const ranked = inputs()
      .filter(input => input !== exclude)
      .map(input => ({ input, score: acceptScore(input) }))
      .filter(item => item.score > 0)
      .sort((a, b) => b.score - a.score);
    return ranked[0]?.input || null;
  }

  function attachTrigger() {
    const selectors = host === "chatgpt.com"
      ? [
          'button[data-testid*="composer-plus" i]',
          'button[aria-label*="attach" i]',
          'button[aria-label*="add" i]',
          'button[aria-label*="upload" i]'
        ]
      : host === "claude.ai"
        ? [
            'button[aria-label*="attach" i]',
            'button[aria-label*="add" i]',
            'button[data-testid*="attach" i]',
            'button[aria-label*="upload" i]'
          ]
        : [
            'button[aria-label*="upload" i]',
            'button[aria-label*="attach" i]',
            'button[aria-label*="add" i]'
          ];
    for (const selector of selectors) {
      const found = Array.from(document.querySelectorAll(selector)).find(node =>
        node instanceof HTMLElement && !node.closest('[id^="privacygate-"]')
      );
      if (found) return found;
    }
    return null;
  }

  function inject(input, file) {
    if (!(input instanceof HTMLInputElement) || !input.isConnected) return false;
    const transfer = new DataTransfer();
    transfer.items.add(file);
    rerouting = true;
    try {
      input.files = transfer.files;
      input.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
      input.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
      return true;
    } catch (_error) {
      return false;
    } finally {
      queueMicrotask(() => { rerouting = false; });
    }
  }

  function pageShows(file) {
    const text = String(document.body?.innerText || "");
    if (text.includes(file.name)) return true;
    const stem = String(file.name || "").replace(/\.[^.]+$/, "");
    return stem.length >= 10 && text.includes(stem.slice(0, Math.min(24, stem.length)));
  }

  function notice(message, error = false) {
    let node = document.getElementById("privacygate-xlsx-compat-notice");
    if (!node) {
      node = document.createElement("div");
      node.id = "privacygate-xlsx-compat-notice";
      Object.assign(node.style, {
        position: "fixed", left: "50%", top: "42%", transform: "translate(-50%,-50%)",
        zIndex: "2147483647", maxWidth: "min(680px,calc(100vw - 32px))", padding: "11px 15px",
        borderRadius: "10px", color: "#fff", textAlign: "center", fontFamily: "Arial,sans-serif",
        fontSize: "13px", fontWeight: "750", boxShadow: "0 8px 30px rgba(0,0,0,.30)"
      });
      document.documentElement.appendChild(node);
    }
    node.style.background = error ? "#991b1b" : "#065f46";
    node.textContent = message;
    setTimeout(() => node.remove(), 4200);
  }

  async function reroute(file, sourceInput) {
    const key = `${file.name}:${file.size}`;
    const last = Number(recent.get(key) || 0);
    if (Date.now() - last < 2500) return;
    recent.set(key, Date.now());

    let target = bestXlsxInput(sourceInput);
    if (target && inject(target, file)) {
      await sleep(450);
      if (pageShows(file) || Array.from(target.files || []).some(item => item.name === file.name)) return;
    }

    const trigger = attachTrigger();
    try { trigger?.click(); } catch (_error) {}

    for (let attempt = 0; attempt < 30; attempt += 1) {
      await sleep(90);
      target = bestXlsxInput(sourceInput);
      if (!target) continue;
      if (!inject(target, file)) continue;
      await sleep(450);
      if (pageShows(file) || Array.from(target.files || []).some(item => item.name === file.name)) return;
    }

    notice("PrivacyGate — the XLSX was protected locally, but this page did not expose a spreadsheet-compatible attachment input.", true);
  }

  function intercept(event) {
    if (rerouting || event.isTrusted) return;
    const input = event.target;
    if (!(input instanceof HTMLInputElement) || input.type !== "file") return;
    const file = Array.from(input.files || []).find(isProtectedXlsx);
    if (!file) return;

    const score = acceptScore(input);
    if (score >= 200 && !(/image\//.test(String(input.accept || "").toLowerCase()) && score < 400)) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    reroute(file, input);
  }

  document.addEventListener("input", intercept, true);
  document.addEventListener("change", intercept, true);
})();
