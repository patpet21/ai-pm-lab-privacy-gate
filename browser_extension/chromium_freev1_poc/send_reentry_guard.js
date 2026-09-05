(() => {
  "use strict";

  if (window.top !== window) return;
  const host = location.hostname.toLowerCase();
  if (!new Set(["chatgpt.com", "claude.ai", "gemini.google.com"]).has(host)) return;

  const STORAGE_KEY = "privacygateProtectionEnabled";
  const LOCK_MS = 3000;
  const GESTURE_MS = 350;
  let enabled = true;
  let gestureStartedAt = 0;
  let lockedUntil = 0;
  let gestureTypes = new Set();

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
      return button.matches('button[data-testid="send-button"], button[aria-label*="send" i], button[aria-label*="submit" i]');
    }
    return button.matches(
      'button[data-testid*="send" i], button[data-test-id*="send" i], ' +
      'button[aria-label*="send" i], button[aria-label*="submit" i], ' +
      'button[class*="send" i], button[type="submit"], ' +
      '[role="button"][aria-label*="send" i]'
    );
  }

  function isSendAttempt(event) {
    const box = composer();
    if (!box) return false;
    if (event.type === "keydown") {
      return event.key === "Enter" && !event.shiftKey && !event.ctrlKey && !event.altKey && !event.metaKey &&
        (event.target === box || box.contains?.(event.target));
    }
    if (event.type === "submit") {
      return event.target instanceof HTMLFormElement && event.target.contains(box);
    }
    if (event.type === "click") return isSendButton(event.target, box);
    return false;
  }

  function privacyGateBusy() {
    return Boolean(
      document.getElementById("privacygate-freev1-checking") ||
      document.getElementById("privacygate-freev1-review") ||
      document.getElementById("privacygate-document-working") ||
      document.getElementById("privacygate-document-review") ||
      document.getElementById("privacygate-multi-ai-document-working") ||
      document.getElementById("privacygate-multi-ai-document-review")
    );
  }

  function stop(event) {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
  }

  function guard(event) {
    if (!enabled || !event.isTrusted || !isSendAttempt(event)) return;
    const now = Date.now();

    if (privacyGateBusy()) {
      stop(event);
      return;
    }

    const sameGesture = gestureStartedAt > 0 && now - gestureStartedAt <= GESTURE_MS;
    if (sameGesture) {
      if (gestureTypes.has(event.type)) {
        stop(event);
        return;
      }
      gestureTypes.add(event.type);
      return;
    }

    if (now < lockedUntil) {
      stop(event);
      return;
    }

    gestureStartedAt = now;
    lockedUntil = now + LOCK_MS;
    gestureTypes = new Set([event.type]);
  }

  for (const type of ["keydown", "submit", "click"]) {
    document.addEventListener(type, guard, true);
  }

  chrome.storage.local.get({ [STORAGE_KEY]: true }, values => {
    enabled = values?.[STORAGE_KEY] !== false;
  });
  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName !== "local" || !changes[STORAGE_KEY]) return;
    enabled = changes[STORAGE_KEY].newValue !== false;
    if (!enabled) {
      gestureStartedAt = 0;
      lockedUntil = 0;
      gestureTypes.clear();
    }
  });
})();
