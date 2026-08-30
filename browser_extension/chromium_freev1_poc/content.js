(() => {
  "use strict";

  if (window.top !== window) return;

  let analysisBusy = false;

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

    window.__privacyGateNoticeTimer = setTimeout(() => {
      el.remove();
    }, 3500);
  }

  function analyzeCurrentComposer() {
    const box = composer();
    const text = composerText(box).trim();

    if (!text || analysisBusy) return;

    analysisBusy = true;

    chrome.runtime.sendMessage(
      {
        type: "PG_ANALYZE",
        text
      },
      response => {
        analysisBusy = false;

        if (chrome.runtime.lastError || !response?.ok) {
          notice(
            "PrivacyGate — local analysis unavailable",
            "error"
          );
          return;
        }

        const count =
          response.data?.findings_count ?? 0;

        if (count === 0) {
          notice(
            "PrivacyGate — no sensitive data detected (POC keeps Send blocked)",
            "success"
          );
        } else {
          notice(
            `PrivacyGate — ${count} sensitive item${count === 1 ? "" : "s"} detected`,
            "normal"
          );
        }

        console.log(
          "[PrivacyGate] findings:",
          response.data?.findings || []
        );
      }
    );
  }

  function block(event, reason) {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    notice("PrivacyGate — Send blocked locally");

    console.log(
      "[PrivacyGate FreeV1] SEND BLOCKED:",
      reason
    );

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

      if (
        box &&
        (event.target === box || box.contains(event.target))
      ) {
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

  chrome.runtime.sendMessage(
    { type: "PG_BRIDGE_STATUS" },
    response => {
      if (response?.ok) {
        notice(
          "PrivacyGate — Local Bridge connected",
          "success"
        );
      }
    }
  );
})();