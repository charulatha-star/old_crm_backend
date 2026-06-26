/**
 * invoice_dynamic_filter.js
 *
 * Place this file at:
 *   your_app/static/custom_admin/js/invoice_dynamic_filter.js
 *
 * Triggers a page reload with ?company=<id>&invoice_on=<date> when:
 *   - Company changes (only if invoice_on is already filled)
 *   - invoice_on changes (only if company is already selected)
 *
 * Both fields must be filled before the reload happens, ensuring
 * contact_person and campaigns are filtered by company + invoice month.
 */

(function () {
    "use strict";


    // ------------------------------------------------------------------
    // Enable / disable dependent fields
    // ------------------------------------------------------------------

    // function toggleDependentFields(companySelect, invoiceDateField) {
    //     const companyId   = companySelect ? companySelect.value : "";
    //     const invoiceDate = invoiceDateField ? invoiceDateField.value : "";
    //     const isReady     = !!(companyId && invoiceDate);

    function toggleDependentFields(companySelect, invoiceMonthField) {
        const companyId   = companySelect ? companySelect.value : "";
        const invoiceDate = invoiceMonthField ? invoiceMonthField.value : "";
        const isReady     = !!(companyId && invoiceDate);

        const dependentFields = [
            "id_contact_person",
            "id_campaigns",
            "id_additional_discount",
            "id_gst",
            "id_vat_tax",
            "id_from_company_address",
            "id_from_company_bank",
            "id_authorized_person",
        ];

        dependentFields.forEach(function (fieldId) {
            // Handle both single inputs and filter_horizontal widgets
            const field = document.getElementById(fieldId);
            if (field) {
                field.disabled = !isReady;
                field.style.opacity = isReady ? "1" : "0.4";
                field.style.pointerEvents = isReady ? "auto" : "none";
            }

            // filter_horizontal (campaigns) renders as two <select> + buttons
            const fromBox = document.getElementById(fieldId + "_from");
            const toBox   = document.getElementById(fieldId + "_to");
            [fromBox, toBox].forEach(function (el) {
                if (!el) return;
                el.disabled = !isReady;
                el.style.opacity = isReady ? "1" : "0.4";
                el.style.pointerEvents = isReady ? "auto" : "none";
            });

            // Disable the add/remove buttons for filter_horizontal
            const widget = document.querySelector(".field-" + fieldId.replace("id_", ""));
            if (widget) {
                widget.querySelectorAll("a.selector-add, a.selector-remove, a.selector-chooseall, a.selector-clearall")
                    .forEach(function (btn) {
                        btn.style.pointerEvents = isReady ? "auto" : "none";
                        btn.style.opacity       = isReady ? "1" : "0.4";
                    });
            }
        });
    }

    // ------------------------------------------------------------------
    // Loader overlay
    // ------------------------------------------------------------------

    function createLoader() {
        const overlay = document.createElement("div");
        overlay.id = "company-filter-loader";
        overlay.style.cssText = [
            "position: fixed",
            "inset: 0",
            "background: rgba(0, 0, 0, 0.45)",
            "display: flex",
            "align-items: center",
            "justify-content: center",
            "z-index: 99999",
            "flex-direction: column",
            "gap: 14px",
        ].join(";");

        // Spinner ring
        const spinner = document.createElement("div");
        spinner.style.cssText = [
            "width: 52px",
            "height: 52px",
            "border: 5px solid rgba(255,255,255,0.25)",
            "border-top-color: #ffffff",
            "border-radius: 50%",
            "animation: cfLoader-spin 0.75s linear infinite",
        ].join(";");

        // Label
        const label = document.createElement("span");
        label.textContent = "Loading\u2026";
        label.style.cssText = [
            "color: #ffffff",
            "font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
            "font-size: 14px",
            "letter-spacing: 0.04em",
        ].join(";");

        // Keyframe injection (once)
        if (!document.getElementById("cfLoader-style")) {
            const style = document.createElement("style");
            style.id = "cfLoader-style";
            style.textContent = "@keyframes cfLoader-spin { to { transform: rotate(360deg); } }";
            document.head.appendChild(style);
        }

        overlay.appendChild(spinner);
        overlay.appendChild(label);
        return overlay;
    }

    function showLoader() {
        if (!document.getElementById("company-filter-loader")) {
            document.body.appendChild(createLoader());
        }
    }

    // ------------------------------------------------------------------
    // Core reload logic
    // ------------------------------------------------------------------ invoiceMonthField

    // function buildUrlAndReload(companySelect, invoiceDateField) {
    function buildUrlAndReload(companySelect, invoiceMonthField) {
        const companyId  = companySelect ? companySelect.value : "";
        // const invoiceDate = invoiceDateField ? invoiceDateField.value : "";
        const invoiceDate = invoiceMonthField ? invoiceMonthField.value : "";

        // Both fields must be filled before reloading
        // if (companyId && !invoiceMonth) {
        if (companyId && !invoiceDate) {
            alert("First select Invoice Month");
            companySelect.value = "";  // reset company selection
            return;
        }

        showLoader();

        const url = new URL(window.location.href);
        url.searchParams.set("company", companyId);
        // url.searchParams.set("invoice_on", invoiceDate);
        url.searchParams.set("invoice_month", invoiceDate);
        window.location.href = url.toString();
    }

    // ------------------------------------------------------------------
    // Attach listeners
    // ------------------------------------------------------------------

    function init() {
        const companySelect    = document.getElementById("id_company");
        // const invoiceDateField = document.getElementById("id_invoice_on");
        const invoiceMonthField = document.getElementById("id_invoice_month");

        if (!companySelect) return;

        // Run on page load to disable fields if params are missing
        // toggleDependentFields(companySelect, invoiceDateField);
        toggleDependentFields(companySelect, invoiceMonthField);

        // Company changes → alert if invoice_on not filled, else reload
        companySelect.addEventListener("change", function () {
            const companyId   = companySelect.value;
            const invoiceDate = invoiceMonthField ? invoiceMonthField.value : "";
            // const invoiceDate = invoiceDateField ? invoiceDateField.value : "";

            if (companyId && !invoiceDate) {
                // alert("Please select an Invoice Date before choosing a Company.");
                alert("First select Invoice Month");
                companySelect.value = "";
                // toggleDependentFields(companySelect, invoiceDateField);
                toggleDependentFields(companySelect, invoiceMonthField);
                return;
            }

            // buildUrlAndReload(companySelect, invoiceDateField);
            buildUrlAndReload(companySelect, invoiceMonthField);
        });

        // invoice_on changes → update field states, reload if company also filled
        // if (invoiceDateField) {
        if (invoiceMonthField){
            // invoiceDateField.addEventListener("change", function () {
            invoiceMonthField.addEventListener("change", function () {
            
                // toggleDependentFields(companySelect, invoiceDateField);
                // buildUrlAndReload(companySelect, invoiceDateField);

                toggleDependentFields(companySelect, invoiceMonthField);
                buildUrlAndReload(companySelect, invoiceMonthField);
            });
        }
    }

    // ------------------------------------------------------------------
    // Init
    // ------------------------------------------------------------------

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }

})();













