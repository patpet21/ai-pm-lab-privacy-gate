(() => {
  "use strict";

  if (window.top !== window) return;

  let analysisBusy = false;
  let reviewOpen = false;
  let approvedSendText = null;
  let approvedSendTimer = null;
  let lastSessionId = null;

  const TOKEN_COLORS = {
    PERSON: "#DDE7FF",
    EMAIL_ADDRESS: "#D9F3EE",
    PHONE_NUMBER: "#FFE8CC",
    US_SSN: "#FFDDE2",
    US_ZIP_CODE: "#E8DFFF",
    IP_ADDRESS: "#D8EEFF",
    LOCATION: "#FFF1BD",
    DATE_TIME: "#E3F2D7",
    CREDIT_CARD: "#F8DDF1",
    US_BANK_NUMBER: "#F5E0D3",
    US_ROUTING_NUMBER: "#E5EED2",
    SWIFT_BIC: "#DDEBD7",
    CARD_LAST_FOUR: "#F8DDF1",
    CARD_TRANSACTION_ID: "#F3E3D5",
    TRANSFER_TRANSACTION_ID: "#E2E6F5",
    STATEMENT_REFERENCE: "#DEE7EE",
    POSTAL_CODE: "#E8DFFF",
    STREET_ADDRESS: "#FFF1BD",
    MONEY_AMOUNT: "#DDEFD9",
    MERCHANT: "#E5E0F5",
    COUNTERPARTY: "#DCE8F8",
    TRANSACTION_REFERENCE: "#F4E7D5",
    BUSINESS_REGISTRATION_NUMBER: "#DEE7EE",
    INVOICE_NUMBER: "#E2E6F5",
    PURCHASE_ORDER_ID: "#E5E0F5",
    CONTRACT_ID: "#D9F0F3",
    CUSTOMER_ID: "#DCE8F8",
    EMPLOYEE_ID: "#DDE7FF",
    CASE_REFERENCE: "#F4E7D5",
    PROPERTY_IDENTIFIER: "#D9F0F3",
    CUSTOM: "#E7E9ED",
    REDACTED: "#D8DEE5"
  };

  function composer() {
    return (
      document.querySelector("#prompt-textarea") ||
      document.querySelector('[contenteditable="true"]')
    );
  }

  function composerText(box) {
    if (!box) return "";

    if (
      box instanceof HTMLTextAreaElement ||
      box instanceof HTMLInputElement
    ) {
      return box.value || "";
    }

    return box.innerText || box.textContent || "";
  }

  function sendButton() {
    return document.querySelector(
      'button[data-testid="send-button"],' +
      'button[aria-label*="send" i],' +
      'button[aria-label*="submit" i]'
    );
  }

  function notice(message, kind = "normal") {
    let el = document.getElementById("privacygate-freev1-notice");

    if (!el) {
      el = document.createElement("div");
      el.id = "privacygate-freev1-notice";
      Object.assign(el.style, {
        position: "fixed",
        right: "24px",
        bottom: "100px",
        zIndex: "2147483647",
        padding: "12px 16px",
        borderRadius: "10px",
        color: "#ffffff",
        fontFamily: "Arial, sans-serif",
        fontSize: "14px",
        fontWeight: "600",
        boxShadow: "0 8px 30px rgba(0,0,0,.30)"
      });
      document.documentElement.appendChild(el);
    }

    el.style.background =
      kind === "success" ? "#065f46" :
      kind === "error" ? "#991b1b" :
      "#111827";
    el.textContent = message;

    clearTimeout(window.__privacyGateNoticeTimer);
    window.__privacyGateNoticeTimer = setTimeout(() => el.remove(), 3500);
  }

  function showWorking(label = "PrivacyGate checking…") {
    document.getElementById("privacygate-freev1-checking")?.remove();

    const indicator = document.createElement("div");
    indicator.id = "privacygate-freev1-checking";
    Object.assign(indicator.style, {
      position: "fixed",
      right: "24px",
      bottom: "100px",
      zIndex: "2147483647",
      display: "flex",
      alignItems: "center",
      gap: "9px",
      padding: "10px 13px",
      border: "1px solid #D8E1EC",
      borderRadius: "999px",
      background: "rgba(255,255,255,.96)",
      color: "#273247",
      fontFamily: "Arial, sans-serif",
      fontSize: "13px",
      fontWeight: "700",
      boxShadow: "0 8px 26px rgba(15,23,42,.18)"
    });

    const spinner = document.createElement("span");
    Object.assign(spinner.style, {
      width: "14px",
      height: "14px",
      flex: "0 0 14px",
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
    indicator.append(spinner, text);
    document.documentElement.appendChild(indicator);
  }

  function hideWorking() {
    document.getElementById("privacygate-freev1-checking")?.remove();
  }

  function closeReview() {
    document.getElementById("privacygate-freev1-review")?.remove();
    reviewOpen = false;
    composer()?.focus();
  }

  function findingValue(text, finding) {
    const start = Number(finding?.start);
    const end = Number(finding?.end);

    if (
      !Number.isInteger(start) ||
      !Number.isInteger(end) ||
      start < 0 ||
      end <= start ||
      end > text.length
    ) {
      return "Value unavailable";
    }

    return text.slice(start, end);
  }

  function replaceComposerText(box, text) {
    if (!box) return false;

    box.focus();

    if (
      box instanceof HTMLTextAreaElement ||
      box instanceof HTMLInputElement
    ) {
      const prototype = box instanceof HTMLTextAreaElement
        ? HTMLTextAreaElement.prototype
        : HTMLInputElement.prototype;
      const descriptor = Object.getOwnPropertyDescriptor(prototype, "value");
      descriptor?.set?.call(box, text);
      box.dispatchEvent(new Event("input", { bubbles: true }));
      return composerText(box) === text;
    }

    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(box);
    selection?.removeAllRanges();
    selection?.addRange(range);

    let inserted = false;
    try {
      inserted = document.execCommand("insertText", false, text);
    } catch (_error) {
      inserted = false;
    }

    if (!inserted || composerText(box) !== text) {
      box.replaceChildren(document.createTextNode(text));
      box.dispatchEvent(
        new InputEvent("input", {
          bubbles: true,
          inputType: "insertText",
          data: text
        })
      );
    }

    return composerText(box) === text;
  }

  function approvedSendActive() {
    const box = composer();
    return (
      typeof approvedSendText === "string" &&
      box &&
      composerText(box) === approvedSendText
    );
  }

  function clearApprovedSend() {
    approvedSendText = null;
    if (approvedSendTimer) {
      clearTimeout(approvedSendTimer);
      approvedSendTimer = null;
    }
  }

  function approveAndSend(expectedText) {
    const box = composer();
    if (!box || composerText(box) !== expectedText) {
      clearApprovedSend();
      notice(
        "PrivacyGate — message changed before send. Nothing was sent.",
        "error"
      );
      return;
    }

    approvedSendText = expectedText;

    const clickWhenReady = attempt => {
      const button = sendButton();
      if (button && !button.disabled) {
        button.click();
        approvedSendTimer = setTimeout(clearApprovedSend, 2000);
        return;
      }

      if (attempt < 20) {
        setTimeout(() => clickWhenReady(attempt + 1), 50);
        return;
      }

      notice(
        "PrivacyGate — protected text is ready. Press Send once to continue.",
        "error"
      );
    };

    setTimeout(() => clickWhenReady(0), 40);
  }

  function protectAndSend(textSnapshot, selectedIds) {
    const currentBox = composer();
    if (!currentBox || composerText(currentBox) !== textSnapshot) {
      closeReview();
      notice(
        "PrivacyGate — text changed after scan. Press Send to scan again.",
        "error"
      );
      return;
    }

    closeReview();
    showWorking("PrivacyGate protecting…");

    chrome.runtime.sendMessage(
      {
        type: "PG_PROTECT",
        text: textSnapshot,
        findingIds: selectedIds
      },
      response => {
        hideWorking();

        if (chrome.runtime.lastError || !response?.ok) {
          notice(
            "PrivacyGate — local protection unavailable. Nothing was sent.",
            "error"
          );
          return;
        }

        const box = composer();
        if (!box || composerText(box) !== textSnapshot) {
          notice(
            "PrivacyGate — text changed during protection. Nothing was sent.",
            "error"
          );
          return;
        }

        const protectedText = response.data?.protected_text;
        if (typeof protectedText !== "string" || !protectedText.trim()) {
          notice(
            "PrivacyGate — protected text was not returned. Nothing was sent.",
            "error"
          );
          return;
        }

        if (!replaceComposerText(box, protectedText)) {
          notice(
            "PrivacyGate — could not replace the composer safely. Nothing was sent.",
            "error"
          );
          return;
        }

        lastSessionId = response.data?.session_id || null;
        console.log(
          "[PrivacyGate FreeV1] Protected locally:",
          Number(response.data?.applied_findings_count || 0),
          "item(s)"
        );

        approveAndSend(protectedText);
      }
    );
  }

  function showReview(textSnapshot, findings) {
    hideWorking();
    document.getElementById("privacygate-freev1-review")?.remove();
    reviewOpen = true;

    const overlay = document.createElement("div");
    overlay.id = "privacygate-freev1-review";
    Object.assign(overlay.style, {
      position: "fixed",
      inset: "0",
      zIndex: "2147483646",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: "24px",
      background: "rgba(15, 23, 42, 0.42)",
      backdropFilter: "blur(2px)",
      fontFamily: "Arial, sans-serif"
    });

    const card = document.createElement("section");
    card.setAttribute("role", "dialog");
    card.setAttribute("aria-modal", "true");
    card.setAttribute("aria-labelledby", "privacygate-freev1-review-title");
    Object.assign(card.style, {
      width: "min(620px, 94vw)",
      maxHeight: "min(720px, 88vh)",
      display: "flex",
      flexDirection: "column",
      overflow: "hidden",
      background: "#ffffff",
      color: "#172033",
      border: "1px solid #DDE3EA",
      borderRadius: "18px",
      boxShadow: "0 24px 70px rgba(15, 23, 42, 0.28)"
    });

    const header = document.createElement("div");
    Object.assign(header.style, {
      padding: "22px 24px 18px",
      borderBottom: "1px solid #E7EBF0"
    });

    const brandRow = document.createElement("div");
    Object.assign(brandRow.style, {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      gap: "12px",
      marginBottom: "10px"
    });

    const brand = document.createElement("div");
    brand.textContent = "PrivacyGate";
    Object.assign(brand.style, {
      fontSize: "13px",
      fontWeight: "800",
      letterSpacing: "0.08em",
      textTransform: "uppercase",
      color: "#2348B5"
    });

    const localBadge = document.createElement("span");
    localBadge.textContent = "LOCAL · Protected";
    Object.assign(localBadge.style, {
      padding: "6px 9px",
      borderRadius: "999px",
      background: "#E9F7F1",
      color: "#126246",
      fontSize: "11px",
      fontWeight: "800"
    });

    brandRow.append(brand, localBadge);

    const title = document.createElement("h2");
    title.id = "privacygate-freev1-review-title";
    title.textContent = "Sensitive information detected";
    Object.assign(title.style, {
      margin: "0 0 7px",
      fontSize: "22px",
      lineHeight: "1.2",
      fontWeight: "750"
    });

    const subtitle = document.createElement("p");
    subtitle.textContent =
      "Review each item before anything is sent. Checked = protect · Unchecked = keep.";
    Object.assign(subtitle.style, {
      margin: "0",
      color: "#647084",
      fontSize: "13px",
      lineHeight: "1.5"
    });

    header.append(brandRow, title, subtitle);

    const list = document.createElement("div");
    Object.assign(list.style, {
      padding: "14px 24px",
      overflowY: "auto",
      display: "flex",
      flexDirection: "column",
      gap: "9px"
    });

    for (const finding of findings) {
      const row = document.createElement("label");
      Object.assign(row.style, {
        display: "grid",
        gridTemplateColumns: "22px minmax(115px, auto) 1fr",
        alignItems: "center",
        gap: "11px",
        padding: "12px 13px",
        border: "1px solid #E1E6ED",
        borderRadius: "12px",
        cursor: "pointer",
        background: "#FBFCFE"
      });

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = true;
      checkbox.dataset.findingId = String(finding?.finding_id || "");
      checkbox.setAttribute(
        "aria-label",
        `Protect ${finding?.entity_type || "detected item"}`
      );
      Object.assign(checkbox.style, {
        width: "17px",
        height: "17px",
        margin: "0",
        accentColor: "#2348B5"
      });

      const type = String(finding?.entity_type || "DETECTED").toUpperCase();
      const pill = document.createElement("span");
      pill.textContent = type.replaceAll("_", " ");
      Object.assign(pill.style, {
        justifySelf: "start",
        padding: "5px 8px",
        borderRadius: "7px",
        background: TOKEN_COLORS[type] || "#E7E9ED",
        color: "#273247",
        fontSize: "10px",
        lineHeight: "1.2",
        fontWeight: "800",
        letterSpacing: "0.025em"
      });

      const value = document.createElement("span");
      value.textContent = findingValue(textSnapshot, finding);
      Object.assign(value.style, {
        minWidth: "0",
        overflowWrap: "anywhere",
        color: "#172033",
        fontSize: "13px",
        fontWeight: "600"
      });

      row.append(checkbox, pill, value);
      list.appendChild(row);
    }

    const footer = document.createElement("div");
    Object.assign(footer.style, {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      gap: "12px",
      padding: "16px 24px 20px",
      borderTop: "1px solid #E7EBF0",
      background: "#FBFCFE"
    });

    const count = document.createElement("span");
    count.textContent = `${findings.length} detected item${findings.length === 1 ? "" : "s"}`;
    Object.assign(count.style, {
      color: "#647084",
      fontSize: "12px",
      fontWeight: "700"
    });

    const actions = document.createElement("div");
    Object.assign(actions.style, {
      display: "flex",
      gap: "9px"
    });

    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.textContent = "Cancel";
    Object.assign(cancel.style, {
      padding: "10px 15px",
      border: "1px solid #CDD5DF",
      borderRadius: "9px",
      background: "#ffffff",
      color: "#273247",
      fontSize: "13px",
      fontWeight: "700",
      cursor: "pointer"
    });
    cancel.addEventListener("click", closeReview);

    const protect = document.createElement("button");
    protect.type = "button";
    protect.textContent = "Protect & Send";
    Object.assign(protect.style, {
      padding: "10px 16px",
      border: "1px solid #2348B5",
      borderRadius: "9px",
      background: "#2348B5",
      color: "#ffffff",
      fontSize: "13px",
      fontWeight: "800",
      cursor: "pointer"
    });

    protect.addEventListener("click", () => {
      const selectedIds = Array.from(
        list.querySelectorAll('input[type="checkbox"]:checked')
      )
        .map(input => input.dataset.findingId)
        .filter(Boolean);

      protectAndSend(textSnapshot, selectedIds);
    });

    actions.append(cancel, protect);
    footer.append(count, actions);
    card.append(header, list, footer);
    overlay.appendChild(card);
    document.documentElement.appendChild(overlay);
    cancel.focus();
  }

  function analyzeCurrentComposer() {
    const box = composer();
    const textSnapshot = composerText(box);

    if (!textSnapshot.trim() || analysisBusy || reviewOpen) return;

    analysisBusy = true;
    showWorking();

    chrome.runtime.sendMessage(
      {
        type: "PG_ANALYZE",
        text: textSnapshot
      },
      response => {
        analysisBusy = false;
        hideWorking();

        if (chrome.runtime.lastError || !response?.ok) {
          notice(
            "PrivacyGate — local analysis unavailable. Nothing was sent.",
            "error"
          );
          return;
        }

        if (composerText(composer()) !== textSnapshot) {
          notice(
            "PrivacyGate — text changed during scan. Press Send to scan again.",
            "error"
          );
          return;
        }

        const findings = Array.isArray(response.data?.findings)
          ? response.data.findings
          : [];

        if (findings.length === 0) {
          approveAndSend(textSnapshot);
          return;
        }

        showReview(textSnapshot, findings);
      }
    );
  }

  function block(event, reason) {
    if (approvedSendActive()) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    if (reviewOpen) return;

    console.log("[PrivacyGate FreeV1] Send intercepted:", reason);
    analyzeCurrentComposer();
  }

  document.addEventListener(
    "keydown",
    event => {
      if (
        event.key !== "Enter" ||
        event.shiftKey ||
        event.ctrlKey ||
        event.altKey ||
        event.metaKey
      ) {
        return;
      }

      const box = composer();
      if (box && (event.target === box || box.contains(event.target))) {
        block(event, "Enter");
      }
    },
    true
  );

  document.addEventListener(
    "submit",
    event => {
      const box = composer();
      if (
        box &&
        event.target instanceof HTMLFormElement &&
        event.target.contains(box)
      ) {
        block(event, "Form submit");
      }
    },
    true
  );

  document.addEventListener(
    "click",
    event => {
      if (!(event.target instanceof Element)) return;

      const button = event.target.closest(
        'button[data-testid="send-button"],' +
        'button[aria-label*="send" i],' +
        'button[aria-label*="submit" i]'
      );

      if (button && composer()) {
        block(event, "Send button");
      }
    },
    true
  );

  document.addEventListener(
    "keydown",
    event => {
      if (event.key === "Escape" && reviewOpen) {
        event.preventDefault();
        event.stopPropagation();
        closeReview();
      }
    },
    true
  );

  chrome.runtime.sendMessage(
    { type: "PG_BRIDGE_STATUS" },
    response => {
      if (response?.ok) {
        notice("PrivacyGate — Local Bridge connected", "success");
      }
    }
  );

  void lastSessionId;
})();
