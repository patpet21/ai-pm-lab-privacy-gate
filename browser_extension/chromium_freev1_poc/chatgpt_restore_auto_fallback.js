(() => {
  "use strict";

  if (window.top !== window || location.hostname.toLowerCase() !== "chatgpt.com") return;

  const STORAGE_KEY = "privacygateProtectionEnabled";
  const FRAME_CLASS = "privacygate-secure-restore-frame";
  const FALLBACK_CLASS = "privacygate-auto-restore-frame";
  const OVERLAY_SOURCE = "privacygate-secure-restore";
  const PLACEHOLDER_RE = /\[\[PG(?:\\?_[A-Z0-9]+)+\]\]/g;
  const pending = new WeakSet();
  const restoredByRoot = new WeakMap();
  let enabled = true;

  function canonical(text) {
    return String(text || "")
      .replace(/[\u200B-\u200D\uFEFF]/g, "")
      .replace(PLACEHOLDER_RE, token => token.replace(/\\_/g, "_"));
  }

  function hasPlaceholder(text) {
    PLACEHOLDER_RE.lastIndex = 0;
    return PLACEHOLDER_RE.test(canonical(text));
  }

  function existingRestoreNear(root) {
    const parent = root?.parentElement;
    if (!parent) return false;
    if (root.querySelector?.(`.${FRAME_CLASS}, .${FALLBACK_CLASS}`)) return true;
    const siblings = Array.from(parent.children || []);
    const index = siblings.indexOf(root);
    return siblings.slice(Math.max(0, index - 1), index + 3).some(node =>
      node instanceof Element &&
      (node.classList.contains(FRAME_CLASS) || node.classList.contains(FALLBACK_CLASS))
    );
  }

  function sendToFrame(frame, text) {
    if (!frame?.contentWindow) return;
    frame.contentWindow.postMessage(
      { source: OVERLAY_SOURCE, type: "PG_RENDER_RESTORED_TEXT", text },
      new URL(chrome.runtime.getURL("/")).origin
    );
  }

  function mount(root, restoredText) {
    if (!root?.isConnected || existingRestoreNear(root)) return;
    const frame = document.createElement("iframe");
    frame.className = `${FRAME_CLASS} ${FALLBACK_CLASS}`;
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
      overflow: "hidden",
      overflowAnchor: "none"
    });
    root.insertAdjacentElement("afterend", frame);
    if (!frame.isConnected && root.parentElement) {
      root.parentElement.insertBefore(frame, root.nextSibling);
    }
    frame.addEventListener("load", () => sendToFrame(frame, restoredText));
    setTimeout(() => sendToFrame(frame, restoredText), 120);
  }

  function tryRestore(root) {
    if (!enabled || !root?.isConnected || pending.has(root) || existingRestoreNear(root)) return;
    const text = canonical(root.innerText || root.textContent || "");
    if (!hasPlaceholder(text)) return;
    if (restoredByRoot.get(root) === text) return;

    // Give the normal per-conversation restore guard first chance. This fallback
    // exists only for tokens that belong to a previously persisted local session.
    pending.add(root);
    setTimeout(() => {
      if (!root.isConnected || !enabled || existingRestoreNear(root)) {
        pending.delete(root);
        return;
      }
      chrome.runtime.sendMessage({ type: "PG_RESTORE_AUTO", text }, response => {
        pending.delete(root);
        if (chrome.runtime.lastError || !response?.ok || !root.isConnected || !enabled) return;
        const restoredText = response.data?.restored_text;
        if (typeof restoredText !== "string" || !restoredText || restoredText === text) return;
        if (canonical(root.innerText || root.textContent || "") !== text) return;
        restoredByRoot.set(root, text);
        mount(root, restoredText);
      });
    }, 650);
  }

  function scan() {
    if (!enabled) return;
    const roots = Array.from(document.querySelectorAll('[data-message-author-role="assistant"]'));
    roots.forEach(root => {
      if (hasPlaceholder(root.innerText || root.textContent || "")) tryRestore(root);
    });
  }

  window.addEventListener("message", event => {
    const frame = Array.from(document.querySelectorAll(`.${FALLBACK_CLASS}`))
      .find(item => item.contentWindow === event.source);
    if (!frame) return;
    const data = event.data;
    if (!data || data.source !== OVERLAY_SOURCE || data.type !== "PG_OVERLAY_HEIGHT") return;
    const height = Math.max(72, Math.min(Number(data.height || 0), 2400));
    if (Number.isFinite(height) && height > 0) frame.style.height = `${Math.ceil(height)}px`;
  });

  chrome.storage.local.get({ [STORAGE_KEY]: true }, values => {
    enabled = values?.[STORAGE_KEY] !== false;
    if (enabled) setTimeout(scan, 300);
  });
  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName !== "local" || !changes[STORAGE_KEY]) return;
    enabled = changes[STORAGE_KEY].newValue !== false;
    if (!enabled) {
      document.querySelectorAll(`.${FALLBACK_CLASS}`).forEach(frame => frame.remove());
    } else {
      scan();
    }
  });

  setInterval(scan, 1200);
})();
