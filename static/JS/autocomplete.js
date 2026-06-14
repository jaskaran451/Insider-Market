(function () {
    "use strict";

    function createElement(tag, className) {
        const element = document.createElement(tag);

        if (className) {
            element.className = className;
        }

        return element;
    }

    function debounce(callback, delay) {
        let timer = null;

        return function (...args) {
            clearTimeout(timer);

            timer = setTimeout(function () {
                callback.apply(null, args);
            }, delay);
        };
    }

    function closeAllAutocompleteBoxes() {
    document.querySelectorAll(".company-autocomplete-box").forEach(function (box) {
        box.remove();
    });

    document.querySelectorAll(".panel-wrapper").forEach(function (panel) {
        panel.classList.remove("autocomplete-hidden");
    });
}

    function formatSuggestion(item) {
        const symbol = item.symbol || "";
        const name = item.name || "";
        const exchange = item.exchange || "";

        return `
            <div class="company-suggestion-symbol">${symbol}</div>
            <div class="company-suggestion-info">
                <strong>${name}</strong>
                <span>${exchange || "Market result"}</span>
            </div>
        `;
    }

    async function fetchCompanySuggestions(query) {
        const response = await fetch("search?q=" + encodeURIComponent(query));
        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.message || "Company search failed");
        }

        return data.results || [];
    }
    function positionAutocompleteBox(input, box) {
    const rect = input.getBoundingClientRect();

    box.style.position = "fixed";
    box.style.left = rect.left + "px";
    box.style.top = rect.bottom + 10 + "px";
    box.style.width = rect.width + "px";
    box.style.zIndex = "3000";

    const maxHeight = window.innerHeight - rect.bottom - 80;
    box.style.maxHeight = Math.max(220, maxHeight) + "px";
    box.style.overflowY = "auto";
}

    function attachCompanyAutocomplete(options) {
        const input = document.getElementById(options.inputId);

        if (!input) {
            return;
        }

        const form = options.formId ? document.getElementById(options.formId) : null;
        const hiddenInput = options.hiddenInputId ? document.getElementById(options.hiddenInputId) : null;
        const minChars = options.minChars || 2;
        const autoSubmit = options.autoSubmit === true;

        input.setAttribute("autocomplete", "off");

        const wrapper = input.closest(options.wrapperSelector || "form") || input.parentElement;

        if (wrapper) {
            wrapper.classList.add("autocomplete-wrapper");
        }

        function renderSuggestions(results) {
            closeAllAutocompleteBoxes();

            if (!results.length || !wrapper) {
                return;
            }

            const box = createElement("div", "company-autocomplete-box");
            box.dataset.ownerInput = input.id;

            results.forEach(function (item) {
                const option = createElement("button", "company-autocomplete-item");
                option.type = "button";
                option.innerHTML = formatSuggestion(item);

                option.addEventListener("click", function () {
                    input.value = item.symbol;

                    if (hiddenInput) {
                        hiddenInput.value = item.symbol;
                    }

                    input.dataset.selectedSymbol = item.symbol;
                    input.dataset.selectedName = item.name || "";

                    closeAllAutocompleteBoxes();

                    if (typeof options.onSelect === "function") {
                        options.onSelect(item);
                    }

                    if (autoSubmit && form) {
                        form.requestSubmit();
                    }
                });

                window.addEventListener("resize", function () {
                const box = document.querySelector(
                    '.company-autocomplete-box[data-owner-input="' + input.id + '"]'
                );

                if (box) {
                    positionAutocompleteBox(input, box);
                }
            });

            window.addEventListener("scroll", function () {
                const box = document.querySelector(
                    '.company-autocomplete-box[data-owner-input="' + input.id + '"]'
                );

                if (box) {
                    positionAutocompleteBox(input, box);
                }
            }, true);

                box.appendChild(option);
                document.querySelectorAll(".panel-wrapper").forEach(function (panel) {
                    panel.classList.add("autocomplete-hidden");
                });
            });

            document.body.appendChild(box);
            positionAutocompleteBox(input, box);
        }

        const handleSearch = debounce(async function () {
            const query = input.value.trim();

            if (hiddenInput) {
                hiddenInput.value = query.toUpperCase();
            }

            if (query.length < minChars) {
                closeAllAutocompleteBoxes();
                return;
            }

            try {
                const results = await fetchCompanySuggestions(query);
                renderSuggestions(results);
            } catch (error) {
                console.error(error);
                closeAllAutocompleteBoxes();
            }
        }, 300);

        input.addEventListener("input", handleSearch);

        input.addEventListener("keydown", function (event) {
            if (event.key === "Escape") {
                closeAllAutocompleteBoxes();
            }
        });

        document.addEventListener("click", function (event) {
            if (!wrapper || wrapper.contains(event.target)) {
                return;
            }

            closeAllAutocompleteBoxes();
        });
    }

    window.attachCompanyAutocomplete = attachCompanyAutocomplete;
})();