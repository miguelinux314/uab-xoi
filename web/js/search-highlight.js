// Esc clears the automatic search-result highlight (Material's
// `search.highlight`: <mark> elements plus the ?h=... URL parameter) after
// following a search result. Ignored while typing in a field (there Esc
// keeps its usual meaning, e.g. closing the search box).
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  const target = event.target;
  if (target && (target.matches("input, textarea, select") || target.isContentEditable)) return;
  document.querySelectorAll("article mark").forEach((mark) => {
    mark.replaceWith(...mark.childNodes);
  });
  const url = new URL(window.location.href);
  if (url.searchParams.has("h")) {
    url.searchParams.delete("h");
    window.history.replaceState(null, "", url);
  }
});
