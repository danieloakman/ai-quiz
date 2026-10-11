(() => {
  const timer = document.getElementById("question-timer");
  const timeoutForm = document.getElementById("timeout-form");
  if (!timer || !timeoutForm) return;

  const total = Number(timer.dataset.seconds);
  if (!Number.isFinite(total) || total < 1) return;

  const valueEl = timer.querySelector(".timer-value");
  if (!valueEl) return;

  const started = Date.now();
  let submitted = false;

  function remaining() {
    return Math.max(0, total - Math.floor((Date.now() - started) / 1000));
  }

  function paint(seconds) {
    valueEl.textContent = String(seconds);
    timer.classList.toggle("urgent", seconds <= 5);
  }

  function submitTimeout() {
    if (submitted) return;
    if (timeoutForm.dataset.busy === "1") return;
    submitted = true;
    if (typeof timeoutForm.requestSubmit === "function") {
      timeoutForm.requestSubmit();
    } else {
      timeoutForm.submit();
    }
  }

  function tick() {
    const left = remaining();
    paint(left);
    if (left <= 0) {
      submitTimeout();
      return;
    }
    window.setTimeout(tick, 250);
  }

  paint(remaining());
  window.setTimeout(tick, 250);
})();
