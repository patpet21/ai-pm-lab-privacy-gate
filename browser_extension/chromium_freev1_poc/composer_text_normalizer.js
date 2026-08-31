(() => {
  "use strict";

  if (window.top !== window) return;

  const PLACEHOLDER_MARKER = "[[PG_";
  const descriptor = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "innerText");

  if (!descriptor?.get) return;

  function isComposer(element) {
    return Boolean(
      element &&
      (
        element.id === "prompt-textarea" ||
        element.matches?.('[contenteditable="true"]')
      )
    );
  }

  function normalizeProtectedText(value) {
    return String(value || "")
      .replace(/\r\n?/g, "\n")
      .replace(/\u00a0/g, " ")
      .replace(/[ \t]+$/gm, "")
      .trim();
  }

  Object.defineProperty(HTMLElement.prototype, "innerText", {
    configurable: descriptor.configurable,
    enumerable: descriptor.enumerable,
    get() {
      const value = descriptor.get.call(this);
      if (isComposer(this) && String(value || "").includes(PLACEHOLDER_MARKER)) {
        return normalizeProtectedText(value);
      }
      return value;
    },
    set: descriptor.set
      ? function setInnerText(value) {
          return descriptor.set.call(this, value);
        }
      : undefined
  });
})();
