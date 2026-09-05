(() => {
  "use strict";

  if (window.top !== window) return;

  const host = location.hostname.toLowerCase();
  if (!new Set(["chatgpt.com", "claude.ai", "gemini.google.com"]).has(host)) return;

  const PROTECTED_FILE_RE = /(?:_protected)?_privacygate(?:_\d+)?\.(?:pdf|docx)$/i;

  function composer() {
    if (host === "chatgpt.com") {
      return (
        document.querySelector("#prompt-textarea") ||
        document.querySelector('[contenteditable="true"]')
      );
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
    if (box instanceof HTMLTextAreaElement || box instanceof HTMLInputElement) {
      return box.value || "";
    }
    return box.innerText || box.textContent || "";
  }

  function sendScope(box) {
    if (!box) return null;
    return (
      box.closest("form") ||
      box.closest("fieldset") ||
      box.closest("rich-textarea")?.parentElement?.parentElement ||
      box.parentElement?.parentElement ||
      box.parentElement
    );
  }

  function isProtectedFileName(value) {
    return PROTECTED_FILE_RE.test(String(value || "").trim());
  }

  function hasProtectedAttachment(box) {
    const scope = sendScope(box) || document;

    for (const input of Array.from(scope.querySelectorAll?.('input[type="file"]') || [])) {
      if (!(input instanceof HTMLInputElement)) continue;
      for (const file of Array.from(input.files || [])) {
        if (isProtectedFileName(file?.name)) return true;
      }
    }

    const candidates = Array.from(
      scope.querySelectorAll?.('[title], [aria-label], [data-testid*="file" i], [data-test-id*="file" i]') || []
    );
    for (const element of candidates) {
      if (!(element instanceof Element)) continue;
      const values = [
        element.getAttribute("title"),
        element.getAttribute("aria-label"),
        element.textContent
      ];
      if (values.some(value => {
        const text = String(value || "");
        return text.split(/\s+/).some(part => isProtectedFileName(part.replace(/[),;]+$/g, "")));
      })) return true;
    }

    const scopeText = String(scope.innerText || scope.textContent || "");
    return /(?:_protected)?_privacygate(?:_\d+)?\.(?:pdf|docx)\b/i.test(scopeText);
  }

  function isSendButton(target, box) {
    if (!(target instanceof Element) || !box) return false;
    const button = target.closest('button, [role="button"]');
    if (!(button instanceof Element)) return false;

    const scope = sendScope(box);
    if (scope instanceof Element && !scope.contains(button)) return false;

    if (host === "chatgpt.com") {
      return Boolean(button.matches(
        'button[data-testid="send-button"], button[aria-label*="send" i], button[aria-label*="submit" i]'
      ));
    }

    return Boolean(button.matches(
      'button[data-testid*="send" i], button[data-test-id*="send" i], ' +
      'button[aria-label*="send" i], button[aria-label*="submit" i], ' +
      'button[class*="send" i], button[type="submit"], ' +
      '[role="button"][aria-label*="send" i]'
    ));
  }

  function isProtectedAttachmentOnlySendAttempt(event) {
    const box = composer();
    if (!box || composerText(box).trim() || !hasProtectedAttachment(box)) return false;

    if (event.type === "keydown") {
      return (
        event.key === "Enter" &&
        !event.shiftKey &&
        !event.ctrlKey &&
        !event.altKey &&
        !event.metaKey &&
        (event.target === box || box.contains?.(event.target))
      );
    }

    if (event.type === "submit") {
      return Boolean(
        event.target instanceof HTMLFormElement &&
        event.target.contains(box)
      );
    }

    if (event.type === "click") {
      return isSendButton(event.target, box);
    }

    return false;
  }

  const originalPreventDefault = Event.prototype.preventDefault;
  const originalStopPropagation = Event.prototype.stopPropagation;
  const originalStopImmediatePropagation = Event.prototype.stopImmediatePropagation;

  Event.prototype.preventDefault = function privacyGateProtectedAttachmentPreventDefault() {
    if (isProtectedAttachmentOnlySendAttempt(this)) return;
    return originalPreventDefault.call(this);
  };

  Event.prototype.stopPropagation = function privacyGateProtectedAttachmentStopPropagation() {
    if (isProtectedAttachmentOnlySendAttempt(this)) return;
    return originalStopPropagation.call(this);
  };

  Event.prototype.stopImmediatePropagation = function privacyGateProtectedAttachmentStopImmediatePropagation() {
    if (isProtectedAttachmentOnlySendAttempt(this)) return;
    return originalStopImmediatePropagation.call(this);
  };
})();
