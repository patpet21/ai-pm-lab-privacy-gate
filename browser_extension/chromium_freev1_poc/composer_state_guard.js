(() => {
  "use strict";

  if (window.top !== window) return;

  const PLACEHOLDER_MARKER = "[[PG_";
  const nativeButtonClick = HTMLButtonElement.prototype.click;
  let protectedSendBusy = false;

  function composer() {
    return (
      document.querySelector("#prompt-textarea") ||
      document.querySelector('[contenteditable="true"]')
    );
  }

  function composerText(box) {
    if (!box) return "";
    if (box instanceof HTMLTextAreaElement || box instanceof HTMLInputElement) {
      return box.value || "";
    }
    return box.innerText || box.textContent || "";
  }

  function normalized(text) {
    return String(text || "")
      .replace(/\r\n?/g, "\n")
      .replace(/\u00a0/g, " ")
      .replace(/[ \t]+\n/g, "\n")
      .trim();
  }

  function isSendButton(button) {
    return Boolean(
      button?.matches?.(
        'button[data-testid="send-button"],' +
        'button[aria-label*="send" i],' +
        'button[aria-label*="submit" i]'
      )
    );
  }

  function notice(message) {
    document.getElementById("privacygate-composer-sync-error")?.remove();
    const element = document.createElement("div");
    element.id = "privacygate-composer-sync-error";
    Object.assign(element.style, {
      position: "fixed",
      left: "50%",
      top: "50%",
      transform: "translate(-50%, -50%)",
      zIndex: "2147483647",
      maxWidth: "520px",
      padding: "13px 17px",
      borderRadius: "12px",
      background: "#991b1b",
      color: "#fff",
      fontFamily: "Arial, sans-serif",
      fontSize: "13px",
      fontWeight: "700",
      boxShadow: "0 12px 36px rgba(0,0,0,.30)"
    });
    element.textContent = message;
    document.documentElement.appendChild(element);
    setTimeout(() => element.remove(), 5000);
  }

  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  async function verifyProtectedComposer(protectedText) {
    const expected = normalized(protectedText);
    if (!expected.includes(PLACEHOLDER_MARKER)) return false;

    // Do not mutate the editor here. content.js must have committed the protected
    // text through the browser editing pipeline already. We only verify that the
    // site's own re-render keeps the exact protected value stable before Send.
    for (const delay of [180, 280, 420, 620]) {
      await sleep(delay);
      const box = composer();
      const current = normalized(composerText(box));
      if (
        !box ||
        current !== expected ||
        !current.includes(PLACEHOLDER_MARKER)
      ) {
        return false;
      }
    }

    return true;
  }

  HTMLButtonElement.prototype.click = function privacyGateVerifiedClick() {
    const button = this;
    const box = composer();
    const currentText = composerText(box);

    if (
      !isSendButton(button) ||
      !currentText.includes(PLACEHOLDER_MARKER)
    ) {
      return nativeButtonClick.call(button);
    }

    if (protectedSendBusy) return;
    protectedSendBusy = true;
    const protectedText = currentText;

    verifyProtectedComposer(protectedText)
      .then(ok => {
        if (!ok) {
          notice(
            "PrivacyGate blocked Send because the protected composer was not stable. Nothing was sent."
          );
          return;
        }
        nativeButtonClick.call(button);
      })
      .catch(() => {
        notice("PrivacyGate could not verify the protected composer. Nothing was sent.");
      })
      .finally(() => {
        protectedSendBusy = false;
      });
  };
})();
