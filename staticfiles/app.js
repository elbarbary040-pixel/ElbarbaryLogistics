(function () {
    function syncLayoutHeights() {
        const header = document.querySelector(".app-header");
        const footer = document.querySelector(".app-footer");
        const root = document.documentElement;

        if (header) root.style.setProperty("--app-header-height", `${header.offsetHeight}px`);
        if (footer) root.style.setProperty("--app-footer-height", `${footer.offsetHeight}px`);
    }

    function initToast() {
        const toastEl = document.getElementById("app-toast");
        const toastBody = document.getElementById("app-toast-body");
        if (!toastEl || !toastBody || typeof bootstrap === "undefined") return null;

        const toast = new bootstrap.Toast(toastEl, { delay: 2800 });

        return {
            show: (message, variant) => {
                toastEl.classList.remove("text-bg-dark", "text-bg-primary", "text-bg-success", "text-bg-warning", "text-bg-danger", "text-bg-secondary");
                toastEl.classList.add(`text-bg-${variant || "dark"}`);
                toastBody.textContent = message;
                toast.show();
            },
        };
    }

    function initComingSoon(toast) {
        document.querySelectorAll("[data-coming-soon]").forEach((btn) => {
            btn.addEventListener("click", () => {
                const msg = btn.getAttribute("data-coming-soon");
                if (!msg) return;
                if (toast) toast.show(msg, "secondary");
                else alert(msg);
            });
        });
    }

    function initBulkSelection(toast) {
        const bulkFormId = document.body.dataset.bulkFormId || "";
        if (!bulkFormId) return;

        const form = document.getElementById(bulkFormId);
        if (!form) return;

        const selectAll = form.querySelector("#select-all");
        const checkboxes = Array.from(form.querySelectorAll('input[name="order_ids"]'));
        const selectedCountEl = document.getElementById("selected-count");
        const actionButtons = Array.from(document.querySelectorAll('[data-requires-selection="true"]'));

        function selectedCount() {
            return checkboxes.filter((cb) => cb.checked).length;
        }

        function update() {
            const count = selectedCount();
            const all = checkboxes.length;

            if (selectedCountEl) selectedCountEl.textContent = String(count);

            actionButtons.forEach((btn) => {
                btn.disabled = count === 0;
            });

            if (selectAll) {
                selectAll.checked = all > 0 && count === all;
                selectAll.indeterminate = count > 0 && count < all;
            }
        }

        if (selectAll) {
            selectAll.addEventListener("change", () => {
                checkboxes.forEach((cb) => {
                    cb.checked = selectAll.checked;
                });
                update();
            });
        }

        checkboxes.forEach((cb) => cb.addEventListener("change", update));
        update();
    }

    document.addEventListener("DOMContentLoaded", () => {
        const toast = initToast();
        initComingSoon(toast);
        initBulkSelection(toast);

        syncLayoutHeights();
        window.addEventListener("resize", syncLayoutHeights);
        document.querySelectorAll(".collapse").forEach((el) => {
            el.addEventListener("shown.bs.collapse", syncLayoutHeights);
            el.addEventListener("hidden.bs.collapse", syncLayoutHeights);
        });
        document.querySelectorAll(".offcanvas").forEach((el) => {
            el.addEventListener("shown.bs.offcanvas", syncLayoutHeights);
            el.addEventListener("hidden.bs.offcanvas", syncLayoutHeights);
        });
    });
})();
