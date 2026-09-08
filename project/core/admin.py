from django.contrib import admin
from .models import *


admin.site.register(CustomUser)
admin.site.register(Branch)
admin.site.register(Product)
admin.site.register(SaleInvoice)
admin.site.register(SaleInvoiceItem)
admin.site.register(PurchaseInvoice)
admin.site.register(PurchaseInvoiceItem)
admin.site.register(BranchInventory)
admin.site.register(BranchSalesDelivery)
admin.site.register(ProductExpiry)
admin.site.register(CompanySettings)
admin.site.register(Customer)
admin.site.register(ProductExpiryMovement)
admin.site.register(SupplierPayment)
admin.site.register(LoyaltyTransaction)
admin.site.register(PaymentMethod)
admin.site.register(Supplier)
admin.site.register(Category)
admin.site.register(LoyaltyTransfer)
admin.site.register(CustomerPayment)

@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    list_filter = ('branch',)

