const BRIDGE = "http://127.0.0.1:8765";

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
      fetch(`${BRIDGE}/v1/browser/analyze`, {
        method: "POST",
        cache: "no-store",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          text: message.text,
          profile_key: "property_management",
          language: "en"
        })
      })
        .then(async response => {
          const data = await response.json();

          sendResponse({
            ok: response.ok,
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
  }
);