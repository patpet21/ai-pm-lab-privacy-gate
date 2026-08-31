(() => {
  "use strict";

  const SOURCE = "privacygate-secure-restore";
  const output = document.getElementById("restored");
  let hasRenderedText = false;

  function reportHeight() {
    if (!hasRenderedText) return;
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
      "https://chatgpt.com"
    );
  }

  window.addEventListener("message", event => {
    if (event.source !== window.parent || event.origin !== "https://chatgpt.com") return;
    const data = event.data;
    if (!data || data.source !== SOURCE || data.type !== "PG_RENDER_RESTORED_TEXT") return;
    if (typeof data.text !== "string") return;

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
