import calendar
from datetime import datetime, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum, Q, F
from django.db.models.functions import Coalesce
from django.views import generic

from categories.admin import admin_site
from company_details.models import CompanyDetails
from insertion_order.models import IODetails, Campaigns, SubCampaign, InsertionOrders
from insertion_order.templatetags.reports import month_year_iter


class UnderPacingLineItem(LoginRequiredMixin, generic.TemplateView): # The line items which are under pacing by more than 10% compared to their daily target (calculated based on remaining volume and remaining days in the campaign). This is calculated based on the previous day's report data. This view is accessible to both managers and clients, but clients can only see line items for their own campaigns.
    """
    use this template render the Under pacing Line Items
    """
    login_url = '/'
    template_name = "reports/under_pacing_report.html"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.my_list = []

    def get_context_data(self, **kwargs):
        context = super(UnderPacingLineItem, self).get_context_data(**kwargs)
        context['title'] = 'Bulk Report Upload'
        self.request.current_app = 'Publisher_admin'
        context = admin_site.each_context(self.request)
        filter_dict = {}

        context['pacing'] = "Under"

        context['company_details'] = CompanyDetails.objects.filter(is_active=True)

        if self.request.GET.get('company_name'):
            context['selected_company'] = int(self.request.GET.get('company_name'))

            context['campaigns'] = Campaigns.objects.filter(company=context['selected_company'], is_active=True)

            filter_dict['io__sub_campaign__campaign__company'] = context['selected_company']

        if self.request.GET.get('campaign'):
            context['selected_campaign'] = int(self.request.GET.get('campaign'))
            context['sub_campaigns'] = SubCampaign.objects.filter(campaign=int(self.request.GET.get('campaign')),
                                                                  is_active=True)
            filter_dict['io__sub_campaign__campaign'] = context['selected_campaign']

        if self.request.GET.get('sub_campaign'):
            context['selected_sub_campaign'] = int(self.request.GET.get('sub_campaign'))
            filter_dict['io__sub_campaign'] = context['selected_sub_campaign']

        for line_item in IODetails.objects.filter(end_date__gte=datetime.today().date(), **filter_dict).order_by(
                "end_date"):
            remaining_days = (line_item.end_date - datetime.today().date()).days
            remaining_days = remaining_days if remaining_days > 0 else 0
            remaining_impressions = line_item.volume - line_item.total_impression()
            try:

                # How many impressions needed per day to finish on time
                daily_target = round(remaining_impressions / remaining_days)
            except ZeroDivisionError:
                daily_target = 0
            try:

                # Yesterday's actual delivery
                report = line_item.reports.get(report_on=datetime.today() - timedelta(days=1))

                # % difference from target
                pct = round((daily_target - report.impression) * 100 / report.impression)

                # Only show if under-pacing by more than 10%
                if pct > 0 and pct > 10:
                    self.my_list.append({"object": line_item, "value": pct, "daily_target": daily_target,
                                         "last_date": report.impression,
                                         "differance": daily_target - report.impression})
            except:
                pass
        context['my_list'] = self.my_list

        return context


class OverPacingLineItem(LoginRequiredMixin, generic.TemplateView):
    """
    use this template render the Under pacing Line Items
    """
    login_url = '/'
    template_name = "reports/under_pacing_report.html"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.my_list = []

    def get_context_data(self, **kwargs):
        context = super(OverPacingLineItem, self).get_context_data(**kwargs)
        context['title'] = 'Line Item Performance'
        self.request.current_app = 'Publisher_admin'
        context = admin_site.each_context(self.request)
        filter_dict = {}

        context['pacing'] = "Over"

        context['campaigns'] = Campaigns.objects.filter(is_active=True)

        if self.request.GET.get('campaign'):
            context['selected_campaign'] = int(self.request.GET.get('campaign'))
            context['sub_campaigns'] = SubCampaign.objects.filter(campaign=int(self.request.GET.get('campaign')),
                                                                  is_active=True)
            filter_dict['io__sub_campaign__campaign'] = context['selected_campaign']
        if self.request.GET.get('campaign'):
            context['selected_campaign'] = int(self.request.GET.get('campaign'))
            context['sub_campaigns'] = SubCampaign.objects.filter(campaign=int(self.request.GET.get('campaign')),
                                                                  is_active=True)
            filter_dict['io__sub_campaign__campaign'] = context['selected_campaign']

        if self.request.GET.get('sub_campaign'):
            context['selected_sub_campaign'] = int(self.request.GET.get('sub_campaign'))
            filter_dict['io__sub_campaign'] = context['selected_sub_campaign']

        for line_item in IODetails.objects.filter(end_date__gte=datetime.today().date(), **filter_dict).order_by(
                "end_date"):
            remaining_days = (line_item.end_date - datetime.today().date()).days
            remaining_days = remaining_days if remaining_days > 0 else 0
            remaining_impressions = line_item.volume - line_item.total_impression()
            try:
                daily_target = round(remaining_impressions / remaining_days)
            except ZeroDivisionError:
                daily_target = 0
            try:
                report = line_item.reports.get(report_on=datetime.today() - timedelta(days=1))
                pct = round((daily_target - report.impression) * 100 / report.impression)
                if pct < 0 and pct < -10:
                    self.my_list.append({"object": line_item, "value": pct, "daily_target": daily_target,
                                         "last_date": report.impression,
                                         "differance": daily_target - report.impression})
            except Exception as e:
                pass
        context['my_list'] = self.my_list
        return context


