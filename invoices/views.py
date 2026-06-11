import calendar
from datetime import datetime, timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import render, redirect
from django.utils.decorators import method_decorator
from easy_pdf.views import PDFTemplateView

from invoices import utils

# Version 1 — Old HTML view (just renders template)
def generate_invoice(request, pk):
    data = dict()

    invoice = utils.int_to_invoice(pk)
    today = invoice.invoice_on

    data['invoice'] = invoice
    last_day = calendar.monthrange(today.year, today.month)[1]
    data['last_date'] = datetime(year=today.year, month=today.month, day=last_day)

    data['first_date'] = datetime(year=today.year, month=today.month, day=1)

    return render(request, "invoice_template.html", data)


# PDF Download (staff only) — uses easy_pdf library to render the same template as a PDF. This is the view linked to the "Download Invoice" button in the admin list display and change form.
@method_decorator(staff_member_required, name='dispatch')
class GenerateInvoiceView(PDFTemplateView, ):
    template_name = "invoice_template.html"

    def get(self, request, *args, **kwargs):
        response = super(GenerateInvoiceView, self).get(request, *args, **kwargs)
        if not self.request.user.has_perm('invoices.view_invoices'):
            return HttpResponseRedirect("/")
        return response

    def get_context_data(self, **kwargs):
        invoice = utils.int_to_invoice(self.kwargs['pk'])
        utils.invoice_amount_calculation(invoice)

        show_po = False
        for campaign in invoice.campaigns.all():
            if campaign.purchase_order_no:
                show_po = True
                break

        return super(GenerateInvoiceView, self).get_context_data(
            pagesize='A4',
            filename="{}.pdf".format(invoice, invoice),
            title='{}'.format(invoice),
            invoice=invoice,
            show_po=show_po,
            **kwargs)


# Version 3 — PDF download (alternate template)
class GenerateInvoice2View(PDFTemplateView):
    template_name = "invoice_template2.html"

    def get_context_data(self, **kwargs):
        invoice = utils.int_to_invoice(self.kwargs['pk'])
        utils.invoice_amount_calculation(invoice)

        return super(GenerateInvoice2View, self).get_context_data(
            pagesize='A4',
            filename="{}.pdf".format(invoice, invoice),
            title='{}'.format(invoice),
            invoice=invoice,
            **kwargs)


class AppointmentLetterPdfView(PDFTemplateView):
    template_name = "appointment_letter_pdf.html"

    def get_context_data(self, **kwargs):
        return super(AppointmentLetterPdfView, self).get_context_data(
            pagesize='A4',
            **kwargs)
