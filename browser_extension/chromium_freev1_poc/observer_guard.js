(() => {
  "use strict";

  const NativeMutationObserver = globalThis.MutationObserver;
  if (typeof NativeMutationObserver !== "function") return;

  function belongsToPrivacyGateUi(node) {
    const element = node instanceof Element ? node : node?.parentElement;
    return Boolean(
      element?.closest?.(
        "#privacygate-freev1-bar, #privacygate-freev1-review, #privacygate-freev1-checking, #privacygate-freev1-notice"
      )
    );
  }

  globalThis.MutationObserver = class PrivacyGateSafeMutationObserver extends NativeMutationObserver {
    constructor(callback) {
      super((mutations, observer) => {
        const relevant = mutations.filter(mutation => {
          if (belongsToPrivacyGateUi(mutation.target)) return false;

          if (mutation.type === "childList" && mutation.addedNodes.length) {
            const onlyPrivacyGateNodes = Array.from(mutation.addedNodes).every(node =>
              belongsToPrivacyGateUi(node)
            );
            if (onlyPrivacyGateNodes) return false;
          }

          return true;
        });

        if (relevant.length) {
          callback(relevant, observer);
        }
      });
    }
  };
})();
