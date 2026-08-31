(() => {
  "use strict";

  if (window.top !== window) return;

  const SEND_SELECTOR =
    'button[data-testid="send-button"],' +
    'button[aria-label*="send" i],' +
    'button[aria-label*="submit" i]';
  const PLACEHOLDER_MARKER = "[[PG_";
  const originalDocumentAddEventListener = document.addEventListener;
  const originalButtonClick = HTMLButtonElement.prototype.click;

  function composer() {
    return (
      document.querySelector("#prompt-textarea") ||
      document.querySelector('[contenteditable="true"]')
    );
  }

  function composerText(box) {
    if (!box) return "";
    if (box instanceof HTMLTextAreaElement || box instanceof HTMLInputElement) {
      return box.value || "";
    }
    return box.innerText || box.textContent || "";
  }

  function hasProtectedComposer() {
    return composerText(composer()).includes(PLACEHOLDER_MARKER);
  }

  function approvedProgrammaticSendActive() {
    return Number(window.__privacyGateApprovedSendUntil || 0) > Date.now();
  }

  function isSendEvent(type, event) {
    if (type === "click") {
      return event?.target instanceof Element && Boolean(event.target.closest(SEND_SELECTOR));
    }
    if (type === "submit") {
      const box = composer();
      return Boolean(
        box &&
        event?.target instanceof HTMLFormElement &&
        event.target.contains(box)
      );
    }
    if (type === "keydown") {
      if (event?.key !== "Enter" || event.shiftKey || event.ctrlKey || event.altKey || event.metaKey) {
        return false;
      }
      const box = composer();
      return Boolean(box && (event.target === box || box.contains(event.target)));
    }
    return false;
  }

  HTMLButtonElement.prototype.click = function privacyGateApprovedClick() {
    try {
      if (this.matches?.(SEND_SELECTOR)) {
        // PrivacyGate's approved send is programmatic. Keep a short one-shot
        // window so ChatGPT's click -> submit sequence is not intercepted again.
        window.__privacyGateApprovedSendUntil = Date.now() + 1800;
      }
    } catch (_error) {
      // Fall through to the browser's native click behavior.
    }
    return originalButtonClick.call(this);
  };

  document.addEventListener = function privacyGateRegistrationGuard(type, listener, options) {
    const capture = options === true || Boolean(options && typeof options === "object" && options.capture);
    const guardedType = capture && ["click", "submit", "keydown"].includes(type);

    if (!guardedType || typeof listener !== "function") {
      return originalDocumentAddEventListener.call(this, type, listener, options);
    }

    const wrapped = function privacyGateGuardedListener(event) {
      if (
        isSendEvent(type, event) &&
        (approvedProgrammaticSendActive() || hasProtectedComposer())
      ) {
        // Do not call PrivacyGate's own send interceptor again. We intentionally
        // do not stop propagation here: ChatGPT must receive the already-approved
        // send event normally.
        return;
      }
      return listener.call(this, event);
    };

    return originalDocumentAddEventListener.call(this, type, wrapped, options);
  };

  window.__privacyGateRestoreDocumentAddEventListener = () => {
    document.addEventListener = originalDocumentAddEventListener;
    delete window.__privacyGateRestoreDocumentAddEventListener;
  };
})();
