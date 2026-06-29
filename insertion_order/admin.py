import xlsxwriter
import csv
import io
import json
from datetime import datetime
from datetime import date
from .models import SubCampaign, InsertionOrders

from daterangefilter.filters import PastDateRangeFilter
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponse

from annoying.functions import get_object_or_None
from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.safestring import mark_safe
from django.utils.text import slugify
from django_admin_listfilter_dropdown.filters import ChoiceDropdownFilter, RelatedDropdownFilter

from categories.admin import admin_site
from insertion_order import models, utils
from insertion_order.templatetags.reports import line_item_report
from insertion_order.utils import int_to_io_details


class CsvImportForm(forms.Form):
    csv_file = forms.FileField()

    def clean(self):
        if not (self.cleaned_data['csv_file'] or self.cleaned_data['csv_file'].endswith(".csv")):
            raise forms.ValidationError('Please enter your code in text box or upload an appropriate file.')
        return self.cleaned_data


def url_to_edit_object(obj):
    return reverse('Publisher_admin:%s_%s_change' % (obj._meta.app_label, obj._meta.model_name), args=[obj.id])


@admin.register(models.LineItemsReports, site=admin_site)
class LineItemsReportsAdmin(admin.ModelAdmin):
    list_display = ("id", "report_on")
    change_list_template = 'LineItemReports.html'

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('update-report/<int:pk>/', self.update_report),

        ]
        return my_urls + urls

    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)
        self.request = None

    def changelist_view(self, request, extra_context=None, *args, **kwargs):
        extra_context = extra_context or {}

        if "date" in request.POST:
            self.request = request.POST
            filter_dict = dict()

            date = self.request.get('date', datetime.today().strftime("%Y-%m-%d"))
            filter_dict['end_date__gte'] = date

            if self.request.get('company_details'):
                extra_context['selected_company_details'] = int(self.request.get('company_details'))
                extra_context['campaigns'] = models.Campaigns.objects.filter(
                    company=self.request.get('company_details'))
                filter_dict['io__sub_campaign__campaign__company'] = extra_context['selected_company_details']

            if self.request.get('campaign'):
                extra_context['selected_campaign'] = int(self.request.get('campaign'))
                filter_dict['io__sub_campaign__campaign'] = extra_context['selected_campaign']

            extra_context['line_items'] = models.IODetails.objects.filter(**filter_dict).order_by("-id")
            extra_context['selected_date'] = date
            extra_context['company_details'] = models.CompanyDetails.objects.filter(is_active=True)

        return super().changelist_view(request, extra_context=extra_context, *args, **kwargs)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def update_report(self, request, pk):
    # POST endpoint inside admin
    # Creates or updates a daily report row
    # Returns JSON {"id": line_item.id}
    # Used by the "LineItemReports.html" template via AJAX

        if not request.user.is_authenticated:
            return redirect('/')
        line_item_obj = utils.int_to_io_details(pk)
        line_item = get_object_or_None(models.LineItemsReports, line_item=line_item_obj,
                                       report_on=request.POST['report_on'])
        if line_item:
            line_item.impression = request.POST['impression']
            line_item.clicks = request.POST['clicks']
            line_item.budget = request.POST['budget']
            line_item.save()
        else:
            line_item = models.LineItemsReports.objects.create(report_on=request.POST['report_on'],
                                                               line_item=line_item_obj,
                                                               impression=request.POST['impression'],
                                                               clicks=request.POST['clicks'],
                                                               budget=request.POST['budget'])
        return HttpResponse(json.dumps({"id": line_item.id}), content_type="application/json")


class LineItems(models.IODetails):
    class Meta:
        proxy = True
        verbose_name = "Line Items"
        verbose_name_plural = "4. Line Items"


@admin.register(LineItems, site=admin_site)
class LineItemsAdmin(admin.ModelAdmin):

     # ADD THIS
    class Media:
        js = ('admin/js/campaign_status.js',)
    
    list_display = ("campaign_id", "campaign_name", "io_order_id", "io_name", "item_id", "description", "ethinicity",
                    "start_date", "end_date", "ad_type", "ad_metrics", "unit_cost", "volume", "net_cost")
    date_hierarchy = "end_date"
    search_fields = ("campaign_id", "io_order_id", "item_id")
    readonly_fields = ("item_id", "io")
    list_filter = ("ad_type", "ad_metrics")
    ordering = ("-item_id",)
    change_form_template = "line_item_change_form_template.html"

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['object'] = int_to_io_details(object_id)
        return super(LineItemsAdmin, self).change_view(
            request, object_id, form_url, extra_context=extra_context,
        )
    

        # ADD THIS ENTIRE METHOD
    def get_queryset(self, request):
        qs = super(LineItemsAdmin, self).get_queryset(request)
        today = date.today()

        # Update Line Item status by its own dates
        qs.filter(
            start_date__lte=today,
            end_date__gte=today
        ).exclude(status__in=["Stopped", "Paused"]).update(status="Live")

        qs.filter(
            end_date__lt=today
        ).exclude(status__in=["Stopped", "Paused"]).update(status="Completed")

        qs.filter(
            start_date__gt=today
        ).exclude(status__in=["Stopped", "Paused"]).update(status="Scheduled")

        return qs




    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def io_name(self, obj):
        return obj.io.name

    def io_order_id(self, obj):
        return obj.io.io_id()

    def campaign_name(self, obj):
        return obj.io.campaign.name

    def campaign_id(self, obj):
        return obj.io.campaign.campaign_id

    campaign_id.short_description = "Campaign ID"
    campaign_name.short_description = "Campaign Name"
    io_order_id.short_description = "IO ID"
    io_name.short_description = "IO Name"


class LineItemsReportsAdminInline(admin.StackedInline):
    model = models.LineItemsReports
    fields = ("report_on", ("impression", "clicks"), ("viewable_impression", "measurable_impression"),
              ("video_start", "video_end"), ('budget', "media_cost"))
    extra = 0

    def has_delete_permission(self, request, obj=None):
        return True


@admin.register(models.IODetails, site=admin_site)
class IODetailsAdmin(admin.ModelAdmin):
    list_display = ("description", "ethinicity", "start_date", "end_date", 'ad_type', "ad_metrics")
    change_form_template = "report_upload_change_form.html"
    fieldsets = [
        ('Basic Info', {'fields': (("description", "ethinicity", "ad_type", "end_date"),
                                   ("ad_metrics", "unit_cost", "volume"),
                                   ("net_cost", "total_impression", "total_clicks"))}
         ),
    ]
    readonly_fields = ("description", "ethinicity", "start_date", "end_date", "ad_type", "ad_metrics", "unit_cost",
                       "volume", "net_cost", "total_impression", "total_clicks")
    inlines = [LineItemsReportsAdminInline]

    def has_delete_permission(self, request, obj=None):
        return False

    def has_module_permission(self, request):
        return False

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('upload-report/<int:pk>/', self.upload_report),
        ]
        return my_urls + urls

    def upload_report(self, request, pk):
        io_details = utils.int_to_io_details(pk)
        url = url_to_edit_object(io_details)
        if request.method == "POST":
            if request.FILES["csv_file"].name.endswith(".csv"):
                csv_file = request.FILES["csv_file"]
                decoded_file = csv_file.read().decode('utf-8').splitlines()
                reader = csv.DictReader(decoded_file)
                file_headers = reader.fieldnames
                for header in ["Date of Report(MM-DD-YYYY)", "Impression", "Clicks"]:
                    if header not in file_headers:
                        self.message_user(request, "{} Missing Header in Sheet".format(header), level=messages.ERROR)
                        return redirect(url)
                for row in reader:
                    data = dict()
                    data['line_item'] = io_details
                    try:
                        reported_on = datetime.strptime(row['Date of Report(MM-DD-YYYY)'], '%m-%d-%Y')
                    except Exception as error:
                        self.message_user(request, "{} Date Format wrong kindly Follow MM-DD-YYYY\n{}".format(
                            row['Date of Report(MM-DD-YYYY)'], error), level=messages.ERROR)
                        return redirect(url)
                    data['report_on'] = reported_on
                    data['impression'] = row['Impression']
                    data['clicks'] = row['Clicks']
                    report = get_object_or_None(models.LineItemsReports, line_item=io_details,
                                                report_on=reported_on)
                    if report:
                        data.pop("line_item")
                        data.pop("report_on")
                        report.__dict__.update(**data)
                    else:
                        report = models.LineItemsReports.objects.create(**data)
                    report.save()
            self.message_user(request, "Your csv file has been imported")
            return redirect(url)
        self.message_user(request, "No Files Selected", level=messages.ERROR)
        return redirect(url)

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        url = None
        if obj:
            url = reverse('Publisher_admin:%s_%s_changelist' % (obj._meta.app_label, obj._meta.model_name), )
            url += "upload-report/{}/".format(obj.id)
        context.update({
            'show_save': True,
            'show_save_and_continue': False,
            'show_save_and_add_another': False,
            'show_delete': False,
            "upload_url": url
        })
        return super().render_change_form(request, context, add, change, form_url, obj)


