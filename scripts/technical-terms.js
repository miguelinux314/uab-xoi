// Right-hand column: after the table of contents, a plain list of navigation links titled
// "Technical terms" (translated), one per term (\concept) used on the page, each pointing to the
// first place it appears (no duplicates). Both the nav links and every highlighted occurrence in
// the running text get a native title="" tooltip listing the term in every built language (no
// custom styling: just the browser's own tooltip). Data comes from assets/terms.json (key ->
// {lang: canonical text}, identical copy in every language's own assets/ - written once by
// src/uab_xoi/tex2md.py's main() from each language's first-occurrence text, i.e. the same text
// shown in the Index of Concepts), fetched via window.XOI_ASSETS (set per page by finish_page(),
// no instant-loading on this site so a plain inline <script> is enough - see web/js/wide-tables.js's
// own comment on document$ firing once).
const TITLES = {en: "Technical terms", es: "Términos técnicos", ca: "Termes tècnics"};
const LANG_LABELS = {en: "EN", es: "ES", ca: "CA"};
// Toggle button title/label per current *and next* order, since it always describes the order a
// click would switch *to* (aria-pressed reflects the current one for screen readers).
const ORDER_LABELS = {
  en: {appearance: "Sorted by order of appearance", alphabetical: "Sorted alphabetically"},
  es: {appearance: "Ordenado por orden de aparición", alphabetical: "Ordenado alfabéticamente"},
  ca: {appearance: "Ordenat per ordre d'aparició", alphabetical: "Ordenat alfabèticament"},
};
const SORT_KEY = "xoi-terms-sort"; // localStorage: "appearance" (default) or "alphabetical"

async function loadTerms() {
  try {
    const url = (window.XOI_ASSETS || "assets/") + "terms.json";
    const response = await fetch(url);
    if (!response.ok) throw new Error(response.status);
    return await response.json();
  } catch (error) {
    console.warn("technical-terms.js: could not load terms.json", error);
    return null;
  }
}

function tooltipText(byLang) {
  if (!byLang) return "";
  return Object.keys(LANG_LABELS)
    .filter((l) => byLang[l])
    .map((l) => `${LANG_LABELS[l]}: ${byLang[l]}`)
    .join("\n");
}

// Clicking a term in the sidebar jumps to its first in-page occurrence (plain #id navigation);
// this makes that occurrence briefly flash, then stay in the orange accent color so it's easy to
// spot after the jump. Only one target is ever highlighted at a time.
let xoiHighlighted = null;
function highlightTarget(id) {
  const target = document.getElementById(id);
  if (!target || !target.classList.contains("concept")) return;
  if (xoiHighlighted && xoiHighlighted !== target) xoiHighlighted.classList.remove("xoi-term-target");
  target.classList.remove("xoi-term-flash");
  // Force a reflow so re-adding the class restarts the flash animation on repeated clicks.
  void target.offsetWidth;
  target.classList.add("xoi-term-target", "xoi-term-flash");
  xoiHighlighted = target;
}

