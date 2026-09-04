(() => {
  "use strict";

  const DEFAULT_BRIDGE_PORT = 8765;
  const BRIDGE_PORT_KEY = "privacygateBridgePort";
  const PROFILE_KEY = "privacygateProtectionProfile";
  const DEFAULT_PROFILE_KEY = "general_business";
  const BROWSER_TOKEN_KEY = "privacygateBrowserCredentialV1";
  const PROFILE_KEYS = new Set([
    "general_business",
    "property_management",
    "realtor_brokerage",
    "projects_renovations",
    "construction",
    "legal",
    "healthcare_general"
  ]);
  const SessionRegistry = globalThis.PrivacyGateSessionRegistry;

  function normalizePort(value) {
    const port = Number.parseInt(String(value ?? ""), 10);
    return Number.isInteger(port) && port >= 1024 && port <= 65535
      ? port
      : DEFAULT_BRIDGE_PORT;
  }

  function providerForSender(sender) {
    return SessionRegistry?.senderContext?.(sender)?.provider || null;
  }

  async function settings() {
    const values = await chrome.storage.local.get({
      [BRIDGE_PORT_KEY]: DEFAULT_BRIDGE_PORT,
      [PROFILE_KEY]: DEFAULT_PROFILE_KEY
    });
    const requested = String(values?.[PROFILE_KEY] || "").trim();
    return {
      bridgePort: normalizePort(values?.[BRIDGE_PORT_KEY]),
      profileKey: PROFILE_KEYS.has(requested) ? requested : DEFAULT_PROFILE_KEY
    };
  }

  async function browserToken() {
    const values = await chrome.storage.local.get(BROWSER_TOKEN_KEY);
    const value = values?.[BROWSER_TOKEN_KEY];
    return typeof value === "string" && value.length >= 24 ? value : null;
  }

  async function bridgeJson(path, body) {
    const token = await browserToken();
    if (!token) {
      return {
        ok: false,
        status: 401,
        data: { error: "browser_pairing_required" }
      };
    }
    const { bridgePort } = await settings();
    const response = await fetch(`http://127.0.0.1:${bridgePort}${path}`, {
      method: "POST",
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify(body)
    });
    let data = {};
    try {
      data = await response.json();
    } catch (_error) {
      data = {};
    }
    return { ok: response.ok, status: response.status, data };
  }

  async function analyzeDocx(message) {
    const current = await settings();
    const requested = String(message.profileKey || "").trim();
    const profileKey = PROFILE_KEYS.has(requested) ? requested : current.profileKey;
    const language = message.language === "it" ? "it" : "en";
    const response = await bridgeJson("/v1/browser/docx/analyze", {
      filename: message.filename,
      file_base64: message.fileBase64,
      profile_key: profileKey,
      language
    });
    return { ...response, profileKey, detectedLanguage: language };
  }

  async function protectDocx(message, sender) {
    const provider = providerForSender(sender);
    if (!provider) {
      return {
        ok: false,
        status: 400,
        data: { error: "unsupported_ai_provider" }
      };
    }

    let sessionId = SessionRegistry
      ? await SessionRegistry.getSessionForSender(sender)
      : null;

    const request = id => bridgeJson("/v1/browser/docx/protect", {
      analysis_id: message.analysisId,
      finding_ids: Array.isArray(message.findingIds) ? message.findingIds : [],
      session_id: id || null,
      provider
    });

    let response = await request(sessionId);
    if (
      !response.ok &&
      sessionId &&
      response.status === 404 &&
      response.data?.error === "session_not_found"
    ) {
      if (SessionRegistry) await SessionRegistry.clearSessionForSender(sender);
      sessionId = null;
      response = await request(null);
    }

    if (response.ok && response.data?.session_id && SessionRegistry) {
      await SessionRegistry.setSessionForSender(sender, response.data.session_id);
    }
    return response;
  }

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message?.type === "PG_DOCX_ANALYZE") {
      analyzeDocx(message)
        .then(sendResponse)
        .catch(error => sendResponse({ ok: false, error: String(error) }));
      return true;
    }

    if (message?.type === "PG_DOCX_PROTECT") {
      protectDocx(message, sender)
        .then(sendResponse)
        .catch(error => sendResponse({ ok: false, error: String(error) }));
      return true;
    }
  });
})();
