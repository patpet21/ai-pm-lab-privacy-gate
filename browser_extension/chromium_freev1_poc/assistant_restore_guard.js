(() => {
  "use strict";

  if (window.top !== window) return;

  const pending = new WeakSet();
  let scanTimer = null;

  // Accept canonical placeholders and Markdown-escaped variants returned by
  // ChatGPT, including rendered email/cards that may move outside the original
  // assistant message root during streaming.
  const PLACEHOLDER_RE = /\[\[PG(?:\\?_[A-Z0-9]+)+\]\]/g;

  function normalizePlaceholders(text) {
    return String(text || "").replace(PLACEHOLDER_RE, token =>
      token.replace(/\\_/g, "_")
    );
  }

  function hasPlaceholder(text) {
    PLACEHOLDER_RE.lastIndex = 0;
    return PLACEHOLDER_RE.test(String(text || ""));
  }

  function excludedFromRestore(node) {
    const element = node instanceof Element ? node : node?.parentElement;
    if (!element) return true;

    // Never make the user's outbound bubble look unprotected and never touch
    // the live composer or PrivacyGate's own UI. Everything else containing a
    // session placeholder is an AI-rendered/local surface eligible for restore.
    return Boolean(
      element.closest?.(
        '[data-message-author-role="user"], #prompt-textarea, textarea, input, [contenteditable="true"], ' +
        '#privacygate-freev1-bar, #privacygate-freev1-review, #privacygate-freev1-checking, ' +
        '#privacygate-freev1-notice, #privacygate-composer-sync-error'
      )
    );
  }

  function restoreTextNode(node) {
    if (!(node instanceof Text) || !node.isConnected || pending.has(node)) return;
    if (excludedFromRestore(node)) return;

    const visibleText = node.nodeValue || "";
    if (!hasPlaceholder(visibleText)) return;

    const protectedText = normalizePlaceholders(visibleText);
    pending.add(node);

    chrome.runtime.sendMessage(
      {
        type: "PG_RESTORE",
        text: protectedText
      },
      response => {
        pending.delete(node);

        if (chrome.runtime.lastError || !response?.ok || !node.isConnected) return;

        const restoredText = response.data?.restored_text;
        if (
          typeof restoredText !== "string" ||
          restoredText === protectedText ||
          node.nodeValue !== visibleText ||
          excludedFromRestore(node)
        ) {
          return;
        }

        node.nodeValue = restoredText;
        node.parentElement?.setAttribute("data-privacygate-restored", "true");
      }
    );
  }

  function scan(root = document.body || document.documentElement) {
    if (!root) return;

    if (root instanceof Text) {
      restoreTextNode(root);
      return;
    }

    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node = walker.nextNode();
    while (node) {
      restoreTextNode(node);
      node = walker.nextNode();
    }
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
        restoreTextNode(mutation.target);
        continue;
      }

      for (const added of mutation.addedNodes) {
        if (added instanceof Text) {
          restoreTextNode(added);
        } else if (added instanceof Element) {
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

  // ChatGPT can replace a streamed response/card after local DOM restoration.
  // Re-scan all non-user surfaces so the local view converges back to restored
  // values even after the final render mounts in a different container.
  setInterval(() => scan(), 450);
  scheduleScan(60);
})();
