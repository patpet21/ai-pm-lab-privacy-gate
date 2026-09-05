(() => {
  "use strict";

  if (window.top !== window) return;
  const host = location.hostname.toLowerCase();
  if (!new Set(["chatgpt.com", "claude.ai", "gemini.google.com"]).has(host)) return;

  const STORAGE_KEY = "privacygateProtectionEnabled";
  const STATUS_CLASS = "privacygate-response-status";
  const RESTORE_FRAME_CLASS = "privacygate-secure-restore-frame";
  const PLACEHOLDER_RE = /\[\[PG(?:\\?_[A-Z0-9]+)+\]\]/;
  let enabled = true;
  let awaiting = false;
  let baselineRoot = null;
  let candidateRoot = null;
  let settleTimer = null;
  let expiresTimer = null;

  function textOf(element) {
    return element instanceof Element ? (element.innerText || element.textContent || "") : "";
  }

  function hasPlaceholder(text) {
    return PLACEHOLDER_RE.test(String(text || "").replace(/[\u200B-\u200D\uFEFF]/g, ""));
  }

  function chatGptLatest() {
    const items = Array.from(document.querySelectorAll('[data-message-author-role="assistant"]'));
    return items.at(-1) || null;
  }

  function claudeLatest() {
    const turns = Array.from(document.querySelectorAll('[data-test-render-count]')).filter(turn => {
      if (!(turn instanceof Element)) return false;
      if (turn.matches?.('[data-testid="user-message"], [data-user-message-bubble="true"]')) return false;
      if (turn.querySelector?.('[data-testid="user-message"], [data-user-message-bubble="true"]')) return false;
      return Boolean(
        turn.querySelector?.('.font-claude-response, [data-testid="ai-message"], [data-testid="message-assistant"], .standard-markdown, .progressive-markdown')
      );
    });
    if (turns.length) return turns.at(-1);
    const fallback = Array.from(document.querySelectorAll('.font-claude-response, [data-testid="ai-message"], [data-testid="message-assistant"]'));
    return fallback.at(-1) || null;
  }

  function geminiLatest() {
    const models = Array.from(document.querySelectorAll('model-response'));
    if (models.length) return models.at(-1);
    const fallback = Array.from(document.querySelectorAll('message-content, .model-response-text, .response-content'))
      .filter(item => !item.closest?.('user-query, .user-query, .query-text'));
    return fallback.at(-1) || null;
  }

  function latestResponseRoot() {
    if (host === "chatgpt.com") return chatGptLatest();
    if (host === "claude.ai") return claudeLatest();
    return geminiLatest();
  }

  function restoreExistsNear(root) {
    if (!(root instanceof Element)) return false;
    if (root.querySelector?.(`.${RESTORE_FRAME_CLASS}`)) return true;
    const parent = root.parentElement;
    if (!parent) return false;
    const siblings = Array.from(parent.children || []);
    const index = siblings.indexOf(root);
    return siblings.slice(Math.max(0, index - 1), index + 3).some(node =>
      node instanceof Element && node.classList.contains(RESTORE_FRAME_CLASS)
    );
  }

  function statusExistsNear(root) {
    if (!(root instanceof Element)) return false;
    if (root.querySelector?.(`.${STATUS_CLASS}`)) return true;
    const next = root.nextElementSibling;
    return Boolean(next?.classList?.contains(STATUS_CLASS));
  }

  function mountStatus(root) {
    if (!enabled || !(root instanceof Element) || !root.isConnected || statusExistsNear(root) || restoreExistsNear(root)) return;
    const status = document.createElement("div");
    status.className = STATUS_CLASS;
    status.setAttribute("role", "status");
    Object.assign(status.style, {
      display: "block",
      boxSizing: "border-box",
      width: "100%",
      margin: "8px 0 14px",
      padding: "10px 12px",
      border: "1px solid #BFE8D2",
      borderRadius: "12px",
      background: "#F3FBF7",
      color: "#24523E",
      fontFamily: "Arial,sans-serif",
      fontSize: "12px",
      lineHeight: "1.45",
      fontWeight: "650"
    });
    const title = document.createElement("div");
    title.textContent = "● PRIVACYGATE · RESPONSE CHECKED";
    Object.assign(title.style, {
      color: "#138A52",
      fontSize: "10.5px",
      fontWeight: "850",
      letterSpacing: ".04em",
      marginBottom: "4px"
    });
    const body = document.createElement("div");
    body.textContent = "The AI response returned no PrivacyGate tokens, so no local replacements were needed.";
    status.append(title, body);

    const anchor = root.closest?.('[data-message-author-role="assistant"], [data-test-render-count], model-response') || root;
    anchor.insertAdjacentElement?.("afterend", status);
    if (!status.isConnected && anchor.parentElement) anchor.parentElement.insertBefore(status, anchor.nextSibling);
  }

  function finishAwaiting() {
    awaiting = false;
    baselineRoot = null;
    candidateRoot = null;
    clearTimeout(settleTimer);
    clearTimeout(expiresTimer);
    settleTimer = null;
    expiresTimer = null;
  }

  function evaluateCandidate() {
    if (!awaiting || !enabled || !(candidateRoot instanceof Element) || !candidateRoot.isConnected) return;
    const text = textOf(candidateRoot);
    if (!text.trim()) return;
    if (hasPlaceholder(text) || restoreExistsNear(candidateRoot)) {
      finishAwaiting();
      return;
    }
    mountStatus(candidateRoot);
    finishAwaiting();
  }

  function scheduleSettle() {
    clearTimeout(settleTimer);
    settleTimer = setTimeout(evaluateCandidate, 1800);
  }

  function scanForNewResponse() {
    if (!awaiting || !enabled) return;
    const latest = latestResponseRoot();
    if (!(latest instanceof Element) || latest === baselineRoot) return;
    if (candidateRoot !== latest) candidateRoot = latest;
    scheduleSettle();
  }

  function composer() {
    if (host === "chatgpt.com") return document.querySelector("#prompt-textarea") || document.querySelector('[contenteditable="true"]');
    if (host === "claude.ai") return document.querySelector('div.ProseMirror[contenteditable="true"], [contenteditable="true"][data-placeholder], textarea');
    return document.querySelector('rich-textarea [contenteditable="true"], .ql-editor[contenteditable="true"], textarea[aria-label*="prompt" i], textarea');
  }

  function isSendGesture(event) {
    const box = composer();
    if (!box) return false;
    if (event.type === "keydown") {
      return event.key === "Enter" && !event.shiftKey && !event.ctrlKey && !event.altKey && !event.metaKey &&
        (event.target === box || box.contains?.(event.target));
    }
    if (event.type === "submit") return event.target instanceof HTMLFormElement && event.target.contains(box);
    if (event.type === "click") {
      if (!(event.target instanceof Element)) return false;
      const button = event.target.closest('button,[role="button"]');
      if (!button) return false;
      const label = String(button.getAttribute("aria-label") || button.getAttribute("data-testid") || button.getAttribute("data-test-id") || "").toLowerCase();
      return /send|submit/.test(label) || button.matches('button[type="submit"]');
    }
    return false;
  }

  function beginAwaiting() {
    const attachmentState = globalThis.PrivacyGateAttachmentState;
    if (!attachmentState?.hasProtectedAttachment?.()) return;
    awaiting = true;
    baselineRoot = latestResponseRoot();
    candidateRoot = null;
    clearTimeout(expiresTimer);
    expiresTimer = setTimeout(finishAwaiting, 120000);
  }

  for (const type of ["keydown", "submit", "click"]) {
    document.addEventListener(type, event => {
      if (!enabled || !event.isTrusted || !isSendGesture(event)) return;
      beginAwaiting();
    }, true);
  }

  const observer = new MutationObserver(() => {
    if (awaiting) scanForNewResponse();
  });
  observer.observe(document.documentElement, { childList: true, subtree: true, characterData: true });

  chrome.storage.local.get({ [STORAGE_KEY]: true }, values => {
    enabled = values?.[STORAGE_KEY] !== false;
  });
  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName !== "local" || !changes[STORAGE_KEY]) return;
    enabled = changes[STORAGE_KEY].newValue !== false;
    if (!enabled) {
      finishAwaiting();
      document.querySelectorAll(`.${STATUS_CLASS}`).forEach(item => item.remove());
    }
  });
})();
