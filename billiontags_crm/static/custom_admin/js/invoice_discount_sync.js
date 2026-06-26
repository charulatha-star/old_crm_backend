

document.addEventListener("DOMContentLoaded", function () {
    const discountField = document.getElementById("id_additional_discount");
    if (!discountField) return;

    // Live preview hint
    const hint = document.createElement("span");
    hint.style.cssText = "margin-left:8px; font-size:12px; font-weight:bold;";
    discountField.parentNode.appendChild(hint);

    function getBillingAmount() {
        const el = document.querySelector(".field-billing_amount .readonly");
        if (el) return parseFloat(el.textContent.replace(/[^0-9.]/g, "")) || 0;
        return 0;
    }

    discountField.addEventListener("input", function () {
        const billing = getBillingAmount();
        const val     = this.value.trim();
        if (!val || !billing) { hint.textContent = ""; return; }

        let discount = 0;
        let modeText = "";

        if (val.endsWith("%")) {
            // % mode
            const pct = parseFloat(val) || 0;
            discount  = Math.round((billing * pct / 100) * 100) / 100;
            modeText  = `→ Discount: $${discount} | Bill: $${(billing - discount).toFixed(2)}`;
            hint.style.color = "#28a745";
        } else {
            // Amount mode
            discount = parseFloat(val) || 0;
            const pct = ((discount / billing) * 100).toFixed(4);
            modeText  = `→ ${pct}% | Bill: $${(billing - discount).toFixed(2)}`;
            hint.style.color = "#007bff";
        }

        if (discount > billing) {
            hint.textContent = "⚠️ Discount exceeds billing amount!";
            hint.style.color = "#dc3545";
        } else {
            hint.textContent = modeText;
        }
    });
});