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

document$.subscribe(async () => {
  document.querySelectorAll(".xoi-terms").forEach((el) => el.remove());
  const sidebar = document.querySelector(".md-sidebar--secondary .md-sidebar__inner");
  const conceptSpans = document.querySelectorAll(".md-content .concept[id]");
  if (!conceptSpans.length) return;

  const lang = (document.documentElement.lang || "en").slice(0, 2);
  const allTerms = await loadTerms();

  // Every highlighted occurrence in the text gets the native tooltip, not just the first.
  if (allTerms) {
    conceptSpans.forEach((span) => {
      const byLang = allTerms[span.dataset.key || ""];
      const text = tooltipText(byLang);
      if (text) span.title = text;
    });
  }
  if (!sidebar) return;

  // First occurrence only for the nav list: a term is listed once whether it repeats as the same
  // key or as the same displayed text (different keys can read the same, one key can be shown in
  // several forms).
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
  terms.sort((a, b) => a.text.localeCompare(b.text, lang, {sensitivity: "base"}));

  const nav = document.createElement("nav");
  nav.className = "md-nav xoi-terms";
  nav.setAttribute("aria-label", TITLES[lang] || TITLES.en);
  const title = document.createElement("label");
  title.className = "md-nav__title";
  title.textContent = TITLES[lang] || TITLES.en;
  const list = document.createElement("ul");
  list.className = "md-nav__list";
  for (const term of terms) {
    const item = document.createElement("li");
    item.className = "md-nav__item";
    // Not a link (this is the term itself, not a "jump to" reference): a plain span with the same
    // look, tooltip only - same as the in-text occurrences, no navigation.
    const label = document.createElement("span");
    label.className = "md-nav__link xoi-term-label";
    label.textContent = term.text;
    if (term.title) label.title = term.title;
    item.appendChild(label);
    list.appendChild(item);
  }
  nav.append(title, list);
  sidebar.appendChild(nav);
});
