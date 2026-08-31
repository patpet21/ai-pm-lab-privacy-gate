(() => {
  "use strict";

  const STORAGE_KEY = "privacygateConversationSessionsV1";
  const MAX_ENTRIES = 96;
  const SESSION_ID_RE = /^[a-f0-9]{32}$/;

  // Persist only the opaque conversation -> local session id association.
  // No PII, prompt text, mappings, or restored values are stored here.
  // chrome.storage.local survives normal extension reloads/updates so a browser
  // refresh does not lose the ability to reconnect to a still-live desktop RAM
  // session. Stale ids are rejected by the Bridge and cleared by background.js.
  function store() {
    return chrome.storage.local;
  }

  function validSessionId(value) {
    return typeof value === "string" && SESSION_ID_RE.test(value);
  }

  function extractConversationId(rawUrl) {
    try {
      const url = new URL(String(rawUrl || ""));
      if (url.hostname !== "chatgpt.com") return null;
      const match = url.pathname.match(/(?:^|\/)c\/([^/?#]+)/i);
      return match?.[1] || null;
    } catch (_error) {
      return null;
    }
  }

  function senderContext(sender) {
    const tabId = Number.isInteger(sender?.tab?.id) ? sender.tab.id : null;
    const rawUrl = sender?.url || sender?.tab?.url || "";
    const conversationId = extractConversationId(rawUrl);
    return {
      tabId,
      conversationId,
      conversationKey: conversationId ? `chatgpt:c:${conversationId}` : null,
      draftKey: tabId === null ? null : `chatgpt:tab:${tabId}:draft`
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
    const entries = await loadEntries();

    if (context.conversationKey && entries[context.conversationKey]) {
      entries[context.conversationKey].updatedAt = Date.now();
      await saveEntries(entries);
      return entries[context.conversationKey].sessionId;
    }

    // A brand-new ChatGPT conversation has no /c/<id> URL until the first
    // message is accepted. Migrate the tab-scoped draft session as soon as the
    // conversation receives its permanent id.
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
    const key = `chatgpt:tab:${tabId}:draft`;
    const entries = await loadEntries();
    if (!entries[key]) return false;
    delete entries[key];
    await saveEntries(entries);
    return true;
  }

  async function clearAll() {
    await store().remove(STORAGE_KEY);
  }

  globalThis.PrivacyGateSessionRegistry = Object.freeze({
    extractConversationId,
    senderContext,
    getSessionForSender,
    setSessionForSender,
    clearSessionForSender,
    clearDraftForTab,
    clearAll
  });
})();
