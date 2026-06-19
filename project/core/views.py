from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import *
from .forms import *
from django.db import transaction
from django.db.models import Q , Sum ,F,Count
from decimal import Decimal
from django.core.paginator import Paginator
from .utils import *

from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import logging ,  traceback

@login_required
def home(request):
    user = request.user
    if not request.user.is_authenticated:
        return redirect('user_login')
    if user.is_loyalty_employee():
        return redirect('loyalty_pending')
    if user.is_accountant():
        return redirect('dashboard_accountant')
    if user.can_see_all_data():
        return redirect('dashboard_main')
    return redirect('dashboard_branch')


@login_required
def main_dashboard(request):
    if not request.user.can_see_all_data():
        return redirect('dashboard_branch')
    
    today = timezone.now().date()
    month_start = today.replace(day=1)
    
    branches = Branch.objects.filter(is_active=True)
    branch_count = branches.count()
    total_customers = Customer.objects.filter(is_active=True).count()
    total_products = Product.objects.filter(is_active=True).count()
    
    today_sales = SaleInvoice.objects.filter(
        sale_type='customer',
        status='confirmed',
        created_at__date=today
    ).aggregate(total=Sum('total'))['total'] or 0
    
    month_sales = SaleInvoice.objects.filter(
        sale_type='customer',
        status='confirmed',
        created_at__date__gte=month_start
    ).aggregate(total=Sum('total'))['total'] or 0
    
    total_sales = SaleInvoice.objects.filter(
        sale_type='customer',
        status='confirmed'
    ).aggregate(total=Sum('total'))['total'] or 0
    
    total_purchases = PurchaseInvoice.objects.filter(
        status='confirmed',
        is_auto_generated=False   
    ).aggregate(total=Sum('total'))['total'] or 0
    
    net_profit = total_sales - total_purchases
    
    low_stock_count = BranchInventory.objects.filter(
        quantity__lte=F('min_quantity')
    ).count()
    
    recent_invoices = SaleInvoice.objects.filter(
        status='confirmed'
    ).select_related('branch', 'customer', 'employee').order_by('-created_at')[:10]
    
    branch_sales = []
    for branch in branches:
        sales = SaleInvoice.objects.filter(
            branch=branch,
            sale_type='customer',
            status='confirmed',
            created_at__date__gte=month_start
        ).aggregate(total=Sum('total'))['total'] or 0
        
        commission = float(sales) * float(branch.commission_percentage) / 100
        
        branch_sales.append({
            'branch': branch, 
            'sales': sales, 
            'commission': commission
        })
    
    pending_loyalty = LoyaltyTransfer.objects.filter(
        status='pending'
    ).aggregate(total=Sum('points'))['total'] or 0
    
    pending_debts = SaleInvoice.objects.filter(
        sale_type='customer',
        status='confirmed',
        debt_amount__gt=0
    ).aggregate(total=Sum('debt_amount'))['total'] or 0
    
    return render(request, 'dashboard/main.html', {
        'branch_count': branch_count,
        'total_customers': total_customers,
        'total_products': total_products,
        'today_sales': today_sales,
        'month_sales': month_sales,
        'total_sales': total_sales,
        'net_profit': net_profit,
        'low_stock_count': low_stock_count,
        'recent_invoices': recent_invoices,
        'branch_sales': branch_sales,
        'pending_loyalty': pending_loyalty,
        'pending_debts': pending_debts,
    })


@login_required
def branch_dashboard(request):
    user = request.user
    if user.can_see_all_data():
        return redirect('dashboard_main')
    if not user.branch:
        return render(request, 'dashboard/no_branch.html')
    
    today = timezone.now().date()
    month_start = today.replace(day=1)
    branch = user.branch
    
    today_sales = SaleInvoice.objects.filter(
        branch=branch,
        sale_type='customer',
        status='confirmed',
        created_at__date=today
    ).aggregate(total=Sum('total'))['total'] or 0
    
    month_sales = SaleInvoice.objects.filter(
        branch=branch,
        sale_type='customer',
        status='confirmed',
        created_at__date__gte=month_start
    ).aggregate(total=Sum('total'))['total'] or 0
    
    commission = float(month_sales) * float(branch.commission_percentage) / 100
    
    low_stock = BranchInventory.objects.filter(
        branch=branch,
        quantity__lte=F('min_quantity')
    ).select_related('product')[:5]
    
    recent_invoices = SaleInvoice.objects.filter(
        branch=branch
    ).select_related('customer', 'employee').order_by('-created_at')[:10]
    
    invoice_count_today = SaleInvoice.objects.filter(
        branch=branch,
        created_at__date=today
    ).count()
    
    supply_count = SaleInvoice.objects.filter(
        branch=branch,
        sale_type='branch',
        status='confirmed',
        created_at__date=today
    ).count()
    
    return render(request, 'dashboard/branch.html', {
        'branch': branch,
        'today_sales': today_sales,
        'month_sales': month_sales,
        'commission': commission,
        'low_stock': low_stock,
        'recent_invoices': recent_invoices,
        'invoice_count_today': invoice_count_today,
        'supply_count': supply_count,
    })


@login_required
def accountant_dashboard(request):
    if not (request.user.is_accountant() or request.user.can_see_all_data()):
        return redirect('dashboard_branch')
    
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    date_filter = {}
    if date_from:
        date_filter['created_at__date__gte'] = date_from
    if date_to:
        date_filter['created_at__date__lte'] = date_to
   
    sales_query = SaleInvoice.objects.filter(sale_type='customer', status='confirmed', **date_filter)
    total_revenue = sales_query.aggregate(total=Sum('total'))['total'] or 0
    
    purchase_query = PurchaseInvoice.objects.filter(status='confirmed', is_auto_generated=False, **date_filter)
    total_cost = purchase_query.aggregate(total=Sum('total'))['total'] or 0
    
    cogs = Decimal(0)
    for invoice in sales_query.prefetch_related('items__product'):
        for item in invoice.items.all():
            cogs += item.quantity * item.product.cost_price
    
    gross_profit = total_revenue - cogs
    
    total_commissions = sales_query.aggregate(total=Sum('branch_commission'))['total'] or 0
    net_profit = gross_profit - total_commissions
 
    customer_debts = SaleInvoice.objects.filter(
        sale_type='customer',
        status='confirmed',
        debt_amount__gt=0,
        **date_filter
    )
    total_customer_debt = customer_debts.aggregate(total=Sum('debt_amount'))['total'] or 0
    
    customer_debt_details = []
    for invoice in customer_debts.select_related('customer').values('customer__id', 'customer__full_name', 'customer__phone').annotate(
        total_debt=Sum('debt_amount')
    ).order_by('-total_debt')[:10]:
        customer_debt_details.append({
            'id': invoice['customer__id'],
            'name': invoice['customer__full_name'],
            'phone': invoice['customer__phone'],
            'debt': invoice['total_debt'],
        })
    
    branch_debts = SaleInvoice.objects.filter(
        sale_type='customer',
        status='confirmed',
        branch__is_main=False,
        **date_filter
    ).values('branch__id', 'branch__name', 'branch__commission_percentage').annotate(
        total_sales=Sum('total'),
        total_commission=Sum('branch_commission'),
        amount_due=Sum('total') - Sum('branch_commission')
    ).order_by('-amount_due')
    
    branch_payments = BranchSalesDelivery.objects.filter(**date_filter).values('branch__id', 'branch__name').annotate(
        total_paid=Sum('amount')
    )
    
    branch_debt_list = []
    for branch in branch_debts:
        paid = next((p['total_paid'] for p in branch_payments if p['branch__id'] == branch['branch__id']), 0)
        branch_debt_list.append({
            'id': branch['branch__id'],
            'name': branch['branch__name'],
            'commission_percentage': branch['branch__commission_percentage'],
            'total_sales': branch['total_sales'],
            'commission': branch['total_commission'],
            'amount_due': branch['amount_due'],
            'paid': paid,
            'remaining': branch['amount_due'] - paid,
        })
    
    branch_deliveries_query = BranchSalesDelivery.objects.filter(**date_filter)
    total_branch_deliveries = branch_deliveries_query.aggregate(total=Sum('amount'))['total'] or 0
    
    branch_deliveries_by_method = branch_deliveries_query.values('payment_method').annotate(
        total=Sum('amount'),
        count=Count('id')
    )
    
    delivery_cash_amount = 0
    delivery_cash_count = 0
    delivery_bank_amount = 0
    delivery_bank_count = 0
    
    for method in branch_deliveries_by_method:
        if method['payment_method'] == 'cash':
            delivery_cash_amount = method['total'] or 0
            delivery_cash_count = method['count'] or 0
        elif method['payment_method'] == 'bank_transfer':
            delivery_bank_amount = method['total'] or 0
            delivery_bank_count = method['count'] or 0
    
    sales_by_payment_method = sales_query.values('payment_method__name', 'payment_method__increase_percentage').annotate(
        total=Sum('total'),
        count=Count('id')
    )
    
    sales_payment_methods_list = []
    for method in sales_by_payment_method:
        sales_payment_methods_list.append({
            'name': method['payment_method__name'] or 'غير محدد',
            'total': method['total'] or 0,
            'count': method['count'] or 0,
            'percentage': method['payment_method__increase_percentage'] or 0,
        })
    
    active_customers = Customer.objects.filter(is_active=True).count()
    
    low_stock_count = BranchInventory.objects.filter(
        quantity__lte=F('min_quantity')
    ).count()
    
    today = timezone.now().date()
    today_sales = SaleInvoice.objects.filter(
        sale_type='customer',
        status='confirmed',
        created_at__date=today
    ).aggregate(total=Sum('total'))['total'] or 0
    
    month_start = today.replace(day=1)
    month_sales = SaleInvoice.objects.filter(
        sale_type='customer',
        status='confirmed',
        created_at__date__gte=month_start
    ).aggregate(total=Sum('total'))['total'] or 0
    
    total_unpaid_commissions = sum(b['remaining'] for b in branch_debt_list if b['remaining'] > 0)
    
    context = {
        'date_from': date_from,
        'date_to': date_to,
        'total_revenue': total_revenue,
        'total_cost': total_cost,
        'cogs': cogs,
        'gross_profit': gross_profit,
        'total_commissions': total_commissions,
        'net_profit': net_profit,
        'total_customer_debt': total_customer_debt,
        'customer_debt_details': customer_debt_details,
        'branch_debt_list': branch_debt_list,
        'total_unpaid_commissions': total_unpaid_commissions,
        'today_sales': today_sales,
        'month_sales': month_sales,
        'active_customers': active_customers,
        'low_stock_count': low_stock_count,
        'total_branch_deliveries': total_branch_deliveries,
        'delivery_cash_amount': delivery_cash_amount,
        'delivery_cash_count': delivery_cash_count,
        'delivery_bank_amount': delivery_bank_amount,
        'delivery_bank_count': delivery_bank_count,
        'sales_payment_methods_list': sales_payment_methods_list,
        'overdue_invoices': SaleInvoice.objects.filter(
            sale_type='customer',
            status='confirmed',
            debt_amount__gt=0,
            due_date__lt=today
        ).select_related('branch', 'customer')[:20],
    }
    
    return render(request, 'dashboard/accountant.html', context)


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard_home')
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user and user.is_active:
                login(request, user)
              
                return redirect('dashboard_home')
            else:
                messages.error(request, 'اسم المستخدم أو كلمة المرور غير صحيحة')
    else:
        form = LoginForm()
    return render(request, 'accounts/login.html', {'form': form})


