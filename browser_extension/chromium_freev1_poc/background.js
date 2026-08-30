const BRIDGE = "http://127.0.0.1:8765";

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

  if (/[àèéìòù]/u.test(raw)) {
    return "it";
  }

  const words = raw.match(/[a-zà-ÿ']+/giu) || [];
  let italian = 0;
  let english = 0;

  for (const word of words) {
    if (ITALIAN_HINTS.has(word)) italian += 1;
    if (ENGLISH_HINTS.has(word)) english += 1;
  }

  if (italian >= 2 && italian > english) {
    return "it";
  }

  if (english >= 2 && english > italian) {
    return "en";
  }

  // Keep the historical default for ambiguous names, IDs, emails and short text.
  return "en";
}

async function bridgeJson(path, body) {
  const response = await fetch(`${BRIDGE}${path}`, {
    method: "POST",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(body)
  });

  const data = await response.json();
  return {
    ok: response.ok,
    status: response.status,
    data
  };
}

chrome.runtime.onMessage.addListener(
  (message, sender, sendResponse) => {
    if (message?.type === "PG_BRIDGE_STATUS") {
      fetch(`${BRIDGE}/v1/status`, {
        method: "GET",
        cache: "no-store"
      })
        .then(async response => {
          const data = await response.json();
          sendResponse({
            ok: response.ok && data.status === "ready",
            status: response.status,
            data
          });
        })
        .catch(error => {
          sendResponse({
            ok: false,
            error: String(error)
          });
        });

      return true;
    }

    if (message?.type === "PG_ANALYZE") {
      const language = detectPromptLanguage(message.text);

      bridgeJson("/v1/browser/analyze", {
        text: message.text,
        profile_key: "property_management",
        language
      })
        .then(response => {
          sendResponse({
            ...response,
            detectedLanguage: language
          });
        })
        .catch(error => {
          sendResponse({
            ok: false,
            error: String(error)
          });
        });

      return true;
    }

    if (message?.type === "PG_PROTECT") {
      const language = detectPromptLanguage(message.text);

      bridgeJson("/v1/browser/protect", {
        text: message.text,
        profile_key: "property_management",
        language,
        finding_ids: Array.isArray(message.findingIds)
          ? message.findingIds
          : [],
        replacement_mode: "reversible",
        session_id: message.sessionId || null
      })
        .then(sendResponse)
        .catch(error => {
          sendResponse({
            ok: false,
            error: String(error)
          });
        });

      return true;
    }

    if (message?.type === "PG_RESTORE") {
      bridgeJson("/v1/browser/restore", {
        text: message.text,
        session_id: message.sessionId
      })
        .then(sendResponse)
        .catch(error => {
          sendResponse({
            ok: false,
            error: String(error)
          });
        });

      return true;
    }
  }
);
