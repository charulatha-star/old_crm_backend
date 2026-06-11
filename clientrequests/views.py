from threading import Thread

from django.urls import reverse_lazy

from django.views import generic

from categories.utils import SendEmailViewMixin
from clientrequests import models
from clientrequests.forms import CampaignRequestForm


class CampaignRequestView(generic.CreateView, SendEmailViewMixin):
    """
    use this endpoint do create campaign requests
    """
    model = models.CampaignRequest
    form_class = CampaignRequestForm
    success_url = reverse_lazy('campaign_request_success')

    def form_valid(self, form):
        campaign_request = super().form_valid(form)
        self.html_body_template_name = "email/campaign_request_client.html"
        self.subject_template_name = "email/campaign_request_client_subject.txt"
        Thread(target=self.send_email, args=("jegacse92@gmail.com", {"request": self.object},)).start()

        return campaign_request


class CampaignRequestSuccessView(generic.TemplateView):
    """
    use this endpoint do render campaign success page
    """
    template_name = "clientrequests/success.html"