class ReportNotLineItem(LoginRequiredMixin, generic.ListView):
    """
    use this template render the Under pacing Line Items
    """
    login_url = '/'
    template_name = "reports/report_not_available.html"
    paginate_by = 20

    def get_queryset(self):
        return IODetails.objects.filter(end_date__gte=datetime.today().date()).exclude(
            reports__report_on=datetime.today() - timedelta(days=1)).order_by("-end_date")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.my_list = []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.request.current_app = 'Publisher_admin'
        context.update(admin_site.each_context(self.request))
        context.update({"date": datetime.today() - timedelta(days=1)})
        return context


class InvoiceSummaryReportView(LoginRequiredMixin, generic.ListView):
    """
    use this template render the Under pacing Line Items
    """
    login_url = '/'
    template_name = "reports/invoice_summary.html"

    def get_queryset(self):
        today = datetime.today()

        if self.request.GET.get('company') and self.request.GET.get('date'):
            today = datetime.strptime(self.request.GET.get('date'), '%Y-%m-%d')
            self.company = CompanyDetails.objects.get(name=self.request.GET.get('company'))
        else:
            self.company = None
        month_start = today.replace(day=1)
        month_end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
        qs = InsertionOrders.objects.filter(start_date__lte=month_end, end_date__gte=month_start).order_by("-created_on")

        if self.company:
            qs = qs.filter(sub_campaign__campaign__company=self.company)
        return qs

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.my_list = []
        self.company = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.request.current_app = 'Publisher_admin'
        context.update(admin_site.each_context(self.request))
        context.update({'company': CompanyDetails.objects.filter(is_active=True)})
        context.update({'title': 'Line Item Performance'})

        if self.request.GET.get('company') and self.request.GET.get('date'):
            invoice_on = datetime.strptime(self.request.GET.get('date'), '%Y-%m-%d')
            context.update({"invoice_on": invoice_on})
            start_date = self.get_queryset().dates('start_date', 'month').first()
            if start_date:
                reporting_dates = [x for x in
                                   month_year_iter(start_date.month, start_date.year, invoice_on.month,
                                                   invoice_on.year)]
                context.update({"reporting_dates": reporting_dates})
            context.update({"currency": self.company})

        return context


class SpendSummaryView(LoginRequiredMixin, generic.ListView):
    """
    use this endpoint render the spend summary result
    """
    login_url = '/'
    template_name = "analytics/spend_summary.html"

    def get_queryset(self):
        if self.request.GET.get('company'):
            return CompanyDetails.objects.filter(is_active=True, id=self.request.GET.get('company'))
        return CompanyDetails.objects.filter(is_active=True).order_by("-created_on").annotate(
            impression=Sum('campaigns__sub_campaign__insertion_order__io_details__reports__impression')).order_by(
            "-impression")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({'title': 'Spend Summary'})
        self.request.current_app = 'Publisher_admin'
        context.update(admin_site.each_context(self.request))
        context.update({'companies': CompanyDetails.objects.filter(is_active=True)})

        if self.request.GET.get('end_date') and self.request.GET.get('start_date'):
            context.update({"end_date": datetime.strptime(self.request.GET.get('end_date'), '%Y-%m-%d')})
            context.update({"start_date": datetime.strptime(self.request.GET.get('start_date'), '%Y-%m-%d')})
        else:
            context.update({"end_date": datetime.today() - timedelta(days=1)})
            context.update({"start_date": datetime.today() - timedelta(days=1)})

        return context


