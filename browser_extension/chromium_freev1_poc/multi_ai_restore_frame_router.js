(() => {
  "use strict";

  if (window.top !== window) return;
  const host = location.hostname.toLowerCase();
  if (!new Set(["claude.ai", "gemini.google.com"]).has(host)) return;

  const FRAME_CLASS = "privacygate-secure-restore-frame";
  const targetUrl = chrome.runtime.getURL("multi_ai_restore_overlay.html");

  function route(frame) {
    if (!(frame instanceof HTMLIFrameElement) || !frame.classList.contains(FRAME_CLASS)) return;
    if (frame.src !== targetUrl) frame.src = targetUrl;
  }

  document.querySelectorAll?.(`iframe.${FRAME_CLASS}`).forEach(route);

  const observer = new MutationObserver(mutations => {
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes || []) {
        if (!(node instanceof Element)) continue;
        if (node.matches?.(`iframe.${FRAME_CLASS}`)) route(node);
        node.querySelectorAll?.(`iframe.${FRAME_CLASS}`).forEach(route);
      }
    }
  });

  observer.observe(document.documentElement, { childList: true, subtree: true });
})();
