(() => {
  "use strict";

  if (window.top !== window) return;

  const NOTICE_IDS = new Set([
    "privacygate-freev1-notice",
    "privacygate-pdf-notice"
  ]);

  function centerNotice(node) {
    if (!(node instanceof HTMLElement) || !NOTICE_IDS.has(node.id)) return;
    Object.assign(node.style, {
      left: "50%",
      top: "50%",
      right: "auto",
      bottom: "auto",
      transform: "translate(-50%, -50%)",
      width: "max-content",
      maxWidth: "min(520px, calc(100vw - 32px))",
      textAlign: "center"
    });
  }

  function scan(root) {
    if (!(root instanceof Element)) return;
    centerNotice(root);
    for (const id of NOTICE_IDS) {
      const found = root.querySelector?.(`#${id}`);
      if (found) centerNotice(found);
    }
  }

  const observer = new MutationObserver(records => {
    for (const record of records) {
      for (const node of record.addedNodes) {
        scan(node);
      }
    }
  });

  const start = () => {
    document.querySelectorAll(
      "#privacygate-freev1-notice, #privacygate-pdf-notice"
    ).forEach(centerNotice);
    observer.observe(document.documentElement, { childList: true, subtree: true });
  };

  if (document.documentElement) start();
  else document.addEventListener("DOMContentLoaded", start, { once: true });
})();
