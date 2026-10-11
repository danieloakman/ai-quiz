(() => {
  const gate = document.getElementById("next-gate");
  if (!gate) return;

  const sessionId = gate.dataset.sessionId;
  if (!sessionId || gate.querySelector(".deal-error")) return;

  let tries = 0;
  const maxTries = 120;

  async function poll() {
    tries += 1;
    try {
      const res = await fetch(`/api/play/${sessionId}`, {
        headers: { Accept: "application/json" },
      });
      if (!res.ok) throw new Error(`status ${res.status}`);
      const body = await res.json();
      if (body.deal_error) {
        window.location.reload();
        return;
      }
      if (body.question || body.finished) {
        window.location.reload();
        return;
      }
    } catch {
      // keep polling through transient errors
    }
    if (tries < maxTries) {
      window.setTimeout(poll, 400);
    } else {
      const status = document.getElementById("next-status");
      if (status) {
        status.textContent = "Timed out waiting for the next question.";
        status.classList.add("deal-error");
      }
    }
  }

  window.setTimeout(poll, 300);
})();
