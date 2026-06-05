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