const BRIDGE = "http://127.0.0.1:8765";
const BROWSER_TOKEN_KEY = "privacygateBrowserCredentialV1";

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

async function bridgeStatus() {
  const token = await getBrowserToken();
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`${BRIDGE}/v1/browser/status`, {
    method: "GET",
    cache: "no-store",
    headers
  });
  const data = await response.json();
  const paired = Boolean(response.ok && data?.paired);
  if (token && response.ok && !paired) {
    await setBrowserToken(null);
  }
  return {
    ok: response.ok && paired,
    bridgeReady: response.ok && data?.status === "ready",
    paired,
    status: response.status,
    data
  };
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
          sendResponse({ ok: true, paired: true });
          return;
        }
        sendResponse({ ...response, paired: false });
      })
      .catch(error => sendResponse({ ok: false, paired: false, error: String(error) }));
    return true;
  }

  if (message?.type === "PG_FORGET_PAIRING") {
    setBrowserToken(null)
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
    const language = detectPromptLanguage(message.text);
    bridgeJson("/v1/browser/protect", {
      text: message.text,
      profile_key: "property_management",
      language,
      finding_ids: Array.isArray(message.findingIds) ? message.findingIds : [],
      replacement_mode: "reversible",
      session_id: message.sessionId || null
    })
      .then(sendResponse)
      .catch(error => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  if (message?.type === "PG_RESTORE") {
    bridgeJson("/v1/browser/restore", {
      text: message.text,
      session_id: message.sessionId
    })
      .then(sendResponse)
      .catch(error => sendResponse({ ok: false, error: String(error) }));
    return true;
  }
});
