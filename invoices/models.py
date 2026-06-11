from django.db import models
from django.db.models import Sum

from categories.models import Ethnicity, AdsFormats, Metrics, ModeOfPayment, InvoiceCompanyAddress, InvoiceBankDetails, \
    InvoiceAuthorizedPerson
from company_details.models import CompanyDetails, CompanyContacts
from insertion_order.models import Campaigns, IODetails

INVOICE_STATUS = (
    ("Not Paid", "Not Paid"),
    ("Partial Paid", "Partial Paid"),
    ("Paid", "Paid"),
)



class Invoices(models.Model):
    objects = None
    invoice_no = models.CharField(max_length=120, unique=True, verbose_name="Invoice Number")   # "BTU2600001" - auto-generated
    company = models.ForeignKey(CompanyDetails, on_delete=models.CASCADE)   # which client
    from_company_address = models.ForeignKey(InvoiceCompanyAddress, blank=True, null=True, on_delete=models.CASCADE)  # Billiontags address
    from_company_bank = models.ForeignKey(InvoiceBankDetails, blank=True, null=True, on_delete=models.CASCADE)  # bank details
    authorized_person = models.ForeignKey(InvoiceAuthorizedPerson, blank=True, null=True, on_delete=models.CASCADE)   # who signs
    contact_person = models.ForeignKey(CompanyContacts, on_delete=models.CASCADE)  # who to bill
    total_amount = models.FloatField(default=0.0) # raw total amount before discount and tax
    due_date = models.DateField()  # payment due date
    additional_discount = models.PositiveIntegerField(default=0.0, verbose_name="Offers or Discount")  # discount given
    vat_tax = models.PositiveIntegerField(default=0.0, verbose_name="VAT %", blank=True, null=True,)   # VAT % (e.g. 5%)
    gst = models.PositiveIntegerField(verbose_name="GST %", blank=True, null=True)   # GST % (e.g. 18%)
    total_discount = models.FloatField(verbose_name="Bill Adjustment", default=0.0)
    billing_amount = models.FloatField(default=0.0)  # after GST/VAT
    vat_tax_amount = models.FloatField(default=0.0)
    gst_amount = models.FloatField(default=0.0)
    invoice_on = models.DateField(verbose_name="Invoice Date")  # invoice date e.g. June 1
    invoice_from = models.DateField()    # billing period start e.g. June 1
    invoice_to = models.DateField()  # billing period end e.g. June 30
    is_approved = models.BooleanField(default=False, verbose_name="Manager Approved")
    status = models.CharField(max_length=20, choices=INVOICE_STATUS, default="Not Paid", verbose_name="Payment Status")
    campaigns = models.ManyToManyField(Campaigns, related_name="invoiced_campaign") # which campaigns invoiced 
    created_on = models.DateField(auto_now_add=True, verbose_name="Invoice Date")
    updated_on = models.DateField(auto_now=True)

    class Meta:
        db_table = "tbl_invoice"
        verbose_name = "Invoice"
        verbose_name_plural = "Invoice"

    def __str__(self):
        return self.invoice_no

    def total_pay_amount(self):
        # billing_amount - discount  --> 53000 - 1000 = 52000 total amount payable by client
        return round(self.billing_amount - self.additional_discount, 2)

    def total_line_items(self):
        # sum of all line item net costs
        net_cost = self.line_items.all().aggregate(net_cost=Sum('net_cost'))['net_cost']
        if net_cost:
            return round(net_cost, 2)  # Example: 50000
        return 0

    def total_volume(self):
        volume = self.line_items.all().aggregate(volume=Sum('volume'))['volume']
        if volume:
            return round(volume, 2)
        return 0

    def additional_discount_per(self):
        if self.additional_discount:
            return round((self.additional_discount / self.billing_amount) * 100, 2)
        return 0

    def total_paid(self):
         # total payments received so far
        return self.payment_history.aggregate(amount=Sum("amount"))['amount']

    def balance_amount(self):
        # how much client still owes
        amount = self.payment_history.aggregate(amount=Sum("amount"))['amount']
        if not amount:
            amount = 0
        return round(self.total_pay_amount() - amount, 2)
     # Example: 52000 - 25000 = 27000 remaining

    def total_billing_cost(self):
        billing_cost = self.line_items.all().aggregate(billing_cost=Sum('billing_cost'))['billing_cost']
        if billing_cost:
            return round(billing_cost, 2)
        return 0

    total_billing_cost.short_description = "Total Billing Cost"
    total_pay_amount.short_description = "Bill Amount"
    additional_discount_per.short_description = "Discount %"
    total_paid.short_description = "Total Paid Amount"


class OtherCharges(models.Model):
    objects = None
    invoice = models.ForeignKey(Invoices, on_delete=models.CASCADE, related_name="other_charges")
    title = models.CharField(max_length=60)
    amount = models.FloatField()

    class Meta:
        db_table = "tbl_invoice_other_charges"
        verbose_name = "Other Charge"
        verbose_name_plural = "Other Charges"

    def __str__(self):
        return self.title


class ServiceCharges(models.Model):
    objects = None
    invoice = models.ForeignKey(Invoices, on_delete=models.CASCADE)
    title = models.CharField(max_length=60)
    amount = models.FloatField()

    class Meta:
        db_table = "tbl_invoice_services_charges"
        verbose_name = "Services Charge"
        verbose_name_plural = "Services Charges"

    def __str__(self):
        return self.title

# Invoice Line Items - each line item corresponds to one IODetails (insertion order line item) and contains billing details for that line item
class BillingLineItems(models.Model):
    objects = None
    invoice = models.ForeignKey(Invoices, on_delete=models.CASCADE, related_name="line_items")
    line_item = models.ForeignKey(IODetails, on_delete=models.CASCADE, )   # which campaign line item
    description = models.CharField(max_length=120, )
    ethinicity = models.ForeignKey(Ethnicity, on_delete=models.CASCADE)
    start_date = models.DateField(verbose_name="Billing Start Date")
    end_date = models.DateField(verbose_name="Billing End Date")
    ad_type = models.ForeignKey(AdsFormats, on_delete=models.CASCADE)
    ad_metrics = models.ForeignKey(Metrics, on_delete=models.CASCADE)
    unit_cost = models.FloatField()
    volume = models.IntegerField()
    net_cost = models.FloatField()  # volume/1000 * unit_cost
    billing_cost = models.FloatField()  # after discount
    discount = models.FloatField(default=0.0)

    class Meta:
        db_table = "tbl_invoice_line_item"
        verbose_name_plural = "Line Items"
        unique_together = ("invoice", "line_item", "description")

    def __str__(self):
        return self.description


# Payment history for each invoice - multiple payments can be made for one invoice, e.g. partial payment, payment through different modes etc. This table captures all payment transactions related to an invoice.
class PaymentHistory(models.Model):
    objects = None
    invoice = models.ForeignKey(Invoices, on_delete=models.CASCADE, related_name="payment_history")
    mode_of_payment = models.ForeignKey(ModeOfPayment, on_delete=models.CASCADE)   # Bank Transfer, Cheque etc
    amount = models.FloatField()
    date = models.DateField(verbose_name="Transaction Date")
    additional_info = models.CharField(max_length=120, blank=True, null=True)  # "NEFT REF: 12345"
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tbl_payment_history"
        verbose_name = "Payment History"
        verbose_name_plural = "Payment History"
        ordering = ("-created_on",)

    def __str__(self):
        return "{} {} {}".format(self.invoice, self.mode_of_payment, self.amount)