@login_required
def logout_view(request):

    logout(request)
    return redirect('user_login')


@login_required
def users_list(request):
    if not request.user.can_see_all_data():
        messages.error(request, 'ليس لديك صلاحية للوصول لهذه الصفحة')
        return redirect('dashboard_home')
    users = CustomUser.objects.select_related('branch').order_by('username')
    return render(request, 'accounts/users_list.html', {'users': users})


@login_required
def user_create(request):
    if not request.user.can_see_all_data():
        messages.error(request, 'ليس لديك صلاحية للوصول لهذه الصفحة')
        return redirect('dashboard_home')
    if request.method == 'POST':
        form = UserCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
    
            messages.success(request, f'تم إنشاء المستخدم {user.username} بنجاح')
            return redirect('users_list')
    else:
        form = UserCreateForm()
    return render(request, 'accounts/user_form.html', {'form': form, 'title': 'إضافة مستخدم جديد'})


@login_required
def user_edit(request, pk):
    if not request.user.can_see_all_data():
        messages.error(request, 'ليس لديك صلاحية للوصول لهذه الصفحة')
        return redirect('dashboard_home')
    user = get_object_or_404(CustomUser, pk=pk)
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
          
            messages.success(request, 'تم تحديث بيانات المستخدم بنجاح')
            return redirect('users_list')
    else:
        form = UserEditForm(instance=user)
    return render(request, 'accounts/user_form.html', {'form': form, 'title': 'تعديل المستخدم', 'user_obj': user})


@login_required
def user_delete(request, pk):
    if not request.user.is_main_admin():
        messages.error(request, 'غير مصرح لك بهذه العملية')
        return redirect('users_list')
    
    user = get_object_or_404(CustomUser, pk=pk)
    
    if user == request.user:
        messages.error(request, 'لا يمكنك حذف حسابك الخاص')
        return redirect('users_list')
    
    user.delete()
    messages.success(request, f'تم حذف المستخدم {user.get_full_name() or user.username} بنجاح')
    return redirect('users_list')

@login_required
def profile(request):
    return render(request, 'accounts/profile.html', {'user_obj': request.user})



@login_required
def branch_list(request):
    if not request.user.can_see_all_data():
        messages.error(request, 'ليس لديك صلاحية للوصول لهذه الصفحة')
        return redirect('dashboard_home')
    branches = Branch.objects.all().order_by('-is_main', 'name')
    return render(request, 'branches/list.html', {'branches': branches})


@login_required
def branch_create(request):
    if not request.user.is_main_admin():
        messages.error(request, 'ليس لديك صلاحية لإنشاء فروع')
        return redirect('branches_list')
    if request.method == 'POST':
        form = BranchForm(request.POST)
        if form.is_valid():
            branch = form.save()
           
            messages.success(request, f'تم إنشاء الفرع "{branch.name}" بنجاح')
            return redirect('branches_list')
    else:
        form = BranchForm()
    return render(request, 'branches/form.html', {'form': form, 'title': 'إضافة فرع جديد'})


@login_required
def branch_edit(request, pk):
    if not request.user.is_main_admin():
        messages.error(request, 'ليس لديك صلاحية لتعديل الفروع')
        return redirect('branches_list')
    branch = get_object_or_404(Branch, pk=pk)
    if request.method == 'POST':
        form = BranchForm(request.POST, instance=branch)
        if form.is_valid():
            form.save()
         
            messages.success(request, 'تم تحديث بيانات الفرع بنجاح')
            return redirect('branches_list')
    else:
        form = BranchForm(instance=branch)
    return render(request, 'branches/form.html', {'form': form, 'title': f'تعديل الفرع: {branch.name}', 'branch': branch})


@login_required
def branch_detail(request, pk):

    
    branch = get_object_or_404(Branch, pk=pk)
    employees = branch.employees.filter(is_active=True)
    
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    sales_query = SaleInvoice.objects.filter(
        branch=branch,
        sale_type='customer',
        status='confirmed'
    )
    
    if date_from:
        sales_query = sales_query.filter(created_at__date__gte=date_from)
    if date_to:
        sales_query = sales_query.filter(created_at__date__lte=date_to)
    
    total_sales = sales_query.aggregate(total=Sum('total'))['total'] or 0
    total_commission = sales_query.aggregate(total=Sum('branch_commission'))['total'] or 0
    
    amount_due_to_main = total_sales - total_commission
    
    deliveries_query = BranchSalesDelivery.objects.filter(branch=branch)
    if date_from:
        deliveries_query = deliveries_query.filter(delivery_date__date__gte=date_from)
    if date_to:
        deliveries_query = deliveries_query.filter(delivery_date__date__lte=date_to)
    
    total_delivered = deliveries_query.aggregate(total=Sum('amount'))['total'] or 0
    remaining_to_deliver = amount_due_to_main - total_delivered
    
    period_invoices = sales_query.order_by('-created_at')[:50]
    recent_deliveries = BranchSalesDelivery.objects.filter(branch=branch).order_by('-delivery_date')[:10]
    last_delivery = BranchSalesDelivery.objects.filter(branch=branch).order_by('-delivery_date').first()
    context = {
        'branch': branch,
        'employees': employees,
        'total_sales': total_sales,
        'total_commission': total_commission,
        'amount_due_to_main': amount_due_to_main,
        'total_delivered': total_delivered,
        'remaining_to_deliver': remaining_to_deliver,
        'period_invoices': period_invoices,
        'recent_deliveries': recent_deliveries,
        'last_delivery': last_delivery,
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'branches/detail.html', context)

@login_required
def branch_delete(request, pk):
    if not request.user.is_main_admin():
        return JsonResponse({'error': 'غير مصرح'}, status=403)
    branch = get_object_or_404(Branch, pk=pk)
    if branch.is_main:
        return JsonResponse({'error': 'لا يمكن حذف الفرع الرئيسي'}, status=400)
    name = branch.name
    branch.is_active = False
    branch.save()
    return JsonResponse({'success': True, 'message': f'تم تعطيل الفرع {name}'})


@login_required
def sale_invoice_create(request):
    
    if not request.user.branch:
        main_branch = Branch.get_main_branch()
        if main_branch:
            request.user.branch = main_branch
            request.user.save()
        else:
            messages.error(request, 'لا يوجد فرع مرتبط بحسابك ولا يوجد فرع رئيسي')
            return redirect('dashboard_home')
    
    user_branch = request.user.branch
    if user_branch.is_main:
        allowed_sale_types = ['customer', 'branch']
    else:
        allowed_sale_types = ['customer']
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                sale_type = request.POST.get('sale_type')
                if sale_type == 'branch' and not user_branch.is_main:
                    raise ValidationErr('الفرع الفرعي لا يمكنه عمل توريد لفرع آخر')
                
                payment_method_id = request.POST.get('payment_method')
                payment_method = None
                if payment_method_id:
                    payment_method = PaymentMethod.objects.filter(id=payment_method_id, is_active=True).first()
                
                is_cash_customer = request.POST.get('is_cash_customer') == 'on'
                customer_id = None
                cash_customer_name = None
                cash_customer_phone = None
                
                if is_cash_customer:
                    pass
                else:
                    customer_id = request.POST.get('customer') or None
                    if not customer_id and sale_type == 'customer':
                        raise ValidationErr('الرجاء اختيار عميل')
                
                invoice = SaleInvoice(
                    sale_type=sale_type,
                    branch=user_branch,
                    target_branch_id=request.POST.get('target_branch') or None,
                    customer_id=customer_id,
                    discount=Decimal(request.POST.get('discount', 0)),
                    paid_amount=Decimal(request.POST.get('paid_amount', 0)),
                    due_date=request.POST.get('due_date') or None,
                    notes=request.POST.get('notes', ''),
                    employee=request.user,
                    status='draft',
                    subtotal=0,
                    total=0,
                    payment_method=payment_method,
                    is_cash_customer=is_cash_customer,
                    
                )
                invoice.save()
                
                subtotal = Decimal(0)
                items_added = False
                
                for key, value in request.POST.items():
                    if key.endswith('_id'):
                        product_id = value
                        prefix = key.replace('_id', '')
                        quantity = int(request.POST.get(f'{prefix}_quantity', 0))
                        unit_price = Decimal(request.POST.get(f'{prefix}_price', 0))
                        
                        if quantity > 0:
                            items_added = True
                            product = Product.objects.get(id=product_id)
                            
                            inventory = BranchInventory.objects.filter(
                                branch=user_branch, 
                                product=product
                            ).first()
                            
                            available_stock = inventory.quantity if inventory else 0
                            if quantity > available_stock:
                                raise ValidationErr(
                                    f'الكمية المطلوبة للمنتج {product.name} ({quantity}) تتجاوز المخزون المتوفر ({available_stock})'
                                )
                            
                            total_price = unit_price * quantity
                            subtotal += total_price
                            
                            SaleInvoiceItem.objects.create(
                                invoice=invoice,
                                product=product,
                                quantity=quantity,
                                unit_price=unit_price,
                                total_price=total_price
                            )
                
                if not items_added:
                    raise ValidationErr('الرجاء إضافة منتج واحد على الأقل للفاتورة')
                
                invoice.subtotal = subtotal
                invoice.total = subtotal - invoice.discount
                
                if invoice.payment_method and invoice.payment_method.increase_percentage > 0:
                    invoice.additional_fees = invoice.total * (invoice.payment_method.increase_percentage / Decimal('100'))
                    invoice.total += invoice.additional_fees
                
                invoice.save()
                invoice.update_loyalty_points()
                
                if sale_type == 'branch':
                    invoice.paid_amount = invoice.total
                    invoice.debt_amount = 0
                    invoice.save()
                
                messages.success(request, f'تم إنشاء الفاتورة رقم {invoice.invoice_number} بنجاح')
                
                if request.POST.get('confirm') == 'yes':
                    try:
                        invoice.confirm()
                        messages.info(request, 'تم تأكيد الفاتورة ومعالجة المخزون')
                    except ValidationErr as e:
                        messages.warning(request, f'تم إنشاء الفاتورة ولكن حدث خطأ في التأكيد: {str(e)}')
                
                return redirect('sale_invoice_detail', pk=invoice.pk)
                
        except ValidationErr as e:
            messages.error(request, str(e))
            return redirect('sale_invoice_create')
        except Exception as e:
            messages.error(request, f'حدث خطأ غير متوقع: {str(e)}')
            return redirect('sale_invoice_create')
    
    branches = Branch.objects.filter(is_active=True)
    if not user_branch.is_main:
        branches = branches.exclude(pk=user_branch.pk)
    
    payment_methods = PaymentMethod.objects.filter(is_active=True)
    
    products_with_stock = []
    branch_inventories = BranchInventory.objects.filter(
        branch=user_branch,
        quantity__gt=0 
    ).select_related('product')
    
    for inventory in branch_inventories:
        products_with_stock.append({
            'id': inventory.product.id,
            'name': inventory.product.name,
            'selling_price': inventory.product.selling_price,
            'loyalty_points': inventory.product.loyalty_points,
            'stock': inventory.quantity,
            'barcode': inventory.product.barcode,
            'cost_price': inventory.product.cost_price
        })
    
    products_with_stock.sort(key=lambda x: x['name'])
    
    context = {
        'branches': branches,
        'customers': Customer.objects.filter(is_active=True),
        'allowed_sale_types': allowed_sale_types,
        'user_branch': user_branch,
        'payment_methods': payment_methods,
        'products': products_with_stock,
    }
    return render(request, 'invoices/sale_invoice_create.html', context)



