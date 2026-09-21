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
