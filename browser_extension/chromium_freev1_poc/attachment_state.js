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
  const SENT_AT_ATTR = "data-privacygate-protected-attachment-sent-at";
  const TTL_MS = 15 * 60 * 1000;
  const SEND_WINDOW_MS = 3200;
  const PROTECTED_FILE_RE = /(?:_protected)?_privacygate(?:_\d+)?\.(?:pdf|docx)$/i;
  const INVISIBLE_SEND_MARKER_RE = /[\u200B-\u200D\u2060\uFEFF]/g;

  function protectedName(value) {
    const name = String(value || "").trim();
    return PROTECTED_FILE_RE.test(name) ? name : "";
  }

  function semanticText(value) {
    return String(value || "").replace(INVISIBLE_SEND_MARKER_RE, "").trim();
  }

  function clearAttachment({ keepSentAt = true } = {}) {
    ROOT.removeAttribute(STATE_ATTR);
    ROOT.removeAttribute(NAME_ATTR);
    ROOT.removeAttribute(EXPIRES_ATTR);
    ROOT.removeAttribute(SEND_WINDOW_ATTR);
    if (!keepSentAt) ROOT.removeAttribute(SENT_AT_ATTR);
  }

  function setState(state, filename) {
    const name = protectedName(filename);
    if (!name) return false;
    ROOT.setAttribute(STATE_ATTR, state);
    ROOT.setAttribute(NAME_ATTR, name);
    ROOT.setAttribute(EXPIRES_ATTR, String(Date.now() + TTL_MS));
    return true;
  }

  function markPrepared(filename) {
    return setState("prepared", filename);
  }

  function markAttached(filename) {
    return setState("attached", filename);
  }

  function alive(requiredState = null) {
    const state = ROOT.getAttribute(STATE_ATTR);
    if (!state) return false;
    if (requiredState && state !== requiredState) return false;
    const expires = Number(ROOT.getAttribute(EXPIRES_ATTR) || 0);
    if (!Number.isFinite(expires) || expires <= Date.now()) {
      clearAttachment();
      return false;
    }
    return true;
  }

  function hasPreparedAttachment() {
    return alive("prepared") || alive("attached");
  }

  function hasProtectedAttachment() {
    return alive("attached");
  }

  function beginSendWindow() {
    if (!hasProtectedAttachment()) return false;
    const until = Date.now() + SEND_WINDOW_MS;
    ROOT.setAttribute(SEND_WINDOW_ATTR, String(until));
    setTimeout(() => {
      const current = Number(ROOT.getAttribute(SEND_WINDOW_ATTR) || 0);
      if (current === until) clearAttachment();
    }, SEND_WINDOW_MS + 900);
    return true;
  }

  function inSendWindow() {
    if (!hasProtectedAttachment()) return false;
    return Number(ROOT.getAttribute(SEND_WINDOW_ATTR) || 0) > Date.now();
  }

  function allowAttachmentOnlySend(text) {
    if (semanticText(text)) return false;
    if (!hasProtectedAttachment()) return false;
    if (!inSendWindow()) beginSendWindow();
    return true;
  }

  function markSent() {
    if (!hasPreparedAttachment()) return false;
    ROOT.setAttribute(SENT_AT_ATTR, String(Date.now()));
    return true;
  }

  function wasRecentlySent(maxAgeMs = 120000) {
    const sentAt = Number(ROOT.getAttribute(SENT_AT_ATTR) || 0);
    return Number.isFinite(sentAt) && sentAt > 0 && Date.now() - sentAt <= Math.max(1000, Number(maxAgeMs) || 120000);
  }

  globalThis.PrivacyGateAttachmentState = Object.freeze({
    markPrepared,
    markAttached,
    markSent,
    clear: clearAttachment,
    hasPreparedAttachment,
    hasProtectedAttachment,
    allowAttachmentOnlySend,
    inSendWindow,
    wasRecentlySent,
    semanticText,
    protectedFilename: () => hasPreparedAttachment() ? String(ROOT.getAttribute(NAME_ATTR) || "") : ""
  });
})();
