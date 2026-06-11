from django import forms

from clientrequests import models
from django_summernote.widgets import SummernoteWidget


class CampaignRequestForm(forms.ModelForm):
    image = forms.ImageField(widget=forms.FileInput(attrs={'multiple': True}), required=False, label="File Attachment")

    class Meta:
        model = models.CampaignRequest
        fields = ('name', 'contact_email', 'body_of_content', "image")
        widgets = {
            'body_of_content': SummernoteWidget(attrs={'summernote': {'width': '100%', 'height': '400px'}}),
        }


