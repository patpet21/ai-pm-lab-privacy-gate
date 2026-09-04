importScripts("session_registry.js");

const DEFAULT_BRIDGE_PORT = 8765;
const BRIDGE_PORT_KEY = "privacygateBridgePort";
const PROFILE_KEY = "privacygateProtectionProfile";
const DEFAULT_PROFILE_KEY = "property_management";
const BROWSER_TOKEN_KEY = "privacygateBrowserCredentialV1";
const BROWSER_CLIENT_ID_KEY = "privacygateBrowserClientIdV1";
const SessionRegistry = globalThis.PrivacyGateSessionRegistry;
const PROFILE_KEYS = new Set([
  "general_business",
  "property_management",
  "realtor_brokerage",
  "projects_renovations",
  "construction",
  "legal",
  "healthcare_general"
]);

async function installPrivacyGateActionIcon() {
  try {
    const response = await fetch(chrome.runtime.getURL("privacygate-mark.svg"), {
      cache: "no-store"
    });
    if (!response.ok) return;

    const bitmap = await createImageBitmap(await response.blob());
    const imageData = {};
    for (const size of [16, 32, 48, 128]) {
      const canvas = new OffscreenCanvas(size, size);
      const context = canvas.getContext("2d");
      if (!context) continue;
      context.clearRect(0, 0, size, size);
      context.drawImage(bitmap, 0, 0, size, size);
      imageData[size] = context.getImageData(0, 0, size, size);
    }
    bitmap.close?.();

    if (Object.keys(imageData).length) {
      await chrome.action.setIcon({ imageData });
    }
  } catch (_error) {
    // Branding must never interfere with browser protection.
  }
}

const ITALIAN_HINTS = new Set([
  "a", "ad", "anche", "allora", "che", "chi", "come", "con", "cosa", "da",
  "di", "e", "è", "gli", "ho", "i", "il", "in", "io", "la", "le", "lo",
  "ma", "mi", "non", "noi", "per", "perché", "pero", "però", "possiamo",
  "puoi", "quindi", "sei", "si", "sì", "siamo", "sono", "su", "tra", "tu",
  "un", "una", "voi"
]);

const ENGLISH_HINTS = new Set([
  "a", "an", "and", "are", "can", "do", "for", "how", "i", "in", "is", "it",
  "my", "not", "of", "on", "please", "that", "the", "this", "to", "we", "what",
  "with", "you", "your"
]);

