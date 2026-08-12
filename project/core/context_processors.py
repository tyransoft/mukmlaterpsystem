from django.utils import timezone
from datetime import timedelta
from .models import CompanySettings,Branch, ProductExpiry

def company_settings(request):
    return {
        'company_settings': CompanySettings.get_settings()
    }

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
    warning_records = expiry_records.filter(expiry_date__gte=today, expiry_date__lte=three_months_later).count()
    return {
        'warning_records': warning_records
        }
