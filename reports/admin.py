import datetime

from django.contrib import admin
from django.db.models import Sum
from django.utils.safestring import mark_safe

from categories.admin import admin_site
from insertion_order.models import IODetails

# Under Pacing Admin Panel View
class LineItemUnderPacing(IODetails):
    class Meta:
        proxy = True
        verbose_name = "Under Pacing Line Item"
        verbose_name_plural = "Over Pacing Line Items"


@admin.register(LineItemUnderPacing, site=admin_site)
class LineItemUnderPacingAdminInline(admin.ModelAdmin):
    list_display = ("item_id", "report_id", "description", "start_date", "end_date", "ad_type", "ad_metrics",
                    "unit_cost", "volume", "avg_ctr", "report_status")
    date_hierarchy = "end_date"

    fieldsets = [
        ('Basic Info', {'fields': (("description", "ethinicity", "ad_type", "end_date"),
                                   ("ad_metrics", "unit_cost", "volume"),
                                   ("net_cost",))}
         ),
    ]
    readonly_fields = ("description", "ethinicity", "start_date", "end_date", "ad_type", "ad_metrics", "unit_cost",
                       "volume", "net_cost")

    def get_queryset(self, request):
        qs = super(LineItemUnderPacingAdminInline, self).get_queryset(request)

        return qs.filter(end_date__gte=datetime.datetime.today().date()).order_by("-end_date")

    def report_status(self, obj):
        today = datetime.datetime.today()
        my_list = "<ul class=''>"

        remaining_days = (obj.end_date - today.date()).days
        remaining_days = remaining_days if remaining_days > 0 else 0
        remaining_impressions = obj.volume - obj.total_impression()
        try:
            daily_target = round(remaining_impressions / remaining_days)
        except ZeroDivisionError:
            daily_target = 0
        report = obj.reports.latest("report_on")
        if report:
            pct = round((daily_target - report.impression) * 100 / report.impression)
            if pct > 0 and pct > 10:
                return mark_safe("""<div class=" text-danger">{} Under {} ({}%)</div>""".format(daily_target,
                                                                                                report.impression,
                                                                                                pct))
        return mark_safe(my_list + "</ul>")
