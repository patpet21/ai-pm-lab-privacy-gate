(() => {
  "use strict";

  if (window.top !== window) return;

  const STORAGE_KEY = "privacygateProtectionEnabled";
  let protectionEnabled = true;

  function carriesFiles(event) {
    const transfer = event.dataTransfer;
    if (!transfer) return false;
    const types = Array.from(transfer.types || []);
    return types.includes("Files") || (transfer.items && Array.from(transfer.items).some(item => item.kind === "file"));
  }

  function interceptNativeDropUi(event) {
    if (!protectionEnabled || !carriesFiles(event)) return;

    // Prevent ChatGPT from entering its own full-page "Add anything" drag state.
    // The actual drop event is intentionally NOT handled here: pdf_upload_guard.js
    // owns it and routes the file through PrivacyGate scan -> review -> protected attach.
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    if (event.dataTransfer) {
      try {
        event.dataTransfer.dropEffect = "copy";
      } catch (_error) {
        // Cosmetic only; never affect protection.
      }
    }
  }

  document.addEventListener("dragenter", interceptNativeDropUi, true);
  document.addEventListener("dragover", interceptNativeDropUi, true);

  chrome.storage.local.get({ [STORAGE_KEY]: true }, values => {
    protectionEnabled = values?.[STORAGE_KEY] !== false;
  });

  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName !== "local" || !changes[STORAGE_KEY]) return;
    protectionEnabled = changes[STORAGE_KEY].newValue !== false;
  });
})();
