(() => {
  "use strict";

  if (window.top !== window) return;
  const host = location.hostname.toLowerCase();
  if (!new Set(["claude.ai", "gemini.google.com"]).has(host)) return;

  const BAR_ID = "privacygate-freev1-bar";

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
      document.querySelector('textarea[aria-label*="prompt" i]') ||
      document.querySelector('textarea')
    );
  }

  function visualShell(box) {
    if (!(box instanceof Element)) return null;
    const boxRect = box.getBoundingClientRect();
    let node = box;
    let best = null;
    for (let depth = 0; depth < 8 && node?.parentElement; depth += 1) {
      node = node.parentElement;
      const rect = node.getBoundingClientRect();
      if (rect.width < Math.max(260, boxRect.width * 0.9)) continue;
      if (rect.height < 48 || rect.height > 240) continue;
      if (rect.bottom <= boxRect.bottom - 4) continue;
      const score = Math.abs(rect.height - (host === "gemini.google.com" ? 108 : 78));
      if (!best || score < best.score) best = { node, rect, score };
    }
    return best?.node || box.parentElement;
  }

  function place() {
    const bar = document.getElementById(BAR_ID);
    const box = composer();
    if (!bar || !box) return;
    const shell = visualShell(box);
    const rect = shell?.getBoundingClientRect?.();
    if (!rect || !Number.isFinite(rect.left) || rect.width <= 0) return;

    Object.assign(bar.style, {
      position: "fixed",
      left: `${Math.round(rect.left)}px`,
      top: `${Math.round(rect.bottom + 6)}px`,
      width: `${Math.round(rect.width)}px`,
      padding: "0",
      margin: "0",
      transform: "none",
      zIndex: "2147483644",
      pointerEvents: "none"
    });
  }

  const timer = setInterval(() => {
    if (!document.documentElement?.isConnected) {
      clearInterval(timer);
      return;
    }
    place();
  }, 350);

  window.addEventListener("resize", place, { passive: true });
  window.addEventListener("scroll", place, { passive: true, capture: true });
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", place, { once: true });
  } else {
    place();
  }
})();
