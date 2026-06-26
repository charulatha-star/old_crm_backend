// document.addEventListener("DOMContentLoaded", function () {

//     const submitRow = document.querySelector(".submit-row");

//     if (!submitRow) return;

//     const btn = document.createElement("input");

//     btn.type = "button";
//     btn.value = "Generate Invoice";
//     btn.className = "default";
//     btn.style.background = "#28a745";
//     btn.style.marginTop = "10px";
//     btn.style.width = "100%";

//     submitRow.appendChild(btn);

//     btn.addEventListener("click", function () {

//         const company =
//             document.getElementById("id_company").value;

//         const invoice_month =
//             document.getElementById("id_invoice_month").value;

//         if (!company) {
//             alert("Select company");
//             return;
//         }

//         if (!invoice_month) {
//             alert("Select invoice month");
//             return;
//         }

//         btn.disabled = true;
//         btn.value = "Generating...";

//         fetch(
//             "/invoices/allinvoice/generate-auto-invoice/",
//             {
//                 method: "POST",
//                 headers: {
//                     "Content-Type":
//                         "application/x-www-form-urlencoded",
//                     "X-CSRFToken":
//                         document.querySelector(
//                             "[name=csrfmiddlewaretoken]"
//                         ).value
//                 },
//                 body:
//                     "company=" +
//                     company +
//                     "&invoice_month=" +
//                     invoice_month
//             }
//         )
//         .then(res => res.json())
//         .then(data => {

//             alert(data.message);

//             btn.disabled = false;
//             btn.value = "Generate Invoice";

//             if (data.status) {
//                 location.reload();
//             }
//         });
//     });

// });

// ------------------------------------


document.addEventListener("DOMContentLoaded", function () {

    const submitRow = document.querySelector(".submit-row");
    if (!submitRow) return;

    const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]").value;

    // ─── Helper: generic fetch + alert ───────────────────────────────────────
    function postAndAlert(url, body, btn, originalLabel) {
        btn.disabled = true;
        btn.value = "Generating...";

        fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded",
                "X-CSRFToken": csrfToken
            },
            body: body
        })
        .then(res => res.json())
        .then(data => {
            alert(data.message);
            btn.disabled = false;
            btn.value = originalLabel;
            if (data.status) location.reload();
        })
        .catch(() => {
            alert("Something went wrong. Please try again.");
            btn.disabled = false;
            btn.value = originalLabel;
        });
    }

    // ─── Button 1: Generate Invoice (single company) ─────────────────────────
    const btnSingle = document.createElement("input");
    btnSingle.type    = "button";
    btnSingle.value   = "Generate Invoice";
    btnSingle.className = "default";
    btnSingle.style.cssText = "background:#28a745;margin-top:10px;width:100%;";

    btnSingle.addEventListener("click", function () {
        const company       = document.getElementById("id_company").value;
        const invoice_month = document.getElementById("id_invoice_month").value;

        if (!company)       { alert("Select company");       return; }
        if (!invoice_month) { alert("Select invoice month"); return; }

        postAndAlert(
            "/invoices/allinvoice/generate-auto-invoice/",
            "company=" + company + "&invoice_month=" + invoice_month,
            btnSingle,
            "Generate Invoice"
        );
    });

    // ─── Button 2: Generate All Invoices (all companies for month) ────────────
    const btnAll = document.createElement("input");
    btnAll.type    = "button";
    btnAll.value   = "Generate All Invoices";
    btnAll.className = "default";
    btnAll.style.cssText = "background:#007bff;margin-top:6px;width:100%;";

    btnAll.addEventListener("click", function () {
        const invoice_month = document.getElementById("id_invoice_month").value;

        if (!invoice_month) { alert("Select invoice month"); return; }

        const confirmed = confirm(
            "This will generate invoices for ALL active companies for " +
            invoice_month + ".\n\nContinue?"
        );
        if (!confirmed) return;

        postAndAlert(
            "/invoices/allinvoice/generate-monthly-invoices/",
            "invoice_month=" + invoice_month,
            btnAll,
            "Generate All Invoices"
        );
    });

    submitRow.appendChild(btnSingle);
    submitRow.appendChild(btnAll);
});