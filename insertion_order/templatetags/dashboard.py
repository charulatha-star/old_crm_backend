import calendar
from datetime import datetime, timedelta, date

from django import template
from django.db import models
from django.db.models import F, Sum, ExpressionWrapper
from django.db.models.functions import TruncDay, Coalesce

from categories.models import Country
from invoices.models import Invoices
from invoices.utils import metrics_amount_calculation
from ..models import SubCampaign, LineItemsReports, IODetails
from ..utils import RealTimeCurrencyConverter

register = template.Library()

calendar.monthrange(2008, 2)


def line_item_budget_calculator(line_item):
    data = {}
    # return value declare
    budget_next_month = 0

    month = datetime.today()

    this_month_end_date = date(month.year, month.month, calendar.monthrange(month.year, month.month)[-1])
    this_month_start_date = month.date().replace(day=1)

    prev_month = this_month_start_date - timedelta(days=1)

    next_month = this_month_end_date + timedelta(days=1)
    next_month_end_date = date(next_month.year, next_month.month,
                               calendar.monthrange(next_month.year, next_month.month)[-1])
    next_month_start_date = next_month.replace(day=1)

    # last_month_budget calculation
    last_month_impressions = line_item.reports.filter(report_on__month=prev_month.month, report_on__year=month.year
                                                      ).aggregate(impression=Sum('impression'))['impression']
    budget_last_month = metrics_amount_calculation(line_item, last_month_impressions)

    # yesterday_budget calculation
    last_yesterday_impressions = line_item.reports.filter(report_on=datetime.today() - timedelta(days=1),
                                                          ).aggregate(impression=Sum('impression'))['impression']
    budget_yesterday = metrics_amount_calculation(line_item, last_yesterday_impressions)

    # This Month Budget Calculation
    if line_item.start_date >= this_month_start_date:
        campaign_start_date = line_item.start_date
    else:
        campaign_start_date = this_month_start_date

    today_remaining_days = (line_item.end_date - campaign_start_date).days + 1

    if line_item.end_date >= this_month_end_date:
        campaign_end_date = this_month_end_date
    else:
        campaign_end_date = line_item.end_date

    if line_item.start_date <= month.date():
        this_month_campaign_days = (campaign_end_date - campaign_start_date).days + 1
    else:
        this_month_campaign_days = 0

    archived_impressions = line_item.reports.exclude(report_on__month=month.month, report_on__year=month.year
                                                     ).aggregate(impression=Sum('impression'))['impression']

    archived_impressions = archived_impressions if archived_impressions else 0
    remaining_impressions = line_item.volume - archived_impressions
    if remaining_impressions < 0:
        remaining_impressions = 0

    try:
        daily_target = remaining_impressions / today_remaining_days
    except:
        daily_target = 0

    budget_this_month = metrics_amount_calculation(line_item, daily_target * this_month_campaign_days)

    # Next Month Budget Calculation
    if line_item.end_date > this_month_end_date:
        if line_item.end_date >= next_month_end_date:
            campaign_end_date = next_month_end_date
        else:
            campaign_end_date = line_item.end_date

        next_month_campaign_days = (campaign_end_date - next_month_start_date).days + 1
        budget_next_month = metrics_amount_calculation(line_item, daily_target * next_month_campaign_days)
   
    data['budget_this_month'] = round(budget_this_month, 2)
    data['budget_next_month'] = round(budget_next_month, 2)
    data['budget_last_month'] = round(budget_last_month, 2)
    data['this_month_booked'] = round(daily_target * this_month_campaign_days)
    data['budget_yesterday'] = round(budget_yesterday, 2)

    return data