function detectPromptLanguage(text) {
  const raw = String(text || "").toLowerCase();
  if (/[àèéìòù]/u.test(raw)) return "it";

  const words = raw.match(/[a-zà-ÿ']+/giu) || [];
  let italian = 0;
  let english = 0;
  for (const word of words) {
    if (ITALIAN_HINTS.has(word)) italian += 1;
    if (ENGLISH_HINTS.has(word)) english += 1;
  }
  if (italian >= 2 && italian > english) return "it";
  if (english >= 2 && english > italian) return "en";
  return "en";
}

function normalizeBridgePort(value) {
  const port = Number.parseInt(String(value ?? ""), 10);
  return Number.isInteger(port) && port >= 1024 && port <= 65535
    ? port
    : DEFAULT_BRIDGE_PORT;
}

function normalizeProfileKey(value) {
  const key = typeof value === "string" ? value.trim() : "";
  return PROFILE_KEYS.has(key) ? key : DEFAULT_PROFILE_KEY;
}

function providerForSender(sender) {
  return SessionRegistry?.senderContext?.(sender)?.provider || "chatgpt";
}

async function getExtensionSettings() {
  const values = await chrome.storage.local.get({
    [BRIDGE_PORT_KEY]: DEFAULT_BRIDGE_PORT,
    [PROFILE_KEY]: DEFAULT_PROFILE_KEY
  });
  return {
    bridgePort: normalizeBridgePort(values?.[BRIDGE_PORT_KEY]),
    profileKey: normalizeProfileKey(values?.[PROFILE_KEY])
  };
}

async function saveExtensionSettings({ bridgePort, profileKey }) {
  const normalizedPort = normalizeBridgePort(bridgePort);
  const normalizedProfile = normalizeProfileKey(profileKey);
  await chrome.storage.local.set({
    [BRIDGE_PORT_KEY]: normalizedPort,
    [PROFILE_KEY]: normalizedProfile
  });
  return { bridgePort: normalizedPort, profileKey: normalizedProfile };
}

async function getBridgeBase() {
  const { bridgePort } = await getExtensionSettings();
  return `http://127.0.0.1:${bridgePort}`;
}

async function getBrowserToken() {
  const values = await chrome.storage.local.get(BROWSER_TOKEN_KEY);
  const token = values?.[BROWSER_TOKEN_KEY];
  return typeof token === "string" && token.length >= 24 ? token : null;
}

async function setBrowserToken(token) {
  if (typeof token === "string" && token.length >= 24) {
    await chrome.storage.local.set({ [BROWSER_TOKEN_KEY]: token });
  } else {
    await chrome.storage.local.remove(BROWSER_TOKEN_KEY);
  }
}

async function getBrowserClientId() {
  const values = await chrome.storage.local.get(BROWSER_CLIENT_ID_KEY);
  const current = values?.[BROWSER_CLIENT_ID_KEY];
  if (typeof current === "string" && /^[a-f0-9-]{20,64}$/i.test(current)) {
    return current;
  }

  const generated = crypto.randomUUID();
  await chrome.storage.local.set({ [BROWSER_CLIENT_ID_KEY]: generated });
  return generated;
}

async function responseJson(response) {
  try {
    return await response.json();
  } catch (_error) {
    return {};
  }
}

async function bridgeJson(path, body, { authenticated = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (authenticated) {
    const token = await getBrowserToken();
    if (!token) {
      return {
        ok: false,
        status: 401,
        data: { error: "browser_pairing_required" }
      };
    }
    headers.Authorization = `Bearer ${token}`;
  }

  const bridge = await getBridgeBase();
  const response = await fetch(`${bridge}${path}`, {
    method: "POST",
    cache: "no-store",
    headers,
    body: JSON.stringify(body)
  });
  const data = await responseJson(response);
  return { ok: response.ok, status: response.status, data };
}

async function baseBridgeStatus() {
  const bridge = await getBridgeBase();
  const response = await fetch(`${bridge}/v1/status`, {
    method: "GET",
    cache: "no-store"
  });
  const data = await responseJson(response);
  return {
    ok: response.ok && data?.status === "ready",
    status: response.status,
    data
  };
}

async function bridgeStatus() {
  const base = await baseBridgeStatus();
  const bridgeReady = Boolean(base.ok);

  if (!bridgeReady) {
    return {
      ok: false,
      bridgeReady: false,
      paired: false,
      status: base.status,
      data: base.data
    };
  }

  const token = await getBrowserToken();
  if (!token) {
    return {
      ok: false,
      bridgeReady: true,
      paired: false,
      status: base.status,
      data: base.data
    };
  }

  try {
    const headers = { Authorization: `Bearer ${token}` };
    const bridge = await getBridgeBase();
    const response = await fetch(`${bridge}/v1/browser/status`, {
      method: "GET",
      cache: "no-store",
      headers
    });
    const data = await responseJson(response);

    if (response.ok) {
      const paired = Boolean(data?.paired);
      if (!paired) {
        await setBrowserToken(null);
        await SessionRegistry.clearAll();
      }
      return {
        ok: paired,
        bridgeReady: true,
        paired,
        status: response.status,
        data
      };
    }

    const pairingRejected =
      response.status === 401 ||
      response.status === 403 ||
      data?.error === "browser_pairing_required";
    if (pairingRejected) {
      await setBrowserToken(null);
      await SessionRegistry.clearAll();
    }
    return {
      ok: false,
      bridgeReady: true,
      paired: false,
      pairingRejected,
      pairingError: !pairingRejected,
      status: response.status,
      data
    };
  } catch (error) {
    return {
      ok: false,
      bridgeReady: false,
      paired: false,
      error: String(error)
    };
  }
}

async function protectForConversation(message, sender) {
  const language = detectPromptLanguage(message.text);
  const { profileKey } = await getExtensionSettings();
  const provider = providerForSender(sender);
  let sessionId = await SessionRegistry.getSessionForSender(sender);

  const request = id => bridgeJson("/v1/browser/protect", {
    text: message.text,
    profile_key: profileKey,
    language,
    finding_ids: Array.isArray(message.findingIds) ? message.findingIds : [],
    replacement_mode: "reversible",
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
    await SessionRegistry.clearSessionForSender(sender);
    sessionId = null;
    response = await request(null);
  }

  if (response.ok && response.data?.session_id) {
    await SessionRegistry.setSessionForSender(sender, response.data.session_id);
  }

  return { ...response, detectedLanguage: language, profileKey, provider };
}

async function restoreForConversation(message, sender) {
  const sessionId = await SessionRegistry.getSessionForSender(sender);
  if (!sessionId) {
    return {
      ok: false,
      status: 404,
      data: { error: "browser_session_unavailable" }
    };
  }

  const response = await bridgeJson("/v1/browser/restore", {
    text: message.text,
    session_id: sessionId
  });

  if (
    !response.ok &&
    response.status === 404 &&
    response.data?.error === "session_not_found"
  ) {
    await SessionRegistry.clearSessionForSender(sender);
  }

  return response;
}

async function revokeBrowserPairing() {
  const token = await getBrowserToken();
  if (!token) {
    await SessionRegistry.clearAll();
    return { ok: true, revoked: false, alreadyDisconnected: true };
  }

  const bridge = await getBridgeBase();
  let response;
  try {
    response = await fetch(`${bridge}/v1/browser/pairing`, {
      method: "DELETE",
      cache: "no-store",
      headers: { Authorization: `Bearer ${token}` }
    });
  } catch (error) {
    return {
      ok: false,
      revoked: false,
      error: `PrivacyGate Desktop is not reachable: ${String(error)}`
    };
  }

  const data = await responseJson(response);
  if (response.ok && data?.revoked === true) {
    await setBrowserToken(null);
    await SessionRegistry.clearAll();
    return { ok: true, revoked: true };
  }

  if (response.status === 401 && data?.error === "browser_pairing_required") {
    await setBrowserToken(null);
    await SessionRegistry.clearAll();
    return { ok: true, revoked: false, alreadyDisconnected: true };
  }

  return {
    ok: false,
    revoked: false,
    status: response.status,
    data,
    error: "PrivacyGate Desktop could not revoke this browser credential. Keep the pairing and try again after the desktop app is updated and running."
  };
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "PG_BRIDGE_STATUS") {
    bridgeStatus()
      .then(sendResponse)
      .catch(error => sendResponse({ ok: false, bridgeReady: false, paired: false, error: String(error) }));
    return true;
  }

  if (message?.type === "PG_GET_EXTENSION_SETTINGS") {
    getExtensionSettings()
      .then(settings => sendResponse({ ok: true, ...settings }))
      .catch(error => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  if (message?.type === "PG_SET_EXTENSION_SETTINGS") {
    saveExtensionSettings({
      bridgePort: message.bridgePort,
      profileKey: message.profileKey
    })
      .then(settings => sendResponse({ ok: true, ...settings }))
      .catch(error => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  if (message?.type === "PG_PAIR") {
    const code = String(message.code || "").trim();
    (async () => {
      const clientId = await getBrowserClientId();
      const response = await bridgeJson(
        "/v1/browser/pair",
        {
          code,
          client_name: `PrivacyGate Chromium · ${clientId}`
        },
        { authenticated: false }
      );
      const token = response.data?.browser_token;
      if (response.ok && typeof token === "string") {
        await setBrowserToken(token);
        await SessionRegistry.clearAll();
        return { ok: true, paired: true };
      }
      return { ...response, paired: false };
    })()
      .then(sendResponse)
      .catch(error => sendResponse({ ok: false, paired: false, error: String(error) }));
    return true;
  }

  if (message?.type === "PG_FORGET_PAIRING") {
    revokeBrowserPairing()
      .then(sendResponse)
      .catch(error => sendResponse({ ok: false, revoked: false, error: String(error) }));
    return true;
  }

  if (message?.type === "PG_ANALYZE") {
    (async () => {
      const language = detectPromptLanguage(message.text);
      const { profileKey } = await getExtensionSettings();
      const response = await bridgeJson("/v1/browser/analyze", {
        text: message.text,
        profile_key: profileKey,
        language
      });
      return { ...response, detectedLanguage: language, profileKey };
    })()
      .then(sendResponse)
      .catch(error => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  if (message?.type === "PG_PROTECT") {
    protectForConversation(message, sender)
      .then(sendResponse)
      .catch(error => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  if (message?.type === "PG_RESTORE") {
    restoreForConversation(message, sender)
      .then(sendResponse)
      .catch(error => sendResponse({ ok: false, error: String(error) }));
    return true;
  }
});

chrome.runtime.onInstalled.addListener(() => {
  installPrivacyGateActionIcon();
});
chrome.runtime.onStartup.addListener(() => {
  installPrivacyGateActionIcon();
});
installPrivacyGateActionIcon();

chrome.tabs?.onRemoved?.addListener(tabId => {
  SessionRegistry.clearDraftForTab(tabId).catch(() => {});
});

async function analyzePdfForBrowser(message) {
  const settings = await getExtensionSettings();
  const requestedProfile =
    typeof message.profileKey === "string" && PROFILE_KEYS.has(message.profileKey.trim())
      ? message.profileKey.trim()
      : settings.profileKey;
  const language = message.language === "it" ? "it" : "en";
  const response = await bridgeJson("/v1/browser/pdf/analyze", {
    filename: message.filename,
    file_base64: message.fileBase64,
    profile_key: requestedProfile,
    language
  });
  return { ...response, detectedLanguage: language, profileKey: requestedProfile };
}

async function protectPdfForConversation(message, sender) {
  const provider = providerForSender(sender);
  let sessionId = await SessionRegistry.getSessionForSender(sender);

  const request = id => bridgeJson("/v1/browser/pdf/protect", {
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
    await SessionRegistry.clearSessionForSender(sender);
    sessionId = null;
    response = await request(null);
  }

  if (response.ok && response.data?.session_id) {
    await SessionRegistry.setSessionForSender(sender, response.data.session_id);
  }
  return response;
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "PG_PDF_ANALYZE") {
    analyzePdfForBrowser(message)
      .then(sendResponse)
      .catch(error => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  if (message?.type === "PG_PDF_PROTECT") {
    protectPdfForConversation(message, sender)
      .then(sendResponse)
      .catch(error => sendResponse({ ok: false, error: String(error) }));
    return true;
  }
});