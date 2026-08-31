(() => {
  "use strict";

  if (window.top !== window) return;

  const PLACEHOLDER_MARKER = "[[PG_";
  const nativeReplaceChildren = Element.prototype.replaceChildren;

  function isComposer(element) {
    return Boolean(
      element &&
      (
        element.id === "prompt-textarea" ||
        element.matches?.('[contenteditable="true"]')
      )
    );
  }

  function replacementText(nodes) {
    return nodes
      .map(node => {
        if (node instanceof Text) return node.nodeValue || "";
        if (node instanceof Node) return node.textContent || "";
        return String(node ?? "");
      })
      .join("");
  }

  Element.prototype.replaceChildren = function privacyGateSafeReplaceChildren(...nodes) {
    if (isComposer(this) && replacementText(nodes).includes(PLACEHOLDER_MARKER)) {
      // content.js uses replaceChildren only as a last-resort visual fallback
      // when the browser editing command was not accepted. Never allow that
      // fallback for protected text: it can make placeholders visible while the
      // site's internal editor state still contains the original sensitive text.
      console.warn(
        "[PrivacyGate FreeV1] Unsafe protected composer DOM fallback blocked."
      );
      return;
    }

    return nativeReplaceChildren.apply(this, nodes);
  };
})();
