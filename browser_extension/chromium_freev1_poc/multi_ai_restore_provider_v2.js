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

  function textOf(element) {
    return element instanceof Element ? (element.innerText || element.textContent || "") : "";
  }

  function isInsidePrivacyGate(element) {
    return Boolean(element?.closest?.(
      '[id^="privacygate-"], .' + FRAME_CLASS + ', .privacygate-response-status'
    ));
  }

  function isUserContent(element) {
    if (!(element instanceof Element)) return false;
    if (host === "claude.ai") {
      return Boolean(
        element.matches?.('[data-testid="user-message"], [data-user-message-bubble="true"], .font-user-message') ||
        element.closest?.('[data-testid="user-message"], [data-user-message-bubble="true"], .font-user-message')
      );
    }
    return Boolean(
      element.matches?.('user-query, .user-query, .query-text, [data-testid="user-message"]') ||
      element.closest?.('user-query, .user-query, .query-text, [data-testid="user-message"]')
    );
  }

  function pushCandidate(result, seen, root, content, anchor = root) {
    if (!(root instanceof Element) || !(content instanceof Element)) return;
    if (!root.isConnected || !content.isConnected || seen.has(root)) return;
    if (isInsidePrivacyGate(content) || isUserContent(content)) return;
    const protectedText = canonical(textOf(content));
    if (!hasPlaceholder(protectedText)) return;
    seen.add(root);
    result.push({ root, content, anchor, protectedText });
  }

  function claudeCandidates() {
    const result = [];
    const seen = new Set();

    // Prefer assistant response elements directly. Do not reject the entire outer
    // turn merely because it also contains the user's preceding message.
    document.querySelectorAll(
      '.font-claude-response, [data-testid="ai-message"], [data-testid="message-assistant"], .assistant-message'
    ).forEach(content => {
      if (!(content instanceof Element) || isUserContent(content)) return;
      const root =
        content.closest('[data-test-render-count]') ||
        content.closest('article') ||
        content;
      pushCandidate(result, seen, root, content, root);
    });

    // Current Claude variants can split one assistant answer across progressive /
    // standard markdown blocks. Resolve the containing assistant response when it
    // exists, otherwise restore the token-bearing block itself.
    document.querySelectorAll('.standard-markdown, .progressive-markdown, [data-is-streaming]').forEach(block => {
      if (!(block instanceof Element) || isUserContent(block)) return;
      const content = block.closest('.font-claude-response') || block;
      const root =
        content.closest('[data-test-render-count]') ||
        content.closest('article') ||
        content;
      pushCandidate(result, seen, root, content, root);
    });

    return result;
  }

  function geminiCandidates() {
    const result = [];
    const seen = new Set();

    document.querySelectorAll('model-response').forEach(model => {
      if (!(model instanceof Element)) return;
      const content =
        model.querySelector('message-content') ||
        model.querySelector('.model-response-text, .response-content, [class*="response-content" i]') ||
        model;
      pushCandidate(result, seen, model, content, model);
    });

    document.querySelectorAll('message-content, .model-response-text, .response-content').forEach(content => {
      if (!(content instanceof Element) || isUserContent(content)) return;
      const root = content.closest('model-response') || content;
      pushCandidate(result, seen, root, content, root);
    });

    return result;
  }

  function genericTokenCandidates(existing) {
    const result = [];
    const seen = new Set(existing.map(item => item.root));
    const walker = document.createTreeWalker(
      document.body || document.documentElement,
      NodeFilter.SHOW_TEXT
    );
    let node;
    while ((node = walker.nextNode())) {
      const value = String(node.nodeValue || "");
      if (!value.includes("[[PG")) continue;
      const leaf = node.parentElement;
      if (!(leaf instanceof Element) || isInsidePrivacyGate(leaf) || isUserContent(leaf)) continue;

      let content;
      let root;
      if (host === "claude.ai") {
        content =
          leaf.closest('.font-claude-response, [data-testid="ai-message"], [data-testid="message-assistant"], .assistant-message') ||
          leaf.closest('.standard-markdown, .progressive-markdown') ||
          leaf;
        root =
          content.closest('[data-test-render-count]') ||
          content.closest('article') ||
          content;
      } else {
        content =
          leaf.closest('message-content, .model-response-text, .response-content') ||
          leaf.closest('model-response') ||
          leaf;
        root = content.closest('model-response') || content;
      }
      pushCandidate(result, seen, root, content, root);
    }
    return result;
  }

  function candidates() {
    const primary = host === "claude.ai" ? claudeCandidates() : geminiCandidates();
    return primary.concat(genericTokenCandidates(primary));
  }

  function estimatedHeight(content) {
    const height = Number(content?.getBoundingClientRect?.().height || 0);
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

  function ensureFrame(candidate) {
    const { root, anchor, content } = candidate;
    let state = views.get(root);
    if (state?.frame?.isConnected) return state;

    const frame = document.createElement("iframe");
    frame.className = FRAME_CLASS;
    frame.dataset.pgProviderRestore = host === "claude.ai" ? "claude" : "gemini";
    frame.src = chrome.runtime.getURL("multi_ai_restore_overlay.html");
    frame.title = "PrivacyGate local restored view";
    frame.setAttribute("aria-label", "PrivacyGate local restored view");
    frame.referrerPolicy = "no-referrer";
    Object.assign(frame.style, {
      display: "block",
      width: "100%",
      minHeight: "92px",
      height: `${estimatedHeight(content)}px`,
      margin: "10px 0 14px",
      border: "0",
      borderRadius: "14px",
      background: "transparent",
      overflow: "hidden",
      overflowAnchor: "none"
    });

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

  function restoreCandidate(candidate) {
    if (!enabled || !candidate?.root?.isConnected || !candidate?.content?.isConnected) return;
    const { root } = candidate;
    const protectedText = canonical(textOf(candidate.content));
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
        retryAfter.set(root, Date.now() + 1800);
        return;
      }
      const restoredText = response.data?.restored_text;
      if (typeof restoredText !== "string" || !restoredText || restoredText === protectedText) {
        retryAfter.set(root, Date.now() + 1800);
        return;
      }
      if (canonical(textOf(candidate.content)) !== protectedText) {
        schedule(90);
        return;
      }
      retryAfter.delete(root);
      const state = ensureFrame(candidate);
      state.protectedText = protectedText;
      state.restoredText = restoredText;
      sendToFrame(state.frame, restoredText);
    });
  }

  function cleanup(activeRoots) {
    for (const [root, state] of Array.from(views.entries())) {
      if (!enabled || !root.isConnected || !state.frame?.isConnected || !activeRoots.has(root)) {
        removeView(root);
      }
    }
  }

  function scan() {
    if (!enabled) return;
    const items = candidates();
    const activeRoots = new Set(items.map(item => item.root));
    cleanup(activeRoots);
    items.forEach(restoreCandidate);
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

  document.querySelectorAll?.(`iframe.${FRAME_CLASS}`).forEach(frame => frame.remove());

  const observer = new MutationObserver(mutations => {
    const meaningful = mutations.some(mutation => {
      if (mutation.target instanceof Element && mutation.target.closest?.(`.${FRAME_CLASS}`)) return false;
      return mutation.type === "characterData" ||
        Array.from(mutation.addedNodes || []).some(node => !(node instanceof Element && node.classList?.contains(FRAME_CLASS)));
    });
    if (meaningful) schedule(110);
  });
  observer.observe(document.documentElement, { childList: true, subtree: true, characterData: true });

  chrome.storage.local.get({ [STORAGE_KEY]: true }, values => {
    enabled = values?.[STORAGE_KEY] !== false;
    if (enabled) schedule(80);
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
    if (enabled) scan();
  }, 1200);
})();
