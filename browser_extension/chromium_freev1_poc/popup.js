const state = document.getElementById("state");
const connectedSection = document.getElementById("connectedSection");
const pairSection = document.getElementById("pairSection");
const codeInput = document.getElementById("code");
const pairButton = document.getElementById("pairButton");
const forgetButton = document.getElementById("forgetButton");
const message = document.getElementById("message");
const protectionState = document.getElementById("protectionState");
const protectionToggle = document.getElementById("protectionToggle");
const profileSelect = document.getElementById("profileSelect");
const bridgePort = document.getElementById("bridgePort");
const saveSettingsButton = document.getElementById("saveSettingsButton");

const PROTECTION_STORAGE_KEY = "privacygateProtectionEnabled";
let protectionEnabled = true;

function setState(kind, text) {
  state.className = kind;
  state.textContent = text;
}

function setMessage(text, isError = false) {
  message.textContent = text || "";
  message.style.color = isError ? "#B54747" : "#61798A";
}

function renderProtectionState(enabled) {
  protectionEnabled = Boolean(enabled);
  protectionState.textContent = protectionEnabled ? "ON" : "OFF";
  protectionState.style.color = protectionEnabled ? "#23824B" : "#61798A";
  protectionToggle.setAttribute("aria-checked", protectionEnabled ? "true" : "false");
  protectionToggle.title = protectionEnabled
    ? "Turn Browser Protection off"
    : "Turn Browser Protection on";
}

async function refreshProtectionState() {
  const values = await chrome.storage.local.get({ [PROTECTION_STORAGE_KEY]: true });
  renderProtectionState(values?.[PROTECTION_STORAGE_KEY] !== false);
}

async function setProtectionState(enabled) {
  renderProtectionState(enabled);
  await chrome.storage.local.set({ [PROTECTION_STORAGE_KEY]: Boolean(enabled) });
}

function renderStatus(response) {
  const bridgeReady = Boolean(response?.bridgeReady);
  const paired = Boolean(response?.paired && response?.ok);

  connectedSection.hidden = true;
  pairSection.hidden = true;
  forgetButton.hidden = true;

  if (response?.pairingError) {
    setState("offline", "APP ERROR");
    forgetButton.hidden = false;
    setMessage(
      "PrivacyGate responded, but the browser pairing could not be verified. Do not reconnect yet; check the desktop app and try again.",
      true
    );
    return;
  }

  if (!bridgeReady) {
    setState("offline", "APP OFFLINE");
    pairSection.hidden = false;
    pairButton.disabled = true;
    setMessage("Open PrivacyGate desktop and make sure the Local Privacy Bridge is running on the port shown below.");
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

function loadExtensionSettings() {
  chrome.runtime.sendMessage({ type: "PG_GET_EXTENSION_SETTINGS" }, response => {
    if (chrome.runtime.lastError || !response?.ok) {
      setMessage("Could not load extension settings.", true);
      return;
    }
    bridgePort.value = String(response.bridgePort || 8765);
    profileSelect.value = response.profileKey || "property_management";
  });
}

codeInput.addEventListener("input", () => {
  codeInput.value = codeInput.value.replace(/\D/g, "").slice(0, 8);
});

bridgePort.addEventListener("input", () => {
  bridgePort.value = bridgePort.value.replace(/\D/g, "").slice(0, 5);
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
      const detail = response?.data?.message || response?.data?.error || response?.error || "Connection failed.";
      setMessage(detail, true);
      return;
    }
    codeInput.value = "";
    setMessage("Connected. Browser Protection is ready.");
    setTimeout(refreshStatus, 100);
  });
});

protectionToggle.addEventListener("click", () => {
  setProtectionState(!protectionEnabled).catch(() => {
    setMessage("Could not change Browser Protection state.", true);
    refreshProtectionState();
  });
});

saveSettingsButton.addEventListener("click", () => {
  const port = Number.parseInt(bridgePort.value.trim(), 10);
  if (!Number.isInteger(port) || port < 1024 || port > 65535) {
    setMessage("Enter a desktop bridge port between 1024 and 65535.", true);
    return;
  }

  saveSettingsButton.disabled = true;
  setMessage("Saving local extension settings…");
  chrome.runtime.sendMessage(
    {
      type: "PG_SET_EXTENSION_SETTINGS",
      bridgePort: port,
      profileKey: profileSelect.value
    },
    response => {
      saveSettingsButton.disabled = false;
      if (chrome.runtime.lastError || !response?.ok) {
        setMessage(response?.error || "Could not save extension settings.", true);
        return;
      }
      bridgePort.value = String(response.bridgePort);
      profileSelect.value = response.profileKey;
      setMessage("Settings saved. Checking PrivacyGate Desktop…");
      setTimeout(refreshStatus, 100);
    }
  );
});

forgetButton.addEventListener("click", () => {
  forgetButton.disabled = true;
  setMessage("Revoking this browser credential locally…");
  chrome.runtime.sendMessage({ type: "PG_FORGET_PAIRING" }, response => {
    forgetButton.disabled = false;
    if (chrome.runtime.lastError || !response?.ok) {
      setMessage(
        response?.error || "Could not disconnect this browser. Keep PrivacyGate Desktop open and try again.",
        true
      );
      return;
    }
    setMessage("This browser has been disconnected and its desktop credential was revoked.");
    setTimeout(refreshStatus, 100);
  });
});

chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName !== "local" || !changes[PROTECTION_STORAGE_KEY]) return;
  renderProtectionState(changes[PROTECTION_STORAGE_KEY].newValue !== false);
});

refreshProtectionState();
loadExtensionSettings();
refreshStatus();
