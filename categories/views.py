
from django.shortcuts import render

# Create your views here.
import json
import calendar
from datetime import date
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.core.mail import EmailMultiAlternatives
from django.core.mail import get_connection

from categories.models import AedExchangeRateMonth, AedExchangeRate


def get_email_connection(my_username="support@wowtamilnadu.com", my_password="qlow jdan kgnb upqv"):
    smtp_host = 'smtp.gmail.com'
    smtp_port = 587
    smtp_use_tls = True
    return get_connection(host=smtp_host, port=smtp_port, username=my_username, password=my_password,
                          use_tls=smtp_use_tls)


@csrf_exempt
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
            "",
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


# ---------- AED Exchange Rate views ----------

def get_month_end_date(year, month):
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, last_day)


def aed_exchange_rates(request):
    months = AedExchangeRateMonth.objects.prefetch_related("rates").order_by("year", "month")
    currency_choices = AedExchangeRate.CURRENCY_CHOICES
    return render(request, "categories/aed_exchange_rates.html", {
        "months": months,
        "currency_choices": currency_choices,
    })


@require_POST
def add_aed_exchange_rate(request):
    month = int(request.POST.get("month"))
    year = int(request.POST.get("year"))
    currency = request.POST.get("currency")
    exchange_rate = request.POST.get("exchange_rate")

    month_obj, _ = AedExchangeRateMonth.objects.get_or_create(month=month, year=year)
    effective_date = get_month_end_date(year, month)

    if AedExchangeRate.objects.filter(month=month_obj, currency=currency).exists():
        return JsonResponse(
            {"success": False, "error": "{} rate already added for this month".format(currency)},
            status=400
        )

    rate_obj = AedExchangeRate.objects.create(
        month=month_obj,
        currency=currency,
        exchange_rate=exchange_rate,
        effective_date=effective_date,
    )

    return JsonResponse({
        "success": True,
        "id": rate_obj.id,
        "currency": rate_obj.currency,
        "exchange_rate": str(rate_obj.exchange_rate),
        "effective_date": str(rate_obj.effective_date),
    })












