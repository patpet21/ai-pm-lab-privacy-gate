(() => {
  "use strict";

  if (window.top !== window) return;

  const pending = new WeakSet();
  let scanTimer = null;

  // Accept both canonical placeholders and Markdown-escaped variants returned
  // by AI web UIs, e.g. [[PG_BATCH_TOKEN_PERSON_001]] and
  // [[PG\_BATCH\_TOKEN\_PERSON\_001]].
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

  function assistantRootFor(node) {
    const element = node instanceof Element ? node : node?.parentElement;
    return element?.closest?.('[data-message-author-role="assistant"]') || null;
  }

  function restoreTextNode(node) {
    if (!(node instanceof Text) || !node.isConnected || pending.has(node)) return;
    if (!assistantRootFor(node)) return;

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
          node.nodeValue !== visibleText
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

    const assistantRoots = root instanceof Element && root.matches?.('[data-message-author-role="assistant"]')
      ? [root]
      : Array.from(
          root.querySelectorAll?.('[data-message-author-role="assistant"]') || []
        );

    for (const assistantRoot of assistantRoots) {
      const walker = document.createTreeWalker(assistantRoot, NodeFilter.SHOW_TEXT);
      let node = walker.nextNode();
      while (node) {
        restoreTextNode(node);
        node = walker.nextNode();
      }
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
          if (added.matches?.('[data-message-author-role="assistant"]')) {
            scan(added);
          } else if (added.querySelector?.('[data-message-author-role="assistant"]')) {
            scan(added);
          }
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

  // ChatGPT can re-render streamed markdown after a local DOM replacement.
  // This lightweight pass restores it again without touching user messages.
  setInterval(() => scan(), 600);
  scheduleScan(60);
})();
