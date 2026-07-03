from decimal import Decimal
from django import forms
from .models import ExpenseProvider  # añade al import existente

from .models import (
    Expense,
    Mensajero,
    Motorcycle,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchasePayment,
    SalesInvoice,
    SalesInvoiceItem,
    SalesPayment,
    SupplierProduct,
)
from django.forms import formset_factory, modelformset_factory


# ─────────────────────────────────────────
# COMPRAS
# ─────────────────────────────────────────

class PurchaseInvoiceForm(forms.ModelForm):
    is_paid = forms.BooleanField(
        required=False,
        label="Marcar como pagada",
        widget=forms.CheckboxInput(attrs={
            "class": "h-5 w-5 rounded border-2 border-slate-400 text-emerald-600 focus:ring-emerald-500",
        }),
    )
    class Meta:
        model = PurchaseInvoice
        fields = ["supplier", "invoice_date", "freight_cost", "notes"]  # ← quitar invoice_number
        widgets = {
            "supplier": forms.Select(attrs={
                "class": "w-full rounded-xl border border-slate-300 px-3 py-2"
            }),
            "invoice_date": forms.DateInput(format="%Y-%m-%d", attrs={
                "type": "date",
                "class": "w-full rounded-xl border border-slate-300 px-3 py-2"
            }),
            "freight_cost": forms.NumberInput(attrs={
                "step": "0.01",
                "min": "0",
                "class": "w-full rounded-xl border border-slate-300 px-3 py-2"
            }),
            "notes": forms.Textarea(attrs={
                "rows": 3,
                "class": "w-full rounded-xl border border-slate-300 px-3 py-2"
            }),
        }


class PurchaseInvoiceItemForm(forms.ModelForm):
    class Meta:
        model = PurchaseInvoiceItem
        fields = ["supplier_product", "basket_quantity", "block_quantity", "weight_kg"]
        widgets = {
            "supplier_product": forms.Select(attrs={
                "class": "w-full rounded-xl border border-slate-300 px-3 py-2"
            }),
            "basket_quantity": forms.NumberInput(attrs={
                "step": "0.01",
                "min": "0",
                "class": "w-full rounded-xl border border-slate-300 px-3 py-2"
            }),
            "block_quantity": forms.NumberInput(attrs={
                "step": "1",
                "min": "0",
                "placeholder": "0",
                "class": "w-full rounded-xl border border-slate-300 px-3 py-2"
            }),
            "weight_kg": forms.NumberInput(attrs={
                "step": "0.01",
                "min": "0",
                "class": "w-full rounded-xl border border-slate-300 px-3 py-2"
            }),
        }

    def __init__(self, *args, **kwargs):
        supplier = kwargs.pop("supplier", None)
        super().__init__(*args, **kwargs)
        self.fields["supplier_product"].queryset = SupplierProduct.objects.none()
        if supplier:
            self.fields["supplier_product"].queryset = SupplierProduct.objects.filter(
                supplier=supplier,
                is_active=True,
                product__is_active=True,
            ).select_related("product", "supplier")

    def clean_weight_kg(self):
        weight = self.cleaned_data.get("weight_kg")
        if weight is not None and weight < 0:
            raise forms.ValidationError("El peso no puede ser negativo.")
        return weight

    def clean_basket_quantity(self):
        baskets = self.cleaned_data.get("basket_quantity")
        if baskets is not None and baskets < 0:
            raise forms.ValidationError("La cantidad de canastas no puede ser negativa.")
        return baskets

