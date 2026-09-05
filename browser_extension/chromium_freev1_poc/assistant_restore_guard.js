(() => {
  "use strict";

  if (window.top !== window) return;

  const STORAGE_KEY = "privacygateProtectionEnabled";
  const FRAME_CLASS = "privacygate-secure-restore-frame";
  const OVERLAY_SOURCE = "privacygate-secure-restore";
  const PLACEHOLDER_RE = /\[\[PG(?:\\?_[A-Z0-9]+)+\]\]/g;

  const HOST = location.hostname.toLowerCase();

  const PROVIDERS = {
    "chatgpt.com": {
      assistant: [
        '[data-message-author-role="assistant"]'
      ],
      user: [
        '[data-message-author-role="user"]'
      ],
      composer: [
        "#prompt-textarea"
      ],
      preferredContent: [
        ".markdown"
      ]
    },
    "gemini.google.com": {
      assistant: [
        "model-response",
        '[data-test-id="model-response"]',
        '[data-testid="model-response"]',
        ".model-response-text",
        ".response-container"
      ],
      user: [
        "user-query",
        '[data-test-id="user-query"]',
        '[data-testid="user-query"]',
        ".user-query"
      ],
      composer: [
        "rich-textarea",
        'textarea[aria-label*="prompt" i]',
        '[contenteditable="true"][role="textbox"]'
      ],
      preferredContent: [
        "message-content",
        ".model-response-text",
        ".markdown"
      ]
    },
    "claude.ai": {
      assistant: [
        '[data-testid="assistant-message"]',
        '[data-testid="assistant-message-content"]',
        '[data-testid*="assistant-message"]',
        '[data-is-streaming="true"]',
        ".font-claude-response"
      ],
      user: [
        '[data-testid="user-message"]',
        '[data-testid*="user-message"]'
      ],
      composer: [
        '[data-testid*="composer"] [contenteditable="true"]',
        '[contenteditable="true"][role="textbox"]',
        'textarea[aria-label*="message" i]'
      ],
      preferredContent: [
        '[data-testid="assistant-message-content"]',
        ".font-claude-response",
        ".markdown"
      ]
    }
  };

  const provider =
    PROVIDERS[HOST] ||
    Object.entries(PROVIDERS).find(([hostname]) => HOST.endsWith(`.${hostname}`))?.[1] ||
    { assistant: [], user: [], composer: [], preferredContent: [] };

  const COMMON_ASSISTANT_SELECTORS = [
    '[data-message-author-role="assistant"]',
    '[data-testid="assistant-message"]',
    '[data-testid="assistant-message-content"]',
    '[data-testid*="assistant-message"]',
    "model-response",
    '[data-test-id="model-response"]',
    '[data-testid="model-response"]'
  ];

  const COMMON_USER_SELECTORS = [
    '[data-message-author-role="user"]',
    '[data-testid="user-message"]',
    '[data-testid*="user-message"]',
    "user-query",
    '[data-test-id="user-query"]',
    '[data-testid="user-query"]'
  ];

  const COMMON_COMPOSER_SELECTORS = [
    "#prompt-textarea",
    "rich-textarea",
    "textarea",
    'input[type="text"]',
    '[contenteditable="true"][role="textbox"]',
    '[data-testid*="composer"] [contenteditable="true"]'
  ];

  const ASSISTANT_SELECTOR = [...new Set([...provider.assistant, ...COMMON_ASSISTANT_SELECTORS])].join(",");
  const USER_SELECTOR = [...new Set([...provider.user, ...COMMON_USER_SELECTORS])].join(",");
  const COMPOSER_SELECTOR = [...new Set([...provider.composer, ...COMMON_COMPOSER_SELECTORS])].join(",");

  const views = new Map();
  const pendingTextByRoot = new WeakMap();
  const retryAfterByRoot = new WeakMap();

  let protectionEnabled = true;
  let scanTimer = null;

  function canonicalizePlaceholders(text) {
    return String(text || "").replace(PLACEHOLDER_RE, token =>
      token.replace(/\\_/g, "_")
    );
  }

  function hasPlaceholder(text) {
    PLACEHOLDER_RE.lastIndex = 0;
    return PLACEHOLDER_RE.test(String(text || ""));
  }

  function visibleText(root) {
    if (!(root instanceof Element)) return "";
    return root.innerText || root.textContent || "";
  }

  function isExtensionUi(element) {
    if (!(element instanceof Element)) return false;
    return Boolean(
      element.closest?.(
        "#privacygate-freev1-bar," +
        "#privacygate-freev1-review," +
        "#privacygate-freev1-checking," +
        "#privacygate-freev1-notice," +
        "#privacygate-composer-sync-error," +
        "#privacygate-network-gate-toast," +
        "#privacygate-pdf-notice," +
        "#privacygate-pdf-working," +
        "#privacygate-pdf-review," +
        "#privacygate-pdf-post-attach-hint," +
        "." + FRAME_CLASS
      )
    );
  }

  function isUserOrComposer(element) {
    if (!(element instanceof Element)) return true;

    if (USER_SELECTOR && element.closest?.(USER_SELECTOR)) return true;

    if (COMPOSER_SELECTOR) {
      const composer = element.closest?.(COMPOSER_SELECTOR);
      if (composer) return true;
    }

    return false;
  }

  function excludedElement(element) {
    if (!(element instanceof Element)) return true;
    return isExtensionUi(element) || isUserOrComposer(element);
  }

  function explicitAssistantRoot(element) {
    if (!(element instanceof Element) || !ASSISTANT_SELECTOR) return null;

    if (element.matches?.(ASSISTANT_SELECTOR)) return element;
    return element.closest?.(ASSISTANT_SELECTOR) || null;
  }

  function assistantContentRoot(root) {
    if (!(root instanceof Element)) return null;

    const preferredSelectors = [
      ...provider.preferredContent,
      '[data-testid="assistant-message-content"]',
      "message-content",
      ".model-response-text",
      ".markdown"
    ];

    for (const selector of [...new Set(preferredSelectors)]) {
      if (!selector) continue;

      if (root.matches?.(selector) && hasPlaceholder(visibleText(root))) {
        return root;
      }

      const match = Array.from(root.querySelectorAll?.(selector) || [])
        .find(node => hasPlaceholder(visibleText(node)));

      if (match) return match;
    }

    return root;
  }

  function safeGenericRootFromTextNode(textNode) {
    let element = textNode?.parentElement;
    if (!(element instanceof Element) || excludedElement(element)) return null;

    const explicit = explicitAssistantRoot(element);
    if (explicit && !excludedElement(explicit)) {
      return assistantContentRoot(explicit);
    }

    // Never infer a response root from editable/form UI.
    if (element.closest?.("form")) return null;
    if (element.closest?.('[contenteditable="true"], textarea, input')) return null;

    // Prefer semantic/message wrappers used by modern AI UIs.
    const semantic = element.closest?.(
      'article,[role="article"],' +
      '[data-testid*="message"],[data-test-id*="message"],' +
      "model-response,message-content"
    );

    if (
      semantic instanceof Element &&
      !excludedElement(semantic) &&
      hasPlaceholder(visibleText(semantic))
    ) {
      return assistantContentRoot(semantic);
    }

    // Last-resort fallback: keep the restored overlay scoped to the smallest
    // meaningful block that contains the PrivacyGate placeholder.
    const block = element.closest?.(
      "p,li,pre,code,blockquote,td,th,div,section"
    );

    if (
      !(block instanceof Element) ||
      excludedElement(block) ||
      !hasPlaceholder(visibleText(block))
    ) {
      return null;
    }

    return block;
  }

  function addCandidate(roots, seen, candidate) {
    if (!(candidate instanceof Element)) return;

    const root = assistantContentRoot(candidate);
    if (
      !(root instanceof Element) ||
      seen.has(root) ||
      excludedElement(root) ||
      !hasPlaceholder(visibleText(root))
    ) {
      return;
    }

    seen.add(root);
    roots.push(root);
  }

  function candidateRoots(scope = document) {
    const roots = [];
    const seen = new Set();

    const queryScope =
      scope instanceof Element || scope instanceof Document ? scope : document;

    if (queryScope instanceof Element && ASSISTANT_SELECTOR) {
      if (queryScope.matches?.(ASSISTANT_SELECTOR)) {
        addCandidate(roots, seen, queryScope);
      }

      const ancestor = queryScope.closest?.(ASSISTANT_SELECTOR);
      if (ancestor) addCandidate(roots, seen, ancestor);
    }

    for (const assistant of queryScope.querySelectorAll?.(ASSISTANT_SELECTOR) || []) {
      addCandidate(roots, seen, assistant);
    }

    // Generic placeholder fallback. This is deliberately based on PrivacyGate's
    // unique token format rather than fragile provider CSS classes, so Claude or
    // Gemini DOM changes do not silently disable local restore.
    const walker = document.createTreeWalker(
      queryScope,
      NodeFilter.SHOW_TEXT,
      {
        acceptNode(node) {
          return hasPlaceholder(node.nodeValue)
            ? NodeFilter.FILTER_ACCEPT
            : NodeFilter.FILTER_REJECT;
        }
      }
    );

    let node = walker.nextNode();
    while (node) {
      addCandidate(roots, seen, safeGenericRootFromTextNode(node));
      node = walker.nextNode();
    }

    return roots;
  }

  function removeView(root) {
    const state = views.get(root);
    if (!state) return;
    state.frame?.remove();
    views.delete(root);
  }

  function removeAllViews() {
    for (const root of Array.from(views.keys())) removeView(root);
    document.querySelectorAll?.(`.${FRAME_CLASS}`).forEach(frame => frame.remove());
  }

  function cleanupViews() {
    for (const [root, state] of Array.from(views.entries())) {
      if (!root.isConnected || !state.frame?.isConnected || !protectionEnabled) {
        removeView(root);
      }
    }
  }

  function anchorFor(root) {
    if (!(root instanceof Element)) return root;

    const explicit = explicitAssistantRoot(root);
    return (
      explicit ||
      root.closest?.('article,[role="article"],model-response') ||
      root.parentElement ||
      root
    );
  }

  function estimatedFrameHeight(root) {
    const rectHeight = Number(root?.getBoundingClientRect?.().height || 0);
    if (!Number.isFinite(rectHeight) || rectHeight <= 0) return 140;
    return Math.max(92, Math.min(Math.ceil(rectHeight + 54), 2400));
  }

  function ensureFrame(root) {
    let state = views.get(root);
    if (state?.frame?.isConnected) return state;

    const frame = document.createElement("iframe");
    frame.className = FRAME_CLASS;
    frame.src = chrome.runtime.getURL("restore_overlay.html");
    frame.setAttribute("title", "PrivacyGate local restored view");
    frame.setAttribute("aria-label", "PrivacyGate local restored view");
    frame.setAttribute("referrerpolicy", "no-referrer");

    Object.assign(frame.style, {
      display: "block",
      width: "100%",
      minHeight: "92px",
      height: `${estimatedFrameHeight(root)}px`,
      margin: "10px 0 14px",
      border: "0",
      borderRadius: "14px",
      background: "transparent",
      overflow: "hidden",
      overflowAnchor: "none"
    });

    const anchor = anchorFor(root);

    anchor.insertAdjacentElement?.("afterend", frame);
    if (!frame.isConnected && anchor.parentElement) {
      anchor.parentElement.insertBefore(frame, anchor.nextSibling);
    }

    state = {
      frame,
      lastProtectedText: "",
      lastRestoredText: ""
    };
    views.set(root, state);

    frame.addEventListener("load", () => {
      const current = views.get(root);
      if (!current || current.frame !== frame || !current.lastRestoredText) return;
      sendToFrame(frame, current.lastRestoredText);
    });

    return state;
  }

  function sendToFrame(frame, restoredText) {
    if (!frame?.contentWindow || typeof restoredText !== "string") return;

    const targetOrigin = new URL(chrome.runtime.getURL("/")).origin;

    frame.contentWindow.postMessage(
      {
        source: OVERLAY_SOURCE,
        type: "PG_RENDER_RESTORED_TEXT",
        text: restoredText
      },
      targetOrigin
    );
  }

  function renderRestored(root, protectedText, restoredText) {
    if (!protectionEnabled || !root.isConnected) return;

    const state = ensureFrame(root);
    state.lastProtectedText = protectedText;
    state.lastRestoredText = restoredText;
    sendToFrame(state.frame, restoredText);
  }

  function restoreRoot(root) {
    if (
      !protectionEnabled ||
      !(root instanceof Element) ||
      !root.isConnected ||
      excludedElement(root)
    ) {
      return;
    }

    const rawText = visibleText(root);

    if (!hasPlaceholder(rawText)) {
      removeView(root);
      return;
    }

    const protectedText = canonicalizePlaceholders(rawText);
    const state = views.get(root);

    if (state?.lastProtectedText === protectedText && state.lastRestoredText) return;
    if (pendingTextByRoot.get(root) === protectedText) return;

    const retryAfter = Number(retryAfterByRoot.get(root) || 0);
    if (retryAfter > Date.now()) return;

    // Mount nothing until the local bridge has successfully restored the text.
    // This avoids stale frames while an AI response is still streaming.
    pendingTextByRoot.set(root, protectedText);

    chrome.runtime.sendMessage(
      {
        type: "PG_RESTORE",
        text: protectedText
      },
      response => {
        if (pendingTextByRoot.get(root) === protectedText) {
          pendingTextByRoot.delete(root);
        }

        if (
          chrome.runtime.lastError ||
          !response?.ok ||
          !root.isConnected ||
          !protectionEnabled
        ) {
          retryAfterByRoot.set(root, Date.now() + 5000);
          return;
        }

        const restoredText = response.data?.restored_text;

        if (
          typeof restoredText !== "string" ||
          !restoredText ||
          restoredText === protectedText
        ) {
          retryAfterByRoot.set(root, Date.now() + 5000);
          return;
        }

        // If the provider changed the streamed/final response while the bridge
        // call was in flight, discard the stale result and scan again.
        if (canonicalizePlaceholders(visibleText(root)) !== protectedText) {
          scheduleScan(80);
          return;
        }

        retryAfterByRoot.delete(root);

        // SECURITY BOUNDARY: restored sensitive text is never written into the
        // AI provider's DOM. It is rendered only in a chrome-extension:// iframe.
        renderRestored(root, protectedText, restoredText);
      }
    );
  }

  function scan(scope = document) {
    if (!protectionEnabled) return;

    cleanupViews();

    for (const root of candidateRoots(scope)) {
      restoreRoot(root);
    }
  }

  function scheduleScan(delay = 120, scope = document) {
    clearTimeout(scanTimer);
    scanTimer = setTimeout(() => {
      scanTimer = null;
      scan(scope);
    }, delay);
  }

  const observer = new MutationObserver(mutations => {
    if (!protectionEnabled) return;

    for (const mutation of mutations) {
      if (mutation.type === "characterData") {
        const parent = mutation.target?.parentElement;
        if (parent && hasPlaceholder(parent.textContent || "")) {
          scheduleScan(80, parent);
          return;
        }
      }

      for (const node of mutation.addedNodes || []) {
        if (!(node instanceof Element)) continue;

        if (
          hasPlaceholder(visibleText(node)) ||
          (ASSISTANT_SELECTOR && (
            node.matches?.(ASSISTANT_SELECTOR) ||
            node.querySelector?.(ASSISTANT_SELECTOR)
          ))
        ) {
          scheduleScan(80, node);
          return;
        }
      }
    }
  });

  function startObserver() {
    if (!document.documentElement) {
      setTimeout(startObserver, 25);
      return;
    }

    observer.observe(document.documentElement, {
      childList: true,
      characterData: true,
      subtree: true
    });

    scheduleScan(0);
  }

  chrome.storage.local.get({ [STORAGE_KEY]: true }, values => {
    protectionEnabled = values?.[STORAGE_KEY] !== false;

    if (protectionEnabled) {
      scheduleScan(0);
    } else {
      removeAllViews();
    }
  });

  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName !== "local" || !changes[STORAGE_KEY]) return;

    protectionEnabled = changes[STORAGE_KEY].newValue !== false;

    if (protectionEnabled) {
      scheduleScan(0);
    } else {
      removeAllViews();
    }
  });

  window.addEventListener("pageshow", () => scheduleScan(0));
  window.addEventListener("popstate", () => scheduleScan(0));

  startObserver();
})();
