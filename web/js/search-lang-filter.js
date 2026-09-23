// mkdocs-static-i18n builds one combined search index across en/es/ca by design (see
// plugins.i18n.reconfigure_search in web/mkdocs.yml - it only de-duplicates identical entries,
// it doesn't split the index per language), so a search on any page normally mixes in results
// from the other two languages. Hide any result whose page isn't in the current page's language,
// client-side, since Material always renders the full result list into the DOM regardless.
document$.subscribe(() => {
  const list = document.querySelector(".md-search-result__list");
  if (!list) return;

  const lang = (document.documentElement.lang || "en").slice(0, 2);

  function pageLang(href) {
    try {
      const path = new URL(href, location.href).pathname;
      const m = path.match(/^\/(es|ca)\//);
      return m ? m[1] : "en";
    } catch (error) {
      return "en";
    }
  }

  function filterResults() {
    list.querySelectorAll(":scope > .md-search-result__item").forEach((item) => {
      const link = item.querySelector(":scope > a.md-search-result__link");
      if (!link) return;
      item.style.display = pageLang(link.getAttribute("href")) === lang ? "" : "none";
    });
  }

  filterResults();
  // Material clears and rebuilds the <li> list on every keystroke/result update.
  new MutationObserver(filterResults).observe(list, {childList: true});
});
