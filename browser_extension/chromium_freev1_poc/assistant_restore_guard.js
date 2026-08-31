(() => {
  "use strict";

  if (window.top !== window) return;

  const STORAGE_KEY = "privacygateProtectionEnabled";
  const FRAME_CLASS = "privacygate-secure-restore-frame";
  const OVERLAY_SOURCE = "privacygate-secure-restore";
  const PLACEHOLDER_RE = /\[\[PG(?:\\?_[A-Z0-9]+)+\]\]/g;
  const views = new Map();
  const pendingTextByRoot = new WeakMap();
  const retryAfterByRoot = new WeakMap();
  let protectionEnabled = true;
  let scanTimer = null;

  function canonicalizePlaceholders(text) {
    return String(text || "").replace(PLACEHOLDER_RE, token =>
      token.replace(/\\_/g, "_")
    );
  }

  function hasPlaceholder(text) {
    PLACEHOLDER_RE.lastIndex = 0;
    return PLACEHOLDER_RE.test(String(text || ""));
  }

  function excludedElement(element) {
    if (!(element instanceof Element)) return true;
    return Boolean(
      element.closest?.(
        '[data-message-author-role="user"], #prompt-textarea, ' +
        '#privacygate-freev1-bar, #privacygate-freev1-review, #privacygate-freev1-checking, ' +
        '#privacygate-freev1-notice, #privacygate-composer-sync-error, .' + FRAME_CLASS
      )
    );
  }

  function visibleText(root) {
    if (!(root instanceof Element)) return "";
    return root.innerText || root.textContent || "";
  }

  function assistantContentRoot(root) {
    if (!(root instanceof Element)) return null;

    if (root.matches?.('[data-message-author-role="assistant"]')) {
      const markdown = Array.from(root.querySelectorAll?.(".markdown") || [])
        .find(node => hasPlaceholder(visibleText(node)));
      return markdown || root;
    }

    return root;
  }

  function candidateRoots(scope = document) {
    const roots = [];
    const seen = new Set();
    const queryScope = scope instanceof Element || scope instanceof Document ? scope : document;

    for (const assistant of queryScope.querySelectorAll?.('[data-message-author-role="assistant"]') || []) {
      const root = assistantContentRoot(assistant);
      if (!root || excludedElement(root) || !hasPlaceholder(visibleText(root))) continue;
      seen.add(root);
      roots.push(root);
    }

    for (const editable of queryScope.querySelectorAll?.('[contenteditable="true"]') || []) {
      if (excludedElement(editable) || !hasPlaceholder(visibleText(editable))) continue;
      if (editable.closest?.('[data-message-author-role="assistant"]')) continue;
      if (seen.has(editable)) continue;
      seen.add(editable);
      roots.push(editable);
    }

    return roots;
  }

  function removeView(root) {
    const state = views.get(root);
    if (!state) return;
    state.frame?.remove();
    views.delete(root);
  }

  function removeAllViews() {
    for (const root of Array.from(views.keys())) removeView(root);
    document.querySelectorAll?.(`.${FRAME_CLASS}`).forEach(frame => frame.remove());
  }

  function cleanupViews() {
    for (const [root, state] of Array.from(views.entries())) {
      if (!root.isConnected || !state.frame?.isConnected || !protectionEnabled) {
        removeView(root);
      }
    }
  }

  function anchorFor(root) {
    return (
      root.closest?.('[data-message-author-role="assistant"]') ||
      root.closest?.("article") ||
      root.parentElement ||
      root
    );
  }

  function estimatedFrameHeight(root) {
    const rectHeight = Number(root?.getBoundingClientRect?.().height || 0);
    if (!Number.isFinite(rectHeight) || rectHeight <= 0) return 140;
    return Math.max(92, Math.min(Math.ceil(rectHeight + 54), 2400));
  }

  function ensureFrame(root) {
    let state = views.get(root);
    if (state?.frame?.isConnected) return state;

    const frame = document.createElement("iframe");
    frame.className = FRAME_CLASS;
    frame.src = chrome.runtime.getURL("restore_overlay.html");
    frame.setAttribute("title", "PrivacyGate local restored view");
    frame.setAttribute("aria-label", "PrivacyGate local restored view");
    frame.setAttribute("referrerpolicy", "no-referrer");
    Object.assign(frame.style, {
      display: "block",
      width: "100%",
      minHeight: "92px",
      height: `${estimatedFrameHeight(root)}px`,
      margin: "10px 0 14px",
      border: "0",
      borderRadius: "14px",
      background: "transparent",
      overflow: "hidden",
      overflowAnchor: "none"
    });

    const anchor = anchorFor(root);
    anchor.insertAdjacentElement?.("afterend", frame);
    if (!frame.isConnected && anchor.parentElement) {
      anchor.parentElement.insertBefore(frame, anchor.nextSibling);
    }

    state = {
      frame,
      lastProtectedText: "",
      lastRestoredText: ""
    };
    views.set(root, state);

    frame.addEventListener("load", () => {
      const current = views.get(root);
      if (!current || current.frame !== frame || !current.lastRestoredText) return;
      sendToFrame(frame, current.lastRestoredText);
    });

    return state;
  }

  function sendToFrame(frame, restoredText) {
    if (!frame?.contentWindow || typeof restoredText !== "string") return;
    const targetOrigin = new URL(chrome.runtime.getURL("/")).origin;
    frame.contentWindow.postMessage(
      {
        source: OVERLAY_SOURCE,
        type: "PG_RENDER_RESTORED_TEXT",
        text: restoredText
      },
      targetOrigin
    );
  }

  function renderRestored(root, protectedText, restoredText) {
    if (!protectionEnabled || !root.isConnected) return;
    const state = ensureFrame(root);
    state.lastProtectedText = protectedText;
    state.lastRestoredText = restoredText;
    sendToFrame(state.frame, restoredText);
  }

  function restoreRoot(root) {
    if (!protectionEnabled || !(root instanceof Element) || !root.isConnected || excludedElement(root)) {
      return;
    }

    const rawText = visibleText(root);
    if (!hasPlaceholder(rawText)) {
      removeView(root);
      return;
    }

    const protectedText = canonicalizePlaceholders(rawText);
    const state = views.get(root);
    if (state?.lastProtectedText === protectedText && state.lastRestoredText) return;
    if (pendingTextByRoot.get(root) === protectedText) return;

    const retryAfter = Number(retryAfterByRoot.get(root) || 0);
    if (retryAfter > Date.now()) return;

    // Do not create any iframe yet. A local restored view is mounted only after
    // the Bridge has successfully restored the text. This prevents a stale or
    // missing session from repeatedly inserting/removing blank frames and
    // causing ChatGPT to jump during page hydration or extension reloads.
    pendingTextByRoot.set(root, protectedText);

    chrome.runtime.sendMessage(
      {
        type: "PG_RESTORE",
        text: protectedText
      },
      response => {
        if (pendingTextByRoot.get(root) === protectedText) {
          pendingTextByRoot.delete(root);
        }

        if (
          chrome.runtime.lastError ||
          !response?.ok ||
          !root.isConnected ||
          !protectionEnabled
        ) {
          retryAfterByRoot.set(root, Date.now() + 5000);
          return;
        }

        const restoredText = response.data?.restored_text;
        if (
          typeof restoredText !== "string" ||
          !restoredText ||
          restoredText === protectedText
        ) {
          retryAfterByRoot.set(root, Date.now() + 5000);
          return;
        }

        // If ChatGPT changed the streamed/final response while the Bridge call
        // was in flight, discard this result and let the next scan restore the
        // current text instead of mounting an outdated view.
        if (canonicalizePlaceholders(visibleText(root)) !== protectedText) {
          scheduleScan(80);
          return;
        }

        retryAfterByRoot.delete(root);

        // SECURITY BOUNDARY: never write restoredText into ChatGPT's DOM.
        // It is sent only into a chrome-extension:// iframe, which the page
        // cannot read because of the browser same-origin boundary.
        renderRestored(root, protectedText, restoredText);
      }
    );
  }

  function scan(scope = document) {
    if (!protectionEnabled) return;
    cleanupViews();
    for (const root of candidateRoots(scope)) restoreRoot(root);
  }

  function scheduleScan(delay = 120) {
    clearTimeout(scanTimer);
    scanTimer = setTimeout(() => {
      scanTimer = null;
      scan(document);
    }, delay);
  }

  window.addEventListener("message", event => {
    const frameEntry = Array.from(views.values()).find(state => state.frame?.contentWindow === event.source);
    if (!frameEntry) return;
    const data = event.data;
    if (!data || data.source !== OVERLAY_SOURCE || data.type !== "PG_OVERLAY_HEIGHT") return;
    const height = Math.max(72, Math.min(Number(data.height || 0), 2400));
    if (!Number.isFinite(height) || height <= 0) return;

    const nextHeight = Math.ceil(height);
    const currentHeight = Number.parseFloat(frameEntry.frame.style.height || "0");
    if (!Number.isFinite(currentHeight) || Math.abs(currentHeight - nextHeight) >= 10) {
      frameEntry.frame.style.height = `${nextHeight}px`;
    }
  });

  const observer = new MutationObserver(mutations => {
    // Ignore mutation batches generated solely by our own frame insertion.
    const meaningful = mutations.some(mutation => {
      if (mutation.target instanceof Element && mutation.target.closest?.(`.${FRAME_CLASS}`)) {
        return false;
      }
      return Array.from(mutation.addedNodes || []).some(node => {
        return !(node instanceof Element && node.classList?.contains(FRAME_CLASS));
      }) || mutation.type === "characterData";
    });
    if (meaningful) scheduleScan(140);
  });

  observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true
  });

  chrome.storage.local.get({ [STORAGE_KEY]: true }, values => {
    protectionEnabled = values?.[STORAGE_KEY] !== false;
    if (protectionEnabled) scheduleScan(120);
    else removeAllViews();
  });

  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName !== "local" || !changes[STORAGE_KEY]) return;
    protectionEnabled = changes[STORAGE_KEY].newValue !== false;
    if (protectionEnabled) scheduleScan(120);
    else removeAllViews();
  });

  // Mutation observation handles live streaming. This slower reconciliation is
  // only a safety net for provider-side rerenders that do not surface as a
  // useful local mutation sequence.
  setInterval(() => {
    cleanupViews();
    if (protectionEnabled) scan(document);
  }, 1800);
})();
