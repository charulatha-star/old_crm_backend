from django.shortcuts import render

# Create your views here.
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import EmailMultiAlternatives
from django.core.mail import get_connection


def get_email_connection(my_username="support@wowtamilnadu.com", my_password="qlow jdan kgnb upqv"):
    smtp_host = 'smtp.gmail.com'
    smtp_port = 587
    smtp_use_tls = True
    return get_connection(host=smtp_host, port=smtp_port, username=my_username, password=my_password,
                          use_tls=smtp_use_tls)


@csrf_exempt  # optional — only needed if you're calling this from external clients
def send_email_view(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON payload"}, status=400)

    subject = data.get("subject", "No Subject")
    html_body = data.get("html_body", "<p>No Content</p>")
    from_email = data.get("from_email", "support@wowtamilnadu.com")
    to_email = data.get("to_email", [])
    cc_email = data.get("cc", [])
    bcc_email = data.get("bcc", [])

    try:
        connection = get_email_connection()
        email_message = EmailMultiAlternatives(
            subject,
            "",  # plain text body (optional)
            from_email,
            to_email,
            bcc=bcc_email,
            cc=cc_email,
            connection=connection,
        )
        email_message.attach_alternative(html_body, "text/html")
        sent_count = email_message.send()

        return JsonResponse({"success": True, "sent": sent_count})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)
