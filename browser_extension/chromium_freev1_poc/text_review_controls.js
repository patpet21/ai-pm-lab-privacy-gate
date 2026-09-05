(() => {
  "use strict";

  if (window.top !== window) return;
  if (!new Set(["chatgpt.com", "claude.ai", "gemini.google.com"]).has(location.hostname.toLowerCase())) return;

  const REVIEW_ID = "privacygate-freev1-review";
  const CONTROL_ID = "privacygate-text-review-controls";
  const PROFILES = [
    ["general_business", "General — Recommended"],
    ["property_management", "Property Management"],
    ["realtor_brokerage", "Realtor / Brokerage"],
    ["projects_renovations", "Projects & Renovations"],
    ["construction", "Construction"],
    ["legal", "Legal"],
    ["healthcare_general", "Healthcare — General"]
  ];

  const ITALIAN_HINTS = new Set([
    "a", "ad", "anche", "che", "come", "con", "da", "di", "e", "è", "gli",
    "ho", "i", "il", "in", "io", "la", "le", "lo", "ma", "mi", "non", "noi",
    "per", "perché", "però", "possiamo", "puoi", "quindi", "sei", "si", "sì",
    "siamo", "sono", "su", "tra", "tu", "un", "una", "voi"
  ]);
  const ENGLISH_HINTS = new Set([
    "a", "an", "and", "are", "can", "do", "for", "how", "i", "in", "is", "it",
    "my", "not", "of", "on", "please", "that", "the", "this", "to", "we", "what",
    "with", "you", "your"
  ]);

  function style(element, values) {
    Object.assign(element.style, values);
    return element;
  }

  function composer() {
    const host = location.hostname.toLowerCase();
    if (host === "chatgpt.com") {
      return document.querySelector("#prompt-textarea") || document.querySelector('[contenteditable="true"]');
    }
    if (host === "claude.ai") {
      return (
        document.querySelector('div.ProseMirror[contenteditable="true"]') ||
        document.querySelector('[contenteditable="true"][data-placeholder]') ||
        document.querySelector('fieldset [contenteditable="true"]') ||
        document.querySelector('textarea[placeholder*="message" i]') ||
        document.querySelector("textarea")
      );
    }
    return (
      document.querySelector('rich-textarea [contenteditable="true"]') ||
      document.querySelector('.ql-editor[contenteditable="true"]') ||
      document.querySelector('[contenteditable="true"][aria-label*="prompt" i]') ||
      document.querySelector('[contenteditable="true"][aria-label*="message" i]') ||
      document.querySelector('textarea[aria-label*="prompt" i]') ||
      document.querySelector("textarea")
    );
  }

  function composerText() {
    const box = composer();
    if (!box) return "";
    if (box instanceof HTMLTextAreaElement || box instanceof HTMLInputElement) return box.value || "";
    return box.innerText || box.textContent || "";
  }

  function detectLanguage(text) {
    const raw = String(text || "").toLowerCase();
    if (/[àèéìòù]/u.test(raw)) return "it";
    const words = raw.match(/[a-zà-ÿ']+/giu) || [];
    let italian = 0;
    let english = 0;
    for (const word of words) {
      if (ITALIAN_HINTS.has(word)) italian += 1;
      if (ENGLISH_HINTS.has(word)) english += 1;
    }
    return italian >= 2 && italian > english ? "it" : "en";
  }

  function findingValue(text, finding) {
    const start = Number(finding?.start);
    const end = Number(finding?.end);
    if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end <= start || end > text.length) {
      return "Value unavailable";
    }
    return text.slice(start, end);
  }

  function buildFindingRow(textSnapshot, finding) {
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
      justifySelf: "start",
      padding: "5px 8px",
      borderRadius: "999px",
      background: "#EEF3FF",
      color: "#27416F",
      fontSize: "10px",
      fontWeight: "850",
      letterSpacing: ".015em"
    });
    type.textContent = String(finding?.entity_type || "DETECTED").replaceAll("_", " ");

    const value = style(document.createElement("span"), {
      minWidth: "0",
      overflowWrap: "anywhere",
      color: "#172033",
      fontSize: "12.5px",
      fontWeight: "650"
    });
    value.textContent = findingValue(textSnapshot, finding);

    row.append(checkbox, type, value);
    return row;
  }

  function findParts(overlay) {
    const card = overlay.querySelector("section");
    if (!card) return null;
    const children = Array.from(card.children);
    const list = children.find(child => child.querySelector?.('input[data-finding-id]'));
    if (!list) return null;
    const footer = children[children.length - 1];
    const protectButton = Array.from(card.querySelectorAll("button")).find(button =>
      /protect\s*&\s*send/i.test(button.textContent || "")
    );
    if (!protectButton) return null;
    const header = children[0];
    return { card, header, list, footer, protectButton };
  }

  function selectControl(labelText, options) {
    const wrap = style(document.createElement("label"), {
      display: "flex",
      flexDirection: "column",
      gap: "5px",
      minWidth: "170px",
      flex: "1 1 190px"
    });
    const label = style(document.createElement("span"), {
      color: "#647084",
      fontSize: "10px",
      fontWeight: "850",
      letterSpacing: ".045em",
      textTransform: "uppercase"
    });
    label.textContent = labelText;
    const select = style(document.createElement("select"), {
      width: "100%",
      minHeight: "36px",
      padding: "7px 10px",
      border: "1px solid #BCC8D8",
      borderRadius: "8px",
      background: "#FFFFFF",
      color: "#172033",
      fontSize: "12px",
      fontWeight: "650",
      outline: "none",
      cursor: "pointer"
    });
    for (const [value, text] of options) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = text;
      select.appendChild(option);
    }
    wrap.append(label, select);
    return { wrap, select };
  }

  function smallButton(text) {
    const button = style(document.createElement("button"), {
      padding: "7px 10px",
      border: "1px solid #C7D1DE",
      borderRadius: "7px",
      background: "#FFFFFF",
      color: "#273247",
      fontSize: "11px",
      fontWeight: "750",
      cursor: "pointer"
    });
    button.type = "button";
    button.textContent = text;
    return button;
  }

  function enhance(overlay) {
    if (!(overlay instanceof Element) || overlay.dataset.pgTextReviewEnhanced === "true") return;
    const parts = findParts(overlay);
    if (!parts) return;

    overlay.dataset.pgTextReviewEnhanced = "true";
    const textSnapshot = composerText();
    const initialLanguage = detectLanguage(textSnapshot);
    const { card, header, list, footer, protectButton } = parts;

    const controls = style(document.createElement("div"), {
      padding: "12px 22px 11px",
      borderBottom: "1px solid #E7EBF0",
      background: "#F8FAFD",
      display: "flex",
      flexDirection: "column",
      gap: "10px"
    });
    controls.id = CONTROL_ID;

    const mainRow = style(document.createElement("div"), {
      display: "flex",
      alignItems: "flex-end",
      gap: "9px",
      flexWrap: "wrap"
    });

    const profile = selectControl("Profile", PROFILES);
    const language = selectControl("Language", [
      ["en", "English"],
      ["it", "Italiano"]
    ]);
    language.select.value = initialLanguage;

    const rescan = smallButton("Rescan");
    style(rescan, {
      minHeight: "36px",
      padding: "7px 13px",
      borderColor: "#9DB1CF",
      color: "#2348B5"
    });

    mainRow.append(profile.wrap, language.wrap, rescan);

    const selectionRow = style(document.createElement("div"), {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      gap: "10px",
      flexWrap: "wrap"
    });
    const left = style(document.createElement("div"), {
      display: "flex",
      alignItems: "center",
      gap: "7px"
    });
    const selectAll = smallButton("Select all");
    const clearAll = smallButton("Clear all");
    left.append(selectAll, clearAll);

    const status = style(document.createElement("span"), {
      color: "#647084",
      fontSize: "11px",
      fontWeight: "750"
    });
    selectionRow.append(left, status);
    controls.append(mainRow, selectionRow);
    card.insertBefore(controls, list);

    const footerCount = Array.from(footer?.children || []).find(item => item.tagName === "SPAN");

    function checkboxes() {
      return Array.from(list.querySelectorAll('input[type="checkbox"][data-finding-id]'));
    }

    function updateSelectionStatus(extra = "") {
      const boxes = checkboxes();
      const selected = boxes.filter(box => box.checked).length;
      status.textContent = extra || `${selected} of ${boxes.length} selected`;
    }

    function setDirty() {
      protectButton.disabled = true;
      protectButton.style.opacity = ".52";
      protectButton.style.cursor = "not-allowed";
      updateSelectionStatus("Options changed · Rescan required");
    }

    function setReady() {
      protectButton.disabled = false;
      protectButton.style.opacity = "1";
      protectButton.style.cursor = "pointer";
      updateSelectionStatus();
    }

    function rebuild(findings) {
      list.replaceChildren(...findings.map(finding => buildFindingRow(textSnapshot, finding)));
      if (footerCount) {
        footerCount.textContent = `${findings.length} detected item${findings.length === 1 ? "" : "s"}`;
      }
      setReady();
      if (!findings.length) {
        protectButton.disabled = true;
        protectButton.style.opacity = ".52";
        protectButton.style.cursor = "not-allowed";
        updateSelectionStatus("No sensitive items detected with these options");
      }
    }

    list.addEventListener("change", event => {
      if (event.target instanceof HTMLInputElement && event.target.type === "checkbox") {
        updateSelectionStatus();
      }
    });

    selectAll.addEventListener("click", () => {
      checkboxes().forEach(box => { box.checked = true; });
      updateSelectionStatus();
    });
    clearAll.addEventListener("click", () => {
      checkboxes().forEach(box => { box.checked = false; });
      updateSelectionStatus();
    });

    profile.select.addEventListener("change", setDirty);
    language.select.addEventListener("change", setDirty);

    rescan.addEventListener("click", () => {
      rescan.disabled = true;
      rescan.textContent = "Scanning…";
      protectButton.disabled = true;
      updateSelectionStatus("Rescanning locally…");

      chrome.runtime.sendMessage(
        {
          type: "PG_TEXT_RESCAN",
          text: textSnapshot,
          profileKey: profile.select.value,
          language: language.select.value
        },
        response => {
          rescan.disabled = false;
          rescan.textContent = "Rescan";
          if (chrome.runtime.lastError || !response?.ok) {
            protectButton.disabled = true;
            protectButton.style.opacity = ".52";
            protectButton.style.cursor = "not-allowed";
            updateSelectionStatus("Rescan failed · nothing will be sent");
            return;
          }
          const findings = Array.isArray(response.data?.findings) ? response.data.findings : [];
          rebuild(findings);
        }
      );
    });

    chrome.runtime.sendMessage({ type: "PG_GET_EXTENSION_SETTINGS" }, response => {
      if (response?.ok && PROFILES.some(([key]) => key === response.profileKey)) {
        profile.select.value = response.profileKey;
      }
    });

    updateSelectionStatus();
  }

  function scan() {
    const overlay = document.getElementById(REVIEW_ID);
    if (overlay) enhance(overlay);
  }

  const observer = new MutationObserver(mutations => {
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes || []) {
        if (!(node instanceof Element)) continue;
        if (node.id === REVIEW_ID || node.querySelector?.(`#${REVIEW_ID}`)) {
          queueMicrotask(scan);
          return;
        }
      }
    }
  });

  observer.observe(document.documentElement, { childList: true, subtree: true });
  scan();
})();
