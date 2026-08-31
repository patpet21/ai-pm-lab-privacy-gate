importScripts("session_registry.js");

const BRIDGE = "http://127.0.0.1:8765";
const BROWSER_TOKEN_KEY = "privacygateBrowserCredentialV1";
const SessionRegistry = globalThis.PrivacyGateSessionRegistry;

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

  const response = await fetch(`${BRIDGE}${path}`, {
    method: "POST",
    cache: "no-store",
    headers,
    body: JSON.stringify(body)
  });
  const data = await response.json();
  return { ok: response.ok, status: response.status, data };
}

async function baseBridgeStatus() {
  const response = await fetch(`${BRIDGE}/v1/status`, {
    method: "GET",
    cache: "no-store"
  });
  const data = await response.json();
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
    const response = await fetch(`${BRIDGE}/v1/browser/status`, {
      method: "GET",
      cache: "no-store",
      headers
    });
    const data = await response.json();

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

    return {
      ok: true,
      bridgeReady: true,
      paired: true,
      status: response.status,
      data: { ...data, status: "ready", paired: true }
    };
  } catch (_error) {
    return {
      ok: true,
      bridgeReady: true,
      paired: true,
      status: base.status,
      data: { ...base.data, paired: true }
    };
  }
}

async function protectForConversation(message, sender) {
  const language = detectPromptLanguage(message.text);
  let sessionId = await SessionRegistry.getSessionForSender(sender);

  const request = id => bridgeJson("/v1/browser/protect", {
    text: message.text,
    profile_key: "property_management",
    language,
    finding_ids: Array.isArray(message.findingIds) ? message.findingIds : [],
    replacement_mode: "reversible",
    session_id: id || null
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

  return { ...response, detectedLanguage: language };
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

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "PG_BRIDGE_STATUS") {
    bridgeStatus()
      .then(sendResponse)
      .catch(error => sendResponse({ ok: false, bridgeReady: false, paired: false, error: String(error) }));
    return true;
  }

  if (message?.type === "PG_PAIR") {
    const code = String(message.code || "").trim();
    bridgeJson(
      "/v1/browser/pair",
      {
        code,
        client_name: `Chromium extension ${chrome.runtime.getManifest().version}`
      },
      { authenticated: false }
    )
      .then(async response => {
        const token = response.data?.browser_token;
        if (response.ok && typeof token === "string") {
          await setBrowserToken(token);
          await SessionRegistry.clearAll();
          sendResponse({ ok: true, paired: true });
          return;
        }
        sendResponse({ ...response, paired: false });
      })
      .catch(error => sendResponse({ ok: false, paired: false, error: String(error) }));
    return true;
  }

  if (message?.type === "PG_FORGET_PAIRING") {
    Promise.all([setBrowserToken(null), SessionRegistry.clearAll()])
      .then(() => sendResponse({ ok: true }))
      .catch(error => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  if (message?.type === "PG_ANALYZE") {
    const language = detectPromptLanguage(message.text);
    bridgeJson("/v1/browser/analyze", {
      text: message.text,
      profile_key: "property_management",
      language
    })
      .then(response => sendResponse({ ...response, detectedLanguage: language }))
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
  const profileKey =
    typeof message.profileKey === "string" && message.profileKey.trim()
      ? message.profileKey.trim()
      : "general_business";
  const language = message.language === "it" ? "it" : "en";
  const response = await bridgeJson("/v1/browser/pdf/analyze", {
    filename: message.filename,
    file_base64: message.fileBase64,
    profile_key: profileKey,
    language
  });
  return { ...response, detectedLanguage: language, profileKey };
}

async function protectPdfForConversation(message, sender) {
  let sessionId = await SessionRegistry.getSessionForSender(sender);

  const request = id => bridgeJson("/v1/browser/pdf/protect", {
    analysis_id: message.analysisId,
    finding_ids: Array.isArray(message.findingIds) ? message.findingIds : [],
    session_id: id || null
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
