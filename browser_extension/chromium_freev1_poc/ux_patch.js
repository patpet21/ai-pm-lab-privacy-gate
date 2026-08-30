(() => {
  "use strict";

  if (window.top !== window) return;

  function centerWorkingIndicator(indicator) {
    if (!indicator || indicator.dataset.privacygateUxPatched === "true") return;
    indicator.dataset.privacygateUxPatched = "true";

    Object.assign(indicator.style, {
      left: "50%",
      top: "50%",
      right: "auto",
      bottom: "auto",
      transform: "translate(-50%, -50%)",
      opacity: "0",
      visibility: "hidden",
      transition: "opacity 120ms ease",
      boxShadow: "0 12px 34px rgba(15,23,42,.20)"
    });

    setTimeout(() => {
      if (!indicator.isConnected) return;
      indicator.style.visibility = "visible";
      indicator.style.opacity = "1";
    }, 180);
  }

  function enrichAnalysisError(notice) {
    if (!notice || notice.dataset.privacygateDiagnosticApplied === "true") return;
    if (!notice.textContent?.includes("local analysis unavailable")) return;

    notice.dataset.privacygateDiagnosticApplied = "true";

    chrome.runtime.sendMessage(
      { type: "PG_ANALYZE_DIAGNOSTIC" },
      response => {
        if (!notice.isConnected || chrome.runtime.lastError) return;

        const diagnostic = response?.diagnostic;
        if (!diagnostic) return;

        const status = Number(diagnostic.status || 0);
        const code = String(diagnostic.code || "unknown_error");

        notice.textContent = status > 0
          ? `PrivacyGate — local check failed (HTTP ${status}: ${code}). Nothing was sent.`
          : "PrivacyGate — Local Privacy Bridge is not reachable. Nothing was sent.";
      }
    );
  }

  function inspect(root = document) {
    const indicator = root.querySelector?.("#privacygate-freev1-checking");
    if (indicator) centerWorkingIndicator(indicator);

    const notice = root.querySelector?.("#privacygate-freev1-notice");
    if (notice) enrichAnalysisError(notice);
  }

  const observer = new MutationObserver(records => {
    for (const record of records) {
      for (const node of record.addedNodes) {
        if (!(node instanceof Element)) continue;

        if (node.id === "privacygate-freev1-checking") {
          centerWorkingIndicator(node);
        } else if (node.id === "privacygate-freev1-notice") {
          enrichAnalysisError(node);
        } else {
          inspect(node);
        }
      }

      if (record.type === "characterData") {
        const parent = record.target.parentElement;
        if (parent?.id === "privacygate-freev1-notice") {
          enrichAnalysisError(parent);
        }
      }
    }
  });

  observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true
  });

  inspect();
})();
