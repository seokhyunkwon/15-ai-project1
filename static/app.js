(function () {
  function ensureToast() {
    var toast = document.querySelector(".loading-toast");
    if (toast) return toast;
    toast = document.createElement("div");
    toast.className = "loading-toast";
    toast.setAttribute("role", "status");
    toast.setAttribute("aria-live", "polite");
    document.body.appendChild(toast);
    return toast;
  }

  function startLoading(message) {
    var toast = ensureToast();
    toast.textContent = message || "처리 중입니다...";
    document.body.classList.add("is-loading");
  }

  document.addEventListener("submit", function (event) {
    var form = event.target.closest("[data-loading-form]");
    if (!form) return;
    startLoading(form.dataset.loadingMessage);
    var button = event.submitter || form.querySelector("button[type='submit']");
    if (button) {
      button.dataset.originalText = button.textContent;
      button.textContent = form.dataset.loadingButton || "처리 중...";
      button.disabled = true;
    }
  });

  document.addEventListener("click", function (event) {
    var link = event.target.closest("[data-loading-link]");
    if (!link || link.target === "_blank" || event.defaultPrevented) return;
    startLoading(link.dataset.loadingMessage);
    link.classList.add("is-busy");
  });
})();
