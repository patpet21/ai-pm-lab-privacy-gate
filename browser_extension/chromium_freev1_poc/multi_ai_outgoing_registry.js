(() => {
  "use strict";

  if (window.top !== window) return;
  const host = location.hostname.toLowerCase();
  if (!new Set(["claude.ai", "gemini.google.com"]).has(host)) return;

  const PLACEHOLDER_RE = /\[\[PG(?:\\?_[A-Z0-9]+)+\]\]/g;
  const recent = [];
  const MAX_RECENT = 12;

  function canonical(text) {
    return String(text || "")
      .replace(/[\u200B-\u200D\uFEFF]/g, "")
      .replace(PLACEHOLDER_RE, token => token.replace(/\\_/g, "_"))
      .replace(/\s+/g, " ")
      .trim();
  }

  function hasPlaceholder(text) {
    PLACEHOLDER_RE.lastIndex = 0;
    return PLACEHOLDER_RE.test(String(text || ""));
  }

  function composer() {
    if (host === "claude.ai") {
      return (
        document.querySelector('div.ProseMirror[contenteditable="true"]') ||
        document.querySelector('[contenteditable="true"][data-placeholder]') ||
        document.querySelector('textarea[placeholder*="message" i]') ||
        document.querySelector('textarea')
      );
    }
    return (
      document.querySelector('rich-textarea [contenteditable="true"]') ||
      document.querySelector('.ql-editor[contenteditable="true"]') ||
      document.querySelector('[contenteditable="true"][aria-label*="prompt" i]') ||
      document.querySelector('[contenteditable="true"][aria-label*="message" i]') ||
      document.querySelector('textarea[aria-label*="prompt" i]') ||
      document.querySelector('textarea')
    );
  }

  function composerText(box = composer()) {
    if (!box) return "";
    if (box instanceof HTMLTextAreaElement || box instanceof HTMLInputElement) return box.value || "";
    return box.innerText || box.textContent || "";
  }

  function remember(text) {
    if (!hasPlaceholder(text)) return;
    const value = canonical(text);
    if (!value) return;
    const existing = recent.indexOf(value);
    if (existing >= 0) recent.splice(existing, 1);
    recent.unshift(value);
    if (recent.length > MAX_RECENT) recent.length = MAX_RECENT;
  }

  function isOutgoing(text) {
    const value = canonical(text);
    return Boolean(value) && recent.includes(value);
  }

  function captureComposer() {
    const text = composerText();
    if (hasPlaceholder(text)) remember(text);
  }

  globalThis.PrivacyGateMultiAiOutgoing = Object.freeze({
    remember,
    isOutgoing
  });

  // replaceComposerText() emits an input event after PrivacyGate writes the
  // protected prompt. Capture that exact protected value before the provider
  // clears/rerenders the composer.
  document.addEventListener("input", captureComposer, true);
  document.addEventListener("change", captureComposer, true);

  // Safety net for provider editor implementations that swallow synthetic input.
  setInterval(captureComposer, 180);
})();
