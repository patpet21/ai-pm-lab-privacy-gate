(() => {
  "use strict";

  if (window.top !== window || location.hostname.toLowerCase() !== "gemini.google.com") return;

  const STORAGE_KEY = "privacygateProtectionEnabled";
  const FRAME_CLASS = "privacygate-secure-restore-frame";
  const OVERLAY_SOURCE = "privacygate-secure-restore";
  const TOKEN_RE = /\[\[PG(?:_[A-Z0-9]+)+\]\]/g;
  const TOKEN_FRAGMENT_RE = /\[\[\s*PG[\s\S]{0,220}?\]\]/g;
  const views = new Map();
  const pending = new WeakMap();
  const retryAfter = new WeakMap();
  let enabled = true;
  let timer = null;

  function canonical(text) {
    const cleaned = String(text || "").replace(/[\u200B-\u200D\u2060\uFEFF]/g, "");
    return cleaned.replace(TOKEN_FRAGMENT_RE, fragment =>
      fragment.replace(/\\_/g, "_").replace(/\s+/g, "")
    );
  }

  function hasToken(text) {
    TOKEN_RE.lastIndex = 0;
    return TOKEN_RE.test(canonical(text));
  }

  function textOf(element) {
    return element instanceof Element ? (element.innerText || element.textContent || "") : "";
  }

  function candidates() {
    const result = [];
    const seen = new Set();

    document.querySelectorAll("model-response").forEach(model => {
      if (!(model instanceof Element) || seen.has(model)) return;
      const protectedText = canonical(textOf(model));
      if (!hasToken(protectedText)) return;
      seen.add(model);
      result.push({ root: model, content: model, anchor: model, protectedText });
    });

    // Gemini experiments occasionally omit the model-response custom element.
    // In that case inspect only response-shaped containers and explicitly reject
    // anything inside user-query/composer surfaces.
    document.querySelectorAll(
      "message-content, .model-response-text, .response-content, [class*='response-content' i]"
    ).forEach(content => {
      if (!(content instanceof Element)) return;
      if (content.closest("user-query, .user-query, .query-text, form, rich-textarea")) return;
      const root = content.closest("model-response") || content;
      if (seen.has(root)) return;
      const protectedText = canonical(textOf(root));
      if (!hasToken(protectedText)) return;
      seen.add(root);
      result.push({ root, content: root, anchor: root, protectedText });
    });

    return result;
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

    // Reuse an adjacent PrivacyGate frame if a previous scan already created it.
    const adjacent = anchor.nextElementSibling;
    if (adjacent instanceof HTMLIFrameElement && adjacent.classList.contains(FRAME_CLASS)) {
      state = { frame: adjacent, protectedText: "", restoredText: "" };
      views.set(root, state);
      return state;
    }

    const frame = document.createElement("iframe");
    frame.className = FRAME_CLASS;
    frame.dataset.pgProviderRestore = "gemini";
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
    if (!enabled || !candidate?.root?.isConnected) return;
    const { root } = candidate;
    const protectedText = canonical(textOf(root));
    if (!hasToken(protectedText)) {
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
        retryAfter.set(root, Date.now() + 2200);
        return;
      }
      const restoredText = response.data?.restored_text;
      if (typeof restoredText !== "string" || !restoredText || restoredText === protectedText) {
        retryAfter.set(root, Date.now() + 2200);
        return;
      }
      if (canonical(textOf(root)) !== protectedText) {
        schedule(100);
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
  }, 1300);
})();