@register.simple_tag()
def admin_dashboard(request):
    data = dict()
    today = datetime.today()
    this_month_end_date = date(today.year, today.month, calendar.monthrange(today.year, today.month)[-1])

    campaign = SubCampaign.objects.filter()
    line_items = IODetails.objects.filter()

    converter = RealTimeCurrencyConverter()

    this_month_booked = 0

    data['campaign'] = {
        "live": campaign.filter(status="Live").count(),
        "scheduled": campaign.filter(status="Scheduled").count(),
        "completed": campaign.filter(status="Completed").count(),
        "stopped": campaign.filter(status__in=["Stopped", "Paused"]).count()
    }

    data["closing_campaign"] = IODetails.objects.filter(end_date__month=today.month).order_by("end_date")[:10]
    data["top_performing_campaign"] = IODetails.objects.filter(end_date__month__gte=today.month - 1, status="Live",
                                                               end_date__year=today.year).annotate(
        ctr=ExpressionWrapper((Sum('reports__clicks') / Sum('reports__impression')) * 100,
                              output_field=models.FloatField())).order_by("-ctr")[:10]

    data['country'] = Country.objects.filter(is_active=True)
    data['selected_country'] = Country.objects.get(id=request.GET.get("country", 1))
    invoice = Invoices.objects.filter(due_date__month=datetime.today().month, status="Not Paid")

    data["budget"] = []
    data["total_budget"] = {
        'total_budget_this_month': 0,
        'total_budget_last_month': 0,
        'total_budget_next_month': 0,
        'total_budget_yesterday': 0,
    }

    for country in data['country']:
        budget_dict = {"title": country.title,
                       "iso_code_3": country.iso_code_3,
                       "currency_symbols": country.currency_symbols,
                       'total_budget_this_month': 0,
                       'total_budget_last_month': 0,
                       'total_budget_next_month': 0,
                       'total_budget_yesterday': 0,
                       }

        for line_item in IODetails.objects.filter(io__sub_campaign__campaign__company__billing_currency=country,
                                                  end_date__month__gte=today.month - 1, end_date__year=today.year):
            result = line_item_budget_calculator(line_item)
            budget_dict['total_budget_next_month'] += result['budget_next_month']
            budget_dict['total_budget_last_month'] += result['budget_last_month']
            budget_dict['total_budget_this_month'] += result['budget_this_month']
            budget_dict['total_budget_yesterday'] += result['budget_yesterday']
            this_month_booked += result['this_month_booked']

        data["budget"].append(budget_dict)
        data["total_budget"]['total_budget_this_month'] += converter.convert(country.iso_code_3, "INR",
                                                                             budget_dict['total_budget_this_month'])
        data["total_budget"]['total_budget_last_month'] += converter.convert(country.iso_code_3, "INR",
                                                                             budget_dict['total_budget_last_month'])
        data["total_budget"]['total_budget_next_month'] += converter.convert(country.iso_code_3, "INR",
                                                                             budget_dict['total_budget_next_month'])
        data["total_budget"]['total_budget_yesterday'] += converter.convert(country.iso_code_3, "INR",
                                                                            budget_dict['total_budget_yesterday'])

    data["invoice"] = []

    data["total_invoice"] = {
        'total_not_paid': 0,
        'total_last_month': 0,
        'total_this_year': 0,
    }

    for country in data['country']:
        invoice_dict = {
            "title": country.title, "iso_code_3": country.iso_code_3, "currency_symbols": country.currency_symbols,
            "not_paid": invoice.filter(company__billing_currency=country).annotate(
                not_paid_amount=ExpressionWrapper(F('billing_amount') - Coalesce(Sum('payment_history__amount'), 0),
                                                  output_field=models.FloatField())).aggregate(
                not_paid=Sum('not_paid_amount'))['not_paid'],
            "last_month":
                invoice.filter(company__billing_currency=country).filter(invoice_on__month=today.month - 1).aggregate(
                    amount=Sum('billing_amount'))['amount'],
            "this_year":
                invoice.filter(company__billing_currency=country).filter(invoice_on__year=today.year).aggregate(
                    amount=Sum('billing_amount'))['amount'],
        }
        data["invoice"].append(invoice_dict)

        data["total_invoice"]['total_not_paid'] += converter.convert(country.iso_code_3, "INR",
                                                                     invoice_dict['not_paid'])
        data["total_invoice"]['total_last_month'] += converter.convert(country.iso_code_3, "INR",
                                                                       invoice_dict['last_month'])
        data["total_invoice"]['total_this_year'] += converter.convert(country.iso_code_3, "INR",
                                                                      invoice_dict['this_year'])

    data['last_30_days'] = LineItemsReports.objects.filter(
        line_item__io__sub_campaign__campaign__company__billing_currency=data['selected_country'],
        report_on__gte=datetime.now() - timedelta(days=30)
    ).annotate(
        day=TruncDay('report_on')
    ).values('day').annotate(
        budget=Sum(
            ExpressionWrapper(
                (F('impression') * F("line_item__unit_cost")) / 1000,
                output_field=models.FloatField())))

    data['volumes'] = {
        "yesterday": line_items.filter(reports__report_on=today - timedelta(days=1)).aggregate(
            impression=Sum('reports__impression'))['impression'],
        "this_month":
            line_items.filter(reports__report_on__month=today.month).aggregate(impression=Sum('reports__impression'))[
                'impression'],
        "this_month_booked": this_month_booked,
        "clicks": line_items.filter(reports__report_on__month=today.month).aggregate(clicks=Sum('reports__clicks'))[
            'clicks']
    }

    prev_month = today.replace(day=1) - timedelta(days=1)
    data['spend'] = {
        "yesterday":
            line_items.filter(reports__report_on=today - timedelta(days=1)).aggregate(budget=Sum('reports__budget'))[
                'budget'],
        "this_month": line_items.filter(reports__report_on__month=today.month).aggregate(budget=Sum('reports__budget'))[
            'budget'],
        "last_month":
            line_items.filter(reports__report_on__month=prev_month.month).aggregate(budget=Sum('reports__budget'))[
                'budget'],
        "this_year": line_items.filter(reports__report_on__year=today.year).aggregate(clicks=Sum('reports__clicks'))[
            'clicks']
    }

    data['date'] = {
        "yesterday": today - timedelta(days=1),
        "this_month": today,
        "next_month": this_month_end_date + timedelta(days=1),
        "last_month": today.replace(day=1) - timedelta(days=1)
    }

    return data


