from django.contrib import admin
from django_summernote.admin import SummernoteModelAdmin

from categories.admin import admin_site
from clientrequests import models
from django.utils.safestring import mark_safe


class CampaignRequestImagesAdminInline(admin.StackedInline):
    model = models.CampaignRequestImages
    fields = ("image",)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.CampaignRequest, site=admin_site)
class CampaignRequestAdmin(SummernoteModelAdmin):
    list_display = ("id", "name", "contact_email", "created_on")
    fields = (("name", "contact_email"), "body_of_content_html", "created_on")
    readonly_fields = ("created_on", "body_of_content_html")
    inlines = [CampaignRequestImagesAdminInline]
    summernote_fields = ("body_of_content",)

    def get_queryset(self, request):
        qs = super(CampaignRequestAdmin, self).get_queryset(request)
        if request.user.groups.filter(name__in=["Clients"]):
            return qs.filter(created_by=request.user)
        return qs

    def get_fields(self, request, obj=None):
        if obj:
            return [("name", "contact_email"), "body_of_content_html", "created_on"]
        return [("name", "contact_email"), "body_of_content"]

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def body_of_content_html(self, obj):
        return mark_safe(obj.body_of_content)

    body_of_content_html.short_description = "Body of content"


@admin.register(models.LineItemRequest, site=admin_site)
class LineItemRequestAdmin(admin.ModelAdmin):
    list_display = ("created_on", "line_item_id", "line_item", "status", "reason")
    search_fields = ("line_item__item_id", "line_item__description")
    date_hierarchy = "created_on"
    list_filter = ("status",)

    def has_delete_permission(self, request, obj=None):
        return False

    def line_item_id(self, obj):
        return obj.line_item.item_id

    def get_queryset(self, request):
        qs = super(LineItemRequestAdmin, self).get_queryset(request)
        if request.user.groups.filter(name__in=["Clients"]):
            return qs.filter(line_item__io__sub_campaign__campaign__company__user=request.user)
        return qs

    line_item_id.short_description = "Line Item ID"
