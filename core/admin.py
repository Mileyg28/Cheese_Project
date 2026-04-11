from django.contrib import admin
from .models import Product, Supplier


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "sale_pricing_type",
        "purchase_pricing_type",
        "is_active",
        "created_at",
    )
    list_filter = (
        "sale_pricing_type",
        "purchase_pricing_type",
        "is_active",
    )
    search_fields = ("name", "description")
    ordering = ("name",)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "document_number",
        "phone",
        "email",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active",)
    search_fields = ("name", "document_number", "phone", "email")
    ordering = ("name",)


from .models import SupplierProduct

@admin.register(SupplierProduct)
class SupplierProductAdmin(admin.ModelAdmin):
    list_display = (
        "supplier",
        "product",
        "kilos_per_basket",
        "default_purchase_price",
        "is_active",
    )
    list_filter = ("supplier", "is_active")
    search_fields = ("supplier__name", "product__name")



from django.contrib import admin
from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "document_number",
        "phone",
        "neighborhood",
        "email",
        "is_active",
        "created_at",
    )
    search_fields = (
        "name",
        "document_number",
        "phone",
        "email",
        "neighborhood",
    )
    list_filter = (
        "is_active",
        "neighborhood",
        "created_at",
    )
    ordering = ("name",)