(() => {
  "use strict";

  if (window.top !== window) return;

  const host = location.hostname.toLowerCase();
  if (!new Set(["chatgpt.com", "claude.ai", "gemini.google.com"]).has(host)) return;

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

  function isAttachmentOnlySendAttempt(event) {
    const box = composer();
    if (!box || composerText(box).trim()) return false;

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

  Event.prototype.preventDefault = function privacyGateAttachmentOnlyPreventDefault() {
    if (isAttachmentOnlySendAttempt(this)) return;
    return originalPreventDefault.call(this);
  };

  Event.prototype.stopPropagation = function privacyGateAttachmentOnlyStopPropagation() {
    if (isAttachmentOnlySendAttempt(this)) return;
    return originalStopPropagation.call(this);
  };

  Event.prototype.stopImmediatePropagation = function privacyGateAttachmentOnlyStopImmediatePropagation() {
    if (isAttachmentOnlySendAttempt(this)) return;
    return originalStopImmediatePropagation.call(this);
  };
})();
