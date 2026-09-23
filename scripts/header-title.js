// The header title (site name, e.g. "Redes de Ordenadores e Internet: Guía de Estudio") has two
// jobs beyond just sitting there:
//
// 1. On narrow screens it doesn't fit and Material truncates it with an ellipsis - swap in the
//    short "XOI: ..." form instead once that happens, so it always reads in full.
// 2. On wide screens (where navigation.tabs shows the top-level sections as a bar under the
//    header) that bar isn't sticky (navigation.tabs.sticky is off), so it scrolls away with the
//    rest of the page - once it has, splice the current section into the title too, if there's
//    still room for it.
const SITE_NAME_SHORT = {en: "XOI: Study guide", es: "XOI: Guía de estudio", ca: "XOI: Guia d'estudi"};
const WIDE_SCREEN = "(min-width: 76.25em)"; // Material's own navigation.tabs breakpoint

// The real site name, read once per page load (before updateHeaderTitle() starts overwriting
// the span's text) and kept for the rest of that load - this site reloads fully on navigation
// (no instant loading), so a fresh copy of this script, and a fresh read, runs every time.
let siteNameFull = null;

function updateHeaderTitle() {
  const span = document.querySelector(".md-header__topic:first-child .md-ellipsis");
  if (!span) return;
  if (siteNameFull === null) siteNameFull = span.textContent.trim();
  const lang = (document.documentElement.lang || "en").slice(0, 2);
  const full = siteNameFull;
  const short = SITE_NAME_SHORT[lang] || SITE_NAME_SHORT.en;

  span.textContent = full;
  let label = span.scrollWidth > span.clientWidth ? short : full;

  const tabs = document.querySelector(".md-tabs");
  const activeTab = document.querySelector(".md-tabs__item--active .md-tabs__link");
  if (tabs && activeTab && window.matchMedia(WIDE_SCREEN).matches) {
    const header = document.querySelector(".md-header");
    const headerHeight = header ? header.getBoundingClientRect().height : 0;
    const tabsHidden = tabs.getBoundingClientRect().bottom <= headerHeight;
    if (tabsHidden) {
      const withSection = `${label} — ${activeTab.textContent.trim()}`;
      span.textContent = withSection;
      if (span.scrollWidth <= span.clientWidth) label = withSection;
    }
  }
  span.textContent = label;
}

let ticking = false;
function scheduleUpdate() {
  if (ticking) return;
  ticking = true;
  requestAnimationFrame(() => {
    updateHeaderTitle();
    ticking = false;
  });
}
document$.subscribe(() => {
  updateHeaderTitle();
  window.addEventListener("scroll", scheduleUpdate, {passive: true});
});
window.addEventListener("resize", scheduleUpdate);
