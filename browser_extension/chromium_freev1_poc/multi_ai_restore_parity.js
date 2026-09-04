(() => {
  "use strict";

  if (window.top !== window) return;
  const host = location.hostname.toLowerCase();
  if (!new Set(["claude.ai", "gemini.google.com"]).has(host)) return;

  const STORAGE_KEY = "privacygateProtectionEnabled";
  const FRAME_CLASS = "privacygate-secure-restore-frame";
  const OVERLAY_SOURCE = "privacygate-secure-restore";
  const PLACEHOLDER_RE = /\[\[PG(?:\\?_[A-Z0-9]+)+\]\]/g;
  const views = new Map();
  const pendingTextByRoot = new WeakMap();
  const retryAfterByRoot = new WeakMap();
  let enabled = true;
  let scanTimer = null;

  function canonical(text) {
    return String(text || "")
      .replace(/[\u200B-\u200D\uFEFF]/g, "")
      .replace(PLACEHOLDER_RE, token => token.replace(/\\_/g, "_"));
  }

  function hasPlaceholder(text) {
    PLACEHOLDER_RE.lastIndex = 0;
    return PLACEHOLDER_RE.test(canonical(text));
  }

  function visibleText(root) {
    return root instanceof Element ? (root.innerText || root.textContent || "") : "";
  }

  function composer() {
    if (host === "claude.ai") {
      return document.querySelector('div.ProseMirror[contenteditable="true"], [contenteditable="true"][data-placeholder], textarea');
    }
    return document.querySelector('rich-textarea [contenteditable="true"], .ql-editor[contenteditable="true"], textarea[aria-label*="prompt" i], textarea');
  }

  function excluded(element) {
    if (!(element instanceof Element)) return true;
    const box = composer();
    return Boolean(
      (box && (element === box || element.contains(box) || box.contains(element))) ||
      element.closest?.(
        '#privacygate-freev1-bar, #privacygate-freev1-review, #privacygate-freev1-checking, ' +
        '#privacygate-freev1-notice, #privacygate-document-review, #privacygate-document-working, .' + FRAME_CLASS
      )
    );
  }

  function selectors() {
    if (host === "claude.ai") {
      return [
        '[data-testid*="assistant" i]',
        '[data-testid*="message" i]',
        '[class*="assistant" i]',
        '[class*="response" i]',
        'article',
        '.prose',
        'p', 'li', 'pre', 'blockquote', 'code'
      ];
    }
    return [
      'model-response',
      'message-content',
      '[class*="model-response" i]',
      '[class*="response" i]',
      '[data-test-id*="response" i]',
      'article',
      '.markdown',
      'p', 'li', 'pre', 'blockquote', 'code'
    ];
  }

  function candidateRoots() {
    const found = [];
    const seen = new Set();
    for (const selector of selectors()) {
      for (const node of document.querySelectorAll?.(selector) || []) {
        if (!(node instanceof Element) || seen.has(node) || excluded(node)) continue;
        const text = visibleText(node);
        if (!hasPlaceholder(text)) continue;
        seen.add(node);
        found.push(node);
      }
    }

    // Prefer the smallest visible response element that still contains the full placeholder text.
    return found.filter(root => !found.some(other => other !== root && root.contains(other) && hasPlaceholder(visibleText(other))));
  }

  function anchorFor(root) {
    if (host === "claude.ai") {
      return root.closest?.('[data-testid*="assistant" i], [data-testid*="message" i], article') || root;
    }
    return root.closest?.('model-response, message-content, [class*="model-response" i], article') || root;
  }

  function estimatedHeight(root) {
    const height = Number(root?.getBoundingClientRect?.().height || 0);
    return Number.isFinite(height) && height > 0 ? Math.max(92, Math.min(Math.ceil(height + 54), 2400)) : 150;
  }

  function sendToFrame(frame, text) {
    if (!frame?.contentWindow) return;
    frame.contentWindow.postMessage(
      { source: OVERLAY_SOURCE, type: "PG_RENDER_RESTORED_TEXT", text },
      new URL(chrome.runtime.getURL("/")).origin
    );
  }

  function ensureFrame(root) {
    let state = views.get(root);
    if (state?.frame?.isConnected) return state;

    const frame = document.createElement("iframe");
    frame.className = FRAME_CLASS;
    frame.src = chrome.runtime.getURL("restore_overlay.html");
    frame.title = "PrivacyGate local restored view";
    frame.setAttribute("aria-label", "PrivacyGate local restored view");
    frame.referrerPolicy = "no-referrer";
    Object.assign(frame.style, {
      display: "block",
      width: "100%",
      minHeight: "92px",
      height: `${estimatedHeight(root)}px`,
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

    state = { frame, protectedText: "", restoredText: "" };
    views.set(root, state);
    frame.addEventListener("load", () => {
      const current = views.get(root);
      if (current?.restoredText) sendToFrame(frame, current.restoredText);
    });
    return state;
  }

  function removeView(root) {
    const state = views.get(root);
    state?.frame?.remove();
    views.delete(root);
  }

  function cleanup() {
    for (const [root, state] of Array.from(views.entries())) {
      if (!enabled || !root.isConnected || !state.frame?.isConnected) removeView(root);
    }
  }

  function restoreRoot(root) {
    if (!enabled || !root?.isConnected || excluded(root)) return;
    const protectedText = canonical(visibleText(root));
    if (!hasPlaceholder(protectedText)) {
      removeView(root);
      return;
    }

    const current = views.get(root);
    if (current?.protectedText === protectedText && current.restoredText) return;
    if (pendingTextByRoot.get(root) === protectedText) return;
    if (Number(retryAfterByRoot.get(root) || 0) > Date.now()) return;

    pendingTextByRoot.set(root, protectedText);
    chrome.runtime.sendMessage({ type: "PG_RESTORE", text: protectedText }, response => {
      if (pendingTextByRoot.get(root) === protectedText) pendingTextByRoot.delete(root);
      if (chrome.runtime.lastError || !response?.ok || !root.isConnected || !enabled) {
        retryAfterByRoot.set(root, Date.now() + 4000);
        return;
      }
      const restoredText = response.data?.restored_text;
      if (typeof restoredText !== "string" || !restoredText || restoredText === protectedText) {
        retryAfterByRoot.set(root, Date.now() + 4000);
        return;
      }
      if (canonical(visibleText(root)) !== protectedText) {
        schedule(80);
        return;
      }
      retryAfterByRoot.delete(root);
      const state = ensureFrame(root);
      state.protectedText = protectedText;
      state.restoredText = restoredText;
      sendToFrame(state.frame, restoredText);
    });
  }

  function scan() {
    if (!enabled) return;
    cleanup();
    candidateRoots().forEach(restoreRoot);
  }

  function schedule(delay = 120) {
    clearTimeout(scanTimer);
    scanTimer = setTimeout(scan, delay);
  }

  window.addEventListener("message", event => {
    const state = Array.from(views.values()).find(item => item.frame?.contentWindow === event.source);
    if (!state) return;
    const data = event.data;
    if (!data || data.source !== OVERLAY_SOURCE || data.type !== "PG_OVERLAY_HEIGHT") return;
    const height = Math.max(72, Math.min(Number(data.height || 0), 2400));
    if (Number.isFinite(height) && height > 0) state.frame.style.height = `${Math.ceil(height)}px`;
  });

  const observer = new MutationObserver(mutations => {
    const meaningful = mutations.some(mutation => {
      if (mutation.target instanceof Element && mutation.target.closest?.(`.${FRAME_CLASS}`)) return false;
      return mutation.type === "characterData" || Array.from(mutation.addedNodes || []).some(node => !(node instanceof Element && node.classList?.contains(FRAME_CLASS)));
    });
    if (meaningful) schedule(140);
  });
  observer.observe(document.documentElement, { childList: true, subtree: true, characterData: true });

  chrome.storage.local.get({ [STORAGE_KEY]: true }, values => {
    enabled = values?.[STORAGE_KEY] !== false;
    if (enabled) schedule(120);
  });
  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName !== "local" || !changes[STORAGE_KEY]) return;
    enabled = changes[STORAGE_KEY].newValue !== false;
    if (!enabled) {
      for (const root of Array.from(views.keys())) removeView(root);
    } else {
      schedule(0);
    }
  });

  setInterval(() => {
    cleanup();
    if (enabled) scan();
  }, 1800);
})();