class LineItemForm(forms.ModelForm):
    reports = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        if 'instance' in kwargs:
            report_id = ", ".join([x.report_id for x in kwargs['instance'].report_ids.all()])
            initial = kwargs.get('initial', {})
            initial['reports'] = report_id
            kwargs['initial'] = initial

        super(LineItemForm, self).__init__(*args, **kwargs)

    def clean_reports(self):
        try:
            self.cleaned_data['reports'].split(",")
        except:
            raise ValidationError('Invalid Report ID')
        return self.cleaned_data['reports']

    def save(self, commit=True):
        instance = super(LineItemForm, self).save(commit=commit)
        if self.cleaned_data['reports'].split(","):
            old_report_id = instance.report_ids.all()
            new_report_id = [utils.int_to_report_ids(x) for x in self.cleaned_data['reports'].split(",") if
                             not isinstance(utils.int_to_report_ids(x), str)]
            new_not_report_id = [utils.int_to_report_ids(x) for x in self.cleaned_data['reports'].split(",") if
                                 isinstance(utils.int_to_report_ids(x), str)]

            old_set, new_set = utils.perform_operation(old_report_id, new_report_id)
            for remove_obj in old_set:
                remove_obj.delete()

            for add_obj in new_not_report_id:
                models.LineItemReportingID.objects.get_or_create(line_item=instance, report_id=add_obj.strip())

        return instance


# New Class
# class LineItemPauseHistoryInline(admin.StackedInline):
#     model = models.LineItemPauseHistory
#     fields = (("paused_from", "paused_to", "reason"),)
#     extra = 0
#     verbose_name = "Pause Period"
#     verbose_name_plural = "Pause Periods"

#     def has_delete_permission(self, request, obj=None):
#         return True


# @admin.register(models.IODetails, site=admin_site)
class IODetailsAdminInline(admin.StackedInline):
    # inlines = [LineItemsReportsAdminInline, LineItemPauseHistoryInline]  # New field
    model = models.IODetails
    fields = (("item_id", "reports"), "category", "description", "ethinicity", ("start_date", "end_date"),
              "ad_type", "ad_metrics", "unit_cost", "volume", "avg_ctr", "status",
              "net_cost", "total_impression", "total_clicks", "view_line_items")
    readonly_fields = ("net_cost", "view_line_items", "total_impression", "total_clicks", "item_id")
    extra = 1
    min_num = 1
    form = LineItemForm

    def view_line_items(self, obj):
        if obj.id:
            url = url_to_edit_object(obj)
            return mark_safe("<a class='custom-inline-link-field' "
                             "href='{}'>View Reports</a>".format(url))
        return "-"

    view_line_items.short_description = "Line Items"

    def has_delete_permission(self, request, obj=None):
        return False



class EmailCCContentAdminInline(admin.StackedInline):
    model = models.EmailCCContent
    fields = ("cc_email",)
    extra = 0


