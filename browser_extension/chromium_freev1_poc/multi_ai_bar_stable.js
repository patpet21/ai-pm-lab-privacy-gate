(() => {
  "use strict";

  if (window.top !== window) return;
  const host = location.hostname.toLowerCase();
  if (!new Set(["claude.ai", "gemini.google.com"]).has(host)) return;

  const STORAGE_KEY = "privacygateProtectionEnabled";
  const BAR_ID = "privacygate-multi-ai-stable-bar";
  let enabled = true;
  let bridgeConnected = false;

  function style(el, values) {
    Object.assign(el.style, values);
    return el;
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

  function visualShell(box) {
    if (!(box instanceof Element)) return null;
    const boxRect = box.getBoundingClientRect();
    let node = box;
    let best = null;
    for (let depth = 0; depth < 9 && node?.parentElement; depth += 1) {
      node = node.parentElement;
      const rect = node.getBoundingClientRect();
      if (rect.width < Math.max(280, boxRect.width * 0.92)) continue;
      if (rect.height < 48 || rect.height > 260) continue;
      if (rect.bottom < boxRect.bottom - 6) continue;
      const desired = host === "gemini.google.com" ? 112 : 80;
      const score = Math.abs(rect.height - desired) + Math.abs(rect.width - boxRect.width) * 0.02;
      if (!best || score < best.score) best = { node, score };
    }
    return best?.node || box.parentElement;
  }

  function installHideRule() {
    if (document.getElementById("privacygate-hide-provider-owned-bar")) return;
    const tag = document.createElement("style");
    tag.id = "privacygate-hide-provider-owned-bar";
    tag.textContent = '#privacygate-freev1-bar{display:none!important;}';
    (document.head || document.documentElement).appendChild(tag);
  }

  function buildBar() {
    const outer = style(document.createElement("div"), {
      position: "fixed",
      zIndex: "2147483645",
      pointerEvents: "none",
      display: "flex",
      justifyContent: "center",
      fontFamily: "Arial, sans-serif"
    });
    outer.id = BAR_ID;

    const panel = style(document.createElement("div"), {
      display: "flex",
      alignItems: "center",
      gap: "9px",
      minHeight: "28px",
      padding: "4px 8px 4px 6px",
      border: "1px solid rgba(148,163,184,.34)",
      borderRadius: "999px",
      background: "rgba(15,23,42,.94)",
      color: "#F8FAFC",
      boxShadow: "0 4px 16px rgba(15,23,42,.22)",
      pointerEvents: "auto",
      userSelect: "none",
      backdropFilter: "blur(8px)"
    });

    const mark = style(document.createElement("span"), {
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      width: "20px", height: "20px", borderRadius: "6px",
      background: "#1D4ED8", color: "#fff", fontSize: "9px", fontWeight: "900"
    });
    mark.textContent = "PG";

    const brand = style(document.createElement("span"), { fontSize: "11px", fontWeight: "800" });
    brand.textContent = "PrivacyGate";

    const state = style(document.createElement("span"), { fontSize: "10.5px", fontWeight: "750" });
    state.dataset.pgStable = "state";
    const divider = style(document.createElement("span"), { width: "1px", height: "14px", background: "rgba(148,163,184,.35)" });
    const bridge = style(document.createElement("span"), { fontSize: "10px", fontWeight: "700" });
    bridge.dataset.pgStable = "bridge";

    const toggle = style(document.createElement("button"), {
      position: "relative", width: "38px", height: "22px", padding: "2px",
      margin: "0 0 0 2px", border: "0", borderRadius: "999px", cursor: "pointer",
      outline: "none", transition: "background .16s ease"
    });
    toggle.type = "button";
    toggle.dataset.pgStable = "toggle";
    toggle.setAttribute("role", "switch");
    toggle.setAttribute("aria-label", "PrivacyGate browser protection");

    const knob = style(document.createElement("span"), {
      display: "block", width: "18px", height: "18px", borderRadius: "50%",
      background: "#fff", boxShadow: "0 1px 4px rgba(15,23,42,.32)", transition: "transform .16s ease"
    });
    knob.dataset.pgStable = "knob";
    toggle.appendChild(knob);

    toggle.addEventListener("click", event => {
      event.preventDefault();
      event.stopPropagation();
      enabled = !enabled;
      chrome.storage.local.set({ [STORAGE_KEY]: enabled });
      update();
    });

    panel.append(mark, brand, state, divider, bridge, toggle);
    outer.appendChild(panel);
    return outer;
  }

  function ensure() {
    installHideRule();
    if (!document.body) return null;
    let bar = document.getElementById(BAR_ID);
    if (!bar) {
      bar = buildBar();
      document.body.appendChild(bar);
    }
    return bar;
  }

  function update() {
    const bar = ensure();
    if (!bar) return;
    const state = bar.querySelector('[data-pg-stable="state"]');
    const bridge = bar.querySelector('[data-pg-stable="bridge"]');
    const toggle = bar.querySelector('[data-pg-stable="toggle"]');
    const knob = bar.querySelector('[data-pg-stable="knob"]');
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

  function place() {
    const bar = ensure();
    const box = composer();
    if (!bar || !box) {
      if (bar) bar.style.visibility = "hidden";
      return;
    }
    const shell = visualShell(box);
    const rect = shell?.getBoundingClientRect?.();
    if (!rect || !Number.isFinite(rect.left) || rect.width <= 0) {
      bar.style.visibility = "hidden";
      return;
    }

    const panelWidth = Math.min(Math.max(rect.width, 280), window.innerWidth - 24);
    // Claude often places the composer flush against the viewport bottom. Keep
    // the PrivacyGate pill visually below the composer when space exists, but
    // clamp it inside the viewport instead of letting it disappear off-screen.
    const desiredTop = rect.bottom + 6;
    const safeTop = Math.max(6, Math.min(desiredTop, window.innerHeight - 34));

    Object.assign(bar.style, {
      visibility: "visible",
      left: `${Math.round(rect.left + rect.width / 2)}px`,
      top: `${Math.round(safeTop)}px`,
      width: `${Math.round(panelWidth)}px`,
      transform: "translateX(-50%)"
    });
  }

  function refreshStatus() {
    chrome.runtime.sendMessage({ type: "PG_BRIDGE_STATUS" }, response => {
      if (!chrome.runtime.lastError) {
        bridgeConnected = Boolean(response?.ok);
        update();
      }
    });
  }

  chrome.storage.local.get({ [STORAGE_KEY]: true }, values => {
    enabled = values?.[STORAGE_KEY] !== false;
    update();
    place();
    refreshStatus();
  });

  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName !== "local" || !changes[STORAGE_KEY]) return;
    enabled = changes[STORAGE_KEY].newValue !== false;
    update();
  });

  const timer = setInterval(() => {
    if (!document.documentElement?.isConnected) {
      clearInterval(timer);
      return;
    }
    place();
  }, 500);
  setInterval(refreshStatus, 5000);
  window.addEventListener("resize", place, { passive: true });
  window.addEventListener("scroll", place, { passive: true, capture: true });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => { update(); place(); }, { once: true });
  } else {
    update();
    place();
  }
})();
