(() => {
  "use strict";

  if (window.top !== window) return;

  const STORAGE_KEY = "privacygateProtectionEnabled";

  function syncVisibleControl(enabled, attempt = 0) {
    const toggle = document.querySelector(
      '#privacygate-freev1-bar [data-pg-role="toggle"]'
    );

    if (!toggle) {
      if (attempt < 5) {
        setTimeout(() => syncVisibleControl(enabled, attempt + 1), 120 * (attempt + 1));
      }
      return;
    }

    const current = toggle.getAttribute("aria-checked") !== "false";
    if (current !== Boolean(enabled)) {
      // Use content.js's own switch handler so its private in-memory state,
      // review UI and send interception state all change together.
      toggle.click();
    }
  }

  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName !== "local") return;
    const change = changes?.[STORAGE_KEY];
    if (!change) return;
    syncVisibleControl(change.newValue !== false);
  });
})();
