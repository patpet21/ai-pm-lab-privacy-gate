(() => {
  "use strict";

  if (window.top !== window) return;

  let scanTimer = null;
  const pendingTokens = new Set();

  // Accept canonical placeholders and Markdown-escaped variants, including
  // placeholders split across several DOM text nodes in ChatGPT's final cards.
  const PLACEHOLDER_RE = /\[\[PG(?:\\?_[A-Z0-9]+)+\]\]/g;

  function canonicalToken(token) {
    return String(token || "").replace(/\\_/g, "_");
  }

  function excludedElement(element) {
    if (!(element instanceof Element)) return true;
    return Boolean(
      element.closest?.(
        '[data-message-author-role="user"], #prompt-textarea, ' +
        '#privacygate-freev1-bar, #privacygate-freev1-review, #privacygate-freev1-checking, ' +
        '#privacygate-freev1-notice, #privacygate-composer-sync-error'
      )
    );
  }

  function textMap(root) {
    const entries = [];
    let text = "";
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node = walker.nextNode();

    while (node) {
      if (!excludedElement(node.parentElement)) {
        const value = node.nodeValue || "";
        if (value) {
          entries.push({ node, start: text.length, end: text.length + value.length });
          text += value;
        }
      }
      node = walker.nextNode();
    }

    return { text, entries };
  }

  function locateBoundary(entries, offset, isEnd = false) {
    for (const entry of entries) {
      if (offset < entry.end || (isEnd && offset === entry.end)) {
        return {
          node: entry.node,
          offset: Math.max(0, Math.min(offset - entry.start, (entry.node.nodeValue || "").length))
        };
      }
    }
    return null;
  }

  function findCanonicalRange(root, wantedCanonical) {
    if (!(root instanceof Element) || !root.isConnected || excludedElement(root)) return null;

    const { text, entries } = textMap(root);
    PLACEHOLDER_RE.lastIndex = 0;
    let match;

    while ((match = PLACEHOLDER_RE.exec(text))) {
      if (canonicalToken(match[0]) !== wantedCanonical) continue;

      const start = locateBoundary(entries, match.index, false);
      const end = locateBoundary(entries, match.index + match[0].length, true);
      if (!start || !end || !start.node.isConnected || !end.node.isConnected) return null;

      return {
        visibleToken: match[0],
        start,
        end
      };
    }

    return null;
  }

  function replaceRange(root, wantedCanonical, restoredValue) {
    const located = findCanonicalRange(root, wantedCanonical);
    if (!located) return false;

    const range = document.createRange();
    try {
      range.setStart(located.start.node, located.start.offset);
      range.setEnd(located.end.node, located.end.offset);
      range.deleteContents();
      const replacement = document.createTextNode(restoredValue);
      range.insertNode(replacement);
      replacement.parentElement?.setAttribute("data-privacygate-restored", "true");
      return true;
    } catch (_error) {
      return false;
    } finally {
      range.detach?.();
    }
  }

  function restoreToken(root, visibleToken) {
    const canonical = canonicalToken(visibleToken);
    if (!canonical.startsWith("[[PG_") || pendingTokens.has(canonical)) return;

    pendingTokens.add(canonical);
    chrome.runtime.sendMessage(
      {
        type: "PG_RESTORE",
        text: canonical
      },
      response => {
        pendingTokens.delete(canonical);
        if (chrome.runtime.lastError || !response?.ok || !root.isConnected) return;

        const restored = response.data?.restored_text;
        if (
          typeof restored !== "string" ||
          !restored ||
          restored === canonical
        ) {
          return;
        }

        replaceRange(root, canonical, restored);
      }
    );
  }

  function scanRoot(root) {
    if (!(root instanceof Element) || !root.isConnected || excludedElement(root)) return;

    const { text } = textMap(root);
    if (!text.includes("PG")) return;

    PLACEHOLDER_RE.lastIndex = 0;
    const tokens = [];
    let match;
    while ((match = PLACEHOLDER_RE.exec(text))) {
      tokens.push(match[0]);
    }

    // Restore from the last token backwards. This keeps earlier flattened
    // offsets stable when several placeholders exist in the same long card.
    for (let index = tokens.length - 1; index >= 0; index -= 1) {
      restoreToken(root, tokens[index]);
    }
  }

  function candidateRoots(root = document) {
    const roots = new Set();
    const scope = root instanceof Element || root instanceof Document ? root : document;

    if (root instanceof Element && !excludedElement(root)) {
      const ownText = root.textContent || "";
      if (ownText.includes("PG")) roots.add(root);
    }

    for (const element of scope.querySelectorAll?.(
      '[data-message-author-role="assistant"], [contenteditable="true"]'
    ) || []) {
      if (excludedElement(element)) continue;
      if ((element.textContent || "").includes("PG")) roots.add(element);
    }

    // Fallback for final cards that are neither assistant roots nor explicitly
    // contenteditable. Start from a text fragment containing PG and climb to the
    // smallest ancestor whose concatenated text contains a complete placeholder.
    const walkerRoot = root instanceof Element ? root : (document.body || document.documentElement);
    if (walkerRoot) {
      const walker = document.createTreeWalker(walkerRoot, NodeFilter.SHOW_TEXT);
      let node = walker.nextNode();
      while (node) {
        if ((node.nodeValue || "").includes("PG") && !excludedElement(node.parentElement)) {
          let element = node.parentElement;
          let depth = 0;
          while (element && depth < 7 && element !== document.body) {
            if (excludedElement(element)) break;
            const value = element.textContent || "";
            PLACEHOLDER_RE.lastIndex = 0;
            if (PLACEHOLDER_RE.test(value)) {
              roots.add(element);
              break;
            }
            element = element.parentElement;
            depth += 1;
          }
        }
        node = walker.nextNode();
      }
    }

    return roots;
  }

  function scan(root = document) {
    for (const candidate of candidateRoots(root)) {
      scanRoot(candidate);
    }
  }

  function scheduleScan(delay = 80) {
    clearTimeout(scanTimer);
    scanTimer = setTimeout(() => {
      scanTimer = null;
      scan(document);
    }, delay);
  }

  const observer = new MutationObserver(mutations => {
    for (const mutation of mutations) {
      if (mutation.type === "characterData") {
        const parent = mutation.target?.parentElement;
        if (parent) scan(parent);
        continue;
      }

      for (const added of mutation.addedNodes) {
        if (added instanceof Element) {
          scan(added);
        } else if (added instanceof Text && added.parentElement) {
          scan(added.parentElement);
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

  // ChatGPT can replace the streamed tree with a different final card tree.
  // Keep reconciling locally; user messages and the real prompt composer are
  // explicitly excluded above.
  setInterval(() => scan(document), 350);
  scheduleScan(60);
})();
