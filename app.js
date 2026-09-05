// Simple interactive tab switching and filter functionality
document.addEventListener("DOMContentLoaded", () => {
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabPanes = document.querySelectorAll(".tab-pane");

  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-tab");

      // Update button states
      tabBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      // Update pane states
      tabPanes.forEach((pane) => {
        if (pane.id === targetId) {
          pane.classList.add("active");
        } else {
          pane.classList.remove("active");
        }
      });
    });
  });

  // Smooth scroll for internal links
  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener("click", function (e) {
      const href = this.getAttribute("href");
      if (href !== "#") {
        e.preventDefault();
        const targetElement = document.querySelector(href);
        if (targetElement) {
          targetElement.scrollIntoView({
            behavior: "smooth",
            block: "start"
          });
        }
      }
    });
  });
});

