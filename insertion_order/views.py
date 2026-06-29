# It handle entire ad campaign lifecycle

import csv
import json
from datetime import datetime

from annoying.functions import get_object_or_None
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.views import generic
from django.views.decorators.csrf import csrf_exempt

from billiontags_crm import settings
from categories.admin import admin_site
from categories.models import PerformanceCategory, PerformanceSubCategory
from clientrequests.models import LineItemRequest
from insertion_order import utils, models
from insertion_order.models import LineItemsPerformance, IODetails
from insertion_order.utils import int_to_performance_category
import os

# Renders the Insertion Order as an HTML page (used as input for PDF generation by utils.render_to_pdf). Two templates — one with dates, one without.
# ---------------------------------------------------------------------------
# IO Generation
# ---------------------------------------------------------------------------

def generate_io(request, pk):
    order = utils.int_to_io(pk)
    return render(request, "io_template.html", {"order": order})


def generate_io_date(request, pk):
    order = utils.int_to_io(pk)
    return render(request, "io_template_date.html", {"order": order})



def error_upload(rowdict, header_list=None, mode="w"):
    with open(settings.STATICFILES_DIRS[0] + 'custom_admin/files/bulk_upload_error.csv', mode, newline='') as csvfile:
    

        fieldnames = header_list if header_list else []
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        if mode == "w":
            writer.writeheader()
            writer.writerow({})
        else:
            write_dict = {}
            for field in fieldnames:
                write_dict[field] = rowdict.get(field, "")

            writer.writerow(write_dict)




@staff_member_required
def download_report(request):
    if not request.user.is_authenticated:
        return redirect('/')

    queryset = models.IODetails.objects.all()
    response = HttpResponse(content_type='text/csv')

    # force download.
    response['Content-Disposition'] = 'attachment;filename=export.csv'
    # the csv writer

    writer = csv.writer(response)
    field_names = ["Campaign ID", "Campaign Name", "SubCampaign ID", "Subcampagin Name", "Insertion Order Id",
                   "Insertion Order Name", "Line Item Id", "Line Item Name"]
    # Write a first row with header information

    writer.writerow(field_names)
    # Write data rows

    for obj in queryset:
        writer.writerow([obj.io.sub_campaign.campaign.campaign_id, obj.io.sub_campaign.campaign.name,
                         obj.io.sub_campaign.booking_id, obj.io.sub_campaign.name, obj.io.io_id(), obj.io.name,
                         obj.item_id, obj.description])
    return response


