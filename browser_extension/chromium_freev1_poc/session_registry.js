(() => {
  "use strict";

  const STORAGE_KEY = "privacygateConversationSessionsV1";
  const MAX_ENTRIES = 144;
  const SESSION_ID_RE = /^[a-f0-9]{32}$/;
  const PROVIDERS = new Set(["chatgpt", "claude", "gemini"]);

  // Persist only opaque provider/conversation -> local session associations.
  // No PII, prompt text, mappings, or restored values are stored in the extension.
  function store() {
    return chrome.storage.local;
  }

  function validSessionId(value) {
    return typeof value === "string" && SESSION_ID_RE.test(value);
  }

  function providerForUrl(rawUrl) {
    try {
      const host = new URL(String(rawUrl || "")).hostname.toLowerCase();
      if (host === "chatgpt.com") return "chatgpt";
      if (host === "claude.ai") return "claude";
      if (host === "gemini.google.com") return "gemini";
    } catch (_error) {
      // Invalid/empty sender URL.
    }
    return null;
  }

  function extractConversationId(rawUrl) {
    try {
      const url = new URL(String(rawUrl || ""));
      const provider = providerForUrl(rawUrl);
      let match = null;
      if (provider === "chatgpt") {
        match = url.pathname.match(/(?:^|\/)c\/([^/?#]+)/i);
      } else if (provider === "claude") {
        match = url.pathname.match(/(?:^|\/)chat\/([^/?#]+)/i);
      } else if (provider === "gemini") {
        match = url.pathname.match(/(?:^|\/)app\/([^/?#]+)/i);
      }
      return match?.[1] || null;
    } catch (_error) {
      return null;
    }
  }

  function senderContext(sender) {
    const tabId = Number.isInteger(sender?.tab?.id) ? sender.tab.id : null;
    const rawUrl = sender?.url || sender?.tab?.url || "";
    const provider = providerForUrl(rawUrl);
    const conversationId = extractConversationId(rawUrl);
    return {
      tabId,
      provider,
      conversationId,
      conversationKey:
        provider && conversationId ? `${provider}:c:${conversationId}` : null,
      draftKey:
        provider && tabId !== null ? `${provider}:tab:${tabId}:draft` : null
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
          updatedAt: Number.isFinite(updatedAt) && updatedAt > 0 ? updatedAt : Date.now()
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

  async function getSessionForSender(sender) {
    const context = senderContext(sender);
    if (!context.provider) return null;
    const entries = await loadEntries();

    if (context.conversationKey && entries[context.conversationKey]) {
      entries[context.conversationKey].updatedAt = Date.now();
      await saveEntries(entries);
      return entries[context.conversationKey].sessionId;
    }

    // New conversations begin with a tab-scoped draft key. As soon as the AI
    // website assigns a permanent conversation URL, migrate that same local
    // mapping without exposing any sensitive values to chrome.storage.
    if (
      context.conversationKey &&
      context.draftKey &&
      entries[context.draftKey]
    ) {
      const migrated = { ...entries[context.draftKey], updatedAt: Date.now() };
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
    if (!context.provider || !targetKey) return false;

    const entries = await loadEntries();
    entries[targetKey] = { sessionId, updatedAt: Date.now() };
    if (context.conversationKey && context.draftKey) {
      delete entries[context.draftKey];
    }
    await saveEntries(entries);
    return true;
  }

  async function clearSessionForSender(sender) {
    const context = senderContext(sender);
    const entries = await loadEntries();
    let changed = false;
    for (const key of [context.conversationKey, context.draftKey]) {
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
    for (const provider of PROVIDERS) {
      const key = `${provider}:tab:${tabId}:draft`;
      if (entries[key]) {
        delete entries[key];
        changed = true;
      }
    }
    if (changed) await saveEntries(entries);
    return changed;
  }

  async function clearAll() {
    await store().remove(STORAGE_KEY);
  }

  globalThis.PrivacyGateSessionRegistry = Object.freeze({
    providerForUrl,
    extractConversationId,
    senderContext,
    getSessionForSender,
    setSessionForSender,
    clearSessionForSender,
    clearDraftForTab,
    clearAll
  });
})();
