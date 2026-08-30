const state = document.getElementById("state");
const pairSection = document.getElementById("pairSection");
const codeInput = document.getElementById("code");
const pairButton = document.getElementById("pairButton");
const forgetButton = document.getElementById("forgetButton");
const message = document.getElementById("message");

function setState(kind, text) {
  state.className = kind;
  state.textContent = text;
}

function setMessage(text, isError = false) {
  message.textContent = text || "";
  message.style.color = isError ? "#B54747" : "#61798A";
}

function renderStatus(response) {
  const bridgeReady = Boolean(response?.bridgeReady);
  const paired = Boolean(response?.paired && response?.ok);

  if (!bridgeReady) {
    setState("offline", "OFFLINE");
    pairSection.hidden = false;
    forgetButton.hidden = true;
    setMessage("Open PrivacyGate desktop and enable Local Privacy Bridge.");
    return;
  }

  if (paired) {
    setState("paired", "PAIRED");
    pairSection.hidden = true;
    forgetButton.hidden = false;
    setMessage("");
    return;
  }

  setState("unpaired", "PAIR REQUIRED");
  pairSection.hidden = false;
  forgetButton.hidden = true;
  setMessage("Create an 8-digit code in PrivacyGate → Settings → Services → Browser Protection.");
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
    setMessage("Enter the complete 8-digit pairing code.", true);
    return;
  }

  pairButton.disabled = true;
  setMessage("Pairing locally…");
  chrome.runtime.sendMessage({ type: "PG_PAIR", code }, response => {
    pairButton.disabled = false;
    if (chrome.runtime.lastError || !response?.ok) {
      const detail = response?.data?.message || response?.data?.error || "Pairing failed.";
      setMessage(detail, true);
      return;
    }
    codeInput.value = "";
    setMessage("Paired. Browser Protection is ready.");
    setTimeout(refreshStatus, 100);
  });
});

forgetButton.addEventListener("click", () => {
  chrome.runtime.sendMessage({ type: "PG_FORGET_PAIRING" }, () => {
    setMessage("Local browser credential removed from this extension.");
    setTimeout(refreshStatus, 100);
  });
});

refreshStatus();
