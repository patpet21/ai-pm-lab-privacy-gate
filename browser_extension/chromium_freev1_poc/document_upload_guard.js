(() => {
  "use strict";

  if (window.top !== window) return;

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
  let injectingProtectedFile = false;
  let currentTargetInput = null;

  function style(element, values) {
    Object.assign(element.style, values);
    return element;
  }

  function stopEvent(event) {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
  }

  function providerName() {
    const host = location.hostname.toLowerCase();
    if (host === "claude.ai") return "Claude";
    if (host === "gemini.google.com") return "Gemini";
    return "ChatGPT";
  }

  function fileKind(file) {
    if (!(file instanceof File)) return null;
    const name = String(file.name || "").toLowerCase();
    if (file.type === "application/pdf" || name.endsWith(".pdf")) return "pdf";
    if (
      file.type === "application/vnd.openxmlformats-officedocument.wordprocessingml.document" ||
      name.endsWith(".docx")
    ) return "docx";
    return null;
  }

  function notice(message, kind = "normal") {
    let element = document.getElementById("privacygate-document-notice");
    if (!element) {
      element = document.createElement("div");
      element.id = "privacygate-document-notice";
      element.setAttribute("role", "status");
      element.setAttribute("aria-live", "polite");
      style(element, {
        position: "fixed",
        left: "50%",
        top: "50%",
        transform: "translate(-50%, -50%)",
        zIndex: "2147483647",
        width: "max-content",
        maxWidth: "min(560px, calc(100vw - 32px))",
        padding: "12px 16px",
        borderRadius: "10px",
        color: "#ffffff",
        textAlign: "center",
        fontFamily: "Arial, sans-serif",
        fontSize: "13px",
        fontWeight: "650",
        lineHeight: "1.4",
        boxShadow: "0 8px 30px rgba(0,0,0,.30)"
      });
      document.documentElement.appendChild(element);
    }
    element.style.background =
      kind === "success" ? "#065f46" :
      kind === "error" ? "#991b1b" : "#111827";
    element.textContent = message;
    clearTimeout(window.__privacyGateDocumentNoticeTimer);
    window.__privacyGateDocumentNoticeTimer = setTimeout(() => element.remove(), 4400);
  }

  function setBusy(enabled, label = "PrivacyGate protecting document locally…") {
    busy = Boolean(enabled);
    document.getElementById("privacygate-document-working")?.remove();
    if (!busy) return;

    const overlay = style(document.createElement("div"), {
      position: "fixed",
      inset: "0",
      zIndex: "2147483646",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      background: "rgba(15,23,42,.34)",
      backdropFilter: "blur(2px)",
      fontFamily: "Arial, sans-serif"
    });
    overlay.id = "privacygate-document-working";

    const card = style(document.createElement("div"), {
      display: "flex",
      alignItems: "center",
      gap: "11px",
      padding: "14px 18px",
      border: "1px solid #D8E1EC",
      borderRadius: "999px",
      background: "rgba(255,255,255,.98)",
      color: "#273247",
      boxShadow: "0 14px 40px rgba(15,23,42,.24)",
      fontSize: "13px",
      fontWeight: "750"
    });
    const spinner = style(document.createElement("span"), {
      width: "16px",
      height: "16px",
      border: "2px solid #D7E0EC",
      borderTopColor: "#0B858A",
      borderRadius: "50%"
    });
    spinner.animate(
      [{ transform: "rotate(0deg)" }, { transform: "rotate(360deg)" }],
      { duration: 750, iterations: Infinity, easing: "linear" }
    );
    const text = document.createElement("span");
    text.textContent = label;
    card.append(spinner, text);
    overlay.appendChild(card);
    document.documentElement.appendChild(overlay);
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
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    return new File([bytes], filename, {
      type: kind === "pdf"
        ? "application/pdf"
        : "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      lastModified: Date.now()
    });
  }

  function resolveUploadInput(preferred) {
    if (
      preferred instanceof HTMLInputElement &&
      preferred.type === "file" &&
      preferred.isConnected
    ) return preferred;
    return Array.from(document.querySelectorAll('input[type="file"]'))
      .find(input => input instanceof HTMLInputElement) || null;
  }

  function injectProtectedFile(preferredInput, protectedFile) {
    const input = resolveUploadInput(preferredInput);
    if (!input) throw new Error(`${providerName()} upload input is no longer available`);
    const transfer = new DataTransfer();
    transfer.items.add(protectedFile);
    injectingProtectedFile = true;
    try {
      input.files = transfer.files;
      input.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
      input.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
    } finally {
      queueMicrotask(() => { injectingProtectedFile = false; });
    }
  }

  function runtimeMessage(message) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(message, response => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
          return;
        }
        resolve(response);
      });
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

  function makeSelect(options, selectedValue) {
    const select = style(document.createElement("select"), {
      minHeight: "36px",
      padding: "0 34px 0 10px",
      border: "1px solid #CDD5DF",
      borderRadius: "9px",
      background: "#ffffff",
      color: "#273247",
      fontSize: "12px",
      fontWeight: "700",
      outline: "none"
    });
    for (const [value, label] of options) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      option.selected = value === selectedValue;
      select.appendChild(option);
    }
    return select;
  }

  function closeReview() {
    document.getElementById("privacygate-document-review")?.remove();
  }

  function showReview(file, kind, analysis, targetInput, settings) {
    return new Promise(resolve => {
      closeReview();
      const findings = Array.isArray(analysis?.findings) ? analysis.findings : [];
      const overlay = style(document.createElement("div"), {
        position: "fixed",
        inset: "0",
        zIndex: "2147483647",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "24px",
        background: "rgba(15,23,42,.45)",
        backdropFilter: "blur(2px)",
        fontFamily: "Arial, sans-serif"
      });
      overlay.id = "privacygate-document-review";

      const card = style(document.createElement("section"), {
        width: "min(820px, 96vw)",
        maxHeight: "min(790px, 92vh)",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        background: "#ffffff",
        color: "#172033",
        border: "1px solid #DDE3EA",
        borderRadius: "18px",
        boxShadow: "0 24px 70px rgba(15,23,42,.30)"
      });

      const header = style(document.createElement("div"), {
        padding: "20px 22px 16px",
        borderBottom: "1px solid #E7EBF0"
      });
      const brandRow = style(document.createElement("div"), {
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "12px",
        marginBottom: "9px"
      });
      const brand = style(document.createElement("div"), {
        color: "#2348B5",
        fontSize: "13px",
        fontWeight: "850",
        letterSpacing: ".08em",
        textTransform: "uppercase"
      });
      brand.textContent = `PrivacyGate · ${kind === "pdf" ? "PDF" : "WORD"}`;
      const badge = style(document.createElement("span"), {
        padding: "6px 9px",
        borderRadius: "999px",
        background: "#E9F7F1",
        color: "#126246",
        fontSize: "11px",
        fontWeight: "800"
      });
      badge.textContent = "LOCAL ONLY";
      brandRow.append(brand, badge);

      const title = style(document.createElement("h2"), {
        margin: "0 0 5px",
        fontSize: "20px",
        lineHeight: "1.25",
        fontWeight: "780"
      });
      title.textContent = "Review detected information";
      const subtitle = style(document.createElement("p"), {
        margin: "0",
        color: "#647084",
        fontSize: "12.5px",
        lineHeight: "1.45"
      });
      subtitle.textContent = `${file.name} · Choose what PrivacyGate should protect before ${providerName()} receives the document.`;

      const settingsRow = style(document.createElement("div"), {
        display: "flex",
        flexWrap: "wrap",
        alignItems: "end",
        gap: "10px",
        marginTop: "14px"
      });
      const profileLabel = style(document.createElement("label"), {
        display: "flex", flexDirection: "column", gap: "5px",
        color: "#5B667A", fontSize: "10.5px", fontWeight: "800",
        textTransform: "uppercase", letterSpacing: ".04em"
      });
      profileLabel.textContent = "Profile";
      const profileSelect = makeSelect(PROFILE_OPTIONS, settings.profileKey);
      profileLabel.appendChild(profileSelect);
      const languageLabel = style(document.createElement("label"), {
        display: "flex", flexDirection: "column", gap: "5px",
        color: "#5B667A", fontSize: "10.5px", fontWeight: "800",
        textTransform: "uppercase", letterSpacing: ".04em"
      });
      languageLabel.textContent = "Language";
      const languageSelect = makeSelect([["en", "English"], ["it", "Italiano"]], settings.language);
      languageLabel.appendChild(languageSelect);
      const rescan = style(document.createElement("button"), {
        minHeight: "36px", padding: "0 13px", border: "1px solid #CBD5E1",
        borderRadius: "9px", background: "#F8FAFC", color: "#64748B",
        fontSize: "12px", fontWeight: "800"
      });
      rescan.type = "button";
      rescan.textContent = "Rescan";
      settingsRow.append(profileLabel, languageLabel, rescan);
      header.append(brandRow, title, subtitle, settingsRow);

      const toolbar = style(document.createElement("div"), {
        display: "flex", alignItems: "center", justifyContent: "space-between",
        gap: "10px", padding: "10px 22px", background: "#F8FAFC",
        borderBottom: "1px solid #E7EBF0"
      });
      const actionsLeft = style(document.createElement("div"), { display: "flex", gap: "7px" });
      const mini = label => style(Object.assign(document.createElement("button"), { type: "button", textContent: label }), {
        padding: "6px 9px", border: "1px solid #D7DEE8", borderRadius: "8px",
        background: "#fff", color: "#334155", fontSize: "11px", fontWeight: "750", cursor: "pointer"
      });
      const selectAll = mini("Select all");
      const clearAll = mini("Clear all");
      const selectedLabel = style(document.createElement("span"), {
        color: "#647084", fontSize: "11.5px", fontWeight: "700"
      });
      actionsLeft.append(selectAll, clearAll);
      toolbar.append(actionsLeft, selectedLabel);

      const list = style(document.createElement("div"), {
        padding: "12px 22px", overflowY: "auto", display: "flex",
        flexDirection: "column", gap: "8px"
      });
      const checkboxes = [];
      for (const finding of findings) {
        const row = style(document.createElement("label"), {
          display: "grid", gridTemplateColumns: "22px minmax(135px,170px) minmax(220px,1fr) minmax(80px,130px)",
          alignItems: "center", gap: "10px", padding: "11px 12px",
          border: "1px solid #E1E6ED", borderRadius: "11px", cursor: "pointer", background: "#FBFCFE"
        });
        const checkbox = style(document.createElement("input"), {
          width: "17px", height: "17px", margin: "0", accentColor: "#2348B5"
        });
        checkbox.type = "checkbox";
        checkbox.checked = true;
        checkbox.dataset.findingId = String(finding?.finding_id || "");
        checkboxes.push(checkbox);
        const type = style(document.createElement("span"), {
          display: "inline-flex", width: "fit-content", padding: "5px 8px",
          borderRadius: "999px", background: "#EEF3FF", color: "#27416F",
          fontSize: "10.5px", fontWeight: "850"
        });
        type.textContent = String(finding?.entity_type || "DETECTED").replaceAll("_", " ");
        const value = style(document.createElement("span"), {
          overflowWrap: "anywhere", color: "#172033", fontSize: "12.5px", fontWeight: "650"
        });
        value.textContent = String(finding?.display_value || "Value unavailable");
        const locationText = kind === "pdf"
          ? `Page ${Number(finding?.page_number || 1)}`
          : String(finding?.location || `Block ${Number(finding?.page_number || 1)}`);
        const locationCell = style(document.createElement("span"), {
          color: "#647084", fontSize: "10.5px", fontWeight: "750", textAlign: "right"
        });
        locationCell.textContent = locationText;
        row.append(checkbox, type, value, locationCell);
        list.appendChild(row);
      }

      const footer = style(document.createElement("div"), {
        display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px",
        padding: "15px 22px 18px", borderTop: "1px solid #E7EBF0", background: "#FBFCFE"
      });
      const note = style(document.createElement("span"), {
        color: "#647084", fontSize: "11px", fontWeight: "700"
      });
      note.textContent = `Detected values stay local and are not sent to ${providerName()} by PrivacyGate.`;
      const actions = style(document.createElement("div"), { display: "flex", gap: "9px", flexShrink: "0" });
      const cancel = style(document.createElement("button"), {
        padding: "10px 15px", border: "1px solid #CDD5DF", borderRadius: "9px",
        background: "#fff", color: "#273247", fontSize: "13px", fontWeight: "700", cursor: "pointer"
      });
      cancel.type = "button";
      cancel.textContent = "Cancel";
      const protect = style(document.createElement("button"), {
        padding: "10px 16px", border: "1px solid #2348B5", borderRadius: "9px",
        background: "#2348B5", color: "#fff", fontSize: "13px", fontWeight: "800", cursor: "pointer"
      });
      protect.type = "button";
      protect.textContent = "Protect & Attach";
      actions.append(cancel, protect);
      footer.append(note, actions);

      const updateCount = () => {
        selectedLabel.textContent = `${checkboxes.filter(item => item.checked).length} of ${findings.length} selected`;
      };
      const updateDirty = () => {
        const dirty = profileSelect.value !== settings.profileKey || languageSelect.value !== settings.language;
        rescan.disabled = !dirty;
        rescan.style.cursor = dirty ? "pointer" : "default";
        rescan.style.color = dirty ? "#2348B5" : "#64748B";
        protect.disabled = dirty;
        protect.style.opacity = dirty ? ".5" : "1";
      };
      checkboxes.forEach(item => item.addEventListener("change", updateCount));
      selectAll.addEventListener("click", () => { checkboxes.forEach(item => { item.checked = true; }); updateCount(); });
      clearAll.addEventListener("click", () => { checkboxes.forEach(item => { item.checked = false; }); updateCount(); });
      profileSelect.addEventListener("change", updateDirty);
      languageSelect.addEventListener("change", () => { saveLanguage(languageSelect.value); updateDirty(); });
      cancel.addEventListener("click", () => { closeReview(); resolve(null); });
      rescan.addEventListener("click", () => {
        if (rescan.disabled) return;
        const next = { action: "rescan", profileKey: profileSelect.value, language: languageSelect.value, targetInput };
        closeReview(); resolve(next);
      });
      protect.addEventListener("click", () => {
        if (protect.disabled) return;
        const selectedIds = checkboxes.filter(item => item.checked).map(item => item.dataset.findingId).filter(Boolean);
        closeReview(); resolve({ action: "protect", selectedIds, targetInput });
      });

      card.append(header, toolbar, list, footer);
      overlay.appendChild(card);
      document.documentElement.appendChild(overlay);
      updateCount();
      updateDirty();
      cancel.focus();
    });
  }

  function errorMessage(response, kind) {
    const code = response?.data?.error || response?.error || "local_service_error";
    if (code === "pdf_requires_ocr") {
      return "PrivacyGate — this PDF is image-only. OCR browser protection is not enabled yet. Nothing was attached.";
    }
    if (code === "browser_pairing_required") {
      return "PrivacyGate — browser pairing is required. Nothing was attached.";
    }
    const detail = response?.data?.message;
    if (response?.status) {
      return `PrivacyGate — ${kind.toUpperCase()} protection failed (HTTP ${response.status}: ${code})${detail ? ` — ${detail}` : ""}. Nothing was attached.`;
    }
    return "PrivacyGate — Local Privacy Bridge is unavailable. Nothing was attached.";
  }

  async function protectDocument(file, targetInput) {
    if (busy || !protectionEnabled) return;
    const kind = fileKind(file);
    if (!kind) {
      notice("PrivacyGate — Browser Protection currently accepts PDF and Word (.docx). The original file was not attached.", "error");
      return;
    }
    if (file.size <= 0 || file.size > MAX_FILE_BYTES) {
      notice("PrivacyGate — documents must be between 1 byte and 12 MB. Nothing was attached.", "error");
      return;
    }

    currentTargetInput = targetInput;
    try {
      const fileBase64 = await fileToBase64(file);
      let settings = await loadSettings();
      let analyzed = null;
      let selectedIds = [];

      while (true) {
        setBusy(true, `PrivacyGate scanning ${kind === "pdf" ? "PDF" : "Word document"} locally…`);
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

        const findings = Array.isArray(analyzed.data?.findings) ? analyzed.data.findings : [];
        if (!findings.length) {
          selectedIds = [];
          break;
        }

        setBusy(false);
        const reviewed = await showReview(file, kind, analyzed.data, currentTargetInput, settings);
        if (!reviewed) return;
        currentTargetInput = reviewed.targetInput;
        if (reviewed.action === "rescan") {
          settings = { profileKey: reviewed.profileKey, language: reviewed.language };
          saveLanguage(settings.language);
          continue;
        }
        selectedIds = reviewed.selectedIds;
        break;
      }

      setBusy(true, `PrivacyGate creating protected ${kind === "pdf" ? "PDF" : "Word document"}…`);
      const protectedResponse = await runtimeMessage({
        type: kind === "pdf" ? "PG_PDF_PROTECT" : "PG_DOCX_PROTECT",
        analysisId: analyzed.data.analysis_id,
        findingIds: selectedIds
      });
      if (!protectedResponse?.ok) {
        setBusy(false);
        notice(errorMessage(protectedResponse, kind), "error");
        return;
      }

      const encoded = protectedResponse.data?.protected_file_base64;
      const filename = protectedResponse.data?.protected_filename;
      if (typeof encoded !== "string" || !encoded || typeof filename !== "string") {
        throw new Error("Protected document payload is incomplete");
      }

      const protectedFile = base64ToFile(encoded, filename, kind);
      injectProtectedFile(currentTargetInput, protectedFile);
      setBusy(false);
      notice(`PrivacyGate — ${filename} protected locally and attached.`, "success");
    } catch (error) {
      setBusy(false);
      notice(`PrivacyGate — ${String(error?.message || error)}. Nothing was attached.`, "error");
    } finally {
      currentTargetInput = null;
    }
  }

  function openPicker(targetInput) {
    if (busy) return;
    const picker = document.createElement("input");
    picker.type = "file";
    picker.accept = ACCEPT;
    picker.multiple = false;
    picker.addEventListener("change", () => {
      const file = picker.files?.[0] || null;
      if (file) protectDocument(file, targetInput);
    }, { once: true });
    picker.click();
  }

  document.addEventListener("click", event => {
    if (!protectionEnabled || busy || injectingProtectedFile) return;
    if (!(event.target instanceof Element)) return;
    const input = event.target.closest('input[type="file"]');
    if (!(input instanceof HTMLInputElement)) return;
    stopEvent(event);
    openPicker(input);
  }, true);

  document.addEventListener("change", event => {
    if (!protectionEnabled || busy || injectingProtectedFile) return;
    const input = event.target;
    if (!(input instanceof HTMLInputElement) || input.type !== "file") return;
    const files = Array.from(input.files || []);
    if (!files.length) return;
    stopEvent(event);
    input.value = "";
    if (files.length !== 1 || !fileKind(files[0])) {
      notice("PrivacyGate — while Browser Protection is ON, attach one PDF or Word (.docx) file at a time.", "error");
      return;
    }
    protectDocument(files[0], input);
  }, true);

  document.addEventListener("drop", event => {
    if (!protectionEnabled || injectingProtectedFile) return;
    const files = Array.from(event.dataTransfer?.files || []);
    if (!files.length) return;
    stopEvent(event);
    if (files.length !== 1 || !fileKind(files[0])) {
      notice("PrivacyGate — drag & drop accepts one PDF or Word (.docx) file at a time. No original file was attached.", "error");
      return;
    }
    const input = resolveUploadInput(null);
    if (!input) {
      notice(`PrivacyGate — use ${providerName()}'s Attach button. Nothing was attached.`, "error");
      return;
    }
    protectDocument(files[0], input);
  }, true);

  document.addEventListener("paste", event => {
    if (!protectionEnabled || injectingProtectedFile) return;
    const files = Array.from(event.clipboardData?.files || []);
    if (!files.length) return;
    stopEvent(event);
    if (files.length !== 1 || !fileKind(files[0])) {
      notice("PrivacyGate — pasted files are blocked while Browser Protection is ON. Use Attach for PDF or Word (.docx).", "error");
      return;
    }
    const input = resolveUploadInput(null);
    if (!input) {
      notice(`PrivacyGate — use ${providerName()}'s Attach button. Nothing was attached.`, "error");
      return;
    }
    protectDocument(files[0], input);
  }, true);

  document.addEventListener("keydown", event => {
    if (event.key !== "Escape") return;
    if (document.getElementById("privacygate-document-review")) {
      stopEvent(event);
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
      currentTargetInput = null;
    }
  });
})();
