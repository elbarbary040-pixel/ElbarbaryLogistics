/**
 * تفعيل أزرار الشريط السفلي عند اختيار أوردرات (checkbox name="order_ids").
 */
(function () {
  function refresh() {
    const boxes = document.querySelectorAll('input[name="order_ids"]:checked');
    const n = boxes.length;
    document.querySelectorAll("[data-requires-selection]").forEach(function (btn) {
      btn.disabled = n === 0;
    });
    const badge = document.getElementById("bulk-selection-count");
    if (badge) badge.textContent = String(n);
  }
  document.addEventListener("change", function (e) {
    if (e.target && e.target.name === "order_ids") refresh();
    if (e.target && (e.target.id === "select-all-orders" || e.target.id === "select-all")) {
      const on = e.target.checked;
      document.querySelectorAll('input[name="order_ids"]').forEach(function (c) {
        c.checked = on;
      });
      refresh();
    }
  });
  document.addEventListener("DOMContentLoaded", refresh);
})();