@admin.register(models.InsertionOrders, site=admin_site)
class InsertionOrdersAdmin(admin.ModelAdmin):

    # ADD THIS
    class Media:
        js = ('admin/js/campaign_status.js',)
    readonly_fields = ("order_id", "created_on", "io_file", "view_io_file_link", "generate_io_file", "order_taken_by")
    search_fields = ("order_id", "name", "work_order_no")
    date_hierarchy = "created_on"
    inlines = [IODetailsAdminInline, EmailCCContentAdminInline]
    fieldsets = [
        ('New IO Info', {'fields': (("order_id", "created_on", "view_io_file_link", "generate_io_file"), "name",
                                    "contact_person", "work_order_no", "report_id", ("start_date", "end_date"),
                                    "geo", "status")}
         ),
        ('Official Purpose', {'fields': ("to_email", "signed_io", "order_taken_by")})
    ]

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not request.user.groups.filter(name="Juniors_logins").exists():
            form.base_fields["contact_person"].choices = [(x.id, x.name) for x in
                                                          models.CompanyContacts.objects.filter(is_active=1)]
        else:
            form.base_fields["contact_person"].queryset = models.CompanyContacts.objects.filter(is_active=1)
        return form

    def get_queryset(self, request):
        self.request = request
        qs = super(InsertionOrdersAdmin, self).get_queryset(request)

        # Add this block
        today = date.today()

        qs.filter(
            start_date__lte=today,
            end_date__gte=today
        ).exclude(status__in=["Stopped", "Paused"]).update(status="Live")

        qs.filter(
            end_date__lt=today
        ).exclude(status__in=["Stopped", "Paused"]).update(status="Completed")

        qs.filter(
            start_date__gt=today
        ).exclude(status__in=["Stopped", "Paused"]).update(status="Scheduled")
        # ───────────────────────────────────────────
        return qs

        #return super(InsertionOrdersAdmin, self).get_queryset(request)

    def get_list_display(self, request):
        if request.user.groups.filter(name="Juniors_logins").exists():
            return ("sub_campaign", "io_id", "name", "start_date", "end_date", "total_impressions", "import_line_items")
        return ("sub_campaign", "io_id", "name", "start_date", "end_date", "total_impressions", "total_cost", "view_io",
                "sent_email", "import_line_items")

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('generate-io/<int:pk>/', self.render_io_template, name='admin_generate_io'),
            path('import-line_item/<int:pk>/', self.upload_line_items),
            #path('preview-io/<int:pk>/', self.preview_io, name='admin_preview_io'),  # ADDED
        ]
        return my_urls + urls
    

    # def preview_io(self, request, pk):
    #     order = utils.int_to_io(pk)
    #     return render(request, "io_preview.html", {"order": order})


    def save_model(self, request, obj, form, change):
        if not change:
            obj.order_id = utils.generate_order_id(obj)
            obj.created_by = request.user
            obj.total_cost = 0
            obj.total_impressions = 0
        if hasattr(obj, "order_taken_by"):
            if not obj.order_taken_by:
                obj.order_taken_by = request.user
        admin.ModelAdmin.save_model(self, request, obj, form, change) 
        #super(InsertionOrdersAdmin, self).save_model(request, obj, form, change)


    # def save_model(self, request, obj, form, change):
    #     # Don't auto-set status anymore
    #     # calculated_status property handles it on the fly
    #     # Only preserve manual Stopped/Paused
    #     super(CampaignsAdmin, self).save_model(request, obj, form, change)


    # Net cost is auto-calculated when line items are saved 
    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)

        for obj in formset.deleted_objects:
            obj.delete()

        for instance in instances:
            if instance.ad_metrics.id == 1:  # CPM 
                instance.net_cost = round((instance.volume / 1000) * instance.unit_cost, 2)
            else:
                instance.net_cost = round(instance.volume * instance.unit_cost, 2)
            instance.save()

        formset.save_m2m()

    def has_delete_permission(self, request, obj=None):
        return False

    def import_line_items(self, obj):
        return mark_safe(
            "<a class='btn btn-outline-secondary btn-sm' href='import-line_item/{}/'>Import Line Items</a>".format(
                obj.id))

    def view_io(self, obj):
        if obj.io_file:
            return mark_safe(
                "<center><a href='generate-io/{id}/' class='btn btn-outline-secondary btn-sm'>Generate IO</a>"
                "<br><br><a href='{io}' target='_blank' class='btn btn-outline-secondary btn-sm'>View IO</a> "
                "</center>".format(id=obj.id, io=obj.io_file.url))
        return mark_safe(
            "<center><a href='generate-io/{id}/' class='btn btn-outline-secondary btn-sm'>Generate IO</a>"
            "</center>".format(id=obj.id))




    def sent_email(self, obj):
        return mark_safe("<a class='btn btn-outline-secondary btn-sm'>Send Email</a>")

    def upload_line_items(self, request, pk):
    # Reads CSV with columns:
    # Name, Ethnicity, Start Date, End Date, Ad Format, Units, Unit cost, Volume, Average CTR, Status
    # Creates or updates IODetails records
        if request.method == "POST":
            insertion_orders = utils.int_to_io(pk)
            csv_file = request.FILES["csv_file"]
            decoded_file = csv_file.read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded_file)
            for row in reader:
                ethinicity, _ = models.Ethnicity.objects.get_or_create(title=row['Ethnicity'].strip(),
                                                                       country=insertion_orders.sub_campaign.campaign.company.country)
                start_date = datetime.strptime(row['Start Date'].strip(), "%d-%m-%Y")
                end_date = datetime.strptime(row['End Date'].strip(), "%d-%m-%Y")
                ad_type = models.AdsFormats.objects.get(title=row['Ad Format'].strip())
                units = models.Metrics.objects.get(title=row['Units'].strip())
                unit_cost = row['Unit cost'].strip()
                volume = row['Volume'].strip()
                avg_ctr = row['Average CTR'].strip()
                status = row['Status'].strip()
                if units.id == 1:
                    net_cost = round((int(row['Volume'].strip()) / 1000) * float(row['Unit cost'].strip()), 2)
                else:
                    net_cost = round(int(row['Volume'].strip()) * float(row['Unit cost'].strip()), 2)

                if row.get('Line Item ID'):
                    try:
                        line_item = models.IODetails.objects.get(item_id=row['Line Item ID'].strip())
                        line_item.description = row.get('Name', line_item.description).strip()
                        line_item.start_date = start_date
                        line_item.end_date = end_date
                        line_item.ethinicity = ethinicity
                        line_item.ad_type = ad_type
                        line_item.units = units
                        line_item.unit_cost = unit_cost
                        line_item.volume = volume
                        line_item.avg_ctr = avg_ctr
                        line_item.status = status
                        line_item.net_cost = net_cost
                        line_item.save()
                    except Exception as e:
                        self.message_user(request, "{name} Not added - {e}".format(name=row.get('Name'), e=e),
                                          level=messages.ERROR)

                else:
                    try:
                        models.IODetails.objects.get_or_create(
                            io=insertion_orders, description=row['Name'].strip(), defaults={
                                "description": row['Name'].strip(), "io_id": insertion_orders.id,
                                "start_date": start_date, "end_date": end_date, "ethinicity": ethinicity,
                                "ad_type": ad_type, "net_cost": net_cost,
                                "ad_metrics": units, "unit_cost": unit_cost, "volume": volume, "avg_ctr": avg_ctr,
                                "status": status
                            })
                    except Exception as e:
                        self.message_user(request, "{name} Not added - {e}".format(name=row.get('Name'), e=e),
                                          level=messages.ERROR)
            return redirect("../../")

        form = CsvImportForm()
        payload = {"form": form}
        return render(request, "csv_import_new.html", payload)

    @staticmethod
    def render_io_template(request, pk):
        order = utils.int_to_io(pk)
        return utils.render_to_pdf(request, order)

    def view_io_file_link(self, obj):
        if self.request.user.groups.filter(name="Juniors_logins").exists():
            return "-"

        if obj.io_file:
            return mark_safe("<a class='custom-inline-link-field' target='_blank' href='{url}'"
                             ">View IO</a>".format(url=obj.io_file.url))
        return "-"

    def generate_io_file(self, obj):
        if self.request.user.groups.filter(name="Juniors_logins").exists():
            return "-"

        if obj.io_file:
            url = reverse('Publisher_admin:admin_generate_io', args=[obj.id])
            return mark_safe("<a class='custom-inline-link-field' target='_blank' href='{url}'"
                             ">Generate IO</a>".format(url=url))
        return "-"

    view_io.short_description = "View IO"
    sent_email.short_description = "Send Email"
    view_io_file_link.short_description = "View IO"
    generate_io_file.short_description = "Generate IO"


