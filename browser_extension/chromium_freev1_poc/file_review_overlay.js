(() => {
  "use strict";

  const SOURCE = "privacygate-file-review";
  const profiles = [
    ["general_business", "General — Recommended"],
    ["property_management", "Property Management"],
    ["realtor_brokerage", "Realtor / Brokerage"],
    ["projects_renovations", "Projects & Renovations"],
    ["construction", "Construction"],
    ["legal", "Legal"],
    ["healthcare_general", "Healthcare — General"]
  ];

  const list = document.getElementById("list");
  const subtitle = document.getElementById("subtitle");
  const profile = document.getElementById("profile");
  const language = document.getElementById("language");
  const count = document.getElementById("count");
  const selected = document.getElementById("selected");
  let findings = [];

  for (const [value, label] of profiles) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    profile.appendChild(option);
  }

  function checkedIds() {
    return Array.from(list.querySelectorAll('input[type="checkbox"]:checked'))
      .map(input => input.dataset.findingId)
      .filter(Boolean);
  }

  function updateCounts() {
    const active = checkedIds().length;
    count.textContent = `${findings.length} detected item${findings.length === 1 ? "" : "s"}`;
    selected.textContent = `${active} selected`;
  }

  function render(payload) {
    findings = Array.isArray(payload.findings) ? payload.findings : [];
    subtitle.textContent = `${payload.filename || "File"} · Original values remain inside this extension-owned review surface.`;
    profile.value = payload.profileKey || "general_business";
    language.value = payload.language === "it" ? "it" : "en";
    list.replaceChildren();

    if (!findings.length) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = "No sensitive information was detected with the selected profile.";
      list.appendChild(empty);
      updateCounts();
      return;
    }

    for (const finding of findings) {
      const row = document.createElement("label");
      row.className = "row";

      const box = document.createElement("input");
      box.type = "checkbox";
      box.checked = true;
      box.dataset.findingId = String(finding.finding_id || "");
      box.addEventListener("change", updateCounts);

      const type = document.createElement("span");
      type.className = "type";
      type.textContent = String(finding.entity_type || "SENSITIVE");

      const value = document.createElement("span");
      value.className = "value";
      value.textContent = String(finding.display_value || "Detected value");

      const location = document.createElement("span");
      location.className = "location";
      location.textContent = String(finding.location || (finding.page_number ? `Page/segment ${finding.page_number}` : ""));

      row.append(box, type, value, location);
      list.appendChild(row);
    }
    updateCounts();
  }

  function reply(action) {
    parent.postMessage({
      source: SOURCE,
      type: "PG_FILE_REVIEW_RESULT",
      action,
      findingIds: checkedIds(),
      profileKey: profile.value,
      language: language.value
    }, "*");
  }

  document.getElementById("all").addEventListener("click", () => {
    list.querySelectorAll('input[type="checkbox"]').forEach(input => { input.checked = true; });
    updateCounts();
  });
  document.getElementById("none").addEventListener("click", () => {
    list.querySelectorAll('input[type="checkbox"]').forEach(input => { input.checked = false; });
    updateCounts();
  });
  document.getElementById("cancel").addEventListener("click", () => reply("cancel"));
  document.getElementById("rescan").addEventListener("click", () => reply("rescan"));
  document.getElementById("protect").addEventListener("click", () => reply("protect"));

  window.addEventListener("message", event => {
    const data = event.data;
    if (!data || data.source !== SOURCE || data.type !== "PG_FILE_REVIEW_INIT") return;
    render(data.payload || {});
  });

  parent.postMessage({ source: SOURCE, type: "PG_FILE_REVIEW_READY" }, "*");
})();
