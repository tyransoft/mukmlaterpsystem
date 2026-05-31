from decimal import Decimal
from xml.dom import ValidationErr

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.db.models import Sum



class Branch(models.Model):
    name = models.CharField(max_length=200, verbose_name='اسم الفرع')
    address = models.TextField(blank=True, verbose_name='العنوان')
    phone = models.CharField(max_length=20, blank=True, verbose_name='الهاتف')
    commission_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name='نسبة العمولة %'
    )
    is_main = models.BooleanField(default=False, verbose_name='الفرع الرئيسي')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'فرع'
        verbose_name_plural = 'الفروع'
        ordering = ['-is_main', 'name']

    def __str__(self):
        return f"{self.name} {'(رئيسي)' if self.is_main else ''}"

    def save(self, *args, **kwargs):
        if self.is_main:
            Branch.objects.exclude(pk=self.pk).update(is_main=False)
        super().save(*args, **kwargs)

    @classmethod
    def get_main_branch(cls):
        return cls.objects.filter(is_main=True).first()



    def get_commission_amount(self):
        total_sales = self.get_total_sales()
        return (total_sales * self.commission_percentage) / 100

    def get_inventory_value(self):
        from .models import BranchInventory
        from django.db.models import Sum, F, ExpressionWrapper, DecimalField
        result = BranchInventory.objects.filter(branch=self).aggregate(
            value=Sum(ExpressionWrapper(
                F('quantity') * F('product__cost_price'),
                output_field=DecimalField()
            ))
        )
        return result['value'] or 0

class Role(models.TextChoices):
    SUPER_ADMIN = 'super_admin', 'مدير النظام'
    ADMIN = 'admin', 'مدير'
    BRANCH_MANAGER = 'branch_manager', 'مدير فرع'
    BRANCH_EMPLOYEE = 'branch_employee', 'موظف فرع'
    ACCOUNTANT = 'accountant', 'محاسب'
    LOYALTY_EMPLOYEE = 'loyalty_employee', 'موظف نقاط الولاء'


class CustomUser(AbstractUser):
    role = models.CharField(max_length=30, choices=Role.choices, default=Role.BRANCH_EMPLOYEE, verbose_name='الدور')
    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employees',
        verbose_name='الفرع'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'مستخدم'
        verbose_name_plural = 'المستخدمون'

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    def is_main_admin(self):
        return self.role in [Role.SUPER_ADMIN, Role.ADMIN]

    def is_accountant(self):
        return self.role == Role.ACCOUNTANT

    def is_branch_staff(self):
        return self.role in [Role.BRANCH_MANAGER, Role.BRANCH_EMPLOYEE]

    def is_loyalty_employee(self):
        return self.role == Role.LOYALTY_EMPLOYEE

    def can_see_all_data(self):
        return self.role in [Role.SUPER_ADMIN, Role.ADMIN, Role.ACCOUNTANT]

    def can_modify_prices(self):
        return self.role in [Role.SUPER_ADMIN, Role.ADMIN]

    def can_create_sale_to_branch(self):
        return self.role in [Role.SUPER_ADMIN, Role.ADMIN, Role.BRANCH_MANAGER]
    
    def can_create_purchase(self):
        return self.role in [Role.SUPER_ADMIN, Role.ADMIN]
    
    def get_allowed_sale_types(self):
        if self.can_create_sale_to_branch():
            return ['customer', 'branch']
        return ['customer']    
    
    def get_accessible_branches(self):
        from .models import Branch
        if self.can_see_all_data():
            return Branch.objects.filter(is_active=True)
        elif self.branch:
            return Branch.objects.filter(pk=self.branch.pk)
        return Branch.objects.none()
    








