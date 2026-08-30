const state = document.getElementById("state");
const connectedSection = document.getElementById("connectedSection");
const pairSection = document.getElementById("pairSection");
const codeInput = document.getElementById("code");
const pairButton = document.getElementById("pairButton");
const forgetButton = document.getElementById("forgetButton");
const message = document.getElementById("message");
const protectionState = document.getElementById("protectionState");

const PROTECTION_STORAGE_KEY = "privacygateProtectionEnabled";

function setState(kind, text) {
  state.className = kind;
  state.textContent = text;
}

function setMessage(text, isError = false) {
  message.textContent = text || "";
  message.style.color = isError ? "#B54747" : "#61798A";
}

async function refreshProtectionState() {
  const values = await chrome.storage.local.get({ [PROTECTION_STORAGE_KEY]: true });
  const enabled = values?.[PROTECTION_STORAGE_KEY] !== false;
  protectionState.textContent = enabled ? "ON" : "OFF";
  protectionState.style.background = enabled ? "#EAF8F1" : "#EEF3F7";
  protectionState.style.color = enabled ? "#23824B" : "#61798A";
}

function renderStatus(response) {
  const bridgeReady = Boolean(response?.bridgeReady);
  const paired = Boolean(response?.paired && response?.ok);

  connectedSection.hidden = true;
  pairSection.hidden = true;
  forgetButton.hidden = true;

  if (!bridgeReady) {
    setState("offline", "APP OFFLINE");
    pairSection.hidden = false;
    pairButton.disabled = true;
    setMessage("Open PrivacyGate desktop and make sure Local Privacy Bridge is running.");
    return;
  }

  if (paired) {
    setState("paired", "CONNECTED");
    connectedSection.hidden = false;
    forgetButton.hidden = false;
    setMessage("");
    refreshProtectionState();
    return;
  }

  setState("unpaired", "CONNECT ONCE");
  pairSection.hidden = false;
  pairButton.disabled = false;
  setMessage("Create a one-time code in PrivacyGate → Settings → Services → Browser Protection.");
}

function refreshStatus() {
  chrome.runtime.sendMessage({ type: "PG_BRIDGE_STATUS" }, response => {
    if (chrome.runtime.lastError) {
      renderStatus({ bridgeReady: false, paired: false });
      return;
    }
    renderStatus(response);
  });
}

codeInput.addEventListener("input", () => {
  codeInput.value = codeInput.value.replace(/\D/g, "").slice(0, 8);
});

pairButton.addEventListener("click", () => {
  const code = codeInput.value.trim();
  if (!/^\d{8}$/.test(code)) {
    setMessage("Enter the complete 8-digit connection code.", true);
    return;
  }

  pairButton.disabled = true;
  setMessage("Connecting locally…");
  chrome.runtime.sendMessage({ type: "PG_PAIR", code }, response => {
    pairButton.disabled = false;
    if (chrome.runtime.lastError || !response?.ok) {
      const detail = response?.data?.message || response?.data?.error || "Connection failed.";
      setMessage(detail, true);
      return;
    }
    codeInput.value = "";
    setMessage("Connected. Browser Protection is ready.");
    setTimeout(refreshStatus, 100);
  });
});

forgetButton.addEventListener("click", () => {
  chrome.runtime.sendMessage({ type: "PG_FORGET_PAIRING" }, () => {
    setMessage("This browser has been disconnected from PrivacyGate.");
    setTimeout(refreshStatus, 100);
  });
});

refreshStatus();