// (function () {
//     "use strict";

//     // FIX: actual Django field is "invoice_on" (model: invoice_on = DateField),
//     // so the real input id is "id_invoice_on" — NOT "id_invoice_month".
//     // We try id_invoice_on first, fallback to id_invoice_month in case
//     // the field is ever renamed.
//     function getInvoiceDateField() {
//         return document.getElementById("id_invoice_on")
//             || document.getElementById("id_invoice_month");
//     }

//     function toggleDependentFields(companySelect, invoiceDateField) {
//         const companyId = companySelect ? companySelect.value : "";
//         const invoiceDate = invoiceDateField ? invoiceDateField.value : "";
//         const isReady = !!(companyId && invoiceDate);

//         const dependentFields = [
//             "id_contact_person",
//             "id_campaigns",
//             "id_additional_discount",
//             "id_gst",
//             "id_vat_tax",
//             "id_from_company_address",
//             "id_from_company_bank",
//             "id_authorized_person",
//         ];

//         dependentFields.forEach(function (fieldId) {
//             const field = document.getElementById(fieldId);

//             if (field) {
//                 field.disabled = !isReady;
//                 field.style.opacity = isReady ? "1" : "0.4";
//             }

//             const fromBox = document.getElementById(fieldId + "_from");
//             const toBox = document.getElementById(fieldId + "_to");

