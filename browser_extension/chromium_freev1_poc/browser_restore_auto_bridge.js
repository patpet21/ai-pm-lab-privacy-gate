(() => {
  "use strict";

  const BRIDGE_PORT_KEY = "privacygateBridgePort";
  const BROWSER_TOKEN_KEY = "privacygateBrowserCredentialV1";
  const DEFAULT_BRIDGE_PORT = 8765;

  function responseJson(response) {
    return response.json().catch(() => ({}));
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type !== "PG_RESTORE_AUTO") return;

    (async () => {
      const text = String(message.text || "");
      if (!text.trim()) {
        return { ok: false, status: 400, data: { error: "text_required" } };
      }

      const values = await chrome.storage.local.get({
        [BRIDGE_PORT_KEY]: DEFAULT_BRIDGE_PORT,
        [BROWSER_TOKEN_KEY]: null
      });
      const port = Number.parseInt(String(values?.[BRIDGE_PORT_KEY] ?? ""), 10);
      const safePort = Number.isInteger(port) && port >= 1024 && port <= 65535
        ? port
        : DEFAULT_BRIDGE_PORT;
      const token = values?.[BROWSER_TOKEN_KEY];
      if (typeof token !== "string" || token.length < 24) {
        return { ok: false, status: 401, data: { error: "browser_pairing_required" } };
      }

      const response = await fetch(
        `http://127.0.0.1:${safePort}/v1/browser/restore-auto`,
        {
          method: "POST",
          cache: "no-store",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`
          },
          body: JSON.stringify({ text })
        }
      );
      const data = await responseJson(response);
      return { ok: response.ok, status: response.status, data };
    })()
      .then(sendResponse)
      .catch(error => sendResponse({ ok: false, error: String(error) }));

    return true;
  });
})();
