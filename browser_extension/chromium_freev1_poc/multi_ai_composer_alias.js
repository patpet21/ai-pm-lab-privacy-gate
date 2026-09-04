(() => {
  "use strict";

  if (window.top !== window) return;
  const host = location.hostname.toLowerCase();
  if (!new Set(["claude.ai", "gemini.google.com"]).has(host)) return;

  function candidate() {
    if (host === "claude.ai") {
      return (
        document.querySelector('div.ProseMirror[contenteditable="true"]') ||
        document.querySelector('[contenteditable="true"][data-placeholder]') ||
        document.querySelector('fieldset [contenteditable="true"]') ||
        document.querySelector('textarea[placeholder*="message" i]')
      );
    }
    return (
      document.querySelector('rich-textarea [contenteditable="true"]') ||
      document.querySelector('[contenteditable="true"][aria-label*="prompt" i]') ||
      document.querySelector('[contenteditable="true"][aria-label*="message" i]') ||
      document.querySelector('textarea[aria-label*="prompt" i]')
    );
  }

  function applyAlias() {
    const current = document.getElementById("prompt-textarea");
    if (current?.isConnected) return;
    const box = candidate();
    if (!(box instanceof HTMLElement)) return;
    box.id = "prompt-textarea";
    box.dataset.privacygateComposerAlias = host;
  }

  const observer = new MutationObserver(applyAlias);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  applyAlias();
})();
