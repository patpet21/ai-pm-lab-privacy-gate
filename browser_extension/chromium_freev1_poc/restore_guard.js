(() => {
  "use strict";

  if (window.top !== window) return;

  const PLACEHOLDER_MARKER = "[[PG_";
  const pendingNodes = new WeakSet();
  let scanTimer = null;

  function privacyGateUi(node) {
    const element = node instanceof Element ? node : node?.parentElement;
    return Boolean(
      element?.closest?.(
        "#privacygate-freev1-bar, #privacygate-freev1-review, #privacygate-freev1-checking, #privacygate-freev1-notice"
      )
    );
  }

  function insideAssistantMessage(node) {
    const element = node instanceof Element ? node : node?.parentElement;
    return Boolean(element?.closest?.('[data-message-author-role="assistant"]'));
  }

  function eligibleTextNode(node) {
    if (!(node instanceof Text)) return false;
    if (!node.isConnected || pendingNodes.has(node)) return false;
    if (privacyGateUi(node) || !insideAssistantMessage(node)) return false;
    return (node.nodeValue || "").includes(PLACEHOLDER_MARKER);
  }

  function restoreNode(node) {
    if (!eligibleTextNode(node)) return;

    const protectedText = node.nodeValue || "";
    pendingNodes.add(node);

    chrome.runtime.sendMessage(
      {
        type: "PG_RESTORE",
        text: protectedText
      },
      response => {
        pendingNodes.delete(node);

        if (chrome.runtime.lastError || !response?.ok) return;

        const restoredText = response.data?.restored_text;
        if (
          typeof restoredText !== "string" ||
          restoredText === protectedText ||
          !node.isConnected ||
          node.nodeValue !== protectedText
        ) {
          return;
        }

        node.nodeValue = restoredText;
        node.parentElement?.setAttribute("data-privacygate-local-restored", "true");
      }
    );
  }

  function scan(root = document.body || document.documentElement) {
    if (!root) return;

    if (root instanceof Text) {
      restoreNode(root);
      return;
    }

    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const candidates = [];
    let node = walker.nextNode();
    while (node) {
      if (eligibleTextNode(node)) candidates.push(node);
      node = walker.nextNode();
    }

    for (const candidate of candidates) restoreNode(candidate);
  }

  function scheduleScan(delay = 80) {
    clearTimeout(scanTimer);
    scanTimer = setTimeout(() => {
      scanTimer = null;
      scan();
    }, delay);
  }

  const observer = new MutationObserver(mutations => {
    for (const mutation of mutations) {
      if (mutation.type === "characterData") {
        if (eligibleTextNode(mutation.target)) {
          restoreNode(mutation.target);
        }
        continue;
      }

      for (const added of mutation.addedNodes) {
        if (added instanceof Text) {
          restoreNode(added);
        } else if (added instanceof Element && !privacyGateUi(added)) {
          scan(added);
        }
      }
    }

    scheduleScan(120);
  });

  observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true
  });

  // ChatGPT may re-render streamed assistant response chunks after a local DOM replacement.
  // A light periodic pass makes the assistant-only local view resilient without touching user bubbles.
  setInterval(() => scan(), 700);
  scheduleScan(50);
})();
