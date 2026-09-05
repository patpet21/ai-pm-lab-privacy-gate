(() => {
  "use strict";

  const STORAGE_KEY = "privacygateConversationSessionsV1";
  const MAX_ENTRIES = 96;
  const SESSION_ID_RE = /^[a-f0-9]{32}$/;
  const SUPPORTED_PROVIDERS = new Set(["chatgpt", "gemini", "claude"]);

  // Persist only the opaque conversation -> local session id association.
  // No PII, prompt text, mappings, document content, or restored values are
  // stored here. chrome.storage.local survives extension reloads/updates so a
  // refresh can reconnect to a still-live desktop RAM session. Stale ids are
  // rejected by the local Bridge and cleared by background.js.
  function store() {
    return chrome.storage.local;
  }

  function validSessionId(value) {
    return typeof value === "string" && SESSION_ID_RE.test(value);
  }

  function providerFromUrl(rawUrl) {
    try {
      const hostname = new URL(String(rawUrl || "")).hostname.toLowerCase();

      if (hostname === "chatgpt.com" || hostname.endsWith(".chatgpt.com")) {
        return "chatgpt";
      }
      if (hostname === "gemini.google.com") {
        return "gemini";
      }
      if (hostname === "claude.ai" || hostname.endsWith(".claude.ai")) {
        return "claude";
      }
      return null;
    } catch (_error) {
      return null;
    }
  }

  function extractConversationId(rawUrl) {
    try {
      const url = new URL(String(rawUrl || ""));
      const provider = providerFromUrl(url.href);

      if (provider === "chatgpt") {
        return url.pathname.match(/(?:^|\/)c\/([^/?#]+)/i)?.[1] || null;
      }

      if (provider === "gemini") {
        return url.pathname.match(/(?:^|\/)app\/([^/?#]+)/i)?.[1] || null;
      }

      if (provider === "claude") {
        return url.pathname.match(/(?:^|\/)chat\/([^/?#]+)/i)?.[1] || null;
      }

      return null;
    } catch (_error) {
      return null;
    }
  }

  function senderContext(sender) {
    const tabId = Number.isInteger(sender?.tab?.id) ? sender.tab.id : null;
    const rawUrl = sender?.url || sender?.tab?.url || "";
    const provider = providerFromUrl(rawUrl);
    const conversationId = extractConversationId(rawUrl);

    return {
      tabId,
      provider,
      conversationId,
      conversationKey:
        provider && conversationId
          ? `${provider}:conversation:${conversationId}`
          : null,
      draftKey:
        provider && tabId !== null
          ? `${provider}:tab:${tabId}:draft`
          : null
    };
  }

  async function loadEntries() {
    const values = await store().get(STORAGE_KEY);
    const raw = values?.[STORAGE_KEY];
    const entries = {};

    if (!raw || typeof raw !== "object" || Array.isArray(raw)) return entries;

    for (const [key, value] of Object.entries(raw)) {
      const sessionId = value?.sessionId;
      const updatedAt = Number(value?.updatedAt || 0);

      if (validSessionId(sessionId)) {
        entries[key] = {
          sessionId,
          updatedAt:
            Number.isFinite(updatedAt) && updatedAt > 0
              ? updatedAt
              : Date.now()
        };
      }
    }

    return entries;
  }

  async function saveEntries(entries) {
    const sorted = Object.entries(entries)
      .filter(([, value]) => validSessionId(value?.sessionId))
      .sort((a, b) => Number(b[1]?.updatedAt || 0) - Number(a[1]?.updatedAt || 0))
      .slice(0, MAX_ENTRIES);

    await store().set({ [STORAGE_KEY]: Object.fromEntries(sorted) });
  }

  function legacyChatGptConversationKey(context) {
    if (
      context.provider !== "chatgpt" ||
      !context.conversationId
    ) {
      return null;
    }

    return `chatgpt:c:${context.conversationId}`;
  }

  async function getSessionForSender(sender) {
    const context = senderContext(sender);
    const entries = await loadEntries();

    // Migrate the pre-v1 ChatGPT conversation key without losing an active
    // local restore session.
    const legacyKey = legacyChatGptConversationKey(context);
    if (
      context.conversationKey &&
      legacyKey &&
      !entries[context.conversationKey] &&
      entries[legacyKey]
    ) {
      entries[context.conversationKey] = {
        ...entries[legacyKey],
        updatedAt: Date.now()
      };
      delete entries[legacyKey];
      await saveEntries(entries);
    }

    if (context.conversationKey && entries[context.conversationKey]) {
      entries[context.conversationKey].updatedAt = Date.now();
      await saveEntries(entries);
      return entries[context.conversationKey].sessionId;
    }

    // A brand-new conversation may not receive its permanent URL until the
    // first message is accepted. Migrate the tab-scoped draft as soon as the
    // provider exposes a conversation id.
    if (
      context.conversationKey &&
      context.draftKey &&
      entries[context.draftKey]
    ) {
      const migrated = {
        ...entries[context.draftKey],
        updatedAt: Date.now()
      };

      entries[context.conversationKey] = migrated;
      delete entries[context.draftKey];
      await saveEntries(entries);
      return migrated.sessionId;
    }

    if (context.draftKey && entries[context.draftKey]) {
      entries[context.draftKey].updatedAt = Date.now();
      await saveEntries(entries);
      return entries[context.draftKey].sessionId;
    }

    return null;
  }

  async function setSessionForSender(sender, sessionId) {
    if (!validSessionId(sessionId)) return false;

    const context = senderContext(sender);
    const targetKey = context.conversationKey || context.draftKey;
    if (!targetKey) return false;

    const entries = await loadEntries();
    entries[targetKey] = {
      sessionId,
      updatedAt: Date.now()
    };

    if (context.conversationKey && context.draftKey) {
      delete entries[context.draftKey];
    }

    const legacyKey = legacyChatGptConversationKey(context);
    if (legacyKey) delete entries[legacyKey];

    await saveEntries(entries);
    return true;
  }

  async function clearSessionForSender(sender) {
    const context = senderContext(sender);
    const entries = await loadEntries();
    let changed = false;

    const keys = [
      context.conversationKey,
      context.draftKey,
      legacyChatGptConversationKey(context)
    ];

    for (const key of keys) {
      if (key && entries[key]) {
        delete entries[key];
        changed = true;
      }
    }

    if (changed) await saveEntries(entries);
    return changed;
  }

  async function clearDraftForTab(tabId) {
    if (!Number.isInteger(tabId)) return false;

    const entries = await loadEntries();
    let changed = false;

    for (const provider of SUPPORTED_PROVIDERS) {
      const key = `${provider}:tab:${tabId}:draft`;
      if (entries[key]) {
        delete entries[key];
        changed = true;
      }
    }

    const legacyKey = `chatgpt:tab:${tabId}:draft`;
    if (entries[legacyKey]) {
      delete entries[legacyKey];
      changed = true;
    }

    if (changed) await saveEntries(entries);
    return changed;
  }

  async function clearAll() {
    await store().remove(STORAGE_KEY);
  }

  globalThis.PrivacyGateSessionRegistry = Object.freeze({
    providerFromUrl,
    extractConversationId,
    senderContext,
    getSessionForSender,
    setSessionForSender,
    clearSessionForSender,
    clearDraftForTab,
    clearAll
  });
})();
