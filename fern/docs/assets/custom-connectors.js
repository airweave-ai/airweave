// Hide Fern page titles on connector pages (but not overview)
(function() {
  // Function to hide title elements
  function hideConnectorTitles() {
    // Check if we're on a connector page by examining the URL (exclude overview)
    const path = window.location.pathname;
    if (path.includes('/connectors/') && !path.includes('/connectors/overview')) {
      // Try different selectors to find and hide the title
      const titleSelectors = [
        '.fern-page-heading',
        '.markdown-container > h1:first-child',
        'h1.fern-page-heading',
        'header > h1',
        '.content-container > h1'
      ];

      titleSelectors.forEach(selector => {
        const elements = document.querySelectorAll(selector);
        elements.forEach(el => {
          el.style.display = 'none';
        });
      });
    }
  }

  // Run on page load
  hideConnectorTitles();

  // Also run after any navigation events
  if (typeof MutationObserver !== 'undefined') {
    const observer = new MutationObserver(function(mutations) {
      hideConnectorTitles();
    });

    observer.observe(document.documentElement, {
      childList: true,
      subtree: true
    });
  }

  // Run again after a short delay to catch any dynamic content
  setTimeout(hideConnectorTitles, 500);
})();
