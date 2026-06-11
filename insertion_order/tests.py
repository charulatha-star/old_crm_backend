from django.test import TestCase

# Create your tests here.
from insertion_order import models


def create_campaign():
    for io in models.InsertionOrders.objects.all():
        campaign, created = models.Campaigns.objects.get_or_create(name=io.name, defaults={
            "name": io.name,
            "company": io.company,
            "start_date": io.start_date,
            "end_date": io.end_date,
            "status": "Active",
            "payment_type": io.payment_type,
            "payment_term": io.payment_term})
        io.campaign = campaign
        io.save()
