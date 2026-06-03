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

  function activateTabs(scope, tabSelector, panelSelector, index) {
    var tabs = scope.querySelectorAll(tabSelector);
    var panels = scope.querySelectorAll(panelSelector);

    tabs.forEach(function (tab) {
      var active = tab.dataset.questionTab === String(index) || tab.dataset.answerTab === String(index);
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-pressed", active ? "true" : "false");
    });

    panels.forEach(function (panel) {
      var active = panel.dataset.questionPanel === String(index) || panel.dataset.answerPanel === String(index);
      panel.classList.toggle("active", active);
    });
  }

  function refreshQuestionLabels(builder) {
    var tabs = builder.querySelectorAll("[data-question-tab]");
    var panels = builder.querySelectorAll("[data-question-panel]");
    var removeButton = builder.querySelector("[data-remove-question]");

    tabs.forEach(function (tab, index) {
      tab.dataset.questionTab = String(index);
      tab.textContent = "Q" + (index + 1);
    });

    panels.forEach(function (panel, index) {
      var title = panel.querySelector(".question-panel-title");
      panel.dataset.questionPanel = String(index);
      if (title) title.textContent = "Q" + (index + 1) + ".";
    });

    if (removeButton) removeButton.hidden = tabs.length <= 1;
  }

  function initQuestionBuilder() {
    var builder = document.querySelector("[data-question-builder]");
    if (!builder) return;

    var tabsWrap = builder.querySelector("[data-question-tabs]");
    var panelsWrap = builder.querySelector("[data-question-panels]");
    var addButton = builder.querySelector("[data-add-question]");
    var removeButton = builder.querySelector("[data-remove-question]");
    if (!tabsWrap || !panelsWrap || !addButton) return;

    tabsWrap.addEventListener("click", function (event) {
      var tab = event.target.closest("[data-question-tab]");
      if (!tab) return;
      activateTabs(builder, "[data-question-tab]", "[data-question-panel]", tab.dataset.questionTab);
    });

    addButton.addEventListener("click", function () {
      var index = panelsWrap.querySelectorAll("[data-question-panel]").length;

      var tab = document.createElement("button");
      tab.type = "button";
      tab.className = "question-tab";
      tab.dataset.questionTab = String(index);
      tab.textContent = "Q" + (index + 1);
      tab.setAttribute("aria-pressed", "false");
      tabsWrap.insertBefore(tab, addButton);

      var panel = document.createElement("label");
      panel.className = "question-panel";
      panel.dataset.questionPanel = String(index);

      var title = document.createElement("span");
      title.className = "question-panel-title";
      title.textContent = "Q" + (index + 1) + ".";

      var input = document.createElement("input");
      input.type = "text";
      input.name = "questions";
      input.placeholder = "예: 핵심역량 및 자기소개";

      panel.appendChild(title);
      panel.appendChild(input);
      panelsWrap.appendChild(panel);
      refreshQuestionLabels(builder);
      activateTabs(builder, "[data-question-tab]", "[data-question-panel]", index);
      input.focus();
    });

    if (removeButton) {
      removeButton.addEventListener("click", function () {
        var tabs = Array.prototype.slice.call(builder.querySelectorAll("[data-question-tab]"));
        var panels = Array.prototype.slice.call(builder.querySelectorAll("[data-question-panel]"));
        if (tabs.length <= 1) return;

        var activeIndex = tabs.findIndex(function (tab) {
          return tab.classList.contains("active");
        });
        if (activeIndex < 0) activeIndex = tabs.length - 1;

        if (tabs[activeIndex]) tabs[activeIndex].remove();
        if (panels[activeIndex]) panels[activeIndex].remove();

        var nextIndex = Math.max(0, activeIndex - 1);
        refreshQuestionLabels(builder);
        activateTabs(builder, "[data-question-tab]", "[data-question-panel]", nextIndex);
      });
    }

    refreshQuestionLabels(builder);
  }

  function refreshStarCards(builder) {
    var cards = builder.querySelectorAll("[data-star-card]");
    cards.forEach(function (card, index) {
      var remove = card.querySelector("[data-remove-star]");
      card.classList.toggle("is-single", cards.length === 1);
      if (remove) remove.hidden = cards.length === 1;
    });
  }

  function createStarCard(index) {
    var card = document.createElement("article");
    card.className = "star-card";
    card.dataset.starCard = "";
    card.innerHTML =
      '<div class="star-title-row">' +
        '<label>경험 이름' +
          '<input type="text" name="star_titles" placeholder="예: AI 뉴스 브리핑 프로젝트">' +
        '</label>' +
        '<button type="button" class="star-remove" data-remove-star>삭제</button>' +
      '</div>' +
      '<div class="star-input-grid">' +
        '<label><span>S</span> Situation' +
          '<textarea name="star_situations" rows="4" placeholder="어떤 상황이었나요?"></textarea>' +
        '</label>' +
        '<label><span>T</span> Task' +
          '<textarea name="star_tasks" rows="4" placeholder="내가 맡은 역할이나 해결해야 할 과제는 무엇이었나요?"></textarea>' +
        '</label>' +
        '<label><span>A</span> Action' +
          '<textarea name="star_actions" rows="5" placeholder="내가 실제로 한 행동을 구체적으로 적어 주세요."></textarea>' +
        '</label>' +
        '<label><span>R</span> Result' +
          '<textarea name="star_results" rows="4" placeholder="결과, 성과, 배운 점은 무엇이었나요?"></textarea>' +
        '</label>' +
      '</div>';
    return card;
  }

  function initStarBuilder() {
    var builder = document.querySelector("[data-star-builder]");
    if (!builder) return;

    var list = builder.querySelector("[data-star-list]");
    var addButton = builder.querySelector("[data-add-star]");
    if (!list || !addButton) return;

    addButton.addEventListener("click", function () {
      var index = list.querySelectorAll("[data-star-card]").length;
      var card = createStarCard(index);
      list.appendChild(card);
      refreshStarCards(builder);
      var firstInput = card.querySelector("input, textarea");
      if (firstInput) firstInput.focus();
    });

    list.addEventListener("click", function (event) {
      var removeButton = event.target.closest("[data-remove-star]");
      if (!removeButton) return;
      var card = removeButton.closest("[data-star-card]");
      if (!card || list.querySelectorAll("[data-star-card]").length === 1) return;
      card.remove();
      refreshStarCards(builder);
    });

    refreshStarCards(builder);
  }

  function initAnswerTabs() {
    var tabsWrap = document.querySelector("[data-answer-tabs]");
    var panelsWrap = document.querySelector("[data-answer-panels]");
    if (!tabsWrap || !panelsWrap) return;

    var scope = tabsWrap.parentElement;
    tabsWrap.addEventListener("click", function (event) {
      var tab = event.target.closest("[data-answer-tab]");
      if (!tab) return;
      activateTabs(scope, "[data-answer-tab]", "[data-answer-panel]", tab.dataset.answerTab);
    });
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

  initQuestionBuilder();
  initStarBuilder();
  initAnswerTabs();
})();
