(() => {
  "use strict";

  if (typeof restoreForConversation !== "function" || typeof bridgeJson !== "function") return;

  const originalRestoreForConversation = restoreForConversation;

  restoreForConversation = async function privacyGateRestoreWithPersistedFallback(message, sender) {
    const text = String(message?.text || "");
    const response = await originalRestoreForConversation(message, sender);

    const errorCode = response?.data?.error;
    const unchanged = response?.ok && response?.data?.restored_text === text;
    const missingSession =
      response?.status === 404 &&
      (errorCode === "session_not_found" || errorCode === "browser_session_unavailable");

    if (!text.trim() || (!unchanged && !missingSession)) {
      return response;
    }

    const recovered = await bridgeJson("/v1/browser/restore-auto", { text });
    return recovered?.ok ? recovered : response;
  };
})();
