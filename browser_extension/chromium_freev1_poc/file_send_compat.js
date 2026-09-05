(() => {
  "use strict";

  if (window.top !== window) return;
  const host = location.hostname.toLowerCase();
  if (!new Set(["chatgpt.com", "claude.ai", "gemini.google.com"]).has(host)) return;

  const ALLOW = Symbol("privacygateProtectedFileOnlySend");

  function composer() {
    if (host === "chatgpt.com") {
      return document.querySelector("#prompt-textarea") || document.querySelector('[contenteditable="true"]');
    }
    if (host === "claude.ai") {
      return document.querySelector('div.ProseMirror[contenteditable="true"]') ||
        document.querySelector('[contenteditable="true"][data-placeholder]') ||
        document.querySelector('fieldset [contenteditable="true"]') ||
        document.querySelector('textarea[placeholder*="message" i]') || document.querySelector("textarea");
    }
    return document.querySelector('rich-textarea [contenteditable="true"]') ||
      document.querySelector('.ql-editor[contenteditable="true"]') ||
      document.querySelector('[contenteditable="true"][aria-label*="prompt" i]') ||
      document.querySelector('[contenteditable="true"][aria-label*="message" i]') ||
      document.querySelector('textarea[aria-label*="prompt" i]') || document.querySelector("textarea");
  }

  function text(box) {
    if (!box) return "";
    if (box instanceof HTMLTextAreaElement || box instanceof HTMLInputElement) return box.value || "";
    return box.innerText || box.textContent || "";
  }

  function sendButton() {
    const box = composer();
    if (!box) return null;
    const scope = box.closest("form") || box.closest("fieldset") || box.closest("rich-textarea")?.parentElement?.parentElement || box.parentElement?.parentElement || document;
    const selectors = [
      'button[data-testid="send-button"]', 'button[data-testid*="send" i]',
      'button[data-test-id*="send" i]', 'button[aria-label*="send" i]',
      'button[aria-label*="submit" i]', 'button[type="submit"]'
    ];
    for (const selector of selectors) {
      const item = Array.from(scope.querySelectorAll?.(selector) || []).find(node => node instanceof HTMLElement && !node.closest('[id^="privacygate-"]'));
      if (item) return item;
    }
    return null;
  }

  function isSendAttempt(event) {
    const box = composer();
    if (!box) return false;
    if (event.type === "keydown") {
      return event.key === "Enter" && !event.shiftKey && !event.ctrlKey && !event.altKey && !event.metaKey && (event.target === box || box.contains?.(event.target));
    }
    if (event.type === "submit") return event.target instanceof HTMLFormElement && event.target.contains(box);
    if (event.type === "click") {
      const target = event.target instanceof Element ? event.target.closest('button,[role="button"]') : null;
      const send = sendButton();
      return Boolean(target && send && (target === send || send.contains(target)));
    }
    return false;
  }

  function mark(event) {
    const state = globalThis.PrivacyGateFileState;
    const box = composer();
    if (!event.isTrusted || !state?.hasAttached?.() || !box || text(box).trim() || !isSendAttempt(event)) return;
    Object.defineProperty(event, ALLOW, { value: true, configurable: false });
    state.markSendAttempt?.();
  }

  for (const type of ["keydown", "submit", "click"]) document.addEventListener(type, mark, true);

  const preventDefault = Event.prototype.preventDefault;
  const stopPropagation = Event.prototype.stopPropagation;
  const stopImmediatePropagation = Event.prototype.stopImmediatePropagation;

  Event.prototype.preventDefault = function privacyGateFileSendPreventDefault() {
    if (this?.[ALLOW]) return;
    return preventDefault.call(this);
  };
  Event.prototype.stopPropagation = function privacyGateFileSendStopPropagation() {
    if (this?.[ALLOW]) return;
    return stopPropagation.call(this);
  };
  Event.prototype.stopImmediatePropagation = function privacyGateFileSendStopImmediatePropagation() {
    if (this?.[ALLOW]) return;
    return stopImmediatePropagation.call(this);
  };
})();