class Customer(models.Model):
    full_name = models.CharField(max_length=200, verbose_name='الاسم الكامل')
    phone = models.CharField(max_length=20, unique=True, verbose_name='رقم الهاتف')
    address = models.TextField(blank=True, verbose_name='العنوان')
    loyalty_points = models.IntegerField(default=0, verbose_name='نقاط الولاء')
    debt_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='رصيد الدين'
    )
    created_by = models.ForeignKey(
        'core.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='أنشأ بواسطة'
    )
    created_branch = models.ForeignKey(
        Branch, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='فرع الإنشاء'
    )
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'عميل'
        verbose_name_plural = 'العملاء'
        ordering = ['full_name']

    def __str__(self):
        return f"{self.full_name} ({self.phone})"

    def get_total_purchases(self):
        from .models import Invoice
        result = Invoice.objects.filter(
            customer=self,
            invoice_type='sale',
            status__in=['confirmed', 'paid', 'partial']
        ).aggregate(total=Sum('total'))
        return result['total'] or 0

    def get_pending_loyalty_points(self):
        from .models import LoyaltyTransfer
        result = LoyaltyTransfer.objects.filter(
            customer=self, status='pending'
        ).aggregate(total=Sum('points'))
        return result['total'] or 0
    
    @property
    def total_debt(self):
        return self.debt_balance
    
    def get_debt_invoices(self):
        from .models import SaleInvoice
        return SaleInvoice.objects.filter(
            customer=self,
            sale_type='customer',
            status='confirmed',
            debt_amount__gt=0
        ).order_by('due_date')    


class CustomerPayment(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='المبلغ المسدد')
    payment_date = models.DateTimeField(default=timezone.now, verbose_name='تاريخ التسديد')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    receipt_number = models.CharField(max_length=50, unique=True, blank=True, verbose_name='رقم الإيصال')
    created_by = models.ForeignKey('core.CustomUser', on_delete=models.SET_NULL, null=True, verbose_name='تم بواسطة')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'تسديد دين عميل'
        verbose_name_plural = 'تسديدات ديون العملاء'
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"{self.customer.full_name} - {self.amount} - {self.payment_date}"
    
    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = self._generate_receipt_number()
        super().save(*args, **kwargs)
    
    def _generate_receipt_number(self):
        date_str = timezone.now().strftime('%Y%m%d')
        count = CustomerPayment.objects.filter(
            payment_date__date=timezone.now().date()
        ).count() + 1
        return f"{date_str}{count:04d}"




class BranchInventory(models.Model):
    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE,
        verbose_name='الفرع', related_name='inventory'
    )
    product = models.ForeignKey(
        'core.Product', on_delete=models.CASCADE,
        verbose_name='المنتج', related_name='branch_inventories'
    )

    quantity = models.IntegerField(default=0, verbose_name='الكمية')
    min_quantity = models.IntegerField(default=5, verbose_name='الحد الأدنى')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'مخزون الفرع'
        verbose_name_plural = 'مخزون الفروع'
        unique_together = ['branch', 'product']
        ordering = ['product__name']

    def __str__(self):
        return f"{self.branch.name} - {self.product.name}: {self.quantity}"

    @property
    def is_low_stock(self):
        return self.quantity <= self.min_quantity

    @property
    def stock_value(self):
        return self.quantity * self.product.cost_price




class LoyaltyTransfer(models.Model):
    STATUS_CHOICES = [
        ('pending', 'معلق'),
        ('transferred', 'تم التحويل'),
    ]
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='loyalty_transfers')
    sale_invoice = models.ForeignKey('core.SaleInvoice', on_delete=models.SET_NULL, null=True, blank=True, related_name='loyalty_transfers')
    points = models.IntegerField()
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    transferred_by = models.ForeignKey('core.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='handled_loyalty_transfers')
    transfer_date = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def mark_as_transferred(self, employee):
        self.status = 'transferred'
        self.transferred_by = employee
        self.transfer_date = timezone.now()
        self.save()
        self.customer.loyalty_points += self.points  
        self.customer.save()

class Category(models.Model):
    name = models.CharField(max_length=200, verbose_name='اسم الفئة')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'فئة'
        verbose_name_plural = 'الفئات'
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=200, verbose_name='اسم المنتج')

    barcode = models.CharField(max_length=100, blank=True, verbose_name='الباركود')
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='الفئة', related_name='products'
    )
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='سعر التكلفة')
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='سعر البيع')

    loyalty_points = models.IntegerField(default=0, verbose_name='نقاط الولاء لكل وحدة')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'منتج'
        verbose_name_plural = 'المنتجات'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.barcode})"

  

    def get_total_stock(self):
        from .models import BranchInventory
        from django.db.models import Sum
        result = BranchInventory.objects.filter(product=self).aggregate(total=Sum('quantity'))
        return result['total'] or 0

    def get_branch_stock(self, branch):
        from .models import BranchInventory
        try:
            inv = BranchInventory.objects.get(product=self, branch=branch)
            return inv.quantity
        except BranchInventory.DoesNotExist:
            return 0

    def update_cost_price(self, new_cost_price, new_quantity, branch=None):
      from .models import BranchInventory
    
      if branch is None:
        from .models import Branch
        branch = Branch.get_main_branch()
    
      try:
        current_inventory = BranchInventory.objects.get(branch=branch, product=self)
        current_quantity = current_inventory.quantity
        current_total_cost = current_quantity * self.cost_price
      except BranchInventory.DoesNotExist:
        current_quantity = 0
        current_total_cost = 0
    
      new_total_cost = new_quantity * new_cost_price
      total_quantity = current_quantity + new_quantity
    
      if total_quantity > 0:
        new_average_cost = (current_total_cost + new_total_cost) / total_quantity
        self.cost_price = round(new_average_cost, 2)
        self.save()
        return True
      return False

