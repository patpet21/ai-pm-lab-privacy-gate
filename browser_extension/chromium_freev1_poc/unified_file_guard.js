(() => {
  "use strict";

  if (window.top !== window) return;
  const host = location.hostname.toLowerCase();
  if (!new Set(["chatgpt.com", "claude.ai", "gemini.google.com"]).has(host)) return;

  const STORAGE_KEY = "privacygateProtectionEnabled";
  const LANGUAGE_KEY = "privacygateDocumentLanguageV1";
  const REVIEW_SOURCE = "privacygate-file-review";
  const MAX_BYTES = 12 * 1024 * 1024;
  const SUPPORTED = new Set([".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".png", ".jpg", ".jpeg"]);
  const ACCEPT = ".pdf,.docx,.xlsx,.pptx,.txt,.png,.jpg,.jpeg,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.openxmlformats-officedocument.presentationml.presentation,text/plain,image/png,image/jpeg";

  let enabled = true;
  let busy = false;
  let internalInjecting = false;
  let pendingProtectedFile = null;
  let reviewFrame = null;
  let reviewReady = false;
  let reviewResolve = null;
  let reviewPayload = null;
  let attachedProtectedFilename = "";
  let attachedExpiresAt = 0;
  let sentClearTimer = null;

  function providerName() {
    if (host === "claude.ai") return "Claude";
    if (host === "gemini.google.com") return "Gemini";
    return "ChatGPT";
  }

  function suffixOf(name) {
    const match = String(name || "").toLowerCase().match(/(\.[a-z0-9]+)$/);
    return match ? match[1] : "";
  }

  function isSupported(file) {
    return file instanceof File && SUPPORTED.has(suffixOf(file.name));
  }

  function protectedMime(file) {
    const suffix = suffixOf(file.name);
    const bySuffix = {
      ".pdf": "application/pdf",
      ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
      ".txt": "text/plain",
      ".png": "image/png",
      ".jpg": "image/jpeg",
      ".jpeg": "image/jpeg"
    };
    return bySuffix[suffix] || file.type || "application/octet-stream";
  }

  function stop(event) {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
  }

  function notice(message, kind = "normal") {
    let node = document.getElementById("privacygate-unified-file-notice");
    if (!node) {
      node = document.createElement("div");
      node.id = "privacygate-unified-file-notice";
      node.setAttribute("role", "status");
      Object.assign(node.style, {
        position: "fixed",
        left: "50%",
        top: "50%",
        transform: "translate(-50%,-50%)",
        zIndex: "2147483647",
        maxWidth: "min(620px,calc(100vw - 32px))",
        padding: "12px 16px",
        borderRadius: "10px",
        color: "#fff",
        textAlign: "center",
        fontFamily: "Arial,sans-serif",
        fontSize: "13px",
        fontWeight: "750",
        boxShadow: "0 8px 30px rgba(0,0,0,.30)"
      });
      document.documentElement.appendChild(node);
    }
    node.style.background = kind === "success" ? "#065f46" : kind === "error" ? "#991b1b" : "#111827";
    node.textContent = String(message || "");
    clearTimeout(window.__privacyGateUnifiedFileNoticeTimer);
    window.__privacyGateUnifiedFileNoticeTimer = setTimeout(() => node.remove(), 4800);
  }

  function setBusy(value, label = "PrivacyGate processing file locally…") {
    busy = Boolean(value);
    document.getElementById("privacygate-unified-file-working")?.remove();
    if (!busy) return;
    const overlay = document.createElement("div");
    overlay.id = "privacygate-unified-file-working";
    Object.assign(overlay.style, {
      position: "fixed", inset: "0", zIndex: "2147483646", display: "flex",
      alignItems: "center", justifyContent: "center", background: "rgba(15,23,42,.34)",
      backdropFilter: "blur(2px)", fontFamily: "Arial,sans-serif"
    });
    const pill = document.createElement("div");
    Object.assign(pill.style, {
      padding: "13px 18px", borderRadius: "999px", background: "#fff", color: "#273247",
      border: "1px solid #d8e1ec", boxShadow: "0 14px 40px rgba(15,23,42,.24)",
      fontSize: "13px", fontWeight: "750"
    });
    pill.textContent = label;
    overlay.appendChild(pill);
    document.documentElement.appendChild(overlay);
  }

  function runtimeMessage(message) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(message, response => {
        if (chrome.runtime.lastError) return reject(new Error(chrome.runtime.lastError.message));
        resolve(response);
      });
    });
  }

  function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(reader.error || new Error("Unable to read file"));
      reader.onload = () => {
        const value = String(reader.result || "");
        const comma = value.indexOf(",");
        if (comma < 0) return reject(new Error("Unable to encode file"));
        resolve(value.slice(comma + 1));
      };
      reader.readAsDataURL(file);
    });
  }

  function base64ToFile(encoded, filename, original) {
    const binary = atob(String(encoded || ""));
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    return new File([bytes], filename, { type: protectedMime({ name: filename, type: original?.type }), lastModified: Date.now() });
  }

  async function settings() {
    const [extension, local] = await Promise.all([
      runtimeMessage({ type: "PG_GET_EXTENSION_SETTINGS" }),
      new Promise(resolve => chrome.storage.local.get({ [LANGUAGE_KEY]: "en" }, resolve))
    ]);
    return {
      profileKey: extension?.profileKey || "general_business",
      language: local?.[LANGUAGE_KEY] === "it" ? "it" : "en"
    };
  }

  function saveLanguage(language) {
    chrome.storage.local.set({ [LANGUAGE_KEY]: language === "it" ? "it" : "en" });
  }

  function composer() {
    if (host === "chatgpt.com") {
      return document.querySelector("#prompt-textarea") || document.querySelector('[contenteditable="true"]');
    }
    if (host === "claude.ai") {
      return document.querySelector('div.ProseMirror[contenteditable="true"]') ||
        document.querySelector('[contenteditable="true"][data-placeholder]') ||
        document.querySelector('fieldset [contenteditable="true"]') ||
        document.querySelector('textarea[placeholder*="message" i]') || document.querySelector("textarea");
    }
    return document.querySelector('rich-textarea [contenteditable="true"]') ||
      document.querySelector('.ql-editor[contenteditable="true"]') ||
      document.querySelector('[contenteditable="true"][aria-label*="prompt" i]') ||
      document.querySelector('[contenteditable="true"][aria-label*="message" i]') ||
      document.querySelector('textarea[aria-label*="prompt" i]') || document.querySelector("textarea");
  }

  function composerText(box = composer()) {
    if (!box) return "";
    if (box instanceof HTMLTextAreaElement || box instanceof HTMLInputElement) return box.value || "";
    return box.innerText || box.textContent || "";
  }

  function sendButton() {
    const box = composer();
    if (!box) return null;
    const scope = box.closest("form") || box.closest("fieldset") || box.closest("rich-textarea")?.parentElement?.parentElement || box.parentElement?.parentElement || document;
    const selectors = [
      'button[data-testid="send-button"]', 'button[data-testid*="send" i]',
      'button[data-test-id*="send" i]', 'button[aria-label*="send" i]',
      'button[aria-label*="submit" i]', 'button[type="submit"]'
    ];
    for (const selector of selectors) {
      const item = Array.from(scope.querySelectorAll?.(selector) || []).find(node => node instanceof HTMLElement && !node.closest('[id^="privacygate-"]'));
      if (item) return item;
    }
    return null;
  }

  function setComposerText(box, text) {
    try {
      if (box instanceof HTMLTextAreaElement || box instanceof HTMLInputElement) {
        const proto = box instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
        const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
        if (setter) setter.call(box, text); else box.value = text;
      } else {
        box.textContent = text;
      }
      box.dispatchEvent(new InputEvent("input", { bubbles: true, composed: true, inputType: "insertText", data: text }));
      return true;
    } catch (_error) {
      return false;
    }
  }

  async function ensureAttachmentOnlySendReady() {
    await new Promise(resolve => setTimeout(resolve, 180));
    const box = composer();
    if (!box || composerText(box).trim()) return;
    const button = sendButton();
    const disabled = !button || button.getAttribute("aria-disabled") === "true" || (button instanceof HTMLButtonElement && button.disabled);
    if (disabled) setComposerText(box, "Analyze the attached file.");
  }

  function nativeInputs() {
    return Array.from(document.querySelectorAll('input[type="file"]')).filter(input =>
      input instanceof HTMLInputElement && input.isConnected && !input.id?.startsWith("privacygate-") && !input.closest?.('[id^="privacygate-"]')
    );
  }

  function bestInput(preferred = null) {
    if (preferred instanceof HTMLInputElement && preferred.isConnected) return preferred;
    const inputs = nativeInputs();
    if (!inputs.length) return null;
    const accepting = inputs.find(input => {
      const value = String(input.accept || "").toLowerCase();
      return !value || /pdf|word|sheet|excel|presentation|powerpoint|image|text|docx|xlsx|pptx/.test(value);
    });
    return accepting || inputs[0];
  }

  function injectProtected(input, file) {
    const target = bestInput(input);
    if (!target) return false;
    const transfer = new DataTransfer();
    transfer.items.add(file);
    internalInjecting = true;
    try {
      target.files = transfer.files;
      target.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
      target.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
      return true;
    } catch (_error) {
      return false;
    } finally {
      queueMicrotask(() => { internalInjecting = false; });
    }
  }

  function markAttached(filename) {
    attachedProtectedFilename = String(filename || "");
    attachedExpiresAt = Date.now() + 15 * 60 * 1000;
  }

  function hasAttached() {
    if (!attachedProtectedFilename || attachedExpiresAt <= Date.now()) {
      attachedProtectedFilename = "";
      attachedExpiresAt = 0;
      return false;
    }
    return true;
  }

  function clearAttached() {
    attachedProtectedFilename = "";
    attachedExpiresAt = 0;
  }

  function markSendAttempt() {
    clearTimeout(sentClearTimer);
    sentClearTimer = setTimeout(clearAttached, 5000);
  }

  globalThis.PrivacyGateFileState = Object.freeze({
    hasAttached,
    filename: () => hasAttached() ? attachedProtectedFilename : "",
    clear: clearAttached,
    markSendAttempt
  });

  function closeReview(result = null) {
    const resolver = reviewResolve;
    reviewResolve = null;
    reviewReady = false;
    reviewPayload = null;
    reviewFrame?.remove();
    reviewFrame = null;
    if (resolver) resolver(result);
  }

  function showReview(file, analyzed, currentSettings) {
    return new Promise(resolve => {
      closeReview();
      reviewResolve = resolve;
      reviewPayload = {
        filename: file.name,
        findings: Array.isArray(analyzed?.findings) ? analyzed.findings : [],
        profileKey: currentSettings.profileKey,
        language: currentSettings.language
      };
      const frame = document.createElement("iframe");
      frame.id = "privacygate-file-review-frame";
      frame.src = chrome.runtime.getURL("file_review_overlay.html");
      frame.title = "PrivacyGate local file review";
      frame.referrerPolicy = "no-referrer";
      Object.assign(frame.style, {
        position: "fixed", inset: "0", width: "100vw", height: "100vh", border: "0",
        zIndex: "2147483647", background: "transparent"
      });
      reviewFrame = frame;
      document.documentElement.appendChild(frame);
      frame.addEventListener("load", () => {
        if (reviewFrame !== frame || !reviewPayload) return;
        frame.contentWindow?.postMessage({ source: REVIEW_SOURCE, type: "PG_FILE_REVIEW_INIT", payload: reviewPayload }, new URL(chrome.runtime.getURL("/")).origin);
      });
    });
  }

  window.addEventListener("message", event => {
    if (!reviewFrame || event.source !== reviewFrame.contentWindow) return;
    const data = event.data;
    if (!data || data.source !== REVIEW_SOURCE) return;
    if (data.type === "PG_FILE_REVIEW_READY") {
      reviewReady = true;
      if (reviewPayload) reviewFrame.contentWindow?.postMessage({ source: REVIEW_SOURCE, type: "PG_FILE_REVIEW_INIT", payload: reviewPayload }, new URL(chrome.runtime.getURL("/")).origin);
      return;
    }
    if (data.type !== "PG_FILE_REVIEW_RESULT") return;
    closeReview({
      action: data.action,
      findingIds: Array.isArray(data.findingIds) ? data.findingIds : [],
      profileKey: String(data.profileKey || "general_business"),
      language: data.language === "it" ? "it" : "en"
    });
  });

  function errorMessage(response) {
    const code = response?.data?.error || response?.error || "local_service_error";
    const detail = response?.data?.message;
    if (code === "browser_pairing_required") return "PrivacyGate — browser pairing is required. The original file was not attached.";
    if (code === "file_operation_busy") return "PrivacyGate — another file is already being processed locally. Nothing was attached.";
    if (code === "file_operation_timeout") return "PrivacyGate — local file processing timed out. Nothing was attached.";
    if (code === "already_protected_document") return "PrivacyGate — this file is already protected. Automatic double protection was blocked.";
    if (code === "document_has_no_readable_text") return `PrivacyGate — ${detail || "no readable text was found in this file"}. Nothing was attached.`;
    if (response?.status) return `PrivacyGate — file protection failed (HTTP ${response.status}: ${code})${detail ? ` — ${detail}` : ""}. Nothing was attached.`;
    return "PrivacyGate — Local Privacy Bridge is unavailable. Nothing was attached.";
  }

  async function analyze(file, fileBase64, currentSettings) {
    return runtimeMessage({
      type: "PG_FILE_ANALYZE",
      filename: file.name,
      fileBase64,
      profileKey: currentSettings.profileKey,
      language: currentSettings.language
    });
  }

  async function protect(file, input = null) {
    if (!enabled || busy) return;
    if (!isSupported(file)) {
      notice("PrivacyGate — supported files: PDF, DOCX, XLSX, PPTX, TXT, PNG, JPG/JPEG. The original was not attached.", "error");
      return;
    }
    if (file.size <= 0 || file.size > MAX_BYTES) {
      notice("PrivacyGate — browser files must be between 1 byte and 12 MB. Nothing was attached.", "error");
      return;
    }

    busy = true;
    pendingProtectedFile = null;
    clearAttached();
    try {
      const fileBase64 = await fileToBase64(file);
      let currentSettings = await settings();
      let analyzed;
      let decision;

      while (true) {
        setBusy(true, `PrivacyGate scanning ${suffixOf(file.name).toUpperCase()} locally…`);
        analyzed = await analyze(file, fileBase64, currentSettings);
        setBusy(false);
        if (!analyzed?.ok) {
          notice(errorMessage(analyzed), "error");
          return;
        }

        const findings = Array.isArray(analyzed.data?.findings) ? analyzed.data.findings : [];
        if (!findings.length) {
          decision = { action: "protect", findingIds: [], profileKey: currentSettings.profileKey, language: currentSettings.language };
          break;
        }

        decision = await showReview(file, analyzed.data, currentSettings);
        if (!decision || decision.action === "cancel") return;
        currentSettings = { profileKey: decision.profileKey, language: decision.language };
        saveLanguage(currentSettings.language);
        if (decision.action === "rescan") continue;
        break;
      }

      setBusy(true, `PrivacyGate creating protected ${suffixOf(file.name).toUpperCase()}…`);
      const protectedResponse = await runtimeMessage({
        type: "PG_FILE_PROTECT",
        analysisId: analyzed.data.analysis_id,
        findingIds: decision.findingIds
      });
      setBusy(false);
      if (!protectedResponse?.ok) {
        notice(errorMessage(protectedResponse), "error");
        return;
      }

      const encoded = protectedResponse.data?.protected_file_base64;
      const filename = protectedResponse.data?.protected_filename;
      if (typeof encoded !== "string" || !encoded || typeof filename !== "string" || !filename) {
        throw new Error("Protected file payload is incomplete");
      }
      const protectedFile = base64ToFile(encoded, filename, file);
      if (injectProtected(input, protectedFile)) {
        markAttached(filename);
        await ensureAttachmentOnlySendReady();
        notice(`PrivacyGate — ${filename} protected locally and attached.`, "success");
        return;
      }

      pendingProtectedFile = protectedFile;
      notice(`PrivacyGate — ${filename} is protected and ready. Click ${providerName()}'s Attach button once; PrivacyGate will insert the protected copy only.`, "normal");
    } catch (error) {
      setBusy(false);
      notice(`PrivacyGate — ${String(error?.message || error)}. Nothing was attached.`, "error");
    } finally {
      busy = false;
      setBusy(false);
    }
  }

  document.addEventListener("change", event => {
    const input = event.target;
    if (!(input instanceof HTMLInputElement) || input.type !== "file" || input.id?.startsWith("privacygate-")) return;
    if (internalInjecting || !event.isTrusted || !enabled) return;
    const files = Array.from(input.files || []);
    if (!files.length) return;
    stop(event);
    input.value = "";
    if (files.length !== 1) {
      notice("PrivacyGate — attach one file at a time while protection is ON. Nothing was attached.", "error");
      return;
    }
    protect(files[0], input);
  }, true);

  document.addEventListener("drop", event => {
    if (internalInjecting || !event.isTrusted || !enabled) return;
    const files = Array.from(event.dataTransfer?.files || []);
    if (!files.length) return;
    stop(event);
    if (files.length !== 1) {
      notice("PrivacyGate — drop one file at a time. Nothing was attached.", "error");
      return;
    }
    protect(files[0], bestInput());
  }, true);

  document.addEventListener("paste", event => {
    if (internalInjecting || !event.isTrusted || !enabled) return;
    const files = Array.from(event.clipboardData?.files || []);
    if (!files.length) return;
    stop(event);
    if (files.length !== 1) {
      notice("PrivacyGate — paste one file at a time. Nothing was attached.", "error");
      return;
    }
    protect(files[0], bestInput());
  }, true);

  document.addEventListener("click", event => {
    if (!pendingProtectedFile || !(event.target instanceof Element)) return;
    const input = event.target.closest('input[type="file"]');
    if (!(input instanceof HTMLInputElement)) return;
    stop(event);
    const file = pendingProtectedFile;
    if (injectProtected(input, file)) {
      pendingProtectedFile = null;
      markAttached(file.name);
      ensureAttachmentOnlySendReady();
      notice(`PrivacyGate — ${file.name} protected locally and attached.`, "success");
    } else {
      notice("PrivacyGate — the provider did not expose a usable upload input. The original file was not sent.", "error");
    }
  }, true);

  function isSendGesture(event) {
    const box = composer();
    if (!box) return false;
    if (event.type === "keydown") {
      return event.key === "Enter" && !event.shiftKey && !event.ctrlKey && !event.altKey && !event.metaKey && (event.target === box || box.contains?.(event.target));
    }
    if (event.type === "submit") return event.target instanceof HTMLFormElement && event.target.contains(box);
    if (event.type === "click") {
      const button = event.target instanceof Element ? event.target.closest('button,[role="button"]') : null;
      const send = sendButton();
      return Boolean(button && send && (button === send || send.contains(button)));
    }
    return false;
  }

  for (const type of ["keydown", "submit", "click"]) {
    document.addEventListener(type, event => {
      if (event.isTrusted && hasAttached() && isSendGesture(event)) markSendAttempt();
    }, true);
  }

  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && reviewFrame) {
      stop(event);
      closeReview({ action: "cancel" });
    }
  }, true);

  chrome.storage.local.get({ [STORAGE_KEY]: true }, values => {
    enabled = values?.[STORAGE_KEY] !== false;
  });
  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName !== "local" || !changes[STORAGE_KEY]) return;
    enabled = changes[STORAGE_KEY].newValue !== false;
    if (!enabled) {
      closeReview({ action: "cancel" });
      setBusy(false);
      pendingProtectedFile = null;
      clearAttached();
    }
  });
})();
