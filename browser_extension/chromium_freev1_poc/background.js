const BRIDGE = "http://127.0.0.1:8765";

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
      bridgeJson("/v1/browser/analyze", {
        text: message.text,
        profile_key: "property_management",
        language: "en"
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

    if (message?.type === "PG_PROTECT") {
      bridgeJson("/v1/browser/protect", {
        text: message.text,
        profile_key: "property_management",
        language: "en",
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
