
function comfirmModel(type, id, balance) {
    var model = $('#myModal');
    var model_text = "";
    var confirm_action_url = "";
    switch (type) {
        case 1:
            model_text = `Really Do You want Rest Password a Employee`;
            model = $('#ProfileModal');
            confirm_action_url = `${id}/update_payment/`;
            break;


        default:
            model_text = "Really Do You complete this action";
            confirm_action_url = "/";
            break;
    }

    model.modal('show');
    $('#move_order_id').attr("action", confirm_action_url);
    $('#model-text').text(model_text)
    $('#amount').attr("max", balance)
}

function downloadCampaigns(element) {
    console.log("Function called")
    element.disabled = true

    $.ajax({
        url: `/insertion_order/bulk-upload/download-report/`,
        method: 'GET',
        success: function (response) {
            var encodedUri = 'data:application/csv;charset=utf-8,' + encodeURIComponent(response);
            var link = document.createElement("a");
            link.setAttribute("href", encodedUri);
            link.setAttribute("id", "download")
            link.setAttribute("download", "Report.csv");
            link.innerHTML = "Download Report";
            document.body.appendChild(link);
            link.click();
            element.disabled = false
            link.remove();
        },
        error: function (response) {
            console.log(response)
            element.disabled = false
        }
    });
}

function handleRadioClick(myRadio) {
    $(`input[value='${myRadio.value}'].line-item-radio`).prop('checked', true)
}

function statusChangeClick(myRadio){
    const selected_value = myRadio.value
    const current_value = myRadio.getAttribute("data-status")
    const line_item_id = myRadio.getAttribute("name")

    if(selected_value != current_value){
        $('#exampleModalLongTitle').text("Reason for " + selected_value + " Line Item")
        $('#exampleModal').modal('show');
        $('#modelSubmit').attr("onclick", `onSubmitModel('${myRadio.id}', '${selected_value}', '${line_item_id}')`)
    }
}

function onSubmitModel(element_id, selected_value, line_item_id){
    const reason_value = $('#modelReason').val()
    $(`#${element_id}`).parent().parent().parent().next("td").text(reason_value + " "+selected_value )
      $.ajax({
        url: `/insertion_order/line-item/${line_item_id}/`,
        method: 'POST',
        headers: {
            'Content-Type':'application/json',
        },
        data:JSON.stringify({
            "status": selected_value,
            "reason": reason_value
        }),
        success: function (response) {
             location.reload();
        },
        error: function (response) {
            console.log(response)
        }
        });

    $('#exampleModal').modal('hide');
}