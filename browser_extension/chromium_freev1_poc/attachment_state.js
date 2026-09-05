(() => {
  "use strict";

  if (window.top !== window) return;

  const host = location.hostname.toLowerCase();
  if (!new Set(["chatgpt.com", "claude.ai", "gemini.google.com"]).has(host)) return;

  const ROOT = document.documentElement;
  const STATE_ATTR = "data-privacygate-protected-attachment";
  const NAME_ATTR = "data-privacygate-protected-attachment-name";
  const EXPIRES_ATTR = "data-privacygate-protected-attachment-expires";
  const SEND_WINDOW_ATTR = "data-privacygate-attachment-send-window";
  const TTL_MS = 15 * 60 * 1000;
  const SEND_WINDOW_MS = 2500;
  const PROTECTED_FILE_RE = /_privacygate(?:_\d+)?\.(?:pdf|docx)$/i;

  function protectedName(value) {
    const name = String(value || "").trim();
    return PROTECTED_FILE_RE.test(name) ? name : "";
  }

  function clear() {
    ROOT.removeAttribute(STATE_ATTR);
    ROOT.removeAttribute(NAME_ATTR);
    ROOT.removeAttribute(EXPIRES_ATTR);
    ROOT.removeAttribute(SEND_WINDOW_ATTR);
  }

  function markAttached(filename) {
    const name = protectedName(filename);
    if (!name) return false;
    ROOT.setAttribute(STATE_ATTR, "attached");
    ROOT.setAttribute(NAME_ATTR, name);
    ROOT.setAttribute(EXPIRES_ATTR, String(Date.now() + TTL_MS));
    return true;
  }

  function alive() {
    if (ROOT.getAttribute(STATE_ATTR) !== "attached") return false;
    const expires = Number(ROOT.getAttribute(EXPIRES_ATTR) || 0);
    if (!Number.isFinite(expires) || expires <= Date.now()) {
      clear();
      return false;
    }
    return true;
  }

  function beginSendWindow() {
    if (!alive()) return false;
    const until = Date.now() + SEND_WINDOW_MS;
    ROOT.setAttribute(SEND_WINDOW_ATTR, String(until));
    setTimeout(() => {
      const current = Number(ROOT.getAttribute(SEND_WINDOW_ATTR) || 0);
      if (current === until) clear();
    }, SEND_WINDOW_MS + 700);
    return true;
  }

  function inSendWindow() {
    if (!alive()) return false;
    return Number(ROOT.getAttribute(SEND_WINDOW_ATTR) || 0) > Date.now();
  }

  function allowAttachmentOnlySend(text) {
    if (String(text || "").trim()) return false;
    if (!alive()) return false;
    if (!inSendWindow()) beginSendWindow();
    return true;
  }

  function filesFromEvent(event) {
    if (event?.target instanceof HTMLInputElement && event.target.type === "file") {
      return Array.from(event.target.files || []);
    }
    return Array.from(event?.dataTransfer?.files || event?.clipboardData?.files || []);
  }

  function observeProtectedFile(event) {
    for (const file of filesFromEvent(event)) {
      if (markAttached(file?.name)) return;
    }
  }

  for (const type of ["input", "change", "drop", "paste"]) {
    document.addEventListener(type, observeProtectedFile, true);
  }

  globalThis.PrivacyGateAttachmentState = Object.freeze({
    markAttached,
    clear,
    hasProtectedAttachment: alive,
    allowAttachmentOnlySend,
    inSendWindow,
    protectedFilename: () => alive() ? String(ROOT.getAttribute(NAME_ATTR) || "") : ""
  });
})();