@login_required
def purchase_invoice_create(request):
    if not request.user.branch:
        main_branch = Branch.get_main_branch()
        if main_branch:
            request.user.branch = main_branch
            request.user.save()
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                supplier_id = request.POST.get('supplier')
                discount = Decimal(request.POST.get('discount', 0))
                paid_amount = Decimal(request.POST.get('paid_amount', 0))
                notes = request.POST.get('notes', '')
                
                if not supplier_id:
                    raise ValidationErr('الرجاء اختيار مورد')
                
                invoice = PurchaseInvoice(
                    branch=request.user.branch,
                    supplier_id=supplier_id,
                    discount=discount,
                    paid_amount=paid_amount,
                    notes=notes,
                    employee=request.user,
                    status='draft',
                    subtotal=0,
                    total=0,
                    is_auto_generated=False
                )
                invoice.save()
                
                subtotal = Decimal(0)
                items_added = False
                
                for key, value in request.POST.items():
                    if key.endswith('_id'):
                        product_id = value
                        prefix = key.replace('_id', '')
                        quantity = int(request.POST.get(f'{prefix}_quantity', 0))
                        unit_price = Decimal(request.POST.get(f'{prefix}_price', 0))
                        
                        if quantity > 0:
                            items_added = True
                            product = Product.objects.get(id=product_id)
                            total_price = unit_price * quantity
                            subtotal += total_price
                            
                            PurchaseInvoiceItem.objects.create(
                                invoice=invoice,
                                product=product,
                                quantity=quantity,
                                unit_price=unit_price,
                                total_price=total_price
                            )
                
                if not items_added:
                    raise ValidationErr('الرجاء إضافة منتجات للفاتورة')
                
                invoice.subtotal = subtotal
                invoice.total = subtotal - discount
                invoice.save()
                
                invoice.update_loyalty_points()
                
                messages.success(request, f'تم إنشاء الفاتورة رقم {invoice.invoice_number} بنجاح')
                
                if request.POST.get('confirm') == 'yes':
                    invoice.confirm()
                    messages.info(request, 'تم تأكيد الفاتورة وإضافة نقاط الولاء للفرع الرئيسي')
                
                return redirect('purchase_invoice_detail', pk=invoice.pk)
                
        except ValidationErr as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'حدث خطأ: {str(e)}')
    
    products = Product.objects.filter(is_active=True)
    suppliers = Supplier.objects.filter(is_active=True)
    
    context = {
        'products': products,
        'suppliers': suppliers,
        'user_branch': request.user.branch,
    }
    return render(request, 'invoices/purchase_invoice_create.html', context)



@login_required
def sale_invoice_detail(request, pk):
    
    invoice = get_object_or_404(SaleInvoice, pk=pk)
    
    if not request.user.is_main_admin() and invoice.branch != request.user.branch:
        messages.error(request, 'غير مصرح لك بمشاهدة هذه الفاتورة')
        return redirect('sale_invoices_list')
    
    context = {'invoice': invoice}
    return render(request, 'invoices/sale_invoice_detail.html', context)


@login_required
def purchase_invoice_detail(request, pk):
    """عرض تفاصيل فاتورة مشتريات"""
    from .models import PurchaseInvoice
    
    invoice = get_object_or_404(PurchaseInvoice, pk=pk)
    
    if not request.user.is_main_admin() and invoice.branch != request.user.branch:
        messages.error(request, 'غير مصرح لك بمشاهدة هذه الفاتورة')
        return redirect('purchase_invoices_list')
    
    context = {'invoice': invoice}
    return render(request, 'invoices/purchase_invoice_detail.html', context)


@login_required
def sale_invoice_confirm(request, pk):
    from .models import SaleInvoice
    
    invoice = get_object_or_404(SaleInvoice, pk=pk)
    
    if invoice.branch != request.user.branch and not request.user.is_main_admin():
        messages.error(request, 'غير مصرح لك بتأكيد هذه الفاتورة')
        return redirect('sale_invoices_list')
    
    if invoice.status != 'draft':
        messages.warning(request, 'لا يمكن تأكيد فاتورة ليست في حالة مسودة')
        return redirect('sale_invoice_detail', pk=pk)
    
    if invoice.confirm():
        messages.success(request, f'تم تأكيد الفاتورة رقم {invoice.invoice_number} بنجاح')
    else:
        messages.error(request, 'حدث خطأ أثناء تأكيد الفاتورة')
    
    return redirect('sale_invoice_detail', pk=pk)


@login_required
def purchase_invoice_confirm(request, pk):
    
    if not request.user.is_main_admin():
        messages.error(request, 'غير مصرح لك بتأكيد فواتير المشتريات')
        return redirect('dashboard')
    
    invoice = get_object_or_404(PurchaseInvoice, pk=pk)
    
    if invoice.status != 'draft':
        messages.warning(request, 'لا يمكن تأكيد فاتورة ليست في حالة مسودة')
        return redirect('purchase_invoice_detail', pk=pk)
    
    if invoice.confirm():
        messages.success(request, f'تم تأكيد فاتورة المشتريات رقم {invoice.invoice_number} بنجاح')
    else:
        messages.error(request, 'حدث خطأ أثناء تأكيد الفاتورة')
    
    return redirect('purchase_invoice_detail', pk=pk)

















@login_required
def customer_list(request):
    query = request.GET.get('q', '')
    customers = Customer.objects.filter(is_active=True)
    if query:
        customers = customers.filter(
            Q(full_name__icontains=query) | Q(phone__icontains=query)
        )
    return render(request, 'customers/list.html', {'customers': customers, 'query': query})


