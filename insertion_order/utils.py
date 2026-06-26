# utils.py is helper function 

from datetime import datetime

import pdfkit
import requests
from PyPDF2 import PdfFileMerger
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.shortcuts import redirect

from billiontags_crm.settings import MEDIA_ROOT
from insertion_order import models

import pdfkit

WKHTMLTOPDF_PATH = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"


def render_to_pdf(request, order):
    domain = "http://" + get_current_site(request).name
    config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)
    pdfkit.from_url(
        domain + '/generate-io/{id}/'.format(id=order.pk),
        MEDIA_ROOT + '/insertion-orders/{id}.pdf'.format(id=order.order_id),
        configuration=config
    )
    order.io_file = '/insertion-orders/{id}.pdf'.format(id=order.order_id)
    order.save()
    return redirect("../../")

# int_to_io, int_to_campaigns, int_to_sub_campaigns, int_to_io_details, int_to_performance_category, int_to_company — all do the same thing for different models. Clean, reusable pattern.

# def render_to_pdf(request, order):  # PDF generation 
#     domain = "http://" + get_current_site(request).name
#     pdfkit.from_url(domain + '/generate-io/{id}/'.format(id=order.pk),
#                     MEDIA_ROOT + '/insertion-orders/{id}.pdf'.format(id=order.order_id))

#     order.io_file = '/insertion-orders/{id}.pdf'.format(id=order.order_id)
#     order.save()
#     return redirect("../../")


def int_to_io(pk):
    try:
        return models.InsertionOrders.objects.get(pk=pk)
    except ObjectDoesNotExist:
        raise ValidationError("Invalid ID")


def int_to_campaigns(pk):
    try:
        return models.Campaigns.objects.get(pk=pk)
    except ObjectDoesNotExist:
        raise ValidationError("Invalid ID")


def int_to_sub_campaigns(pk):
    try:
        return models.SubCampaign.objects.get(pk=pk)
    except ObjectDoesNotExist:
        raise ValidationError("Invalid ID")


def int_to_io_details(pk):
    try:
        return models.IODetails.objects.get(pk=pk)
    except ObjectDoesNotExist:
        raise ValidationError("Invalid ID")


def int_to_performance_category(pk):
    try:
        return models.PerformanceCategory.objects.get(pk=pk)
    except ObjectDoesNotExist:
        raise ValidationError("Invalid ID")


def int_to_report_ids(pk):
    try:
        return models.LineItemReportingID.objects.get(report_id=pk.strip())
    except ObjectDoesNotExist:
        return pk.strip()


def int_to_company(pk):
    try:
        return models.CompanyDetails.objects.get(pk=pk)
    except ObjectDoesNotExist:
        raise ValidationError("Invalid ID")


# Duplicated from InsertionOrders.save() in models.py — should ideally be in one place only.
def generate_order_id(obj):
    order_format = "BT{}{}".format("D" if obj.company.is_domestic else "I", datetime.now().strftime("%y"))
    order_count = models.InsertionOrders.objects.filter(order_id__icontains=order_format).count()
    return "{}{:06d}".format(order_format, order_count + 1 if order_count else 1)


def get_or_none(classmodel, **kwargs):
    try:
        return classmodel.objects.get(**kwargs)
    except classmodel.DoesNotExist:
        return None


# Fetches live exchange rates from an external API. Used for converting campaign costs between INR and other currencies (since it's an international ad network).  This API call happens on every instantiation — should be cached.

class RealTimeCurrencyConverter(object):
    def __init__(self):
        self.data = requests.get("https://api.exchangerate-api.com/v4/latest/INR").json()
        self.currencies = self.data['rates']

    def convert(self, from_currency, to_currency, amount):
        amount = amount if amount else 0
        # first convert it into USD if it is not in USD.
        # because our base currency is USD
        if from_currency != 'INR':
            amount = amount / self.currencies[from_currency]

            # limiting the precision to 3 decimal places
        amount = round(amount * self.currencies[to_currency], 3)
        return amount


def perform_operation(queryset, new_set):
    old_set = set(queryset)
    new_set = set(new_set)

    old_set = old_set.difference(new_set)
    new_set = new_set.difference(queryset)

    return old_set, new_set



# New defined function 


# def get_active_days(line_item, from_date=None, to_date=None):
#     """
#     Line item actual running days calculate
#     Paused periods-

#     Args:
#         line_item: IODetails instance
#         from_date: calculate start (default: line_item.start_date)
#         to_date:   calculate end   (default: today or line_item.end_date)

#     Returns:
#         dict: {
#             'total_days': 11,
#             'paused_days': 3,
#             'active_days': 8,
#             'daily_target': 1250,
#         }
#     """
#     from datetime import date, timedelta

#     start = from_date or line_item.start_date
#     end   = to_date   or min(line_item.end_date, date.today())

#     total_days = (end - start).days + 1
#     if total_days <= 0:
#         return {
#             'total_days': 0,
#             'paused_days': 0,
#             'active_days': 0,
#             'daily_target': 0,
#         }

#     # Paused days calculate
#     paused_days = 0
#     for pause in line_item.pause_history.all():
#         # Pause period-ஐ line item range-க்கு clip பண்ணு
#         pause_start = max(pause.paused_from, start)
#         pause_end   = min(pause.paused_to,   end)

#         if pause_start <= pause_end:
#             paused_days += (pause_end - pause_start).days + 1

#     active_days = max(total_days - paused_days, 1)  # minimum 1 day

#     # Daily target
#     remaining_impressions = line_item.volume - line_item.total_impression()
#     remaining_impressions = max(remaining_impressions, 0)

#     try:
#         daily_target = round(remaining_impressions / active_days)
#     except ZeroDivisionError:
#         daily_target = 0

#     return {
#         'total_days'   : total_days,
#         'paused_days'  : paused_days,
#         'active_days'  : active_days,
#         'daily_target' : daily_target,
#         'remaining_impressions': remaining_impressions,
#     }