class InventoryMovement(models.Model):
    MOVEMENT_TYPES = [
        ('sale', 'مبيعات'),
        ('purchase', 'مشتريات'),
        ('supply_out', 'توريد صادر'),
        ('supply_in', 'توريد وارد'),
        ('adjustment', 'تعديل'),
    ]
    
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField()
    quantity_before = models.IntegerField(default=0)
    quantity_after = models.IntegerField(default=0)
    
    sale_invoice = models.ForeignKey('core.SaleInvoice', on_delete=models.SET_NULL, null=True, blank=True)
    purchase_invoice = models.ForeignKey('core.PurchaseInvoice', on_delete=models.SET_NULL, null=True, blank=True)
    
    notes = models.TextField(blank=True)
    employee = models.ForeignKey('core.CustomUser', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Supplier(models.Model):
    name = models.CharField(max_length=200, verbose_name='اسم المورد')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'مورد'
        verbose_name_plural = 'الموردين'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_total_purchases(self):
        from django.db.models import Sum
        result = PurchaseInvoice.objects.filter(
            supplier=self,
            status='confirmed'
        ).aggregate(total=Sum('total'))
        return result['total'] or 0


class PurchaseInvoice(models.Model):
    STATUS_CHOICES = [
        ('draft', 'مسودة'),
        ('confirmed', 'مؤكدة'),
        ('cancelled', 'ملغاة'),
    ]
    
    invoice_number = models.CharField(max_length=50, unique=True)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='purchase_invoices')
    
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)

    
    source_sale_invoice = models.ForeignKey('core.SaleInvoice', on_delete=models.SET_NULL, null=True, blank=True, related_name='generated_purchases')
    
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    notes = models.TextField(blank=True)
    
    employee = models.ForeignKey('core.CustomUser', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    is_auto_generated = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'فاتورة مشتريات'
        verbose_name_plural = 'فواتير المشتريات'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.invoice_number}"
    
    def save(self, *args, **kwargs):
        if not self.invoice_number and not self.is_auto_generated:
            self.invoice_number = self._generate_invoice_number()
        super().save(*args, **kwargs)
    
    def _generate_invoice_number(self):
        date_str = timezone.now().strftime('%Y%m%d')
        count = PurchaseInvoice.objects.filter(
            created_at__date=timezone.now().date(),
            is_auto_generated=False
        ).count() + 1
        return f"{date_str}{count:04d}"
    
    def confirm(self):
        if self.status == 'draft' and not self.is_auto_generated:
            self.status = 'confirmed'
            self.save()
            self._process_inventory()
            return True
        return False

    def _process_inventory(self):
      if self.is_auto_generated:
        return False
    
      for item in self.items.all():
        product = item.product
        
        product.update_cost_price(item.unit_price, item.quantity, self.branch)
        
        inventory, created = BranchInventory.objects.get_or_create(
            branch=self.branch,
            product=item.product,
            defaults={'quantity': 0, 'min_quantity': 5}
        )
        
        old_quantity = inventory.quantity
        inventory.quantity += item.quantity
        inventory.save()
        
        InventoryMovement.objects.create(
            branch=self.branch,
            product=item.product,
            movement_type='purchase',
            quantity=item.quantity,
            quantity_before=old_quantity,
            quantity_after=inventory.quantity,
            purchase_invoice=self,
            employee=self.employee,
            notes=f"شراء من {self.supplier.name if self.supplier else 'مورد'}"
        )
      return True
       
        
