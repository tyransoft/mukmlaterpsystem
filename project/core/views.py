from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import *
from .forms import *
from django.db import transaction
from django.db.models import Q , Sum ,F,Count,DecimalField, ExpressionWrapper
from decimal import Decimal
from django.core.paginator import Paginator
from .utils import *
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import logging ,  traceback








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
    
    total_loyalty_amount = CustomerLoyaltyReward.objects.aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    total_loyalty_points = CustomerLoyaltyReward.objects.aggregate(
        total=Sum('points')
    )['total'] or 0
    
    month_loyalty_amount = CustomerLoyaltyReward.objects.filter(
        reward_date__date__gte=month_start
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    today_loyalty_amount = CustomerLoyaltyReward.objects.filter(
        reward_date__date=today
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    net_sales = total_sales - total_loyalty_amount
    
    net_month_sales = month_sales - month_loyalty_amount
    
    net_today_sales = today_sales - today_loyalty_amount
    
    net_profit = net_sales - total_purchases
    
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
        
        branch_loyalty = CustomerLoyaltyReward.objects.filter(
            branch=branch,
            reward_date__date__gte=month_start
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        net_branch_sales = sales - branch_loyalty
        
        commission = float(net_branch_sales) * float(branch.commission_percentage) / 100
        
        branch_sales.append({
            'branch': branch, 
            'sales': sales,
            'loyalty': branch_loyalty,
            'net_sales': net_branch_sales,
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
        'total_loyalty_amount': total_loyalty_amount,
        'total_loyalty_points': total_loyalty_points,
        'month_loyalty_amount': month_loyalty_amount,
        'today_loyalty_amount': today_loyalty_amount,
        'net_sales': net_sales,
        'net_month_sales': net_month_sales,
        'net_today_sales': net_today_sales,
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
   
    if not user.branch:
        return redirect('/')
    
    today = timezone.now().date()
    month_start = today.replace(day=1)
    if user.can_see_all_data() and branch.is_main:
        branch = Branch.objects.get(id=request.GET.get('branch_id', branch.id)) 
    else:
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
    
    today_loyalty_amount = CustomerLoyaltyReward.objects.filter(
        branch=branch,
        reward_date__date=today
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    today_loyalty_points = CustomerLoyaltyReward.objects.filter(
        branch=branch,
        reward_date__date=today
    ).aggregate(total=Sum('points'))['total'] or 0
    
    month_loyalty_amount = CustomerLoyaltyReward.objects.filter(
        branch=branch,
        reward_date__date__gte=month_start
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    month_loyalty_points = CustomerLoyaltyReward.objects.filter(
        branch=branch,
        reward_date__date__gte=month_start
    ).aggregate(total=Sum('points'))['total'] or 0
    
    total_loyalty_amount = CustomerLoyaltyReward.objects.filter(
        branch=branch
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    total_loyalty_points = CustomerLoyaltyReward.objects.filter(
        branch=branch
    ).aggregate(total=Sum('points'))['total'] or 0
    
    net_today_sales = today_sales - today_loyalty_amount
    
    net_month_sales = month_sales - month_loyalty_amount
    
    commission = float(net_month_sales) * float(branch.commission_percentage) / 100
    
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
        
        'today_loyalty_amount': today_loyalty_amount,
        'today_loyalty_points': today_loyalty_points,
        'month_loyalty_amount': month_loyalty_amount,
        'month_loyalty_points': month_loyalty_points,
        'total_loyalty_amount': total_loyalty_amount,
        'total_loyalty_points': total_loyalty_points,
        
        'net_today_sales': net_today_sales,
        'net_month_sales': net_month_sales,
        
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
   
    delivery_date_filter = {}
    reward_date_filter = {}
    if date_from:
      delivery_date_filter['delivery_date__date__gte'] = date_from

    if date_to:
      delivery_date_filter['delivery_date__date__lte'] = date_to

    if date_from:
       reward_date_filter['reward_date__date__gte'] = date_from

    if date_to:
      reward_date_filter['reward_date__date__lte'] = date_to


    sales_query = SaleInvoice.objects.filter(sale_type='customer', status='confirmed', **date_filter)
    total_revenue = sales_query.aggregate(total=Sum('total'))['total'] or 0
    total_branch_loyalty = (
      CustomerLoyaltyReward.objects
      .filter(**reward_date_filter)
      .aggregate(total=Sum('amount'))['total'] or Decimal('0')
    )

    net_revenue = total_revenue - total_branch_loyalty    
    purchase_query = PurchaseInvoice.objects.filter(status='confirmed', is_auto_generated=False, **date_filter)
    total_cost = purchase_query.aggregate(total=Sum('total'))['total'] or 0
    
    cogs = Decimal(0)
    for invoice in sales_query.prefetch_related('items__product'):
        for item in invoice.items.all():
            cost_price = (
            item.cost_price
               if item.cost_price > 0
               else item.product.cost_price
              )

            cogs += item.quantity * cost_price
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
    
    branch_debts = SaleInvoice.objects.filter(
      sale_type='customer',
      status='confirmed',
      branch__is_main=False,
      **date_filter
      ).values(
         'branch__id', 'branch__name', 'branch__commission_percentage'
      ).annotate(
        total_sales=Sum('total'),
        total_commission=Sum('branch_commission'),
       ).order_by('-total_sales')

    branch_loyalties = CustomerLoyaltyReward.objects.filter(
      branch__is_main=False,
       **reward_date_filter   
    ).values('branch__id').annotate(
      total_loyalty=Sum('amount'),
      total_points=Sum('points')
    )

    branch_payments = BranchSalesDelivery.objects.filter(
      **delivery_date_filter
    ).values('branch__id', 'branch__name').annotate(
        total_paid=Sum('amount')
    )


    all_branches = Branch.objects.filter(
      is_main=False
        ).values(
       'id', 'name', 'commission_percentage'
        ).order_by('name')

    sales_by_branch = SaleInvoice.objects.filter(
      sale_type='customer',
      status='confirmed',
      branch__is_main=False,
      **date_filter
        ).values('branch_id').annotate(
       total_sales=Sum('total'),
      total_commission=Sum('branch_commission'),
    )

    sales_map = {
      row['branch_id']: row
     for row in sales_by_branch
    }

    loyalties_by_branch = CustomerLoyaltyReward.objects.filter(
      branch__is_main=False,
       **reward_date_filter
      ).values('branch_id').annotate(
       total_loyalty=Sum('amount'),
      total_points=Sum('points'),
    )

    loyalty_map = {
      row['branch_id']: row
      for row in loyalties_by_branch
    }

    payments_by_branch = BranchSalesDelivery.objects.filter(
      branch__is_main=False,
      **delivery_date_filter
    ).values('branch_id').annotate(
      total_paid=Sum('amount')
    )

    payments_map = {
      row['branch_id']: row['total_paid'] or Decimal('0')
      for row in payments_by_branch
    }

    branch_debt_list = []

    for branch in all_branches:
        branch_id = branch['id']

        sales_data = sales_map.get(branch_id, {})
        loyalty_data = loyalty_map.get(branch_id, {})

        total_sales = sales_data.get(
                'total_sales'
        ) or Decimal('0')

        total_commission = sales_data.get(
                'total_commission'
        ) or Decimal('0')

        branch_loyalty_amount = loyalty_data.get(
                'total_loyalty'
        ) or Decimal('0')

        branch_loyalty_points = loyalty_data.get(
                'total_points'
        ) or 0

        paid = payments_map.get(
                branch_id,
                Decimal('0')
        )

        net_sales = total_sales - branch_loyalty_amount

        amount_due = net_sales - total_commission

        remaining = amount_due - paid

        branch_debt_list.append({
                'id': branch_id,
                'name': branch['name'],
                'commission_percentage': branch['commission_percentage'],
                'total_sales': total_sales,
                'loyalty': branch_loyalty_amount,
                'loyalty_points': branch_loyalty_points,
                'net_sales': net_sales,
                'commission': total_commission,
                'amount_due': amount_due,
                'paid': paid,
                'remaining': remaining,
        })

    total_unpaid_commissions = sum(
    (
        b['remaining']
        for b in branch_debt_list
    ),
    Decimal('0')
)

    branch_deliveries_query = BranchSalesDelivery.objects.filter(**delivery_date_filter)
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
    
    delivery_sales_query = sales_query.filter(is_delivery=True)
    total_delivery_sales = delivery_sales_query.aggregate(total=Sum('total'))['total'] or 0
    delivery_sales_count = delivery_sales_query.count() 
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
        'total_delivery_sales': total_delivery_sales,
        'delivery_sales_count': delivery_sales_count,
        'sales_payment_methods_list': sales_payment_methods_list,
        'net_revenue':net_revenue,
        'total_branch_loyalty':total_branch_loyalty,
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
        form = UserEditForm(request.POST, instance=user, request=request)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث بيانات المستخدم بنجاح')
            return redirect('users_list')
    else:
        form = UserEditForm(instance=user, request=request)
    
    return render(request, 'accounts/user_form.html', {
        'form': form, 
        'title': 'تعديل المستخدم', 
        'user_obj': user
    })

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

    today = timezone.localdate()

    date_from = request.GET.get('date_from') or today.replace(day=1).isoformat()
    date_to = request.GET.get('date_to') or today.isoformat()

    sales_query = SaleInvoice.objects.filter(
        branch=branch,
        sale_type='customer',
        status='confirmed',
        created_at__date__gte=date_from,
        created_at__date__lte=date_to
    )

    total_sales = sales_query.aggregate(
        total=Sum('total')
    )['total'] or 0
    branch_loyalty = CustomerLoyaltyReward.objects.filter(
       branch=branch,
       reward_date__date__gte=date_from,
       reward_date__date__lte=date_to
         ).aggregate(
           total=Sum('amount')
          )['total'] or 0

    net_sales = total_sales - branch_loyalty

    total_commission = sales_query.aggregate(
        total=Sum('branch_commission')
    )['total'] or 0

    amount_due_to_main = net_sales - total_commission

    deliveries_query = BranchSalesDelivery.objects.filter(
        branch=branch,
        delivery_date__date__gte=date_from,
        delivery_date__date__lte=date_to
    )

    total_delivered = deliveries_query.aggregate(
        total=Sum('amount')
    )['total'] or 0

    remaining_to_deliver = amount_due_to_main - total_delivered

    period_invoices = sales_query.order_by('-created_at')[:50]

    recent_deliveries = BranchSalesDelivery.objects.filter(
        branch=branch
    ).order_by('-delivery_date')[:10]

    last_delivery = BranchSalesDelivery.objects.filter(
        branch=branch
    ).order_by('-delivery_date').first()

    movement_types = [
        'sale',
        'return_sale',
        'purchase',
        'supply_in',
        'supply_out',
        'adjustment',
        'damage',
        'stocktake',
        'return_supply_out',
    ]

    movements_qs = InventoryMovement.objects.filter(
        branch=branch,
        movement_type__in=movement_types,
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
    )

    product_ids = movements_qs.values_list(
        'product_id',
        flat=True
    ).distinct()

    products_in_movements = Product.objects.filter(
        id__in=product_ids
    ).order_by('name')

    inventory_comparison = []

    for product in products_in_movements:
        before_filter = InventoryMovement.objects.filter(
            branch=branch,
            product=product,
            created_at__date__lt=date_from,
        )

        last_before_movement = before_filter.order_by(
            '-created_at',
            '-id'
        ).first()

        if last_before_movement:
            stock_before = last_before_movement.quantity_after
        else:
            first_in_period = movements_qs.filter(
                product=product
            ).order_by(
                'created_at',
                'id'
            ).first()

            if first_in_period:
                stock_before = first_in_period.quantity_before
            else:
                stock_before = 0

        incoming = movements_qs.filter(
            product=product,
            quantity__gt=0
        ).exclude(
            movement_type='return_sale'
        ).aggregate(
            total=Sum('quantity')
        )['total'] or 0

        sold_to_customers = abs(
            movements_qs.filter(
                product=product,
                movement_type='sale',
                quantity__lt=0
            ).aggregate(
                total=Sum('quantity')
            )['total'] or 0
        )

        supplied_out = abs(
            movements_qs.filter(
                product=product,
                movement_type='supply_out',
                quantity__lt=0
            ).aggregate(
                total=Sum('quantity')
            )['total'] or 0
        )

        damaged_out = abs(
            movements_qs.filter(
                product=product,
                movement_type__in=['damage', 'stocktake', 'return_supply_out'],
                quantity__lt=0
            ).aggregate(
                total=Sum('quantity')
            )['total'] or 0
        )

        damaged_in = movements_qs.filter(
            product=product,
            movement_type__in=['damage', 'stocktake', 'return_sale'],
            quantity__gt=0
        ).aggregate(
            total=Sum('quantity')
        )['total'] or 0

        net_movement = movements_qs.filter(
            product=product
        ).aggregate(
            total=Sum('quantity')
        )['total'] or 0

        expected_stock = stock_before + net_movement

        current_inv = BranchInventory.objects.filter(
            branch=branch,
            product=product
        ).first()

        current_stock = current_inv.quantity if current_inv else 0

        difference = current_stock - expected_stock

        if difference == 0:
            stock_status = 'match'
        elif difference > 0:
            stock_status = 'surplus'
        else:
            stock_status = 'shortage'

        inventory_comparison.append({
            'product_id': product.id,
            'product_name': product.name,
            'product_barcode': product.barcode,
            'stock_before': stock_before,
            'incoming': incoming,
            'sold_to_customers': sold_to_customers,
            'supplied_out': supplied_out,
            'damaged_out': damaged_out,
            'damaged_in': damaged_in,
            'net_movement': net_movement,
            'expected_stock': expected_stock,
            'current_stock': current_stock,
            'difference': difference,
            'stock_status': stock_status,
        })

    inventory_comparison.sort(
        key=lambda x: x['product_name']
    )

    total_products_count = len(inventory_comparison)

    matched_count = sum(
        1 for x in inventory_comparison
        if x['stock_status'] == 'match'
    )

    surplus_count = sum(
        1 for x in inventory_comparison
        if x['stock_status'] == 'surplus'
    )

    shortage_count = sum(
        1 for x in inventory_comparison
        if x['stock_status'] == 'shortage'
    )

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
        'inventory_comparison': inventory_comparison,
        'total_products_count': total_products_count,
        'matched_count': matched_count,
        'surplus_count': surplus_count,
        'shortage_count': shortage_count,
        'branch_loyalty': branch_loyalty,
        'net_sales': net_sales,
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
      messages.error(request, 'حسابك غير مرتبط بفرع. يرجى ربطه بفرع أولاً.')
      return redirect('dashboard_home')

    user_branch = request.user.branch

    if not user_branch.is_active:
      messages.error(request, 'الفرع المرتبط بحسابك غير نشط.')
      return redirect('dashboard_home')

    allowed_sale_types = (
      ['customer', 'branch']
      if user_branch.is_main
       else ['customer']
     )
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                sale_type = request.POST.get('sale_type')

                if sale_type not in allowed_sale_types:
                  raise ValidationErr('نوع عملية البيع غير مسموح لهذا الفرع.')

                target_branch = None

                if sale_type == 'branch':
                    target_branch_id = request.POST.get('target_branch')

                    if not target_branch_id:
                        raise ValidationErr('يرجى تحديد الفرع المستهدف.')
 
                    target_branch = Branch.objects.filter(
                         pk=target_branch_id,
                         is_active=True,
                        ).first()

                    if not target_branch:
                       raise ValidationErr('الفرع المستهدف غير موجود أو غير نشط.')

                    if target_branch.pk == user_branch.pk:
                           raise ValidationErr('لا يمكن توريد البضاعة إلى نفس الفرع.')
                payment_method_id = request.POST.get('payment_method')
                payment_method = None
                if payment_method_id:
                    payment_method = PaymentMethod.objects.filter(id=payment_method_id, is_active=True).first()
                
                is_cash_customer = request.POST.get('is_cash_customer') == 'on'
                is_delivery = request.POST.get('is_delivery') == 'on'
                delivery_company = request.POST.get('delivery_company', '').strip()
                
                
                customer_id = None
                if is_cash_customer:
                    pass
                else:
                    customer_id = request.POST.get('customer') or None
                    if not customer_id and sale_type == 'customer':
                        raise ValidationErr('الرجاء اختيار عميل')
                
                invoice = SaleInvoice(
                    sale_type=sale_type,
                    branch=user_branch,
                    target_branch=target_branch,
                    customer_id=customer_id,
                    discount=Decimal('0'),
                    paid_amount=Decimal(request.POST.get('paid_amount', 0) or 0),
                    due_date=request.POST.get('due_date') or None,
                    notes=request.POST.get('notes', ''),
                    employee=request.user,
                    status='draft',
                    subtotal=0,
                    total=0,
                    payment_method=payment_method,
                    is_cash_customer=is_cash_customer,
                    is_delivery=is_delivery,
                )
                invoice.notes = invoice.notes
                invoice.save()
                
                subtotal = Decimal(0)
                total_unit_discount = Decimal(0)
                items_added = False
                
                for key, value in request.POST.items():
                    if key.endswith('_id'):
                        product_id = value
                        prefix = key.replace('_id', '')
                        quantity = int(request.POST.get(f'{prefix}_quantity', 0) or 0)
                        unit_price = Decimal(request.POST.get(f'{prefix}_price', 0) or 0)
                        unit_discount = Decimal(request.POST.get(f'{prefix}_discount', 0) or 0)
                        
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
                            
                            if unit_discount < 0:
                                raise ValidationErr(
                                    f'خصم الوحدة للمنتج {product.name} لا يمكن أن يكون سالباً'
                                )
                          
                            
                            net_unit_price = unit_price - unit_discount
                            total_price = unit_price * quantity
                            subtotal += total_price

                            total_unit_discount += unit_discount * quantity

                            SaleInvoiceItem.objects.create(
                                invoice=invoice,
                                product=product,
                                quantity=quantity,
                                unit_price=unit_price,
                                unit_discount=unit_discount,
                                total_price=(
                                (unit_price - unit_discount) * quantity
                                )
                            )
                
                if not items_added:
                    raise ValidationErr('الرجاء إضافة منتج واحد على الأقل للفاتورة')
                
                invoice.subtotal = subtotal
                invoice.discount = total_unit_discount
                invoice.total = subtotal - total_unit_discount
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
    
    branches = Branch.objects.filter(
          is_active=True
          ).exclude(
             pk=user_branch.pk
             ) if user_branch.is_main else Branch.objects.none() 
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
            'selling_price': inventory.product.get_final_price(user_branch),
            'loyalty_points': inventory.product.loyalty_points,
            'stock': inventory.quantity,
            'barcode': inventory.product.barcode,
            'cost_price': inventory.product.cost_price
        })
    
    products_with_stock.sort(key=lambda x: x['name'])
    
    context = {
        'branches': branches,
        'customers': Customer.objects.filter(is_active=True, created_branch=user_branch),
        'allowed_sale_types': allowed_sale_types,
        'user_branch': user_branch,
        'payment_methods': payment_methods,
        'products': products_with_stock,
    }
    return render(request, 'invoices/sale_invoice_create.html', context)

@login_required
def purchase_invoice_create(request):
    if not request.user.branch:
     messages.error(
        request,
        'حسابك غير مرتبط بفرع. يرجى ربطه بفرع أولاً.'
      )
     return redirect('dashboard_home')

    if not request.user.branch.is_active:
       messages.error(request, 'الفرع المرتبط بحسابك غير نشط.')
       return redirect('dashboard_home')
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
                    messages.info(request, 'تم تأكيد الفاتورة وإضافة النقاط  للفرع الرئيسي')
                
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
    user_branch = request.user.branch

    customers = Customer.objects.filter(is_active=True, created_branch=user_branch)
    if query:
        customers = customers.filter(
            Q(full_name__icontains=query) | Q(phone__icontains=query)
        )
    return render(request, 'customers/list.html', {'customers': customers, 'query': query})


@login_required
def customer_create(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST,branch=request.user.branch)
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

    total_loyalty_points = CustomerLoyaltyReward.objects.filter(
        customer=customer
    ).aggregate(total=Sum('points'))['total'] or 0 

    total_loyalty_amount = CustomerLoyaltyReward.objects.filter(
        customer=customer
    ).aggregate(total=Sum('amount'))['total'] or 0

    total_points_earned = LoyaltyTransfer.objects.filter(
        customer=customer,
        status='transferred'
    ).aggregate(total=Sum('points'))['total'] or 0
    
    return render(request, 'customers/detail.html', {
        'customer': customer,
        'invoices': invoices,
        'pending_transfers': pending_transfers,
        'total_purchases': total_purchases,
        'total_loyalty_points': total_loyalty_points,
        'total_loyalty_amount': total_loyalty_amount,
        'total_points_earned': total_points_earned,
    })


@login_required
def customer_search_ajax(request):
    user_branch = request.user.branch

    query = request.GET.get('q', '')
    customers = Customer.objects.filter(
        Q(full_name__icontains=query) | Q(phone__icontains=query) | Q(customer_id__icontains=query),
        is_active=True,created_branch=user_branch
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
            url = reverse('inventory_list')
            return redirect(f'{url}?branch={branch_id}')
    
    inventory = BranchInventory.objects.select_related('product').filter(
        branch=branch
    ).order_by('product__name')
    
    totals = inventory.aggregate(
        total_cost_value=Sum(
            ExpressionWrapper(
                F('quantity') * F('product__cost_price'),
                output_field=DecimalField(max_digits=15, decimal_places=2)
            )
        ),
        total_selling_value=Sum(
            ExpressionWrapper(
                F('quantity') * F('product__selling_price'),
                output_field=DecimalField(max_digits=15, decimal_places=2)
            )
        ),
        total_loyalty_points=Sum(
            ExpressionWrapper(
                F('quantity') * F('product__loyalty_points'),
                output_field=DecimalField(max_digits=15, decimal_places=2)
            )
        ),
        total_quantity=Sum('quantity'),
    )
    
    total_cost_value = totals['total_cost_value'] or Decimal('0')
    total_selling_value = totals['total_selling_value'] or Decimal('0')
    total_loyalty_points = totals['total_loyalty_points'] or Decimal('0')
    total_quantity = totals['total_quantity'] or 0
    total_profit = total_selling_value - total_cost_value
    
    return render(request, 'inventory/print.html', {
        'inventory': inventory,
        'branch': branch,
        'now': timezone.now(),
        'total_cost_value': total_cost_value,
        'total_selling_value': total_selling_value,
        'total_loyalty_points': total_loyalty_points,
        'total_quantity': total_quantity,
        'total_profit': total_profit,
    })


@login_required
def inventory_stocktake(request):
    user = request.user

    branch_id = request.GET.get('branch') or request.POST.get('branch')

    if user.can_see_all_data() and branch_id:
        branch = get_object_or_404(Branch, pk=branch_id)
    elif user.branch:
        branch = user.branch
    else:
        messages.error(request, 'لا يوجد فرع محدد لإجراء الجرد')
        return redirect('dashboard_home')

    if request.method == 'POST':
        try:
            with transaction.atomic():
                branch = Branch.objects.select_for_update().get(pk=branch.pk)

                inventory_items = (
                    BranchInventory.objects
                    .select_for_update()
                    .select_related('product')
                    .filter(branch=branch)
                )

                points_delta_total = Decimal('0')
                changes_count = 0

                for item in inventory_items:
                    posted_quantity = request.POST.get(
                        f'quantity_{item.pk}'
                    )

                    if posted_quantity is None:
                        continue

                    try:
                        new_quantity = int(posted_quantity)
                    except (ValueError, TypeError):
                        raise ValueError(
                            f'الكمية المدخلة للمنتج {item.product.name} غير صحيحة'
                        )

                    if new_quantity < 0:
                        raise ValueError(
                            f'كمية المنتج {item.product.name} لا يمكن أن تكون سالبة'
                        )

                    old_quantity = item.quantity
                    difference = new_quantity - old_quantity

                    if difference == 0:
                        continue

                    points_per_unit = Decimal(
                        str(item.product.loyalty_points or 0)
                    )

                    points_difference = (
                        Decimal(difference) * points_per_unit
                    )

                    InventoryMovement.objects.create(
                        branch=branch,
                        product=item.product,
                        movement_type='stocktake',
                        quantity=difference,
                        quantity_before=old_quantity,
                        quantity_after=new_quantity,
                        notes=(
                            f'جرد دوري - تعديل من {old_quantity} '
                            f'إلى {new_quantity}'
                        ),
                        employee=user,
                    )

                    item.quantity = new_quantity
                    item.save(update_fields=['quantity'])

                    points_delta_total += points_difference
                    changes_count += 1

                if points_delta_total != 0:
                    branch.loyalty_points_inventory = (
                        branch.loyalty_points_inventory
                        + points_delta_total
                    )
                    branch.save(
                        update_fields=['loyalty_points_inventory', 'updated_at']
                    )

            messages.success(
                request,
                f'تم حفظ الجرد بنجاح. عدد المنتجات المعدلة: {changes_count}. '
            )
            return redirect('inventory_list')

        except ValueError as e:
            messages.error(request, str(e))

    inventory_items = (
        BranchInventory.objects
        .select_related('product')
        .filter(branch=branch)
    )

    return render(request, 'inventory/stocktake.html', {
        'inventory_items': inventory_items,
        'branch': branch,
        'branchname': branch.name,
    })



@login_required
def inventory_damage(request, pk):
    inv = get_object_or_404(
        BranchInventory.objects.select_related('branch', 'product'),
        pk=pk
    )

    user = request.user

    if not user.can_see_all_data():
        if not user.branch or user.branch_id != inv.branch_id:
            messages.error(request, 'ليس لديك صلاحية لتسجيل تلف هذا المخزون')
            url = reverse('inventory_list')
            return redirect(f'{url}?branch={inv.branch_id}')

    if request.method == 'POST':
        try:
            quantity = int(request.POST.get('quantity', 0))
            notes = request.POST.get('notes', '').strip()

            if quantity <= 0:
                messages.error(request, 'الكمية يجب أن تكون أكبر من صفر')

            else:
                with transaction.atomic():
                    branch = Branch.objects.select_for_update().get(
                        pk=inv.branch
                    )

                    inv = (
                        BranchInventory.objects
                        .select_for_update()
                        .select_related('product')
                        .get(pk=pk)
                    )

                    if quantity > inv.quantity:
                        raise ValueError(
                            f'الكمية المدخلة أكبر من المتوفر ({inv.quantity})'
                        )

                    old_quantity = inv.quantity
                    new_quantity = old_quantity - quantity

                    points_per_unit = Decimal(
                        str(inv.product.loyalty_points or 0)
                    )

                    points_to_deduct = Decimal(quantity) * points_per_unit

                    InventoryMovement.objects.create(
                        branch=branch,
                        product=inv.product,
                        movement_type='damage',
                        quantity=-quantity,
                        quantity_before=old_quantity,
                        quantity_after=new_quantity,
                        notes=f'تلف - {notes}' if notes else 'تلف',
                        employee=user,
                    )

                    inv.quantity = new_quantity
                    inv.save(update_fields=['quantity'])

                    branch.loyalty_points_inventory -= points_to_deduct
                    branch.save(
                        update_fields=['loyalty_points_inventory', 'updated_at']
                    )

                messages.success(
                    request,
                    f'تم تسجيل تلف {quantity} وحدة من {inv.product.name}. '
                    f'تم خصم {points_to_deduct} نقطة من رصيد الفرع.'
                )

                url = reverse('inventory_list')
                return redirect(f'{url}?branch={inv.branch}')

        except ValueError as e:
            messages.error(request, str(e))

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
        messages.error(request, 'هذه الصفحة مخصصة لموظفي النقاط  فقط')
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
def export_pending_transfers(request):
    if not (request.user.is_loyalty_employee() or request.user.can_see_all_data()):
        messages.error(request, 'هذه الصفحة مخصصة لموظفي النقاط فقط')
        return redirect('dashboard_home')

    branch_id = request.GET.get('branch', '')

    transfers = LoyaltyTransfer.objects.filter(
        status='pending'
    ).select_related(
        'customer',
        'branch',
        'sale_invoice'
    ).order_by('-created_at')

    if branch_id:
        transfers = transfers.filter(branch_id=branch_id)

    transfers = list(transfers)

    if not transfers:
        messages.warning(request, 'لا توجد نقاط معلقة للتصدير')
        return redirect('loyalty_pending')

    wb = generate_loyalty_transfer_excel(
        transfers,
        'pending'
    )

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    if branch_id:
        filename = f'النقاط_المعلقة_فرع_{branch_id}_{timestamp}.xlsx'
    else:
        filename = f'النقاط_المعلقة_كل_الفروع_{timestamp}.xlsx'

    with transaction.atomic():
        for transfer in transfers:
            transfer.mark_as_transferred(request.user)

    return create_excel_response(wb, filename)


@login_required
def export_transfer_history(request):
    if not (request.user.is_loyalty_employee() or request.user.can_see_all_data()):
        messages.error(request, 'هذه الصفحة مخصصة لموظفي النقاط فقط')
        return redirect('dashboard_home')

    branch_id = request.GET.get('branch', '')

    transfers = LoyaltyTransfer.objects.filter(
        status='transferred'
    ).select_related(
        'customer',
        'branch',
        'transferred_by',
        'sale_invoice'
    ).order_by('-transfer_date')

    if branch_id:
        transfers = transfers.filter(branch_id=branch_id)

    transfers = list(transfers)

    if not transfers:
        messages.warning(request, 'لا يوجد سجل تحويلات للتصدير')
        return redirect('loyalty_history')

    wb = generate_loyalty_transfer_excel(
        transfers,
        'history'
    )

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    if branch_id:
        filename = f'سجل_تحويلات_فرع_{branch_id}_{timestamp}.xlsx'
    else:
        filename = f'سجل_تحويلات_كل_الفروع_{timestamp}.xlsx'

    return create_excel_response(wb, filename)



@login_required
def product_list(request):
    query = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    products = Product.objects.select_related('category').filter(is_active=True)
    if query:
        products = products.filter(Q(name__icontains=query)  | Q(barcode__icontains=query))
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

    invoices = SaleInvoice.objects.select_related(
        'branch',
        'target_branch',
        'customer',
        'employee'
    )

    if not user.can_see_all_data():
        invoices = invoices.filter(branch=user.branch)

    target_branch_id = request.GET.get('target_branch', '')

    if target_branch_id:
        invoices = invoices.filter(
            branch=Branch.objects.get(id=target_branch_id)
        )

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
        'total_amount': invoices.aggregate(
            total=Sum('total')
        )['total'] or 0,

        'draft_count': invoices.filter(
            status='draft'
        ).count(),

        'confirmed_count': invoices.filter(
            status='confirmed'
        ).count(),
    }

    branches = Branch.objects.all().order_by('name') \
        if user.can_see_all_data() else Branch.objects.filter(pk=user.branch_id)

    context = {
        'invoices': invoices,
        'stats': stats,

        'status_filter': status,
        'sale_type_filter': sale_type,
        'target_branch_filter': target_branch_id,

        'date_from': date_from,
        'date_to': date_to,

        'status_choices': SaleInvoice.STATUS_CHOICES,
        'sale_type_choices': SaleInvoice.SALE_TYPE_CHOICES,

        'branches': branches,
        'is_admin': user.can_see_all_data(),
    }

    return render(
        request,
        'invoices/sale_invoices_list.html',
        context
    )

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
    branch_loyalty = sales_query.aggregate(total=Sum('total_loyalty_points'))['total'] or 0
    net_sales = total_sales - branch_loyalty
    amount_due_to_main = net_sales - total_commission
    
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
        'branch_loyalty': branch_loyalty,
        'net_sales': net_sales,
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
        if not increase_value:
            messages.error(request, 'الرجاء إدخال قيمة الزيادة')
            return redirect('products_bulk_price_update')
        
        try:
            increase_value = Decimal(increase_value)
        except (ValueError, TypeError):
            messages.error(request, 'الرجاء إدخال قيمة رقمية صحيحة')
            return redirect('products_bulk_price_update')
        
        if increase_value <= 0:
            messages.error(request, ' الرجاء إدخال قيمة زيادة أكبر من صفر')
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
            'price': float(inv.product.get_final_price(branch)),
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
def cancel_draft_invoice(request, pk):
    invoice = get_object_or_404(SaleInvoice, pk=pk)

    if invoice.status != 'draft':
        messages.error(request, 'يمكن إلغاء الفواتير المسودة فقط')
        return redirect('sale_invoices_list')

    invoice.status = 'cancelled'
    invoice.save(update_fields=['status'])

    messages.success(request, 'تم إلغاء الفاتورة المسودة بنجاح')
    return redirect('sale_invoices_list')


@login_required
def sale_invoice_return(request, pk):
    if request.method != 'POST':
        invoice = get_object_or_404(SaleInvoice, pk=pk)

        return render(request, 'invoices/sale_invoice_return.html', {
            'invoice': invoice,
            'items': invoice.items.all(),
        })

    user = request.user
    return_type = request.POST.get('return_type')
    selected_items = request.POST.getlist('items')

    if return_type not in ('full', 'partial'):
        messages.error(request, 'نوع المرتجع غير صحيح')
        return redirect('sale_invoice_return', pk=pk)

    if return_type == 'partial' and not selected_items:
        messages.error(request, 'الرجاء اختيار المنتجات التي سيتم إرجاعها')
        return redirect('sale_invoice_return', pk=pk)

   

    try:
        with transaction.atomic():
            invoice = get_object_or_404(
                SaleInvoice.objects.select_for_update(),
                pk=pk,
            )

            if invoice.status != 'confirmed':
                raise ValueError('لا يمكن عمل مرتجع إلا لفاتورة مؤكدة')

            

            branch = (
                Branch.objects.select_for_update()
                .get(pk=invoice.branch_id)
            )

            items = list(
                invoice.items.select_related('product').all()
            )

            if not items:
                raise ValueError('لا توجد منتجات في الفاتورة')

            selected_ids = set(selected_items)

            if return_type == 'partial':
                valid_ids = {str(item.pk) for item in items}

                if not selected_ids.issubset(valid_ids):
                    raise ValueError('تم اختيار منتج غير تابع لهذه الفاتورة')

            return_lines = []
            total_return_amount = Decimal('0')
            returned_points = Decimal('0')

            for item in items:
                if return_type == 'partial' and str(item.pk) not in selected_ids:
                    continue

                if return_type == 'full':
                    return_quantity = item.quantity
                else:
                    try:
                        return_quantity = int(
                            request.POST.get(f'quantity_{item.pk}', 0)
                        )
                    except (ValueError, TypeError):
                        raise ValueError(
                            f'كمية المرتجع غير صحيحة للمنتج {item.product.name}'
                        )

                if return_quantity < 0:
                    raise ValueError('كمية المرتجع لا يمكن أن تكون سالبة')

                if return_quantity == 0:
                    continue

                if return_quantity > item.quantity:
                    raise ValueError(
                        f'كمية المرتجع للمنتج {item.product.name} '
                        f'أكبر من الكمية المتبقية ({item.quantity})'
                    )

                product_points = Decimal(
                    str(item.product.loyalty_points or 0)
                )
                line_points = product_points * Decimal(return_quantity)

                return_amount = (
                    Decimal(str(item.unit_price))
                    * Decimal(return_quantity)
                )

                return_lines.append({
                    'item': item,
                    'quantity': return_quantity,
                    'amount': return_amount,
                    'points': line_points,
                })

                total_return_amount += return_amount
                returned_points += line_points

            if not return_lines:
                raise ValueError('لم يتم تحديد كمية صالحة للإرجاع')

            points_deltas = {}

            def add_points_delta(branch_id, delta):
                points_deltas[branch_id] = (
                    points_deltas.get(branch_id, Decimal('0')) + delta
                )

            for line in return_lines:
                item = line['item']
                qty = line['quantity']
                points = line['points']
                product = item.product

                if invoice.sale_type == 'customer':
                    inventory, created = BranchInventory.objects.get_or_create(
                        branch=branch,
                        product=product,
                        defaults={
                            'quantity': 0,
                            'min_quantity': 5,
                        },
                    )

                    inventory = (
                        BranchInventory.objects.select_for_update()
                        .get(pk=inventory.pk)
                    )

                    old_quantity = inventory.quantity
                    new_quantity = old_quantity + qty

                    inventory.quantity = new_quantity
                    inventory.save(update_fields=['quantity'])

                    InventoryMovement.objects.create(
                        branch=branch,
                        product=product,
                        movement_type='return_sale',
                        quantity=qty,
                        quantity_before=old_quantity,
                        quantity_after=new_quantity,
                        sale_invoice=invoice,
                        employee=user,
                        notes=(
                            f'مرتجع {"كامل" if return_type == "full" else "جزئي"} '
                            f'للفاتورة {invoice.invoice_number}'
                        ),
                    )

                    add_points_delta(branch.pk, points)

                elif invoice.sale_type == 'branch' and invoice.target_branch:
                    target_branch = (
                        Branch.objects.select_for_update()
                        .get(pk=invoice.target_branch_id)
                    )

                    source_inventory, created = (
                        BranchInventory.objects.get_or_create(
                            branch=branch,
                            product=product,
                            defaults={
                                'quantity': 0,
                                'min_quantity': 5,
                            },
                        )
                    )

                    source_inventory = (
                        BranchInventory.objects.select_for_update()
                        .get(pk=source_inventory.pk)
                    )

                    old_source_qty = source_inventory.quantity
                    new_source_qty = old_source_qty + qty

                    source_inventory.quantity = new_source_qty
                    source_inventory.save(update_fields=['quantity'])

                    InventoryMovement.objects.create(
                        branch=branch,
                        product=product,
                        movement_type='return_supply_out',
                        quantity=qty,
                        quantity_before=old_source_qty,
                        quantity_after=new_source_qty,
                        sale_invoice=invoice,
                        employee=user,
                        notes=(
                            f'إرجاع توريد من الفاتورة '
                            f'{invoice.invoice_number}'
                        ),
                    )

                    target_inventory = (
                        BranchInventory.objects.select_for_update()
                        .filter(
                            branch=target_branch,
                            product=product,
                        )
                        .first()
                    )

                    if not target_inventory:
                        raise ValueError(
                            f'المنتج {product.name} غير موجود في مخزون '
                            f'الفرع المستهدف؛ تعذر عكس التوريد'
                        )

                    old_target_qty = target_inventory.quantity

                    if old_target_qty < qty:
                        raise ValueError(
                            f'لا يمكن إلغاء التوريد للمنتج {product.name}: '
                            f'المتوفر في الفرع المستهدف {old_target_qty} '
                            f'والمطلوب إرجاعه {qty}'
                        )

                    new_target_qty = old_target_qty - qty
                    target_inventory.quantity = new_target_qty
                    target_inventory.save(update_fields=['quantity'])

                    InventoryMovement.objects.create(
                        branch=target_branch,
                        product=product,
                        movement_type='return_supply_out',
                        quantity=-qty,
                        quantity_before=old_target_qty,
                        quantity_after=new_target_qty,
                        sale_invoice=invoice,
                        employee=user,
                        notes=(
                            f'إلغاء استلام توريد من الفاتورة '
                            f'{invoice.invoice_number}'
                        ),
                    )

                    add_points_delta(branch.pk, points)
                    add_points_delta(target_branch.pk, -points)

                if return_type == 'partial':
                    item.quantity -= qty
                    item.total_price = (
                        Decimal(str(item.unit_price))
                        * Decimal(item.quantity)
                    )
                    item.save(update_fields=['quantity', 'total_price'])

            for branch_id, delta in points_deltas.items():
                if delta == 0:
                    continue

                points_branch = (
                    Branch.objects.select_for_update().get(pk=branch_id)
                )
                points_branch.loyalty_points_inventory += delta
                points_branch.save(
                    update_fields=[
                        'loyalty_points_inventory',
                        'updated_at',
                    ]
                )

            if (
                invoice.sale_type == 'customer'
                and invoice.customer
                and not invoice.is_cash_customer
                and returned_points > 0
            ):
                loyalty_transfer = (
                    LoyaltyTransfer.objects.select_for_update()
                    .filter(sale_invoice=invoice)
                    .first()
                )

                if loyalty_transfer:
                    if loyalty_transfer.status == 'pending':
                        loyalty_transfer.points = max(
                            Decimal('0'),
                            Decimal(str(loyalty_transfer.points))
                            - returned_points,
                        )
                        loyalty_transfer.save(update_fields=['points'])

                    elif loyalty_transfer.status == 'transferred':
                        customer = (
                            Customer.objects.select_for_update()
                            .get(pk=invoice.customer_id)
                        )

                        

                        LoyaltyTransfer.objects.create(
                            branch=branch,
                            customer=customer,
                            sale_invoice=invoice,
                            points=-returned_points,
                            status='pending',
                            
                        )

            if return_type == 'full':
                if invoice.sale_type == 'branch' and invoice.target_branch:
                    PurchaseInvoice.objects.filter(
                        source_sale_invoice=invoice
                    ).delete()

                invoice.status = 'cancelled'

                if invoice.sale_type == 'customer' and not branch.is_main:
                    commission_rate = (
                        branch.commission_percentage / Decimal('100')
                    )
                    invoice.branch_commission = (
                        invoice.total * commission_rate
                    )

                invoice.save()

                if (
                    invoice.sale_type == 'customer'
                    and invoice.customer
                    and not invoice.is_cash_customer
                ):
                    total_debt = SaleInvoice.objects.filter(
                        customer=invoice.customer,
                        sale_type='customer',
                        status='confirmed',
                    ).aggregate(total=Sum('debt_amount'))['total'] or Decimal('0')

                    invoice.customer.debt_balance = total_debt
                    invoice.customer.save(update_fields=['debt_balance'])

            else:
                invoice.subtotal = max(
                    Decimal('0'),
                    Decimal(str(invoice.subtotal)) - total_return_amount,
                )
                invoice.total = max(
                    Decimal('0'),
                    Decimal(str(invoice.total)) - total_return_amount,
                )

                if invoice.sale_type == 'customer' and not branch.is_main:
                    commission_rate = (
                        branch.commission_percentage / Decimal('100')
                    )
                    invoice.branch_commission = (
                        invoice.total * commission_rate
                    )
                elif invoice.sale_type == 'branch':
                    invoice.branch_commission = Decimal('0')

                if invoice.paid_amount > invoice.total:
                    invoice.paid_amount = invoice.total

                invoice.debt_amount = (
                    invoice.total - invoice.paid_amount
                )

                if invoice.sale_type == 'customer':
                    invoice.total_loyalty_points = max(
                        Decimal('0'),
                        Decimal(str(invoice.total_loyalty_points or 0))
                        - returned_points,
                    )

                invoice.save()

                if (
                    invoice.sale_type == 'customer'
                    and invoice.customer
                    and not invoice.is_cash_customer
                ):
                    total_debt = SaleInvoice.objects.filter(
                        customer=invoice.customer,
                        sale_type='customer',
                        status='confirmed',
                    ).aggregate(total=Sum('debt_amount'))['total'] or Decimal('0')

                    invoice.customer.debt_balance = total_debt
                    invoice.customer.save(update_fields=['debt_balance'])


        messages.success(
            request,
            f'تم عمل المرتجع بنجاح بقيمة {total_return_amount:,.2f} د.ل'
        )
        return redirect('sale_invoices_list')

    except ValueError as e:
        messages.error(request, str(e))
        return redirect('sale_invoice_return', pk=pk)
    
    except Exception as e:
      import logging
      logging.exception(
        "Sale invoice return failed. Invoice ID: %s", pk
      )
      messages.error(
        request,
        f'خطأ أثناء المرتجع: {type(e).__name__}: {e}'
      )
      return redirect('sale_invoice_return', pk=pk)
 
@login_required
def branch_adjust_points(request, pk):
    branch = get_object_or_404(Branch, pk=pk)
    
    if not request.user.can_see_all_data() :
        messages.error(request, 'غير مصرح لك بتعديل النقاط')
        return redirect('branches_detail', pk=pk)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        points = request.POST.get('points')
        reason = request.POST.get('reason', '')
        
        try:
            points = Decimal(str(points))
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
                messages.success(request, f'تم إضافة {points} نقطة  للفرع {branch.name}')
                
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
                messages.success(request, f'تم خصم {points} نقطة من الفرع {branch.name}')
            
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


@login_required
def company_settings_view(request):
    settings = CompanySettings.get_settings()  
    return render(request, 'settings_view.html', {
        'settings': settings
    })

@login_required
def company_settings_edit(request):
    if not request.user.is_main_admin():
        messages.error(request, 'ليس لديك صلاحية لتعديل إعدادات الشركة')
        return redirect('company_settings_view')
    
    settings = CompanySettings.get_settings()
    
    if request.method == 'POST':
        form = CompanySettingsForm(request.POST, request.FILES, instance=settings)
        if form.is_valid():
            form.save()
            messages.success(request, ' تم تحديث إعدادات الشركة بنجاح')
            return redirect('company_settings_view')
        else:
            messages.error(request, ' يرجى تصحيح الأخطاء في النموذج')
    else:
        form = CompanySettingsForm(instance=settings)
    
    return render(request, 'settings_edit.html', {
        'form': form,
        'settings': settings
    })    


@login_required
def loyalty_rewards_list(request):
    branches = Branch.objects.all().order_by('name')

    if request.user.can_see_all_data():
        rewards = CustomerLoyaltyReward.objects.select_related(
            'customer', 'branch', 'created_by'
        ).all()
    else:
        rewards = CustomerLoyaltyReward.objects.select_related(
            'customer', 'branch', 'created_by'
        ).filter(branch=request.user.branch)

    search = request.GET.get('search', '').strip()
    branch_id = request.GET.get('branch', '').strip()

    if search and not branch_id:
        messages.warning(request, 'يجب اختيار الفرع أولاً قبل البحث.')
        rewards = rewards.none()
    else:
        if branch_id:
            rewards = rewards.filter(branch__id=branch_id)

        if search:
            rewards = rewards.filter(
                Q(customer__full_name__icontains=search) |
                Q(customer__phone__icontains=search) |
                Q(customer__customer_id__icontains=search)
            )

    paginator = Paginator(rewards.order_by('-reward_date'), 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'title': 'تسليم عمولة نقاط',
        'page_obj': page_obj,
        'search': search,
        'branch_id': branch_id,
        'branches': branches,
    }
    return render(request, 'customers/loyalty_rewards_list.html', context)

@login_required
def loyalty_reward_add(request):
    user = request.user
    can_select_branch = user.can_see_all_data()

    if can_select_branch:
        branch_id = (
            request.POST.get('branch')
            if request.method == 'POST'
            else request.GET.get('branch')
        )

        branch = Branch.objects.filter(
            pk=branch_id,
            is_active=True,
        ).first() if branch_id else None
    else:
        branch = user.branch

    if request.method == 'POST':
        if not branch:
            messages.error(request, 'يرجى اختيار فرع صحيح')
            return redirect('loyalty_reward_add')

        form = CustomerLoyaltyRewardForm(
            request.POST,
            branch=branch,
        )

        if form.is_valid():
            reward = form.save(commit=False)
            reward.created_by = user
            reward.branch = branch
            reward.save()

            messages.success(request, 'تمت الإضافة بنجاح')
            return redirect('loyalty_rewards_list')

    else:
        form = CustomerLoyaltyRewardForm(branch=branch)

    return render(request, 'customers/loyalty_reward_form.html', {
        'title': 'تسليم عمولة نقاط',
        'form': form,
        'can_select_branch': can_select_branch,
        'branches': Branch.objects.filter(is_active=True),
        'selected_branch': branch,
    })


@login_required
def loyalty_reward_edit(request, pk):
    user = request.user
    can_select_branch = user.can_see_all_data()

    if can_select_branch:
        reward = get_object_or_404(
            CustomerLoyaltyReward,
            pk=pk,
        )
    else:
        reward = get_object_or_404(
            CustomerLoyaltyReward,
            pk=pk,
            branch=user.branch,
        )

    if request.method == 'POST':
        if can_select_branch:
            branch_id = request.POST.get('branch')
            branch = Branch.objects.filter(
                pk=branch_id,
                is_active=True,
            ).first() if branch_id else None
        else:
            branch = reward.branch

        if not branch:
            messages.error(request, 'يرجى اختيار فرع صحيح')
            return redirect('loyalty_reward_edit', pk=pk)

        form = CustomerLoyaltyRewardForm(
            request.POST,
            instance=reward,
            branch=branch,
        )

        if form.is_valid():
            reward = form.save(commit=False)
            reward.branch = branch
            reward.save()

            messages.success(request, 'تم التعديل بنجاح')
            return redirect('loyalty_rewards_list')

    else:
        branch = reward.branch
        form = CustomerLoyaltyRewardForm(
            instance=reward,
            branch=branch,
        )

    return render(request, 'customers/loyalty_reward_form.html', {
        'title': 'تعديل تسليم عمولة نقاط',
        'form': form,
        'reward': reward,
        'can_select_branch': can_select_branch,
        'branches': Branch.objects.filter(is_active=True),
        'selected_branch': branch,
    })


@login_required
def loyalty_reward_delete(request, pk):
    reward = get_object_or_404(CustomerLoyaltyReward, pk=pk)

    if request.method == 'POST':
        reward.delete()
        messages.success(request, 'تم حذف  بنجاح')
        return redirect('loyalty_rewards_list')

    context = {
        'title': 'حذف تسليم عمولة نقاط',
        'reward': reward,
    }
    return render(request, 'customers/loyalty_reward_confirm_delete.html', context)









@login_required
def discount_offer_add(request):
    products = Product.objects.filter(is_active=True).order_by('name')
    branches = Branch.objects.all().order_by('name')

    if request.method == 'POST':
        product_ids = request.POST.getlist('product_ids[]')
        branch_ids = request.POST.getlist('branch_ids[]')

        discount_type = request.POST.get('discount_type', 'percentage')
        try:
            value = float(request.POST.get('value', 0))
        except (TypeError, ValueError):
            value = 0

        is_active = request.POST.get('is_active') == 'on'

        errors = []

        if not product_ids:
            errors.append('يجب اختيار منتج واحد على الأقل.')
        if not branch_ids:
            errors.append('يجب اختيار فرع واحد على الأقل.')
        if value <= 0:
            errors.append('قيمة الخصم يجب أن تكون أكبر من صفر.')
        if discount_type == 'percentage' and value > 100:
            errors.append('نسبة الخصم لا يمكن أن تتجاوز 100%.')

        if not errors:
            for pid in product_ids:
                for bid in branch_ids:
                    if DiscountOffer.objects.filter(
                        product_id=pid,
                        branch_id=bid,
                        is_active=True,
                    ).exists():
                        pname = Product.objects.get(id=pid).name
                        bname = Branch.objects.get(id=bid).name
                        errors.append(f'يوجد بالفعل خصم نشط على "{pname}" في فرع "{bname}".')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            created_count = 0
            with transaction.atomic():
                for pid in product_ids:
                    for bid in branch_ids:
                        DiscountOffer.objects.create(
                            product_id=pid,
                            branch_id=bid,
                            discount_type=discount_type,
                            value=value,
                            is_active=is_active,
                        )
                        created_count += 1

            messages.success(request, f'تم إنشاء {created_count} عرض تخفيض بنجاح.')
            return redirect('discount_offer_add')

    context = {
        'products': products,
        'branches': branches,
        'title': 'إضافة عرض تخفيض جديد',
    }
    return render(request, 'discounts/discount_offer_add.html', context)







@login_required
def discount_offers_list(request):
    offers = DiscountOffer.objects.select_related(
        'product', 'branch'
    ).order_by('-created_at')

    search = request.GET.get('search', '').strip()
    product_id = request.GET.get('product', '').strip()
    branch_id = request.GET.get('branch', '').strip()
    discount_type = request.GET.get('discount_type', '').strip()
    status = request.GET.get('status', '').strip()

    if search:
        offers = offers.filter(
            Q(product__name__icontains=search) |
            Q(branch__name__icontains=search)
        )
    if product_id:
        offers = offers.filter(product_id=product_id)
    if branch_id:
        offers = offers.filter(branch_id=branch_id)
    if discount_type:
        offers = offers.filter(discount_type=discount_type)
    if status == 'active':
        offers = offers.filter(is_active=True)
    elif status == 'inactive':
        offers = offers.filter(is_active=False)

    paginator = Paginator(offers, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'title': 'العروض والخصومات',
        'page_obj': page_obj,
        'search': search,
        'product_id': product_id,
        'branch_id': branch_id,
        'discount_type': discount_type,
        'status': status,
        'products': Product.objects.filter(is_active=True).order_by('name'),
        'branches': Branch.objects.all().order_by('name'),
        'discount_types': DiscountOffer.DISCOUNT_TYPES,
    }
    return render(request, 'discounts/discount_offers_list.html', context)


@login_required
def discount_offer_delete(request, pk):
    offer = get_object_or_404(DiscountOffer, pk=pk)

    if request.method == 'POST':
        if not request.user.can_see_all_data() :
            messages.error(request, 'لا تملك صلاحية حذف هذا العرض.')
            return redirect('discount_offers_list')

        offer.delete()
        messages.success(request, 'تم حذف عرض التخفيض بنجاح.')
        return redirect('discount_offers_list')

    context = {
        'offer': offer,
        'title': 'حذف عرض تخفيض',
    }
    return render(request, 'discounts/discount_offer_delete.html', context)




@login_required
def inventory_full_report_pdf(request):
    import io
    import html
    from pathlib import Path
    from datetime import date
    from decimal import Decimal
    from collections import defaultdict

    from django.conf import settings
    from django.http import HttpResponse
    from django.utils import timezone

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        KeepTogether,
    )

    import arabic_reshaper
    from bidi.algorithm import get_display

    today = timezone.localdate()
    first_day = today.replace(day=1)

    try:
        date_from = date.fromisoformat(
            request.GET.get("date_from", first_day.isoformat())
        )
        date_to = date.fromisoformat(
            request.GET.get("date_to", today.isoformat())
        )
        if date_from > date_to:
            raise ValueError
    except (ValueError, TypeError):
        date_from, date_to = first_day, today

    branches = list(
        Branch.objects.all().order_by("-is_main", "name")
    )
    main_branch = Branch.get_main_branch()
    normal_branches = [
        branch for branch in branches if not branch.is_main
    ]

    font_path = (
        Path(settings.BASE_DIR)
        / "static"
        / "fonts"
        / "Amiri-Regular.ttf"
    )

    if not font_path.exists():
        return HttpResponse(
            "ملف الخط العربي غير موجود في static/fonts/Amiri-Regular.ttf",
            status=500,
            content_type="text/plain; charset=utf-8",
        )

    if "Amiri" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("Amiri", str(font_path)))

    def ar(value):
        value = html.escape(str(value if value is not None else ""))
        return get_display(arabic_reshaper.reshape(value))

    def money(value):
        return f"{float(value or 0):,.2f} د.ل"

    def number(value):
        return f"{float(value or 0):,.2f}"

    def quantity(value):
        return f"{float(value or 0):,.2f}"

    def decimal(value):
        return Decimal(str(value or 0))

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName="Amiri",
        fontSize=17,
        leading=24,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#1F3A5F"),
        spaceAfter=5,
    )

    heading_style = ParagraphStyle(
        "ReportHeading",
        parent=styles["Heading2"],
        fontName="Amiri",
        fontSize=12,
        leading=17,
        alignment=TA_RIGHT,
        textColor=colors.HexColor("#1F3A5F"),
        spaceBefore=5,
        spaceAfter=5,
    )

    normal_style = ParagraphStyle(
        "ReportNormal",
        parent=styles["Normal"],
        fontName="Amiri",
        fontSize=9,
        leading=13,
        alignment=TA_RIGHT,
    )

    cell_style = ParagraphStyle(
        "ReportCell",
        parent=normal_style,
        fontSize=8,
        leading=11,
    )

    header_style = ParagraphStyle(
        "ReportHeader",
        parent=cell_style,
        alignment=TA_CENTER,
        textColor=colors.white,
    )

    def p(value, style=cell_style):
        return Paragraph(ar(value), style)

    def make_table(headers, rows, widths):
        headers = list(reversed(headers))
        rows = [list(reversed(row)) for row in rows]
        widths = list(reversed(widths))

        data = [
            [p(value, header_style) for value in headers]
        ]

        for row in rows:
            data.append([
                value if isinstance(value, Paragraph) else p(value)
                for value in row
            ])

        table = Table(
            data,
            colWidths=widths,
            repeatRows=1,
            hAlign="CENTER",
        )

        table.setStyle(TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#2563EB"),
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.4,
                colors.HexColor("#D1D5DB"),
            ),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            (
                "ROWBACKGROUNDS",
                (0, 1),
                (-1, -1),
                [
                    colors.white,
                    colors.HexColor("#F3F6FA"),
                ],
            ),
        ]))

        return table

    story = []

    stock_by_branch = defaultdict(
        lambda: {
            "quantity": Decimal("0"),
            "cost": Decimal("0"),
            "sale": Decimal("0"),
        }
    )

    inventory = (
        BranchInventory.objects
        .filter(branch__in=branches)
        .select_related("branch", "product", "product__category")
        .order_by(
            "branch__name",
            "product__category__name",
            "product__name",
        )
    )

    for item in inventory.iterator():
        qty = decimal(item.quantity)
        cost_price = decimal(item.product.cost_price)
        selling_price = decimal(item.product.selling_price)

        data = stock_by_branch[item.branch_id]
        data["quantity"] += qty
        data["cost"] += qty * cost_price
        data["sale"] += qty * selling_price

    sales_by_branch = defaultdict(
        lambda: {
            "count": 0,
            "total": Decimal("0"),
            "delivery_total": Decimal("0"),
        }
    )

    sales_by_payment = defaultdict(
        lambda: {
            "count": 0,
            "total": Decimal("0"),
        }
    )

    sales = (
        SaleInvoice.objects
        .filter(
            branch__in=branches,
            status="confirmed",
            created_at__date__range=(date_from, date_to),
        )
        .select_related("branch", "payment_method")
        .only(
            "branch_id",
            "total",
            "payment_method_id",
            "payment_method__name",
            "is_delivery",
        )
    )

    for invoice in sales.iterator():
        amount = decimal(invoice.total)
        branch_data = sales_by_branch[invoice.branch_id]

        branch_data["count"] += 1
        branch_data["total"] += amount

        if invoice.is_delivery:
            branch_data["delivery_total"] += amount

        payment = invoice.payment_method
        payment_name = (
            getattr(payment, "name", None)
            or (str(payment) if payment else "غير محددة")
        )

        payment_data = sales_by_payment[
            (invoice.branch_id, payment_name)
        ]
        payment_data["count"] += 1
        payment_data["total"] += amount

    deliveries_by_branch = defaultdict(
        lambda: {
            "count": 0,
            "total": Decimal("0"),
            "cash": Decimal("0"),
            "bank_transfer": Decimal("0"),
        }
    )

    deliveries = BranchSalesDelivery.objects.filter(
        branch__in=branches,
        delivery_date__date__range=(date_from, date_to),
    ).only(
        "branch_id",
        "amount",
        "payment_method",
    )

    for delivery in deliveries.iterator():
        amount = decimal(delivery.amount)
        data = deliveries_by_branch[delivery.branch_id]

        data["count"] += 1
        data["total"] += amount

        if delivery.payment_method == "cash":
            data["cash"] += amount
        elif delivery.payment_method == "bank_transfer":
            data["bank_transfer"] += amount

    rewards_by_branch = defaultdict(
        lambda: {
            "count": 0,
            "points": Decimal("0"),
            "amount": Decimal("0"),
        }
    )

    rewards = CustomerLoyaltyReward.objects.filter(
        branch__in=branches,
        reward_date__date__range=(date_from, date_to),
    ).only(
        "branch_id",
        "points",
        "amount",
    )

    for reward in rewards.iterator():
        data = rewards_by_branch[reward.branch_id]
        data["count"] += 1
        data["points"] += decimal(reward.points)
        data["amount"] += decimal(reward.amount)

    story.append(p("تقرير الفروع والمخزون والمبيعات", title_style))
    story.append(p(
        f"الفترة: {date_from.isoformat()} إلى {date_to.isoformat()}",
        normal_style,
    ))
    story.append(Spacer(1, 5 * mm))

    story.append(p("1. قيمة المخزون الحالي لكل فرع", heading_style))

    stock_rows = []
    total_stock_sale = Decimal("0")

    for branch in branches:
        value = stock_by_branch[branch.id]["sale"]
        total_stock_sale += value
        stock_rows.append([branch.name, money(value)])

    stock_rows.append(["الإجمالي العام", money(total_stock_sale)])

    story.append(make_table(
        ["الفرع", "قيمة المخزون بسعر البيع"],
        stock_rows,
        [75 * mm, 75 * mm],
    ))
    story.append(Spacer(1, 7 * mm))

    def branch_summary_row(branch):
        stock = stock_by_branch[branch.id]
        sales_data = sales_by_branch[branch.id]
        delivery_data = deliveries_by_branch[branch.id]
        reward_data = rewards_by_branch[branch.id]

        total_sales = sales_data["total"]
        total_deliveries = delivery_data["total"]
        total_rewards = reward_data["amount"]
        remaining = total_sales - total_deliveries - total_rewards

        return [
            branch.name,
            money(stock["sale"]),
            money(total_sales),
            money(total_deliveries),
            money(total_rewards),
            money(remaining),
            number(branch.loyalty_points_inventory),
        ]

    summary_headers = [
        "الفرع",
        "قيمة المخزون بسعر البيع",
        "إجمالي المبيعات",
        "إجمالي التسليمات",
        "قيمة المكافآت",
        "المبلغ المتبقي",
        "رصيد النقاط الحالي",
    ]

    summary_widths = [
        35 * mm,
        38 * mm,
        34 * mm,
        34 * mm,
        34 * mm,
        38 * mm,
        34 * mm,
    ]

    story.append(p("2. ملخص الفروع", heading_style))

    normal_rows = [
        branch_summary_row(branch)
        for branch in normal_branches
    ]

    if not normal_rows:
        normal_rows = [[
            "لا توجد فروع",
            money(0),
            money(0),
            money(0),
            money(0),
            money(0),
            number(0),
        ]]

    story.append(make_table(
        summary_headers,
        normal_rows,
        summary_widths,
    ))

    story.append(Spacer(1, 7 * mm))
    story.append(p("3. توزيع مبيعات الفروع حسب طريقة الدفع", heading_style))

    payment_rows = []
    payment_total = Decimal("0")
    payment_count = 0

    for branch in branches:
        branch_has_payments = False

        for (branch_id, payment_name), data in sorted(
            sales_by_payment.items(),
            key=lambda item: (
                item[0][0],
                item[0][1].casefold(),
            ),
        ):
            if branch_id != branch.id:
                continue

            branch_has_payments = True
            payment_count += data["count"]
            payment_total += data["total"]

            payment_rows.append([
                branch.name,
                payment_name,
                str(data["count"]),
                money(data["total"]),
            ])

        if not branch_has_payments:
            payment_rows.append([
                branch.name,
                "لا توجد مبيعات",
                "0",
                money(0),
            ])

    payment_rows.append([
        "الإجمالي العام",
        "جميع طرق الدفع",
        str(payment_count),
        money(payment_total),
    ])

    story.append(make_table(
        ["الفرع", "طريقة الدفع", "عدد الفواتير", "إجمالي المبيعات"],
        payment_rows,
        [55 * mm, 50 * mm, 30 * mm, 45 * mm],
    ))

    story.append(Spacer(1, 7 * mm))
    story.append(p("4. تسليمات الفروع حسب طريقة التسليم", heading_style))

    delivery_rows = []
    grand_delivery_count = 0
    grand_delivery_cash = Decimal("0")
    grand_delivery_transfer = Decimal("0")
    grand_delivery_total = Decimal("0")

    for branch in branches:
        data = deliveries_by_branch[branch.id]

        grand_delivery_count += data["count"]
        grand_delivery_cash += data["cash"]
        grand_delivery_transfer += data["bank_transfer"]
        grand_delivery_total += data["total"]

        delivery_rows.append([
            branch.name,
            str(data["count"]),
            money(data["cash"]),
            money(data["bank_transfer"]),
            money(data["total"]),
        ])

    delivery_rows.append([
        "الإجمالي العام",
        str(grand_delivery_count),
        money(grand_delivery_cash),
        money(grand_delivery_transfer),
        money(grand_delivery_total),
    ])

    story.append(make_table(
        [
            "الفرع",
            "عدد التسليمات",
            "كاش",
            "تحويل بنكي",
            "إجمالي التسليمات",
        ],
        delivery_rows,
        [45 * mm, 30 * mm, 38 * mm, 38 * mm, 45 * mm],
    ))

    for branch in normal_branches:
        story.append(Spacer(1, 7 * mm))
        story.append(p(f"منتجات الفرع: {branch.name}", heading_style))

        branch_inventory = (
            BranchInventory.objects
            .filter(branch=branch)
            .select_related("product", "product__category")
            .order_by(
                "product__category__name",
                "product__name",
            )
        )

        product_rows = []
        total_quantity = Decimal("0")

        for item in branch_inventory:
            category_name = (
                item.product.category.name
                if item.product.category_id
                else "بدون فئة"
            )
            qty = decimal(item.quantity)
            total_quantity += qty

            product_rows.append([
                category_name,
                item.product.name,
                quantity(qty),
            ])

        if product_rows:
            product_rows.append([
                "الإجمالي",
                "",
                quantity(total_quantity),
            ])
        else:
            product_rows.append([
                "—",
                "لا توجد منتجات",
                "0.00",
            ])

        story.append(make_table(
            ["الفئة", "المنتج", "الكمية الحالية"],
            product_rows,
            [50 * mm, 85 * mm, 35 * mm],
        ))

    if main_branch:
        story.append(Spacer(1, 8 * mm))
        story.append(p(
            f"5. ملخص الفرع الرئيسي: {main_branch.name}",
            heading_style,
        ))
        story.append(make_table(
            summary_headers,
            [branch_summary_row(main_branch)],
            summary_widths,
        ))

        story.append(Spacer(1, 7 * mm))
        story.append(p(
            f"منتجات الفرع الرئيسي: {main_branch.name}",
            heading_style,
        ))

        main_inventory = (
            BranchInventory.objects
            .filter(branch=main_branch)
            .select_related("product", "product__category")
            .order_by(
                "product__category__name",
                "product__name",
            )
        )

        main_product_rows = []
        main_total_quantity = Decimal("0")

        for item in main_inventory:
            category_name = (
                item.product.category.name
                if item.product.category_id
                else "بدون فئة"
            )
            qty = decimal(item.quantity)
            main_total_quantity += qty

            main_product_rows.append([
                category_name,
                item.product.name,
                quantity(qty),
            ])

        if main_product_rows:
            main_product_rows.append([
                "الإجمالي",
                "",
                quantity(main_total_quantity),
            ])
        else:
            main_product_rows.append([
                "—",
                "لا توجد منتجات",
                "0.00",
            ])

        story.append(make_table(
            ["الفئة", "المنتج", "الكمية الحالية"],
            main_product_rows,
            [50 * mm, 85 * mm, 35 * mm],
        ))

    story.append(Spacer(1, 10 * mm))
    story.append(p("الإجماليات العامة", title_style))
    story.append(Spacer(1, 4 * mm))

    grand_stock_value = sum(
        (stock_by_branch[branch.id]["sale"] for branch in branches),
        Decimal("0"),
    )

    grand_points = sum(
        (
            decimal(branch.loyalty_points_inventory)
            for branch in branches
        ),
        Decimal("0"),
    )

    grand_sales = sum(
        (
            sales_by_branch[branch.id]["total"]
            for branch in normal_branches
        ),
        Decimal("0"),
    )

    grand_all_sales = sum(
        (
            sales_by_branch[branch.id]["total"]
            for branch in branches
        ),
        Decimal("0"),
    )

    grand_rewards = sum(
        (
            rewards_by_branch[branch.id]["amount"]
            for branch in branches
        ),
        Decimal("0"),
    )

    grand_delivery_sales = sum(
        (
            sales_by_branch[branch.id]["delivery_total"]
            for branch in branches
        ),
        Decimal("0"),
    )

    grand_remaining = sum(
        (
            sales_by_branch[branch.id]["total"]
            - deliveries_by_branch[branch.id]["total"]
            - rewards_by_branch[branch.id]["amount"]
            for branch in branches
        ),
        Decimal("0"),
    )

    grand_total_rows = [
        [
            "إجمالي قيمة المخزون بسعر البيع لجميع الفروع",
            money(grand_stock_value),
        ],
        [
            "إجمالي رصيد النقاط الحالي لجميع الفروع",
            number(grand_points),
        ],
        [
            "إجمالي المبيعات باستثناء الفرع الرئيسي",
            money(grand_sales),
        ],
        [
            "إجمالي مبيعات جميع الفروع",
            money(grand_all_sales),
        ],
        [
            "إجمالي مبيعات التوصيل لجميع الفروع",
            money(grand_delivery_sales),
        ],
        [
            "إجمالي تسليمات جميع الفروع",
            money(grand_delivery_total),
        ],
        [
            "إجمالي المبلغ المتبقي لجميع الفروع",
            money(grand_remaining),
        ],
        [
            "إجمالي قيمة المكافآت لجميع الفروع",
            money(grand_rewards),
        ],
    ]

    story.append(make_table(
        ["البيان", "الإجمالي"],
        grand_total_rows,
        [100 * mm, 65 * mm],
    ))

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=12 * mm,
        bottomMargin=14 * mm,
        title="تقرير الفروع والمخزون والمبيعات",
    )

    def page_number(canvas, document):
        canvas.saveState()
        canvas.setFont("Amiri", 8)
        canvas.drawCentredString(
            landscape(A4)[0] / 2,
            7 * mm,
            ar(f"صفحة {document.page}"),
        )
        canvas.restoreState()

    doc.build(
        story,
        onFirstPage=page_number,
        onLaterPages=page_number,
    )

    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/pdf",
    )
    response["Content-Disposition"] = (
        'attachment; filename="inventory_full_report.pdf"'
    )

    buffer.close()
    return response
