from django.contrib import admin
from .models import *


admin.site.register(CustomUser)
admin.site.register(Branch)
admin.site.register(Product)
admin.site.register(SaleInvoice)
admin.site.register(SaleInvoiceItem)
admin.site.register(PurchaseInvoice)
admin.site.register(PurchaseInvoiceItem)
