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

  function forceEditorInput(box, protectedText) {
    if (!box) return false;
    box.focus();

    if (box instanceof HTMLTextAreaElement || box instanceof HTMLInputElement) {
      const prototype = box instanceof HTMLTextAreaElement
        ? HTMLTextAreaElement.prototype
        : HTMLInputElement.prototype;
      const descriptor = Object.getOwnPropertyDescriptor(prototype, "value");
      descriptor?.set?.call(box, protectedText);
      box.dispatchEvent(new InputEvent("input", {
        bubbles: true,
        inputType: "insertText",
        data: protectedText
      }));
      return normalized(composerText(box)) === normalized(protectedText);
    }

    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(box);
    selection?.removeAllRanges();
    selection?.addRange(range);

    let inserted = false;
    try {
      inserted = document.execCommand("insertText", false, protectedText);
    } catch (_error) {
      inserted = false;
    }

    // Let React/Lexical/ProseMirror-style editors observe an editing event.
    box.dispatchEvent(new InputEvent("input", {
      bubbles: true,
      composed: true,
      inputType: "insertText",
      data: protectedText
    }));

    return inserted && normalized(composerText(box)) === normalized(protectedText);
  }

  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  async function verifyProtectedComposer(protectedText) {
    const expected = normalized(protectedText);
    let box = composer();
    if (!box || !expected.includes(PLACEHOLDER_MARKER)) return false;

    // Re-apply through the browser editing pipeline so the site's editor state,
    // not only the visible DOM, has a chance to accept the protected text.
    forceEditorInput(box, protectedText);

    for (const delay of [120, 220, 360]) {
      await sleep(delay);
      box = composer();
      const current = normalized(composerText(box));
      if (current !== expected) {
        // One guarded retry; if ChatGPT restores the original text, fail closed.
        if (!box || !forceEditorInput(box, protectedText)) return false;
      }
    }

    await sleep(180);
    box = composer();
    return Boolean(
      box &&
      normalized(composerText(box)) === expected &&
      normalized(composerText(box)).includes(PLACEHOLDER_MARKER)
    );
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
            "PrivacyGate blocked Send because ChatGPT restored the original composer state. Nothing was sent."
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