//             [fromBox, toBox].forEach(function (el) {
//                 if (!el) return;

//                 el.disabled = !isReady;
//                 el.style.opacity = isReady ? "1" : "0.4";
//             });
//         });
//     }

//     function createLoader() {
//         const overlay = document.createElement("div");
//         overlay.id = "company-filter-loader";
//         overlay.style.cssText = `
//             position: fixed;
//             inset: 0;
//             background: rgba(0,0,0,0.45);
//             display: flex;
//             align-items: center;
//             justify-content: center;
//             z-index: 99999;
//         `;

//         overlay.innerHTML = `
//             <div style="
//                 width:50px;
//                 height:50px;
//                 border:5px solid rgba(255,255,255,.3);
//                 border-top-color:white;
//                 border-radius:50%;
//                 animation: spin .8s linear infinite;
//             "></div>
//         `;

//         if (!document.getElementById("loader-style")) {
//             const style = document.createElement("style");
//             style.id = "loader-style";
//             style.innerHTML = `
//                 @keyframes spin {
//                     to { transform: rotate(360deg); }
//                 }
//             `;
//             document.head.appendChild(style);
//         }

//         return overlay;
//     }

//     function showLoader() {
//         if (!document.getElementById("company-filter-loader")) {
//             document.body.appendChild(createLoader());
//         }
//     }

//     function buildUrlAndReload(companySelect, invoiceDateField) {

//         const companyId = companySelect ? companySelect.value : "";
//         const invoiceDate = invoiceDateField ? invoiceDateField.value : "";

//         console.log("Company:", companyId);
//         console.log("Invoice Date:", invoiceDate);

//         if (companyId && !invoiceDate) {
//             alert("Please select Invoice Date first");
//             companySelect.value = "";
//             return;
//         }

//         showLoader();

//         const url = new URL(window.location.href);

//         url.searchParams.set("company", companyId);
//         // FIX: backend (InvoiceAdminForm._resolve_invoice_date) reads
//         // request.GET.get("invoice_on") — keep the query param name
//         // consistent with the model field, not "invoice_month".
//         url.searchParams.set("invoice_on", invoiceDate);

//         window.location.href = url.toString();
//     }

//     function init() {

//         const companySelect = document.getElementById("id_company");
//         const invoiceDateField = getInvoiceDateField();

//         console.log("Company Field:", companySelect);
//         console.log("Invoice Date Field:", invoiceDateField);

//         if (!companySelect || !invoiceDateField) {
//             console.error("Required fields not found (id_company / id_invoice_on)");
//             return;
//         }

//         toggleDependentFields(companySelect, invoiceDateField);

//         companySelect.addEventListener("change", function () {

//             const companyId = companySelect.value;
//             const invoiceDate = invoiceDateField.value;

//             console.log("Company Changed:", companyId);
//             console.log("Invoice Date Value:", invoiceDate);

//             if (companyId && !invoiceDate) {
//                 alert("Please select Invoice Date first");
//                 companySelect.value = "";
//                 toggleDependentFields(companySelect, invoiceDateField);
//                 return;
//             }

//             buildUrlAndReload(companySelect, invoiceDateField);
//         });

//         invoiceDateField.addEventListener("change", function () {

//             toggleDependentFields(companySelect, invoiceDateField);

//             if (companySelect.value) {
//                 buildUrlAndReload(companySelect, invoiceDateField);
//             }
//         });
//     }

//     if (document.readyState === "loading") {
//         document.addEventListener("DOMContentLoaded", init);
//     } else {
//         init();
//     }

// })();