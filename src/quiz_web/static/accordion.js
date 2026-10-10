(() => {
  const DURATION = 280;
  const EASE = "cubic-bezier(0.22, 1, 0.36, 1)";

  function panelOf(details) {
    return details.querySelector(":scope > .accordion-panel");
  }

  function animate(details, open) {
    const panel = panelOf(details);
    if (!panel) {
      details.open = open;
      return;
    }

    if (details.dataset.animating === "1") return;
    details.dataset.animating = "1";

    if (open) {
      details.open = true;
      panel.style.height = "0px";
      panel.style.opacity = "0";
      panel.style.overflow = "hidden";
      const target = panel.scrollHeight;
      const anim = panel.animate(
        [
          { height: "0px", opacity: 0 },
          { height: `${target}px`, opacity: 1 },
        ],
        { duration: DURATION, easing: EASE, fill: "forwards" }
      );
      anim.onfinish = () => {
        panel.style.height = "";
        panel.style.opacity = "";
        panel.style.overflow = "";
        anim.cancel();
        details.dataset.animating = "0";
      };
      return;
    }

    const start = panel.scrollHeight;
    panel.style.height = `${start}px`;
    panel.style.opacity = "1";
    panel.style.overflow = "hidden";
    const anim = panel.animate(
      [
        { height: `${start}px`, opacity: 1 },
        { height: "0px", opacity: 0 },
      ],
      { duration: DURATION, easing: EASE, fill: "forwards" }
    );
    anim.onfinish = () => {
      details.open = false;
      panel.style.height = "";
      panel.style.opacity = "";
      panel.style.overflow = "";
      anim.cancel();
      details.dataset.animating = "0";
    };
  }

  function bind(details) {
    const summary = details.querySelector(":scope > summary");
    if (!summary || !panelOf(details)) return;
    summary.addEventListener("click", (event) => {
      event.preventDefault();
      animate(details, !details.open);
    });
  }

  document.querySelectorAll("details.accordion").forEach(bind);
})();
