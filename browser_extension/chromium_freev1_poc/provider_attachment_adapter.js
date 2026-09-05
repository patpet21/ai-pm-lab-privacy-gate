(() => {
  "use strict";

  if (window.top !== window) return;
  const host = location.hostname.toLowerCase();
  if (!new Set(["chatgpt.com", "claude.ai", "gemini.google.com"]).has(host)) return;

  const state = globalThis.PrivacyGateAttachmentState;
  if (!state) return;

  const PROTECTED_FILE_RE = /(?:_protected)?_privacygate(?:_\d+)?\.(?:pdf|docx)$/i;
  const GEMINI_ATTACHMENT_ONLY_MARKER = "\u2060";
  const CONFIRM_TIMEOUT_MS = 2800;
  const RETRY_INPUT_WINDOW_MS = 1900;
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

  function filenameAppearsInProviderDom(filename) {
    const name = String(filename || "");
    if (!name) return false;
    const root = document.body || document.documentElement;
    if (!(root instanceof Element)) return false;

    const attributes = ["title", "aria-label", "data-file-name", "data-filename", "data-testid", "data-test-id"];
    for (const element of root.querySelectorAll?.("*") || []) {
      if (!(element instanceof Element) || excluded(element)) continue;
      for (const attr of attributes) {
        const value = element.getAttribute?.(attr);
        if (typeof value === "string" && value.includes(name)) return true;
      }
    }

    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node = walker.nextNode();
    while (node) {
      const parent = node.parentElement;
      if (parent && !excluded(parent) && String(node.nodeValue || "").includes(name)) return true;
      node = walker.nextNode();
    }
    return false;
  }

  async function waitForAcceptance(file, timeoutMs = CONFIRM_TIMEOUT_MS) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      if (filenameAppearsInProviderDom(file.name)) return true;
      await sleep(100);
    }
    return false;
  }

  function nativeInputs() {
    return Array.from(document.querySelectorAll('input[type="file"]')).filter(input =>
      input instanceof HTMLInputElement &&
      input.isConnected &&
      !input.id?.startsWith("privacygate-") &&
      !input.closest?.('[id^="privacygate-"]')
    );
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
    if (input && inject(input, file)) {
      if (await waitForAcceptance(file, 1100)) return true;
    }

    const trigger = attachTrigger();
    if (trigger) {
      try { trigger.click(); } catch (_error) {}
    }

    const deadline = Date.now() + RETRY_INPUT_WINDOW_MS;
    while (Date.now() < deadline) {
      await sleep(80);
      input = bestInput();
      if (!input || !inject(input, file)) continue;
      if (await waitForAcceptance(file, 1100)) return true;
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

    // Some Gemini Chromium variants leave the provider Send control disabled
    // after accepting a generated File while the editor is visually empty.
    // A word-joiner creates a real editor state without exposing or displaying
    // any user data; PrivacyGate still treats this value as semantically empty.
    if (!String(composerText(box)).includes(GEMINI_ATTACHMENT_ONLY_MARKER)) {
      setComposerText(box, GEMINI_ATTACHMENT_ONLY_MARKER);
      await sleep(120);
    }
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
    window.__privacyGateProviderAttachmentNoticeTimer = setTimeout(() => element.remove(), 5200);
  }

  async function confirmOrRecover(file) {
    if (!protectedFile(file)) return false;
    pendingFile = file;
    state.markPrepared(file.name);
    const token = ++confirmationToken;

    if (await waitForAcceptance(file)) {
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
      showAdapterNotice(`PrivacyGate — ${file.name} attached after provider retry.`, "success");
      return true;
    }

    if (token !== confirmationToken) return false;
    state.markPrepared(file.name);
    showAdapterNotice(
      `PrivacyGate — the protected file is ready, but ${host === "claude.ai" ? "Claude" : host === "gemini.google.com" ? "Gemini" : "ChatGPT"} has not confirmed the attachment. Click its Attach button once; PrivacyGate will retry the protected file only.`,
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
    const input = bestInput();
    if (input) inject(input, file);
    if (await waitForAcceptance(file, 2200)) {
      state.markAttached(file.name);
      pendingFile = null;
      await prepareAttachmentOnlyComposer();
      showAdapterNotice(`PrivacyGate — ${file.name} protected locally and attached.`, "success");
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
