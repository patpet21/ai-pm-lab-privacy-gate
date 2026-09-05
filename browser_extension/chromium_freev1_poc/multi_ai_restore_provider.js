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

  function isClaudeUser(element) {
    if (!(element instanceof Element)) return false;
    return Boolean(
      element.matches?.('[data-testid="user-message"], [data-user-message-bubble="true"], .font-user-message') ||
      element.closest?.('[data-testid="user-message"], [data-user-message-bubble="true"], .font-user-message') ||
      element.querySelector?.('[data-testid="user-message"], [data-user-message-bubble="true"], .font-user-message')
    );
  }

  function claudeCandidates() {
    const result = [];
    const seen = new Set();

    // Current Claude UI groups each turn in a data-test-render-count container.
    // User turns expose data-testid="user-message" / data-user-message-bubble;
    // assistant turns expose a font-claude-response (possibly containing several
    // standard/progressive markdown blocks). Work at the whole assistant response
    // level so one model turn always produces exactly one local restored view.
    document.querySelectorAll('[data-test-render-count]').forEach(turn => {
      if (!(turn instanceof Element) || isClaudeUser(turn)) return;
      const content =
        turn.querySelector('.font-claude-response') ||
        turn.querySelector('[data-testid="ai-message"], [data-testid="message-assistant"]') ||
        turn.querySelector('[data-is-streaming]') ||
        turn.querySelector('.standard-markdown, .progressive-markdown');
      if (!(content instanceof Element)) return;
      const protectedText = canonical(textOf(content));
      if (!hasPlaceholder(protectedText) || seen.has(turn)) return;
      seen.add(turn);
      result.push({ root: turn, content, anchor: turn, protectedText });
    });

    // Fallback for Claude variants where the outer turn attribute is absent.
    document.querySelectorAll(
      '.font-claude-response, [data-testid="ai-message"], [data-testid="message-assistant"], .assistant-message'
    ).forEach(content => {
      if (!(content instanceof Element) || isClaudeUser(content)) return;
      const root = content.closest('[data-test-render-count]') || content;
      if (seen.has(root) || isClaudeUser(root)) return;
      const protectedText = canonical(textOf(content));
      if (!hasPlaceholder(protectedText)) return;
      seen.add(root);
      result.push({ root, content, anchor: root, protectedText });
    });

    return result;
  }

  function geminiCandidates() {
    const result = [];
    const seen = new Set();

    // Gemini exposes semantic Angular custom elements: user-query for the user
    // and model-response for Gemini. Never inspect user-query. The model-response
    // node is the durable unit even when each token lives in a different <p>.
    document.querySelectorAll('model-response').forEach(model => {
      if (!(model instanceof Element) || seen.has(model)) return;
      const content =
        model.querySelector('message-content') ||
        model.querySelector('.model-response-text, .response-content, [class*="response-content" i]') ||
        model;
      const protectedText = canonical(textOf(content));
      if (!hasPlaceholder(protectedText)) return;
      seen.add(model);
      result.push({ root: model, content, anchor: model, protectedText });
    });

    // Fallback for experiments where model-response is not present.
    document.querySelectorAll('message-content, .model-response-text, .response-content').forEach(content => {
      if (!(content instanceof Element)) return;
      if (content.closest('user-query, .user-query, .query-text')) return;
      const root = content.closest('model-response') || content;
      if (seen.has(root)) return;
      const protectedText = canonical(textOf(content));
      if (!hasPlaceholder(protectedText)) return;
      seen.add(root);
      result.push({ root, content, anchor: root, protectedText });
    });

    return result;
  }

  function candidates() {
    return host === "claude.ai" ? claudeCandidates() : geminiCandidates();
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
        retryAfter.set(root, Date.now() + 2500);
        return;
      }
      const restoredText = response.data?.restored_text;
      if (typeof restoredText !== "string" || !restoredText || restoredText === protectedText) {
        retryAfter.set(root, Date.now() + 2500);
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

  // Remove all frames produced by older multi-AI restore builds. New frames are
  // recreated only for actual assistant/model response containers.
  document.querySelectorAll?.(`iframe.${FRAME_CLASS}`).forEach(frame => frame.remove());

  const observer = new MutationObserver(mutations => {
    const meaningful = mutations.some(mutation => {
      if (mutation.target instanceof Element && mutation.target.closest?.(`.${FRAME_CLASS}`)) return false;
      return mutation.type === "characterData" ||
        Array.from(mutation.addedNodes || []).some(node => !(node instanceof Element && node.classList?.contains(FRAME_CLASS)));
    });
    if (meaningful) schedule(130);
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
  }, 1400);
})();
