/* Keep bookmarks to the original one-page Week 1 report useful. */
(() => {
  const reportSections = new Set(["#report", "#atlas", "#degrees", "#islands", "#experiment", "#methods"]);
  if (reportSections.has(window.location.hash)) {
    window.location.replace(`week1/index.html${window.location.hash}`);
  }
})();
