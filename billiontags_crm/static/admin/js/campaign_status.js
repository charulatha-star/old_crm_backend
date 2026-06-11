// document.addEventListener('DOMContentLoaded', function () {

//     var startDateField = document.querySelector('#id_start_date');
//     var endDateField = document.querySelector('#id_end_date');
//     var statusField = document.querySelector('#id_status');

//     var originalStatus = statusField ? statusField.value : '';

//     function getToday() {
//         var now = new Date();
//         var yyyy = now.getFullYear();
//         var mm = String(now.getMonth() + 1).padStart(2, '0');
//         var dd = String(now.getDate()).padStart(2, '0');
//         return yyyy + '-' + mm + '-' + dd;
//     }

//     function updateStatus() {
//         var startDate = startDateField.value;
//         var endDate = endDateField.value;

//         if (!startDate || !endDate) return;

//         // Stopped/Paused 
//         var currentStatus = statusField.value;
//         if (currentStatus === 'Stopped' || currentStatus === 'Paused') return;


//         if ((originalStatus === 'Stopped' || originalStatus === 'Paused')) {
//             var startChanged = startDate !== originalStartDate;
//             var endChanged = endDate !== originalEndDate;
//             if (!startChanged && !endChanged) {
//                 statusField.value = originalStatus;
//                 return;
//             }
//         }

//         var todayStr = getToday(); // "2026-06-06"

//         // String comparison — timezone issue
//         if (startDate > todayStr) {
//             statusField.value = 'Scheduled';
//         } else if (startDate <= todayStr && endDate >= todayStr) {
//             statusField.value = 'Live';
//         } else if (endDate < todayStr) {
//             statusField.value = 'Completed';
//         }
//     }

//     var originalStartDate = startDateField ? startDateField.value : '';
//     var originalEndDate = endDateField ? endDateField.value : '';

//     // Status field manually change 
//     if (statusField) {
//         statusField.addEventListener('change', function () {
//             // User Stopped/Paused select 
//             if (statusField.value === 'Stopped' || statusField.value === 'Paused') {
//                 originalStatus = statusField.value;
//             }
//         });
//     }


//     // blur + change 
//     if (startDateField) {
//         startDateField.addEventListener('blur', updateStatus);
//         startDateField.addEventListener('change', updateStatus);
//     }
//     if (endDateField) {
//         endDateField.addEventListener('blur', updateStatus);
//         endDateField.addEventListener('change', updateStatus);
//     }

//     // Edit page load 
//     updateStatus();
// });



//  SECOND CHANGE 




document.addEventListener('DOMContentLoaded', function () {

    // ── Helper: get today as YYYY-MM-DD string ──────────
    function getToday() {
        var now = new Date();
        var yyyy = now.getFullYear();
        var mm = String(now.getMonth() + 1).padStart(2, '0');
        var dd = String(now.getDate()).padStart(2, '0');
        return yyyy + '-' + mm + '-' + dd;
    }

    // ── Core logic: update status based on dates ─────────
    function updateStatus(startField, endField, statusField) {
        if (!startField || !endField || !statusField) return;

        var startDate = startField.value;
        var endDate = endField.value;

        if (!startDate || !endDate) return;

        // Don't override Stopped/Paused
        var currentStatus = statusField.value;
        if (currentStatus === 'Stopped' || currentStatus === 'Paused') return;

        var todayStr = getToday();

        if (startDate > todayStr) {
            statusField.value = 'Scheduled';
        } else if (startDate <= todayStr && endDate >= todayStr) {
            statusField.value = 'Live';
        } else if (endDate < todayStr) {
            statusField.value = 'Completed';
        }
    }

    // ── Attach listeners to a set of fields ──────────────
    function attachListeners(startField, endField, statusField) {
        if (!startField || !endField || !statusField) return;

        // Status manually changed to Stopped/Paused — respect it
        statusField.addEventListener('change', function () {
            if (statusField.value === 'Stopped' || statusField.value === 'Paused') {
                statusField.dataset.manualStatus = statusField.value;
            }
        });

        function trigger() {
            // If user manually set Stopped/Paused, don't override
            if (statusField.dataset.manualStatus === 'Stopped' ||
                statusField.dataset.manualStatus === 'Paused') return;
            updateStatus(startField, endField, statusField);
        }

        startField.addEventListener('blur', trigger);
        startField.addEventListener('change', trigger);
        endField.addEventListener('blur', trigger);
        endField.addEventListener('change', trigger);

        // Run once on page load
        updateStatus(startField, endField, statusField);
    }

    // ── 1. Main form (Campaign / SubCampaign / IO / LineItem) ──
    var mainStart  = document.querySelector('#id_start_date');
    var mainEnd    = document.querySelector('#id_end_date');
    var mainStatus = document.querySelector('#id_status');
    attachListeners(mainStart, mainEnd, mainStatus);

    // ── 2. SubCampaign inline rows ────────────────────────
    // (inside Campaign change form)
    function attachInlineListeners(prefix) {
        // Handle existing rows
        document.querySelectorAll('[id^="id_' + prefix + '-"][id$="-start_date"]')
            .forEach(function (startField) {
                var rowId = startField.id.replace('start_date', '');
                // e.g. "id_sub_campaign-0-"
                var endField    = document.querySelector('#' + rowId + 'end_date');
                var statusField = document.querySelector('#' + rowId + 'status');
                attachListeners(startField, endField, statusField);
            });
    }

    // SubCampaign inline (inside Campaign form)
    attachInlineListeners('sub_campaign');

    // IO inline (inside SubCampaign form)
    attachInlineListeners('insertion_order');

    // Line Item inline (inside IO form)
    attachInlineListeners('io_details');

    // ── 3. Handle dynamically added inline rows ───────────
    // When user clicks "Add another SubCampaign/IO/LineItem"
    var observer = new MutationObserver(function (mutations) {
        mutations.forEach(function (mutation) {
            mutation.addedNodes.forEach(function (node) {
                if (node.nodeType !== 1) return; // only elements

                // Find start_date inside the new row
                var newStart = node.querySelector('[id$="-start_date"]');
                if (newStart) {
                    var rowId       = newStart.id.replace('start_date', '');
                    var newEnd      = node.querySelector('#' + rowId + 'end_date');
                    var newStatus   = node.querySelector('#' + rowId + 'status');
                    attachListeners(newStart, newEnd, newStatus);
                }
            });
        });
    });

    // Observe the whole content area for new rows
    var contentMain = document.querySelector('#content-main');
    if (contentMain) {
        observer.observe(contentMain, { childList: true, subtree: true });
    }

});