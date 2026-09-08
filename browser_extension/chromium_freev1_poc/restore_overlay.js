(() => {
  "use strict";

  const SOURCE = "privacygate-secure-restore";
  const ALLOWED_PARENT_ORIGINS = new Set([
    "https://chatgpt.com",
    "https://gemini.google.com",
    "https://claude.ai"
  ]);
  const output = document.getElementById("restored");
  let hasRenderedText = false;
  let parentOrigin = null;

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
    if (event.source !== window.parent) return;
    if (!ALLOWED_PARENT_ORIGINS.has(event.origin)) return;

    const data = event.data;
    if (!data || data.source !== SOURCE || data.type !== "PG_RENDER_RESTORED_TEXT") return;
    if (typeof data.text !== "string") return;

    // Pin resize responses to the validated provider origin that rendered the
    // restored value. The iframe never posts restored content back to the page.
    parentOrigin = event.origin;
    output.textContent = data.text;
    hasRenderedText = true;
    requestAnimationFrame(reportHeight);
    setTimeout(reportHeight, 60);
  });

  // Do not report an empty iframe height on load. The parent reserves an
  // estimated height and we resize only after real restored content exists.
  if (typeof ResizeObserver === "function") {
    const observer = new ResizeObserver(() => reportHeight());
    observer.observe(document.documentElement);
  }
})();
