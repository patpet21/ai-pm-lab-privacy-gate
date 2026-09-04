(() => {
  "use strict";

  if (window.top !== window) return;
  const host = location.hostname.toLowerCase();
  if (!new Set(["claude.ai", "gemini.google.com"]).has(host)) return;

  const STORAGE_KEY = "privacygateProtectionEnabled";
  const LANGUAGE_STORAGE_KEY = "privacygateDocumentLanguageV1";
  const MAX_FILE_BYTES = 12 * 1024 * 1024;
  const ACCEPT = ".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document";
  const PROFILE_OPTIONS = [
    ["general_business", "General — Recommended"],
    ["property_management", "Property Management"],
    ["realtor_brokerage", "Realtor / Brokerage"],
    ["projects_renovations", "Projects & Renovations"],
    ["construction", "Construction"],
    ["legal", "Legal"],
    ["healthcare_general", "Healthcare — General"]
  ];

  let protectionEnabled = true;
  let busy = false;
  let internalInjecting = false;
  let pendingProtectedFile = null;
  let pendingDropTarget = null;
  let attachFlowTimer = null;

  function style(el, values) {
    Object.assign(el.style, values);
    return el;
  }

  function stop(event) {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
  }

  function providerName() {
    return host === "claude.ai" ? "Claude" : "Gemini";
  }

  function fileKind(file) {
    if (!(file instanceof File)) return null;
    const name = String(file.name || "").toLowerCase();
    if (file.type === "application/pdf" || name.endsWith(".pdf")) return "pdf";
    if (file.type === "application/vnd.openxmlformats-officedocument.wordprocessingml.document" || name.endsWith(".docx")) return "docx";
    return null;
  }

  function notice(message, kind = "normal") {
    if (!document.body) return;
    let el = document.getElementById("privacygate-multi-ai-document-notice");
    if (!el) {
      el = document.createElement("div");
      el.id = "privacygate-multi-ai-document-notice";
      el.setAttribute("role", "status");
      el.setAttribute("aria-live", "polite");
      style(el, {
        position: "fixed", left: "50%", top: "50%", transform: "translate(-50%, -50%)",
        zIndex: "2147483647", maxWidth: "min(620px, calc(100vw - 32px))",
        padding: "12px 16px", borderRadius: "10px", color: "#fff", textAlign: "center",
        fontFamily: "Arial, sans-serif", fontSize: "13px", fontWeight: "700",
        boxShadow: "0 8px 30px rgba(0,0,0,.30)"
      });
      document.body.appendChild(el);
    }
    el.style.background = kind === "success" ? "#065f46" : kind === "error" ? "#991b1b" : "#111827";
    el.textContent = String(message || "");
    clearTimeout(window.__privacyGateMultiAiDocumentNoticeTimer);
    window.__privacyGateMultiAiDocumentNoticeTimer = setTimeout(() => el.remove(), 4400);
  }

  function setBusy(value, label = "PrivacyGate protecting document locally…") {
    busy = Boolean(value);
    document.getElementById("privacygate-multi-ai-document-working")?.remove();
    if (!busy || !document.body) return;
    const overlay = style(document.createElement("div"), {
      position: "fixed", inset: "0", zIndex: "2147483646", display: "flex",
      alignItems: "center", justifyContent: "center", background: "rgba(15,23,42,.34)",
      backdropFilter: "blur(2px)", fontFamily: "Arial, sans-serif"
    });
    overlay.id = "privacygate-multi-ai-document-working";
    const card = style(document.createElement("div"), {
      display: "flex", alignItems: "center", gap: "11px", padding: "14px 18px",
      border: "1px solid #D8E1EC", borderRadius: "999px", background: "rgba(255,255,255,.98)",
      color: "#273247", boxShadow: "0 14px 40px rgba(15,23,42,.24)", fontSize: "13px", fontWeight: "750"
    });
    const spinner = style(document.createElement("span"), {
      width: "16px", height: "16px", border: "2px solid #D7E0EC", borderTopColor: "#0B858A", borderRadius: "50%"
    });
    spinner.animate([{ transform: "rotate(0deg)" }, { transform: "rotate(360deg)" }], { duration: 750, iterations: Infinity, easing: "linear" });
    const text = document.createElement("span");
    text.textContent = label;
    card.append(spinner, text);
    overlay.appendChild(card);
    document.body.appendChild(overlay);
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
      reader.onerror = () => reject(reader.error || new Error("Unable to read document"));
      reader.onload = () => {
        const value = String(reader.result || "");
        const comma = value.indexOf(",");
        if (comma < 0) return reject(new Error("Unable to encode document"));
        resolve(value.slice(comma + 1));
      };
      reader.readAsDataURL(file);
    });
  }

  function base64ToFile(base64, filename, kind) {
    const binary = atob(String(base64 || ""));
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    return new File([bytes], filename, {
      type: kind === "pdf" ? "application/pdf" : "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      lastModified: Date.now()
    });
  }

  async function loadSettings() {
    const [extensionSettings, local] = await Promise.all([
      runtimeMessage({ type: "PG_GET_EXTENSION_SETTINGS" }),
      new Promise(resolve => chrome.storage.local.get({ [LANGUAGE_STORAGE_KEY]: "en" }, resolve))
    ]);
    return {
      profileKey: extensionSettings?.profileKey || "general_business",
      language: local?.[LANGUAGE_STORAGE_KEY] === "it" ? "it" : "en"
    };
  }

  function saveLanguage(language) {
    chrome.storage.local.set({ [LANGUAGE_STORAGE_KEY]: language === "it" ? "it" : "en" });
  }

  function nativeInputs() {
    return Array.from(document.querySelectorAll('input[type="file"]')).filter(input =>
      input instanceof HTMLInputElement &&
      input.isConnected &&
      !input.id?.startsWith("privacygate-") &&
      !input.closest?.('[id^="privacygate-"]')
    );
  }

  function injectIntoNativeInput(input, file) {
    if (!(input instanceof HTMLInputElement) || !(file instanceof File) || !input.isConnected) return false;
    const transfer = new DataTransfer();
    transfer.items.add(file);
    internalInjecting = true;
    try {
      input.files = transfer.files;
      input.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
      input.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
    } finally {
      internalInjecting = false;
    }
    pendingProtectedFile = null;
    pendingDropTarget = null;
    clearTimeout(attachFlowTimer);
    attachFlowTimer = null;
    notice(`PrivacyGate — ${file.name} protected locally and attached.`, "success");
    return true;
  }

  function attachButtonCandidates() {
    const selectors = [
      'button[aria-label*="attach" i]',
      'button[aria-label*="upload" i]',
      'button[aria-label*="add file" i]',
      'button[aria-label*="add files" i]',
      'button[aria-label*="add content" i]',
      'button[data-testid*="attach" i]',
      'button[data-testid*="upload" i]',
      '[role="button"][aria-label*="attach" i]',
      '[role="button"][aria-label*="upload" i]'
    ];
    const items = [];
    for (const selector of selectors) items.push(...document.querySelectorAll(selector));
    return items.filter((item, index, all) => item instanceof HTMLElement && all.indexOf(item) === index);
  }

  function uploadMenuCandidate() {
    const candidates = Array.from(document.querySelectorAll('[role="menuitem"], [role="option"], button, [role="button"]'));
    return candidates.find(item => {
      if (!(item instanceof HTMLElement)) return false;
      const text = String(item.innerText || item.textContent || item.getAttribute("aria-label") || "").trim().toLowerCase();
      return /upload|add file|files from|computer|document/.test(text) && !/send|submit/.test(text);
    }) || null;
  }

  function continueAttachFlow(attempt = 0) {
    if (!pendingProtectedFile) return;
    const native = nativeInputs()[0];
    if (native && injectIntoNativeInput(native, pendingProtectedFile)) return;

    if (attempt === 0) {
      const trigger = attachButtonCandidates()[0];
      if (trigger) {
        try { trigger.click(); } catch (_error) {}
      }
    }

    if (attempt >= 2) {
      const menu = uploadMenuCandidate();
      if (menu) {
        try { menu.click(); } catch (_error) {}
      }
    }

    if (attempt < 30) {
      attachFlowTimer = setTimeout(() => continueAttachFlow(attempt + 1), 80);
      return;
    }

    notice(`PrivacyGate — ${pendingProtectedFile.name} is protected and ready. Click ${providerName()}'s Attach button once to insert it.`, "success");
  }

  function handoffProtectedFile(file, preferredInput = null) {
    if (preferredInput instanceof HTMLInputElement && preferredInput.isConnected && injectIntoNativeInput(preferredInput, file)) return;
    const native = nativeInputs()[0];
    if (native && injectIntoNativeInput(native, file)) return;
    pendingProtectedFile = file;
    continueAttachFlow(0);
  }

  function openPicker(preferredInput = null) {
    if (busy) return;
    const picker = document.createElement("input");
    picker.type = "file";
    picker.accept = ACCEPT;
    picker.multiple = false;
    picker.addEventListener("change", () => {
      const file = picker.files?.[0] || null;
      if (file) protectDocument(file, preferredInput);
    }, { once: true });
    picker.click();
  }

  function makeSelect(options, value) {
    const select = style(document.createElement("select"), {
      minHeight: "36px", padding: "0 34px 0 10px", border: "1px solid #CDD5DF",
      borderRadius: "9px", background: "#fff", color: "#273247", fontSize: "12px", fontWeight: "700"
    });
    for (const [key, label] of options) {
      const option = document.createElement("option");
      option.value = key;
      option.textContent = label;
      option.selected = key === value;
      select.appendChild(option);
    }
    return select;
  }

  function closeReview() {
    document.getElementById("privacygate-multi-ai-document-review")?.remove();
  }

  function showReview(file, kind, analysis, settings) {
    return new Promise(resolve => {
      closeReview();
      const findings = Array.isArray(analysis?.findings) ? analysis.findings : [];
      const overlay = style(document.createElement("div"), {
        position: "fixed", inset: "0", zIndex: "2147483647", display: "flex", alignItems: "center",
        justifyContent: "center", padding: "24px", background: "rgba(15,23,42,.45)", backdropFilter: "blur(2px)",
        fontFamily: "Arial, sans-serif"
      });
      overlay.id = "privacygate-multi-ai-document-review";
      const card = style(document.createElement("section"), {
        width: "min(820px,96vw)", maxHeight: "min(790px,92vh)", display: "flex", flexDirection: "column",
        overflow: "hidden", background: "#fff", color: "#172033", border: "1px solid #DDE3EA",
        borderRadius: "18px", boxShadow: "0 24px 70px rgba(15,23,42,.30)"
      });
      const header = style(document.createElement("div"), { padding: "20px 22px 16px", borderBottom: "1px solid #E7EBF0" });
      const brandRow = style(document.createElement("div"), { display: "flex", justifyContent: "space-between", alignItems: "center" });
      const brand = style(document.createElement("div"), { color: "#2348B5", fontSize: "13px", fontWeight: "850", letterSpacing: ".08em", textTransform: "uppercase" });
      brand.textContent = `PrivacyGate · ${kind === "pdf" ? "PDF" : "WORD"}`;
      const badge = style(document.createElement("span"), { padding: "6px 9px", borderRadius: "999px", background: "#E9F7F1", color: "#126246", fontSize: "11px", fontWeight: "800" });
      badge.textContent = "LOCAL ONLY";
      brandRow.append(brand, badge);
      const title = style(document.createElement("h2"), { margin: "9px 0 5px", fontSize: "20px" });
      title.textContent = "Review detected information";
      const subtitle = style(document.createElement("p"), { margin: "0", color: "#647084", fontSize: "12.5px" });
      subtitle.textContent = `${file.name} · Choose what PrivacyGate should protect before ${providerName()} receives the document.`;
      const settingsRow = style(document.createElement("div"), { display: "flex", flexWrap: "wrap", gap: "10px", marginTop: "14px", alignItems: "end" });
      const profileSelect = makeSelect(PROFILE_OPTIONS, settings.profileKey);
      const languageSelect = makeSelect([["en", "English"], ["it", "Italiano"]], settings.language);
      settingsRow.append(profileSelect, languageSelect);
      header.append(brandRow, title, subtitle, settingsRow);

      const list = style(document.createElement("div"), { padding: "12px 22px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "8px" });
      const checkboxes = [];
      for (const finding of findings) {
        const row = style(document.createElement("label"), {
          display: "grid", gridTemplateColumns: "22px minmax(135px,170px) minmax(220px,1fr) minmax(80px,130px)",
          alignItems: "center", gap: "10px", padding: "11px 12px", border: "1px solid #E1E6ED", borderRadius: "11px", background: "#FBFCFE"
        });
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = true;
        checkbox.dataset.findingId = String(finding?.finding_id || "");
        checkbox.style.accentColor = "#2348B5";
        checkboxes.push(checkbox);
        const type = style(document.createElement("span"), { padding: "5px 8px", borderRadius: "999px", background: "#EEF3FF", color: "#27416F", fontSize: "10.5px", fontWeight: "850" });
        type.textContent = String(finding?.entity_type || "DETECTED").replaceAll("_", " ");
        const value = style(document.createElement("span"), { fontSize: "12.5px", fontWeight: "650", overflowWrap: "anywhere" });
        value.textContent = String(finding?.display_value || "Value unavailable");
        const locationCell = style(document.createElement("span"), { color: "#647084", fontSize: "10.5px", fontWeight: "750", textAlign: "right" });
        locationCell.textContent = kind === "pdf" ? `Page ${Number(finding?.page_number || 1)}` : String(finding?.location || `Block ${Number(finding?.page_number || 1)}`);
        row.append(checkbox, type, value, locationCell);
        list.appendChild(row);
      }

      const footer = style(document.createElement("div"), { display: "flex", justifyContent: "space-between", alignItems: "center", gap: "12px", padding: "15px 22px 18px", borderTop: "1px solid #E7EBF0", background: "#FBFCFE" });
      const note = style(document.createElement("span"), { color: "#647084", fontSize: "11px", fontWeight: "700" });
      note.textContent = `Detected values stay local and are not sent to ${providerName()} by PrivacyGate.`;
      const actions = style(document.createElement("div"), { display: "flex", gap: "9px" });
      const cancel = style(document.createElement("button"), { padding: "10px 15px", border: "1px solid #CDD5DF", borderRadius: "9px", background: "#fff", color: "#273247", fontWeight: "700", cursor: "pointer" });
      cancel.type = "button";
      cancel.textContent = "Cancel";
      const protect = style(document.createElement("button"), { padding: "10px 16px", border: "1px solid #2348B5", borderRadius: "9px", background: "#2348B5", color: "#fff", fontWeight: "800", cursor: "pointer" });
      protect.type = "button";
      protect.textContent = "Protect & Attach";
      actions.append(cancel, protect);
      footer.append(note, actions);

      cancel.addEventListener("click", () => { closeReview(); resolve(null); });
      protect.addEventListener("click", () => {
        const ids = checkboxes.filter(item => item.checked).map(item => item.dataset.findingId).filter(Boolean);
        const nextSettings = { profileKey: profileSelect.value, language: languageSelect.value };
        saveLanguage(nextSettings.language);
        closeReview();
        resolve({ findingIds: ids, settings: nextSettings });
      });

      card.append(header, list, footer);
      overlay.appendChild(card);
      document.body.appendChild(overlay);
      cancel.focus();
    });
  }

  function errorMessage(response, kind) {
    const code = response?.data?.error || response?.error || "local_service_error";
    const detail = response?.data?.message;
    if (code === "pdf_requires_ocr") return "PrivacyGate — this PDF is image-only. OCR browser protection is not enabled yet. Nothing was attached.";
    if (code === "browser_pairing_required") return "PrivacyGate — browser pairing is required. Nothing was attached.";
    if (response?.status) return `PrivacyGate — ${kind.toUpperCase()} protection failed (HTTP ${response.status}: ${code})${detail ? ` — ${detail}` : ""}. Nothing was attached.`;
    return "PrivacyGate — Local Privacy Bridge is unavailable. Nothing was attached.";
  }

  async function protectDocument(file, preferredInput = null) {
    if (busy || !protectionEnabled) return;
    const kind = fileKind(file);
    if (!kind) {
      notice("PrivacyGate — Browser Protection accepts PDF and Word (.docx). The original file was not attached.", "error");
      return;
    }
    if (file.size <= 0 || file.size > MAX_FILE_BYTES) {
      notice("PrivacyGate — documents must be between 1 byte and 12 MB. Nothing was attached.", "error");
      return;
    }

    try {
      const fileBase64 = await fileToBase64(file);
      let settings = await loadSettings();
      setBusy(true, `PrivacyGate scanning ${kind === "pdf" ? "PDF" : "Word document"} locally…`);
      let analyzed = await runtimeMessage({
        type: kind === "pdf" ? "PG_PDF_ANALYZE" : "PG_DOCX_ANALYZE",
        filename: file.name,
        fileBase64,
        profileKey: settings.profileKey,
        language: settings.language
      });
      if (!analyzed?.ok) {
        setBusy(false);
        notice(errorMessage(analyzed, kind), "error");
        return;
      }

      let findingIds = [];
      const findings = Array.isArray(analyzed.data?.findings) ? analyzed.data.findings : [];
      if (findings.length) {
        setBusy(false);
        const reviewed = await showReview(file, kind, analyzed.data, settings);
        if (!reviewed) return;
        findingIds = reviewed.findingIds;
        if (reviewed.settings.profileKey !== settings.profileKey || reviewed.settings.language !== settings.language) {
          settings = reviewed.settings;
          setBusy(true, `PrivacyGate rescanning ${kind === "pdf" ? "PDF" : "Word document"} locally…`);
          analyzed = await runtimeMessage({
            type: kind === "pdf" ? "PG_PDF_ANALYZE" : "PG_DOCX_ANALYZE",
            filename: file.name,
            fileBase64,
            profileKey: settings.profileKey,
            language: settings.language
          });
          if (!analyzed?.ok) {
            setBusy(false);
            notice(errorMessage(analyzed, kind), "error");
            return;
          }
          findingIds = (Array.isArray(analyzed.data?.findings) ? analyzed.data.findings : []).map(item => item.finding_id).filter(Boolean);
        }
      }

      setBusy(true, `PrivacyGate creating protected ${kind === "pdf" ? "PDF" : "Word document"}…`);
      const protectedResponse = await runtimeMessage({
        type: kind === "pdf" ? "PG_PDF_PROTECT" : "PG_DOCX_PROTECT",
        analysisId: analyzed.data.analysis_id,
        findingIds
      });
      if (!protectedResponse?.ok) {
        setBusy(false);
        notice(errorMessage(protectedResponse, kind), "error");
        return;
      }

      const encoded = protectedResponse.data?.protected_file_base64;
      const filename = protectedResponse.data?.protected_filename;
      if (typeof encoded !== "string" || !encoded || typeof filename !== "string") throw new Error("Protected document payload is incomplete");
      const protectedFile = base64ToFile(encoded, filename, kind);
      setBusy(false);
      handoffProtectedFile(protectedFile, preferredInput);
    } catch (error) {
      setBusy(false);
      notice(`PrivacyGate — ${String(error?.message || error)}. Nothing was attached.`, "error");
    }
  }

  document.addEventListener("click", event => {
    if (!protectionEnabled || busy) return;
    if (!(event.target instanceof Element)) return;
    const input = event.target.closest('input[type="file"]');
    if (!(input instanceof HTMLInputElement) || input.id?.startsWith("privacygate-")) return;

    if (pendingProtectedFile) {
      stop(event);
      injectIntoNativeInput(input, pendingProtectedFile);
      return;
    }

    if (internalInjecting) return;
    stop(event);
    openPicker(input);
  }, true);

  document.addEventListener("change", event => {
    const input = event.target;
    if (!(input instanceof HTMLInputElement) || input.type !== "file" || input.id?.startsWith("privacygate-")) return;
    if (internalInjecting) return;
    if (!protectionEnabled || busy) return;
    const files = Array.from(input.files || []);
    if (!files.length) return;
    stop(event);
    input.value = "";
    if (files.length !== 1 || !fileKind(files[0])) {
      notice("PrivacyGate — attach one PDF or Word (.docx) file at a time.", "error");
      return;
    }
    protectDocument(files[0], input);
  }, true);

  document.addEventListener("drop", event => {
    if (!protectionEnabled || busy || internalInjecting) return;
    const files = Array.from(event.dataTransfer?.files || []);
    if (!files.length) return;
    stop(event);
    if (files.length !== 1 || !fileKind(files[0])) {
      notice("PrivacyGate — drag & drop accepts one PDF or Word (.docx) file at a time. Nothing was attached.", "error");
      return;
    }
    pendingDropTarget = event.target instanceof Element ? event.target : null;
    protectDocument(files[0], null);
  }, true);

  document.addEventListener("paste", event => {
    if (!protectionEnabled || busy || internalInjecting) return;
    const files = Array.from(event.clipboardData?.files || []);
    if (!files.length) return;
    stop(event);
    if (files.length !== 1 || !fileKind(files[0])) {
      notice("PrivacyGate — pasted files are blocked while Browser Protection is ON.", "error");
      return;
    }
    protectDocument(files[0], null);
  }, true);

  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && document.getElementById("privacygate-multi-ai-document-review")) {
      stop(event);
      closeReview();
    }
  }, true);

  chrome.storage.local.get({ [STORAGE_KEY]: true }, values => {
    protectionEnabled = values?.[STORAGE_KEY] !== false;
  });
  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName !== "local" || !changes[STORAGE_KEY]) return;
    protectionEnabled = changes[STORAGE_KEY].newValue !== false;
    if (!protectionEnabled) {
      closeReview();
      setBusy(false);
      pendingProtectedFile = null;
      pendingDropTarget = null;
      clearTimeout(attachFlowTimer);
      attachFlowTimer = null;
    }
  });
})();