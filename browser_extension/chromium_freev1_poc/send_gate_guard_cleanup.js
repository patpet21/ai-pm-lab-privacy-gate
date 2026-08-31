(() => {
  "use strict";
  try {
    window.__privacyGateRestoreDocumentAddEventListener?.();
  } catch (_error) {
    // Registration patch is temporary; if cleanup fails, the extension remains fail-closed.
  }
})();
