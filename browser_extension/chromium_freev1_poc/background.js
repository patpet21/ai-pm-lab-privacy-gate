const BRIDGE = "http://127.0.0.1:8765";

let lastAnalyzeDiagnostic = null;

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function bridgeJson(path, body, attempt = 0) {
  try {
    const response = await fetch(`${BRIDGE}${path}`, {
      method: "POST",
      cache: "no-store",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(body)
    });

    let data = {};
    try {
      data = await response.json();
    } catch (_error) {
      data = { error: "invalid_bridge_response" };
    }

    if (!response.ok && response.status >= 500 && attempt < 1) {
      await sleep(160);
      return bridgeJson(path, body, attempt + 1);
    }

    return {
      ok: response.ok,
      status: response.status,
      data
    };
  } catch (error) {
    if (attempt < 1) {
      await sleep(160);
      return bridgeJson(path, body, attempt + 1);
    }

    return {
      ok: false,
      status: 0,
      error: String(error),
      data: { error: "bridge_unreachable" }
    };
  }
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
            status: 0,
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
        .then(response => {
          if (response.ok) {
            lastAnalyzeDiagnostic = null;
          } else {
            lastAnalyzeDiagnostic = {
              status: Number(response.status || 0),
              code: String(response.data?.error || "unknown_error"),
              networkError: response.error ? String(response.error) : null
            };
          }
          sendResponse(response);
        })
        .catch(error => {
          lastAnalyzeDiagnostic = {
            status: 0,
            code: "bridge_unreachable",
            networkError: String(error)
          };
          sendResponse({
            ok: false,
            status: 0,
            error: String(error),
            data: { error: "bridge_unreachable" }
          });
        });

      return true;
    }

    if (message?.type === "PG_ANALYZE_DIAGNOSTIC") {
      sendResponse({
        ok: true,
        diagnostic: lastAnalyzeDiagnostic
      });
      return false;
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
            status: 0,
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
            status: 0,
            error: String(error)
          });
        });

      return true;
    }
  }
);
