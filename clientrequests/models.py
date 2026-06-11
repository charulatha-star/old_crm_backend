from django.contrib.auth.models import User
from django.db import models

from insertion_order.models import IODetails


class CampaignRequest(models.Model):
    objects = None
    name = models.CharField(max_length=120)
    body_of_content = models.TextField()
    contact_email = models.EmailField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    created_on = models.DateTimeField(auto_now_add=True, verbose_name="Request Date")
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tbl_campaign_request"


class CampaignRequestImages(models.Model):
    objects = None
    campaign_request = models.ForeignKey(CampaignRequest, on_delete=models.CASCADE)
    image = models.ImageField(upload_to="campaign-request")

    class Meta:
        db_table = "tbl_campaign_request_images"


class LineItemRequest(models.Model):
    objects = None
    line_item = models.ForeignKey(IODetails, on_delete=models.CASCADE, verbose_name="Line Item Name")
    status = models.CharField(max_length=30, verbose_name="Raise Status")
    reason = models.CharField(max_length=256)
    request_status = models.BooleanField(null=True, default=None)
    created_on = models.DateTimeField(auto_now_add=True, verbose_name="Request Date")
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tbl_line_status_request"
        verbose_name = "Line Item Request"
        verbose_name_plural = "Line Item Request"

    def __str__(self):
        return self.line_item.description
