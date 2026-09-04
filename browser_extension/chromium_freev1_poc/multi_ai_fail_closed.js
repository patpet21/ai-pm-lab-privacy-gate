(() => {
  "use strict";

  const host = location.hostname.toLowerCase();
  if (!new Set(["claude.ai", "gemini.google.com"]).has(host)) return;

  const SOURCE = "privacygate-freev1";
  const ARM_TYPE = "PG_NETWORK_GATE_ARM";
  const MAX_AGE_MS = 10000;
  let pending = null;

  function compact(value) {
    return String(value || "")
      .normalize("NFC")
      .replace(/\r\n?/g, "\n")
      .replace(/\u00a0/g, " ")
      .replace(/\s+/gu, " ")
      .trim();
  }

  function active() {
    if (!pending) return null;
    if (Date.now() - pending.createdAt > MAX_AGE_MS) {
      pending = null;
      return null;
    }
    return pending;
  }

  function aiEndpoint(url) {
    const value = String(url || "").toLowerCase();
    if (host === "claude.ai") {
      return (
        value.includes("completion") ||
        value.includes("message") ||
        value.includes("conversation") ||
        value.includes("chat_")
      );
    }
    return (
      value.includes("batchexecute") ||
      value.includes("generate") ||
      value.includes("stream") ||
      value.includes("conversation") ||
      value.includes("message")
    );
  }

  function stringsFrom(value, depth = 0, output = []) {
    if (depth > 8 || value == null) return output;
    if (typeof value === "string") {
      output.push(compact(value));
      try {
        const parsed = JSON.parse(value);
        stringsFrom(parsed, depth + 1, output);
      } catch (_error) {
        // Plain text body.
      }
      return output;
    }
    if (value instanceof URLSearchParams) {
      output.push(compact(value.toString()));
      return output;
    }
    if (value instanceof FormData) {
      for (const [, entry] of value.entries()) {
        if (typeof entry === "string") stringsFrom(entry, depth + 1, output);
      }
      return output;
    }
    if (Array.isArray(value)) {
      value.forEach(entry => stringsFrom(entry, depth + 1, output));
      return output;
    }
    if (typeof value === "object") {
      Object.values(value).forEach(entry => stringsFrom(entry, depth + 1, output));
    }
    return output;
  }

  function containsRawOriginal(body) {
    const item = active();
    if (!item || body == null) return false;
    const original = item.original;
    if (!original) return false;
    const strings = stringsFrom(body);
    if (strings.some(value => value === original || value.includes(original))) return true;
    return compact(strings.join(" ")).includes(original);
  }

  window.addEventListener("message", event => {
    if (event.source !== window) return;
    const data = event.data;
    if (!data || data.source !== SOURCE || data.type !== ARM_TYPE) return;
    const original = compact(data.originalText);
    if (!original) return;
    pending = { original, createdAt: Date.now() };
  });

  const nativeFetch = window.fetch.bind(window);
  window.fetch = async function privacyGateMultiAiFailClosedFetch(input, init) {
    const item = active();
    if (!item) return nativeFetch(input, init);
    const request = input instanceof Request ? input : null;
    const method = String(init?.method || request?.method || "GET").toUpperCase();
    const url = request?.url || String(input || "");
    if (!["POST", "PUT", "PATCH"].includes(method) || !aiEndpoint(url)) {
      return nativeFetch(input, init);
    }

    let body = init && Object.prototype.hasOwnProperty.call(init, "body") ? init.body : null;
    if (body == null && request) {
      try { body = await request.clone().text(); } catch (_error) { body = null; }
    }
    if (containsRawOriginal(body)) {
      throw new Error("PrivacyGate blocked an unprotected outbound AI request");
    }
    return nativeFetch(input, init);
  };

  const xhrMeta = new WeakMap();
  const nativeOpen = XMLHttpRequest.prototype.open;
  const nativeSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function privacyGateMultiAiOpen(method, url, ...rest) {
    xhrMeta.set(this, { method: String(method || "GET").toUpperCase(), url: String(url || "") });
    return nativeOpen.call(this, method, url, ...rest);
  };
  XMLHttpRequest.prototype.send = function privacyGateMultiAiSend(body) {
    const meta = xhrMeta.get(this) || { method: "GET", url: "" };
    if (
      active() &&
      ["POST", "PUT", "PATCH"].includes(meta.method) &&
      aiEndpoint(meta.url) &&
      containsRawOriginal(body)
    ) {
      queueMicrotask(() => this.dispatchEvent(new ProgressEvent("error")));
      return;
    }
    return nativeSend.call(this, body);
  };

  const nativeWebSocketSend = WebSocket.prototype.send;
  WebSocket.prototype.send = function privacyGateMultiAiWebSocketSend(data) {
    if (active() && containsRawOriginal(data)) return;
    return nativeWebSocketSend.call(this, data);
  };
})();