# Add this file on (29/06/2026)
@staff_member_required
def download_error_report(request):
    file_path = settings.STATICFILES_DIRS[0] + 'custom_admin/files/bulk_upload_error.csv'
    
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            response = HttpResponse(f.read(), content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="bulk_upload_error.csv"'
            return response
    
    return HttpResponse("Error file not found.", status=404)



#  Bulk Report Upload
@staff_member_required
def custom_admin_view(request):
    """
    If you're using multiple admin sites with independent views you'll need to set
    current_app manually and use correct admin.site

    """
    request.current_app = 'Publisher_admin'
    context = admin_site.each_context(request)
    context.update({
        'title': 'Bulk Report Upload',
    })
    template_name = 'reports/bulk_upload.html'
    if request.method == "POST":
        if request.FILES["csv_file"].name.endswith(".csv"):
            csv_file = request.FILES["csv_file"]
            decoded_file = csv_file.read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded_file)
            file_headers = reader.fieldnames
            header_list = ["Advertiser ID", "Insertion Order ID", "Line Item ID", "Campaign ID", "Billable Impressions",
                           "Clicks", "Revenue (Adv Currency)", "Media Cost (Advertiser Currency)", "Date"]
            header_errors = []
            for header in header_list:
                if header not in file_headers:
                    header_errors.append(header)
            if header_errors:
                context.update({
                    "errors": header_errors
                })
                return render(request, template_name, context)

            error_header = [x for x in file_headers]
            error_header.append("Upload Errors")
            error_upload(rowdict={}, header_list=error_header)
            upload_report_count = 0
            error_report_count = 0
            for row in reader:
                if row['Line Item ID']:
                    excel_errors = []

                    report_id = utils.get_or_none(models.LineItemReportingID, report_id=row['Line Item ID'])

                    report_on = ""

                    if row['Date'].strip():
                        try:
                            report_on = datetime.strptime(row['Date'].strip(), "%d/%m/%Y")
                        except Exception as e:
                            excel_errors.append(str(e))
                    else:
                        excel_errors.append("Date filed can't be empty or null value")

                    if not row.get("Billable Impressions"):
                        excel_errors.append("Billable Impressions filed can't be empty or null value")

                    if not report_id:
                        excel_errors.append("Line Item ID DoesNotExist")

                    # if not excel_errors:
                    #     if insertion_order.campaign
                    #         excel_errors.append("Campaign's Insertion Order ID mismatch")
                    #
                    #     if line_item.io.campaign != campaign:
                    #         excel_errors.append("Campaign's Line Item ID mismatch")
                    #
                    #     if line_item.io != insertion_order:
                    #         excel_errors.append("Insertion Order's Line Item ID mismatch")

                    if not excel_errors:
                        line_item = report_id.line_item

                        if line_item and line_item.category:
                            new_header_list = ["Viewable Impressions", "Measurable Impressions"]
                            if line_item.category.category.id in [1, 2, 3]:
                                new_header_list.append("Start Views")
                                new_header_list.append("Complete Views")
                                new_header_list.append("3rd Quartile Views")
                                new_header_list.append("Midpoint Views")
                                new_header_list.append("1st Quartile Views")

                            for header in new_header_list:
                                if header not in file_headers:
                                    excel_errors.append("{} values required".format(header))

                                elif header not in row and not row.get(header, None):
                                    excel_errors.append("{} values required".format(header))

                        upload_report_count += 1
                        budget = row.get('Revenue (Adv Currency)', "").strip().replace("Rs.", "")
                        media_cost = row.get("Media Cost (Advertiser Currency)", "").strip().replace("Rs.", "")

                        report_id_on = utils.get_or_none(models.ReportingIdReports,
                                                         report_on=report_on, reporting=report_id)

                        if report_id_on:
                            report_id_on.impression = row['Billable Impressions']
                            report_id_on.clicks = row['Clicks']
                            report_id_on.budget = budget
                            report_id_on.media_cost = media_cost

                            if row.get("Viewable Impressions", None):
                                report_id_on.viewable_impression = row.get("Viewable Impressions", None)
                            if row.get("Measurable Impressions", None):
                                report_id_on.measurable_impression = row.get("Measurable Impressions", None)

                            if row.get("Start Views", None):
                                report_id_on.video_start = row.get("Start Views", 0)

                            if row.get("Complete Views", None):
                                report_id_on.video_end = row.get("Complete Views", 0)

                            if row.get("1st Quartile Views", None):
                                report_id_on.fist_quartile_view = row.get("1st Quartile Views", 0)

                            if row.get("Midpoint Views", None):
                                report_id_on.second_quartile_view = row.get("Midpoint Views", 0)

                            if row.get("3rd Quartile Views", None):
                                report_id_on.third_quartile_view = row.get("3rd Quartile Views", 0)

                            report_id_on.save()
                        else:
                            video_start = 0
                            video_end = 0
                            fist_quartile_view = 0
                            second_quartile_view = 0
                            third_quartile_view = 0
                            viewable_impression = 0
                            measurable_impression = 0

                            if row.get("Viewable Impressions", 0):
                                viewable_impression = row.get("Viewable Impressions", 0)
                            if row.get("Measurable Impressions", 0):
                                measurable_impression = row.get("Measurable Impressions", 0)

                            if row.get("Start Views", None):
                                video_start = row.get("Start Views", 0)

                            if row.get("Complete Views", None):
                                video_end = row.get("Complete Views", 0)

                            if row.get("1st Quartile Views", None):
                                fist_quartile_view = row.get("1st Quartile Views", 0)

                            if row.get("Midpoint Views", None):
                                second_quartile_view = row.get("Midpoint Views", 0)

                            if row.get("3rd Quartile Views", None):
                                third_quartile_view = row.get("3rd Quartile Views", 0)

                            models.ReportingIdReports.objects.create(report_on=report_on,
                                                                     reporting=report_id,
                                                                     impression=row['Billable Impressions'],
                                                                     clicks=row['Clicks'],
                                                                     budget=budget,
                                                                     media_cost=media_cost,
                                                                     viewable_impression=viewable_impression,
                                                                     measurable_impression=measurable_impression,
                                                                     video_start=video_start,
                                                                     video_end=video_end,
                                                                     fist_quartile_view=fist_quartile_view,
                                                                     second_quartile_view=second_quartile_view,
                                                                     third_quartile_view=third_quartile_view,
                                                                     )

                        line_item_obj = get_object_or_None(models.LineItemsReports, line_item=line_item,
                                                           report_on=report_on)
                        if line_item_obj:
                            report = line_item.report_ids.filter(reporting__report_on=report_on).aggregate(
                                impression=Sum('reporting__impression'), clicks=Sum('reporting__clicks'),
                                viewable_impression=Sum('reporting__viewable_impression'),
                                video_start=Sum('reporting__video_start'),
                                measurable_impression=Sum('reporting__measurable_impression'),
                                video_end=Sum('reporting__video_end'),
                                fist_quartile_view=Sum('reporting__fist_quartile_view'),
                                second_quartile_view=Sum('reporting__second_quartile_view'),
                                third_quartile_view=Sum('reporting__third_quartile_view'),
                                budget=Sum('reporting__budget'), media_cost=Sum('reporting__media_cost'))

                            line_item_obj.impression = round(report.get("impression", 0), 3)
                            line_item_obj.clicks = round(report.get("clicks", 0), 3)
                            line_item_obj.viewable_impression = round(report.get("viewable_impression", 0), 3)
                            line_item_obj.video_start = round(report.get("video_start", 0), 3)
                            line_item_obj.measurable_impression = round(report.get("measurable_impression", 0), 3)
                            line_item_obj.video_end = round(report.get("video_end", 0), 3)
                            line_item_obj.fist_quartile_view = round(report.get("fist_quartile_view", 0), 3)
                            line_item_obj.second_quartile_view = round(report.get("second_quartile_view", 0), 3)
                            line_item_obj.third_quartile_view = round(report.get("third_quartile_view", 0), 3)
                            line_item_obj.budget = round(report.get("budget", 0), 3)
                            line_item_obj.media_cost = round(report.get("media_cost", 0), 3)
                            line_item_obj.save()
                            models.LineItemsReports.objects.filter(id=line_item_obj.id).update(**report)
                        else:
                            report = line_item.report_ids.filter(reporting__report_on=report_on).aggregate(
                                impression=Sum('reporting__impression'), clicks=Sum('reporting__clicks'),
                                viewable_impression=Sum('reporting__viewable_impression'),
                                video_start=Sum('reporting__video_start'),
                                measurable_impression=Sum('reporting__measurable_impression'),
                                video_end=Sum('reporting__video_end'),
                                fist_quartile_view=Sum('reporting__fist_quartile_view'),
                                second_quartile_view=Sum('reporting__second_quartile_view'),
                                third_quartile_view=Sum('reporting__third_quartile_view'),
                                budget=Sum('reporting__budget'), media_cost=Sum('reporting__media_cost'))
                            models.LineItemsReports.objects.create(report_on=report_on, line_item=line_item, **report)
                    else:
                        error_report_count += 1
                        row_dict = row
                        row_dict['Upload Errors'] = ", ".join(excel_errors)
                        error_upload(row, error_header, mode="a")

            context.update({
                "upload_report_count": upload_report_count,
                "error_report_count": error_report_count
            })
    return render(request, template_name, context)