document$.subscribe(async () => {
  document.querySelectorAll(".xoi-terms").forEach((el) => el.remove());
  const sidebar = document.querySelector(".md-sidebar--secondary .md-sidebar__inner");
  const conceptSpans = document.querySelectorAll(".md-content .concept[id]");
  // The "Technical terms" index page (concepts.md) has no .concept spans of its own (it's a
  // generated index, not chapter prose), but its by-section table links and alphabetical list
  // terms still want the same per-language tooltip - both carry data-key (see tex2md.py's
  // concepts_page()).
  const indexTerms = document.querySelectorAll(".md-content [data-key]");

  // Arriving here via a link from elsewhere (e.g. the "By section" table on the Technical
  // terms page) should flash the target the same way a same-page sidebar click does; plain
  // #id navigation alone doesn't add the flash, and this page reloads (no instant loading),
  // so this only needs to run once per load, from the current hash.
  if (location.hash) highlightTarget(decodeURIComponent(location.hash.slice(1)));

  if (!conceptSpans.length && !indexTerms.length) return;

  const lang = (document.documentElement.lang || "en").slice(0, 2);
  const allTerms = await loadTerms();

  // Every highlighted occurrence in the text gets the native tooltip, not just the first.
  if (allTerms) {
    conceptSpans.forEach((span) => {
      const byLang = allTerms[span.dataset.key || ""];
      const text = tooltipText(byLang);
      if (text) span.title = text;
    });
    indexTerms.forEach((el) => {
      const byLang = allTerms[el.dataset.key || ""];
      const text = tooltipText(byLang);
      if (text) el.title = text;
    });
  }
  if (!sidebar) return;

  // First occurrence only for the nav list: a term is listed once whether it repeats as the same
  // key or as the same displayed text (different keys can read the same, one key can be shown in
  // several forms). conceptSpans is already in document order, so `terms` starts out in order of
  // first appearance on the page - that's the default sort; alphabetical is the other toggle state.
  const clean = (s) => s.trim().replace(/\s+/g, " ");
  const seenKeys = new Set();
  const seenTexts = new Set();
  const terms = [];
  conceptSpans.forEach((span) => {
    const inlineText = clean(span.textContent);
    const key = (span.dataset.key || inlineText).toLowerCase();
    const textKey = inlineText.toLowerCase();
    if (!inlineText || seenKeys.has(key) || seenTexts.has(textKey)) return;
    seenKeys.add(key);
    seenTexts.add(textKey);
    // The nav list shows the canonical (Index of Concepts) term, not whatever inflected form
    // happens to sit inline here - fall back to the inline text if terms.json has no entry.
    const byLang = allTerms && allTerms[span.dataset.key || ""];
    terms.push({id: span.id, text: (byLang && byLang[lang]) || inlineText, title: tooltipText(byLang)});
  });
  if (!terms.length) return;
  const alphabetical = terms.slice().sort((a, b) => a.text.localeCompare(b.text, lang, {sensitivity: "base"}));

  const labels = ORDER_LABELS[lang] || ORDER_LABELS.en;
  let order = "appearance";
  try {
    const saved = localStorage.getItem(SORT_KEY);
    if (saved === "alphabetical" || saved === "appearance") order = saved;
  } catch (error) { /* private mode / blocked storage: default order */ }

  const nav = document.createElement("nav");
  nav.className = "md-nav xoi-terms";
  nav.setAttribute("aria-label", TITLES[lang] || TITLES.en);
  const titleRow = document.createElement("div");
  titleRow.className = "xoi-terms-title-row";
  const title = document.createElement("label");
  title.className = "md-nav__title";
  title.textContent = TITLES[lang] || TITLES.en;
  const sortButton = document.createElement("button");
  sortButton.type = "button";
  sortButton.className = "xoi-terms-sort";
  sortButton.setAttribute("aria-label", labels.alphabetical);
  sortButton.innerHTML =
    '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">' +
    '<path fill="currentColor" d="M7 4l4 4H8v8H6V8H3l4-4zm10 16l-4-4h3V8h2v8h3l-4 4z"/></svg>';
  const list = document.createElement("ul");
  list.className = "md-nav__list";

  function render() {
    const sorted = order === "alphabetical" ? alphabetical : terms;
    sortButton.setAttribute("aria-pressed", String(order === "alphabetical"));
    sortButton.title = order === "alphabetical" ? labels.alphabetical : labels.appearance;
    list.textContent = "";
    for (const term of sorted) {
      const item = document.createElement("li");
      item.className = "md-nav__item";
      // A real link: clicking jumps to the term's first in-page occurrence, same look as the
      // in-text occurrences plus the native tooltip.
      const link = document.createElement("a");
      link.className = "md-nav__link xoi-term-label";
      link.href = "#" + term.id;
      link.textContent = term.text;
      if (term.title) link.title = term.title;
      link.addEventListener("click", () => highlightTarget(term.id));
      item.appendChild(link);
      list.appendChild(item);
    }
  }
  sortButton.addEventListener("click", () => {
    order = order === "alphabetical" ? "appearance" : "alphabetical";
    try { localStorage.setItem(SORT_KEY, order); } catch (error) { /* ignore */ }
    render();
  });
  render();

  titleRow.append(title, sortButton);
  nav.append(titleRow, list);
  sidebar.appendChild(nav);
});
