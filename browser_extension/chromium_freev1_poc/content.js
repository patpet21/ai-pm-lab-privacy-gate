(() => {
  "use strict";

  if (window.top !== window) return;

  const STORAGE_KEY = "privacygateProtectionEnabled";
  const PLACEHOLDER_MARKER = "[[PG_";

  let analysisBusy = false;
  let reviewOpen = false;
  let approvedSendText = null;
  let approvedSendTimer = null;
  let lastSessionId = null;
  let restoreScanTimer = null;
  let restoreErrorShown = false;
  let workingTimer = null;
  let protectionEnabled = true;
  let bridgeConnected = false;

  const restoringNodes = new WeakSet();

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

  function style(element, values) {
    Object.assign(element.style, values);
    return element;
  }

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

  function composerShell() {
    const box = composer();
    if (!box) return null;
    return box.closest("form") || box.parentElement;
  }

  function sendButton() {
    return document.querySelector(
      'button[data-testid="send-button"],' +
      'button[aria-label*="send" i],' +
      'button[aria-label*="submit" i]'
    );
  }

  function notice(message, kind = "normal") {
    let element = document.getElementById("privacygate-freev1-notice");

    if (!element) {
      element = document.createElement("div");
      element.id = "privacygate-freev1-notice";
      style(element, {
        position: "fixed",
        right: "24px",
        bottom: "100px",
        zIndex: "2147483647",
        padding: "12px 16px",
        borderRadius: "10px",
        color: "#ffffff",
        fontFamily: "Arial, sans-serif",
        fontSize: "13px",
        fontWeight: "650",
        boxShadow: "0 8px 30px rgba(0,0,0,.30)"
      });
      document.documentElement.appendChild(element);
    }

    element.style.background =
      kind === "success" ? "#065f46" :
      kind === "error" ? "#991b1b" :
      "#111827";
    element.textContent = message;

    clearTimeout(window.__privacyGateNoticeTimer);
    window.__privacyGateNoticeTimer = setTimeout(() => element.remove(), 3500);
  }

  function hideWorking() {
    if (workingTimer) {
      clearTimeout(workingTimer);
      workingTimer = null;
    }
    document.getElementById("privacygate-freev1-checking")?.remove();
  }

  function showWorking(label = "PrivacyGate checking…", delay = 180) {
    hideWorking();

    workingTimer = setTimeout(() => {
      workingTimer = null;
      const indicator = style(document.createElement("div"), {
        position: "fixed",
        left: "50%",
        top: "50%",
        transform: "translate(-50%, -50%)",
        zIndex: "2147483647",
        display: "flex",
        alignItems: "center",
        gap: "9px",
        padding: "10px 14px",
        border: "1px solid #D8E1EC",
        borderRadius: "999px",
        background: "rgba(255,255,255,.97)",
        color: "#273247",
        fontFamily: "Arial, sans-serif",
        fontSize: "13px",
        fontWeight: "700",
        boxShadow: "0 12px 34px rgba(15,23,42,.22)"
      });
      indicator.id = "privacygate-freev1-checking";

      const spinner = style(document.createElement("span"), {
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
    }, Math.max(0, delay));
  }

  function updateProtectionBar() {
    const bar = document.getElementById("privacygate-freev1-bar");
    if (!bar) return;

    const state = bar.querySelector('[data-pg-role="state"]');
    const bridge = bar.querySelector('[data-pg-role="bridge"]');
    const toggle = bar.querySelector('[data-pg-role="toggle"]');
    const knob = bar.querySelector('[data-pg-role="knob"]');

    if (state) {
      state.textContent = protectionEnabled ? "Protection ON" : "Protection OFF";
      state.style.color = protectionEnabled ? "#86EFAC" : "#CBD5E1";
    }

    if (bridge) {
      bridge.textContent = bridgeConnected ? "● Local" : "● Bridge offline";
      bridge.style.color = bridgeConnected ? "#86EFAC" : "#FBBF24";
    }

    if (toggle) {
      toggle.setAttribute("aria-checked", protectionEnabled ? "true" : "false");
      toggle.title = protectionEnabled
        ? "Turn PrivacyGate protection off"
        : "Turn PrivacyGate protection on";
      toggle.style.background = protectionEnabled ? "#16A34A" : "#64748B";
    }

    if (knob) {
      knob.style.transform = protectionEnabled
        ? "translateX(16px)"
        : "translateX(0)";
    }
  }

  function setProtectionEnabled(enabled) {
    protectionEnabled = Boolean(enabled);

    if (!protectionEnabled) {
      analysisBusy = false;
      hideWorking();
      closeReview();
      clearApprovedSend();
    }

    updateProtectionBar();
    chrome.storage.local.set({ [STORAGE_KEY]: protectionEnabled });
  }

  function buildProtectionBar() {
    const bar = style(document.createElement("div"), {
      width: "100%",
      boxSizing: "border-box",
      display: "flex",
      justifyContent: "center",
      padding: "6px 10px 0",
      pointerEvents: "none",
      fontFamily: "Arial, sans-serif"
    });
    bar.id = "privacygate-freev1-bar";

    const panel = style(document.createElement("div"), {
      display: "flex",
      alignItems: "center",
      gap: "9px",
      minHeight: "28px",
      padding: "4px 8px 4px 6px",
      border: "1px solid rgba(148,163,184,.34)",
      borderRadius: "999px",
      background: "rgba(15,23,42,.93)",
      color: "#F8FAFC",
      boxShadow: "0 4px 16px rgba(15,23,42,.18)",
      pointerEvents: "auto",
      userSelect: "none"
    });

    const mark = style(document.createElement("span"), {
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      width: "20px",
      height: "20px",
      borderRadius: "6px",
      background: "#1D4ED8",
      color: "#FFFFFF",
      fontSize: "9px",
      fontWeight: "900",
      letterSpacing: ".04em"
    });
    mark.textContent = "PG";

    const brand = style(document.createElement("span"), {
      fontSize: "11px",
      fontWeight: "800",
      letterSpacing: ".015em"
    });
    brand.textContent = "PrivacyGate";

    const state = style(document.createElement("span"), {
      fontSize: "10.5px",
      fontWeight: "750"
    });
    state.dataset.pgRole = "state";

    const divider = style(document.createElement("span"), {
      width: "1px",
      height: "14px",
      background: "rgba(148,163,184,.35)"
    });

    const bridge = style(document.createElement("span"), {
      fontSize: "10px",
      fontWeight: "700"
    });
    bridge.dataset.pgRole = "bridge";

    const toggle = style(document.createElement("button"), {
      position: "relative",
      width: "38px",
      height: "22px",
      padding: "2px",
      margin: "0 0 0 2px",
      border: "0",
      borderRadius: "999px",
      cursor: "pointer",
      outline: "none",
      transition: "background .16s ease"
    });
    toggle.type = "button";
    toggle.dataset.pgRole = "toggle";
    toggle.setAttribute("role", "switch");
    toggle.setAttribute("aria-label", "PrivacyGate browser protection");

    const knob = style(document.createElement("span"), {
      display: "block",
      width: "18px",
      height: "18px",
      borderRadius: "50%",
      background: "#FFFFFF",
      boxShadow: "0 1px 4px rgba(15,23,42,.32)",
      transition: "transform .16s ease"
    });
    knob.dataset.pgRole = "knob";
    toggle.appendChild(knob);

    toggle.addEventListener("click", event => {
      event.preventDefault();
      event.stopPropagation();
      setProtectionEnabled(!protectionEnabled);
    });

    panel.append(mark, brand, state, divider, bridge, toggle);
    bar.appendChild(panel);
    return bar;
  }

  function ensureProtectionBar() {
    const shell = composerShell();
    if (!shell?.parentElement) return;

    let bar = document.getElementById("privacygate-freev1-bar");

    if (bar && bar.previousElementSibling === shell) {
      updateProtectionBar();
      return;
    }

    bar?.remove();
    bar = buildProtectionBar();
    shell.insertAdjacentElement("afterend", bar);
    updateProtectionBar();
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
    if (!protectionEnabled) return;

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
      if (!protectionEnabled) {
        clearApprovedSend();
        return;
      }

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

  function scheduleRestoreScan(delay = 90) {
    if (!lastSessionId) return;
    clearTimeout(restoreScanTimer);
    restoreScanTimer = setTimeout(scanAssistantResponses, delay);
  }

  function restoreTextNode(node) {
    if (
      !lastSessionId ||
      !node?.isConnected ||
      restoringNodes.has(node)
    ) {
      return;
    }

    const protectedText = node.nodeValue || "";
    if (!protectedText.includes(PLACEHOLDER_MARKER)) return;

    const sessionId = lastSessionId;
    restoringNodes.add(node);

    chrome.runtime.sendMessage(
      {
        type: "PG_RESTORE",
        text: protectedText,
        sessionId
      },
      response => {
        restoringNodes.delete(node);

        if (chrome.runtime.lastError || !response?.ok) {
          if (!restoreErrorShown) {
            restoreErrorShown = true;
            notice(
              "PrivacyGate — response restore unavailable. Protected placeholders remain visible.",
              "error"
            );
          }
          return;
        }

        const restoredText = response.data?.restored_text;
        if (
          typeof restoredText !== "string" ||
          restoredText === protectedText ||
          !node.isConnected ||
          node.nodeValue !== protectedText
        ) {
          return;
        }

        node.nodeValue = restoredText;
        node.parentElement?.setAttribute("data-privacygate-restored", "true");
        restoreErrorShown = false;
      }
    );
  }

  function scanAssistantResponses() {
    if (!lastSessionId) return;

    const roots = document.querySelectorAll(
      '[data-message-author-role="assistant"]'
    );

    for (const root of roots) {
      const walker = document.createTreeWalker(
        root,
        NodeFilter.SHOW_TEXT
      );

      const candidates = [];
      let node = walker.nextNode();
      while (node) {
        if ((node.nodeValue || "").includes(PLACEHOLDER_MARKER)) {
          candidates.push(node);
        }
        node = walker.nextNode();
      }

      for (const candidate of candidates) {
        restoreTextNode(candidate);
      }
    }
  }

  function protectAndSend(textSnapshot, selectedIds) {
    if (!protectionEnabled) return;

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
    showWorking("PrivacyGate protecting…", 70);

    chrome.runtime.sendMessage(
      {
        type: "PG_PROTECT",
        text: textSnapshot,
        findingIds: selectedIds,
        sessionId: lastSessionId
      },
      response => {
        hideWorking();

        if (!protectionEnabled) return;

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

        lastSessionId = response.data?.session_id || lastSessionId;
        restoreErrorShown = false;

        console.log(
          "[PrivacyGate FreeV1] Protected locally:",
          Number(response.data?.applied_findings_count || 0),
          "item(s)"
        );

        approveAndSend(protectedText);
        scheduleRestoreScan(150);
      }
    );
  }

  function showReview(textSnapshot, findings) {
    hideWorking();
    document.getElementById("privacygate-freev1-review")?.remove();
    reviewOpen = true;

    const overlay = style(document.createElement("div"), {
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
    overlay.id = "privacygate-freev1-review";

    const card = style(document.createElement("section"), {
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
    card.setAttribute("role", "dialog");
    card.setAttribute("aria-modal", "true");
    card.setAttribute("aria-labelledby", "privacygate-freev1-review-title");

    const header = style(document.createElement("div"), {
      padding: "22px 24px 18px",
      borderBottom: "1px solid #E7EBF0"
    });

    const brandRow = style(document.createElement("div"), {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      gap: "12px",
      marginBottom: "10px"
    });

    const brand = style(document.createElement("div"), {
      fontSize: "13px",
      fontWeight: "800",
      letterSpacing: "0.08em",
      textTransform: "uppercase",
      color: "#2348B5"
    });
    brand.textContent = "PrivacyGate";

    const localBadge = style(document.createElement("span"), {
      padding: "6px 9px",
      borderRadius: "999px",
      background: "#E9F7F1",
      color: "#126246",
      fontSize: "11px",
      fontWeight: "800"
    });
    localBadge.textContent = "LOCAL · Protected";

    brandRow.append(brand, localBadge);

    const title = style(document.createElement("h2"), {
      margin: "0 0 7px",
      fontSize: "22px",
      lineHeight: "1.2",
      fontWeight: "750"
    });
    title.id = "privacygate-freev1-review-title";
    title.textContent = "Sensitive information detected";

    const subtitle = style(document.createElement("p"), {
      margin: "0",
      color: "#647084",
      fontSize: "13px",
      lineHeight: "1.5"
    });
    subtitle.textContent =
      "Review each item before anything is sent. Checked = protect · Unchecked = keep.";

    header.append(brandRow, title, subtitle);

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
        gridTemplateColumns: "22px minmax(115px, auto) 1fr",
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
      checkbox.setAttribute(
        "aria-label",
        `Protect ${finding?.entity_type || "detected item"}`
      );

      const type = String(finding?.entity_type || "DETECTED").toUpperCase();
      const pill = style(document.createElement("span"), {
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
      pill.textContent = type.replaceAll("_", " ");

      const value = style(document.createElement("span"), {
        minWidth: "0",
        overflowWrap: "anywhere",
        color: "#172033",
        fontSize: "13px",
        fontWeight: "600"
      });
      value.textContent = findingValue(textSnapshot, finding);

      row.append(checkbox, pill, value);
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
    cancel.addEventListener("click", closeReview);

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
    protect.textContent = "Protect & Send";
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

  function analysisFailureMessage(response) {
    const status = Number(response?.status || 0);
    const code = response?.data?.error || response?.error || "bridge_unavailable";

    if (status > 0) {
      return `PrivacyGate — local analysis unavailable (HTTP ${status}: ${code}). Nothing was sent.`;
    }

    return "PrivacyGate — Local Privacy Bridge is not reachable. Nothing was sent.";
  }

  function analyzeCurrentComposer() {
    if (!protectionEnabled) return;

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

        if (!protectionEnabled) return;

        if (chrome.runtime.lastError || !response?.ok) {
          notice(analysisFailureMessage(response), "error");
          bridgeConnected = false;
          updateProtectionBar();
          return;
        }

        bridgeConnected = true;
        updateProtectionBar();

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
    if (!protectionEnabled) {
      return;
    }

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

  const pageObserver = new MutationObserver(() => {
    ensureProtectionBar();
    scheduleRestoreScan();
  });
  pageObserver.observe(document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true
  });

  chrome.storage.local.get({ [STORAGE_KEY]: true }, values => {
    protectionEnabled = values?.[STORAGE_KEY] !== false;
    ensureProtectionBar();
    updateProtectionBar();
  });

  chrome.runtime.sendMessage(
    { type: "PG_BRIDGE_STATUS" },
    response => {
      bridgeConnected = Boolean(response?.ok);
      ensureProtectionBar();
      updateProtectionBar();
    }
  );

  ensureProtectionBar();
})();