@register.simple_tag()
def client_dashboard(user):
    data = dict()
    today = datetime.today()

    if hasattr(user, "company_contact_user"):
        company = user.company_contact_user.company
    else:
        company = user.company

    line_items = IODetails.objects.filter(io__sub_campaign__campaign__company=company)
    campaign = SubCampaign.objects.filter(campaign__company=company)
    data['currency_symbols'] = company.billing_currency.iso_code_3

    this_month_booked = 0

    data['line_item'] = {
        "live": line_items.filter(status="Live").count(),
        "paused": line_items.filter(status="Paused").count(),
        "completed": line_items.filter(status="Completed").count(),
        "stopped": line_items.filter(status="Stopped").count()
    }

    data['campaign'] = {
        "live": campaign.filter(status="Live").count(),
        "scheduled": campaign.filter(status="Scheduled").count(),
        "completed": campaign.filter(status="Completed").count(),
        "stopped": campaign.filter(status__in=["Stopped", "Paused"]).count()
    }

    data["closing_campaign"] = IODetails.objects.filter(end_date__gte=today,
                                                        io__sub_campaign__campaign__company__user=user).order_by(
        "end_date")[:10]
    data["closed_campaign"] = IODetails.objects.filter(end_date__lt=today,
                                                       io__sub_campaign__campaign__company__user=user).annotate(
        ctr=ExpressionWrapper((Sum('reports__clicks') / Sum('reports__impression')) * 100,
                              output_field=models.FloatField())).order_by("-end_date")[:10]
    data["top_performing_campaign"] = IODetails.objects.filter(io__sub_campaign__campaign__company__user=user,
                                                               end_date__month__gte=today.month - 1,
                                                               end_date__year=today.year).annotate(
        ctr=ExpressionWrapper((Sum('reports__clicks') / Sum('reports__impression')) * 100,
                              output_field=models.FloatField())).order_by("-ctr")[:10]
    invoice = Invoices.objects.filter(company__user=user)

    total_budget_this_month = 0
    total_budget_last_month = 0
    total_budget_next_month = 0
    total_budget_yesterday = 0
    two_month_back = today - timedelta(days=61)
    for line_item in IODetails.objects.filter(io__sub_campaign__campaign__company__user=user,
                                              start_date__month__gte=two_month_back.month,
                                              start_date__year__gte=two_month_back.year):
        result = line_item_budget_calculator(line_item)
        print(line_item, result['budget_this_month'])
        total_budget_next_month += result['budget_next_month']
        total_budget_last_month += result['budget_last_month']
        total_budget_this_month += result['budget_this_month']
        total_budget_yesterday += result['budget_yesterday']
        this_month_booked += result['this_month_booked']

    this_month_end_date = date(today.year, today.month, calendar.monthrange(today.year, today.month)[-1])
    data['date'] = {
        "yesterday": today - timedelta(days=1),
        "this_month": today,
        "next_month": this_month_end_date + timedelta(days=1),
        "last_month": today.replace(day=1) - timedelta(days=1)
    }
    data['volumes'] = {
        "yesterday": line_items.filter(reports__report_on=today - timedelta(days=1)).aggregate(
            impression=Sum('reports__impression'))['impression'],
        "this_month":
            line_items.filter(reports__report_on__month=today.month).aggregate(impression=Sum('reports__impression'))[
                'impression'],
        "this_month_booked": this_month_booked,
        "clicks": line_items.filter(reports__report_on=today).aggregate(clicks=Sum('reports__clicks'))['clicks']
    }

    data["invoice"] = {
        "not_paid":
            invoice.annotate(
                not_paid_amount=ExpressionWrapper(F('billing_amount') - Coalesce(Sum('payment_history__amount'), 0),
                                                  output_field=models.FloatField())).aggregate(
                not_paid=Sum('not_paid_amount'))['not_paid']
        ,
        "last_month": invoice.filter(invoice_on__month=today.month - 1).aggregate(amount=Sum('billing_amount'))[
            'amount'],
        "this_year": invoice.filter(invoice_on__year=today.year).aggregate(amount=Sum('billing_amount'))['amount'],
    }

    data["budget"] = {
        "yesterday": total_budget_yesterday,
        "this_month": round(total_budget_this_month, 2),
        "last_month": round(total_budget_last_month, 2),
        "next_month": round(total_budget_next_month, 2),
    }
    data['last_30_days'] = LineItemsReports.objects.filter(line_item__io__sub_campaign__campaign__company__user=user,
                                                           report_on__gte=datetime.now() - timedelta(days=31)
                                                           ).annotate(
        day=TruncDay('report_on')
    ).values('day').annotate(
        budget=Sum(
            ExpressionWrapper(
                (F('impression') * F("line_item__unit_cost")) / 1000,
                output_field=models.FloatField()), ))
    return data


@register.filter
def days_until(date):
    delta = date - datetime.now().date()
    if delta.days == 0:
        return "Completed Today"
    elif delta.days <= -1:
        return "Completed"
    elif delta.days == 1:
        return "{} Day Left".format(delta.days)
    else:
        return "{} Days Left".format(delta.days)
