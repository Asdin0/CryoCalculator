(function () {
  "use strict";

  function name(holder) {
    var source = holder.querySelector(".control-name");
    if (!source) return;

    var text = source.textContent.trim();
    if (!text) return;

    var control = holder.querySelector(".dash-dropdown") ||
      holder.querySelector("button, [role='combobox'], input, select");
    if (!control || control.getAttribute("aria-label") === text) return;

    control.setAttribute("aria-label", text);

    source.setAttribute("aria-hidden", "true");
  }

  function pass() {
    Array.prototype.forEach.call(
      document.querySelectorAll(".named-control"), name);
  }

  function start() {
    pass();
    new MutationObserver(pass).observe(document.body, {
      childList: true, subtree: true
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
