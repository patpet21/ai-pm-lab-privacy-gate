(() => {
  "use strict";

  if (window.top !== window) return;

  const LANGUAGE_STORAGE_KEY = "privacygatePdfLanguageV1";
  const SUCCESS_PATTERN = /protected locally and attached/i;
  let lastHandledText = "";
  let hintTimer = null;

  function style(element, values) {
    Object.assign(element.style, values);
    return element;
  }

  function providerName() {
    const host = location.hostname.toLowerCase();
    if (host === "gemini.google.com") return "Gemini";
    if (host === "claude.ai" || host.endsWith(".claude.ai")) return "Claude";
    return "ChatGPT";
  }

  function composer() {
    return (
      document.querySelector("#prompt-textarea") ||
      document.querySelector('rich-textarea [contenteditable="true"]') ||
      document.querySelector('[data-testid*="composer"] [contenteditable="true"]') ||
      document.querySelector('[contenteditable="true"][role="textbox"]') ||
      document.querySelector("textarea") ||
      document.querySelector('[contenteditable="true"]')
    );
  }

  function composerText() {
    const box = composer();
    if (!box) return "";
    if (box instanceof HTMLTextAreaElement || box instanceof HTMLInputElement) {
      return box.value || "";
    }
    return box.innerText || box.textContent || "";
  }

  function focusComposer() {
    const box = composer();
    if (!(box instanceof HTMLElement)) return;
    box.focus();

    if (box.isContentEditable) {
      const selection = window.getSelection();
      if (!selection) return;
      const range = document.createRange();
      range.selectNodeContents(box);
      range.collapse(false);
      selection.removeAllRanges();
      selection.addRange(range);
    }
  }

  function showHint(message) {
    document.getElementById("privacygate-pdf-post-attach-hint")?.remove();

    const element = style(document.createElement("div"), {
      position: "fixed",
      left: "50%",
      top: "50%",
      transform: "translate(-50%, -50%)",
      zIndex: "2147483647",
      width: "max-content",
      maxWidth: "min(560px, calc(100vw - 32px))",
      padding: "13px 17px",
      borderRadius: "11px",
      background: "#111827",
      color: "#ffffff",
      textAlign: "center",
      fontFamily: "Arial, sans-serif",
      fontSize: "13px",
      fontWeight: "700",
      lineHeight: "1.45",
      boxShadow: "0 12px 36px rgba(0,0,0,.32)"
    });
    element.id = "privacygate-pdf-post-attach-hint";
    element.setAttribute("role", "status");
    element.setAttribute("aria-live", "polite");
    element.textContent = message;
    document.documentElement.appendChild(element);

    setTimeout(() => element.remove(), 7200);
  }

  function getLanguage() {
    return new Promise(resolve => {
      chrome.storage.local.get({ [LANGUAGE_STORAGE_KEY]: "en" }, values => {
        resolve(values?.[LANGUAGE_STORAGE_KEY] === "it" ? "it" : "en");
      });
    });
  }

  async function showPostAttachInstruction() {
    const language = await getLanguage();
    const hasPrompt = Boolean(composerText().trim());
    const provider = providerName();

    let message;
    if (language === "it") {
      message = hasPrompt
        ? `PDF protetto e allegato. La tua richiesta è pronta: premi Invio per inviarla a ${provider}.`
        : `PDF protetto e allegato. Puoi inviarlo direttamente a ${provider} oppure aggiungere una domanda o un'istruzione.`;
    } else {
      message = hasPrompt
        ? `PDF protected and attached. Your request is ready: press Send to submit it to ${provider}.`
        : `PDF protected and attached. You can send it directly to ${provider}, or add a question or instruction first.`;
    }

    showHint(message);
    setTimeout(focusComposer, 80);
  }

  function inspectSuccessNotice() {
    const element = document.getElementById("privacygate-pdf-notice");
    const text = String(element?.textContent || "").trim();
    if (!text || !SUCCESS_PATTERN.test(text) || text === lastHandledText) return;

    lastHandledText = text;
    clearTimeout(hintTimer);
    hintTimer = setTimeout(showPostAttachInstruction, 1600);
  }

  const observer = new MutationObserver(inspectSuccessNotice);
  observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true
  });

  inspectSuccessNotice();
})();
