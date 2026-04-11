import json

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.db import transaction

from .forms import PurchaseInvoiceForm, PurchaseInvoiceItemForm, SalesInvoiceForm, SalesInvoiceItemForm, SalesInvoiceItemFormSet
from .models import Product, PurchaseInvoice, SalesInvoice, SalesPayment, Supplier, SupplierProduct

from django.db.models import Sum
from decimal import Decimal

def home(request):
    purchase_invoices = PurchaseInvoice.objects.select_related("supplier").order_by("-invoice_date", "-id")
    sales_invoices = SalesInvoice.objects.select_related("customer").order_by("-invoice_date", "-id")

    context = {
        "purchase_invoices": purchase_invoices,
        "sales_invoices": sales_invoices,
        "total_purchase_invoices": purchase_invoices.count(),
        "total_sales_invoices": sales_invoices.count(),
        "total_purchased": purchase_invoices.aggregate(total=Sum("total_amount")).get("total") or Decimal("0.00"),
        "total_sold": sales_invoices.aggregate(total=Sum("total_amount")).get("total") or Decimal("0.00"),
    }
    return render(request, "core/purchases/home.html", context)


def create_purchase_invoice(request):
    supplier_id = request.GET.get("supplier") or request.POST.get("supplier")
    selected_supplier = None

    if supplier_id:
        selected_supplier = get_object_or_404(Supplier, pk=supplier_id, is_active=True)

    if request.method == "POST":
        invoice_form = PurchaseInvoiceForm(request.POST)
        item_form = PurchaseInvoiceItemForm(request.POST, supplier=selected_supplier)

        if invoice_form.is_valid() and item_form.is_valid():
            invoice = invoice_form.save(commit=False)

            # Generar número automático
            last = PurchaseInvoice.objects.order_by("-id").first()
            next_number = (int(last.invoice_number) + 1) if last and last.invoice_number.isdigit() else 1
            invoice.invoice_number = str(next_number)

            invoice.save()

            item = item_form.save(commit=False)
            item.invoice = invoice
            item.save()

            messages.success(request, f"Factura de compra #{invoice.invoice_number} creada correctamente.")
            return redirect("create_purchase_invoice")
    else:
        initial = {}
        if selected_supplier:
            initial["supplier"] = selected_supplier.id

        invoice_form = PurchaseInvoiceForm(initial=initial)
        item_form = PurchaseInvoiceItemForm(supplier=selected_supplier)

    context = {
        "invoice_form": invoice_form,
        "item_form": item_form,
        "selected_supplier": selected_supplier,
    }
    return render(request, "core/purchases/create_purchase_invoice.html", context)

# Ajax para obtener los productos de un proveedor
def get_supplier_products(request):
    supplier_id = request.GET.get("supplier_id")

    if not supplier_id:
        return JsonResponse({"products": []})

    supplier_products = SupplierProduct.objects.filter(
        supplier_id=supplier_id,
        is_active=True,
        product__is_active=True,
    ).select_related("product")

    products = [
        {
            "id": sp.id,
            "name": sp.product.name,
            "price_per_kilo": str(sp.default_purchase_price),
            "kilos_per_basket": str(sp.kilos_per_basket or "0.00"),
        }
        for sp in supplier_products
    ]

    return JsonResponse({"products": products})


# vista para la factura de venta
@transaction.atomic
def create_sales_invoice(request):
    if request.method == "POST":
        invoice_form = SalesInvoiceForm(request.POST)
        item_formset = SalesInvoiceItemFormSet(request.POST, prefix="items")

        if invoice_form.is_valid() and item_formset.is_valid():
            is_paid = invoice_form.cleaned_data.get("is_paid", False)

            invoice = invoice_form.save(commit=False)
            invoice.subtotal = 0
            invoice.total_amount = 0
            invoice.amount_paid = 0
            invoice.balance_due = 0
            invoice.save()

            for form in item_formset:
                if form.cleaned_data:
                    item = form.save(commit=False)
                    item.invoice = invoice
                    item.save()

            invoice.refresh_from_db()
            invoice.update_totals()

            if is_paid and invoice.total_amount > 0:
                SalesPayment.objects.create(
                    invoice=invoice,
                    payment_date=invoice.invoice_date,
                    amount=invoice.total_amount,
                    notes="Pago registrado automáticamente al crear la factura.",
                )
                invoice.refresh_from_db()

            messages.success(request, "Factura de venta creada correctamente.")
            return redirect("sales_invoice_detail", pk=invoice.pk)

    else:
        invoice_form = SalesInvoiceForm()
        item_formset = SalesInvoiceItemFormSet(prefix="items")

    # Corre en GET y en POST con errores
    products_data = {
    str(p.id): {
        "pricing_type": p.sale_pricing_type,
        "requires_weight": p.requires_weight,
        "requires_blocks": p.requires_blocks,
        "kg_per_block": float(p.kg_per_block) if p.kg_per_block else None,
    }
    for p in Product.objects.filter(is_active=True)
}

    context = {
        "invoice_form": invoice_form,
        "item_formset": item_formset,
        "products_data": json.dumps(products_data),
    }
    return render(request, "core/purchases/create_sales_invoice.html", context)


def sales_invoice_detail(request, pk):
    invoice = get_object_or_404(
        SalesInvoice.objects.select_related("customer").prefetch_related("items__product"),
        pk=pk,
    )
    return render(request, "core/purchases/sales_invoice_detail.html", {"invoice": invoice})


#VISTA PARA INGRESAR UN PAGO

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from .forms import SalesPaymentForm
from .models import SalesInvoice


def add_sales_payment(request, pk):
    invoice = get_object_or_404(
        SalesInvoice.objects.select_related("customer"),
        pk=pk,
    )

    if request.method == "POST":
        form = SalesPaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.invoice = invoice
            payment.save()
            messages.success(request, "Pago registrado correctamente.")
            return redirect("sales_invoice_detail", pk=invoice.pk)
    else:
        form = SalesPaymentForm()

    context = {
        "invoice": invoice,
        "form": form,
    }
    return render(request, "core/purchases/add_sales_payment.html", context)