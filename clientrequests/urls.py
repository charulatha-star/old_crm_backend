from django.urls import path

from . import views

urlpatterns = [
    path("campaign/", views.CampaignRequestView.as_view(),
         name="campaign_request_api"),
    path("campaign/success/", views.CampaignRequestSuccessView.as_view(),
         name="campaign_request_success"),
]
