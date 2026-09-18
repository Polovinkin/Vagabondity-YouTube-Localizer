const copyButtons = document.querySelectorAll("[data-copy]");

copyButtons.forEach((button) => {
    button.addEventListener("click", async () => {
        const value = button.dataset.copy;

        try {
            await navigator.clipboard.writeText(value);
            const originalLabel = button.textContent;
            button.textContent = "Copied";
            button.classList.add("copied");

            window.setTimeout(() => {
                button.textContent = originalLabel;
                button.classList.remove("copied");
            }, 1600);
        } catch {
            button.textContent = "Select text";
        }
    });
});

const stepLinks = Array.from(document.querySelectorAll(".setup-nav a"));
const steps = Array.from(document.querySelectorAll(".setup-step[data-step]"));

if ("IntersectionObserver" in window && steps.length > 0) {
    const observer = new IntersectionObserver(
        (entries) => {
            const visibleEntry = entries
                .filter((entry) => entry.isIntersecting)
                .sort((first, second) => second.intersectionRatio - first.intersectionRatio)[0];

            if (!visibleEntry) {
                return;
            }

            stepLinks.forEach((link) => {
                const isCurrent = link.getAttribute("href") === `#${visibleEntry.target.dataset.step}`;
                link.classList.toggle("is-active", isCurrent);

                if (isCurrent) {
                    link.setAttribute("aria-current", "step");
                } else {
                    link.removeAttribute("aria-current");
                }
            });
        },
        {
            rootMargin: "-18% 0px -64%",
            threshold: [0.05, 0.2, 0.5],
        },
    );

    steps.forEach((step) => observer.observe(step));
}
