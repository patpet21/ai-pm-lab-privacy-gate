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
  const pending = new WeakMap();
  const retryAfter = new WeakMap();
  let enabled = true;
  let timer = null;

  function canonical(text) {
    return String(text || "")
      .replace(/[\u200B-\u200D\uFEFF]/g, "")
      .replace(PLACEHOLDER_RE, token => token.replace(/\\_/g, "_"));
  }

  function hasPlaceholder(text) {
    PLACEHOLDER_RE.lastIndex = 0;
    return PLACEHOLDER_RE.test(canonical(text));
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
    if (box && (element === box || element.contains(box) || box.contains(element))) return true;
    return Boolean(element.closest?.(
      '#privacygate-freev1-bar, #privacygate-multi-ai-stable-bar, #privacygate-freev1-review, ' +
      '#privacygate-freev1-checking, #privacygate-freev1-notice, #privacygate-document-review, ' +
      '#privacygate-document-working, .' + FRAME_CLASS
    ));
  }

  function textOf(element) {
    return element instanceof Element ? (element.innerText || element.textContent || "") : "";
  }

  function seedNodes() {
    const root = document.querySelector("main") || document.body || document.documentElement;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    let node = walker.nextNode();
    while (node) {
      const value = String(node.nodeValue || "");
      if (value.includes("[[PG") || value.includes("PG_")) nodes.push(node);
      node = walker.nextNode();
    }
    return nodes;
  }

  function smallestPlaceholderRoot(node) {
    let current = node?.parentElement || null;
    let fallback = null;
    for (let depth = 0; depth < 10 && current && current !== document.body; depth += 1) {
      if (!excluded(current) && hasPlaceholder(textOf(current))) {
        fallback = current;
        const tag = current.tagName?.toLowerCase();
        if (["p", "li", "pre", "blockquote", "code"].includes(tag)) return current;
        if (current.matches?.('model-response, message-content, article, [data-testid*="assistant" i], [data-testid*="response" i], [class*="response" i]')) {
          return current;
        }
      }
      current = current.parentElement;
    }
    return fallback;
  }

  function candidateRoots() {
    const roots = [];
    const seen = new Set();
    for (const node of seedNodes()) {
      const root = smallestPlaceholderRoot(node);
      if (!root || seen.has(root) || excluded(root)) continue;
      seen.add(root);
      roots.push(root);
    }

    // Remove broad ancestors when a smaller matching descendant is available.
    return roots.filter(root => !roots.some(other => other !== root && root.contains(other) && hasPlaceholder(textOf(other))));
  }

  function anchorFor(root) {
    if (host === "gemini.google.com") {
      return root.closest?.('model-response, message-content, article, [class*="model-response" i]') || root;
    }
    return root.closest?.('[data-testid*="assistant" i], [data-testid*="message" i], article, [class*="assistant" i], [class*="response" i]') || root;
  }

  function estimatedHeight(root) {
    const height = Number(root?.getBoundingClientRect?.().height || 0);
    if (!Number.isFinite(height) || height <= 0) return 150;
    return Math.max(92, Math.min(Math.ceil(height + 54), 2400));
  }

  function sendToFrame(frame, text) {
    if (!frame?.contentWindow || typeof text !== "string") return;
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
      display: "block", width: "100%", minHeight: "92px", height: `${estimatedHeight(root)}px`,
      margin: "10px 0 14px", border: "0", borderRadius: "14px", background: "transparent",
      overflow: "hidden", overflowAnchor: "none"
    });

    const anchor = anchorFor(root);
    anchor.insertAdjacentElement?.("afterend", frame);
    if (!frame.isConnected && anchor.parentElement) anchor.parentElement.insertBefore(frame, anchor.nextSibling);

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
    const protectedText = canonical(textOf(root));
    if (!hasPlaceholder(protectedText)) {
      removeView(root);
      return;
    }
    const current = views.get(root);
    if (current?.protectedText === protectedText && current.restoredText) return;
    if (pending.get(root) === protectedText) return;
    if (Number(retryAfter.get(root) || 0) > Date.now()) return;

    pending.set(root, protectedText);
    chrome.runtime.sendMessage({ type: "PG_RESTORE", text: protectedText }, response => {
      if (pending.get(root) === protectedText) pending.delete(root);
      if (chrome.runtime.lastError || !response?.ok || !root.isConnected || !enabled) {
        retryAfter.set(root, Date.now() + 3000);
        return;
      }
      const restoredText = response.data?.restored_text;
      if (typeof restoredText !== "string" || !restoredText || restoredText === protectedText) {
        retryAfter.set(root, Date.now() + 3000);
        return;
      }
      if (canonical(textOf(root)) !== protectedText) {
        schedule(80);
        return;
      }
      retryAfter.delete(root);
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
    clearTimeout(timer);
    timer = setTimeout(() => {
      timer = null;
      scan();
    }, delay);
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
    if (enabled) schedule(100);
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
  }, 1600);
})();