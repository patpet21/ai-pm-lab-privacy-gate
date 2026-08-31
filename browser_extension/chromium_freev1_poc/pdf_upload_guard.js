(() => {
  "use strict";

  if (window.top !== window) return;

  const STORAGE_KEY = "privacygateProtectionEnabled";
  const MAX_PDF_BYTES = 12 * 1024 * 1024;
  const PDF_ACCEPT = ".pdf,application/pdf";

  let protectionEnabled = true;
  let busy = false;
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

  function notice(message, kind = "normal") {
    let element = document.getElementById("privacygate-pdf-notice");
    if (!element) {
      element = document.createElement("div");
      element.id = "privacygate-pdf-notice";
      style(element, {
        position: "fixed",
        right: "24px",
        bottom: "100px",
        zIndex: "2147483647",
        maxWidth: "420px",
        padding: "12px 16px",
        borderRadius: "10px",
        color: "#ffffff",
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
      kind === "error" ? "#991b1b" :
      "#111827";
    element.textContent = message;
    clearTimeout(window.__privacyGatePdfNoticeTimer);
    window.__privacyGatePdfNoticeTimer = setTimeout(() => element.remove(), 4200);
  }

  function setBusy(enabled, label = "PrivacyGate protecting PDF locally…") {
    busy = Boolean(enabled);
    document.getElementById("privacygate-pdf-working")?.remove();
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
    overlay.id = "privacygate-pdf-working";

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
      borderTopColor: "#2348B5",
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

  function composerText() {
    const box =
      document.querySelector("#prompt-textarea") ||
      document.querySelector('[contenteditable="true"]');
    if (!box) return "";
    if (box instanceof HTMLTextAreaElement || box instanceof HTMLInputElement) {
      return box.value || "";
    }
    return box.innerText || box.textContent || "";
  }

  function isPdf(file) {
    if (!(file instanceof File)) return false;
    return (
      file.type === "application/pdf" ||
      String(file.name || "").toLowerCase().endsWith(".pdf")
    );
  }

  function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(reader.error || new Error("Unable to read PDF"));
      reader.onload = () => {
        const value = String(reader.result || "");
        const comma = value.indexOf(",");
        if (comma < 0) {
          reject(new Error("Unable to encode PDF"));
          return;
        }
        resolve(value.slice(comma + 1));
      };
      reader.readAsDataURL(file);
    });
  }

  function base64ToFile(base64, filename) {
    const binary = atob(String(base64 || ""));
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    return new File([bytes], filename, {
      type: "application/pdf",
      lastModified: Date.now()
    });
  }

  function resolveUploadInput(preferred) {
    if (
      preferred instanceof HTMLInputElement &&
      preferred.type === "file" &&
      preferred.isConnected
    ) {
      return preferred;
    }

    const inputs = Array.from(document.querySelectorAll('input[type="file"]'));
    return inputs.find(input => input instanceof HTMLInputElement) || null;
  }

  function injectProtectedPdf(preferredInput, protectedFile) {
    const input = resolveUploadInput(preferredInput);
    if (!input) {
      throw new Error("ChatGPT upload input is no longer available");
    }

    const transfer = new DataTransfer();
    transfer.items.add(protectedFile);
    input.files = transfer.files;
    input.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
    input.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
  }

  function closeReview() {
    document.getElementById("privacygate-pdf-review")?.remove();
  }

  function showReview(file, analysis, targetInput) {
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
      overlay.id = "privacygate-pdf-review";

      const card = style(document.createElement("section"), {
        width: "min(660px, 94vw)",
        maxHeight: "min(760px, 90vh)",
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
        padding: "22px 24px 18px",
        borderBottom: "1px solid #E7EBF0"
      });

      const top = style(document.createElement("div"), {
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "12px",
        marginBottom: "10px"
      });

      const brand = style(document.createElement("div"), {
        color: "#2348B5",
        fontSize: "13px",
        fontWeight: "850",
        letterSpacing: ".08em",
        textTransform: "uppercase"
      });
      brand.textContent = "PrivacyGate · PDF";

      const badge = style(document.createElement("span"), {
        padding: "6px 9px",
        borderRadius: "999px",
        background: "#E9F7F1",
        color: "#126246",
        fontSize: "11px",
        fontWeight: "800"
      });
      badge.textContent = "LOCAL ONLY";
      top.append(brand, badge);

      const title = style(document.createElement("h2"), {
        margin: "0 0 6px",
        fontSize: "21px",
        lineHeight: "1.25",
        fontWeight: "780"
      });
      title.textContent = "Sensitive information detected in PDF";

      const subtitle = style(document.createElement("p"), {
        margin: "0",
        color: "#647084",
        fontSize: "13px",
        lineHeight: "1.5"
      });
      subtitle.textContent = `${file.name} · Review what PrivacyGate will protect before the file is attached to ChatGPT.`;
      header.append(top, title, subtitle);

      const list = style(document.createElement("div"), {
        padding: "14px 24px",
        overflowY: "auto",
        display: "flex",
        flexDirection: "column",
        gap: "9px"
      });

      for (const finding of findings) {
        const row = style(document.createElement("label"), {
          display: "grid",
          gridTemplateColumns: "22px minmax(180px,1fr) auto",
          alignItems: "center",
          gap: "11px",
          padding: "12px 13px",
          border: "1px solid #E1E6ED",
          borderRadius: "12px",
          cursor: "pointer",
          background: "#FBFCFE"
        });

        const checkbox = style(document.createElement("input"), {
          width: "17px",
          height: "17px",
          margin: "0",
          accentColor: "#2348B5"
        });
        checkbox.type = "checkbox";
        checkbox.checked = true;
        checkbox.dataset.findingId = String(finding?.finding_id || "");

        const type = style(document.createElement("span"), {
          color: "#273247",
          fontSize: "12px",
          fontWeight: "800"
        });
        type.textContent = String(finding?.entity_type || "DETECTED").replaceAll("_", " ");

        const page = style(document.createElement("span"), {
          color: "#647084",
          fontSize: "11px",
          fontWeight: "750"
        });
        page.textContent = `Page ${Number(finding?.page_number || 1)}`;
        row.append(checkbox, type, page);
        list.appendChild(row);
      }

      const footer = style(document.createElement("div"), {
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "12px",
        padding: "16px 24px 20px",
        borderTop: "1px solid #E7EBF0",
        background: "#FBFCFE"
      });

      const count = style(document.createElement("span"), {
        color: "#647084",
        fontSize: "12px",
        fontWeight: "700"
      });
      count.textContent = `${findings.length} detected item${findings.length === 1 ? "" : "s"}`;

      const actions = style(document.createElement("div"), {
        display: "flex",
        gap: "9px"
      });

      const cancel = style(document.createElement("button"), {
        padding: "10px 15px",
        border: "1px solid #CDD5DF",
        borderRadius: "9px",
        background: "#ffffff",
        color: "#273247",
        fontSize: "13px",
        fontWeight: "700",
        cursor: "pointer"
      });
      cancel.type = "button";
      cancel.textContent = "Cancel";
      cancel.addEventListener("click", () => {
        closeReview();
        resolve(null);
      });

      const protect = style(document.createElement("button"), {
        padding: "10px 16px",
        border: "1px solid #2348B5",
        borderRadius: "9px",
        background: "#2348B5",
        color: "#ffffff",
        fontSize: "13px",
        fontWeight: "800",
        cursor: "pointer"
      });
      protect.type = "button";
      protect.textContent = "Protect & Attach";
      protect.addEventListener("click", () => {
        const selectedIds = Array.from(
          list.querySelectorAll('input[type="checkbox"]:checked')
        )
          .map(input => input.dataset.findingId)
          .filter(Boolean);
        closeReview();
        resolve({ selectedIds, targetInput });
      });

      actions.append(cancel, protect);
      footer.append(count, actions);
      card.append(header, list, footer);
      overlay.appendChild(card);
      document.documentElement.appendChild(overlay);
      cancel.focus();
    });
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

  function errorMessage(response) {
    const code = response?.data?.error || response?.error || "local_service_error";
    if (code === "pdf_requires_ocr") {
      return "PrivacyGate — this PDF is scanned/image-only. OCR browser protection is not enabled yet. Nothing was attached.";
    }
    if (code === "browser_pairing_required") {
      return "PrivacyGate — browser pairing is required. Nothing was attached.";
    }
    if (response?.status) {
      return `PrivacyGate — PDF protection failed (HTTP ${response.status}: ${code}). Nothing was attached.`;
    }
    return "PrivacyGate — Local Privacy Bridge is unavailable. Nothing was attached.";
  }

  async function protectPdf(file, targetInput) {
    if (busy || !protectionEnabled) return;
    if (!isPdf(file)) {
      notice(
        "PrivacyGate — browser file protection currently accepts PDF only. The original file was not attached.",
        "error"
      );
      return;
    }
    if (file.size <= 0 || file.size > MAX_PDF_BYTES) {
      notice("PrivacyGate — PDF must be between 1 byte and 12 MB. Nothing was attached.", "error");
      return;
    }

    currentTargetInput = targetInput;
    setBusy(true, "PrivacyGate scanning PDF locally…");

    try {
      const fileBase64 = await fileToBase64(file);
      const analyzed = await runtimeMessage({
        type: "PG_PDF_ANALYZE",
        filename: file.name,
        fileBase64,
        contextText: composerText()
      });

      if (!analyzed?.ok) {
        setBusy(false);
        notice(errorMessage(analyzed), "error");
        return;
      }

      const findings = Array.isArray(analyzed.data?.findings)
        ? analyzed.data.findings
        : [];

      let selectedIds = [];
      if (findings.length) {
        setBusy(false);
        const reviewed = await showReview(file, analyzed.data, targetInput);
        if (!reviewed) return;
        selectedIds = reviewed.selectedIds;
        currentTargetInput = reviewed.targetInput;
      }

      setBusy(true, "PrivacyGate creating protected PDF…");
      const protectedResponse = await runtimeMessage({
        type: "PG_PDF_PROTECT",
        analysisId: analyzed.data.analysis_id,
        findingIds: selectedIds
      });

      if (!protectedResponse?.ok) {
        setBusy(false);
        notice(errorMessage(protectedResponse), "error");
        return;
      }

      const encoded = protectedResponse.data?.protected_file_base64;
      const filename = protectedResponse.data?.protected_filename;
      if (typeof encoded !== "string" || !encoded || typeof filename !== "string") {
        throw new Error("Protected PDF payload is incomplete");
      }

      const protectedFile = base64ToFile(encoded, filename);
      injectProtectedPdf(currentTargetInput, protectedFile);
      setBusy(false);
      notice(
        `PrivacyGate — ${filename} protected locally and attached.`,
        "success"
      );
    } catch (error) {
      setBusy(false);
      notice(`PrivacyGate — ${String(error?.message || error)}. Nothing was attached.`, "error");
    } finally {
      currentTargetInput = null;
    }
  }

  function openPrivacyGatePicker(targetInput) {
    if (busy) return;
    const picker = document.createElement("input");
    picker.type = "file";
    picker.accept = PDF_ACCEPT;
    picker.multiple = false;
    picker.addEventListener(
      "change",
      () => {
        const file = picker.files?.[0] || null;
        if (file) protectPdf(file, targetInput);
      },
      { once: true }
    );
    picker.click();
  }

  document.addEventListener(
    "click",
    event => {
      if (!protectionEnabled || busy) return;
      if (!(event.target instanceof Element)) return;
      const input = event.target.closest('input[type="file"]');
      if (!(input instanceof HTMLInputElement)) return;
      stopEvent(event);
      openPrivacyGatePicker(input);
    },
    true
  );

  document.addEventListener(
    "drop",
    event => {
      if (!protectionEnabled) return;
      const files = Array.from(event.dataTransfer?.files || []);
      if (!files.length) return;
      stopEvent(event);

      if (files.length !== 1 || !isPdf(files[0])) {
        notice(
          "PrivacyGate — browser drag & drop currently accepts one PDF at a time. No original file was attached.",
          "error"
        );
        return;
      }

      const input = resolveUploadInput(null);
      if (!input) {
        notice("PrivacyGate — use ChatGPT's Attach button for this PDF. Nothing was attached.", "error");
        return;
      }
      protectPdf(files[0], input);
    },
    true
  );

  document.addEventListener(
    "paste",
    event => {
      if (!protectionEnabled) return;
      const files = Array.from(event.clipboardData?.files || []);
      if (!files.length) return;
      stopEvent(event);

      if (files.length !== 1 || !isPdf(files[0])) {
        notice(
          "PrivacyGate — pasted files are blocked while browser protection is ON. Use Attach for a PDF.",
          "error"
        );
        return;
      }

      const input = resolveUploadInput(null);
      if (!input) {
        notice("PrivacyGate — use ChatGPT's Attach button for this PDF. Nothing was attached.", "error");
        return;
      }
      protectPdf(files[0], input);
    },
    true
  );

  document.addEventListener(
    "keydown",
    event => {
      if (event.key !== "Escape") return;
      if (document.getElementById("privacygate-pdf-review")) {
        stopEvent(event);
        closeReview();
      }
    },
    true
  );

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
