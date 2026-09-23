// Click-and-drag horizontal scrolling for .wide-table-inner (the missions
// coverage matrix; see web/css/xoi.css and src/uab_xoi/tex2md.py's
// wrap_wide_table). Runs on every page load (document$ also fires once on a
// normal load, matching web/js/mathjax.js's own pattern).
document$.subscribe(() => {
  document.querySelectorAll(".wide-table-inner").forEach((el) => {
    if (el.dataset.dragBound) return;
    el.dataset.dragBound = "1";

    let dragging = false;
    let startX = 0;
    let startScroll = 0;

    el.addEventListener("mousedown", (event) => {
      dragging = true;
      startX = event.pageX;
      startScroll = el.scrollLeft;
      el.classList.add("dragging");
    });
    document.addEventListener("mouseup", () => {
      dragging = false;
      el.classList.remove("dragging");
    });
    document.addEventListener("mousemove", (event) => {
      if (!dragging) return;
      event.preventDefault();
      el.scrollLeft = startScroll - (event.pageX - startX);
    });
  });
});

// Center each .wide-table on the *screen*, not on the (off-center, sidebar-
// flanked) content column that CSS alone can only center on: pull its left
// edge back to the viewport's left edge and give it the full viewport width
// (minus any scrollbar). Inline styles override the CSS fallback in xoi.css.
function alignWideTables() {
  document.querySelectorAll(".wide-table").forEach((el) => {
    el.style.left = "0px";
    el.style.marginLeft = "0px";
    const parentLeft = el.parentElement.getBoundingClientRect().left;
    el.style.marginLeft = `${-parentLeft}px`;
    el.style.width = `${document.documentElement.clientWidth}px`;
  });
}
document$.subscribe(alignWideTables);
window.addEventListener("resize", alignWideTables);

// Tooltip on each mission-coverage-matrix icon (.mission-table, see xoi.css and tex2md.py's
// wrap_wide_table) with the meaning given in the table's own key (missions/mission_index.tex's
// "$\checkmark$: ... --- $\circlearrowleft$: ... --- $\looparrowright$: ..." line). Each cell is
// a pymdownx.arithmatex span holding the raw `\(\checkmark\)`-style source; MathJax
// (web/js/mathjax.js) typesets it in place, replacing that text with the rendered symbol (and an
// assistive MathML copy holding the same symbol as real text) - match either form, since
// depending on timing this can run before or after that swap.
const MISSION_ICONS = [
  {match: ["\\checkmark", "✓"], en: "Main focus", es: "Foco principal", ca: "Focus principal"},
  {match: ["\\circlearrowleft", "↺"], en: "Review", es: "Repaso", ca: "Repàs"},
  {match: ["\\looparrowright", "↬"], en: "Foreshadow", es: "Anticipo", ca: "Anticipació"},
];
document$.subscribe(() => {
  const lang = (document.documentElement.lang || "en").slice(0, 2);
  document.querySelectorAll(".mission-table .arithmatex").forEach((el) => {
    const text = el.textContent;
    const icon = MISSION_ICONS.find((i) => i.match.some((m) => text.includes(m)));
    if (icon) el.title = icon[lang] || icon.en;
  });
});
