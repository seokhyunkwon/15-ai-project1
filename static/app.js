document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".summary-toggle").forEach((button) => {
    const panel = document.getElementById(button.getAttribute("aria-controls"));

    if (!panel) {
      return;
    }

    button.addEventListener("click", () => {
      const isOpen = button.getAttribute("aria-expanded") === "true";
      button.setAttribute("aria-expanded", String(!isOpen));
      panel.hidden = isOpen;
    });
  });

  const scroller = document.querySelector(".today-news-scroll");

  if (!scroller) {
    return;
  }

  const slides = Array.from(scroller.querySelectorAll(".today-news-slide"));
  const dots = Array.from(document.querySelectorAll(".news-dots button"));

  if (slides.length <= 1) {
    return;
  }

  let currentIndex = 0;
  let timerId = null;

  const setActiveDot = () => {
    dots.forEach((dot, index) => {
      dot.classList.toggle("active", index === currentIndex);
    });
  };

  const goToSlide = (nextIndex) => {
    currentIndex = (nextIndex + slides.length) % slides.length;
    scroller.scrollTo({
      left: slides[currentIndex].offsetLeft - scroller.offsetLeft,
      behavior: "smooth",
    });
    setActiveDot();
  };

  const start = () => {
    stop();
    timerId = window.setInterval(() => {
      goToSlide(currentIndex + 1);
    }, 4200);
  };

  const stop = () => {
    if (timerId) {
      window.clearInterval(timerId);
      timerId = null;
    }
  };

  dots.forEach((dot, index) => {
    dot.addEventListener("click", (event) => {
      event.preventDefault();
      goToSlide(index);
      start();
    });
  });

  scroller.addEventListener("mouseenter", stop);
  scroller.addEventListener("mouseleave", start);
  scroller.addEventListener("focusin", stop);
  scroller.addEventListener("focusout", start);

  setActiveDot();
  start();
});