# Clients can raise a status change request for a line item (e.g., "Please pause this"). Saves to LineItemRequest table for the team to review.
@login_required
@csrf_exempt
def line_item_status_request(request, pk):
    """
    :param request: django request
    :param pk: line item id
    :return: line item object
    """

    if request.method == "POST":
        line_item = utils.int_to_io_details(pk)
        data = json.loads(request.body)
        LineItemRequest.objects.create(line_item=line_item, status=data['status'], reason=data['reason'])
        return JsonResponse({"error": "Invalid request method. Contact your developer"}, status=200)
    else:
        return JsonResponse({"error": "Invalid request method. Contact your developer"}, status=400)


# Compares each line item's actual CTR/viewability against the base_value targets in LineItemsPerformance:
class LineItemsPerformanceViews(generic.TemplateView):
    template_name = "line_items_performance.html"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.my_list = []

    def get_context_data(self, **kwargs):
        context = super(LineItemsPerformanceViews, self).get_context_data(**kwargs)
        context['title'] = 'Bulk Report Upload'
        self.request.current_app = 'Publisher_admin'
        context = admin_site.each_context(self.request)
        filter_dict = {}

        context['performance'] = "Over/under"

        context['categories'] = PerformanceCategory.objects.filter(is_active=True)
        selected_category = None
        if self.request.GET.get('category'):
            context['selected_categories'] = int_to_performance_category(int(self.request.GET.get('category')))
            selected_category = context['selected_categories']
            filter_dict['performance__categories'] = selected_category

        for line_item in IODetails.objects.filter(item_performance__isnull=False,
                                                  item_performance__category__category=selected_category).distinct():

            performance_list = {}
            for base in LineItemsPerformance.objects.filter():
                base_values = base.base_value
                if base.category.id in [1]:

                    archived = line_item.total_ctr()
                else:
                    archived = line_item.total_viewability()

                if archived > base_values:
                    is_under = False
                    performance = "{}".format("Over Performance")
                    percentage = round(((archived - base_values) / base_values) * 100, 2)
                else:
                    is_under = True
                    performance = "{}".format("Under Performance")
                    percentage = round(((base_values - archived) / base_values) * 100, 2)

                performance_list[base.category.id] = {
                    "category": base,
                    "performance": performance,
                    "target": base.base_value,
                    "archived": archived,
                    "is_under": is_under,
                    "percentage": percentage,
                }

            self.my_list.append({"object": line_item, "performance": performance_list})

        context['my_list'] = self.my_list

        return context
