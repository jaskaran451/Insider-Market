(function () {

    function initToastSystem() {

        let container = document.getElementById("notification-container");

        if (!container) {
            container = document.createElement("div");
            container.id = "notification-container";
            document.body.appendChild(container);
        }

        window.notify = function (message, type = "info", duration = 4000) {

            const toast = document.createElement("div");
            toast.className = `toast ${type}`;

            toast.innerHTML = `
                <div style="padding-right:10px;">
                    ${message}
                </div>
                <div class="progress" style="animation-duration:${duration}ms"></div>
            `;

            container.appendChild(toast);

            // AUTO REMOVE (smooth exit)
            setTimeout(() => {
                toast.style.animation = "slideOut 0.35s ease forwards";

                setTimeout(() => {
                    toast.remove();
                }, 350);

            }, duration);
        };

    }

    // SAFE INIT
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initToastSystem);
    } else {
        initToastSystem();
    }

})();
(function () {
    "use strict";

    window.setInlineStatus = function (target, message, type = "info") {
        const element =
            typeof target === "string"
                ? document.getElementById(target)
                : target;

        if (!element) return;

        element.textContent = message;

        element.classList.remove("loading", "success", "error", "warning", "info");
        element.classList.add(type);
    };

    window.resetInlineStatus = function (target) {
        const element =
            typeof target === "string"
                ? document.getElementById(target)
                : target;

        if (!element) return;

        const defaultMessage =
            element.getAttribute("data-default-message") ||
            "Enter a search term to continue.";

        window.setInlineStatus(element, defaultMessage, "info");
    };
})();

(function () {
    "use strict";

    window.createStatusPipeline = function (target, steps, options = {}) {
        const element =
            typeof target === "string"
                ? document.getElementById(target)
                : target;

        if (!element || !Array.isArray(steps) || !steps.length) {
            return {
                stop: function () {},
                success: function () {},
                error: function () {}
            };
        }

        let index = 0;
        let timer = null;
        let stopped = false;

        const interval = options.interval || 1200;

        function applyStep(step, type = "loading") {
            element.textContent = step;

            element.classList.remove("loading", "success", "error", "warning", "info");
            element.classList.add(type);
        }

        function start() {
            applyStep(steps[0], "loading");

            timer = setInterval(function () {
                if (stopped) return;

                index = Math.min(index + 1, steps.length - 1);
                applyStep(steps[index], "loading");

                if (index === steps.length - 1) {
                    clearInterval(timer);
                }
            }, interval);
        }

        start();

        return {
            stop: function () {
                stopped = true;

                if (timer) {
                    clearInterval(timer);
                }
            },

            success: function (message) {
                this.stop();
                applyStep(message, "success");
            },

            error: function (message) {
                this.stop();
                applyStep(message, "error");
            }
        };
    };
})();
(function () {
    "use strict";

    window.setButtonLoading = function (button, isLoading, options = {}) {
        if (!button) return;

        const icon = button.querySelector(".btn-icon");
        const spinner = button.querySelector(".spinner");
        const loadingText = options.loadingText || "";

        if (isLoading) {
            if (!button.dataset.defaultHtml) {
                button.dataset.defaultHtml = button.innerHTML;
            }

            button.disabled = true;
            button.classList.add("button-loading");

            if (icon) icon.classList.add("hidden");
            if (spinner) spinner.classList.remove("hidden");

            if (loadingText && !icon && !spinner) {
                button.textContent = loadingText;
            }

        } else {
            button.disabled = false;
            button.classList.remove("button-loading");

            if (button.dataset.defaultHtml && !icon && !spinner) {
                button.innerHTML = button.dataset.defaultHtml;
                return;
            }

            if (icon) icon.classList.remove("hidden");
            if (spinner) spinner.classList.add("hidden");
        }
    };
})();