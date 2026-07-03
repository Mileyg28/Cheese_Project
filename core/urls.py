from django.urls import path
from django.contrib.auth import views as auth_views
from core.views import home  
from . import views

urlpatterns = [

    # Auth
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path("purchases/create/", views.create_purchase_invoice, name="create_purchase_invoice"),
    path("purchases/<int:pk>/add-payment/", views.add_purchase_payment, name="add_purchase_payment"),
    path("purchases/<int:pk>/", views.purchase_invoice_detail, name="purchase_invoice_detail"),
    path("purchases/<int:pk>/edit/", views.edit_purchase_invoice, name="edit_purchase_invoice"),
    path("ajax/supplier-products/", views.get_supplier_products, name="get_supplier_products"),
    path("sales/invoices/create/", views.create_sales_invoice, name="create_sales_invoice"),
    path("sales/invoices/<int:pk>/", views.sales_invoice_detail, name="sales_invoice_detail"),
    path("sales/invoices/<int:pk>/edit/", views.edit_sales_invoice, name="edit_sales_invoice"),
    path("sales/invoices/<int:pk>/add-payment/",views.add_sales_payment,name="add_sales_payment",),
    path("expenses/",views.expense_list,   name="expense_list"),
    path("expenses/create/", views.create_expense, name="create_expense"),
    path("", views.home, name="home"),
    path("reporte/", views.period_report, name="period_report"),
    path("gastos/proveedores/", views.expense_provider_list, name="expense_provider_list"),
    path("gastos/proveedores/nuevo/", views.create_expense_provider, name="create_expense_provider"),
    path("clientes/", views.customer_list, name="customer_list"),
    path("clientes/<int:pk>/actualizar-campo/", views.update_customer_field, name="update_customer_field"),
]