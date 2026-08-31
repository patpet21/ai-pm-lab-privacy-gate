(() => {
  "use strict";

  if (window.top !== window) return;

  const nativeSendMessage = chrome.runtime.sendMessage.bind(chrome.runtime);

  function safeNoopResponse(message) {
    return {
      ok: true,
      status: 200,
      data: {
        restored_text: String(message?.text || ""),
        session_id: message?.sessionId || null,
        legacy_dom_restore_disabled: true
      }
    };
  }

  function patchedSendMessage(...args) {
    const messageIndex = typeof args[0] === "string" ? 1 : 0;
    const message = args[messageIndex];
    const callbackIndex = args.findIndex(
      (value, index) => index > messageIndex && typeof value === "function"
    );

    // content.js's legacy restore path passes an explicit sessionId and then
    // writes the returned clear value into ChatGPT's DOM. Never allow that.
    // The secure restore overlay intentionally omits sessionId and therefore
    // passes through to the real background restore service below.
    if (
      message?.type === "PG_RESTORE" &&
      Object.prototype.hasOwnProperty.call(message, "sessionId")
    ) {
      const response = safeNoopResponse(message);
      if (callbackIndex >= 0) {
        queueMicrotask(() => args[callbackIndex](response));
        return undefined;
      }
      return Promise.resolve(response);
    }

    return nativeSendMessage(...args);
  }

  try {
    chrome.runtime.sendMessage = patchedSendMessage;
  } catch (_error) {
    try {
      Object.defineProperty(chrome.runtime, "sendMessage", {
        configurable: true,
        value: patchedSendMessage
      });
    } catch (_secondError) {
      // Fail closed for legacy restore: if the wrapper cannot install, the
      // secure overlay may still work, but we do not expose any clear value here.
    }
  }
})();