class InsertionOrdersAdminInline(admin.StackedInline):
    model = models.InsertionOrders
    fieldsets = [
        ('New IO Info', {'fields': ("view_line_items", ("order_id", "created_on", "view_io_file", "generate_io_file"),
                                    "name", "contact_person", "work_order_no", "report_id", ("start_date", "end_date"),
                                    "geo", "status")}
         ),
        ('Official Purpose', {'fields': ("to_email", "signed_io", "order_taken_by")})
    ]
    readonly_fields = ("order_id", "view_line_items", 'total_impressions', "total_cost", "total_impression",
                       "total_clicks", "view_io_file", "generate_io_file", "created_on")
    extra = 0
    min_num = 1

    def get_queryset(self, request):
        self.request = request
        return super(InsertionOrdersAdminInline, self).get_queryset(request)

    # def get_formset(self, request, obj=None, **kwargs):
    #     form = super().get_formset(request, obj, **kwargs)
    #     if request.user.groups.filter(name="Juniors_logins").exists():
    #         form.base_fields["contact_person"].choices = [(x.id, "{}-{}".format(x.company.client_id, x.id)) for x in
    #                                                       models.CompanyContacts.objects.filter(is_active=1)]
    #     else:
    #         form.base_fields["contact_person"].queryset = models.CompanyContacts.objects.filter(is_active=1)
    #     return form

    def view_line_items(self, obj):
        if obj.id:
            return mark_safe(
                "<a class='btn btn-sm btn btn-primary text-white' href='/insertion_order/insertionorders/{id}"
                "/change'>Add/Edit Line Items</a>".format(id=obj.id))
        return "-"

    def view_io_file(self, obj):
        if self.request.user.groups.filter(name="Juniors_logins").exists():
            return "-"
        if obj.io_file:
            return mark_safe("<a class='btn btn-sm btn btn-primary text-white' target='_blank' href='{url}'"
                             ">View IO</a>".format(url=obj.io_file.url))
        return "-"

    def generate_io_file(self, obj):
        if self.request.user.groups.filter(name="Juniors_logins").exists():
            return "-"

        if obj.id:
            url = reverse('Publisher_admin:admin_generate_io', args=[obj.id])
            return mark_safe("<a class='custom-inline-link-field' target='_blank' href='{url}'"
                             ">Generate IO</a>".format(url=url))
        return "-"

    view_line_items.short_description = "Line Items"
    view_io_file.short_description = "View IO"
    generate_io_file.short_description = "Generate IO"

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.SubCampaign, site=admin_site)
class SubCampaignAdmin(admin.ModelAdmin):

    class Media:
        js = ('admin/js/campaign_status.js',)
    list_display = ("campaign_id", "work_order_no", "campaign", "booking_id", "name", "start_date", "end_date",
                    "total_volume_booked", "total_volume_delivered", "remaining_volumes", "status", "view_report",
                    "download_report", "request")
    search_fields = ("name", "campaign__name", "booking_id", "campaign__work_order_no", "campaign__campaign_id")
    inlines = [InsertionOrdersAdminInline]
    list_filter = (("start_date", PastDateRangeFilter), ("end_date", PastDateRangeFilter),
                   ("status", ChoiceDropdownFilter), ("campaign__company", RelatedDropdownFilter))

    def has_delete_permission(self, request, obj=None):
        return False

    def get_list_filter(self, request):
        if request.user.is_superuser:
            return (("start_date", PastDateRangeFilter), ("end_date", PastDateRangeFilter),
                    ("status", ChoiceDropdownFilter), ("campaign__company", RelatedDropdownFilter))
        return (("start_date", PastDateRangeFilter), ("end_date", PastDateRangeFilter),
                ("status", ChoiceDropdownFilter))

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('<int:pk>/view-report/', self.view_campaign_report),
            path('<int:pk>/requests/', self.request_campaign),
            path('<int:pk>/download-report/', self.download_campaign_report),
        ]
        return my_urls + urls

    # def get_formsets_with_inlines(self, request, obj=None):
    #     for inline in self.get_inline_instances(request, obj):
    #         inline.form.base_fields["contact_person"].choices =  [(x.id, "{}-{}".format(x.company.client_id, x.id)) for x in models.CompanyContacts.objects.filter(is_active=1)]
    #         yield inline.get_formset(request, obj), inline

    # def get_form(self, request, obj=None, **kwargs):
    #     form = super().get_form(request, obj, **kwargs)
    #     if request.user.groups.filter(name="Juniors_logins").exists():
    #         form.base_fields["contact_person"].choices = [(x.id, "{}-{}".format(x.company.client_id, x.id)) for x in
    #                                                       models.CompanyContacts.objects.filter(is_active=1)]
    #     else:
    #         form.base_fields["contact_person"].queryset = models.CompanyContacts.objects.filter(is_active=1)
    #     return form

    def get_queryset(self, request):
        qs = super(SubCampaignAdmin, self).get_queryset(request)


        # ── ADD THIS BLOCK ─────────────────────────
        today = date.today()

        # Update SubCampaign status by its own dates
        qs.filter(
            start_date__lte=today,
            end_date__gte=today
        ).exclude(status__in=["Stopped", "Paused"]).update(status="Live")

        qs.filter(
            end_date__lt=today
        ).exclude(status__in=["Stopped", "Paused"]).update(status="Completed")

        qs.filter(
            start_date__gt=today
        ).exclude(status__in=["Stopped", "Paused"]).update(status="Scheduled")
  
    # ==================================================================

        if request.user.groups.filter(id__in=[2]):
            if hasattr(request.user, "company_contact_user"):
                return qs.filter(campaign__company=request.user.company_contact_user.company)
            else:
                return qs.filter(campaign__company__user=request.user)
        return qs

    def get_list_display(self, request):
        if request.user.groups.filter(name__in=["Clients"]):
            return ("campaign_id", "work_order_no", "campaign", "booking_id", "name", "start_date", "end_date",
                    "total_volume_booked", "total_volume_delivered", "remaining_volumes", "campaign_status",
                    "view_report",
                    "download_report", "request")

        return ("campaign_id", "work_order_no", "campaign", "booking_id", "name", "start_date", "end_date",
                "total_volume_booked", "total_volume_delivered", "remaining_volumes", "campaign_status",
                "view_report", "download_report", "report_status")

    def campaign_id(self, obj):
        return obj.campaign.campaign_id

    def work_order_no(self, obj):
        return obj.campaign.work_order_no

    # def campaign_status(self, obj):
    #     return mark_safe("<span class='badge badge-pill badge-{status}'>{status}</span>".format(status=obj.status))

    # add this line today 

    def campaign_status(self, obj):
        from datetime import date
        today = date.today()

        # Respect manual statuses
        if obj.status in ["Stopped", "Paused"]:
            status = obj.status
            color = "danger" if obj.status == "Stopped" else "warning"
        elif obj.start_date > today:
            status = "Scheduled"
            color = "primary"
        elif obj.start_date <= today <= obj.end_date:
            status = "Live"
            color = "success"
        else:
            status = "Completed"
            color = "secondary"

        return mark_safe(
            "<span class='badge badge-pill badge-{color}'>"
            "{status}</span>".format(color=color, status=status)
        )

    def report_status(self, obj):
        today = datetime.today()
        my_list = "<ul class=''>"
        for insertion_order in obj.insertion_order.all():

            for line_item in insertion_order.io_details.all():
                remaining_days = (line_item.end_date - today.date()).days
                remaining_days = remaining_days if remaining_days > 0 else 0
                remaining_impressions = line_item.volume - line_item.total_impression()
                try:
                    daily_target = round(remaining_impressions / remaining_days)
                except ZeroDivisionError:
                    daily_target = 0
                report = line_item.reports.latest("report_on")
                if report:
                    try:
                        pct = round((daily_target - report.impression) * 100 / report.impression)
                    except ZeroDivisionError:
                        pct = 0   
                    if pct > 0 and pct > 10:  # under-delivering by >10% (Show red)
                        my_list += """<li class=" text-danger">{} - {} ({}%)</li>""".format(
                            line_item.description, line_item.item_id, pct)

                    elif pct < 0 and pct < -10:   # over-delivering by >10% (show green)
                        my_list += """<li class=" text-success">{} - {} ({}%)</li>""".format(
                            line_item.description, line_item.item_id, pct)

        return mark_safe(my_list + "</ul>")

    def request(self, obj):
        return mark_safe("""<a href="{}/requests/" class='btn btn-outline-secondary btn-sm'>
        Raise Request</a>""".format(obj.id))

    def view_report(self, obj):
        return mark_safe("""<a href="{}/view-report/" class='btn btn-outline-secondary btn-sm'>
           View Report</a>""".format(obj.id))

    def download_report(self, obj):
        return mark_safe("""<a href="{}/download-report/" class='btn btn-outline-secondary btn-sm'>
              Download</a>""".format(obj.id))


    # def view_campaign_report(self, request, pk):
    #     request.current_app = 'Publisher_admin'
    #     data = admin_site.each_context(request)
    #     data.update({
    #         'title': 'Campaign Report',
    #     })
    #     data['campaign'] = utils.int_to_sub_campaigns(pk)

    #     # Show budget only to superuser or Managers (group id=1)
    #     data['show_budget'] = (
    #     request.user.is_superuser or
    #     request.user.groups.filter(name__in=["Managers"]).exists())
    #     return render(request, "campaign_report.html", data)


    # Today replace this line
    def view_campaign_report(self, request, pk):
        from datetime import date
        request.current_app = 'Publisher_admin'
        data = admin_site.each_context(request)
        data.update({
            'title': 'Campaign Report',
        })
        data['campaign'] = utils.int_to_sub_campaigns(pk)
        data['today'] = date.today()   # ← ADD THIS
        data['show_budget'] = (
            request.user.is_superuser or
            request.user.groups.filter(name__in=["Managers"]).exists() or
            request.user.groups.filter(name__in=["Clients"]).exists()
            )  # ← MODIFY THIS TO ADD CLIENTS
        return render(request, "campaign_report.html", data)




    def request_campaign(self, request, pk):
        request.current_app = 'Publisher_admin'
        data = admin_site.each_context(request)
        data.update({
            'title': 'Campaign Report',
        })
        data['campaign'] = utils.int_to_sub_campaigns(pk)

        return render(request, "clientrequests/campaign-status-request.html", data)

    def download_campaign_report(self, request, pk):

        if not request.user.is_authenticated:
            return redirect('/')
        sub_campaigns = utils.int_to_sub_campaigns(pk)

        output = io.BytesIO()

        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        normal_format = workbook.add_format(
            {'border': 1, 'align': 'center', 'valign': 'vcenter', "font_size": 10})

        merge_format = workbook.add_format(
            {'bold': 1, 'border': 1, 'align': 'center', 'valign': 'vcenter', 'fg_color': '#fce5cd', "font_size": 10})

        for insertion_order in sub_campaigns.insertion_order.all():
            insertion_order_worksheet = workbook.add_worksheet(slugify(insertion_order.io_id()[:20]))

            col = 0

            for idx, line_item in enumerate(insertion_order.io_details.filter(category__isnull=True)):
                report = line_item_report(line_item)
                temp_row = 2

                # Row 1
                insertion_order_worksheet.write(temp_row, col, line_item.start_date.strftime("%d %B, %Y"),
                                                normal_format)
                insertion_order_worksheet.merge_range(temp_row, col + 1, temp_row, col + 2, line_item.description,
                                                      merge_format)
                insertion_order_worksheet.write(temp_row, col + 3, "Daily", normal_format)

                # Row 2
                temp_row += 1
                insertion_order_worksheet.write(temp_row, col, line_item.end_date.strftime("%d %B, %Y"), normal_format)
                insertion_order_worksheet.merge_range(temp_row, col + 1, temp_row, col + 2, "Target impressions",
                                                      merge_format)
                insertion_order_worksheet.write(temp_row, col + 3, line_item.volume, normal_format)

                # Row 3
                temp_row += 1
                # insertion_order_worksheet.write(temp_row, col, report['total_days'], normal_format)
                insertion_order_worksheet.merge_range(temp_row, col + 1, temp_row, col + 2, "Achieved impressions",
                                                      merge_format)
                insertion_order_worksheet.write(temp_row, col + 3, line_item.total_impression(), normal_format)

                # Row 4
                temp_row += 1
                # insertion_order_worksheet.write(temp_row, col, report['remaining_days'], normal_format)
                insertion_order_worksheet.merge_range(temp_row, col + 1, temp_row, col + 2, "Remaining impressions",
                                                      merge_format)
                insertion_order_worksheet.write(temp_row, col + 3, report['remaining_impressions'], normal_format)

                # Row 5
                temp_row += 1
                insertion_order_worksheet.merge_range(temp_row, col + 1, temp_row, col + 2, "Daily Target",
                                                      merge_format)
                insertion_order_worksheet.write(temp_row, col + 3, report['daily_target'], normal_format)

                # Row 6
                temp_row += 1
                insertion_order_worksheet.write(temp_row, col, "Daily Report", normal_format)
                insertion_order_worksheet.write(temp_row, col + 1, line_item.total_impression(), normal_format)
                insertion_order_worksheet.write(temp_row, col + 2, line_item.total_clicks(), normal_format)
                insertion_order_worksheet.write(temp_row, col + 3, "{}%".format(line_item.total_ctr()), normal_format)

                # Row 7
                temp_row += 1
                insertion_order_worksheet.write(temp_row, col, "Date", normal_format)
                insertion_order_worksheet.write(temp_row, col + 1, "Impressions", normal_format)
                insertion_order_worksheet.write(temp_row, col + 2, "Clicks", normal_format)
                insertion_order_worksheet.write(temp_row, col + 3, "CTR", normal_format)

                for daily_report in report['reports']:
                    temp_row += 1
                    insertion_order_worksheet.write(temp_row, col, daily_report['date'].strftime("%d %B, %Y"),
                                                    normal_format)
                    insertion_order_worksheet.write(temp_row, col + 1, daily_report["impression"], normal_format)
                    insertion_order_worksheet.write(temp_row, col + 2, daily_report["clicks"], normal_format)
                    insertion_order_worksheet.write(temp_row, col + 3, daily_report["ctr"], normal_format)

                col += 6

            for line_item in insertion_order.io_details.filter(category__isnull=False):
                report = line_item_report(line_item)
                line_item_worksheet = workbook.add_worksheet(slugify(line_item.description[:20]))

                row = 0
                col = 0
                temp_row = row

                line_item_worksheet.write(row, col, "Insertion Order", merge_format)
                line_item_worksheet.write(row, col + 1, "Insertion Order ID", merge_format)
                line_item_worksheet.write(row, col + 2, "Line Item", merge_format)
                line_item_worksheet.write(row, col + 3, "Date", merge_format)
                line_item_worksheet.write(row, col + 4, "Campaign", merge_format)
                line_item_worksheet.write(row, col + 5, "Campaign ID", merge_format)
                line_item_worksheet.write(row, col + 6, "Impressions", merge_format)
                line_item_worksheet.write(row, col + 7, "Clicks", merge_format)
                line_item_worksheet.write(row, col + 8, "Click Rate (CTR)", merge_format)
                line_item_worksheet.write(row, col + 9, "Start views", merge_format)
                line_item_worksheet.write(row, col + 10, "Complete Views", merge_format)
                line_item_worksheet.write(row, col + 11, "Video Completion Rate (VCR)", merge_format)
                line_item_worksheet.write(row, col + 12, "Viewable Impressions", merge_format)
                line_item_worksheet.write(row, col + 13, "Measurable Impressions", merge_format)
                line_item_worksheet.write(row, col + 14, "Viewability", merge_format)

                for daily_report in report['reports']:
                    temp_row += 1
                    line_item_worksheet.write(temp_row, col, line_item.io.name, normal_format)
                    line_item_worksheet.write(temp_row, col + 1, line_item.io.io_id(), normal_format)
                    line_item_worksheet.write(temp_row, col + 2, line_item.description, normal_format)
                    line_item_worksheet.write(temp_row, col + 3, daily_report['date'].strftime("%d %B, %Y"),
                                              normal_format)
                    line_item_worksheet.write(temp_row, col + 4, line_item.io.sub_campaign.name, normal_format)
                    line_item_worksheet.write(temp_row, col + 5, line_item.io.sub_campaign.booking_id, normal_format)
                    line_item_worksheet.write(temp_row, col + 6, daily_report['impression'], normal_format)
                    line_item_worksheet.write(temp_row, col + 7, daily_report['clicks'], normal_format)
                    line_item_worksheet.write(temp_row, col + 8, "{} %".format(daily_report['ctr']), normal_format)
                    line_item_worksheet.write(temp_row, col + 9, daily_report['video_start'], normal_format)
                    line_item_worksheet.write(temp_row, col + 10, daily_report['video_end'], normal_format)
                    line_item_worksheet.write(temp_row, col + 11, "{} %".format(daily_report['video_completion_rate']),
                                              normal_format)
                    line_item_worksheet.write(temp_row, col + 12, daily_report['viewable_impression'], normal_format)
                    line_item_worksheet.write(temp_row, col + 13, daily_report['measurable_impression'], normal_format)
                    line_item_worksheet.write(temp_row, col + 14, "{} %".format(daily_report['viewability']),
                                              normal_format)

        workbook.close()
        output.seek(0)

        response = HttpResponse(output.read(),
                                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response['Content-Disposition'] = "attachment; filename={}.xlsx".format(slugify(sub_campaigns.name[:30]))

        output.close()

        return response

    view_report.short_description = "View Report"
    download_report.short_description = "Download Report"
    view_campaign_report.short_description = "View Campaign Report"
    work_order_no.short_description = "Client Campaign ID"
    campaign_id.short_description = "Campaign ID"
    request.short_description = "Raise Request"
    campaign_status.short_description = "Sub Campaign Status"


class SubCampaignAdminInline(admin.StackedInline):
    model = models.SubCampaign
    fields = ("view_items", "booking_id", "report_id", "name", "start_date", "end_date", "status")
    readonly_fields = ("booking_id", "view_items")
    min_num = 1
    extra = 0

    def has_delete_permission(self, request, obj=None):
        return False

    def view_items(self, obj):
        if obj.id:
            return mark_safe(
                "<a class='btn btn-sm btn btn-primary text-white' href='/insertion_order/subcampaign/{id}"
                "/change'>Add/Edit Insertion Order</a>".format(id=obj.id))
        return "-"

    view_items.short_description = "Insertion Order"


@admin.register(models.Campaigns, site=admin_site)
class CampaignsAdmin(admin.ModelAdmin):
    
    list_display = ("get_campaign_id", "work_order_no", "name", "company_name", "start_date", "end_date", "status", "total_volume", "total_impression", "remaining_volumes", "total_clicks", "total_cost",
                    "download_file")
    list_display_links = ("get_campaign_id", "name", "company_name", "start_date", "end_date",
                          "status", "total_volume", "total_cost", "total_impression", "total_clicks")
    search_fields = ("name", "campaign_id")
    list_filter = (("start_date", PastDateRangeFilter), ("end_date", PastDateRangeFilter),
                   ("status", ChoiceDropdownFilter), ("company", RelatedDropdownFilter))
    inlines = [SubCampaignAdminInline]
    readonly_fields = ("campaign_id",)
    date_hierarchy = "end_date"

    class Media:
        js = ('admin/js/campaign_status.js',)

    def get_list_filter(self, request):
        if request.user.groups.filter(name="Juniors_logins").exists():
            return (("start_date", PastDateRangeFilter), ("end_date", PastDateRangeFilter),
                    ("status", ChoiceDropdownFilter),)
        return (("start_date", PastDateRangeFilter), ("end_date", PastDateRangeFilter),
                ("status", ChoiceDropdownFilter), ("company", RelatedDropdownFilter))

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('import-csv/', self.import_csv),
            path('download-file/<int:pk>/', self.download_excel),

        ]
        return my_urls + urls

    fieldsets = [
        ('Campaign Details',
         {'fields': (("campaign_id", "work_order_no", "purchase_order_no", "report_id"), "name", "company",
                     ("start_date", "end_date"), "subagency", "brand", "website_url", ("status", "is_active"))}
         ),
    ]

    # Junior 
    def get_list_display(self, request):
        if request.user.groups.filter(name="Juniors_logins").exists():
            return ("get_campaign_id", "work_order_no", "name", "company_name", "start_date", "end_date", "status",
                    "total_volume", "total_impression", "remaining_volumes", "total_clicks")
        return ("get_campaign_id", "work_order_no", "name", "company_name", "start_date", "end_date", "status",
                "total_volume", "total_impression", "remaining_volumes", "total_clicks", "total_cost",
                "download_file")




    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if request.user.groups.filter(name="Juniors_logins").exists():
            form.base_fields["company"].choices = [(x.id, x.client_id) for x in
                                                   models.CompanyDetails.objects.filter(is_active=1)]
        else:
            form.base_fields["company"].queryset = models.CompanyDetails.objects.filter(is_active=1)

            # AUTO FILL STATUS BASED ON DATE — ADD THIS
        if obj and obj.start_date and obj.end_date:
            today = date.today()

            # Only auto-fill if current status is NOT Stopped or Paused
            if obj.status not in ["Stopped", "Paused"]:
                if obj.start_date > today:
                    form.base_fields["status"].initial = "Scheduled"

                elif obj.start_date <= today <= obj.end_date:
                    form.base_fields["status"].initial = "Live"

                elif obj.end_date < today:
                    form.base_fields["status"].initial = "Completed"
        return form
        #return form

    def download_file(self, obj):
        return mark_safe("<a class='addlink btn btn-sm' href='download-file/{}/'>Download file</a>".format(obj.id))

   

    # def get_queryset(self, request):
    #     self.request = request
    #     qs = super(CampaignsAdmin, self).get_queryset(request)
    #     today=date.today()   # Add this line

        
    #     if self.model.__name__ == "ActiveCampaigns":
    #         # Live
    #         return qs.filter(start_date__lte=today, end_date__gte=today) # Add this
    #         #return qs.filter(Q(status="Active") | Q(status="Live"))


    #     elif self.model.__name__ == "InactiveCampaigns":
    #         # Upcoming
    #         #return qs.filter(Q(status="Paused") | Q(status="Not Live"))
    #         return qs.filter(start_date__gt=today) # Add this
        

    #     elif self.model.__name__ == "CompletedCampaigns":
    #         # Completed
    #         #return qs.filter(Q(status="Completed") | Q(status="Stopped"))
    #         return qs.filter(end_date__lt=today) # Add this
    #     else:
    #         return qs.filter() # it show all campaign in admin page
        

    def get_queryset(self, request):
        self.request = request
        qs = super(CampaignsAdmin, self).get_queryset(request)
        today = date.today()
          # ── AUTO UPDATE DB WHEN PAGE LOADS ──────────────
    # Update Live
        qs.filter(
            start_date__lte=today,
            end_date__gte=today
            ).exclude(
                status__in=["Stopped", "Paused"]
                ).update(status="Live")

    # Update Completed
        qs.filter(
            end_date__lt=today
            ).exclude(
                status__in=["Stopped", "Paused"]
                ).update(status="Completed")

    # Update Scheduled
    
        qs.filter(
            start_date__gt=today
            ).exclude(
                status__in=["Stopped", "Paused"]
                ).update(status="Scheduled")
        

        # Add this line (08-06-2024) to cascade status update to SubCampaign and InsertionOrder
        # SubCampaign cascade update
        # SubCampaign.objects.filter(start_date__lte=today, end_date__gte=today
        #                            ).exclude(status__in=["Stopped", "Paused"]).update(status="Live")
        # SubCampaign.objects.filter(
        # end_date__lt=today
        # ).exclude(status__in=["Stopped", "Paused"]).update(status="Completed")
        # SubCampaign.objects.filter(start_date__gt=today
        # ).exclude(status__in=["Stopped", "Paused"]).update(status="Scheduled")


         # InsertionOrder cascade update
        # InsertionOrders.objects.filter(start_date__lte=today, end_date__gte=today
        # ).exclude(status__in=["Stopped", "Paused"]).update(status="Live")
        # InsertionOrders.objects.filter(end_date__lt=today
        # ).exclude(status__in=["Stopped", "Paused"]).update(status="Completed")
        # InsertionOrders.objects.filter(start_date__gt=today
        # ).exclude(status__in=["Stopped", "Paused"]).update(status="Scheduled")

