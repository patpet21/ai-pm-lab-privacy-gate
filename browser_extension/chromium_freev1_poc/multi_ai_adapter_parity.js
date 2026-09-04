(() => {
  "use strict";

  if (window.top !== window) return;

  const host = location.hostname.toLowerCase();
  const PROVIDER = host === "claude.ai" ? "Claude" : host === "gemini.google.com" ? "Gemini" : null;
  if (!PROVIDER) return;

  const STORAGE_KEY = "privacygateProtectionEnabled";
  const BAR_ID = "privacygate-freev1-bar";
  const REVIEW_ID = "privacygate-freev1-review";

  let protectionEnabled = true;
  let bridgeConnected = false;
  let analysisBusy = false;
  let reviewOpen = false;
  let approvedSendText = null;
  let approvedSendTimer = null;
  let workingTimer = null;

  function style(element, values) {
    Object.assign(element.style, values);
    return element;
  }

  function normalized(value) {
    return String(value || "")
      .normalize("NFC")
      .replace(/\r\n?/g, "\n")
      .replace(/\u00a0/g, " ")
      .replace(/[ \t]+$/gm, "")
      .trim();
  }

  function composer() {
    if (host === "claude.ai") {
      return (
        document.querySelector('div.ProseMirror[contenteditable="true"]') ||
        document.querySelector('[contenteditable="true"][data-placeholder]') ||
        document.querySelector('fieldset [contenteditable="true"]') ||
        document.querySelector('textarea[placeholder*="message" i]') ||
        document.querySelector('textarea')
      );
    }

    return (
      document.querySelector('rich-textarea [contenteditable="true"]') ||
      document.querySelector('.ql-editor[contenteditable="true"]') ||
      document.querySelector('[contenteditable="true"][aria-label*="prompt" i]') ||
      document.querySelector('[contenteditable="true"][aria-label*="message" i]') ||
      document.querySelector('textarea[aria-label*="prompt" i]') ||
      document.querySelector('textarea')
    );
  }

  function composerText(box = composer()) {
    if (!box) return "";
    if (box instanceof HTMLTextAreaElement || box instanceof HTMLInputElement) {
      return box.value || "";
    }
    return box.innerText || box.textContent || "";
  }

  function composerShell() {
    const box = composer();
    if (!box) return null;

    if (host === "claude.ai") {
      return (
        box.closest("fieldset") ||
        box.closest("form") ||
        box.parentElement?.parentElement ||
        box.parentElement
      );
    }

    const rich = box.closest("rich-textarea");
    return (
      rich?.parentElement ||
      box.closest("form") ||
      box.parentElement?.parentElement ||
      box.parentElement
    );
  }

  function sendButton() {
    const box = composer();
    if (!box) return null;

    const scope =
      box.closest("form") ||
      box.closest("fieldset") ||
      box.closest("rich-textarea")?.parentElement?.parentElement ||
      box.parentElement?.parentElement ||
      document;

    const selectors = host === "claude.ai"
      ? [
          'button[data-testid*="send" i]',
          'button[aria-label*="send" i]',
          'button[aria-label*="submit" i]',
          'button[type="submit"]'
        ]
      : [
          'button[aria-label*="send" i]',
          'button[data-test-id*="send" i]',
          'button[class*="send" i]',
          '[role="button"][aria-label*="send" i]',
          'button[type="submit"]'
        ];

    for (const selector of selectors) {
      const candidates = Array.from(scope.querySelectorAll?.(selector) || []);
      const found = candidates.find(item =>
        item instanceof HTMLElement &&
        !item.closest(`#${BAR_ID}, #${REVIEW_ID}`) &&
        item.getAttribute("aria-disabled") !== "true" &&
        !(item instanceof HTMLButtonElement && item.disabled)
      );
      if (found) return found;
    }
    return null;
  }

  function notice(message, kind = "normal") {
    if (!document.body) return;
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
      document.body.appendChild(element);
    }
    element.style.background =
      kind === "success" ? "#065f46" :
      kind === "error" ? "#991b1b" :
      "#111827";
    element.textContent = String(message || "");
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
      if (!document.body) return;
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
      document.body.appendChild(indicator);
    }, Math.max(0, delay));
  }

  function updateProtectionBar() {
    const bar = document.getElementById(BAR_ID);
    if (!bar) return;

    const state = bar.querySelector('[data-pg-role="state"]');
    const bridge = bar.querySelector('[data-pg-role="bridge"]');
    const toggle = bar.querySelector('[data-pg-role="toggle"]');
    const knob = bar.querySelector('[data-pg-role="knob"]');

    const stateText = protectionEnabled ? "Protection ON" : "Protection OFF";
    const bridgeText = bridgeConnected ? "● Local" : "● Bridge offline";

    if (state && state.textContent !== stateText) state.textContent = stateText;
    if (bridge && bridge.textContent !== bridgeText) bridge.textContent = bridgeText;
    if (state) state.style.color = protectionEnabled ? "#86EFAC" : "#CBD5E1";
    if (bridge) bridge.style.color = bridgeConnected ? "#86EFAC" : "#FBBF24";

    if (toggle) {
      toggle.setAttribute("aria-checked", protectionEnabled ? "true" : "false");
      toggle.title = protectionEnabled
        ? "Turn PrivacyGate protection off"
        : "Turn PrivacyGate protection on";
      toggle.style.background = protectionEnabled ? "#16A34A" : "#64748B";
    }

    if (knob) {
      knob.style.transform = protectionEnabled ? "translateX(16px)" : "translateX(0)";
    }
  }

  function setProtectionEnabled(value) {
    protectionEnabled = Boolean(value);
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
    bar.id = BAR_ID;

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
    brand.title = `${PROVIDER} protection`;

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
    toggle.setAttribute("aria-label", `PrivacyGate ${PROVIDER} browser protection`);

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

    let bar = document.getElementById(BAR_ID);
    if (bar && bar.previousElementSibling === shell && bar.parentElement === shell.parentElement) {
      updateProtectionBar();
      return;
    }

    bar?.remove();
    bar = buildProtectionBar();
    shell.insertAdjacentElement("afterend", bar);
    updateProtectionBar();
  }

  function replaceComposerText(box, text) {
    if (!box) return false;
    box.focus();

    if (box instanceof HTMLTextAreaElement || box instanceof HTMLInputElement) {
      const proto = box instanceof HTMLTextAreaElement
        ? HTMLTextAreaElement.prototype
        : HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(proto, "value")?.set?.call(box, text);
      box.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
      box.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
      return normalized(composerText(box)) === normalized(text);
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

    if (!inserted || normalized(composerText(box)) !== normalized(text)) {
      box.replaceChildren(document.createTextNode(text));
      box.dispatchEvent(new InputEvent("input", {
        bubbles: true,
        composed: true,
        inputType: "insertText",
        data: text
      }));
    }

    return normalized(composerText(box)) === normalized(text);
  }

  function clearApprovedSend() {
    approvedSendText = null;
    if (approvedSendTimer) {
      clearTimeout(approvedSendTimer);
      approvedSendTimer = null;
    }
  }

  function approvedSendActive() {
    return (
      typeof approvedSendText === "string" &&
      normalized(composerText()) === normalized(approvedSendText)
    );
  }

  function approveAndSend(expectedText) {
    if (!protectionEnabled) return;
    approvedSendText = expectedText;

    const clickWhenReady = attempt => {
      if (!protectionEnabled) {
        clearApprovedSend();
        return;
      }
      const button = sendButton();
      if (button) {
        button.click();
        approvedSendTimer = setTimeout(clearApprovedSend, 2000);
        return;
      }
      if (attempt < 24) {
        setTimeout(() => clickWhenReady(attempt + 1), 60);
        return;
      }
      notice("PrivacyGate — protected text is ready. Press Send once to continue.", "error");
    };

    setTimeout(() => clickWhenReady(0), 50);
  }

  function closeReview() {
    document.getElementById(REVIEW_ID)?.remove();
    reviewOpen = false;
    composer()?.focus();
  }

  function findingValue(text, finding) {
    const start = Number(finding?.start);
    const end = Number(finding?.end);
    if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end <= start || end > text.length) {
      return "Value unavailable";
    }
    return text.slice(start, end);
  }

  function showReview(textSnapshot, findings) {
    if (!document.body) return;
    closeReview();
    reviewOpen = true;

    const overlay = style(document.createElement("div"), {
      position: "fixed",
      inset: "0",
      zIndex: "2147483647",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: "24px",
      background: "rgba(15,23,42,.42)",
      backdropFilter: "blur(2px)",
      fontFamily: "Arial, sans-serif"
    });
    overlay.id = REVIEW_ID;

    const card = style(document.createElement("section"), {
      width: "min(620px, 94vw)",
      maxHeight: "min(720px, 88vh)",
      display: "flex",
      flexDirection: "column",
      overflow: "hidden",
      background: "#FFFFFF",
      color: "#172033",
      border: "1px solid #DDE3EA",
      borderRadius: "18px",
      boxShadow: "0 24px 70px rgba(15,23,42,.28)"
    });

    const header = style(document.createElement("div"), {
      padding: "20px 22px 16px",
      borderBottom: "1px solid #E7EBF0"
    });

    const top = style(document.createElement("div"), {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      gap: "12px"
    });
    const brand = style(document.createElement("div"), {
      color: "#2348B5",
      fontSize: "12px",
      fontWeight: "850",
      letterSpacing: ".07em",
      textTransform: "uppercase"
    });
    brand.textContent = "PrivacyGate";
    const badge = style(document.createElement("span"), {
      padding: "6px 9px",
      borderRadius: "999px",
      background: "#E9F7F1",
      color: "#126246",
      fontSize: "10px",
      fontWeight: "800"
    });
    badge.textContent = "LOCAL · Protected";
    top.append(brand, badge);

    const title = style(document.createElement("h2"), {
      margin: "9px 0 5px",
      fontSize: "21px"
    });
    title.textContent = "Sensitive information detected";
    const subtitle = style(document.createElement("p"), {
      margin: "0",
      color: "#647084",
      fontSize: "12.5px"
    });
    subtitle.textContent = "Review each item before anything is sent. Checked = protect · Unchecked = keep.";
    header.append(top, title, subtitle);

    const list = style(document.createElement("div"), {
      padding: "13px 22px",
      overflowY: "auto",
      display: "flex",
      flexDirection: "column",
      gap: "8px"
    });

    for (const finding of findings) {
      const row = style(document.createElement("label"), {
        display: "grid",
        gridTemplateColumns: "22px minmax(125px,auto) 1fr",
        alignItems: "center",
        gap: "10px",
        padding: "11px 12px",
        border: "1px solid #E1E6ED",
        borderRadius: "11px",
        background: "#FBFCFE",
        cursor: "pointer"
      });
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = true;
      checkbox.dataset.findingId = String(finding?.finding_id || "");
      checkbox.style.accentColor = "#2348B5";
      const type = style(document.createElement("span"), {
        padding: "5px 8px",
        borderRadius: "999px",
        background: "#EEF3FF",
        color: "#27416F",
        fontSize: "10px",
        fontWeight: "850"
      });
      type.textContent = String(finding?.entity_type || "DETECTED").replaceAll("_", " ");
      const value = style(document.createElement("span"), {
        overflowWrap: "anywhere",
        fontSize: "12.5px",
        fontWeight: "650"
      });
      value.textContent = findingValue(textSnapshot, finding);
      row.append(checkbox, type, value);
      list.appendChild(row);
    }

    const footer = style(document.createElement("div"), {
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
      gap: "10px",
      padding: "15px 22px 18px",
      borderTop: "1px solid #E7EBF0",
      background: "#FBFCFE"
    });
    const count = style(document.createElement("span"), {
      color: "#647084",
      fontSize: "11px",
      fontWeight: "700"
    });
    count.textContent = `${findings.length} detected item${findings.length === 1 ? "" : "s"}`;

    const actions = style(document.createElement("div"), {
      display: "flex",
      gap: "8px"
    });
    const cancel = style(document.createElement("button"), {
      padding: "10px 14px",
      border: "1px solid #CDD5DF",
      borderRadius: "9px",
      background: "#FFFFFF",
      color: "#273247",
      fontWeight: "700",
      cursor: "pointer"
    });
    cancel.type = "button";
    cancel.textContent = "Cancel";
    cancel.addEventListener("click", closeReview);

    const protect = style(document.createElement("button"), {
      padding: "10px 15px",
      border: "1px solid #2348B5",
      borderRadius: "9px",
      background: "#2348B5",
      color: "#FFFFFF",
      fontWeight: "800",
      cursor: "pointer"
    });
    protect.type = "button";
    protect.textContent = "Protect & Send";
    protect.addEventListener("click", () => {
      const ids = Array.from(list.querySelectorAll('input[type="checkbox"]:checked'))
        .map(item => item.dataset.findingId)
        .filter(Boolean);
      protectAndSend(textSnapshot, ids);
    });

    actions.append(cancel, protect);
    footer.append(count, actions);
    card.append(header, list, footer);
    overlay.appendChild(card);
    document.body.appendChild(overlay);
    cancel.focus();
  }

  function analyzeAndGate() {
    if (!protectionEnabled || analysisBusy || reviewOpen) return;

    const box = composer();
    const snapshot = composerText(box);
    if (!snapshot.trim()) return;

    analysisBusy = true;
    showWorking("PrivacyGate checking…");

    chrome.runtime.sendMessage({ type: "PG_ANALYZE", text: snapshot }, response => {
      analysisBusy = false;
      hideWorking();

      if (chrome.runtime.lastError || !response?.ok) {
        bridgeConnected = false;
        updateProtectionBar();
        notice("PrivacyGate — Local Privacy Bridge is unavailable. Nothing was sent.", "error");
        return;
      }

      bridgeConnected = true;
      updateProtectionBar();

      if (normalized(composerText()) !== normalized(snapshot)) {
        notice("PrivacyGate — message changed during scan. Nothing was sent.", "error");
        return;
      }

      const findings = Array.isArray(response.data?.findings) ? response.data.findings : [];
      if (!findings.length) {
        approveAndSend(snapshot);
        return;
      }

      showReview(snapshot, findings);
    });
  }

  function protectAndSend(snapshot, findingIds) {
    const box = composer();
    if (!box || normalized(composerText(box)) !== normalized(snapshot)) {
      closeReview();
      notice("PrivacyGate — message changed after scan. Nothing was sent.", "error");
      return;
    }

    closeReview();
    analysisBusy = true;
    showWorking("PrivacyGate protecting locally…", 80);

    chrome.runtime.sendMessage({
      type: "PG_PROTECT",
      text: snapshot,
      findingIds
    }, response => {
      analysisBusy = false;
      hideWorking();

      if (chrome.runtime.lastError || !response?.ok) {
        notice("PrivacyGate — local protection failed. Nothing was sent.", "error");
        return;
      }

      const protectedText = response.data?.protected_text;
      if (typeof protectedText !== "string" || !protectedText.trim()) {
        notice("PrivacyGate — protected text was not returned. Nothing was sent.", "error");
        return;
      }

      const current = composer();
      if (!current || normalized(composerText(current)) !== normalized(snapshot)) {
        notice("PrivacyGate — message changed during protection. Nothing was sent.", "error");
        return;
      }

      if (!replaceComposerText(current, protectedText)) {
        notice(`PrivacyGate — could not safely update the ${PROVIDER} composer. Nothing was sent.`, "error");
        return;
      }

      approveAndSend(protectedText);
      notice("PrivacyGate — protected locally. Sending protected text only.", "success");
    });
  }

  function intercept(event) {
    if (!protectionEnabled || analysisBusy || reviewOpen || approvedSendActive()) return;
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    analyzeAndGate();
  }

  document.addEventListener("keydown", event => {
    if (event.key !== "Enter" || event.shiftKey || event.ctrlKey || event.altKey || event.metaKey) return;
    const box = composer();
    if (box && (event.target === box || box.contains?.(event.target))) {
      intercept(event);
    }
  }, true);

  document.addEventListener("submit", event => {
    const box = composer();
    if (!box || !(event.target instanceof HTMLFormElement) || !event.target.contains(box)) return;
    intercept(event);
  }, true);

  document.addEventListener("click", event => {
    if (!(event.target instanceof Element)) return;
    if (event.target.closest(`#${BAR_ID}, #${REVIEW_ID}`)) return;
    const button = event.target.closest('button, [role="button"]');
    const currentSend = sendButton();
    if (button && currentSend && (button === currentSend || currentSend.contains(button))) {
      intercept(event);
    }
  }, true);

  chrome.storage.local.get({ [STORAGE_KEY]: true }, values => {
    protectionEnabled = values?.[STORAGE_KEY] !== false;
    ensureProtectionBar();
    chrome.runtime.sendMessage({ type: "PG_BRIDGE_STATUS" }, response => {
      bridgeConnected = Boolean(response?.ok);
      updateProtectionBar();
    });
  });

  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName !== "local" || !changes[STORAGE_KEY]) return;
    protectionEnabled = changes[STORAGE_KEY].newValue !== false;
    updateProtectionBar();
  });

  const barTimer = setInterval(() => {
    if (!document.documentElement?.isConnected) {
      clearInterval(barTimer);
      return;
    }
    ensureProtectionBar();
  }, 1500);

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", ensureProtectionBar, { once: true });
  } else {
    ensureProtectionBar();
  }
})();
