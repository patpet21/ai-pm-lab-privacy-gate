(() => {
  "use strict";

  if (window.top !== window) return;
  const host = location.hostname.toLowerCase();
  if (!new Set(["chatgpt.com", "claude.ai", "gemini.google.com"]).has(host)) return;

  const state = globalThis.PrivacyGateAttachmentState;
  if (!state) return;

  const PROTECTED_FILE_RE = /(?:_protected)?_privacygate(?:_\d+)?\.(?:pdf|docx)$/i;
  const CONFIRM_TIMEOUT_MS = 3000;
  const RETRY_INPUT_WINDOW_MS = 1900;
  const GEMINI_AUTO_PROMPT = "Analyze the attached document.";
  let pendingFile = null;
  let retrying = false;
  let confirmationToken = 0;

  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  function protectedFile(value) {
    return value instanceof File && PROTECTED_FILE_RE.test(String(value.name || ""));
  }

  function composer() {
    if (host === "chatgpt.com") {
      return document.querySelector("#prompt-textarea") || document.querySelector('[contenteditable="true"]');
    }
    if (host === "claude.ai") {
      return (
        document.querySelector('div.ProseMirror[contenteditable="true"]') ||
        document.querySelector('[contenteditable="true"][data-placeholder]') ||
        document.querySelector('fieldset [contenteditable="true"]') ||
        document.querySelector('textarea[placeholder*="message" i]') ||
        document.querySelector("textarea")
      );
    }
    return (
      document.querySelector('rich-textarea [contenteditable="true"]') ||
      document.querySelector('.ql-editor[contenteditable="true"]') ||
      document.querySelector('[contenteditable="true"][aria-label*="prompt" i]') ||
      document.querySelector('[contenteditable="true"][aria-label*="message" i]') ||
      document.querySelector('textarea[aria-label*="prompt" i]') ||
      document.querySelector("textarea")
    );
  }

  function composerText(box = composer()) {
    if (!box) return "";
    if (box instanceof HTMLTextAreaElement || box instanceof HTMLInputElement) return box.value || "";
    return box.innerText || box.textContent || "";
  }

  function providerScope() {
    const box = composer();
    return (
      box?.closest("form") ||
      box?.closest("fieldset") ||
      box?.closest("rich-textarea")?.parentElement?.parentElement ||
      box?.parentElement?.parentElement ||
      document.body ||
      document.documentElement
    );
  }

  function excluded(element) {
    return Boolean(
      element?.closest?.(
        '[id^="privacygate-"], .privacygate-secure-restore-frame, .privacygate-auto-restore-frame, .privacygate-response-status'
      )
    );
  }

  function nativeInputs() {
    return Array.from(document.querySelectorAll('input[type="file"]')).filter(input =>
      input instanceof HTMLInputElement &&
      input.isConnected &&
      !input.id?.startsWith("privacygate-") &&
      !input.closest?.('[id^="privacygate-"]')
    );
  }

  function normalizeText(value) {
    return String(value || "").replace(/\s+/g, " ").trim().toLowerCase();
  }

  function filenameParts(filename) {
    const full = String(filename || "").trim();
    const lower = full.toLowerCase();
    const dot = lower.lastIndexOf(".");
    const stem = dot > 0 ? lower.slice(0, dot) : lower;
    const ext = dot > 0 ? lower.slice(dot) : "";
    const tail = stem.slice(-22);
    const head = stem.slice(0, 28);
    return { full: lower, stem, ext, head, tail };
  }

  function elementText(element) {
    if (!(element instanceof Element) || excluded(element)) return "";
    const values = [
      element.getAttribute("title"),
      element.getAttribute("aria-label"),
      element.getAttribute("data-file-name"),
      element.getAttribute("data-filename"),
      element.textContent
    ];
    return normalizeText(values.filter(Boolean).join(" "));
  }

  function likelyAttachmentElements() {
    const scope = providerScope();
    if (!(scope instanceof Element || scope instanceof Document)) return [];
    const selectors = [
      '[data-testid*="attach" i]', '[data-testid*="file" i]',
      '[data-test-id*="attach" i]', '[data-test-id*="file" i]',
      '[class*="attach" i]', '[class*="file-chip" i]', '[class*="attachment" i]',
      '[aria-label*="remove file" i]', '[aria-label*="remove attachment" i]',
      '[title$=".pdf" i]', '[title$=".docx" i]'
    ].join(",");
    return Array.from(scope.querySelectorAll?.(selectors) || []).filter(el =>
      el instanceof Element && !excluded(el)
    );
  }

  function attachmentEvidenceScore() {
    let score = 0;
    for (const input of nativeInputs()) {
      score += Array.from(input.files || []).length * 4;
    }
    score += likelyAttachmentElements().length;
    return score;
  }

  function filenameAppearsInProviderDom(filename) {
    const parts = filenameParts(filename);
    if (!parts.full) return false;

    for (const input of nativeInputs()) {
      for (const file of Array.from(input.files || [])) {
        if (normalizeText(file?.name) === parts.full) return true;
      }
    }

    const candidates = likelyAttachmentElements();
    for (const element of candidates) {
      const text = elementText(element);
      if (!text) continue;
      if (text.includes(parts.full)) return true;
      if (parts.head.length >= 16 && text.includes(parts.head)) return true;
      if (parts.tail.length >= 12 && text.includes(parts.tail)) return true;
      if (parts.ext && text.includes(parts.ext) && text.includes("privacygate")) return true;
    }
    return false;
  }

  async function waitForAcceptance(file, baselineScore = 0, timeoutMs = CONFIRM_TIMEOUT_MS) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      if (filenameAppearsInProviderDom(file.name)) return true;
      if (attachmentEvidenceScore() > baselineScore) return true;
      await sleep(100);
    }
    return false;
  }

  function bestInput() {
    const box = composer();
    const boxRect = box?.getBoundingClientRect?.();
    let best = null;
    for (const input of nativeInputs()) {
      const accept = String(input.accept || "").toLowerCase();
      let score = 0;
      if (/pdf|docx|word|officedocument/.test(accept)) score += 100;
      if (!input.multiple) score += 10;
      const rect = input.getBoundingClientRect?.();
      if (boxRect && rect) score -= Math.min(45, Math.abs((rect.left || 0) - boxRect.left) / 60);
      if (!best || score > best.score) best = { input, score };
    }
    return best?.input || null;
  }

  function inject(input, file) {
    if (!(input instanceof HTMLInputElement) || !input.isConnected || !protectedFile(file)) return false;
    const transfer = new DataTransfer();
    transfer.items.add(file);
    retrying = true;
    try {
      input.files = transfer.files;
      input.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
      input.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
      return true;
    } catch (_error) {
      return false;
    } finally {
      queueMicrotask(() => { retrying = false; });
    }
  }

  function attachTrigger() {
    const scope = providerScope();
    const selectors = [
      'button[aria-label*="attach" i]',
      'button[aria-label*="upload" i]',
      'button[aria-label*="add" i]',
      'button[data-testid*="attach" i]',
      'button[data-testid*="upload" i]',
      'button[data-test-id*="upload" i]',
      '[role="button"][aria-label*="attach" i]',
      '[role="button"][aria-label*="upload" i]',
      '[role="button"][aria-label*="add" i]'
    ];
    for (const selector of selectors) {
      const item = Array.from(scope?.querySelectorAll?.(selector) || []).find(el =>
        el instanceof HTMLElement && !excluded(el)
      );
      if (item) return item;
    }
    return null;
  }

  async function retryNativeInput(file) {
    let input = bestInput();
    let baseline = attachmentEvidenceScore();
    if (input && inject(input, file)) {
      if (await waitForAcceptance(file, baseline, 1200)) return true;
    }

    const trigger = attachTrigger();
    if (trigger) {
      try { trigger.click(); } catch (_error) {}
    }

    const deadline = Date.now() + RETRY_INPUT_WINDOW_MS;
    while (Date.now() < deadline) {
      await sleep(80);
      input = bestInput();
      if (!input) continue;
      baseline = attachmentEvidenceScore();
      if (!inject(input, file)) continue;
      if (await waitForAcceptance(file, baseline, 1200)) return true;
    }
    return false;
  }

  function setComposerText(box, value) {
    if (!box) return false;
    try {
      if (box instanceof HTMLTextAreaElement || box instanceof HTMLInputElement) {
        const proto = box instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
        const descriptor = Object.getOwnPropertyDescriptor(proto, "value");
        descriptor?.set?.call(box, value);
      } else {
        box.textContent = value;
      }
      box.dispatchEvent(new InputEvent("input", {
        bubbles: true,
        composed: true,
        inputType: "insertText",
        data: value
      }));
      return true;
    } catch (_error) {
      return false;
    }
  }

  async function prepareAttachmentOnlyComposer() {
    if (host !== "gemini.google.com" || !state.hasProtectedAttachment()) return;
    const box = composer();
    if (!box || state.semanticText(composerText(box))) return;

    // Gemini currently requires a real prompt in some Chromium builds even when
    // a document is attached. Add a visible neutral prompt so the user can still
    // use Attach -> Protect -> Send without typing anything manually.
    setComposerText(box, GEMINI_AUTO_PROMPT);
    box.setAttribute?.("data-privacygate-auto-prompt", "true");
    await sleep(140);
  }

  function showAdapterNotice(message, kind = "error") {
    if (!document.body) return;
    let element = document.getElementById("privacygate-provider-attachment-notice");
    if (!element) {
      element = document.createElement("div");
      element.id = "privacygate-provider-attachment-notice";
      Object.assign(element.style, {
        position: "fixed",
        left: "50%",
        top: "50%",
        transform: "translate(-50%,-50%)",
        zIndex: "2147483647",
        maxWidth: "min(620px,calc(100vw - 32px))",
        padding: "12px 16px",
        borderRadius: "10px",
        color: "#fff",
        textAlign: "center",
        fontFamily: "Arial,sans-serif",
        fontSize: "13px",
        fontWeight: "750",
        boxShadow: "0 8px 30px rgba(0,0,0,.30)"
      });
      document.body.appendChild(element);
    }
    element.style.background = kind === "success" ? "#065f46" : "#991b1b";
    element.textContent = message;
    clearTimeout(window.__privacyGateProviderAttachmentNoticeTimer);
    window.__privacyGateProviderAttachmentNoticeTimer = setTimeout(() => element.remove(), 4200);
  }

  async function confirmOrRecover(file) {
    if (!protectedFile(file)) return false;
    pendingFile = file;
    state.markPrepared(file.name);
    const token = ++confirmationToken;
    const baseline = attachmentEvidenceScore();

    if (await waitForAcceptance(file, baseline)) {
      if (token !== confirmationToken) return false;
      state.markAttached(file.name);
      pendingFile = null;
      await prepareAttachmentOnlyComposer();
      return true;
    }

    if (await retryNativeInput(file)) {
      if (token !== confirmationToken) return false;
      state.markAttached(file.name);
      pendingFile = null;
      await prepareAttachmentOnlyComposer();
      return true;
    }

    if (token !== confirmationToken) return false;
    state.markPrepared(file.name);
    showAdapterNotice(
      `PrivacyGate — protected file ready, but ${host === "claude.ai" ? "Claude" : host === "gemini.google.com" ? "Gemini" : "ChatGPT"} did not confirm the attachment. Use Attach once to retry the protected file.`,
      "error"
    );
    return false;
  }

  function filesFromEvent(event) {
    if (event?.target instanceof HTMLInputElement && event.target.type === "file") {
      return Array.from(event.target.files || []);
    }
    return Array.from(event?.dataTransfer?.files || event?.clipboardData?.files || []);
  }

  function observeProtectedFile(event) {
    if (retrying) return;
    const file = filesFromEvent(event).find(protectedFile);
    if (!file) return;
    confirmOrRecover(file).catch(() => {});
  }

  function isLikelyAttachGesture(target) {
    if (!(target instanceof Element)) return false;
    if (target.closest('input[type="file"]')) return true;
    const button = target.closest('button,[role="button"]');
    if (!button || excluded(button)) return false;
    const label = String(
      button.getAttribute("aria-label") ||
      button.getAttribute("data-testid") ||
      button.getAttribute("data-test-id") ||
      button.textContent ||
      ""
    ).toLowerCase();
    return /attach|upload|add file|file upload/.test(label) || label.trim() === "+";
  }

  async function retryPendingAfterUserGesture() {
    const file = pendingFile;
    if (!protectedFile(file)) return;
    await sleep(120);
    const baseline = attachmentEvidenceScore();
    const input = bestInput();
    if (input) inject(input, file);
    if (await waitForAcceptance(file, baseline, 2300)) {
      state.markAttached(file.name);
      pendingFile = null;
      await prepareAttachmentOnlyComposer();
    }
  }

  function isSendGesture(event) {
    const box = composer();
    if (!box) return false;
    if (event.type === "keydown") {
      return event.key === "Enter" && !event.shiftKey && !event.ctrlKey && !event.altKey && !event.metaKey &&
        (event.target === box || box.contains?.(event.target));
    }
    if (event.type === "submit") {
      return event.target instanceof HTMLFormElement && event.target.contains(box);
    }
    if (event.type === "click") {
      const target = event.target instanceof Element ? event.target.closest('button,[role="button"]') : null;
      if (!target) return false;
      const label = String(target.getAttribute("aria-label") || target.getAttribute("data-testid") || target.getAttribute("data-test-id") || "").toLowerCase();
      return /send|submit/.test(label) || target.matches('button[type="submit"]');
    }
    return false;
  }

  for (const type of ["input", "change", "drop", "paste"]) {
    document.addEventListener(type, observeProtectedFile, true);
  }

  document.addEventListener("click", event => {
    if (pendingFile && isLikelyAttachGesture(event.target)) {
      retryPendingAfterUserGesture().catch(() => {});
    }
  }, true);

  for (const type of ["keydown", "submit", "click"]) {
    document.addEventListener(type, event => {
      if (!event.isTrusted || !state.hasProtectedAttachment() || !isSendGesture(event)) return;
      state.markSent();
    }, true);
  }

  globalThis.PrivacyGateProviderAttachment = Object.freeze({
    confirmOrRecover,
    prepareAttachmentOnlyComposer,
    providerHasFilename: filenameAppearsInProviderDom,
    pendingProtectedFilename: () => pendingFile?.name || ""
  });
})();
