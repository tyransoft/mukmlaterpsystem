from django.urls import path
from .views import *




urlpatterns = [

    path('accounts/login/', login_view, name='user_login'),
    path('logout/', logout_view, name='logout'),
    path('users/', users_list, name='users_list'),
    path('users/create/', user_create, name='user_create'),
    path('users/<int:pk>/edit/', user_edit, name='user_edit'),
    path('users/<int:pk>/delete/', user_delete, name='user_delete'),
    path('profile/', profile, name='profile'),
    
    path('branches/', branch_list, name='branches_list'),
    path('branches/create/', branch_create, name='branches_create'),
    path('branches/<int:pk>/', branch_detail, name='branches_detail'),
    path('branches/<int:pk>/edit/', branch_edit, name='branches_edit'),
    path('branches/<int:pk>/delete/', branch_delete, name='branches_delete'),
    path('branches/<int:pk>/sales-delivery/', branch_sales_delivery, name='branch_sales_delivery'),
    path('branches/delivery-receipt/<int:pk>/', branch_delivery_receipt, name='branch_delivery_receipt'),
    path('branches/<int:pk>/deliveries-history/', branch_deliveries_history, name='branch_deliveries_history'),
    path('branches/<int:pk>/sales-report/', branch_sales_report, name='branch_sales_report'),
    path('branch/adjust-points/<int:pk>/', branch_adjust_points, name='branch_adjust_points'),

    path('customers/', customer_list, name='customers_list'),
    path('customers/create/', customer_create, name='customers_create'),
    path('customers/<int:pk>/', customer_detail, name='customers_detail'),
    path('customers/<int:pk>/edit/', customer_edit, name='customers_edit'),
    path('customers/search/', customer_search_ajax, name='customers_search_ajax'),    
    path('customers/<int:pk>/payment/', customer_payment_create, name='customer_payment_create'),
    path('customers/payment-receipt/<int:pk>/', customer_payment_receipt, name='customer_payment_receipt'),
    path('customers/<int:pk>/payments/', customer_payments_history, name='customer_payments_history'),


    path('', home, name='dashboard_home'),
    path('dashboard/main/', main_dashboard, name='dashboard_main'),
    path('dashboard/branch/', branch_dashboard, name='dashboard_branch'),
    path('dashboard/accountant/', accountant_dashboard, name='dashboard_accountant'),

    path('inventory/', inventory_list, name='inventory_list'),
    path('inventory/movements/', inventory_movements, name='inventory_movements'),
    path('inventory/low-stock/', low_stock_alerts, name='inventory_low_stock'),
    path('inventory/report/', inventory_report, name='inventory_report'),
    path('ajax/stock/', get_branch_stock_ajax, name='stock_ajax'),
    path('inventory/print/<int:branch_id>/', inventory_print, name='inventory_print'),
    path('inventory/stocktake/', inventory_stocktake, name='inventory_stocktake'),
    path('inventory/damage/<int:pk>/', inventory_damage, name='inventory_damage'),

    path('loyalty/', pending_transfers, name='loyalty_pending'),
    path('loyalty/<int:pk>/mark-transferred/', mark_transferred, name='loyalty_mark_transferred'),
    path('loyalty/mark-all/', mark_all_transferred, name='loyalty_mark_all'),
    path('loyalty/history/', transfer_history, name='loyalty_history'),

    path('products/', product_list, name='products_list'),
    path('products/create/', product_create, name='products_create'),
    path('products/<int:pk>/', product_detail, name='products_detail'),
    path('products/<int:pk>/edit/', product_edit, name='products_edit'),
    path('products/<int:pk>/delete/', product_delete, name='products_delete'),
    path('categories/', category_list, name='categories'),
    path('categories/create/', category_create, name='category_create'),
    path('products/search/', product_search_ajax, name='search_ajax'),
    path('products/bulk-price-update/', products_bulk_price_update, name='products_bulk_price_update'),
    path('products/expiry/', product_expiry_list, name='product_expiry_list'),
    path('products/expiry/create/', product_expiry_create, name='product_expiry_create'),
    path('products/expiry/edit/<int:pk>/', product_expiry_edit, name='product_expiry_edit'),
    path('products/expiry/delete/<int:pk>/', product_expiry_delete, name='product_expiry_delete'),
    path('products/expiry/consume/<int:pk>/', product_expiry_consume, name='product_expiry_consume'),
    path('products/expiry/movements/<int:pk>/', product_expiry_movements, name='product_expiry_movements'),
    path('products/expiry/dashboard/', product_expiry_dashboard, name='product_expiry_dashboard'),

    path('suppliers/', supplier_list, name='supplier_list'),
    path('suppliers/create/', supplier_create, name='supplier_create'),
    path('suppliers/<int:pk>/', supplier_detail, name='supplier_detail'),
    path('suppliers/<int:pk>/edit/', supplier_edit, name='supplier_edit'),
    path('suppliers/<int:pk>/delete/', supplier_delete, name='supplier_delete'),
    path('suppliers/search/ajax/', supplier_search_ajax, name='supplier_search_ajax'),
    path('suppliers/<int:supplier_id>/payment/create/', supplier_payment_create, name='supplier_payment_create'),
    path('suppliers/<int:supplier_id>/payments/', supplier_payment_list, name='supplier_payment_list'),
    path('suppliers/payment/<int:payment_id>/delete/', supplier_payment_delete, name='supplier_payment_delete'),
    path('suppliers/payment/<int:payment_id>/invoice/', supplier_payment_invoice, name='supplier_payment_invoice'),
    
    path('sales/', sale_invoices_list, name='sale_invoices_list'),
    path('sales/create/', sale_invoice_create, name='sale_invoice_create'),
    path('sales/<int:pk>/', sale_invoice_detail, name='sale_invoice_detail'),
    path('sales/<int:pk>/confirm/', sale_invoice_confirm, name='sale_invoice_confirm'),
    path('sales/<int:pk>/cancel/', sale_invoice_cancel, name='sale_invoice_cancel'),
    path('sales/<int:pk>/print/', sale_invoice_print, name='sale_invoice_print'),
    path('invoices/return/<int:pk>/', sale_invoice_return, name='sale_invoice_return'),

    path('purchases/', purchase_invoices_list, name='purchase_invoices_list'),
    path('purchases/create/', purchase_invoice_create, name='purchase_invoice_create'),
    path('purchases/<int:pk>/', purchase_invoice_detail, name='purchase_invoice_detail'),
    path('purchases/<int:pk>/confirm/', purchase_invoice_confirm, name='purchase_invoice_confirm'),
    path('purchases/<int:pk>/print/', purchase_invoice_print, name='purchase_invoice_print'),
    path('api/products-stock/', api_products_stock, name='api_products_stock'),

    path('payment-methods/', payment_methods_list, name='payment_methods_list'),
    path('payment-methods/create/', payment_method_create, name='payment_method_create'),
    path('payment-methods/<int:pk>/edit/', payment_method_edit, name='payment_method_edit'),
    path('payment-methods/<int:pk>/delete/', payment_method_delete, name='payment_method_delete'),
    path('payment-methods/<int:pk>/toggle-status/', payment_method_toggle_status, name='payment_method_toggle_status'),

]