class PurchaseInvoiceItem(models.Model):
    invoice = models.ForeignKey(PurchaseInvoice, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    
    class Meta:
        verbose_name = 'بند فاتورة مشتريات'
        verbose_name_plural = 'بنود فواتير المشتريات'
    
    def save(self, *args, **kwargs):
        self.total_price = self.unit_price * self.quantity
        super().save(*args, **kwargs)










class SaleInvoice(models.Model):
    SALE_TYPE_CHOICES = [
        ('customer', 'بيع لعميل'),
        ('branch', 'توريد لفرع'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'مسودة'),
        ('confirmed', 'مؤكدة'),
        ('cancelled', 'ملغاة'),
    ]
    
    invoice_number = models.CharField(max_length=50, unique=True)
    sale_type = models.CharField(max_length=20, choices=SALE_TYPE_CHOICES)
    
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='sale_invoices')
    target_branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_sale_invoices')
    
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    debt_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    branch_commission = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    total_loyalty_points = models.IntegerField(default=0)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    employee = models.ForeignKey('core.CustomUser', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'فاتورة مبيعات'
        verbose_name_plural = 'فواتير المبيعات'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"SALE-{self.invoice_number}"
    
    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = self._generate_invoice_number()
        
        self.debt_amount = self.total - self.paid_amount
        
        if self.sale_type == 'customer' and not self.branch.is_main:
            commission_rate = self.branch.commission_percentage / Decimal('100')
            self.branch_commission = self.total * commission_rate
        else:
            self.branch_commission = 0
        
        super().save(*args, **kwargs)
    
    def update_loyalty_points(self):
      result = self.items.aggregate(total=Sum('loyalty_points'))['total'] or 0
      self.total_loyalty_points = result
      self.save(update_fields=['total_loyalty_points'])
    @property
    def amount_due_to_main(self):
      if self.sale_type == 'customer' and not self.branch.is_main:
        return self.total - self.branch_commission
      return 0
    def _generate_invoice_number(self):
        prefix = 'C' if self.sale_type == 'customer' else 'B'
        date_str = timezone.now().strftime('%Y%m%d')
        count = SaleInvoice.objects.filter(
            created_at__date=timezone.now().date()
        ).count() + 1
        return f"{prefix}{date_str}{count:04d}"
    
    def confirm(self):
      if self.status == 'draft':
        try:
            self.status = 'confirmed'
            self.save()
            self._process_inventory()  
            
            if self.sale_type == 'customer' and self.customer:
                self._create_loyalty_transfer()
                self._update_customer_debt()
            
            return True
        except ValidationErr as e:
            self.status = 'draft'
            self.save()
            raise e
        except Exception as e:
            self.status = 'draft'
            self.save()
            raise e
      return False
    
    def _process_inventory(self):
      for item in self.items.all():
        if self.sale_type == 'customer':
            inventory, created = BranchInventory.objects.get_or_create(
                branch=self.branch,
                product=item.product,
                defaults={
                    'quantity': 0,
                    'min_quantity': 5
                }
            )
            
            if inventory.quantity < item.quantity:
                raise ValidationErr(f"الكمية غير كافية للمنتج {item.product.name}. المتوفر: {inventory.quantity}")
            
            old_quantity = inventory.quantity
            inventory.quantity -= item.quantity
            inventory.save()
            
            InventoryMovement.objects.create(
                branch=self.branch,
                product=item.product,
                movement_type='sale',
                quantity=-item.quantity,
                quantity_before=old_quantity,
                quantity_after=inventory.quantity,
                sale_invoice=self,
                employee=self.employee,
                notes=f"بيع لعميل: {self.customer.full_name if self.customer else ''}"
            )
            
        elif self.sale_type == 'branch' and self.target_branch:
       
            source_inventory, created = BranchInventory.objects.get_or_create(
                branch=self.branch,
                product=item.product,
                defaults={'quantity': 0, 'min_quantity': 5}
            )
            
            if source_inventory.quantity < item.quantity:
                raise ValidationErr(f"الكمية غير كافية للمنتج {item.product.name} في الفرع المصدر. المتوفر: {source_inventory.quantity}")
            
            old_source_qty = source_inventory.quantity
            source_inventory.quantity -= item.quantity
            source_inventory.save()
            
            InventoryMovement.objects.create(
                branch=self.branch,
                product=item.product,
                movement_type='supply_out',
                quantity=-item.quantity,
                quantity_before=old_source_qty,
                quantity_after=source_inventory.quantity,
                sale_invoice=self,
                employee=self.employee,
                notes=f"توريد لفرع: {self.target_branch.name}"
            )
       
            target_inventory, created = BranchInventory.objects.get_or_create(
                branch=self.target_branch,
                product=item.product,
                defaults={'quantity': 0, 'min_quantity': 5}
            )
            
            old_target_qty = target_inventory.quantity
            target_inventory.quantity += item.quantity
            target_inventory.save()
            
            InventoryMovement.objects.create(
                branch=self.target_branch,
                product=item.product,
                movement_type='supply_in',
                quantity=item.quantity,
                quantity_before=old_target_qty,
                quantity_after=target_inventory.quantity,
                sale_invoice=self,
                employee=self.employee,
                notes=f"استلام من فرع: {self.branch.name}"
            )
            
            
            self._create_purchase_record_for_target_branch()
    def _create_purchase_record_for_target_branch(self):
      if self.target_branch:
        from .models import PurchaseInvoice, PurchaseInvoiceItem
        
        existing = PurchaseInvoice.objects.filter(source_sale_invoice=self).first()
        if existing:
            return existing
        
        purchase = PurchaseInvoice.objects.create(
            invoice_number=f"{self.invoice_number}",
            branch=self.target_branch,
            source_sale_invoice=self,
            subtotal=self.subtotal,
            discount=self.discount,
            total=self.total,
            is_auto_generated=True,
            notes=f"توريد تلقائي من فاتورة مبيعات {self.invoice_number}",
            employee=self.employee,
            status='confirmed' 
        )
        
        for item in self.items.all():
            PurchaseInvoiceItem.objects.create(
                invoice=purchase,
                product=item.product,
                quantity=item.quantity,
                unit_price=item.unit_price,
                total_price=item.total_price
            )
        
        return purchase
    def _create_loyalty_transfer(self):
        LoyaltyTransfer.objects.create(
            customer=self.customer,
            sale_invoice=self,
            points=self.total_loyalty_points,
            branch=self.branch,
            status='pending',
            notes=f"نقاط من فاتورة مبيعات {self.invoice_number}"
        )
    
    def _update_customer_debt(self):
        total_debt = SaleInvoice.objects.filter(
            customer=self.customer,
            sale_type='customer',
            status='confirmed'
        ).aggregate(total=models.Sum('debt_amount'))['total'] or 0
        
        self.customer.debt_balance = total_debt
        self.customer.save()
    
    @property
    def remaining_amount(self):
        return self.total - self.paid_amount


class SaleInvoiceItem(models.Model):
    invoice = models.ForeignKey(SaleInvoice, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    loyalty_points = models.IntegerField(default=0)  
    
    class Meta:
        verbose_name = 'بند فاتورة مبيعات'
        verbose_name_plural = 'بنود فواتير المبيعات'
    
    def save(self, *args, **kwargs):
        self.total_price = self.unit_price * self.quantity
        self.loyalty_points = self.product.loyalty_points * self.quantity
        super().save(*args, **kwargs)

class BranchSalesDelivery(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='sales_deliveries')
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='المبلغ المسلم')
    delivery_date = models.DateTimeField(default=timezone.now, verbose_name='تاريخ التسليم')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_by = models.ForeignKey('core.CustomUser', on_delete=models.SET_NULL, null=True, verbose_name='تم بواسطة')
    receipt_number = models.CharField(max_length=50, blank=True, verbose_name='رقم الإيصال')
    

    
    class Meta:
        verbose_name = 'تسليم مبيعات فرع'
        verbose_name_plural = 'تسليم مبيعات الفروع'
        ordering = ['-delivery_date']
    
    def __str__(self):
        return f"{self.branch.name} - {self.amount} - {self.delivery_date}"
    
    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = self._generate_receipt_number()
        super().save(*args, **kwargs)
    
    def _generate_receipt_number(self):
        date_str = timezone.now().strftime('%Y%m%d')
        count = BranchSalesDelivery.objects.filter(
            delivery_date__date=timezone.now().date()
        ).count() + 1
        return f"{date_str}{count:04d}"