from datetime import timedelta
from django.test import TestCase
from invoices import models

# Data Migration Script to update due dates for all existing invoices based on their company's payment terms. This can be run as a standalone script or integrated into a Django management command. It iterates through all invoices, checks the associated company's payment term, and updates the invoice's due date accordingly (e.g., if payment term is 30 days, it sets due date to invoice_to + 30 days). If no payment term is specified for the company, it defaults to adding 30 days to the invoice_to date.

def update_due_date(): 
    for invoice in models.Invoices.objects.all():
        if invoice.company.payment_term:
            invoice.due_date = invoice.invoice_to + timedelta(days=invoice.company.payment_term.days)
            invoice.save()
        else:
            invoice.due_date = invoice.invoice_to + timedelta(days=30)
            invoice.save()