@login_required
def customer_create(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.created_by = request.user
            customer.created_branch = request.user.branch
            customer.save()
           
            messages.success(request, f'تم إضافة العميل "{customer.full_name}" بنجاح')
            return redirect('customers_list')
    else:
        form = CustomerForm()
    return render(request, 'customers/form.html', {'form': form, 'title': 'إضافة عميل جديد'})


@login_required
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث بيانات العميل بنجاح')
            return redirect('customers_detail', pk=pk)
    else:
        form = CustomerForm(instance=customer)
    return render(request, 'customers/form.html', {'form': form, 'title': f'تعديل: {customer.full_name}', 'customer': customer})



@login_required
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    
    invoices = SaleInvoice.objects.filter(
        customer=customer,
        sale_type='customer'
    ).order_by('-created_at')[:20]
    
    pending_transfers = LoyaltyTransfer.objects.filter(
        customer=customer, 
        status='pending'
    )
    
    total_purchases = SaleInvoice.objects.filter(
        customer=customer,
        sale_type='customer',
        status='confirmed'
    ).aggregate(total=Sum('total'))['total'] or 0
    
    total_points_earned = LoyaltyTransfer.objects.filter(
        customer=customer,
        status='transferred'
    ).aggregate(total=Sum('points'))['total'] or 0
    
    return render(request, 'customers/detail.html', {
        'customer': customer,
        'invoices': invoices,
        'pending_transfers': pending_transfers,
        'total_purchases': total_purchases,
        'total_points_earned': total_points_earned,
    })


@login_required
def customer_search_ajax(request):
    query = request.GET.get('q', '')
    customers = Customer.objects.filter(
        Q(full_name__icontains=query) | Q(phone__icontains=query) | Q(customer_id__icontains=query),
        is_active=True
    )[:10]
    data = [{
        'id': c.pk, 
        'full_name': c.full_name, 
        'phone': c.phone, 
        'customer_id': c.customer_id,
        'loyalty_points': c.loyalty_points, 
        'debt_balance': float(c.debt_balance)
    } for c in customers]
    return JsonResponse({'customers': data})

@login_required
def inventory_list(request):
    user = request.user
    branch_id = request.GET.get('branch', '')
    low_stock = request.GET.get('low_stock', '')
    category_id = request.GET.get('category', '')
    product_query = request.GET.get('product', '')
    
    if user.can_see_all_data():
        branches = Branch.objects.filter(is_active=True)
        if not branch_id:
            inventory = BranchInventory.objects.select_related('branch', 'product', 'product__category')
        else:
            inventory = BranchInventory.objects.select_related('branch', 'product', 'product__category').filter(branch_id=branch_id)
    else:
        if user.branch:
            branches = Branch.objects.filter(pk=user.branch.pk)
            inventory = BranchInventory.objects.select_related('branch', 'product', 'product__category').filter(branch=user.branch)
            branch_id = str(user.branch.pk)
        else:
            branches = Branch.objects.none()
            inventory = BranchInventory.objects.none()
    
    if product_query:
        inventory = inventory.filter(
            Q(product__name__icontains=product_query) | 
            Q(product__barcode__icontains=product_query)
        )
    
    if category_id:
        inventory = inventory.filter(product__category_id=category_id)
    
    if low_stock:
        inventory = inventory.filter(quantity__lte=F('min_quantity'))
    
    inventory = inventory.order_by('product__name', 'branch__name')
    categories = Category.objects.filter(is_active=True)
    
    return render(request, 'inventory/list.html', {
        'inventory': inventory,
        'branches': branches,
        'selected_branch': branch_id,
        'low_stock_filter': low_stock,
        'categories': categories,
        'selected_category': category_id,
        'product_query': product_query,
    })

@login_required
def inventory_print(request, branch_id):
    user = request.user
    
    if user.can_see_all_data():
        branch = get_object_or_404(Branch, pk=branch_id)
    else:
        if not user.branch:
            messages.error(request, 'لا يوجد فرع مرتبط بحسابك')
            return redirect('dashboard_home')
        branch = user.branch
        if branch.pk != branch_id:
            messages.error(request, 'غير مصرح لك بطباعة مخزون فروع أخرى')
            return redirect('inventory_list')
    
    inventory = BranchInventory.objects.select_related('product').filter(branch=branch).order_by('product__name')
    
    return render(request, 'inventory/print.html', {
        'inventory': inventory,
        'branch': branch,
        'now': timezone.now(),
    })


@login_required
def inventory_stocktake(request):
    user = request.user
    
    if not user.branch:
        messages.error(request, 'لا يوجد فرع مرتبط بحسابك لإجراء الجرد')
        return redirect('dashboard_home')
    
    branch = user.branch
    
    inventory_items = BranchInventory.objects.select_related('product').filter(branch=branch)
    
    if request.method == 'POST':
        for item in inventory_items:
            new_quantity = request.POST.get(f'quantity_{item.pk}')
            if new_quantity is not None:
                try:
                    new_quantity = int(new_quantity)
                    old_quantity = item.quantity
                    if new_quantity != old_quantity:
                        InventoryMovement.objects.create(
                            branch=item.branch,
                            product=item.product,
                            movement_type='stocktake',
                            quantity=new_quantity - old_quantity,
                            quantity_before=old_quantity,
                            quantity_after=new_quantity,
                            notes=f'جرد دوري - تعديل من {old_quantity} إلى {new_quantity}',
                            employee=user,
                        )
                        item.quantity = new_quantity
                        item.save()
                except (ValueError, TypeError):
                    pass
        
        messages.success(request, 'تم حفظ الجرد بنجاح')
        return redirect('inventory_list')
    
    return render(request, 'inventory/stocktake.html', {
        'inventory_items': inventory_items,
        'branch': branch,
    })


@login_required
def inventory_damage(request, pk):
    inv = get_object_or_404(BranchInventory, pk=pk)
    
    if not request.user.can_see_all_data():
        if not request.user.branch or request.user.branch != inv.branch:
            messages.error(request, 'ليس لديك صلاحية لتلف هذا المخزون')
            return redirect('inventory_list')
    
    if request.method == 'POST':
        try:
            quantity = int(request.POST.get('quantity', 0))
            notes = request.POST.get('notes', '')
            
            if quantity <= 0:
                messages.error(request, 'الكمية يجب أن تكون أكبر من صفر')
            elif quantity > inv.quantity:
                messages.error(request, f'الكمية المدخلة أكبر من المتوفر ({inv.quantity})')
            else:
                old_quantity = inv.quantity
                new_quantity = old_quantity - quantity
                
                InventoryMovement.objects.create(
                    branch=inv.branch,
                    product=inv.product,
                    movement_type='damage',
                    quantity=-quantity,
                    quantity_before=old_quantity,
                    quantity_after=new_quantity,
                    notes=f'تلف - {notes}' if notes else 'تلف',
                    employee=request.user,
                )
                
                inv.quantity = new_quantity
                inv.save()
                
                messages.success(request, f'تم تسجيل تلف {quantity} وحدة من {inv.product.name}')
                return redirect('inventory_list')
        except ValueError:
            messages.error(request, 'الكمية المدخلة غير صحيحة')
    
    return render(request, 'inventory/damage.html', {
        'inv': inv,
    })


@login_required
def inventory_movements(request):
    user = request.user
    branch_id = request.GET.get('branch', '')
    movement_type = request.GET.get('type', '')
    
    movements = InventoryMovement.objects.select_related(
        'branch', 'product', 'employee', 
        'sale_invoice', 'purchase_invoice'
    )
    
    if not user.can_see_all_data() and user.branch:
        movements = movements.filter(branch=user.branch)
    elif branch_id:
        movements = movements.filter(branch_id=branch_id)
    
    if movement_type:
        movements = movements.filter(movement_type=movement_type)
    
    movements = movements.order_by('-created_at')[:500]
    branches = user.get_accessible_branches()
    
    return render(request, 'inventory/movements.html', {
        'movements': movements,
        'branches': branches,
        'selected_branch': branch_id,
        'movement_types': InventoryMovement.MOVEMENT_TYPES,
        'selected_type': movement_type,
    })



@login_required
def low_stock_alerts(request):
    user = request.user
    inventory = BranchInventory.objects.filter(
        quantity__lte=F('min_quantity')
    ).select_related('branch', 'product')
    if not user.can_see_all_data() and user.branch:
        inventory = inventory.filter(branch=user.branch)
    return render(request, 'inventory/low_stock.html', {'inventory': inventory})


@login_required
def inventory_report(request):
    user = request.user
    branch_id = request.GET.get('branch', '')
    if not user.can_see_all_data():
        branch_id = str(user.branch.pk) if user.branch else ''
    inventory = BranchInventory.objects.select_related('branch', 'product', 'product__category')
    if branch_id:
        inventory = inventory.filter(branch_id=branch_id)
    branches = user.get_accessible_branches()
    total_value = sum(i.stock_value for i in inventory)
    total_sale =  sum(i.sale_stock_value for i in inventory)
    return render(request, 'inventory/report.html', {
        'inventory': inventory,
        'branches': branches,
        'selected_branch': branch_id,
        'total_value': total_value,
        'total_sale':total_sale,
    })


@login_required
def get_branch_stock_ajax(request):
    branch_id = request.GET.get('branch_id')
    product_id = request.GET.get('product_id')
    try:
        inv = BranchInventory.objects.get(branch_id=branch_id, product_id=product_id)
        return JsonResponse({'quantity': inv.quantity, 'min_quantity': inv.min_quantity})
    except BranchInventory.DoesNotExist:
        return JsonResponse({'quantity': 0, 'min_quantity': 0})




@login_required
def pending_transfers(request):
    if not (request.user.is_loyalty_employee() or request.user.can_see_all_data()):
        messages.error(request, 'هذه الصفحة مخصصة لموظفي نقاط الولاء فقط')
        return redirect('dashboard_home')
    
    branch_id = request.GET.get('branch', '')
    transfers = LoyaltyTransfer.objects.filter(
        status='pending'
    ).select_related('customer', 'branch', 'sale_invoice')
    
    if branch_id:
        transfers = transfers.filter(branch_id=branch_id)
    
    branches = Branch.objects.filter(is_active=True)
    total_pending_points = transfers.aggregate(total=Sum('points'))['total'] or 0
    
    customers_summary = (
        transfers.values('customer__pk', 'customer__full_name', 'customer__phone')
        .annotate(total_points=Sum('points'))
        .order_by('-total_points')
    )
    
    return render(request, 'loyalty/pending.html', {
        'transfers': transfers,
        'branches': branches,
        'selected_branch': branch_id,
        'total_pending_points': total_pending_points,
        'customers_summary': customers_summary,
    })




logger = logging.getLogger(__name__)

@login_required
def mark_transferred(request, pk):
    try:
        logger.info(f"mark_transferred called: pk={pk}, user={request.user}")
        
        transfer = get_object_or_404(LoyaltyTransfer, pk=pk, status='pending')
        
        transfer.mark_as_transferred(request.user)
        
        wb = generate_loyalty_transfer_excel([transfer], 'single')
        filename = f"نقاط_تحويل_{transfer.customer.customer_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        return create_excel_response(wb, filename)
        
    except LoyaltyTransfer.DoesNotExist:
        logger.error(f"Transfer not found: pk={pk}")
        return JsonResponse({'error': 'عملية التحويل غير موجودة'}, status=404)
        
    except Exception as e:
        logger.error(f"Error in mark_transferred: {str(e)}")
        logger.error(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def mark_all_transferred(request):
    try:
        logger.info(f"mark_all_transferred called: user={request.user}")
        
        customer_id = request.POST.get('customer_id')
        branch_id = request.POST.get('branch_id')
        
        logger.info(f"customer_id={customer_id}, branch_id={branch_id}")
        
        transfers = LoyaltyTransfer.objects.filter(status='pending')
        
        if customer_id:
            transfers = transfers.filter(customer_id=customer_id)
        if branch_id:
            transfers = transfers.filter(branch_id=branch_id)
        
        logger.info(f"Found {transfers.count()} transfers")
        
        if not transfers.exists():
            return JsonResponse({'success': False, 'message': 'لا توجد عمليات تحويل معلقة'}, status=400)
        
        transferred_transfers = []
        
        for transfer in transfers:
            transfer.mark_as_transferred(request.user)
            transferred_transfers.append(transfer)
        
        wb = generate_loyalty_transfer_excel(transferred_transfers, 'multiple')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{len(transferred_transfers)}_{timestamp}.xlsx"
        
        return create_excel_response(wb, filename)
        
    except Exception as e:
        logger.error(f"Error in mark_all_transferred: {str(e)}")
        logger.error(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def transfer_history(request):
    branch_id = request.GET.get('branch', '')
    transfers = LoyaltyTransfer.objects.filter(status='transferred').select_related(
        'customer', 'branch', 'transferred_by', 'sale_invoice'
    ).order_by('-transfer_date')
    if branch_id:
        transfers = transfers.filter(branch_id=branch_id)
    branches = Branch.objects.filter(is_active=True)
    return render(request, 'loyalty/history.html', {
        'transfers': transfers,
        'branches': branches,
        'selected_branch': branch_id,
    })


@login_required
def product_list(request):
    query = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    products = Product.objects.select_related('category').filter(is_active=True)
    if query:
        products = products.filter(Q(name__icontains=query) | Q(code__icontains=query) | Q(barcode__icontains=query))
    if category_id:
        products = products.filter(category_id=category_id)
    categories = Category.objects.filter(is_active=True)
    return render(request, 'products/list.html', {
        'products': products,
        'categories': categories,
        'query': query,
        'selected_category': category_id,
    })



@login_required
def product_create(request):
    if not request.user.can_modify_prices():
        messages.error(request, 'فقط الفرع الرئيسي يمكنه إضافة المنتجات وتعديل الأسعار')
        return redirect('products_list')
    
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            
            initial_quantity = form.cleaned_data.get('initial_quantity', 0)
            
            if initial_quantity > 0:
                try:
                    main_branch = Branch.objects.get(is_main=True)
                    
                    branch_inventory, created = BranchInventory.objects.get_or_create(
                        branch=main_branch,
                        product=product,
                        defaults={'quantity': initial_quantity}
                    )
                    
                    if not created:
                        branch_inventory.quantity += initial_quantity
                        branch_inventory.save()
                        
                except Branch.DoesNotExist:
                    messages.warning(request, 'لم يتم العثور على فرع رئيسي لإضافة المخزون الأولي')
            else:
                try:
                    main_branch = Branch.objects.get(is_main=True)
                    BranchInventory.objects.get_or_create(
                        branch=main_branch,
                        product=product,
                        defaults={'quantity': 0}
                    )
                except Branch.DoesNotExist:
                    pass
            
            messages.success(request, f'تم إضافة المنتج "{product.name}" بنجاح')
            if initial_quantity > 0:
                messages.info(request, f'تم إضافة {initial_quantity} وحدة إلى مخزون الفرع الرئيسي')
            
            return redirect('products_list')
    else:
        form = ProductForm()
    
    return render(request, 'products/form.html', {'form': form, 'title': 'إضافة منتج جديد'})

@login_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if not request.user.can_modify_prices():
        messages.error(request, 'فقط الفرع الرئيسي يمكنه تعديل أسعار المنتجات')
        return redirect('products_list')
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
        
            messages.success(request, 'تم تحديث بيانات المنتج بنجاح')
            return redirect('products_list')
    else:
        form = ProductForm(instance=product)
    return render(request, 'products/form.html', {'form': form, 'title': f'تعديل: {product.name}', 'product': product})


@login_required
def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    branch_stocks = BranchInventory.objects.filter(product=product).select_related('branch')
    return render(request, 'products/detail.html', {'product': product, 'branch_stocks': branch_stocks})


@login_required
def product_delete(request, pk):
    if not request.user.is_main_admin():
        return JsonResponse({'error': 'غير مصرح'}, status=403)
    product = get_object_or_404(Product, pk=pk)
    product.is_active = False
    product.save()
    return JsonResponse({'success': True})


@login_required
def category_list(request):
    categories = Category.objects.all()
    return render(request, 'products/categories.html', {'categories': categories})


@login_required
def category_create(request):
    if not request.user.can_modify_prices():
        messages.error(request, 'ليس لديك صلاحية لإضافة فئات')
        return redirect('categories')
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إضافة الفئة بنجاح')
            return redirect('categories')
    else:
        form = CategoryForm()
    return render(request, 'products/category_form.html', {'form': form, 'title': 'إضافة فئة جديدة'})


@login_required
def product_search_ajax(request):
    query = request.GET.get('q', '')
    branch_id = request.GET.get('branch_id', '')
    products = Product.objects.filter(
        Q(name__icontains=query) |  Q(barcode__icontains=query),
        is_active=True
    )[:20]
    data = []
    for p in products:
        stock = 0
        if branch_id:
            stock = p.get_branch_stock(branch_id)
        data.append({
            'id': p.pk,
            'name': p.name,
            'cost_price':float(p.cost_price),
            'selling_price': float(p.selling_price),
            'loyalty_points': p.loyalty_points,
            'stock': stock,
        })

    return JsonResponse({'products': data})


@login_required
def supplier_list(request):
    """عرض قائمة الموردين"""
    if not request.user.is_main_admin():
        messages.error(request, 'غير مصرح لك بالوصول إلى هذه الصفحة')
        return redirect('dashboard_home')
    
    query = request.GET.get('q', '')
    suppliers = Supplier.objects.filter(is_active=True)
    if query:
        suppliers = suppliers.filter(
            Q(name__icontains=query) | Q(phone__icontains=query) | Q(tax_number__icontains=query)
        )
    return render(request, 'suppliers/list.html', {'suppliers': suppliers, 'query': query})


@login_required
def supplier_create(request):
    """إنشاء مورد جديد"""
    if not request.user.is_main_admin():
        messages.error(request, 'غير مصرح لك بإنشاء موردين')
        return redirect('dashboard_home')
    
    if request.method == 'POST':
        form = SupplierForm(request.POST)
        if form.is_valid():
            supplier = form.save()
            messages.success(request, f'تم إضافة المورد "{supplier.name}" بنجاح')
            return redirect('supplier_list')
    else:
        form = SupplierForm()
    return render(request, 'suppliers/form.html', {'form': form, 'title': 'إضافة مورد جديد'})


@login_required
def supplier_edit(request, pk):
    """تعديل بيانات مورد"""
    if not request.user.is_main_admin():
        messages.error(request, 'غير مصرح لك بتعديل الموردين')
        return redirect('dashboard_home')
    
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث بيانات المورد بنجاح')
            return redirect('supplier_detail', pk=pk)
    else:
        form = SupplierForm(instance=supplier)
    return render(request, 'suppliers/form.html', {'form': form, 'title': f'تعديل المورد: {supplier.name}', 'supplier': supplier})


@login_required
def supplier_detail(request, pk):
    if not request.user.is_main_admin():
        messages.error(request, 'غير مصرح لك بالوصول إلى هذه الصفحة')
        return redirect('dashboard_home')
    
    supplier = get_object_or_404(Supplier, pk=pk)
    purchases = PurchaseInvoice.objects.filter(supplier=supplier, status='confirmed').order_by('-created_at')[:20]
    total_purchases = supplier.get_total_purchases()
    total_paid =  supplier.get_total_paid_from_invoices()
    recent_payments = supplier.payments.all().order_by('-payment_date')[:10]
    
    return render(request, 'suppliers/detail.html', {
        'supplier': supplier,
        'purchases': purchases,
        'total_purchases': total_purchases,
        'total_paid': total_paid,
        'recent_payments': recent_payments,
    })

@login_required
def supplier_delete(request, pk):
    if not request.user.is_main_admin():
        return JsonResponse({'error': 'غير مصرح'}, status=403)
    
    supplier = get_object_or_404(Supplier, pk=pk)
    supplier.is_active = False
    supplier.save()
    return JsonResponse({'success': True, 'message': f'تم تعطيل المورد {supplier.name}'})


@login_required
def supplier_search_ajax(request):
    query = request.GET.get('q', '')
    suppliers = Supplier.objects.filter(
        Q(name__icontains=query),
        is_active=True
    )[:10]
    data = [{
        'id': s.pk,
        'name': s.name,

    } for s in suppliers]
    return JsonResponse({'suppliers': data})

@login_required
def supplier_payment_create(request, supplier_id):
    supplier = get_object_or_404(Supplier, pk=supplier_id)
    
    if not request.user.is_main_admin():
        messages.error(request, 'غير مصرح لك بهذه العملية')
        return redirect('supplier_detail', pk=supplier_id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                amount = Decimal(request.POST.get('amount', 0))
                payment_date = request.POST.get('payment_date')
                payment_method = request.POST.get('payment_method')
                reference_number = request.POST.get('reference_number', '')
                notes = request.POST.get('notes', '')
                specific_invoice_id = request.POST.get('purchase_invoice_id')
                
                if amount <= 0:
                    raise ValueError('المبلغ يجب أن يكون أكبر من صفر')
                
                unpaid_invoices = PurchaseInvoice.objects.filter(
                    supplier=supplier,
                    status='confirmed'
                ).filter(
                    paid_amount__lt=models.F('total')
                ).order_by('created_at')  
                
                total_debt = sum([inv.total - inv.paid_amount for inv in unpaid_invoices])
                
                if amount > total_debt:
                    raise ValueError(f'المبلغ المدخل ({amount}) يتجاوز إجمالي الدين ({total_debt})')
                
                payment = SupplierPayment.objects.create(
                    supplier=supplier,
                    amount=amount,
                    payment_date=payment_date,
                    payment_method=payment_method,
                    reference_number=reference_number,
                    notes=notes,
                    created_by=request.user
                )
                
                remaining_amount = amount
                paid_invoices = []  
                
                for invoice in unpaid_invoices:
                    if remaining_amount <= 0:
                        break
                    
                    invoice_remaining = invoice.total - invoice.paid_amount
                    
                    if invoice_remaining <= 0:
                        continue
                    
                    if remaining_amount >= invoice_remaining:
                        invoice.paid_amount = invoice.total
                        invoice.debt_amount = 0
                        remaining_amount -= invoice_remaining
                    else:
                        invoice.paid_amount += remaining_amount
                        invoice.debt_amount = invoice.total - invoice.paid_amount
                        remaining_amount = 0
                    
                    invoice.save()
                    paid_invoices.append(invoice)
                    
                
                
                supplier.update_debt_balance()
                
                invoice_details = ', '.join([f"{inv.invoice_number} ({inv.paid_amount}/{inv.total})" for inv in paid_invoices])
                messages.success(
                    request, 
                    f'تم تسجيل مبلغ {amount} كسداد للمورد {supplier.name}\n'
                    f'الفواتير المحدثة: {invoice_details}'
                )
                return redirect('supplier_payment_list', supplier_id=supplier.id)
                
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'حدث خطأ: {str(e)}')
    
    unpaid_invoices = PurchaseInvoice.objects.filter(
        supplier=supplier,
        status='confirmed'
    ).filter(
        paid_amount__lt=models.F('total')
    ).order_by('created_at')
    
    total_debt = sum([inv.total - inv.paid_amount for inv in unpaid_invoices])
    
    context = {
        'supplier': supplier,
        'unpaid_invoices': unpaid_invoices,
        'total_debt': total_debt,
        'total_paid':supplier.get_total_paid_from_invoices() ,
    }
    return render(request, 'suppliers/payment_form.html', context)


@login_required
def supplier_payment_list(request, supplier_id):
    supplier = get_object_or_404(Supplier, pk=supplier_id)
    
    if not request.user.is_main_admin():
        messages.error(request, 'غير مصرح لك بالوصول')
        return redirect('dashboard_home')
    
    payments = supplier.payments.all().order_by('-payment_date')
    
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    
    if from_date:
        payments = payments.filter(payment_date__gte=from_date)
    if to_date:
        payments = payments.filter(payment_date__lte=to_date)
    
    paginator = Paginator(payments, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'supplier': supplier,
        'page_obj': page_obj,
        'from_date': from_date,
        'to_date': to_date,
        'total_paid': supplier.get_total_paid(),
    }
    return render(request, 'suppliers/payment_list.html', context)


@login_required
def supplier_payment_delete(request, payment_id):
    if not request.user.is_main_admin():
        return JsonResponse({'error': 'غير مصرح'}, status=403)
    
    payment = get_object_or_404(SupplierPayment, pk=payment_id)
    supplier = payment.supplier
    
    with transaction.atomic():
        if payment.purchase_invoice:
            payment.purchase_invoice.paid_amount -= payment.amount
            payment.purchase_invoice.save()
        
        payment.delete()
        supplier.update_debt_balance()
    
    return JsonResponse({'success': True})


@login_required
def supplier_payment_invoice(request, payment_id):
    payment = get_object_or_404(SupplierPayment, pk=payment_id)
    
    if not request.user.is_main_admin():
        messages.error(request, 'غير مصرح')
        return redirect('dashboard_home')
    
    return render(request, 'suppliers/payment_invoice.html', {'payment': payment})

@login_required
def sale_invoices_list(request):
    user = request.user
    invoices = SaleInvoice.objects.select_related('branch', 'customer', 'employee')
    
    if not user.can_see_all_data():
        invoices = invoices.filter(branch=user.branch)
    
    status = request.GET.get('status', '')
    if status:
        invoices = invoices.filter(status=status)
    
    sale_type = request.GET.get('sale_type', '')
    if sale_type:
        invoices = invoices.filter(sale_type=sale_type)
    
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        invoices = invoices.filter(created_at__date__gte=date_from)
    if date_to:
        invoices = invoices.filter(created_at__date__lte=date_to)
    
    invoices = invoices.order_by('-created_at')
    
    stats = {
        'total_count': invoices.count(),
        'total_amount': invoices.aggregate(total=Sum('total'))['total'] or 0,
        'draft_count': invoices.filter(status='draft').count(),
        'confirmed_count': invoices.filter(status='confirmed').count(),
    }
    
    context = {
        'invoices': invoices,
        'stats': stats,
        'status_filter': status,
        'sale_type_filter': sale_type,
        'date_from': date_from,
        'date_to': date_to,
        'status_choices': SaleInvoice.STATUS_CHOICES,
        'sale_type_choices': SaleInvoice.SALE_TYPE_CHOICES,
    }
    return render(request, 'invoices/sale_invoices_list.html', context)

@login_required
def purchase_invoices_list(request):
    
    invoices = PurchaseInvoice.objects.select_related('branch', 'supplier', 'employee')
    
    branch_filter = request.GET.get('branch', '')
    
    if request.user.can_see_all_data(): 
        if branch_filter:
            invoices = invoices.filter(branch_id=branch_filter)
    else:
        if request.user.branch:
            invoices = invoices.filter(branch=request.user.branch)
            branch_filter = str(request.user.branch.id)
        else:
            invoices = invoices.none()
    
    status = request.GET.get('status', '')
    if status:
        invoices = invoices.filter(status=status)
    
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        invoices = invoices.filter(created_at__date__gte=date_from)
    if date_to:
        invoices = invoices.filter(created_at__date__lte=date_to)
    
    invoices = invoices.order_by('-created_at')
    
    stats = {
        'total_count': invoices.count(),
        'total_amount': invoices.aggregate(total=Sum('total'))['total'] or 0,
        'draft_count': invoices.filter(status='draft').count(),
        'confirmed_count': invoices.filter(status='confirmed').count(),
    }
    
    branches = request.user.get_accessible_branches()
    
    context = {
        'invoices': invoices,
        'stats': stats,
        'status_filter': status,
        'branch_filter': branch_filter,
        'date_from': date_from,
        'date_to': date_to,
        'status_choices': PurchaseInvoice.STATUS_CHOICES,
        'branches': branches,
        'is_main_admin': request.user.is_main_admin(),
        'user_branch': request.user.branch,
    }
    return render(request, 'invoices/purchase_invoices_list.html', context)


@login_required
def sale_invoice_print(request, pk):
    invoice = get_object_or_404(SaleInvoice, pk=pk)
    
    if not request.user.is_main_admin() and invoice.branch != request.user.branch:
        messages.error(request, 'غير مصرح لك بطباعة هذه الفاتورة')
        return redirect('sale_invoices_list')
    
    return render(request, 'invoices/sale_invoice_print.html', {'invoice': invoice})


@login_required
def purchase_invoice_print(request, pk):
    """طباعة فاتورة مشتريات"""
    if not request.user.is_main_admin():
        messages.error(request, 'غير مصرح لك بطباعة هذه الفاتورة')
        return redirect('dashboard_home')
    
    invoice = get_object_or_404(PurchaseInvoice, pk=pk)
    return render(request, 'invoices/purchase_invoice_print.html', {'invoice': invoice})


@login_required
def sale_invoice_cancel(request, pk):
    invoice = get_object_or_404(SaleInvoice, pk=pk)
    
    if invoice.status != 'draft':
        messages.error(request, 'لا يمكن إلغاء فاتورة تم تأكيدها')
        return redirect('sale_invoice_detail', pk=pk)
    
    if request.method == 'POST':
        invoice.status = 'cancelled'
        invoice.save()
        messages.success(request, f'تم إلغاء الفاتورة رقم {invoice.invoice_number}')
        return redirect('sale_invoices_list')
    
    return render(request, 'invoices/sale_invoice_cancel.html', {'invoice': invoice})





@login_required
def branch_deliveries_history(request, pk):
    branch = get_object_or_404(Branch, pk=pk)
    
    if not request.user.can_see_all_data():
        messages.error(request, 'غير مصرح لك')
        return redirect('dashboard_home')
    
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    deliveries = BranchSalesDelivery.objects.filter(branch=branch)
    
    if date_from:
        deliveries = deliveries.filter(delivery_date__date__gte=date_from)
    if date_to:
        deliveries = deliveries.filter(delivery_date__date__lte=date_to)
    
    deliveries = deliveries.order_by('-delivery_date')
    
    
    total_count = deliveries.count()
    total_amount = deliveries.aggregate(total=Sum('amount'))['total'] or 0
    avg_amount = total_amount / total_count if total_count > 0 else 0
    
    paginator = Paginator(deliveries, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'branch': branch,
        'deliveries': page_obj,
        'total_count': total_count,
        'total_amount': total_amount,
        'avg_amount': avg_amount,
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'branches/deliveries_history.html', context)


@login_required
def branch_sales_delivery(request, pk):
    if not request.user.is_main_admin():
        messages.error(request, 'غير مصرح لك بهذه العملية')
        return redirect('dashboard_home')
    
    branch = get_object_or_404(Branch, pk=pk)
    
    sales_query = SaleInvoice.objects.filter(
        branch=branch,
        sale_type='customer',
        status='confirmed'
    )
    
    total_sales = sales_query.aggregate(total=Sum('total'))['total'] or 0
    total_commission = sales_query.aggregate(total=Sum('branch_commission'))['total'] or 0
    amount_due_to_main = total_sales - total_commission
    
    total_delivered = BranchSalesDelivery.objects.filter(branch=branch).aggregate(total=Sum('amount'))['total'] or 0
    remaining_to_deliver = amount_due_to_main - total_delivered
    
    recent_invoices = sales_query.order_by('-created_at')[:20]
    
    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount', 0))
        delivery_date = request.POST.get('delivery_date')
        payment_method = request.POST.get('payment_method', 'cash')
        notes = request.POST.get('notes', '')
        
        if amount <= 0:
            messages.error(request, 'المبلغ يجب أن يكون أكبر من صفر')
        elif amount > remaining_to_deliver:
            messages.error(request, f'المبلغ المدخل أكبر من المتبقي للتسليم ({remaining_to_deliver:,.2f} د.ل)')
        else:
            delivery = BranchSalesDelivery.objects.create(
                branch=branch,
                amount=amount,
                payment_method=payment_method,
                delivery_date=delivery_date or timezone.now(),
                notes=notes,
                created_by=request.user
            )
            
            messages.success(request, f'تم تسجيل تسليم مبيعات بقيمة {amount:,.2f}  للفرع {branch.name}')
            return redirect('branch_delivery_receipt', pk=delivery.pk)
    
    context = {
        'branch': branch,
        'total_sales': total_sales,
        'total_commission': total_commission,
        'amount_due_to_main': amount_due_to_main,
        'total_delivered': total_delivered,
        'remaining_to_deliver': remaining_to_deliver,
        'recent_invoices': recent_invoices,
        'today': timezone.now(),
    }
    return render(request, 'branches/sales_delivery.html', context)


@login_required
def branch_delivery_receipt(request, pk):
    delivery = get_object_or_404(BranchSalesDelivery, pk=pk)
    
    if not request.user.is_main_admin() and delivery.branch != request.user.branch:
        messages.error(request, 'غير مصرح لك')
        return redirect('dashboard_home')
    
    return render(request, 'branches/delivery_receipt.html', {'delivery': delivery})   


@login_required
def branch_sales_report(request, pk):
    branch = get_object_or_404(Branch, pk=pk)
    
    if not request.user.can_see_all_data():
        messages.error(request, 'غير مصرح لك')
        return redirect('dashboard_home')
    
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    sales = SaleInvoice.objects.filter(
        branch=branch,
        sale_type='customer',
        status='confirmed'
    )
    
    if date_from:
        sales = sales.filter(created_at__date__gte=date_from)
    if date_to:
        sales = sales.filter(created_at__date__lte=date_to)
    
    total_sales = sales.aggregate(total=Sum('total'))['total'] or 0
    total_commission = sales.aggregate(total=Sum('branch_commission'))['total'] or 0
    
    monthly_data = sales.extra(
        select={'month': "strftime('%%Y-%%m', created_at)"}
    ).values('month').annotate(
        total=Sum('total'),
        commission=Sum('branch_commission')
    ).order_by('month')
    
    context = {
        'branch': branch,
        'sales': sales.order_by('-created_at'),
        'total_sales': total_sales,
        'total_commission': total_commission,
        'monthly_data': monthly_data,
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'branches/sales_report.html', context)     


@login_required
def products_bulk_price_update(request):
    if not request.user.can_modify_prices():
        messages.error(request, 'غير مصرح لك بتعديل أسعار المنتجات')
        return redirect('products_list')
    
    query = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    page = request.GET.get('page', 1)
    products = Product.objects.filter(is_active=True)
    
    if query:
        products = products.filter(Q(name__icontains=query) | Q(barcode__icontains=query))
    if category_id:
        products = products.filter(category_id=category_id)
    
    products = products.order_by('name')
    
    paginator = Paginator(products, 20)
    page_obj = paginator.get_page(page)
    
    categories = Category.objects.filter(is_active=True)
    
    if request.method == 'POST':
        selected_products_str = request.POST.get('selected_products', '')
        
        if selected_products_str:
            selected_products = [int(x) for x in selected_products_str.split(',') if x.strip().isdigit()]
        else:
            selected_products = []
        
        increase_type = request.POST.get('increase_type', 'fixed')
        increase_value = Decimal(request.POST.get('increase_value', 0))
        
        if not selected_products:
            messages.error(request, 'الرجاء اختيار منتج واحد على الأقل')
            return redirect('products_bulk_price_update')
        
        if increase_value <= 0:
            messages.error(request, 'الرجاء إدخال قيمة زيادة أكبر من صفر')
            return redirect('products_bulk_price_update')
        
        updated_count = 0
        for product_id in selected_products:
            try:
                product = Product.objects.get(id=product_id, is_active=True)
                old_price = product.selling_price
                
                if increase_type == 'fixed':
                    new_price = old_price + increase_value
                else:  
                    new_price = old_price + (old_price * increase_value / 100)
                
                product.selling_price = round(new_price, 2)
                product.save()
                updated_count += 1
                
            except Product.DoesNotExist:
                continue
        
        messages.success(request, f'تم تحديث {updated_count} منتج بنجاح')
        return redirect('products_bulk_price_update')
    
    context = {
        'products': page_obj,
        'categories': categories,
        'query': query,
        'selected_category': category_id,
        'total_count': products.count(),
    }
    return render(request, 'products/bulk_price_update.html', context)


@login_required
def customer_payment_create(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    
    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount', 0))
        notes = request.POST.get('notes', '')
        
        if amount <= 0:
            messages.error(request, 'المبلغ يجب أن يكون أكبر من صفر')
            return redirect('customer_payment_create', pk=pk)
        
        if amount > customer.debt_balance:
            messages.error(request, f'المبلغ المدخل أكبر من الدين المستحق ({customer.debt_balance:,.2f} د.ل)')
            return redirect('customer_payment_create', pk=pk)
        
        payment = CustomerPayment.objects.create(
            customer=customer,
            amount=amount,
            notes=notes,
            created_by=request.user
        )
        
        customer.debt_balance -= amount
        customer.save()
        
        remaining = amount
        invoices = SaleInvoice.objects.filter(
            customer=customer,
            sale_type='customer',
            status='confirmed',
            debt_amount__gt=0
        ).order_by('due_date')
        
        for invoice in invoices:
            if remaining <= 0:
                break
            if invoice.debt_amount <= remaining:
                remaining -= invoice.debt_amount
                invoice.debt_amount = 0
                invoice.paid_amount = invoice.total
                invoice.status = 'paid'
            else:
                invoice.debt_amount -= remaining
                invoice.paid_amount += remaining
                remaining = 0
            invoice.save()
        
        messages.success(request, f'تم تسديد {amount:,.2f} د.ل من دين العميل {customer.full_name}')
        
        return redirect('customer_payment_receipt', pk=payment.pk)
    
    context = {
        'customer': customer,
        'debt_amount': customer.debt_balance,
    }
    return render(request, 'customers/payment_create.html', context)


@login_required
def customer_payment_receipt(request, pk):
    payment = get_object_or_404(CustomerPayment, pk=pk)
    
    if not request.user.can_see_all_data() and payment.created_by != request.user:
        messages.error(request, 'غير مصرح لك بمشاهدة هذا الإيصال')
        return redirect('customers_list')
    
    return render(request, 'customers/payment_receipt.html', {'payment': payment})


@login_required
def customer_payments_history(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    payments = CustomerPayment.objects.filter(customer=customer).order_by('-payment_date')
    
    return render(request, 'customers/payments_history.html', {
        'customer': customer,
        'payments': payments,
    })    


@login_required
def api_products_stock(request):
    branch = request.user.branch
    if not branch:
        return JsonResponse({'products': []})
    
    q = request.GET.get('q', '')
    products_list = []
    
    inventories = BranchInventory.objects.filter(branch=branch, quantity__gt=0)
    
    if q:
        inventories = inventories.filter(product__name__icontains=q)
    
    for inv in inventories.select_related('product')[:20]:
        products_list.append({
            'id': inv.product.id,
            'name': inv.product.name,
            'price': float(inv.product.selling_price),
            'points': inv.product.loyalty_points,
            'stock': inv.quantity
        })
    
    return JsonResponse({'products': products_list})



def payment_methods_list(request):
    payment_methods = PaymentMethod.objects.all()
    
    search_query = request.GET.get('search', '')
    if search_query:
        payment_methods = payment_methods.filter(name__icontains=search_query)
    
    sort_by = request.GET.get('sort', 'name')
    payment_methods = payment_methods.order_by(sort_by)
    
    paginator = Paginator(payment_methods, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'sort_by': sort_by,
    }
    return render(request, 'payment_methods/list.html', context)

def payment_method_create(request):
    if request.method == 'POST':
        form = PaymentMethodForm(request.POST)
        if form.is_valid():
            payment_method = form.save()
            messages.success(request, f'تم إضافة طريقة الدفع "{payment_method.name}" بنجاح')
            return redirect('payment_methods_list')
    else:
        form = PaymentMethodForm()
    
    context = {'form': form}
    return render(request, 'payment_methods/form.html', context)

def payment_method_edit(request, pk):
    payment_method = get_object_or_404(PaymentMethod, pk=pk)
    
    if request.method == 'POST':
        form = PaymentMethodForm(request.POST, instance=payment_method)
        if form.is_valid():
            payment_method = form.save()
            messages.success(request, f'تم تعديل طريقة الدفع "{payment_method.name}" بنجاح')
            return redirect('payment_methods_list')
    else:
        form = PaymentMethodForm(instance=payment_method)
    
    context = {'form': form, 'payment_method': payment_method}
    return render(request, 'payment_methods/form.html', context)

def payment_method_delete(request, pk):
    payment_method = get_object_or_404(PaymentMethod, pk=pk)
    
    if request.method == 'POST':
        method_name = payment_method.name
        payment_method.delete()
        messages.success(request, f'تم حذف طريقة الدفع "{method_name}" بنجاح')
        return redirect('payment_methods_list')
    
    context = {'payment_method': payment_method}
    return render(request, 'payment_methods/confirm_delete.html', context)

def payment_method_toggle_status(request, pk):
    payment_method = get_object_or_404(PaymentMethod, pk=pk)
    payment_method.is_active = not payment_method.is_active
    payment_method.save()
    
    status = 'مفعلة' if payment_method.is_active else 'غير مفعلة'
    messages.success(request, f'تم {status} طريقة الدفع "{payment_method.name}"')
    return redirect('payment_methods_list')



@login_required
def sale_invoice_return(request, pk):
    invoice = get_object_or_404(SaleInvoice, pk=pk)
    user = request.user
    
    if not user.can_see_all_data():
        if user.branch != invoice.branch:
            messages.error(request, 'غير مصرح لك بعمل مرتجع لهذه الفاتورة')
            return redirect('sale_invoices_list')
    
    if invoice.status != 'confirmed':
        messages.error(request, 'لا يمكن عمل مرتجع إلا للفواتير المؤكدة')
        return redirect('sale_invoices_list')
    
    if request.method == 'POST':
        return_type = request.POST.get('return_type')
        selected_items = request.POST.getlist('items')
        
        if not selected_items and return_type != 'full':
            messages.error(request, 'الرجاء اختيار المنتجات التي سيتم إرجاعها')
            return redirect('sale_invoice_return', pk=pk)
        
        try:
            total_return_amount = 0
            
            if return_type == 'full':
                for item in invoice.items.all():
                    inventory, created = BranchInventory.objects.get_or_create(
                        branch=invoice.branch,
                        product=item.product,
                        defaults={'quantity': 0, 'min_quantity': 5}
                    )
                    
                    old_quantity = inventory.quantity
                    inventory.quantity += item.quantity
                    inventory.save()
                    
                    InventoryMovement.objects.create(
                        branch=invoice.branch,
                        product=item.product,
                        movement_type='return',
                        quantity=item.quantity,
                        quantity_before=old_quantity,
                        quantity_after=inventory.quantity,
                        sale_invoice=invoice,
                        employee=user,
                        notes=f'مرتجع كامل للفاتورة {invoice.invoice_number}'
                    )
                    
                    total_return_amount += item.total_price
                
                invoice.status = 'cancelled'
                invoice.save()
                
                if invoice.sale_type == 'customer' and invoice.customer and not invoice.is_cash_customer:
                    debt_reduction = min(invoice.debt_amount, total_return_amount)
                    invoice.customer.debt_balance -= debt_reduction
                    invoice.customer.save()
                
                if invoice.total_loyalty_points > 0 and invoice.sale_type == 'customer' and invoice.customer and not invoice.is_cash_customer:
                    invoice.branch.loyalty_points_inventory += invoice.total_loyalty_points
                    invoice.branch.save()
                    
                    LoyaltyTransaction.objects.create(
                        branch=invoice.branch,
                        customer=invoice.customer,
                        sale_invoice=invoice,
                        points=invoice.total_loyalty_points,
                        transaction_type='refund',
                        notes=f'استرجاع نقاط من مرتجع فاتورة {invoice.invoice_number}'
                    )
                    
                    pending_transfer = LoyaltyTransfer.objects.filter(
                        sale_invoice=invoice,
                        status='pending'
                    ).first()
                    if pending_transfer:
                        pending_transfer.status = 'cancelled'
                        pending_transfer.save()
            
            else:
                for item_id in selected_items:
                    original_item = invoice.items.get(pk=item_id)
                    return_quantity = int(request.POST.get(f'quantity_{item_id}', 0))
                    
                    if return_quantity <= 0:
                        continue
                    
                    if return_quantity > original_item.quantity:
                        messages.error(request, f'الكمية المرتجعة للمنتج {original_item.product.name} أكبر من الكمية الأصلية')
                        return redirect('sale_invoice_return', pk=pk)
                    
                    return_amount = original_item.unit_price * return_quantity
                    total_return_amount += return_amount
                    
                    inventory, created = BranchInventory.objects.get_or_create(
                        branch=invoice.branch,
                        product=original_item.product,
                        defaults={'quantity': 0, 'min_quantity': 5}
                    )
                    
                    old_quantity = inventory.quantity
                    inventory.quantity += return_quantity
                    inventory.save()
                    
                    InventoryMovement.objects.create(
                        branch=invoice.branch,
                        product=original_item.product,
                        movement_type='return',
                        quantity=return_quantity,
                        quantity_before=old_quantity,
                        quantity_after=inventory.quantity,
                        sale_invoice=invoice,
                        employee=user,
                        notes=f'مرتجع جزئي للفاتورة {invoice.invoice_number}'
                    )
                    
                    original_item.quantity -= return_quantity
                    original_item.total_price = original_item.unit_price * original_item.quantity
                    original_item.save()
                
                invoice.subtotal -= total_return_amount
                invoice.total -= total_return_amount
                
                if invoice.sale_type == 'customer' and not invoice.branch.is_main:
                    from decimal import Decimal
                    commission_rate = invoice.branch.commission_percentage / Decimal('100')
                    invoice.branch_commission = invoice.total * commission_rate
                
                if invoice.paid_amount > invoice.total:
                    invoice.paid_amount = invoice.total
                
                invoice.debt_amount = invoice.total - invoice.paid_amount
                invoice.save()
                
                if invoice.sale_type == 'customer' and invoice.customer and not invoice.is_cash_customer:
                    from django.db.models import Sum
                    total_debt = SaleInvoice.objects.filter(
                        customer=invoice.customer,
                        sale_type='customer',
                        status='confirmed'
                    ).aggregate(total=Sum('debt_amount'))['total'] or 0
                    invoice.customer.debt_balance = total_debt
                    invoice.customer.save()
                
                if invoice.total_loyalty_points > 0 and invoice.sale_type == 'customer' and invoice.customer and not invoice.is_cash_customer:
                    returned_points = 0
                    for item_id in selected_items:
                        original_item = invoice.items.get(pk=item_id)
                        return_quantity = int(request.POST.get(f'quantity_{item_id}', 0))
                        returned_points += original_item.product.loyalty_points * return_quantity
                    
                    if returned_points > 0:
                        invoice.branch.loyalty_points_inventory += returned_points
                        invoice.branch.save()
                        
                        LoyaltyTransaction.objects.create(
                            branch=invoice.branch,
                            customer=invoice.customer,
                            sale_invoice=invoice,
                            points=returned_points,
                            transaction_type='refund',
                            notes=f'استرجاع نقاط من مرتجع جزئي للفاتورة {invoice.invoice_number}'
                        )
                        
                        invoice.total_loyalty_points -= returned_points
                        invoice.save()
            
            messages.success(request, f'تم عمل مرتجع بنجاح بقيمة {total_return_amount:,.2f}')
            return redirect('sale_invoices_list')
            
        except Exception as e:
            messages.error(request, f'حدث خطأ: {str(e)}')
            return redirect('sale_invoice_return', pk=pk)
    
    context = {
        'invoice': invoice,
        'items': invoice.items.all(),
    }
    return render(request, 'invoices/sale_invoice_return.html', context)  


@login_required
def branch_adjust_points(request, pk):
    branch = get_object_or_404(Branch, pk=pk)
    
    if not request.user.can_see_all_data():
        messages.error(request, 'غير مصرح لك بتعديل نقاط الولاء')
        return redirect('branches_detail', pk=pk)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        points = request.POST.get('points')
        reason = request.POST.get('reason', '')
        
        try:
            points = int(points)
            if points <= 0:
                messages.error(request, 'عدد النقاط يجب أن يكون أكبر من صفر')
                return redirect('branches_detail', pk=pk)
            
            if action == 'add':
                branch.loyalty_points_inventory += points
                branch.save()
                
                LoyaltyTransaction.objects.create(
                    branch=branch,
                    customer=None,
                    sale_invoice=None,
                    points=points,
                    transaction_type='manual_add',
                    notes=f'إضافة يدوية من قبل {request.user.get_full_name()} - {reason}'
                )
                messages.success(request, f'تم إضافة {points} نقطة ولاء للفرع {branch.name}')
                
            elif action == 'deduct':
                if points > branch.loyalty_points_inventory:
                    messages.error(request, f'لا يوجد نقاط كافية. المتوفر: {branch.loyalty_points_inventory}')
                    return redirect('branches_detail', pk=pk)
                
                branch.loyalty_points_inventory -= points
                branch.save()
                
                LoyaltyTransaction.objects.create(
                    branch=branch,
                    customer=None,
                    sale_invoice=None,
                    points=-points,
                    transaction_type='manual_deduct',
                    notes=f'خصم يدوي من قبل {request.user.get_full_name()} - {reason}'
                )
                messages.success(request, f'تم خصم {points} نقطة ولاء من الفرع {branch.name}')
            
            else:
                messages.error(request, 'إجراء غير صالح')
                
        except Exception as e:
            messages.error(request, f'حدث خطأ: {str(e)}')
    
    return redirect('branches_detail', pk=pk) 


@login_required
def product_expiry_list(request):
    user = request.user
    
    if user.can_see_all_data():
        branch_id = request.GET.get('branch', '')
        if branch_id:
            expiry_records = ProductExpiry.objects.filter(branch_id=branch_id).select_related('product', 'branch')
        else:
            expiry_records = ProductExpiry.objects.all().select_related('product', 'branch')
        branches = Branch.objects.filter(is_active=True)
    else:
        if user.branch:
            expiry_records = ProductExpiry.objects.filter(branch=user.branch).select_related('product')
            branches = Branch.objects.filter(pk=user.branch.pk)
        else:
            expiry_records = ProductExpiry.objects.none()
            branches = Branch.objects.none()
    
    status_filter = request.GET.get('status', '')
    today = timezone.now().date()
    three_months_later = today + timedelta(days=90)
    
    if status_filter == 'expired':
        expiry_records = expiry_records.filter(expiry_date__lt=today)
    elif status_filter == 'warning':
        expiry_records = expiry_records.filter(expiry_date__gte=today, expiry_date__lte=three_months_later)
    elif status_filter == 'good':
        expiry_records = expiry_records.filter(expiry_date__gt=three_months_later)
    
    product_query = request.GET.get('product', '')
    if product_query:
        expiry_records = expiry_records.filter(
            Q(product__name__icontains=product_query) |
            Q(product__barcode__icontains=product_query)
        )
    
    expiry_records = expiry_records.order_by('expiry_date')
    
    expired_count = expiry_records.filter(expiry_date__lt=today).count()
    warning_count = expiry_records.filter(expiry_date__gte=today, expiry_date__lte=three_months_later).count()
    good_count = expiry_records.filter(expiry_date__gt=three_months_later).count()
    
    total_quantity = expiry_records.aggregate(total=Sum('quantity'))['total'] or 0
    
    context = {
        'expiry_records': expiry_records,
        'branches': branches,
        'selected_branch': branch_id if user.can_see_all_data() else '',
        'status_filter': status_filter,
        'product_query': product_query,
        'expired_count': expired_count,
        'warning_count': warning_count,
        'good_count': good_count,
        'total_quantity': total_quantity,
    }
    return render(request, 'products/expiry_list.html', context)


@login_required
def product_expiry_create(request):
    user = request.user
    
    if not user.can_see_all_data() and not user.branch:
        messages.error(request, 'لا يمكنك إضافة مراقبة صلاحية')
        return redirect('product_expiry_list')
    
    products = Product.objects.filter(is_active=True)
    
    if user.can_see_all_data():
        branches = Branch.objects.filter(is_active=True)
        selected_branch = request.GET.get('branch', '')
    else:
        branches = Branch.objects.filter(pk=user.branch.pk)
        selected_branch = user.branch.pk if user.branch else ''
    
    if request.method == 'POST':
        product_id = request.POST.get('product')
        branch_id = request.POST.get('branch')
        quantity = request.POST.get('quantity')
        expiry_date = request.POST.get('expiry_date')
        batch_number = request.POST.get('batch_number', '')
        notes = request.POST.get('notes', '')
        
        if not product_id or not branch_id or not quantity or not expiry_date:
            messages.error(request, 'الرجاء ملء جميع الحقول المطلوبة')
            return redirect('product_expiry_create')
        
        try:
            quantity = int(quantity)
            if quantity <= 0:
                messages.error(request, 'الكمية يجب أن تكون أكبر من صفر')
                return redirect('product_expiry_create')
            
            product = get_object_or_404(Product, pk=product_id)
            branch = get_object_or_404(Branch, pk=branch_id)
            
            expiry_record = ProductExpiry.objects.create(
                product=product,
                branch=branch,
                quantity=quantity,
                expiry_date=expiry_date,
                batch_number=batch_number,
                notes=notes,
                created_by=user
            )
            
            ProductExpiryMovement.objects.create(
                expiry_record=expiry_record,
                movement_type='create',
                quantity_before=0,
                quantity_after=quantity,
                notes=f'تم إنشاء مراقبة صلاحية بكمية {quantity}',
                employee=user
            )
            
            messages.success(request, f'تم إضافة مراقبة صلاحية للمنتج {product.name}')
            return redirect('product_expiry_list')
            
        except Exception as e:
            messages.error(request, f'حدث خطأ: {str(e)}')
    
    context = {
        'products': products,
        'branches': branches,
        'selected_branch': selected_branch,
    }
    return render(request, 'products/expiry_create.html', context)


@login_required
def product_expiry_edit(request, pk):
    expiry = get_object_or_404(ProductExpiry, pk=pk)
    user = request.user
    
    if not user.can_see_all_data():
        if user.branch != expiry.branch:
            messages.error(request, 'غير مصرح لك بتعديل هذه المراقبة')
            return redirect('product_expiry_list')
    
    products = Product.objects.filter(is_active=True)
    
    if request.method == 'POST':
        product_id = request.POST.get('product')
        quantity = request.POST.get('quantity')
        expiry_date = request.POST.get('expiry_date')
        batch_number = request.POST.get('batch_number', '')
        notes = request.POST.get('notes', '')
        
        if not product_id or not quantity or not expiry_date:
            messages.error(request, 'الرجاء ملء جميع الحقول المطلوبة')
            return redirect('product_expiry_edit', pk=pk)
        
        try:
            quantity = int(quantity)
            if quantity <= 0:
                messages.error(request, 'الكمية يجب أن تكون أكبر من صفر')
                return redirect('product_expiry_edit', pk=pk)
            
            old_quantity = expiry.quantity
            
            expiry.product_id = product_id
            expiry.quantity = quantity
            expiry.expiry_date = expiry_date
            expiry.batch_number = batch_number
            expiry.notes = notes
            expiry.save()
            
            ProductExpiryMovement.objects.create(
                expiry_record=expiry,
                movement_type='update',
                quantity_before=old_quantity,
                quantity_after=quantity,
                notes=f'تم تعديل الكمية من {old_quantity} إلى {quantity}',
                employee=user
            )
            
            messages.success(request, 'تم تحديث مراقبة الصلاحية بنجاح')
            return redirect('product_expiry_list')
            
        except Exception as e:
            messages.error(request, f'حدث خطأ: {str(e)}')
    
    context = {
        'expiry': expiry,
        'products': products,
    }
    return render(request, 'products/expiry_edit.html', context)


@login_required
def product_expiry_delete(request, pk):
    expiry = get_object_or_404(ProductExpiry, pk=pk)
    user = request.user
    
    if not user.can_see_all_data():
        if user.branch != expiry.branch:
            messages.error(request, 'غير مصرح لك بحذف هذه المراقبة')
            return redirect('product_expiry_list')
    
    if request.method == 'POST':
        try:
            ProductExpiryMovement.objects.create(
                expiry_record=expiry,
                movement_type='delete',
                quantity_before=expiry.quantity,
                quantity_after=0,
                notes='تم حذف مراقبة الصلاحية',
                employee=user
            )
            
            expiry.delete()
            messages.success(request, 'تم حذف مراقبة الصلاحية بنجاح')
            
        except Exception as e:
            messages.error(request, f'حدث خطأ: {str(e)}')
        
        return redirect('product_expiry_list')
    
    context = {'expiry': expiry}
    return render(request, 'products/expiry_confirm_delete.html', context)


@login_required
def product_expiry_consume(request, pk):
    expiry = get_object_or_404(ProductExpiry, pk=pk)
    user = request.user
    
    if not user.can_see_all_data():
        if user.branch != expiry.branch:
            messages.error(request, 'غير مصرح لك بتعديل هذه المراقبة')
            return redirect('product_expiry_list')
    
    if request.method == 'POST':
        consume_quantity = request.POST.get('consume_quantity')
        
        try:
            consume_quantity = int(consume_quantity)
            if consume_quantity <= 0:
                messages.error(request, 'الكمية المستهلكة يجب أن تكون أكبر من صفر')
                return redirect('product_expiry_consume', pk=pk)
            
            if consume_quantity > expiry.quantity:
                messages.error(request, f'الكمية المستهلكة أكبر من المتوفر ({expiry.quantity})')
                return redirect('product_expiry_consume', pk=pk)
            
            old_quantity = expiry.quantity
            expiry.quantity -= consume_quantity
            expiry.save()
            
            ProductExpiryMovement.objects.create(
                expiry_record=expiry,
                movement_type='consume',
                quantity_before=old_quantity,
                quantity_after=expiry.quantity,
                notes=f'تم استهلاك {consume_quantity} وحدة',
                employee=user
            )
            
            if expiry.quantity == 0:
                expiry.delete()
                messages.success(request, 'تم استهلاك الكمية بالكامل وتم حذف المراقبة')
            else:
                messages.success(request, f'تم استهلاك {consume_quantity} وحدة من المنتج')
                
        except Exception as e:
            messages.error(request, f'حدث خطأ: {str(e)}')
        
        return redirect('product_expiry_list')
    
    context = {'expiry': expiry}
    return render(request, 'products/expiry_consume.html', context)


@login_required
def product_expiry_movements(request, pk):
    expiry = get_object_or_404(ProductExpiry, pk=pk)
    user = request.user
    
    if not user.can_see_all_data():
        if user.branch != expiry.branch:
            messages.error(request, 'غير مصرح لك بعرض هذه الحركات')
            return redirect('product_expiry_list')
    
    movements = expiry.movements.all().order_by('-created_at')
    
    context = {
        'expiry': expiry,
        'movements': movements,
    }
    return render(request, 'products/expiry_movements.html', context)


@login_required
def product_expiry_dashboard(request):
    user = request.user
    today = timezone.now().date()
    three_months_later = today + timedelta(days=90)
    
    if user.can_see_all_data():
        branch_id = request.GET.get('branch', '')
        if branch_id:
            expiry_records = ProductExpiry.objects.filter(branch_id=branch_id)
        else:
            expiry_records = ProductExpiry.objects.all()
        branches = Branch.objects.filter(is_active=True)
    else:
        if user.branch:
            expiry_records = ProductExpiry.objects.filter(branch=user.branch)
            branches = Branch.objects.filter(pk=user.branch.pk)
        else:
            expiry_records = ProductExpiry.objects.none()
            branches = Branch.objects.none()
    
    expired_records = expiry_records.filter(expiry_date__lt=today)
    warning_records = expiry_records.filter(expiry_date__gte=today, expiry_date__lte=three_months_later)
    
    expired_total_quantity = expired_records.aggregate(total=Sum('quantity'))['total'] or 0
    warning_total_quantity = warning_records.aggregate(total=Sum('quantity'))['total'] or 0
    
    warning_by_month = []
    for i in range(1, 4):
        month_start = today + timedelta(days=(i-1)*30)
        month_end = today + timedelta(days=i*30)
        month_records = expiry_records.filter(expiry_date__gte=month_start, expiry_date__lte=month_end)
        warning_by_month.append({
            'month': i,
            'count': month_records.count(),
            'quantity': month_records.aggregate(total=Sum('quantity'))['total'] or 0,
        })
    
    nearest_expiry = expiry_records.filter(expiry_date__gte=today).order_by('expiry_date').first()
    
    context = {
        'expired_count': expired_records.count(),
        'expired_quantity': expired_total_quantity,
        'warning_count': warning_records.count(),
        'warning_quantity': warning_total_quantity,
        'warning_by_month': warning_by_month,
        'nearest_expiry': nearest_expiry,
        'branches': branches,
        'selected_branch': branch_id if user.can_see_all_data() else '',
    }
    return render(request, 'products/expiry_dashboard.html', context)          