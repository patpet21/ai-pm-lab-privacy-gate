(() => {
  "use strict";

  const SOURCE = "privacygate-freev1";
  const ARM_TYPE = "PG_NETWORK_GATE_ARM";
  const ACK_TYPE = "PG_NETWORK_GATE_ARMED";
  const APPLIED_TYPE = "PG_NETWORK_GATE_APPLIED";
  const BLOCKED_TYPE = "PG_NETWORK_GATE_BLOCKED";
  const MAX_AGE_MS = 10000;
  const MAX_FLEX_PATTERN_CHARS = 50000;

  let pending = null;

  function normalized(value) {
    return String(value || "")
      .normalize("NFC")
      .replace(/\r\n?/g, "\n")
      .replace(/\u00a0/g, " ")
      .replace(/[ \t]+$/gm, "")
      .trim();
  }

  function compactWhitespace(value) {
    return normalized(value).replace(/\s+/gu, " ");
  }

  function escapeRegExp(value) {
    return String(value || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function flexiblePatternSource(value) {
    const original = normalized(value);
    if (!original || original.length > MAX_FLEX_PATTERN_CHARS) return "";
    const parts = original.split(/\s+/u).filter(Boolean);
    if (parts.length < 2) return "";
    return parts.map(escapeRegExp).join("\\s+");
  }

  function activePending() {
    if (!pending) return null;
    if (Date.now() - pending.createdAt > MAX_AGE_MS) {
      pending = null;
      return null;
    }
    return pending;
  }

  function post(type, token, detail = {}) {
    window.postMessage({ source: SOURCE, type, token, ...detail }, "*");
  }

  window.addEventListener("message", event => {
    if (event.source !== window) return;
    const data = event.data;
    if (!data || data.source !== SOURCE || data.type !== ARM_TYPE) return;

    const originalText = String(data.originalText || "");
    const protectedText = String(data.protectedText || "");
    const token = String(data.token || "");
    if (!token || !originalText || !protectedText || originalText === protectedText) return;

    pending = {
      token,
      originalText,
      protectedText,
      compactOriginal: compactWhitespace(originalText),
      flexibleSource: flexiblePatternSource(originalText),
      createdAt: Date.now()
    };
    post(ACK_TYPE, token);
  });

  function replaceString(value, state) {
    const item = activePending();
    if (!item || typeof value !== "string") return value;

    if (value.includes(item.originalText)) {
      state.replaced = true;
      return value.split(item.originalText).join(item.protectedText);
    }

    if (normalized(value) === normalized(item.originalText)) {
      state.replaced = true;
      return item.protectedText;
    }

    if (compactWhitespace(value) === item.compactOriginal) {
      state.replaced = true;
      return item.protectedText;
    }

    if (item.flexibleSource) {
      try {
        const pattern = new RegExp(item.flexibleSource, "gu");
        if (pattern.test(value)) {
          state.replaced = true;
          pattern.lastIndex = 0;
          return value.replace(pattern, item.protectedText);
        }
      } catch (_error) {
        // Fail closed later if this was the prompt request.
      }
    }

    return value;
  }

  function replaceValue(value, state) {
    if (typeof value === "string") return replaceString(value, state);

    if (Array.isArray(value)) {
      const output = value.map(item => replaceValue(item, state));
      if (state.replaced) return output;

      if (value.length > 1 && value.every(item => typeof item === "string")) {
        const item = activePending();
        if (item && compactWhitespace(value.join(" ")) === item.compactOriginal) {
          state.replaced = true;
          return [item.protectedText];
        }
      }
      return output;
    }

    if (value && typeof value === "object") {
      const output = {};
      for (const [key, item] of Object.entries(value)) {
        output[key] = replaceValue(item, state);
      }
      return output;
    }
    return value;
  }

  function transformTextBody(text) {
    const state = { replaced: false };
    let output = String(text || "");

    try {
      const parsed = JSON.parse(output);
      const transformed = replaceValue(parsed, state);
      if (state.replaced) {
        return { replaced: true, body: JSON.stringify(transformed) };
      }
    } catch (_error) {
      // Not JSON. Try raw and JSON-escaped forms below.
    }

    output = replaceString(output, state);
    if (state.replaced) return { replaced: true, body: output };

    const item = activePending();
    if (!item) return { replaced: false, body: output };

    const escapedOriginal = JSON.stringify(item.originalText).slice(1, -1);
    const escapedProtected = JSON.stringify(item.protectedText).slice(1, -1);
    if (escapedOriginal && output.includes(escapedOriginal)) {
      return {
        replaced: true,
        body: output.split(escapedOriginal).join(escapedProtected)
      };
    }

    return { replaced: false, body: output };
  }

  function conversationLike(url) {
    const value = String(url || "").toLowerCase();
    return (
      value.includes("conversation") ||
      value.includes("/responses") ||
      value.includes("/messages") ||
      value.includes("chat/complet")
    );
  }

  function completeApplied(kind) {
    const item = activePending();
    if (!item) return;
    const token = item.token;
    pending = null;
    post(APPLIED_TYPE, token, { transport: kind });
  }

  function blockPending(kind) {
    const item = activePending();
    if (!item) return;
    const token = item.token;
    pending = null;
    post(BLOCKED_TYPE, token, { transport: kind });
  }

  const nativeFetch = window.fetch.bind(window);
  window.fetch = async function privacyGateFetch(input, init) {
    const item = activePending();
    if (!item) return nativeFetch(input, init);

    const request = input instanceof Request ? input : null;
    const method = String(init?.method || request?.method || "GET").toUpperCase();
    if (!["POST", "PUT", "PATCH"].includes(method)) {
      return nativeFetch(input, init);
    }

    const url = request?.url || String(input || "");
    let body;
    let fromRequest = false;

    if (init && Object.prototype.hasOwnProperty.call(init, "body")) {
      body = init.body;
    } else if (request) {
      try {
        body = await request.clone().text();
        fromRequest = true;
      } catch (_error) {
        body = null;
      }
    }

    if (typeof body === "string") {
      const transformed = transformTextBody(body);
      if (transformed.replaced) {
        completeApplied("fetch");
        if (fromRequest && request && !(init && Object.prototype.hasOwnProperty.call(init, "body"))) {
          const replacement = new Request(request, { body: transformed.body });
          return nativeFetch(replacement);
        }
        return nativeFetch(input, { ...(init || {}), body: transformed.body });
      }
    } else if (body instanceof URLSearchParams) {
      const transformed = transformTextBody(body.toString());
      if (transformed.replaced) {
        completeApplied("fetch-urlsearchparams");
        return nativeFetch(input, {
          ...(init || {}),
          body: new URLSearchParams(transformed.body)
        });
      }
    } else if (body instanceof FormData) {
      const copy = new FormData();
      let replaced = false;
      for (const [key, value] of body.entries()) {
        if (typeof value === "string") {
          const state = { replaced: false };
          const next = replaceString(value, state);
          replaced ||= state.replaced;
          copy.append(key, next);
        } else {
          copy.append(key, value);
        }
      }
      if (replaced) {
        completeApplied("fetch-formdata");
        return nativeFetch(input, { ...(init || {}), body: copy });
      }
    }

    if (conversationLike(url)) {
      blockPending("fetch-unverified");
      throw new Error("PrivacyGate blocked an unverified prompt request");
    }

    return nativeFetch(input, init);
  };

  const xhrMeta = new WeakMap();
  const nativeOpen = XMLHttpRequest.prototype.open;
  const nativeSend = XMLHttpRequest.prototype.send;

  XMLHttpRequest.prototype.open = function privacyGateOpen(method, url, ...rest) {
    xhrMeta.set(this, { method: String(method || "GET").toUpperCase(), url: String(url || "") });
    return nativeOpen.call(this, method, url, ...rest);
  };

  XMLHttpRequest.prototype.send = function privacyGateSend(body) {
    const item = activePending();
    if (!item) return nativeSend.call(this, body);

    const meta = xhrMeta.get(this) || { method: "GET", url: "" };
    if (!["POST", "PUT", "PATCH"].includes(meta.method)) {
      return nativeSend.call(this, body);
    }

    if (typeof body === "string") {
      const transformed = transformTextBody(body);
      if (transformed.replaced) {
        completeApplied("xhr");
        return nativeSend.call(this, transformed.body);
      }
    }

    if (conversationLike(meta.url)) {
      blockPending("xhr-unverified");
      queueMicrotask(() => this.dispatchEvent(new ProgressEvent("error")));
      return;
    }

    return nativeSend.call(this, body);
  };

  const nativeWebSocketSend = WebSocket.prototype.send;
  WebSocket.prototype.send = function privacyGateWebSocketSend(data) {
    if (activePending() && typeof data === "string") {
      const transformed = transformTextBody(data);
      if (transformed.replaced) {
        completeApplied("websocket");
        return nativeWebSocketSend.call(this, transformed.body);
      }
    }
    return nativeWebSocketSend.call(this, data);
  };

  if (typeof navigator.sendBeacon === "function") {
    const nativeBeacon = navigator.sendBeacon.bind(navigator);
    navigator.sendBeacon = function privacyGateBeacon(url, data) {
      if (activePending() && typeof data === "string") {
        const transformed = transformTextBody(data);
        if (transformed.replaced) {
          completeApplied("beacon");
          return nativeBeacon(url, transformed.body);
        }
      }
      if (activePending() && conversationLike(url)) {
        blockPending("beacon-unverified");
        return false;
      }
      return nativeBeacon(url, data);
    };
  }
})();