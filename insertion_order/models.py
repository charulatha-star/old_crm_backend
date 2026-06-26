from datetime import datetime

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import Sum

from categories.models import PaymentTerms, AdsFormats, Metrics, Ethnicity, PerformanceCategory, PerformanceSubCategory
from categories.models import PaymentTerms, AdsFormats, Metrics, Ethnicity, MediaTypeSubCategory
from company_details.models import CompanyDetails, CompanyContacts

PAYMENT_TERM = (
    ("Pre Payment", "Pre Payment"),
    ("Post Payment", "Post Payment"),
)

CAMPAIGN_STATUS = (
    ("Scheduled", "Scheduled"),
    ("Live", "Live"),
    ("Paused", "Paused"),
    ("Completed", "Completed"),
    ("Stopped", "Stopped"),
)


class Campaigns(models.Model):
    objects = None
    campaign_id = models.CharField(max_length=30, blank=True, null=True, verbose_name="Campaign ID")
    report_id = models.CharField(max_length=60, blank=True, null=True, verbose_name="Reporting ID")
    name = models.CharField(max_length=120, verbose_name="Campaign Name")
    company = models.ForeignKey(CompanyDetails, on_delete=models.CASCADE, verbose_name="Client Name")
    work_order_no = models.CharField(max_length=30, blank=True, null=True, verbose_name="Client Campaign ID")
    purchase_order_no = models.CharField(max_length=30, blank=True, null=True, verbose_name="Purchase Order ID")
    start_date = models.DateField(verbose_name="Campaign Start Date")
    end_date = models.DateField(verbose_name="Campaign End Date")
    subagency = models.CharField(max_length=120, blank=True, null=True)
    website_url = models.URLField(blank=True, null=True)
    brand = models.CharField(max_length=120, blank=True, null=True)
    status = models.CharField(choices=CAMPAIGN_STATUS, max_length=20, verbose_name="Status")
    payment_type = models.CharField(max_length=50, choices=PAYMENT_TERM, blank=True, null=True)
    payment_term = models.ForeignKey(PaymentTerms, on_delete=models.CASCADE, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_on = models.DateField(auto_now_add=True)
    updated_on = models.DateField(auto_now=True)

    class Meta:
        db_table = "tbl_campaign"
        verbose_name = "Campaign"
        verbose_name_plural = "Campaign"

    def __str__(self):
        return self.name

    def total_volume(self):
        return self.sub_campaign.all().aggregate(volume=Sum('insertion_order__io_details__volume'))['volume']  # sum of all booked impressions across sub-campaigns

    def total_cost(self):
        value_cost = self.sub_campaign.all().aggregate(net_cost=Sum('insertion_order__io_details__net_cost'))[
            'net_cost']
        return "{} {}".format(self.company.billing_currency.iso_code_3, round(value_cost) if value_cost else 0)  # total net cost with currency symbol

    def total_impression(self):
        impression = \
            self.sub_campaign.all().aggregate(impression=Sum('insertion_order__io_details__reports__impression'))[
                'impression']
        return impression if impression else 0     # sum of all delivered impressions

    def total_clicks(self):
        clicks = self.sub_campaign.all().aggregate(clicks=Sum('insertion_order__io_details__reports__clicks'))['clicks']
        return clicks if clicks else 0

    def remaining_volumes(self):
        booked_volumes = self.sub_campaign.all().aggregate(volume=Sum('insertion_order__io_details__volume'))['volume']
        delivered_volumes = \
            self.sub_campaign.all().aggregate(volume=Sum('insertion_order__io_details__reports__impression'))['volume']
        booked_volumes = booked_volumes if booked_volumes else 0
        delivered_volumes = delivered_volumes if delivered_volumes else 0
        return booked_volumes - delivered_volumes # booked - delivered

    def get_campaign_id(self):
        if not self.campaign_id:
            self.campaign_id = "CA{:05d}".format(self.id)       # auto-generates "CA00001" if not set
            self.save()
            return self.campaign_id
        return self.campaign_id

    total_volume.short_description = "Total Volumes Booked"
    total_cost.short_description = "Total Cost"
    total_impression.short_description = "Total Volumes Delivered"
    remaining_volumes.short_description = "Remaining Volumes"
    total_clicks.short_description = "Total Clicks Delivered"
    get_campaign_id.short_description = "Campaign ID"

    # Add this line today(8/6/26)
    #get_campaign_id.short_description = "Campaign ID"



class SubCampaign(models.Model):
    objects = None
    campaign = models.ForeignKey(Campaigns, on_delete=models.CASCADE, related_name="sub_campaign",
                                 verbose_name="Campaign Name")
    booking_id = models.CharField(max_length=20, unique=True, verbose_name="Sub Campaign ID")  # auto-generated in save()
    report_id = models.CharField(max_length=60, blank=True, null=True, verbose_name="Reporting ID")
    name = models.CharField(max_length=120, verbose_name="Sub Campaign Name")
    start_date = models.DateField(verbose_name="Start Date")
    end_date = models.DateField(verbose_name="End Date")
    status = models.CharField(choices=CAMPAIGN_STATUS, max_length=20, verbose_name="Sub Campaign Status")
    is_active = models.BooleanField(default=True)
    created_on = models.DateField(auto_now_add=True)
    updated_on = models.DateField(auto_now=True)

    class Meta:
        db_table = "tbl_sub_campaigns"
        verbose_name = "Sub Campaign"
        verbose_name_plural = "Sub Campaigns"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if hasattr(self, "id") and self.id:
            my_id = self.id
        else:
            try:
                my_id = SubCampaign.objects.latest('id').id
            except ObjectDoesNotExist:
                my_id = 0
            my_id += 1
        self.booking_id = "SB{:05d}".format(my_id)
        super(SubCampaign, self).save(*args, **kwargs)

    def total_volume_booked(self):
        return self.insertion_order.aggregate(volume=Sum('io_details__volume'))['volume']

    def total_volume_delivered(self):
        return self.insertion_order.aggregate(volume=Sum('io_details__reports__impression'))['volume']

    def total_budget(self):
        value_cost = self.insertion_order.all().aggregate(net_cost=Sum('io_details__net_cost'))['net_cost']
        return round(value_cost, 2) if value_cost else 0

    def budget_spend(self):
        total_budget = 0
        for io in self.insertion_order.all():
            for line_item in io.io_details.all():
                delivered_volumes = line_item.reports.aggregate(volume=Sum('impression'))['volume']
                delivered_volumes = delivered_volumes if delivered_volumes else 0
                total_budget += delivered_volumes / 1000 * line_item.unit_cost

        return round(total_budget, 2)

    def remaining_volumes(self):
        booked_volumes = self.insertion_order.aggregate(volume=Sum('io_details__volume'))['volume']
        delivered_volumes = self.insertion_order.aggregate(volume=Sum('io_details__reports__impression'))['volume']
        booked_volumes = booked_volumes if booked_volumes else 0
        delivered_volumes = delivered_volumes if delivered_volumes else 0
        return booked_volumes - delivered_volumes

    remaining_volumes.short_description = "Remaining Volume"
    total_budget.short_description = "Total Budget Booked"


class InsertionOrders(models.Model):
    objects = None
    campaign = models.ForeignKey(Campaigns, on_delete=models.CASCADE, related_name="insertion_order", blank=True,
                                 null=True)
    sub_campaign = models.ForeignKey(SubCampaign, on_delete=models.CASCADE, related_name="insertion_order")
    order_id = models.CharField(max_length=25, unique=True, verbose_name="IO ID")  # BT + D(domestic)/I(international) + year + count
    report_id = models.CharField(max_length=60, blank=True, null=True, verbose_name="Reporting ID")
    name = models.CharField(max_length=120, verbose_name="IO Name")
    work_order_no = models.CharField(max_length=30, blank=True, null=True, verbose_name="Client Campaign ID")
    contact_person = models.ForeignKey(CompanyContacts, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    to_email = models.EmailField(blank=True, null=True)
    geo = models.CharField(blank=True, null=True, max_length=256)
    payment_type = models.CharField(max_length=50, choices=PAYMENT_TERM, blank=True, null=True)
    payment_term = models.ForeignKey(PaymentTerms, on_delete=models.CASCADE, blank=True, null=True)
    order_taken_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Created By")
    io_file = models.FileField(blank=True, null=True)
    signed_io = models.FileField(blank=True, null=True, verbose_name="Signed IO")
    status = models.CharField(choices=CAMPAIGN_STATUS, max_length=20, verbose_name="Status")
    created_on = models.DateTimeField(auto_now_add=True, verbose_name="IO Date")
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tbl_insertion_order"
        verbose_name = "Insertion Order"
        verbose_name_plural = "Insertion Orders"

    def __str__(self):
        return self.order_id

    def save(self, *args, **kwargs):
        if not self.order_id:
            order_format = "BT{}{}".format("D" if self.sub_campaign.campaign.company.is_domestic else "I",
                                           datetime.now().strftime("%y"))
            order_count = InsertionOrders.objects.filter(order_id__icontains=order_format).count()
            self.order_id = "{}{:05d}".format(order_format, order_count + 1 if order_count else 1)
        super(InsertionOrders, self).save(*args, **kwargs)

    def total_impressions(self):
        return self.io_details.all().aggregate(volume=Sum('volume'))['volume']

    def total_cost(self):
        value_cost = self.io_details.all().aggregate(net_cost=Sum('net_cost'))['net_cost']
        return "{} {}".format(self.sub_campaign.campaign.company.billing_currency.currency_symbols,
                              round(value_cost) if value_cost else 0)

    def total_impression(self):
        impression = self.io_details.all().aggregate(impression=Sum('reports__impression'))['impression']
        return impression if impression else 0

    def remaining_volumes(self):
        booked_volume = self.io_details.all().aggregate(volume=Sum('volume'))['volume']
        delivery_volume = self.io_details.all().aggregate(impression=Sum('reports__impression'))['impression']
        booked_volume = booked_volume if booked_volume else 0
        delivery_volume = delivery_volume if delivery_volume else 0
        return booked_volume - delivery_volume

    def total_clicks(self):
        clicks = self.io_details.all().aggregate(clicks=Sum('reports__clicks'))['clicks']
        return clicks if clicks else 0

    def booking_id(self):
        if self.id:
            return "BI{:05d}".format(self.id)
        return "-"

    def io_id(self):
        if self.id:
            return "IO{:05d}".format(self.id)
        return "-"

    io_id.short_description = "IO ID"
    total_cost.short_description = "Total Cost"
    total_impressions.short_description = "Total Volumes"
    total_impression.short_description = "Total Impression"
    total_clicks.short_description = "Total Clicks"


class IODetails(models.Model):
    objects = None
    io = models.ForeignKey(InsertionOrders, on_delete=models.CASCADE, related_name="io_details")
    category = models.ForeignKey(MediaTypeSubCategory, on_delete=models.CASCADE, blank=True, null=True)
    item_id = models.CharField(max_length=60, verbose_name="Line Item ID")   # auto-generated
    report_id = models.CharField(max_length=60, blank=True, null=True, verbose_name="Reporting ID")
    description = models.CharField(max_length=120, verbose_name="Line Item Name")
    ethinicity = models.ForeignKey(Ethnicity, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    ad_type = models.ForeignKey(AdsFormats, on_delete=models.CASCADE, verbose_name="Ad Format")
    ad_metrics = models.ForeignKey(Metrics, on_delete=models.CASCADE, verbose_name="Units")
    unit_cost = models.FloatField()
    volume = models.IntegerField()
    avg_ctr = models.FloatField(verbose_name="Average CTR")
    net_cost = models.FloatField()
    status = models.CharField(choices=CAMPAIGN_STATUS, max_length=20)

    class Meta:
        db_table = "tbl_io_details"
        verbose_name_plural = "Booking Details"
        verbose_name = "Booking Detail"
        unique_together = ("io", "description")
        ordering = ("id",)

    def __str__(self):
        return self.description

    def save(self, *args, **kwargs):
        if hasattr(self, "id") and self.id:
            my_id = self.id
        else:
            my_id = IODetails.objects.latest('id').id
            my_id += 1
        self.item_id = "LI{:05d}".format(my_id)
        super(IODetails, self).save(*args, **kwargs)

    def total_impression(self):       # sum of all daily impression reports
        impression = self.reports.all().aggregate(impression=Sum('impression'))['impression']
        return impression if impression else 0

    def total_clicks(self):    # sum of all daily click reports
        clicks = self.reports.all().aggregate(clicks=Sum('clicks'))['clicks']
        return clicks if clicks else 0

    def total_ctr(self):     # (clicks/impressions) * 100
        report = self.reports.all().aggregate(impression=Sum('impression'), clicks=Sum('clicks'))
        clicks = report["clicks"] if report["clicks"] else 0
        impression = report["impression"] if report["impression"] else 0
        try:
            return round((clicks / impression) * 100, 2)
        except:
            return 0

    def total_viewability(self):        # (viewable/measurable) * 100
        report = self.reports.all().aggregate(viewable_impression=Sum('viewable_impression'),
                                              measurable_impression=Sum('measurable_impression'))
        measurable_impression = report["measurable_impression"] if report["measurable_impression"] else 0
        viewable_impression = report["viewable_impression"] if report["viewable_impression"] else 0
        try:
            return round((viewable_impression / measurable_impression) * 100)
        except:
            return 0

    @property
    def total_budget(self):
        delivered_volumes = self.reports.aggregate(volume=Sum('impression'))['volume']
        delivered_volumes = delivered_volumes if delivered_volumes else 0

        # actual spend = (delivered impressions / 1000) * unit_cost
        budget = (delivered_volumes / 1000) * self.unit_cost
        return budget

    total_impression.short_description = "Total Impression"
    total_clicks.short_description = "Total Clicks"


class EmailCCContent(models.Model):
    io = models.ForeignKey(InsertionOrders, on_delete=models.CASCADE)
    cc_email = models.EmailField()

    class Meta:
        db_table = "tbl_io_cc_details"
        verbose_name = "CC Email"
        verbose_name_plural = "CC Emails"

    def __str__(self):
        return self.cc_email


class LineItemReportingID(models.Model):
    objects = None
    line_item = models.ForeignKey(IODetails, on_delete=models.CASCADE, related_name="report_ids")
    report_id = models.CharField(max_length=60, verbose_name="Reporting ID")

    class Meta:
        db_table = "tbl_line_item_reports_id"
        verbose_name = "Line Items Report"
        verbose_name_plural = "Line Items Report"

    def __str__(self):
        return self.report_id


class ReportingIdReports(models.Model):
    objects = None
    reporting = models.ForeignKey(LineItemReportingID, on_delete=models.CASCADE, related_name="reporting")
    report_on = models.DateField()
    impression = models.PositiveIntegerField()
    clicks = models.PositiveIntegerField()
    viewable_impression = models.PositiveIntegerField(default=0)
    measurable_impression = models.PositiveIntegerField(default=0)
    video_start = models.PositiveIntegerField(default=0)
    video_end = models.PositiveIntegerField(default=0)
    fist_quartile_view = models.PositiveIntegerField(default=0, verbose_name="1st Quartile Views")
    second_quartile_view = models.PositiveIntegerField(default=0, verbose_name="Midpoint Views")
    third_quartile_view = models.PositiveIntegerField(default=0, verbose_name="3rd Quartile Views")
    budget = models.FloatField(default=0.0, verbose_name="Revenue (Adv Currency)")
    media_cost = models.FloatField(default=0.0, verbose_name="Media Cost (Advertiser Currency)")

    class Meta:
        db_table = "tbl_line_items_report_id_reports"
        verbose_name = "ReportId Report"
        verbose_name_plural = "ReportId Reports"
        ordering = ("report_on",)


class LineItemsReports(models.Model):
    objects = None
    line_item = models.ForeignKey(IODetails, on_delete=models.CASCADE, related_name="reports")
    report_on = models.DateField()
    impression = models.PositiveIntegerField()
    clicks = models.PositiveIntegerField()
    viewable_impression = models.PositiveIntegerField(default=0)
    measurable_impression = models.PositiveIntegerField(default=0)
    video_start = models.PositiveIntegerField(default=0)
    video_end = models.PositiveIntegerField(default=0)
    fist_quartile_view = models.PositiveIntegerField(default=0, verbose_name="1st Quartile Views")
    second_quartile_view = models.PositiveIntegerField(default=0, verbose_name="Midpoint Views")
    third_quartile_view = models.PositiveIntegerField(default=0, verbose_name="3rd Quartile Views")
    budget = models.FloatField(default=0.0, verbose_name="Revenue (Adv Currency)")
    media_cost = models.FloatField(default=0.0, verbose_name="Media Cost (Advertiser Currency)")
    created_on = models.DateField(auto_now_add=True)

    class Meta:
        db_table = "tbl_line_items_reports"
        verbose_name = "Report"
        verbose_name_plural = "Reports"
        ordering = ("report_on",)

    def __str__(self):
        return "{}".format(self.report_on.strftime("%d, %b %y, %a"))

    def ctr_calculation(self):
        return round((self.clicks / self.impression) * 100, 2)

    def viewability(self):
        try:
            return round((self.viewable_impression / self.measurable_impression) * 100)
        except:
            return 0

    def video_completion_rate(self):
        try:
            return round((self.video_end / self.video_start) * 100)
        except:
            return 0


class LineItemsPerformance(models.Model):
    objects = None
    category = models.ForeignKey(PerformanceSubCategory, on_delete=models.CASCADE, related_name="performance")
    line_item = models.ForeignKey(IODetails, on_delete=models.CASCADE, related_name="item_performance")
    priority = models.IntegerField()
    base_value = models.FloatField(blank=True, null=True)

    class Meta:
        db_table = "tbl_line_item_performance"
        verbose_name = "Line Item"



# Line Item Pause History model


# class LineItemPauseHistory(models.Model):
#     """
#     Client-requested pause periods for a line item.
#     Multiple pause periods allowed per line item.
    
#     Example:
#       LI09603 paused June 14 → June 16
#       LI09603 paused June 19 → June 19
#     """
#     line_item   = models.ForeignKey(
#         IODetails,
#         on_delete=models.CASCADE,
#         related_name="pause_history"
#     )
#     paused_from = models.DateField(verbose_name="Paused From")
#     paused_to   = models.DateField(verbose_name="Paused To")
#     reason      = models.CharField(
#         max_length=255,
#         blank=True,
#         null=True,
#         verbose_name="Reason"
#     )
#     created_on  = models.DateField(auto_now_add=True)

#     class Meta:
#         db_table = "tbl_line_item_pause_history"
#         verbose_name = "Pause Period"
#         verbose_name_plural = "Pause Periods"

#     def __str__(self):
#         return f"{self.line_item.item_id} | {self.paused_from} → {self.paused_to}"

#     def paused_days(self):
#         return (self.paused_to - self.paused_from).days + 1