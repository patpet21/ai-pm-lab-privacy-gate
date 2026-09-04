(() => {
  "use strict";

  if (window.top !== window) return;
  if (!new Set(["claude.ai", "gemini.google.com"]).has(location.hostname.toLowerCase())) return;

  const STORAGE_KEY = "privacygateProtectionEnabled";
  const FRAME_CLASS = "privacygate-multi-ai-restore-frame";
  const OVERLAY_SOURCE = "privacygate-secure-restore";
  const PLACEHOLDER_RE = /\[\[PG(?:\\?_[A-Z0-9]+)+\]\]/g;
  const views = new Map();
  const pending = new WeakSet();
  let enabled = true;
  let timer = null;

  function canonical(text) {
    return String(text || "").replace(PLACEHOLDER_RE, token => token.replace(/\\_/g, "_"));
  }

  function hasPlaceholder(text) {
    PLACEHOLDER_RE.lastIndex = 0;
    return PLACEHOLDER_RE.test(String(text || ""));
  }

  function composerElement() {
    if (location.hostname === "claude.ai") {
      return document.querySelector('[contenteditable="true"][data-placeholder], div.ProseMirror[contenteditable="true"], textarea');
    }
    return document.querySelector('rich-textarea [contenteditable="true"], textarea, [contenteditable="true"]');
  }

  function excluded(element) {
    if (!(element instanceof Element)) return true;
    const composer = composerElement();
    return Boolean(
      (composer && (element === composer || composer.contains(element) || element.contains(composer))) ||
      element.closest?.(`#privacygate-freev1-bar, #privacygate-freev1-review, .${FRAME_CLASS}`)
    );
  }

  function rootForTextNode(node) {
    const parent = node?.parentElement;
    if (!parent || excluded(parent)) return null;
    return (
      parent.closest("p, li, pre, blockquote, code") ||
      parent.closest('[data-testid*="assistant" i], [data-testid*="response" i], model-response, message-content, article') ||
      parent
    );
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
    frame.referrerPolicy = "no-referrer";
    Object.assign(frame.style, {
      display: "block",
      width: "100%",
      minHeight: "92px",
      height: "150px",
      margin: "10px 0 14px",
      border: "0",
      borderRadius: "14px",
      background: "transparent",
      overflow: "hidden"
    });
    root.insertAdjacentElement("afterend", frame);
    state = { frame, protectedText: "", restoredText: "" };
    views.set(root, state);
    frame.addEventListener("load", () => {
      const current = views.get(root);
      if (current?.restoredText) sendToFrame(frame, current.restoredText);
    });
    return state;
  }

  function restoreRoot(root) {
    if (!enabled || !root?.isConnected || excluded(root) || pending.has(root)) return;
    const raw = root.innerText || root.textContent || "";
    if (!hasPlaceholder(raw)) return;
    const protectedText = canonical(raw);
    const current = views.get(root);
    if (current?.protectedText === protectedText && current.restoredText) return;

    pending.add(root);
    chrome.runtime.sendMessage({ type: "PG_RESTORE", text: protectedText }, response => {
      pending.delete(root);
      if (chrome.runtime.lastError || !response?.ok || !root.isConnected || !enabled) return;
      const restoredText = response.data?.restored_text;
      if (typeof restoredText !== "string" || !restoredText || restoredText === protectedText) return;
      if (canonical(root.innerText || root.textContent || "") !== protectedText) {
        schedule(80);
        return;
      }
      const state = ensureFrame(root);
      state.protectedText = protectedText;
      state.restoredText = restoredText;
      sendToFrame(state.frame, restoredText);
    });
  }

  function scan() {
    if (!enabled) return;
    for (const [root, state] of Array.from(views.entries())) {
      if (!root.isConnected || !state.frame?.isConnected) {
        state.frame?.remove();
        views.delete(root);
      }
    }

    const walker = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_TEXT);
    const roots = new Set();
    let node = walker.nextNode();
    while (node) {
      if (hasPlaceholder(node.nodeValue || "")) {
        const root = rootForTextNode(node);
        if (root && !excluded(root)) roots.add(root);
      }
      node = walker.nextNode();
    }
    roots.forEach(restoreRoot);
  }

  function schedule(delay = 120) {
    clearTimeout(timer);
    timer = setTimeout(scan, delay);
  }

  new MutationObserver(() => schedule()).observe(document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true
  });

  chrome.storage.local.get({ [STORAGE_KEY]: true }, values => {
    enabled = values?.[STORAGE_KEY] !== false;
    schedule(0);
  });
  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName !== "local" || !changes[STORAGE_KEY]) return;
    enabled = changes[STORAGE_KEY].newValue !== false;
    if (!enabled) {
      for (const state of views.values()) state.frame?.remove();
      views.clear();
    } else {
      schedule(0);
    }
  });
})();
