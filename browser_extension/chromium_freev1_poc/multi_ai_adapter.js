(() => {
  "use strict";

  if (window.top !== window) return;
  const host = location.hostname.toLowerCase();
  const PROVIDER = host === "claude.ai" ? "Claude" : host === "gemini.google.com" ? "Gemini" : null;
  if (!PROVIDER) return;

  const STORAGE_KEY = "privacygateProtectionEnabled";
  let enabled = true;
  let busy = false;
  let reviewOpen = false;
  let approvedText = null;
  let approvedTimer = null;
  let bridgeConnected = false;

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

  function sendButton() {
    const box = composer();
    const scope =
      box?.closest("form") ||
      box?.closest("fieldset") ||
      box?.closest("rich-textarea")?.parentElement?.parentElement ||
      box?.parentElement?.parentElement ||
      document;
    const selectors = [
      'button[data-testid*="send" i]',
      'button[aria-label*="send" i]',
      '[role="button"][aria-label*="send" i]',
      'button[type="submit"]'
    ];
    for (const selector of selectors) {
      const candidates = Array.from(scope.querySelectorAll?.(selector) || []);
      const button = candidates.find(item =>
        item instanceof HTMLElement &&
        item.id !== "privacygate-multi-ai-toggle" &&
        item.getAttribute("aria-disabled") !== "true" &&
        !(item instanceof HTMLButtonElement && item.disabled)
      );
      if (button) return button;
    }
    return null;
  }

  function notice(message, kind = "normal") {
    let element = document.getElementById("privacygate-multi-ai-notice");
    if (!element) {
      element = document.createElement("div");
      element.id = "privacygate-multi-ai-notice";
      style(element, {
        position: "fixed",
        left: "50%",
        top: "18%",
        transform: "translateX(-50%)",
        zIndex: "2147483647",
        maxWidth: "min(620px, calc(100vw - 32px))",
        padding: "11px 15px",
        borderRadius: "10px",
        color: "#fff",
        fontFamily: "Arial, sans-serif",
        fontSize: "13px",
        fontWeight: "750",
        boxShadow: "0 12px 34px rgba(0,0,0,.26)"
      });
      document.documentElement.appendChild(element);
    }
    element.style.background = kind === "error" ? "#991b1b" : kind === "success" ? "#065f46" : "#111827";
    element.textContent = message;
    clearTimeout(window.__privacyGateMultiAiNoticeTimer);
    window.__privacyGateMultiAiNoticeTimer = setTimeout(() => element.remove(), 4200);
  }

  function updateBar() {
    const bar = document.getElementById("privacygate-multi-ai-bar");
    if (!bar) return;
    const state = bar.querySelector('[data-pg="state"]');
    const bridge = bar.querySelector('[data-pg="bridge"]');
    const toggle = bar.querySelector('[data-pg="toggle"]');
    const knob = bar.querySelector('[data-pg="knob"]');
    if (state) {
      state.textContent = enabled ? "Protection ON" : "Protection OFF";
      state.style.color = enabled ? "#86EFAC" : "#CBD5E1";
    }
    if (bridge) {
      bridge.textContent = bridgeConnected ? "● Local" : "● Bridge offline";
      bridge.style.color = bridgeConnected ? "#86EFAC" : "#FBBF24";
    }
    if (toggle) {
      toggle.setAttribute("aria-checked", enabled ? "true" : "false");
      toggle.style.background = enabled ? "#16A34A" : "#64748B";
    }
    if (knob) knob.style.transform = enabled ? "translateX(16px)" : "translateX(0)";
  }

  function ensureBar() {
    if (document.getElementById("privacygate-multi-ai-bar")) {
      updateBar();
      return;
    }
    const bar = style(document.createElement("div"), {
      position: "fixed",
      left: "50%",
      bottom: "14px",
      transform: "translateX(-50%)",
      zIndex: "2147483645",
      display: "flex",
      alignItems: "center",
      gap: "8px",
      padding: "7px 10px",
      borderRadius: "999px",
      background: "rgba(15,23,42,.94)",
      color: "#fff",
      border: "1px solid rgba(148,163,184,.28)",
      boxShadow: "0 8px 28px rgba(15,23,42,.24)",
      fontFamily: "Arial, sans-serif",
      fontSize: "11px",
      fontWeight: "750",
      backdropFilter: "blur(8px)"
    });
    bar.id = "privacygate-multi-ai-bar";

    const mark = style(document.createElement("span"), {
      width: "18px",
      height: "18px",
      display: "grid",
      placeItems: "center",
      borderRadius: "50%",
      background: "#2348B5",
      fontSize: "10px",
      fontWeight: "900"
    });
    mark.textContent = "PG";

    const brand = document.createElement("span");
    brand.textContent = `PrivacyGate · ${PROVIDER}`;
    brand.style.fontWeight = "850";

    const state = document.createElement("span");
    state.dataset.pg = "state";
    const bridge = document.createElement("span");
    bridge.dataset.pg = "bridge";

    const toggle = style(document.createElement("button"), {
      width: "38px",
      height: "22px",
      padding: "2px",
      margin: "0 0 0 2px",
      border: "0",
      borderRadius: "999px",
      cursor: "pointer"
    });
    toggle.id = "privacygate-multi-ai-toggle";
    toggle.dataset.pg = "toggle";
    toggle.type = "button";
    toggle.setAttribute("role", "switch");
    toggle.setAttribute("aria-label", "PrivacyGate browser protection");
    const knob = style(document.createElement("span"), {
      display: "block",
      width: "18px",
      height: "18px",
      borderRadius: "50%",
      background: "#fff",
      transition: "transform .16s ease"
    });
    knob.dataset.pg = "knob";
    toggle.appendChild(knob);
    toggle.addEventListener("click", event => {
      event.preventDefault();
      event.stopPropagation();
      enabled = !enabled;
      chrome.storage.local.set({ [STORAGE_KEY]: enabled });
      updateBar();
    });

    bar.append(mark, brand, state, bridge, toggle);
    document.documentElement.appendChild(bar);
    updateBar();
  }

  function setComposerText(box, text) {
    if (!box) return false;
    box.focus();
    if (box instanceof HTMLTextAreaElement || box instanceof HTMLInputElement) {
      const proto = box instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      const descriptor = Object.getOwnPropertyDescriptor(proto, "value");
      descriptor?.set?.call(box, text);
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

  function clearApproved() {
    approvedText = null;
    clearTimeout(approvedTimer);
    approvedTimer = null;
  }

  function approvedActive() {
    return approvedText !== null && normalized(composerText()) === normalized(approvedText);
  }

  function sendApproved(text) {
    approvedText = text;
    clearTimeout(approvedTimer);
    approvedTimer = setTimeout(clearApproved, 10000);

    const trySend = attempt => {
      const button = sendButton();
      if (button) {
        button.click();
        setTimeout(clearApproved, 1600);
        return;
      }
      if (attempt < 20) {
        setTimeout(() => trySend(attempt + 1), 75);
        return;
      }
      notice("PrivacyGate protected the message locally. Press Send once to continue.", "success");
    };
    setTimeout(() => trySend(0), 60);
  }

  function findingValue(text, finding) {
    const start = Number(finding?.start);
    const end = Number(finding?.end);
    return Number.isInteger(start) && Number.isInteger(end) && start >= 0 && end > start && end <= text.length
      ? text.slice(start, end)
      : "Value unavailable";
  }

  function closeReview() {
    document.getElementById("privacygate-multi-ai-review")?.remove();
    reviewOpen = false;
    composer()?.focus();
  }

  function showReview(textSnapshot, findings) {
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
    overlay.id = "privacygate-multi-ai-review";

    const card = style(document.createElement("section"), {
      width: "min(620px, 94vw)",
      maxHeight: "min(720px, 88vh)",
      display: "flex",
      flexDirection: "column",
      overflow: "hidden",
      background: "#fff",
      color: "#172033",
      border: "1px solid #DDE3EA",
      borderRadius: "18px",
      boxShadow: "0 24px 70px rgba(15,23,42,.28)"
    });

    const header = style(document.createElement("div"), { padding: "20px 22px 16px", borderBottom: "1px solid #E7EBF0" });
    const brand = style(document.createElement("div"), { color: "#2348B5", fontSize: "12px", fontWeight: "850", letterSpacing: ".07em", textTransform: "uppercase" });
    brand.textContent = `PrivacyGate · ${PROVIDER}`;
    const title = style(document.createElement("h2"), { margin: "8px 0 5px", fontSize: "21px" });
    title.textContent = "Sensitive information detected";
    const subtitle = style(document.createElement("p"), { margin: "0", color: "#647084", fontSize: "12.5px" });
    subtitle.textContent = "Review each item before anything is sent. Checked = protect · Unchecked = keep.";
    header.append(brand, title, subtitle);

    const list = style(document.createElement("div"), { padding: "13px 22px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "8px" });
    for (const finding of findings) {
      const row = style(document.createElement("label"), {
        display: "grid", gridTemplateColumns: "22px minmax(125px,auto) 1fr", alignItems: "center", gap: "10px",
        padding: "11px 12px", border: "1px solid #E1E6ED", borderRadius: "11px", background: "#FBFCFE", cursor: "pointer"
      });
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = true;
      checkbox.dataset.findingId = String(finding?.finding_id || "");
      checkbox.style.accentColor = "#2348B5";
      const type = style(document.createElement("span"), { padding: "5px 8px", borderRadius: "999px", background: "#EEF3FF", color: "#27416F", fontSize: "10px", fontWeight: "850" });
      type.textContent = String(finding?.entity_type || "DETECTED").replaceAll("_", " ");
      const value = style(document.createElement("span"), { overflowWrap: "anywhere", fontSize: "12.5px", fontWeight: "650" });
      value.textContent = findingValue(textSnapshot, finding);
      row.append(checkbox, type, value);
      list.appendChild(row);
    }

    const footer = style(document.createElement("div"), { display: "flex", justifyContent: "space-between", alignItems: "center", gap: "10px", padding: "15px 22px 18px", borderTop: "1px solid #E7EBF0", background: "#FBFCFE" });
    const count = style(document.createElement("span"), { color: "#647084", fontSize: "11px", fontWeight: "700" });
    count.textContent = `${findings.length} detected item${findings.length === 1 ? "" : "s"}`;
    const actions = style(document.createElement("div"), { display: "flex", gap: "8px" });
    const cancel = style(document.createElement("button"), { padding: "10px 14px", border: "1px solid #CDD5DF", borderRadius: "9px", background: "#fff", color: "#273247", fontWeight: "700", cursor: "pointer" });
    cancel.type = "button";
    cancel.textContent = "Cancel";
    cancel.addEventListener("click", closeReview);
    const protect = style(document.createElement("button"), { padding: "10px 15px", border: "1px solid #2348B5", borderRadius: "9px", background: "#2348B5", color: "#fff", fontWeight: "800", cursor: "pointer" });
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
    document.documentElement.appendChild(overlay);
    cancel.focus();
  }

  function analyzeAndGate() {
    if (!enabled || busy || reviewOpen) return;
    const box = composer();
    const snapshot = composerText(box);
    if (!snapshot.trim()) return;
    busy = true;
    chrome.runtime.sendMessage({ type: "PG_ANALYZE", text: snapshot }, response => {
      busy = false;
      if (chrome.runtime.lastError || !response?.ok) {
        bridgeConnected = false;
        updateBar();
        notice("PrivacyGate — Local Privacy Bridge is unavailable. Nothing was sent.", "error");
        return;
      }
      bridgeConnected = true;
      updateBar();
      if (normalized(composerText()) !== normalized(snapshot)) {
        notice("PrivacyGate — text changed during scan. Press Send again.", "error");
        return;
      }
      const findings = Array.isArray(response.data?.findings) ? response.data.findings : [];
      if (!findings.length) {
        sendApproved(snapshot);
        return;
      }
      showReview(snapshot, findings);
    });
  }

  function protectAndSend(snapshot, findingIds) {
    const box = composer();
    if (!box || normalized(composerText(box)) !== normalized(snapshot)) {
      closeReview();
      notice("PrivacyGate — text changed after scan. Nothing was sent.", "error");
      return;
    }
    closeReview();
    busy = true;
    chrome.runtime.sendMessage({ type: "PG_PROTECT", text: snapshot, findingIds }, response => {
      busy = false;
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
        notice("PrivacyGate — text changed during protection. Nothing was sent.", "error");
        return;
      }
      if (!setComposerText(current, protectedText)) {
        notice(`PrivacyGate — could not safely update the ${PROVIDER} composer. Nothing was sent.`, "error");
        return;
      }
      sendApproved(protectedText);
      notice("PrivacyGate — protected locally. Sending protected text only.", "success");
    });
  }

  function intercept(event) {
    if (!enabled || busy || reviewOpen || approvedActive()) return;
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    analyzeAndGate();
  }

  document.addEventListener("keydown", event => {
    if (event.key !== "Enter" || event.shiftKey || event.ctrlKey || event.altKey || event.metaKey) return;
    const box = composer();
    if (box && (event.target === box || box.contains?.(event.target))) intercept(event);
  }, true);

  document.addEventListener("submit", event => {
    const box = composer();
    if (!box || !(event.target instanceof HTMLFormElement) || !event.target.contains(box)) return;
    intercept(event);
  }, true);

  document.addEventListener("click", event => {
    if (!(event.target instanceof Element)) return;
    if (event.target.closest("#privacygate-multi-ai-bar, #privacygate-multi-ai-review")) return;
    const button = event.target.closest('button, [role="button"]');
    const currentSend = sendButton();
    if (button && currentSend && (button === currentSend || currentSend.contains(button))) intercept(event);
  }, true);

  const observer = new MutationObserver(() => ensureBar());
  observer.observe(document.documentElement, { childList: true, subtree: true });

  chrome.storage.local.get({ [STORAGE_KEY]: true }, values => {
    enabled = values?.[STORAGE_KEY] !== false;
    ensureBar();
    chrome.runtime.sendMessage({ type: "PG_BRIDGE_STATUS" }, response => {
      bridgeConnected = Boolean(response?.ok);
      updateBar();
    });
  });

  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName !== "local" || !changes[STORAGE_KEY]) return;
    enabled = changes[STORAGE_KEY].newValue !== false;
    updateBar();
  });

  ensureBar();
})();
