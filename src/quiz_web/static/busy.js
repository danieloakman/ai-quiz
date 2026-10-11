(() => {
  function markButton(button, message) {
    if (!button || button.dataset.busyMarked === "1") return;
    button.dataset.busyMarked = "1";
    button.classList.add("is-loading");
    button.setAttribute("aria-disabled", "true");

    const spin = document.createElement("span");
    spin.className = "spinner";
    spin.setAttribute("aria-hidden", "true");

    const label = document.createElement("span");
    label.className = "btn-label";
    label.textContent = message;

    button.replaceChildren(spin, label);
  }

  function markSelect(form, message) {
    const select = form.querySelector("select");
    if (!select) return;
    select.classList.add("is-loading");

    let status = form.querySelector(".busy-inline");
    if (!status) {
      status = document.createElement("p");
      status.className = "busy-inline";
      status.setAttribute("role", "status");
      status.setAttribute("aria-live", "polite");
      form.appendChild(status);
    }
    const spin = document.createElement("span");
    spin.className = "spinner spinner-inline";
    spin.setAttribute("aria-hidden", "true");
    status.replaceChildren(spin, document.createTextNode(` ${message}`));
  }

  function lockControls(form) {
    form.querySelectorAll("button, input, select, textarea").forEach((el) => {
      el.disabled = true;
    });
  }

  function onSubmit(event) {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;

    if (form.dataset.busy === "1") {
      event.preventDefault();
      return;
    }
    form.dataset.busy = "1";
    form.classList.add("is-busy");
    form.setAttribute("aria-busy", "true");
    document.body.classList.add("page-busy");

    const message = form.dataset.busyMessage || "Working…";
    const submitter = event.submitter;
    if (submitter instanceof HTMLElement) {
      markButton(submitter, message);
    } else {
      markSelect(form, message);
    }

    // Disable after the browser has already taken the entry list / submitter.
    setTimeout(() => lockControls(form), 0);
  }

  document.addEventListener("submit", onSubmit, true);
})();
