(() => {
  "use strict";

  if (window.top !== window) return;
  const host = location.hostname.toLowerCase();
  if (!new Set(["claude.ai", "gemini.google.com"]).has(host)) return;

  const BRIDGE_ID = "privacygate-multi-ai-drop-input";
  let lastDropTarget = null;
  let replaying = false;

  function ensureBridgeInput() {
    let input = document.getElementById(BRIDGE_ID);
    if (input instanceof HTMLInputElement) return input;
    input = document.createElement("input");
    input.id = BRIDGE_ID;
    input.type = "file";
    input.accept = ".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document";
    Object.assign(input.style, {
      position: "fixed",
      left: "-9999px",
      top: "-9999px",
      width: "1px",
      height: "1px",
      opacity: "0",
      pointerEvents: "none"
    });
    (document.body || document.documentElement).prepend(input);
    return input;
  }

  function replayProtectedDrop(file) {
    const target = lastDropTarget instanceof Element && lastDropTarget.isConnected
      ? lastDropTarget
      : document.elementFromPoint(window.innerWidth / 2, window.innerHeight / 2);
    if (!(target instanceof Element) || !(file instanceof File)) return false;

    const transfer = new DataTransfer();
    transfer.items.add(file);
    replaying = true;
    try {
      for (const type of ["dragenter", "dragover", "drop"]) {
        const event = new DragEvent(type, {
          bubbles: true,
          cancelable: true,
          composed: true,
          dataTransfer: transfer
        });
        target.dispatchEvent(event);
      }
    } finally {
      queueMicrotask(() => { replaying = false; });
    }
    return true;
  }

  document.addEventListener("drop", event => {
    if (replaying) return;
    const files = Array.from(event.dataTransfer?.files || []);
    if (!files.length) return;
    lastDropTarget = event.target instanceof Element ? event.target : null;
    ensureBridgeInput();
  }, true);

  // document_upload_guard injects the protected file into this hidden input when
  // the provider does not expose a stable native <input type=file> during drop.
  // This capture listener runs before document_upload_guard's own change handler,
  // consumes only our bridge input, and replays the protected file to the exact
  // original Claude/Gemini drop target.
  document.addEventListener("change", event => {
    const input = event.target;
    if (!(input instanceof HTMLInputElement) || input.id !== BRIDGE_ID) return;
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    const file = input.files?.[0] || null;
    if (file) replayProtectedDrop(file);
    input.value = "";
  }, true);

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", ensureBridgeInput, { once: true });
  } else {
    ensureBridgeInput();
  }
})();