# LineItem (IODetails) cascade update ← ADD THIS
        # models.IODetails.objects.filter(start_date__lte=today,end_date__gte=today).exclude(status__in=["Stopped", "Paused"]).update(status="Live")
        # models.IODetails.objects.filter(end_date__lt=today).exclude(status__in=["Stopped", "Paused"]).update(status="Completed")
        # models.IODetails.objects.filter(start_date__gt=today).exclude(status__in=["Stopped", "Paused"]).update(status="Scheduled")


        
        if self.model.__name__ == "ActiveCampaigns":
            return qs.filter(
                start_date__lte=today,
                end_date__gte=today
                ).exclude(status__in=["Stopped", "Paused"])
        elif self.model.__name__ == "InactiveCampaigns":
            return qs.filter(
                start_date__gt=today
                ).exclude(status__in=["Stopped", "Paused"])
        elif self.model.__name__ == "CompletedCampaigns":
            return qs.filter(
                end_date__lt=today
                ).exclude(status__in=["Stopped", "Paused"])
        else:
            return qs    



    # def save_model(self, request, obj, form, change):
    #     today = date.today()

    #     # Automatic status based on dates
    #     if obj.start_date and obj.end_date:

    #         # Stopped or Paused → manual
    #         if obj.status in ["Stopped", "Paused"]:
    #             pass
    #         else:
    #             if obj.start_date > today:
    #                 obj.status = "Scheduled"      # Future campaign
    #             elif obj.start_date <= today <= obj.end_date:
    #                 obj.status = "Live"           # Running now
    #             elif obj.end_date < today:
    #                 obj.status = "Completed" 
    #     admin.ModelAdmin.save_model(self, request, obj, form, change)                  # Already finished
    #     #super(CampaignsAdmin, self).save_model(request, obj, form, change)


    def save_model(self, request, obj, form, change):
        today = date.today()
        # ── MAIN SWITCH: Campaign Stopped/Paused ──────
            # Cascade to all related records
        if obj.start_date and obj.end_date:
            if obj.status in ["Stopped", "Paused"]:
                models.SubCampaign.objects.filter(campaign=obj).exclude(status__in=["Stopped", "Paused"]).update(status=obj.status)
                models.InsertionOrders.objects.filter(sub_campaign__campaign=obj).exclude(status__in=["Stopped", "Paused"]).update(status=obj.status)
                models.IODetails.objects.filter(io__sub_campaign__campaign=obj).exclude(status__in=["Stopped", "Paused"]).update(status=obj.status)
            else:
                if obj.start_date > today:
                    obj.status = "Scheduled"
                elif obj.start_date <= today <= obj.end_date:
                    obj.status = "Live"
                elif obj.end_date < today:
                    obj.status = "Completed"
        admin.ModelAdmin.save_model(self, request, obj, form, change)


    
    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if hasattr(instance, "order_taken_by"):
                if not instance.order_taken_by:
                    instance.order_taken_by = request.user
            instance.save()
        formset.save_m2m()

    def has_delete_permission(self, request, obj=None):
        return False

    def import_csv(self, request):
    # Reads "Campaign Name" and "Campaign Status" columns
    # Bulk updates campaign statuses
        if request.method == "POST":
            if request.FILES["csv_file"].name.endswith(".csv"):
                csv_file = request.FILES["csv_file"]
                decoded_file = csv_file.read().decode('utf-8').splitlines()
                reader = csv.DictReader(decoded_file)
                for row in reader:
                    try:
                        campaign = models.Campaigns.objects.get(name=row['Campaign Name'])
                        if row['Campaign Status']:
                            campaign.status = row['Campaign Status']
                            campaign.save()

                        # if not campaign.subagency:
                        #     campaign.subagency = row['Sub Agency']
                        #
                        # if not campaign.brand:
                        #     campaign.brand = row['Brand']
                        #
                        # if row['DV360 Campaign ID']:
                        #     campaign.report_id = row['DV360 Campaign ID']
                        #
                        #     if not campaign.subagency:
                        #         campaign.subagency = row['Sub Agency']
                        #
                        #     if not campaign.brand:
                        #         campaign.brand = row['Brand']
                        #
                        #     insertion_order = models.InsertionOrders.objects.get(sub_campaign__campaign=campaign,
                        #                                                          name=row['Insertion Order Name'])
                        #     insertion_order.report_id = row['DV360 IO ID']
                        #
                        #     line_item = models.IODetails.objects.get(description=row['Line Item Name'],
                        #                                              io=insertion_order)
                        #     line_item.report_id = row['DV360 Line Item ID']
                        #
                        #     campaign.save()
                        #     insertion_order.save()
                        #     line_item.save()

                    except:
                        print(row)

                self.message_user(request, "Your csv file has been imported")
                return redirect("..")

        form = CsvImportForm()
        payload = {"form": form}
        return render(request, "csv_form.html", payload)


    # #Campaign-level and subcampaign download (download_excel):
    # def download_excel(self, request, pk):
    #     campaign = utils.int_to_campaigns(pk)
    #     output = io.BytesIO()

    #     workbook = xlsxwriter.Workbook(output, {'in_memory': True})

    #     normal_format = workbook.add_format(
    #         {'border': 2, 'align': 'center', 'valign': 'vcenter', "font_size": 10, "bold": True,
    #          "border_color": "#CCCCCC"})
    #     data_format = workbook.add_format(
    #         {'border': 2, 'align': 'center', 'valign': 'vcenter', "font_size": 10, "border_color": "#CCCCCC"})
    #     today = datetime.now()

    #     for line_item in models.IODetails.objects.filter(io__sub_campaign__campaign=campaign):
    #         insertion_order_worksheet = workbook.add_worksheet(str(line_item.item_id))

    #         insertion_order_worksheet.write(2, 0, "Date of ID Setup", normal_format)
    #         insertion_order_worksheet.write(3, 0, "Advertiser ID", normal_format)
    #         insertion_order_worksheet.write(4, 0, "Campaign ID", normal_format)
    #         insertion_order_worksheet.write(5, 0, "IO ID", normal_format)
    #         insertion_order_worksheet.write(6, 0, "IO Name", normal_format)
    #         insertion_order_worksheet.write(7, 0, "Impressions Booked", normal_format)
    #         insertion_order_worksheet.write(8, 0, "Start Date", normal_format)
    #         insertion_order_worksheet.write(9, 0, "End Date", normal_format)
    #         insertion_order_worksheet.write(10, 0, "Target CPM", normal_format)
    #         insertion_order_worksheet.write(11, 0, "Target CTR", normal_format)
    #         insertion_order_worksheet.write(12, 0, "Line Item ID", normal_format)
    #         insertion_order_worksheet.write(13, 0, "Line Item Name", normal_format)
    #         insertion_order_worksheet.write(14, 0, "Ethnicity", normal_format)
    #         insertion_order_worksheet.write(15, 0, "Ad Format", normal_format)
    #         insertion_order_worksheet.write(16, 0, "Geography", normal_format)
    #         insertion_order_worksheet.write(17, 0, "Market", normal_format)
    #         insertion_order_worksheet.write(18, 0, "Viewability", normal_format)
    #         insertion_order_worksheet.write(19, 0, "Creative", normal_format)
    #         insertion_order_worksheet.write(20, 0, "VCR", normal_format)
    #         insertion_order_worksheet.write(21, 0, "KPI", normal_format)
    #         insertion_order_worksheet.write(22, 0, "Sitelist", normal_format)

    #         insertion_order_worksheet.write(10, 1, "", data_format)
    #         insertion_order_worksheet.write(11, 1, "", data_format)
    #         insertion_order_worksheet.write(17, 1, "", data_format)
    #         insertion_order_worksheet.write(18, 1, "", data_format)
    #         insertion_order_worksheet.write(19, 1, "", data_format)
    #         insertion_order_worksheet.write(20, 1, "", data_format)
    #         insertion_order_worksheet.write(21, 1, "", data_format)
    #         insertion_order_worksheet.write(22, 1, "", data_format)

    #         insertion_order_worksheet.write(2, 1, today.strftime("%d-%B-%Y"), data_format)
    #         insertion_order_worksheet.write(3, 1, campaign.company.client_id, data_format)
    #         insertion_order_worksheet.write(4, 1, campaign.campaign_id, data_format)
    #         insertion_order_worksheet.write(5, 1, line_item.io.io_id(), data_format)
    #         insertion_order_worksheet.write(6, 1, line_item.io.name, data_format)
    #         insertion_order_worksheet.write(7, 1, line_item.volume, data_format)
    #         insertion_order_worksheet.write(8, 1, line_item.start_date.strftime("%d-%B-%Y"), data_format)
    #         insertion_order_worksheet.write(9, 1, line_item.end_date.strftime("%d-%B-%Y"), data_format)
    #         insertion_order_worksheet.write(12, 1, line_item.item_id, data_format)
    #         insertion_order_worksheet.write(13, 1, line_item.description, data_format)
    #         insertion_order_worksheet.write(14, 1, line_item.ethinicity.title, data_format)
    #         if line_item.ad_type:
    #             insertion_order_worksheet.write(15, 1, line_item.ad_type.title, data_format)
    #         insertion_order_worksheet.write(16, 1, line_item.io.geo, data_format)
    #         insertion_order_worksheet.set_column(0, 0, 16)
    #         insertion_order_worksheet.set_column(1, 1, 50)
    #     workbook.close()
    #     output.seek(0)

    #     response = HttpResponse(output.read(),
    #                             content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    #     response['Content-Disposition'] = "attachment; filename={}.xlsx".format(slugify(campaign.name[:30]))

    #     output.close()
    #     return response
    

    def download_excel(self, request, pk):
        from calendar import monthrange
        campaign = utils.int_to_campaigns(pk)
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        normal_format = workbook.add_format({
            'border': 2, 'align': 'center', 'valign': 'vcenter',
            "font_size": 10, "bold": True, "border_color": "#CCCCCC"
        })
        data_format = workbook.add_format({
            'border': 2, 'align': 'center', 'valign': 'vcenter',
            "font_size": 10, "border_color": "#CCCCCC"
        })

        today = datetime.now()

        # ── Helper 1: Month-wise split ──────────────────────────────────────────
        def get_monthly_splits(start_date, end_date):
            """
            Example:
            start=12-May-2026, end=25-Jun-2026
            → [(12-May, 31-May), (01-Jun, 25-Jun)]

            start=22-Jun-2026, end=23-Jul-2026
            → [(22-Jun, 30-Jun), (01-Jul, 23-Jul)]
            """
            splits = []
            current = start_date

            while current <= end_date:
                last_day = monthrange(current.year, current.month)[1]
                month_end = current.replace(day=last_day)
                actual_end = min(month_end, end_date)
                splits.append((current, actual_end))

                if month_end >= end_date:
                    break

                # Move to 1st of next month
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1, day=1)
                else:
                    current = current.replace(month=current.month + 1, day=1)

            return splits

        # ── Helper 2: Write one IO Setup table block ────────────────────────────
        def write_io_setup_table(worksheet, col, line_item, period_start, period_end):
            """
            

            Impressions Booked = always TOTAL (not split)
            Start Date / End Date = this month's portion only
            Monthly Target = proportional target for this period
            """

            # Monthly target calculation
            total_days = (line_item.end_date - line_item.start_date).days + 1
            days_in_period = (period_end - period_start).days + 1
            try:
                period_target = round((line_item.volume / total_days) * days_in_period)
            except ZeroDivisionError:
                period_target = 0

            row = 2

            # Row 3: Date of ID Setup
            worksheet.write(row, col, "Date of ID Setup", normal_format)
            worksheet.write(row, col + 1, today.strftime("%d-%B-%Y"), data_format)

            # Row 4: Advertiser ID
            row += 1
            worksheet.write(row, col, "Advertiser ID", normal_format)
            worksheet.write(
                row, col + 1,
                line_item.io.sub_campaign.campaign.company.client_id,
                data_format
            )

            # Row 5: Campaign ID
            row += 1
            worksheet.write(row, col, "Campaign ID", normal_format)
            worksheet.write(
                row, col + 1,
                line_item.io.sub_campaign.campaign.campaign_id or "",
                data_format
            )

            # Row 6: IO ID
            row += 1
            worksheet.write(row, col, "IO ID", normal_format)
            worksheet.write(row, col + 1, line_item.io.io_id(), data_format)

            # Row 7: IO Name
            row += 1
            worksheet.write(row, col, "IO Name", normal_format)
            worksheet.write(row, col + 1, line_item.io.name, data_format)

            # Row 8: Impressions Booked — always TOTAL volume
            row += 1
            # worksheet.write(row, col, "Impressions Booked", normal_format)
            # worksheet.write(row, col + 1, line_item.volume, data_format)
            

            # Row 9: Start Date — this period's start
            row += 1
            worksheet.write(row, col, "Start Date", normal_format)
            worksheet.write(
                row, col + 1,
                period_start.strftime("%d-%B-%Y"),
                data_format
            )

            # Row 10: End Date — this period's end
            row += 1
            worksheet.write(row, col, "End Date", normal_format)
            worksheet.write(
                row, col + 1,
                period_end.strftime("%d-%B-%Y"),
                data_format
            )

            # Row 11: Target CPM — blank
            row += 1
            worksheet.write(row, col, "Target CPM", normal_format)
            worksheet.write(row, col + 1, "", data_format)

            # Row 12: Target CTR — blank
            row += 1
            worksheet.write(row, col, "Target CTR", normal_format)
            worksheet.write(row, col + 1, "", data_format)

            # Row 13: Monthly Target — calculated for this period
            row += 1
            month_label = f"{period_start.strftime('%B')} Monthly Target"  # "June Monthly Target"
            worksheet.write(row, col, month_label, normal_format)
            worksheet.write(row, col + 1, period_target, data_format)

            # Row 14: Line Item ID
            row += 1
            worksheet.write(row, col, "Line Item ID", normal_format)
            worksheet.write(row, col + 1, line_item.item_id, data_format)

            # Row 15: Line Item Name
            row += 1
            worksheet.write(row, col, "Line Item Name", normal_format)
            worksheet.write(row, col + 1, line_item.description, data_format)

            # Row 16: Ethnicity
            row += 1
            worksheet.write(row, col, "Ethnicity", normal_format)
            worksheet.write(
                row, col + 1,
                line_item.ethinicity.title if line_item.ethinicity else "",
                data_format
            )

            # Row 17: Ad Format
            row += 1
            worksheet.write(row, col, "Ad Format", normal_format)
            worksheet.write(
                row, col + 1,
                line_item.ad_type.title if line_item.ad_type else "",
                data_format
            )

            # Row 18: Geography
            row += 1
            worksheet.write(row, col, "Geography", normal_format)
            worksheet.write(row, col + 1, line_item.io.geo or "", data_format)

            # Row 19: Market — blank
            row += 1
            worksheet.write(row, col, "Market", normal_format)
            worksheet.write(row, col + 1, "", data_format)

            # Row 20: Viewability — blank
            row += 1
            worksheet.write(row, col, "Viewability", normal_format)
            worksheet.write(row, col + 1, "", data_format)

            # Row 21: Creative — blank
            row += 1
            worksheet.write(row, col, "Creative", normal_format)
            worksheet.write(row, col + 1, "", data_format)

            # Row 22: VCR — blank
            row += 1
            worksheet.write(row, col, "VCR", normal_format)
            worksheet.write(row, col + 1, "", data_format)

            # Row 23: KPI — blank
            row += 1
            worksheet.write(row, col, "KPI", normal_format)
            worksheet.write(row, col + 1, "", data_format)

            # Row 24: Sitelist — blank
            row += 1
            worksheet.write(row, col, "Sitelist", normal_format)
            worksheet.write(row, col + 1, "", data_format)

            # Each table = 2 data cols + 1 gap col
            return col + 3

        # ── Main loop: one sheet per line item ──────────────────────────────────
        for line_item in models.IODetails.objects.filter(
            io__sub_campaign__campaign=campaign
        ).select_related(
            "io",
            "ethinicity",
            "ad_type",
            "io__sub_campaign__campaign__company"
        ):
            sheet_name = str(line_item.item_id)
            worksheet = workbook.add_worksheet(sheet_name)

            # Column widths — repeat for every possible table (up to 6 months)
            for i in range(6):
                base = i * 3
                worksheet.set_column(base,     base,     22)   # label col
                worksheet.set_column(base + 1, base + 1, 45)   # value col
                worksheet.set_column(base + 2, base + 2, 3)    # gap col

            # Get month splits for this line item
            splits = get_monthly_splits(line_item.start_date, line_item.end_date)

            # Write one table per month, side by side
            col = 0
            for (period_start, period_end) in splits:
                col = write_io_setup_table(
                    worksheet, col,
                    line_item,
                    period_start, period_end
                )

        workbook.close()
        output.seek(0)

        response = HttpResponse(
            output.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response['Content-Disposition'] = "attachment; filename={}.xlsx".format(
            slugify(campaign.name[:30])
        )
        output.close()
        return response
        
        


    # Company shown as client_id only (not full name)
    def company_name(self, obj):
        if self.request.user.groups.filter(name="Juniors_logins").exists():
            return obj.company.client_id       # shows "CL00023" not "PepsiCo India"
        return obj.company  # shows full company name


# --- ADD THESE PROXY MODELS ---

class ActiveCampaigns(models.Campaigns):
    class Meta:
        proxy = True
        verbose_name = "Live Campaign"
        verbose_name_plural = "1. Live Campaigns"

class InactiveCampaigns(models.Campaigns):
    class Meta:
        proxy = True
        verbose_name = "Upcoming Campaign"
        verbose_name_plural = "2. Upcoming Campaigns"

class CompletedCampaigns(models.Campaigns):
    class Meta:
        proxy = True
        verbose_name = "Completed Campaign"
        verbose_name_plural = "3. Completed Campaigns"


@admin.register(ActiveCampaigns, site=admin_site)
class ActiveCampaignsAdmin(CampaignsAdmin):
    pass


@admin.register(InactiveCampaigns, site=admin_site)
class InactiveCampaignsAdmin(CampaignsAdmin):
    pass


@admin.register(CompletedCampaigns, site=admin_site)
class CompletedCampaignsAdmin(CampaignsAdmin):
    pass


    


@admin.register(models.LineItemsPerformance, site=admin_site)
class ItemPerformanceAdmin(admin.ModelAdmin):
    list_display = ("category", "line_item", "priority", "base_value")
    list_display_links = ("category", "line_item", "priority", "base_value")

    def has_delete_permission(self, request, obj=None):
        return False