class PurchasePaymentForm(forms.ModelForm):
    class Meta:
        model = PurchasePayment
        fields = ["payment_date", "amount", "notes"]
        widgets = {
            "payment_date": forms.DateInput(format="%Y-%m-%d", attrs={
                "type": "date",
                "class": "w-full rounded-xl border border-slate-300 px-3 py-2",
            }),
            "amount": forms.NumberInput(attrs={
                "step": "0.01",
                "min": "0.01",
                "class": "w-full rounded-xl border border-slate-300 px-3 py-2",
            }),
            "notes": forms.Textarea(attrs={
                "rows": 3,
                "class": "w-full rounded-xl border border-slate-300 px-3 py-2",
            }),
        }
 
    def __init__(self, *args, invoice=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._invoice = invoice
 
    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount is None or amount <= 0:
            raise forms.ValidationError("El valor del pago debe ser mayor que cero.")
        if self._invoice:
            from django.db.models import Sum as _Sum
            current_paid = (
                self._invoice.payments.exclude(pk=self.instance.pk)
                .aggregate(total=_Sum("amount"))
                .get("total") or Decimal("0.00")
            )
            remaining = self._invoice.total_amount - current_paid
            if amount > remaining:
                raise forms.ValidationError(
                    f"El pago no puede superar el saldo pendiente (${remaining:,.0f})."
                )
        return amount
 
# ─────────────────────────────────────────
# VENTAS
# ─────────────────────────────────────────

class SalesInvoiceForm(forms.ModelForm):
    # FIX: is_paid NO existe como campo en el modelo (es una @property).
    # Se declara aquí como campo de formulario explícito, fuera de Meta.fields.
    # La vista lo lee con: invoice_form.cleaned_data.get("is_paid", False)
    is_paid = forms.BooleanField(
        required=False,
        label="Marcar como pagada",
        widget=forms.CheckboxInput(attrs={
            "class": "h-5 w-5 rounded border-2 border-gray-400 text-blue-600 focus:ring-blue-500",
        }),
    )

    class Meta:
        model = SalesInvoice
        fields = [
            "invoice_number",
            "customer",
            "invoice_date",
            "mensajero",
            # notes eliminado
            # is_paid se declara arriba como campo explícito, NO va en esta lista
        ]
        widgets = {
            "invoice_number": forms.TextInput(attrs={
                "class": "w-full rounded-xl border-2 border-gray-400 px-3 py-2.5 text-base focus:border-blue-500 focus:outline-none",
                "maxlength": 4,
                "placeholder": "0001",
            }),
            "customer": forms.Select(attrs={
                "class": "w-full rounded-xl border-2 border-gray-400 px-3 py-2.5 text-base focus:border-blue-500 focus:outline-none",
            }),
            "mensajero": forms.Select(attrs={
                "class": "w-full rounded-xl border-2 border-gray-400 px-3 py-2.5 text-base focus:border-blue-500 focus:outline-none",
            }),
            "invoice_date": forms.DateInput(format="%Y-%m-%d", attrs={
                "type": "date",
                "class": "w-full rounded-xl border-2 border-gray-400 px-3 py-2.5 text-base focus:border-blue-500 focus:outline-none",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mensajero"].queryset = Mensajero.objects.filter(is_active=True)
        self.fields["mensajero"].empty_label = "— Sin mensajero —"
        self.fields["mensajero"].required = False


class SalesInvoiceItemForm(forms.ModelForm):
    class Meta:
        model = SalesInvoiceItem
        fields = ["product", "blocks", "weight_kg", "unit_price"]
        widgets = {
            "product": forms.Select(attrs={
                "class": "w-full rounded-xl border-2 border-gray-400 px-3 py-2.5 text-base focus:border-blue-500 focus:outline-none",
            }),
            "blocks": forms.NumberInput(attrs={
                "class": "w-full rounded-xl border-2 border-gray-400 px-3 py-2.5 text-base focus:border-blue-500 focus:outline-none",
                "min": "1",
            }),
            "weight_kg": forms.NumberInput(attrs={
                "class": "w-full rounded-xl border-2 border-gray-400 px-3 py-2.5 text-base focus:border-blue-500 focus:outline-none",
                "step": "0.01",
                "min": "0",
            }),
            "unit_price": forms.NumberInput(attrs={
                "class": "w-full rounded-xl border-2 border-gray-400 px-3 py-2.5 text-base focus:border-blue-500 focus:outline-none",
                "step": "0.01",
                "min": "0",
            }),
        }

SalesInvoiceItemFormSet = formset_factory(
    SalesInvoiceItemForm,
    extra=0,
    min_num=1,
    validate_min=True,
)

# Formset para EDITAR (con instancias del modelo, soporta DELETE)
SalesInvoiceItemModelFormSet = modelformset_factory(
    SalesInvoiceItem,
    form=SalesInvoiceItemForm,
    extra=0,
    can_delete=True,
)


# ─────────────────────────────────────────
# PAGOS
# ─────────────────────────────────────────

class SalesPaymentForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        self.invoice = kwargs.pop("invoice", None)
        super().__init__(*args, **kwargs)

    def fmt(self, n):
        return f"{int(round(float(n))):,}".replace(",", ".")

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount is None:
            return amount
        if amount <= 0:
            raise forms.ValidationError("El valor del pago debe ser mayor que cero.")
        if self.invoice and amount > self.invoice.balance_due:
            raise forms.ValidationError(
                f"El pago (${self.fmt(amount)}) no puede superar el saldo pendiente (${self.fmt(self.invoice.balance_due)})."
            )
        return amount

    class Meta:
        model = SalesPayment
        fields = ["payment_date", "amount", "notes"]
        widgets = {
            "payment_date": forms.DateInput(format="%Y-%m-%d", attrs={
                "type": "date",
                "class": "w-full rounded-xl border-2 border-slate-300 px-3 py-2.5 text-sm focus:border-emerald-500 focus:outline-none transition",
            }),
            "amount": forms.NumberInput(attrs={
                "step": "any",
                "min": "1",
                "placeholder": "0",
                "class": "w-full rounded-xl border-2 border-slate-300 px-3 py-2.5 text-sm focus:border-emerald-500 focus:outline-none transition",
            }),
            "notes": forms.Textarea(attrs={
                "rows": 3,
                "placeholder": "Ej: Pago en efectivo, transferencia…",
                "class": "w-full rounded-xl border-2 border-slate-300 px-3 py-2.5 text-sm focus:border-emerald-500 focus:outline-none transition resize-none",
            }),
        }
#---------------GASTOS

class ExpenseProviderForm(forms.ModelForm):
    class Meta:
        model = ExpenseProvider
        fields = ["name", "nit", "address", "phone", "email"]
        widgets = {
            "name": forms.TextInput(attrs={
                "placeholder": "Ej: Supermercado XYZ S.A.S.",
                "class": "w-full rounded-xl border-2 border-slate-300 px-3 py-2.5 text-sm "
                         "focus:border-rose-500 focus:outline-none transition",
            }),
            "nit": forms.TextInput(attrs={
                "placeholder": "Ej: 900123456-7",
                "class": "w-full rounded-xl border-2 border-slate-300 px-3 py-2.5 text-sm "
                         "focus:border-rose-500 focus:outline-none transition",
            }),
            "address": forms.TextInput(attrs={
                "class": "w-full rounded-xl border-2 border-slate-300 px-3 py-2.5 text-sm "
                         "focus:border-rose-500 focus:outline-none transition",
            }),
            "phone": forms.TextInput(attrs={
                "class": "w-full rounded-xl border-2 border-slate-300 px-3 py-2.5 text-sm "
                         "focus:border-rose-500 focus:outline-none transition",
            }),
            "email": forms.EmailInput(attrs={
                "class": "w-full rounded-xl border-2 border-slate-300 px-3 py-2.5 text-sm "
                         "focus:border-rose-500 focus:outline-none transition",
            }),
        }


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = [
            "provider", "category", "motorcycle",
            "expense_date", "subtotal", "applies_iva", "description",
        ]
        widgets = {
            "provider": forms.Select(attrs={
                "id": "id_provider",
                "class": "w-full rounded-xl border-2 border-slate-300 px-3 py-2.5 text-sm "
                         "focus:border-rose-500 focus:outline-none transition",
            }),
            "category": forms.Select(attrs={
                "id": "id_category",
                "class": "w-full rounded-xl border-2 border-slate-300 px-3 py-2.5 text-sm "
                         "focus:border-rose-500 focus:outline-none transition",
            }),
            "motorcycle": forms.Select(attrs={
                "id": "id_motorcycle",
                "class": "w-full rounded-xl border-2 border-slate-300 px-3 py-2.5 text-sm "
                         "focus:border-rose-500 focus:outline-none transition",
            }),
            "expense_date": forms.DateInput(attrs={
                "type": "date",
                "class": "w-full rounded-xl border-2 border-slate-300 px-3 py-2.5 text-sm "
                         "focus:border-rose-500 focus:outline-none transition",
            }),
            "subtotal": forms.NumberInput(attrs={
                "id": "id_subtotal",
                "step": "1", "min": "1", "placeholder": "0",
                "class": "w-full rounded-xl border-2 border-slate-300 pl-7 pr-3 py-2.5 text-sm "
                        "focus:border-rose-500 focus:outline-none transition",
            }),
            "applies_iva": forms.CheckboxInput(attrs={
                "id": "id_applies_iva",
                "class": "h-5 w-5 rounded border-2 border-slate-400 text-rose-600 focus:ring-rose-500",
            }),
            "description": forms.Textarea(attrs={
                "rows": 3,
                "placeholder": "Detalle de la compra (ej: 5 cajas de bolsas, recibo #1234)…",
                "class": "w-full rounded-xl border-2 border-slate-300 px-3 py-2.5 text-sm "
                         "focus:border-rose-500 focus:outline-none transition resize-none",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["motorcycle"].queryset = Motorcycle.objects.filter(is_active=True)
        self.fields["motorcycle"].required = False
        self.fields["motorcycle"].empty_label = "— Selecciona una moto —"
        self.fields["description"].required = False
        self.fields["provider"].queryset = ExpenseProvider.objects.filter(is_active=True)
        self.fields["provider"].required = False
        self.fields["provider"].empty_label = "— Sin proveedor / Selecciona —"

    def clean(self):
        cleaned_data = super().clean()
        category   = cleaned_data.get("category")
        motorcycle = cleaned_data.get("motorcycle")
        if category == Expense.CAT_FUEL and not motorcycle:
            self.add_error("motorcycle", "Debes seleccionar la moto para gastos de gasolina.")
        if category != Expense.CAT_FUEL and motorcycle:
            self.add_error("motorcycle", "La moto solo aplica para gastos de gasolina.")
        return cleaned_data
        