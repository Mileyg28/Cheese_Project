from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User, Group
from django import forms

from .models import Customer, Mensajero, Product, Supplier, SupplierProduct


# ── Custom user creation form ──────────────────────────────────────────────────

class CustomUserCreationForm(forms.ModelForm):
    username = forms.CharField(
        label="Username",
        max_length=150,
    )
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput,
    )
    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput,
    )
    role = forms.ChoiceField(
        label="Role",
        choices=[
            ("administrator", "Administrator"),
            ("operator", "Operator"),
        ],
    )

    class Meta:
        model = User
        fields = ("username",)

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords do not match.")
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            role = self.cleaned_data["role"]
            group = Group.objects.get(name=role)
            user.groups.add(group)
        return user


# ── Custom UserAdmin ───────────────────────────────────────────────────────────

class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "password1", "password2", "role"),
        }),
    )

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    list_display = ("username", "email", "get_role", "is_active")
    list_filter = ("groups", "is_active")

    def get_role(self, obj):
        if obj.is_superuser:
            return "Superuser"
        groups = obj.groups.values_list("name", flat=True)
        return ", ".join(groups) if groups else "—"

    get_role.short_description = "Role"


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


# ── Product ───────────────────────────────────────────────────────────────────

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


# ── Supplier ──────────────────────────────────────────────────────────────────

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


# ── Supplier product ──────────────────────────────────────────────────────────

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


# ── Customer ──────────────────────────────────────────────────────────────────

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

# ── Mensajero ─────────────────────────────────────────────────────────────────
 
@admin.register(Mensajero)
class MensajeroAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "phone")
    ordering = ("name",)