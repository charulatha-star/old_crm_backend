
# utils.py - this file contains invoice amount calculation engine.

from annoying.functions import get_object_or_None
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models import Sum, Max

from insertion_order.models import IODetails
from invoices import models


def int_to_invoice(pk):
    try:
        return models.Invoices.objects.get(pk=pk)
    except ObjectDoesNotExist:
        raise ValidationError("Invalid ID")


def perform_operation(queryset, new_set):
    old_set = set(queryset)
    new_set = set(new_set)

    deleted_set = old_set.difference(new_set)
    added_set = new_set.difference(old_set)

    return deleted_set, added_set


def metrics_amount_calculation(line_item, volume=0):
    volume = 0 if volume is None else volume
    if line_item.ad_metrics.id == 1:
        net_cost = round((volume / 1000) * line_item.unit_cost, 2)
    else:
        net_cost = round(volume * line_item.unit_cost, 2)
    return net_cost


def invoice_amount_calculation(invoice, deleted_set=None):
    total_discount = 0
    total_amount = 0
    total_billing_amount = 0

    old_line_items = models.BillingLineItems.objects.filter(invoice=invoice)
    # Get all line items that are relevant for the invoice based on the campaigns linked to the invoice 
    # and the invoice month. This is used to determine which line items to add, update or delete when invoice details are updated (e.g. if campaign is removed from invoice, or if line item metrics have changed such that it no longer falls within the invoice month)
    line_items = IODetails.objects.filter(io__sub_campaign__campaign__in=invoice.campaigns.all(),
                                          reports__report_on__year=invoice.invoice_on.year,
                                          reports__report_on__month=invoice.invoice_on.month).distinct() # Only line items that have reports in June 2026 

    new_line_items = models.BillingLineItems.objects.filter(invoice=invoice, line_item__in=line_items)
    deleted_set, added_set = perform_operation(old_line_items, new_line_items)
    
    # Delete line items that are no longer relevant (e.g. if campaign is removed from invoice, or if line item metrics have changed such that it no longer falls within the invoice month)
    if deleted_set:
        for line_item in deleted_set:
            line_item.delete()

    for campaign in invoice.campaigns.all():

        line_items = IODetails.objects.filter(io__sub_campaign__campaign=campaign,
                                              reports__report_on__year=invoice.invoice_on.year,
                                              reports__report_on__month=invoice.invoice_on.month).distinct()

        for line_item in line_items:
            discount = 0

            report_dict = dict()
            if line_item.ad_metrics.id in [1, 3]:
                volume = line_item.reports.filter(report_on__month=invoice.invoice_on.month,
                                                  report_on__year=invoice.invoice_on.year).aggregate(
                    impression=Sum('impression'))['impression']
                net_cost = metrics_amount_calculation(line_item, volume)
                previous_volume = line_item.reports.exclude(report_on__gte=invoice.invoice_from).aggregate(
                    impression=Sum('impression'))['impression']
                previous_spent = metrics_amount_calculation(line_item, previous_volume)

            else: 
                # calculate volume for each line item 

                volume = line_item.reports.filter(report_on__month=invoice.invoice_on.month,
                                                  report_on__year=invoice.invoice_on.year).aggregate(
                    clicks=Sum('clicks'))['clicks']
                net_cost = metrics_amount_calculation(line_item, volume)
                previous_volume = line_item.reports.exclude(report_on__gte=invoice.invoice_from).aggregate(
                    clicks=Sum('clicks'))['clicks']
                
                # previous month spend
                previous_spent = metrics_amount_calculation(line_item, previous_volume)

            report = get_object_or_None(models.BillingLineItems, description=line_item.description, invoice=invoice,
                                        line_item=line_item)

            # this month + previous month total
            overall_spent = round(net_cost + previous_spent, 2)

            # If total spent > booked amount for the line item, then give discount such that billing cost = total spent (but discount cannot exceed net cost)
            if overall_spent > round(line_item.net_cost, 2):
                discount = round(overall_spent, 2) - round(line_item.net_cost, 2)
       
           # Discount can't be more than this month cost
            if net_cost < discount:
                discount = net_cost

            billing_cost = round(net_cost - discount, 2)
            total_billing_amount += billing_cost
            total_amount += net_cost

            report_dict['invoice'] = invoice
            report_dict['description'] = line_item.description
            report_dict['line_item'] = line_item
            report_dict['ethinicity'] = line_item.ethinicity
            report_dict['start_date'] = line_item.start_date
            report_dict['end_date'] = line_item.end_date
            report_dict['ad_type'] = line_item.ad_type
            report_dict['ad_metrics'] = line_item.ad_metrics
            report_dict['unit_cost'] = line_item.unit_cost
            report_dict['volume'] = volume
            report_dict['net_cost'] = net_cost
            report_dict['billing_cost'] = billing_cost
            report_dict['discount'] = round(discount, 2)

            if report:
                report_dict.pop("invoice")
                report_dict.pop("line_item")
                report.__dict__.update(**report_dict)
            else:
                report = models.BillingLineItems.objects.create(**report_dict)
            report.save()
            total_discount += discount

    invoice.total_discount = round(total_discount, 2)
    invoice.total_amount = round(total_amount, 2)

    # Calculate GST and VAT tax amounts based on the total billing amount after discount. 
    if invoice.vat_tax:
        invoice.vat_tax_amount = round(((total_billing_amount/100)*invoice.vat_tax), 2)

    if invoice.gst:
        invoice.gst_amount = round(((total_billing_amount/100)*invoice.gst), 2)    # ₹48,000 * 18% = ₹8,640

    invoice.billing_amount = round(invoice.gst_amount + invoice.vat_tax_amount + total_billing_amount, 2)   # ₹48,000 + ₹8,640 = ₹56,640 final invoice amount
    invoice.save()
    return
