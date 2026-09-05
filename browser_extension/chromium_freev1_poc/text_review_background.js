(() => {
  "use strict";

  const DEFAULT_BRIDGE_PORT = 8765;
  const BRIDGE_PORT_KEY = "privacygateBridgePort";
  const PROFILE_KEY = "privacygateProtectionProfile";
  const DEFAULT_PROFILE_KEY = "property_management";
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

  const languageOverrides = new Map();
  const OVERRIDE_TTL_MS = 10 * 60 * 1000;

  function fingerprint(text) {
    const value = String(text || "");
    let hash = 2166136261;
    for (let index = 0; index < value.length; index += 1) {
      hash ^= value.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return `${value.length}:${(hash >>> 0).toString(16)}`;
  }

  function normalizedProfile(value) {
    const key = String(value || "").trim();
    return PROFILE_KEYS.has(key) ? key : DEFAULT_PROFILE_KEY;
  }

  function normalizedLanguage(value) {
    return value === "it" ? "it" : "en";
  }

  function normalizedPort(value) {
    const port = Number.parseInt(String(value ?? ""), 10);
    return Number.isInteger(port) && port >= 1024 && port <= 65535
      ? port
      : DEFAULT_BRIDGE_PORT;
  }

  async function extensionState() {
    const values = await chrome.storage.local.get({
      [BRIDGE_PORT_KEY]: DEFAULT_BRIDGE_PORT,
      [PROFILE_KEY]: DEFAULT_PROFILE_KEY,
      [BROWSER_TOKEN_KEY]: null
    });
    const token = values?.[BROWSER_TOKEN_KEY];
    return {
      bridgePort: normalizedPort(values?.[BRIDGE_PORT_KEY]),
      profileKey: normalizedProfile(values?.[PROFILE_KEY]),
      token: typeof token === "string" && token.length >= 24 ? token : null
    };
  }

  async function rescanText(message) {
    const state = await extensionState();
    if (!state.token) {
      return {
        ok: false,
        status: 401,
        data: { error: "browser_pairing_required" }
      };
    }

    const text = String(message.text || "");
    if (!text.trim()) {
      return {
        ok: false,
        status: 400,
        data: { error: "text_required" }
      };
    }

    const profileKey = normalizedProfile(message.profileKey || state.profileKey);
    const language = normalizedLanguage(message.language);
    const response = await fetch(
      `http://127.0.0.1:${state.bridgePort}/v1/browser/analyze`,
      {
        method: "POST",
        cache: "no-store",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${state.token}`
        },
        body: JSON.stringify({
          text,
          profile_key: profileKey,
          language
        })
      }
    );

    let data = {};
    try {
      data = await response.json();
    } catch (_error) {
      data = {};
    }

    if (response.ok) {
      // The selected profile becomes the active browser profile, matching the
      // extension popup/document-review behavior. Language remains per-message.
      await chrome.storage.local.set({ [PROFILE_KEY]: profileKey });
      languageOverrides.set(fingerprint(text), {
        language,
        expiresAt: Date.now() + OVERRIDE_TTL_MS
      });
    }

    return {
      ok: response.ok,
      status: response.status,
      data,
      profileKey,
      detectedLanguage: language
    };
  }

  // Keep the proven PG_PROTECT/session path intact. We only override the
  // language detector for the one text that the user explicitly rescanned.
  // The profile is already persisted above and is therefore picked up by the
  // existing protectForConversation implementation.
  try {
    const baseDetector = detectPromptLanguage;
    detectPromptLanguage = function privacyGateTextReviewLanguage(text) {
      const key = fingerprint(text);
      const override = languageOverrides.get(key);
      if (override) {
        languageOverrides.delete(key);
        if (override.expiresAt >= Date.now()) return override.language;
      }
      return baseDetector(text);
    };
  } catch (_error) {
    // If the service-worker implementation changes, fail back to the proven
    // automatic detector rather than interfering with browser protection.
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type !== "PG_TEXT_RESCAN") return false;
    rescanText(message)
      .then(sendResponse)
      .catch(error => sendResponse({ ok: false, error: String(error) }));
    return true;
  });
})();
