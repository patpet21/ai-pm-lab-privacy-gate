(() => {
  "use strict";

  if (window.top !== window) return;

  const SOURCE = "privacygate-freev1";
  const ARM_TYPE = "PG_NETWORK_GATE_ARM";
  const ACK_TYPE = "PG_NETWORK_GATE_ARMED";
  const APPLIED_TYPE = "PG_NETWORK_GATE_APPLIED";
  const BLOCKED_TYPE = "PG_NETWORK_GATE_BLOCKED";

  const nativeSendMessage = chrome.runtime.sendMessage.bind(chrome.runtime);
  const nativeExecCommand = document.execCommand.bind(document);
  const pendingCallbacks = new Map();
  let passthroughText = null;
  let passthroughTimer = null;

  function normalized(value) {
    return String(value || "")
      .replace(/\r\n?/g, "\n")
      .replace(/\u00a0/g, " ")
      .replace(/[ \t]+$/gm, "")
      .trim();
  }

  function composer() {
    return (
      document.querySelector("#prompt-textarea") ||
      document.querySelector('[contenteditable="true"]')
    );
  }

  function composerText(box) {
    if (!box) return "";
    if (box instanceof HTMLTextAreaElement || box instanceof HTMLInputElement) {
      return box.value || "";
    }
    return box.innerText || box.textContent || "";
  }

  function toast(message, kind) {
    document.getElementById("privacygate-network-gate-toast")?.remove();
    const element = document.createElement("div");
    element.id = "privacygate-network-gate-toast";
    Object.assign(element.style, {
      position: "fixed",
      left: "50%",
      top: "50%",
      transform: "translate(-50%, -50%)",
      zIndex: "2147483647",
      padding: "11px 15px",
      borderRadius: "999px",
      background: kind === "error" ? "#991b1b" : "#065f46",
      color: "#fff",
      fontFamily: "Arial, sans-serif",
      fontSize: "13px",
      fontWeight: "750",
      boxShadow: "0 12px 34px rgba(0,0,0,.28)"
    });
    element.textContent = message;
    document.documentElement.appendChild(element);
    setTimeout(() => element.remove(), kind === "error" ? 5000 : 2200);
  }

  function setPassthrough(text) {
    passthroughText = String(text || "");
    clearTimeout(passthroughTimer);
    passthroughTimer = setTimeout(() => {
      passthroughText = null;
      passthroughTimer = null;
    }, 2500);
  }

  document.execCommand = function privacyGateExecCommand(commandId, showUI, value) {
    if (
      String(commandId || "").toLowerCase() === "inserttext" &&
      typeof passthroughText === "string" &&
      normalized(String(value || "")) === normalized(passthroughText) &&
      normalized(composerText(composer())) === normalized(passthroughText)
    ) {
      // The protected value is applied later at the network boundary. Keep the
      // visible editor untouched so ChatGPT's internal editor state is never
      // desynchronized from the DOM.
      return true;
    }
    return nativeExecCommand(commandId, showUI, value);
  };

  function fakeProtectedResponse(originalMessage, response) {
    return {
      ...response,
      data: {
        ...(response?.data || {}),
        // content.js must leave the ChatGPT composer untouched. The real
        // protected_text has already been armed in the MAIN-world network gate.
        protected_text: originalMessage.text
      }
    };
  }

  function armNetworkGate(message, response, callback) {
    const protectedText = response?.data?.protected_text;
    if (
      !response?.ok ||
      typeof protectedText !== "string" ||
      !protectedText.includes("[[PG_") ||
      typeof message?.text !== "string"
    ) {
      callback(response);
      return;
    }

    const token = crypto.randomUUID();
    const timer = setTimeout(() => {
      const pending = pendingCallbacks.get(token);
      if (!pending) return;
      pendingCallbacks.delete(token);
      pending.callback({
        ok: false,
        status: 0,
        data: { error: "network_gate_unavailable" }
      });
      toast("PrivacyGate — outbound protection gate unavailable. Nothing was sent.", "error");
    }, 800);

    pendingCallbacks.set(token, {
      message,
      response,
      callback,
      timer
    });

    window.postMessage(
      {
        source: SOURCE,
        type: ARM_TYPE,
        token,
        originalText: message.text,
        protectedText
      },
      "*"
    );
  }

  function patchedSendMessage(...args) {
    const messageIndex = typeof args[0] === "string" ? 1 : 0;
    const message = args[messageIndex];
    const callbackIndex = args.findIndex(
      (value, index) => index > messageIndex && typeof value === "function"
    );

    if (message?.type !== "PG_PROTECT" || callbackIndex < 0) {
      return nativeSendMessage(...args);
    }

    const callback = args[callbackIndex];
    args[callbackIndex] = response => armNetworkGate(message, response, callback);
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
      toast("PrivacyGate — browser protection bridge could not initialize.", "error");
    }
  }

  window.addEventListener("message", event => {
    if (event.source !== window) return;
    const data = event.data;
    if (!data || data.source !== SOURCE) return;

    const token = String(data.token || "");

    if (data.type === ACK_TYPE) {
      const pending = pendingCallbacks.get(token);
      if (!pending) return;

      clearTimeout(pending.timer);
      pendingCallbacks.delete(token);
      setPassthrough(pending.message.text);
      pending.callback(fakeProtectedResponse(pending.message, pending.response));
      return;
    }

    if (data.type === APPLIED_TYPE) {
      passthroughText = null;
      clearTimeout(passthroughTimer);
      passthroughTimer = null;
      toast("PrivacyGate — protected request sent locally.", "success");
      return;
    }

    if (data.type === BLOCKED_TYPE) {
      passthroughText = null;
      clearTimeout(passthroughTimer);
      passthroughTimer = null;
      toast("PrivacyGate blocked an unverified outbound request. Nothing was sent.", "error");
    }
  });
})();