class CompanyForecastingSummaryView(LoginRequiredMixin, generic.ListView):
    """
    use this endpoint render the spend summary result
    """
    login_url = '/'
    template_name = "analytics/company-forecasting.html"

    def get_queryset(self):
        if self.request.GET.get('company'):
            return CompanyDetails.objects.filter(is_active=True, id=self.request.GET.get('company'))
        return CompanyDetails.objects.filter(is_active=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.request.current_app = 'Publisher_admin'
        context.update(admin_site.each_context(self.request))
        context.update({'title': 'Company wise Forecasting'})
        end_date = CompanyDetails.objects.filter(is_active=True).dates('campaigns__end_date', 'month').last()
        if end_date:
            context.update({"reporting_dates": [x for x in
                                                month_year_iter(datetime.today().month, datetime.today().year,
                                                                end_date.month, end_date.year)]})

        return context


class CampaignForecastingSummaryView(LoginRequiredMixin, generic.ListView):
    """
    use this endpoint render the spend summary result
    """
    login_url = '/'
    template_name = "analytics/campaign-forecasting.html"

    def get_queryset(self):
        if self.request.GET.get('company'):
            return Campaigns.objects.filter(is_active=True, status="Live",
                                            company=self.request.GET.get('company')).order_by(
                "-created_on")
        return Campaigns.objects.filter(id__in=[])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.request.current_app = 'Publisher_admin'
        context.update(admin_site.each_context(self.request))
        context.update({'title': 'Campaign wise Forecasting'})
        context.update({'companies': CompanyDetails.objects.filter(is_active=True)})
        if self.request.GET.get('company'):
            end_date = Campaigns.objects.filter(is_active=True, status="Live",
                                                company=self.request.GET.get('company')).dates('end_date',
                                                                                               'month').last()
            if end_date:
                context.update({"reporting_dates": [x for x in
                                                    month_year_iter(datetime.today().month, datetime.today().year,
                                                                    end_date.month, end_date.year)]})

        return context


class InvoiceYetNotGeneratedView(LoginRequiredMixin, generic.ListView):
    login_url = '/'
    template_name = "reports/invoice_not_yet_generated.html"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.company = None
        self.my_list = []

    def get_queryset(self):
        today = datetime.today().date()
        campaigns = Campaigns.objects.filter(end_date__lte=today, invoiced_campaign__isnull=True).order_by(
            "-created_on")
        if self.request.GET.get('company'):
            self.company = CompanyDetails.objects.get(name=self.request.GET.get('company'))
            return campaigns.filter(company=self.company).order_by("-created_on")
        return campaigns

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.request.current_app = 'Publisher_admin'
        context.update(admin_site.each_context(self.request))
        context.update({'company': CompanyDetails.objects.filter(is_active=True)})
        context.update({'title': 'Invoice Not Yet Generated'})

        if self.request.GET.get('company'):
            context.update({"currency": self.company})

        context.update({"is_juniors_logins": self.request.user.groups.filter(name="Juniors_logins").exists()})

        return context


class InvoiceUnderDeliveredView(LoginRequiredMixin, generic.ListView):
    login_url = '/'
    template_name = "reports/invoice-under-delivered.html"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.company = None
        self.my_list = []

    def get_queryset(self):
        today = datetime.today().date()
        io_details = IODetails.objects.annotate(impression=Sum('reports__impression'), ).filter(
            impression__lt=(F('volume') - 1000), end_date__lte=today)
        if self.request.GET.get('company'):
            self.company = CompanyDetails.objects.get(name=self.request.GET.get('company'))
            return io_details.filter(io__sub_campaign__campaign__company=self.company)

        return io_details

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.request.current_app = 'Publisher_admin'
        context.update(admin_site.each_context(self.request))
        context.update({'company': CompanyDetails.objects.filter(is_active=True)})
        context.update({'title': 'Invoice Under Delivered'})

        if self.request.GET.get('company'):
            context.update({"currency": self.company})

        context.update({"is_juniors_logins": self.request.user.groups.filter(name="Juniors_logins").exists()})

        return context


class InvoiceOverDeliveredView(LoginRequiredMixin, generic.ListView):
    login_url = '/'
    template_name = "reports/invoice-over-delivered.html"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.company = None
        self.my_list = []


    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.company = None
        self.my_list = []

    def get_queryset(self):
        today = datetime.today().date()
        io_details = IODetails.objects.annotate(impression=Sum('reports__impression'), ).filter(
            impression__gt=(F('volume') + 1000), end_date__lte=today)
        if self.request.GET.get('company'):
            self.company = CompanyDetails.objects.get(name=self.request.GET.get('company'))
            return io_details.filter(io__sub_campaign__campaign__company=self.company)

        return io_details

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.request.current_app = 'Publisher_admin'
        context.update(admin_site.each_context(self.request))
        context.update({'company': CompanyDetails.objects.filter(is_active=True)})
        context.update({'title': 'Invoice Under Delivered'})

        if self.request.GET.get('company'):
            context.update({"currency": self.company})

        context.update({"is_juniors_logins": self.request.user.groups.filter(name="Juniors_logins").exists()})

        return context