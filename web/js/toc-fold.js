// Right-hand "Table of contents": items deeper than the numbered [X.Y] section level (i.e.
// subsubsection headings and below, which show up unnumbered - see "Packet format"/"Operation"
// nested under "[7.2] Ethernet Layer 2 protocol") start folded under their parent, with a small
// toggle to expand them, instead of always listing every sub-heading. Only the secondary
// (right-hand) TOC is touched - the primary (left) navigation sidebar keeps its own behavior.
document$.subscribe(() => {
  const toc = document.querySelector(".md-sidebar--secondary .md-nav--secondary");
  if (!toc) return;

  toc.querySelectorAll(":scope > .md-nav__list > .md-nav__item").forEach((item) => {
    const nested = item.querySelector(":scope > nav.md-nav");
    if (!nested) return; // no subsubsections - nothing to fold

    const link = item.querySelector(":scope > .md-nav__link");
    if (!link || item.querySelector(":scope > .xoi-toc-toggle")) return;

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "xoi-toc-toggle";
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-label", nested.getAttribute("aria-label") || "");
    toggle.innerHTML =
      '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">' +
      '<path fill="currentColor" d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6z"/></svg>';
    toggle.addEventListener("click", () => {
      const expanded = item.classList.toggle("xoi-toc-expanded");
      toggle.setAttribute("aria-expanded", String(expanded));
    });
    link.insertAdjacentElement("afterend", toggle);
  });
});
