(() => {
  "use strict";

  const SOURCE = "privacygate-secure-restore";
  const ALLOWED_PARENT_ORIGINS = new Set([
    "https://claude.ai",
    "https://gemini.google.com"
  ]);
  const output = document.getElementById("restored");
  let hasRenderedText = false;
  let parentOrigin = "";

  function reportHeight() {
    if (!hasRenderedText || !parentOrigin) return;
    const height = Math.max(
      document.documentElement.scrollHeight,
      document.body?.scrollHeight || 0
    );
    window.parent.postMessage(
      {
        source: SOURCE,
        type: "PG_OVERLAY_HEIGHT",
        height
      },
      parentOrigin
    );
  }

  window.addEventListener("message", event => {
    if (event.source !== window.parent || !ALLOWED_PARENT_ORIGINS.has(event.origin)) return;
    const data = event.data;
    if (!data || data.source !== SOURCE || data.type !== "PG_RENDER_RESTORED_TEXT") return;
    if (typeof data.text !== "string" || !data.text) return;

    parentOrigin = event.origin;
    output.textContent = data.text;
    hasRenderedText = true;
    requestAnimationFrame(reportHeight);
    setTimeout(reportHeight, 60);
  });

  if (typeof ResizeObserver === "function") {
    const observer = new ResizeObserver(() => reportHeight());
    observer.observe(document.documentElement);
  }
})();
